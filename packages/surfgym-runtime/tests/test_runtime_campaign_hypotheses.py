"""Bounded characterization tests for the 2026-09-06 runtime campaign."""

import asyncio
import tracemalloc
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image
from surfgym_contracts.protocol.gateway_to_upstream import (
    GatewayAllocateRequest,
    GatewayReleaseRequest,
)
from surfgym_contracts.task import Website
from surfgym_runtime.gateway.registry import Lease, SessionRegistry, SessionState
from surfgym_runtime.support.cua_evaluator import evaluate_cua_reward
from surfgym_runtime.wavepool.instance.service import PlaywrightBrowserWorker
from surfgym_runtime.wavepool.master.registry import LeaseRegistry
from surfgym_runtime.wavepool.master.service import MasterService


def _request() -> GatewayAllocateRequest:
    return GatewayAllocateRequest(
        websites=[Website(website_id="fixture", url="http://fixture.test")], hooks=[]
    )


def _master(registry: LeaseRegistry, client: object) -> MasterService:
    master = object.__new__(MasterService)
    master.client = client
    master.registry = registry
    master._release_wakeup = asyncio.Event()
    return master


class _BlockedAllocationClient:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.released: list[str] = []

    async def allocate(self, _port: int, context_id: str, _request: GatewayAllocateRequest) -> None:
        self.context_id = context_id
        self.started.set()
        await asyncio.Event().wait()

    async def release(self, context_id: str, _port: int, _request: GatewayReleaseRequest) -> None:
        self.released.append(context_id)


def test_h1_cancelled_allocate_enqueues_its_reserved_lease() -> None:
    """Would fail if cancellation can leave the only slot permanently reserved."""

    async def scenario() -> tuple[list[str], bool]:
        registry = LeaseRegistry(instance_start_port=5400, instance_n=1, contexts_per_instance=1)
        client = _BlockedAllocationClient()
        task = asyncio.create_task(_master(registry, client).allocate(_request()))
        await client.started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        return (
            [pending.context_id for pending in await registry.pending_releases()],
            await registry.reserve_lease() is None,
        )

    pending, capacity_is_stranded = asyncio.run(scenario())
    assert pending or not capacity_is_stranded, (
        f"cancel cleanup lost: pending={pending!r}, capacity_is_stranded={capacity_is_stranded}"
    )


class _SerialReleaseClient:
    def __init__(self) -> None:
        self.first_started = asyncio.Event()
        self.second_started = asyncio.Event()
        self.allow_first = asyncio.Event()

    async def release(self, context_id: str, _port: int, _request: GatewayReleaseRequest) -> None:
        if not self.first_started.is_set():
            self.first_started.set()
            await self.allow_first.wait()
        else:
            self.second_started.set()


def test_h2_release_all_dispatches_independent_leases_without_head_of_line_blocking() -> None:
    """A blocked cleanup must not delay another lease while release slots remain."""

    async def scenario() -> None:
        registry = LeaseRegistry(instance_start_port=5400, instance_n=2, contexts_per_instance=1)
        first = await registry.reserve_lease()
        second = await registry.reserve_lease()
        assert first is not None and second is not None
        await registry.enqueue_release(first.context_id)
        await registry.enqueue_release(second.context_id)
        client = _SerialReleaseClient()
        task = asyncio.create_task(_master(registry, client).release_all())
        await client.first_started.wait()
        await asyncio.sleep(0)
        assert client.second_started.is_set()
        client.allow_first.set()
        await task

    asyncio.run(scenario())


class _Page:
    async def screenshot(self) -> bytes:
        image = Image.new("RGB", (20, 10), color=(0, 0, 0))
        output = BytesIO()
        image.save(output, format="PNG")
        return output.getvalue()


@dataclass
class _Layout:
    x: int
    y: int


class _Cursor:
    def to_screen_cursor(self, _layout: _Layout) -> SimpleNamespace:
        return SimpleNamespace(x=0, y=0)


def test_h5_screenshot_has_fixed_wait_and_composites_pages_into_screen_geometry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Characterizes the fixed wait and page-by-page compositing without browser timing claims."""

    async def no_wait(seconds: float) -> None:
        assert seconds == 1

    worker = PlaywrightBrowserWorker(contexts_per_instance=1)
    page = _Page()
    layout = _Layout(x=0, y=0)
    context = SimpleNamespace(
        context_id="ctx", pages={"a": (page, layout)}, active_page_id="a", cursor=_Cursor()
    )
    monkeypatch.setattr(asyncio, "sleep", no_wait)
    monkeypatch.setattr(worker.ctx_manager, "require_context", lambda _context_id: context)
    monkeypatch.setattr(worker.ctx_manager, "require_page", lambda _context_id, _page_id: (page, layout))

    image, x, y = asyncio.run(worker.screenshot("ctx"))

    assert Image.open(image).size == (1920, 1080)
    assert (x, y) == (0, 0)


def test_h6_trace_count_cap_retains_distinct_payload_bytes_until_session_end() -> None:
    """Would fail if trace trimming also imposed a byte budget or discarded retained frames."""

    state = SessionState(task_id="task", lease=Lease(context_id="ctx", port=5400), release_hooks=[])
    tracemalloc.start()
    for index in range(100):
        payload = f"{index:06d}" + "a" * 65_530
        state.append_frame(kind="action", image_b64=payload, media_type="image/png")
    registry = SessionRegistry()
    registry.reserve_session(7)
    registry.start_session(7, state)

    assert len(state.trace) == 50
    assert sum(len(frame.image_b64) for frame in state.trace) == 50 * 65_536
    assert [frame.step for frame in state.trace] == list(range(50, 100))
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert peak_bytes >= 50 * 65_536
    registry.end_session(7)
    assert registry.session_states == {}


def test_h8_imported_reward_can_read_a_run_owned_marker_via_pathlib(tmp_path: Path) -> None:
    """Characterizes the documented trusted-ingestion boundary using only a test marker."""

    marker = tmp_path / "marker.txt"
    marker.write_text("run-owned-marker", encoding="utf-8")
    source = f"from pathlib import Path\nprint(Path({str(marker)!r}).read_text())\nprint('REWARD: 1')\n"

    # The evaluator budget remains tested below with a one-second hung child.
    # This successful cross-process characterization permits Windows interpreter
    # startup under a saturated full suite.
    result = evaluate_cua_reward(source, source_task_id="campaign", sid="sid", snapshots={}, timeout=5)

    assert result.reward == 1
    assert "run-owned-marker" in result.stdout


def test_h8_reward_timeout_returns_for_a_hung_child() -> None:
    with pytest.raises(__import__("subprocess").TimeoutExpired):
        evaluate_cua_reward("while True: pass", source_task_id="campaign", sid="sid", snapshots={}, timeout=1)


def test_h8_moderate_stdout_is_returned_without_a_byte_cap() -> None:
    result = evaluate_cua_reward(
        "print('x' * 131072)\nprint('REWARD: 1')",
        source_task_id="campaign",
        sid="sid",
        snapshots={},
        timeout=5,
    )

    assert len(result.stdout) >= 131_072
