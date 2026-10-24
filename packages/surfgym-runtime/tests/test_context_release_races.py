from __future__ import annotations

import asyncio
from contextlib import suppress

import pytest
from surfgym_contracts.task import Website
from surfgym_runtime.wavepool.instance.error import InstanceError, InstanceNotIdle
from surfgym_runtime.wavepool.instance import service as instance_service
from surfgym_runtime.wavepool.instance.service import NativeBinding, PlaywrightBrowserWorker
from surfgym_runtime.wavepool.instance.service import WebBinding
from surfgym_runtime.wavepool.instance.session import Context, ContextManager, ContextPhase


class _Page:
    async def close(self) -> None: return None


class _BrowserContext:
    def __init__(self) -> None:
        self.close_calls = 0
        self.closed = False
    async def close(self) -> None:
        self.close_calls += 1; self.closed = True


def _worker() -> tuple[PlaywrightBrowserWorker, ContextManager, _BrowserContext]:
    manager = ContextManager(contexts_per_instance=1, vw=100, vh=100)
    browser = _BrowserContext()
    manager._contexts["ctx"] = Context("ctx", browser, {"native": (_Page(), None)}, "native", ("native",))  # type: ignore[arg-type]
    worker = PlaywrightBrowserWorker(contexts_per_instance=1)
    worker.ctx_manager = manager
    worker._native_bindings["ctx"] = NativeBinding("ctx", "native", "http://native.test", None, None, "cap")
    return worker, manager, browser


def test_cancelled_release_waiter_does_not_cancel_shared_cleanup() -> None:
    async def scenario() -> None:
        worker, manager, _browser = _worker()
        started, allow = asyncio.Event(), asyncio.Event(); calls = 0
        async def cleanup(_binding: NativeBinding, **_kwargs: object) -> None:
            nonlocal calls; calls += 1; started.set(); await asyncio.wait_for(allow.wait(), 1)
        worker._release_native_binding = cleanup  # type: ignore[method-assign]
        first = asyncio.create_task(worker.release("ctx", []))
        second = asyncio.create_task(worker.release("ctx", []))
        try:
            await asyncio.wait_for(started.wait(), 1)
            first.cancel()
            with pytest.raises(asyncio.CancelledError): await first
            assert not second.done() and calls == 1
            allow.set(); await asyncio.wait_for(second, 1)
            assert calls == 1 and manager._entries["ctx"].phase is ContextPhase.CLOSED
        finally:
            allow.set()
            for task in (first, second):
                if not task.done(): task.cancel()
                with suppress(asyncio.CancelledError, InstanceError): await task
    asyncio.run(scenario())


