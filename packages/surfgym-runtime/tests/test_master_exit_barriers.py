from __future__ import annotations

import asyncio

import httpx
import pytest

from surfgym_contracts.protocol.gateway_to_upstream import GatewayReleaseRequest
from surfgym_contracts.protocol.upstream_to_gateway import MasterReleaseResponse
from surfgym_runtime.wavepool.instance import server as instance_server
from surfgym_runtime.wavepool.instance import service as instance_service
from surfgym_runtime.wavepool.instance.service import NativeBinding, PlaywrightBrowserWorker
from surfgym_runtime.wavepool.instance.session import ContextEntry, ContextPhase
from surfgym_runtime.wavepool.master.registry import Lease, LeaseRegistry
from surfgym_runtime.wavepool.master.service import MasterService
from surfgym_runtime.wavepool.master.transport import _handle_response


def _master(registry: LeaseRegistry, client: object) -> MasterService:
    master = object.__new__(MasterService)
    master.registry = registry
    master.client = client
    master._release_wakeup = asyncio.Event()
    master._release_tasks = {}
    master._release_semaphore = asyncio.Semaphore(4)
    return master


def test_held_retired_finalizer_does_not_stop_healthy_sibling_progress() -> None:
    class Client:
        def __init__(self) -> None:
            self.retained_started = asyncio.Event()
            self.allow_retained = asyncio.Event()
            self.healthy_completed = asyncio.Event()
            self.released: list[str] = []

        async def release_retained_bindings(self, _lease: Lease) -> None:
            self.retained_started.set()
            await self.allow_retained.wait()

        async def release(self, context_id: str, _port: int, _request: GatewayReleaseRequest) -> None:
            self.released.append(context_id)
            self.healthy_completed.set()

    async def scenario() -> None:
        registry = LeaseRegistry(instance_start_port=5400, instance_n=2, contexts_per_instance=1)
        retired = await registry.reserve_lease("retired")
        healthy = await registry.reserve_lease("healthy")
        assert retired is not None and healthy is not None
        await registry.retire_port(retired.port_slot.port, quiescent=True)
        await registry.enqueue_release(healthy.context_id)
        client = Client()
        master = _master(registry, client)

        releasing = asyncio.create_task(master.release_all())
        try:
            await asyncio.wait_for(client.retained_started.wait(), timeout=1)
            await asyncio.wait_for(client.healthy_completed.wait(), timeout=1)
            assert client.released == [healthy.context_id]
            assert [pending.context_id for pending in await registry.pending_releases()] == ["retired"]
            successor = await registry.reserve_lease("healthy-successor")
            assert successor is not None and successor.port_slot.port == healthy.port_slot.port
        finally:
            client.allow_retained.set()
            await asyncio.wait_for(releasing, timeout=1)
        assert await registry.pending_releases() == []

    asyncio.run(scenario())


def test_unknown_quiescence_blocks_retained_cleanup_until_proven_then_runs_once() -> None:
    class Client:
        def __init__(self) -> None:
            self.calls: list[str] = []

        async def release_retained_bindings(self, lease: Lease) -> None:
            self.calls.append(lease.context_id)

    async def scenario() -> None:
        registry = LeaseRegistry(instance_start_port=5400, instance_n=1, contexts_per_instance=1)
        lease = await registry.reserve_lease("retained")
        assert lease is not None
        client = Client()
        master = _master(registry, client)

        await master.recover_instance_exit(lease.port_slot.port, quiescent=False)
        await master.release_all()
        assert client.calls == []
        assert [pending.context_id for pending in await registry.pending_releases()] == [lease.context_id]

        await master.recover_instance_exit(lease.port_slot.port, quiescent=True)
        await master.recover_instance_exit(lease.port_slot.port, quiescent=False)
        await master.release_all()
        await master.release_all()
        assert client.calls == [lease.context_id]
        assert await registry.pending_releases() == []
        assert await registry.reserve_lease("successor") is None

    asyncio.run(scenario())


@pytest.mark.filterwarnings("ignore:Setting per-request cookies=.*:DeprecationWarning")
def test_instance_asgi_incomplete_release_503_keeps_master_pending_until_completed(
    monkeypatch,
) -> None:
    class AsgiClient:
        def __init__(self, app) -> None:
            self.client = httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://instance.test"
            )
            self.status_codes: list[int] = []

        async def release(self, context_id: str, _port: int, request: GatewayReleaseRequest):
            response = await self.client.post(
                "/release", params={"context_id": context_id}, json=request.model_dump(mode="json")
            )
            self.status_codes.append(response.status_code)
            return _handle_response(response, MasterReleaseResponse, "release", 5400)

        async def close(self) -> None:
            await self.client.aclose()

    async def scenario() -> None:
        worker = PlaywrightBrowserWorker(contexts_per_instance=1)
        binding = NativeBinding(
            context_id="context-id",
            website_id="native",
            origin="http://native.test",
            session_id=None,
            app=None,
            cleanup_capability="test-capability",
        )
        worker.ctx_manager._entries["context-id"] = ContextEntry(
            phase=ContextPhase.CLOSING, native_bindings={"native": binding}
        )
        monkeypatch.setattr(instance_server, "PlaywrightBrowserWorker", lambda **_kwargs: worker)
        app = instance_server.create_app(contexts_per_instance=1)
        client = AsgiClient(app)
        downstream_calls = 0

        def downstream(request: httpx.Request) -> httpx.Response:
            nonlocal downstream_calls
            downstream_calls += 1
            if downstream_calls == 1:
                return httpx.Response(200, json={"ok": False, "cleanup_complete": False})
            return httpx.Response(200, json={"ok": True, "cleanup_complete": True})

        real_async_client = httpx.AsyncClient

        def downstream_client_factory(*, timeout: float) -> httpx.AsyncClient:
            assert timeout == instance_service.DEFAULT_BINDING_CLEANUP_REQUEST_TIMEOUT_SECONDS
            return real_async_client(transport=httpx.MockTransport(downstream))

        monkeypatch.setattr(instance_service.httpx, "AsyncClient", downstream_client_factory)
        registry = LeaseRegistry(instance_start_port=5400, instance_n=1, contexts_per_instance=1)
        lease = await registry.reserve_lease("context-id")
        assert lease is not None
        await registry.enqueue_release(lease.context_id)
        master = _master(registry, client)
        try:
            await master.release_all()
            assert client.status_codes == [200]
            assert downstream_calls == 2
            assert worker.ctx_manager._entries[lease.context_id].phase is ContextPhase.CLOSED
            assert await registry.pending_releases() == []
            successor = await registry.reserve_lease("successor")
            assert successor is not None and successor.port_slot.port == lease.port_slot.port
            assert await registry.reserve_lease("second-successor") is None
        finally:
            await client.close()

    asyncio.run(scenario())
