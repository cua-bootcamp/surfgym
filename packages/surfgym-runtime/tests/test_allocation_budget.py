import asyncio
from types import SimpleNamespace

import pytest
from surfgym_contracts.protocol.gateway_to_upstream import GatewayAllocateRequest
from surfgym_contracts.protocol.upstream_to_gateway import MasterAllocateResponse
from surfgym_contracts.task import Website
from surfgym_runtime.gateway import transport as gateway_transport
from surfgym_runtime.gateway.error import Deadline, TimeOutError
from surfgym_runtime.wavepool.allocation_budget import (
    ALLOCATION_REMAINING_HEADER,
    parse_remaining_seconds,
)
from surfgym_runtime.wavepool.instance import service as instance_service
from surfgym_runtime.wavepool.instance.error import InstanceError
from surfgym_runtime.wavepool.instance.service import PlaywrightBrowserWorker
from surfgym_runtime.wavepool.instance.session import Context, PageLayout
from surfgym_runtime.wavepool.master import service as master_service
from surfgym_runtime.wavepool.master import transport as master_transport
from surfgym_runtime.wavepool.master.error import AllocationDispatchedError
from surfgym_runtime.wavepool.master.service import MasterService
from surfgym_runtime.wavepool.master.transport import InstanceClient
from surfgym_contracts.protocol.upstream_to_gateway import InstanceAllocateResponse


@pytest.mark.parametrize("value", ["", "zero", "0", "-1", "nan", "inf"])
def test_remaining_header_rejects_non_finite_or_non_positive_values(value: str) -> None:
    with pytest.raises(ValueError):
        parse_remaining_seconds(value)


def test_master_client_serializes_relative_remaining_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def request(*_args: object, **kwargs: object) -> MasterAllocateResponse:
        captured.update(kwargs)
        return MasterAllocateResponse(context_id="ctx", instance_host="host", instance_port=1)

    monkeypatch.setattr(gateway_transport, "_request_model", request)
    gateway_transport.MasterClient("host", 1).allocate(
        websites=[Website(website_id="site", url="http://site")],
        allocate_hooks=[],
        release_hooks=[],
        timeout=3.0,
        remaining_seconds=0.75,
    )

    assert captured["timeout"] == 3.0
    assert parse_remaining_seconds(captured["headers"][ALLOCATION_REMAINING_HEADER]) == pytest.approx(0.75)  # type: ignore[index]


def test_gateway_rejects_allocate_when_no_gap_can_be_reserved() -> None:
    transport = object.__new__(gateway_transport.GatewayTransport)
    transport._timeouts = SimpleNamespace(allocate=10.0, layer_gap=1.0)
    transport._master_client = SimpleNamespace(allocate=lambda **_kwargs: pytest.fail("must not dispatch"))

    with pytest.raises(TimeOutError):
        transport.allocate(
            deadline=Deadline(__import__("time").monotonic() + 0.01, "allocate"),
            websites=[Website(website_id="site", url="http://site")],
            allocate_hooks=[],
            release_hooks=[],
        )