def test_cancelled_waiter_retry_joins_one_bounded_native_cleanup_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The request waiter may expire while its retained cleanup owner runs."""
    class Response:
        status_code = 200
        content = b"{}"

        @staticmethod
        def json() -> dict[str, bool]:
            return {"ok": True, "cleanup_complete": True}

    class DeferredClient:
        def __init__(self, *, timeout: float | None = None) -> None:
            self.timeout = timeout

        async def __aenter__(self) -> "DeferredClient":
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def post(self, *_args: object, **_kwargs: object) -> Response:
            posts.append(self.timeout)
            started.set()
            await allow_finish.wait()
            return Response()

    async def scenario() -> None:
        worker, manager, _browser = _worker()
        first = asyncio.create_task(worker.release("ctx", []))
        second: asyncio.Task[None] | None = None
        try:
            await asyncio.wait_for(started.wait(), 1)
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(first, timeout=0.05)

            second = asyncio.create_task(worker.release("ctx", []))
            await asyncio.sleep(0)
            assert not second.done()
            assert posts == [instance_service.DEFAULT_BINDING_CLEANUP_REQUEST_TIMEOUT_SECONDS]

            allow_finish.set()
            await asyncio.wait_for(second, 1)
            assert posts == [instance_service.DEFAULT_BINDING_CLEANUP_REQUEST_TIMEOUT_SECONDS]
            assert manager._entries["ctx"].phase is ContextPhase.CLOSED
        finally:
            allow_finish.set()
            for task in (first, second):
                if task is not None and not task.done():
                    task.cancel()
                if task is not None:
                    with suppress(asyncio.CancelledError, InstanceError):
                        await task

    started, allow_finish = asyncio.Event(), asyncio.Event()
    posts: list[float | None] = []
    monkeypatch.setattr(instance_service.httpx, "AsyncClient", DeferredClient)
    asyncio.run(scenario())


def test_native_cleanup_poll_retry_retains_one_owner_until_terminal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Response:
        status_code = 200
        content = b"{}"

        @staticmethod
        def json() -> dict[str, bool]:
            return {"ok": True, "cleanup_complete": True}

    class Client:
        def __init__(self, *, timeout: float) -> None:
            assert timeout == instance_service.DEFAULT_BINDING_CLEANUP_REQUEST_TIMEOUT_SECONDS

        async def __aenter__(self) -> "Client":
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def post(self, *_args: object, **_kwargs: object) -> Response:
            calls.append(1)
            if len(calls) == 1:
                raise instance_service.httpx.ReadTimeout("poll timed out")
            second_poll_started.set()
            await allow_terminal.wait()
            return Response()

    async def scenario() -> None:
        worker, manager, _browser = _worker()
        worker.binding_cleanup_retry_interval_seconds = 0.001
        first = asyncio.create_task(worker.release("ctx", []))
        try:
            await asyncio.wait_for(second_poll_started.wait(), 1)
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(first, timeout=0.05)

            retained = manager._entries["ctx"].release_task
            assert retained is not None and not retained.done()
            retry = asyncio.create_task(worker.release("ctx", []))
            await asyncio.sleep(0)
            assert calls == [1, 1]
            assert manager._entries["ctx"].release_task is retained

            allow_terminal.set()
            await asyncio.wait_for(retry, 1)
            assert manager._entries["ctx"].phase is ContextPhase.CLOSED
        finally:
            allow_terminal.set()
            if not first.done():
                first.cancel()
            with suppress(asyncio.CancelledError, InstanceError):
                await first

    calls: list[int] = []
    second_poll_started, allow_terminal = asyncio.Event(), asyncio.Event()
    monkeypatch.setattr(instance_service.httpx, "AsyncClient", Client)
    asyncio.run(scenario())


def test_fast_unknown_retries_past_two_calls_on_same_owner_and_capability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Response:
        content = b"{}"

        def __init__(self, complete: bool) -> None:
            self.status_code = 200 if complete else 503
            self.complete = complete

        def json(self) -> dict[str, bool]:
            return {"ok": self.complete, "cleanup_complete": self.complete}

    class Client:
        def __init__(self, *, timeout: float) -> None:
            timeouts.append(timeout)

        async def __aenter__(self) -> "Client":
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def post(self, *_args: object, **kwargs: object) -> Response:
            payloads.append(kwargs["json"])
            if len(payloads) < 3:
                return Response(False)
            third_started.set()
            await allow_terminal.wait()
            return Response(True)

    async def scenario() -> None:
        worker, manager, _browser = _worker()
        worker.binding_cleanup_horizon_seconds = 1.0
        worker.binding_cleanup_request_timeout_seconds = 0.2
        worker.binding_cleanup_retry_interval_seconds = 0.001
        first = asyncio.create_task(worker.release("ctx", []))
        try:
            await asyncio.wait_for(third_started.wait(), 1)
            retained = manager._entries["ctx"].release_task
            retry = asyncio.create_task(worker.release("ctx", []))
            await asyncio.sleep(0)
            assert manager._entries["ctx"].release_task is retained
            assert len(payloads) == 3
            assert payloads == [payloads[0]] * 3
            assert payloads[0]["cleanup_capability"] == "cap"
            allow_terminal.set()
            await asyncio.wait_for(asyncio.gather(first, retry), 1)
            assert manager._entries["ctx"].phase is ContextPhase.CLOSED
        finally:
            allow_terminal.set()
            if not first.done():
                first.cancel()
            with suppress(asyncio.CancelledError, InstanceError):
                await first

    payloads: list[object] = []
    timeouts: list[float] = []
    third_started, allow_terminal = asyncio.Event(), asyncio.Event()
    monkeypatch.setattr(instance_service.httpx, "AsyncClient", Client)
    asyncio.run(scenario())


def test_native_cleanup_request_timeout_is_clamped_to_remaining_owner_horizon(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Response:
        content = b"{}"

        def __init__(self, complete: bool) -> None:
            self.status_code = 200 if complete else 503
            self.complete = complete

        def json(self) -> dict[str, bool]:
            return {"ok": self.complete, "cleanup_complete": self.complete}

    class Client:
        def __init__(self, *, timeout: float) -> None:
            timeouts.append(timeout)

        async def __aenter__(self) -> "Client": return self
        async def __aexit__(self, *_args: object) -> None: return None
        async def post(self, *_args: object, **_kwargs: object) -> Response:
            return Response(len(timeouts) > 1)

    async def scenario() -> None:
        worker, manager, _browser = _worker()
        worker.binding_cleanup_horizon_seconds = 0.2
        worker.binding_cleanup_request_timeout_seconds = 0.15
        worker.binding_cleanup_retry_interval_seconds = 0.1
        await worker.release("ctx", [])
        assert manager._entries["ctx"].phase is ContextPhase.CLOSED

    timeouts: list[float] = []
    monkeypatch.setattr(instance_service.httpx, "AsyncClient", Client)
    asyncio.run(scenario())
    assert timeouts[0] == 0.15
    assert 0 < timeouts[1] < 0.15


def test_native_cleanup_horizon_replays_unknown_without_redispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Client:
        def __init__(self, **_kwargs: object) -> None:
            return None

        async def __aenter__(self) -> "Client":
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def post(self, *_args: object, **_kwargs: object) -> object:
            calls.append(1)
            raise instance_service.httpx.ReadTimeout("poll timed out")

    async def scenario() -> None:
        worker, manager, _browser = _worker()
        worker.binding_cleanup_horizon_seconds = 0.02
        worker.binding_cleanup_request_timeout_seconds = 0.001
        with pytest.raises(InstanceError, match="confirmation is UNKNOWN"):
            await worker.release("ctx", [])
        retained = manager._entries["ctx"].release_task
        assert retained is not None and retained.done()
        calls_at_horizon = len(calls)
        assert manager._entries["ctx"].phase is ContextPhase.CLOSING

        with pytest.raises(InstanceError, match="confirmation is UNKNOWN"):
            await worker.release("ctx", [])
        assert manager._entries["ctx"].release_task is retained
        assert len(calls) == calls_at_horizon

    calls: list[int] = []
    monkeypatch.setattr(instance_service.httpx, "AsyncClient", Client)
    asyncio.run(scenario())


def test_native_unknown_retry_keeps_closing_and_closes_browser_once() -> None:
    async def scenario() -> None:
        worker, manager, browser = _worker(); calls = 0
        async def cleanup(_binding: NativeBinding, **_kwargs: object) -> None:
            nonlocal calls; calls += 1
            if calls == 1: raise InstanceError("UNKNOWN", 503, True)
        worker._release_native_binding = cleanup  # type: ignore[method-assign]
        await worker.release("ctx", [])
        assert calls == 2 and browser.close_calls == 1 and manager._entries["ctx"].phase is ContextPhase.CLOSED
    asyncio.run(scenario())


def test_release_drains_failed_navigation_before_native_cleanup_dispatch() -> None:
    async def scenario() -> None:
        worker, manager, browser = _worker()

        async def failed_navigation() -> None:
            raise InstanceError("navigation failed", 503, retryable=True)

        navigation = asyncio.create_task(failed_navigation())
        with pytest.raises(InstanceError, match="navigation failed"):
            await navigation
        manager.require_context("ctx")
        manager._entries["ctx"].create_task = navigation

        observed: list[bool] = []

        async def cleanup(_binding: NativeBinding, **_kwargs: object) -> None:
            # This is the first point where a native capability could start a
            # Docker reset.  The completed navigation task must have been
            # joined and the BrowserContext closed first.
            observed.append(browser.closed)

        worker._release_native_binding = cleanup  # type: ignore[method-assign]
        await worker.release("ctx", [])

        assert observed == [True]
        assert browser.close_calls == 1
        assert manager._entries["ctx"].phase is ContextPhase.CLOSED

    asyncio.run(scenario())


def test_release_seal_before_create_rejects_late_uuid_without_browser_acquisition() -> None:
    async def scenario() -> None:
        manager = ContextManager(contexts_per_instance=1, vw=100, vh=100)
        await manager.seal("late")
        class Browser:
            calls = 0
            async def new_context(self, **_kwargs): self.calls += 1; return _BrowserContext()
        browser = Browser(); manager._b = browser  # type: ignore[assignment]
        with pytest.raises(InstanceError): await manager.create("late", [Website(website_id="web", url="http://fixture.test")])
        assert browser.calls == 0
    asyncio.run(scenario())


def test_public_release_before_allocate_fences_uuid_and_replays_closed_tombstone() -> None:
    """The public worker path, not a manager-only helper, owns the early fence."""
    class Browser:
        calls = 0

        async def new_context(self, **_kwargs: object) -> _BrowserContext:
            self.calls += 1
            return _BrowserContext()

    async def scenario() -> None:
        worker = PlaywrightBrowserWorker(contexts_per_instance=1)
        browser = Browser()
        worker.ctx_manager._b = browser  # type: ignore[assignment]

        # Release wins before ContextManager.create() can publish CREATING.
        await worker.release("early", [])
        entry = worker.ctx_manager._entries["early"]
        assert entry.phase is ContextPhase.CLOSED
        assert worker.ctx_manager.live_context_ids() == ()

        with pytest.raises(InstanceNotIdle):
            await worker.allocate(
                "early",
                [Website(website_id="web", url="http://fixture.test")],
                [],
            )
        # A retry replays the retained CLOSED success and cannot create a
        # successor entry or touch BrowserContext acquisition.
        await worker.release("early", [])
        assert worker.ctx_manager._entries["early"] is entry
        assert worker.ctx_manager.live_context_ids() == ()
        assert browser.calls == 0

    asyncio.run(scenario())


def test_queued_operation_does_not_replace_owner_and_release_drains_it() -> None:
    async def scenario() -> None:
        worker, manager, _browser = _worker(); entered = asyncio.Event(); hold = asyncio.Event()
        async def cleanup(_binding: NativeBinding, **_kwargs: object) -> None: return None
        worker._release_native_binding = cleanup  # type: ignore[method-assign]
        async def first() -> None:
            async with worker.operation("ctx"):
                entered.set(); await hold.wait()
        async def second() -> None:
            async with worker.operation("ctx"): pass
        a = asyncio.create_task(first()); b = asyncio.create_task(second())
        try:
            await asyncio.wait_for(entered.wait(), 1); await asyncio.sleep(0)
            assert manager._entries["ctx"].active_operation_task is a
            release = asyncio.create_task(worker.release("ctx", []))
            with pytest.raises(asyncio.CancelledError): await asyncio.wait_for(a, 1)
            with pytest.raises(InstanceError): await asyncio.wait_for(b, 1)
            await asyncio.wait_for(release, 1)
            assert manager._entries["ctx"].phase is ContextPhase.CLOSED
        finally:
            hold.set()
            for task in (a, b):
                if not task.done(): task.cancel()
                with suppress(asyncio.CancelledError, InstanceError): await task
    asyncio.run(scenario())


def test_native_and_all_web_bindings_remain_closing_until_last_ack_then_retry() -> None:
    async def scenario() -> None:
        worker, manager, browser = _worker()
        first = WebBinding("ctx", "web-one", "http://one.test", "sid", "/reset", "cookie-one")
        second = WebBinding("ctx", "web-two", "http://two.test", "sid", "/reset", "cookie-two")
        entry = manager._entries.get("ctx")
        if entry is None:
            manager.require_context("ctx")
            entry = manager._entries["ctx"]
        entry.web_bindings.update({"web-one": first, "web-two": second})
        worker._web_bindings["ctx"] = {"web-one": first, "web-two": second}
        native_calls: list[str] = []; web_calls: list[tuple[str, str]] = []
        async def native(binding: NativeBinding, **_kwargs: object) -> None: native_calls.append(binding.cleanup_capability or "")
        async def web(binding: WebBinding) -> None:
            web_calls.append((binding.website_id, binding.cookie_value))
            if binding.website_id == "web-two" and len(web_calls) == 2:
                raise InstanceError("UNKNOWN", 503, True)
        worker._release_native_binding = native  # type: ignore[method-assign]
        worker._release_web_binding = web  # type: ignore[method-assign]
        with pytest.raises(InstanceError): await worker.release("ctx", [])
        assert entry.phase is ContextPhase.CLOSING and browser.close_calls == 1
        assert set(entry.web_bindings) == {"web-one", "web-two"}
        await worker.release("ctx", [])
        assert browser.close_calls == 1 and entry.phase is ContextPhase.CLOSED
        # Completed native cleanup is not replayed when a later web binding
        # remains UNKNOWN; only the unfinished web bindings retry.
        assert native_calls == ["cap"]
        assert web_calls == [("web-one", "cookie-one"), ("web-two", "cookie-two"), ("web-one", "cookie-one"), ("web-two", "cookie-two")]
    asyncio.run(scenario())
