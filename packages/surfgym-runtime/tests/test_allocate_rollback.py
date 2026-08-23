import asyncio
import time
from types import SimpleNamespace
from typing import Any, Callable

import pytest
from pytest import MonkeyPatch
from surfgym_contracts.protocol.gateway_to_upstream import GatewayAllocateRequest
from surfgym_contracts.protocol.upstream_to_gateway import MasterAllocateResponse
from surfgym_contracts.task import Hook, Website
from surfgym_runtime.gateway import service as gateway_service
from surfgym_runtime.gateway import transport as gateway_transport
from surfgym_runtime.gateway.error import Deadline, RetryableError
from surfgym_runtime.gateway.service import Service
from surfgym_runtime.wavepool.master.registry import LeaseRegistry
from surfgym_runtime.wavepool.master.service import MasterService


def _website() -> Website:
    return Website(website_id="fixture", url="http://fixture.test")


def _release_hook() -> Hook:
    return Hook(website_id="fixture", timing="before", script="releaseFixture()")


def _deadline_factory(expires_in: float) -> Callable[[str], Deadline]:
    expires_at = time.monotonic() + expires_in
    return lambda context: Deadline(expires_at, context)


def test_allocate_request_defaults_release_hooks_to_empty() -> None:
    request = GatewayAllocateRequest(websites=[_website()], hooks=[])

    assert request.release_hooks == []


def test_gateway_allocate_forwards_release_hooks_to_transport() -> None:
    release_hook = _release_hook()

    class RecordingTransport:
        def __init__(self) -> None:
            self.release_hooks: list[Hook] | None = None

        def allocate(
            self,
            *,
            deadline: Deadline,
            websites: list[Website],
            allocate_hooks: list[Hook],
            release_hooks: list[Hook],
        ) -> MasterAllocateResponse:
            self.release_hooks = release_hooks
            return MasterAllocateResponse(
                context_id="context-id",
                instance_host="127.0.0.1",
                instance_port=5400,
            )

    transport = RecordingTransport()
    service: Any = object.__new__(Service)
    service.transport = transport
    service.process_timeout = SimpleNamespace(allocate=1.0)

    service._allocate(
        _deadline_factory(5.0),
        [_website()],
        [],
        [release_hook],
    )

    assert transport.release_hooks == [release_hook]


def test_master_client_serializes_release_hooks_in_allocate_request(
    monkeypatch: MonkeyPatch,
) -> None:
    release_hook = _release_hook()
    sent_json: dict[str, object] = {}

    def record_request(
        _url: str,
        _response_schema: object,
        *,
        operation: str,
        timeout: float,
        **kwargs: object,
    ) -> MasterAllocateResponse:
        assert operation == "master.allocate"
        assert timeout == 1.0
        sent_json.update(kwargs["json"])  # type: ignore[arg-type]
        return MasterAllocateResponse(
            context_id="context-id",
            instance_host="127.0.0.1",
            instance_port=5400,
        )

    monkeypatch.setattr(gateway_transport, "_request_model", record_request)
    client = gateway_transport.MasterClient(host="master.test", port=53000)

    client.allocate(
        websites=[_website()],
        allocate_hooks=[],
        release_hooks=[release_hook],
        timeout=1.0,
    )

    assert sent_json["release_hooks"] == [release_hook.model_dump(mode="json")]


class _FailedAllocationClient:
    def __init__(self) -> None:
        self.context_ids: set[str] = set()
        self.allocate_request: GatewayAllocateRequest | None = None
        self.release_hooks: list[Hook] = []

    async def allocate(
        self,
        _port: int,
        context_id: str,
        request: GatewayAllocateRequest,
    ) -> None:
        self.context_ids.add(context_id)
        self.allocate_request = request
        raise RuntimeError("initial navigation failed")

    async def release(self, context_id: str, _port: int, request: object) -> None:
        self.release_hooks = request.hooks  # type: ignore[attr-defined]
        self.context_ids.remove(context_id)

    async def live_context_ids(self, _port: int) -> set[str]:
        return set(self.context_ids)


def _master_with_failed_allocation_client() -> tuple[
    MasterService, LeaseRegistry, _FailedAllocationClient
]:
    registry = LeaseRegistry(instance_start_port=5400, instance_n=1, contexts_per_instance=1)
    client = _FailedAllocationClient()
    master: Any = object.__new__(MasterService)
    master.config = SimpleNamespace(host="127.0.0.1")
    master.client = client
    master.registry = registry
    master._release_wakeup = asyncio.Event()
    return master, registry, client


def test_failed_allocate_forwards_and_enqueues_release_hooks() -> None:
    master, registry, client = _master_with_failed_allocation_client()
    release_hook = _release_hook()
    request = GatewayAllocateRequest(
        websites=[_website()],
        hooks=[],
        release_hooks=[release_hook],
    )

    with pytest.raises(RuntimeError, match="initial navigation failed"):
        asyncio.run(master.allocate(request))

    pending = asyncio.run(registry.pending_releases())
    assert client.allocate_request == request
    assert [item.release_request.hooks for item in pending] == [[release_hook]]


def test_failed_allocate_cleanup_removes_context_and_releases_capacity() -> None:
    master, registry, client = _master_with_failed_allocation_client()
    release_hook = _release_hook()
    request = GatewayAllocateRequest(
        websites=[_website()],
        hooks=[],
        release_hooks=[release_hook],
    )

    with pytest.raises(RuntimeError, match="initial navigation failed"):
        asyncio.run(master.allocate(request))

    asyncio.run(master.release_all())

    assert client.context_ids == set()
    assert client.release_hooks == [release_hook]
    assert asyncio.run(registry.pending_releases()) == []
    assert asyncio.run(registry.reserve_lease()) is not None


def test_allocate_retry_uses_remaining_deadline_when_less_than_configured_timeout(
    monkeypatch: MonkeyPatch,
) -> None:
    class CapacityRetryTransport:
        def __init__(self) -> None:
            self.attempt_timeouts: list[float] = []

        def allocate(
            self,
            *,
            deadline: Deadline,
            websites: list[Website],
            allocate_hooks: list[Hook],
            release_hooks: list[Hook],
        ) -> MasterAllocateResponse:
            self.attempt_timeouts.append(deadline.timeout_for(10.0))
            if len(self.attempt_timeouts) == 1:
                raise RetryableError("No available instance at the moment")
            return MasterAllocateResponse(
                context_id="context-id",
                instance_host="127.0.0.1",
                instance_port=5400,
            )

    monkeypatch.setattr(gateway_service, "jittered_backoff", lambda: iter([0.0]))
    transport = CapacityRetryTransport()
    service: Any = object.__new__(Service)
    service.transport = transport
    service.process_timeout = SimpleNamespace(allocate=10.0)

    result = service._allocate(
        _deadline_factory(1.0),
        [_website()],
        [],
        [_release_hook()],
    )

    assert result == ("context-id", 5400)
    assert len(transport.attempt_timeouts) == 2
    assert all(0 < timeout < 10.0 for timeout in transport.attempt_timeouts)
