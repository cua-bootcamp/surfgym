"""1 instance x 1 context: happy-path lifecycle, verified white-box.

Unlike test_1x1_success.py (which only observes gateway HTTP responses),
this test drives `MasterService`/`LeaseRegistry` directly in this same
process and asserts on their internal dicts after each step. This is only
possible because master is *not* spawned as a subprocess here -- a real
subprocess is a separate OS process with its own memory, so there is no way
(patch or otherwise) to reach into a `LeaseRegistry` living inside it. A real
`instance` server is still spawned as a subprocess, since it needs a real
Playwright browser.

No source code is modified: `MasterService`/`LeaseRegistry` are the exact
same classes master/server.py's `create_app()` uses, just imported and
driven directly instead of behind uvicorn + HTTP.
"""

from __future__ import annotations

import pytest
from surfgym_contracts.protocol.gateway_to_upstream import (
    GatewayAllocateRequest,
    GatewayReleaseRequest,
)
from surfgym_contracts.task import Website
from surfgym_runtime.support import ProcessTimeout, WavepoolConfig
from surfgym_runtime.wavepool.master.registry import LeaseRegistry
from surfgym_runtime.wavepool.master.service import MasterService


async def _log_transport_request(request) -> None:
    print(f"[transport→instance] {request.method} {request.url}")


async def _log_transport_response(response) -> None:
    await response.aread()
    print(f"[transport←instance] {response.status_code} {response.text}")


def _dump_registry(label: str, registry: LeaseRegistry) -> None:
    print(
        f"[registry:{label}] "
        f"lease={list(registry._lease.keys())} "
        f"pending_releases={list(registry._pending_releases.keys())} "
        f"slot0.allocated={registry._slots[0]._allocated_contexts}"
    )


def _wavepool_config(*, host: str, instance_start_port: int) -> WavepoolConfig:
    return WavepoolConfig(
        host=host,
        master_port=0,  # unused: master never binds its own HTTP server here
        instance_start_port=instance_start_port,
        instances=1,
        contexts_per_instance=1,
        process_timeout=ProcessTimeout(
            allocate=30.0,
            release=30.0,
            screenshot=30.0,
            observe=30.0,
            execute=15.0,
            layer_gap=1.0,
        ),
    )


@pytest.mark.asyncio
async def test_success_scenario_via_registry(real_instance, static_site_url):
    host, port = real_instance(contexts_per_instance=1)

    registry = LeaseRegistry(instance_start_port=port, instance_n=1, contexts_per_instance=1)
    master = MasterService(registry, _wavepool_config(host=host, instance_start_port=port))
    # master.client is InstanceClient, which holds the real httpx.AsyncClient
    # actually talking to the real instance subprocess. Hooking it here is
    # only possible because master runs in *this* process, not a subprocess.
    master.client.client.event_hooks = {
        "request": [_log_transport_request],
        "response": [_log_transport_response],
    }
    allocate_request = GatewayAllocateRequest(
        websites=[Website(url=static_site_url)], allocate_hooks=[]
    )

    try:
        _dump_registry("초기 상태", registry)

        # allocate: real instance call happens here (real Playwright context
        # created), and we can look directly at the registry afterward.
        response = await master.allocate(allocate_request)
        _dump_registry("allocate #1 이후", registry)
        assert len(registry._lease) == 1
        assert response.context_id in registry._lease
        assert registry._lease[response.context_id].port_slot.port == port
        assert registry._lease[response.context_id].port_slot._allocated_contexts == 1

        # release: accepted into _pending_releases, but *not yet* applied --
        # this is exactly the "gateway forgot, master/instance still
        # remembers" window from the ledger transition table.
        await master.release(response.context_id, GatewayReleaseRequest(release_hooks=[]))
        _dump_registry("release 접수 (release_all 전)", registry)
        assert response.context_id in registry._pending_releases
        assert response.context_id in registry._lease  # still occupied

        # release_all: this is what release_loop calls every ~10s (or on
        # wakeup). It's the only step that actually calls the real instance
        # and, on success, pops both dicts and frees the PortSlot counter.
        await master.release_all()
        _dump_registry("release_all 이후", registry)
        assert response.context_id not in registry._pending_releases
        assert response.context_id not in registry._lease
        assert registry._slots[0]._allocated_contexts == 0

        # slot reusable: a fresh allocate gets a brand-new context_id and the
        # registry reflects exactly one occupied slot again (no leftover
        # bookkeeping from the previous lease).
        response2 = await master.allocate(allocate_request)
        _dump_registry("allocate #2 이후", registry)
        assert response2.context_id != response.context_id
        assert len(registry._lease) == 1
        assert registry._slots[0]._allocated_contexts == 1

        await master.release(response2.context_id, GatewayReleaseRequest(release_hooks=[]))
        await master.release_all()
        _dump_registry("최종 정리 확인", registry)
        assert len(registry._lease) == 0
        assert len(registry._pending_releases) == 0
    finally:
        await master.close()