def test_instance_client_forwards_budget_after_response_gap(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    async def post(*_args: object, **kwargs: object) -> object:
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(master_transport, "_post", post)
    monkeypatch.setattr(master_transport, "_handle_response", lambda *_args: InstanceAllocateResponse())
    client = InstanceClient("host", SimpleNamespace(allocate=10.0, layer_gap=1.0))

    asyncio.run(client.allocate(
        1,
        "ctx",
        GatewayAllocateRequest(websites=[Website(website_id="site", url="http://site")], hooks=[]),
        timeout=4.0,
        remaining_seconds=3.0,
    ))

    assert captured["timeout"] == 4.0
    assert parse_remaining_seconds(captured["headers"][ALLOCATION_REMAINING_HEADER]) == pytest.approx(3.0)  # type: ignore[index]


class _Registry:
    def __init__(self, *, delay: float = 0.0) -> None:
        self.enqueued: list[str] = []
        self.delay = delay

    async def reserve_lease(self, context_id: str | None, *_args: object):
        await asyncio.sleep(self.delay)
        return SimpleNamespace(context_id=context_id or "ctx", port_slot=SimpleNamespace(port=11))

    async def enqueue_release(self, context_id: str, _request: object) -> None:
        self.enqueued.append(context_id)


class _InstanceClient:
    def __init__(self) -> None:
        self.remaining_seconds: float | None = None

    async def allocate(
        self, *_args: object, timeout: float, remaining_seconds: float
    ) -> None:
        self.remaining_seconds = remaining_seconds


def _master(registry: _Registry, client: _InstanceClient) -> MasterService:
    master = object.__new__(MasterService)
    master.config = SimpleNamespace(host="host", process_timeout=SimpleNamespace(allocate=10.0, layer_gap=1.0))
    master.client = client
    master.registry = registry
    master._release_wakeup = asyncio.Event()
    return master


def test_master_charges_local_elapsed_time_before_instance_dispatch() -> None:
    registry, client = _Registry(delay=0.02), _InstanceClient()
    master = _master(registry, client)

    asyncio.run(master.allocate(
        GatewayAllocateRequest(websites=[Website(website_id="site", url="http://site")], hooks=[]),
        incoming_remaining_seconds=2.0,
    ))

    assert client.remaining_seconds is not None
    assert 0 < client.remaining_seconds < 1.0
    assert registry.enqueued == []


def test_expired_master_budget_enqueues_existing_lease() -> None:
    registry, client = _Registry(delay=0.02), _InstanceClient()
    master = _master(registry, client)

    with pytest.raises(AllocationDispatchedError, match="expired before Instance dispatch"):
        asyncio.run(master.allocate(
            GatewayAllocateRequest(context_id="ctx", websites=[Website(website_id="site", url="http://site")], hooks=[]),
            incoming_remaining_seconds=0.001,
        ))

    assert registry.enqueued == ["ctx"]


class _Page:
    def __init__(self) -> None:
        self.timeout: float | None = None

    async def goto(self, _url: str, **kwargs: object):
        self.timeout = kwargs.get("timeout")  # type: ignore[assignment]
        return None


class _ContextManager:
    def __init__(self, page: _Page, *, delay: float = 0.0) -> None:
        layout = PageLayout(x=0, y=0, width=100, height=100)
        self.context = Context("ctx", object(), {"site": (page, layout)}, "site")  # type: ignore[arg-type]
        self._entries = {"ctx": SimpleNamespace(native_bindings={}, web_bindings={})}
        self.delay = delay

    async def create(self, *_args: object) -> None:
        await asyncio.sleep(self.delay)

    def require_context(self, *_args: object, **_kwargs: object):
        return self.context

    def require_page(self, *_args: object, **_kwargs: object):
        return self.context.pages["site"]

    async def activate(self, *_args: object) -> None:
        return None


def _worker(page: _Page, *, delay: float = 0.0) -> PlaywrightBrowserWorker:
    worker = PlaywrightBrowserWorker(contexts_per_instance=1)
    worker.ctx_manager = _ContextManager(page, delay=delay)  # type: ignore[assignment]
    return worker


def test_instance_passes_shrunk_relative_budget_to_goto() -> None:
    page = _Page()

    asyncio.run(_worker(page, delay=0.02).allocate(
        "ctx", [Website(website_id="site", url="http://site")], [], incoming_remaining_seconds=1.0
    ))

    assert page.timeout is not None
    assert 0 < page.timeout < 1000.0


def test_instance_rejects_expired_budget_before_goto() -> None:
    page = _Page()

    with pytest.raises(InstanceError, match="expired before navigation"):
        asyncio.run(_worker(page, delay=0.02).allocate(
            "ctx", [Website(website_id="site", url="http://site")], [], incoming_remaining_seconds=0.001
        ))

    assert page.timeout is None
