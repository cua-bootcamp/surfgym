from __future__ import annotations

import asyncio

import pytest
from surfgym_contracts.task import Website
from surfgym_runtime.wavepool.instance.error import InstanceError
from surfgym_runtime.wavepool.instance.service import PlaywrightBrowserWorker
from surfgym_runtime.wavepool.instance.session import Context, ContextEntry, ContextManager, ContextPhase


class _Page:
    async def set_viewport_size(self, _viewport: dict[str, int]) -> None:
        return None

    async def add_init_script(self, *, script: str) -> None:
        return None

    async def close(self) -> None:
        return None


class _BrowserContext:
    def __init__(self, *, block_new_page: bool = False) -> None:
        self.new_page_started = asyncio.Event()
        self.allow_new_page = asyncio.Event()
        if not block_new_page:
            self.allow_new_page.set()
        self.close_started = asyncio.Event()
        self.allow_close = asyncio.Event()
        self.allow_close.set()
        self.closed = False

    async def new_page(self) -> _Page:
        self.new_page_started.set()
        await self.allow_new_page.wait()
        return _Page()

    async def close(self) -> None:
        self.close_started.set()
        await self.allow_close.wait()
        self.closed = True


class _FailingCloseBrowserContext(_BrowserContext):
    def __init__(self, *, fail_new_page: bool = False) -> None:
        super().__init__()
        self.fail_new_page = fail_new_page
        self.close_calls = 0

    async def new_page(self) -> _Page:
        if self.fail_new_page:
            raise RuntimeError("new page failed")
        return await super().new_page()

    async def close(self) -> None:
        self.close_calls += 1
        if self.close_calls == 1:
            raise RuntimeError("first close failed")
        await super().close()


class _Browser:
    def __init__(self, contexts: list[_BrowserContext]) -> None:
        self.contexts = contexts
        self.new_context_calls = 0

    async def new_context(self, **_options: object) -> _BrowserContext:
        context = self.contexts[self.new_context_calls]
        self.new_context_calls += 1
        return context


def _manager(browser: _Browser | None = None) -> ContextManager:
    manager = ContextManager(contexts_per_instance=2, vw=1280, vh=720)
    if browser is not None:
        manager._b = browser  # type: ignore[assignment]
    return manager


def _context(context_id: str, browser_context: _BrowserContext) -> Context:
    return Context(
        context_id=context_id,
        context=browser_context,  # type: ignore[arg-type]
        pages={"web": (_Page(), None)},  # type: ignore[dict-item]
        active_page_id="web",
    )


def test_duplicate_create_during_release_hook_fails_closed_without_replacement() -> None:
    async def scenario() -> None:
        replacement = _BrowserContext()
        browser = _Browser([replacement])
        manager = _manager(browser)
        old_browser_context = _BrowserContext()
        old = _context("context-id", old_browser_context)
        manager._contexts["context-id"] = old
        worker = PlaywrightBrowserWorker(contexts_per_instance=1)
        worker.ctx_manager = manager
        hook_started = asyncio.Event()
        allow_hook = asyncio.Event()

        async def run_hooks(*_args: object, **_kwargs: object) -> None:
            hook_started.set()
            await allow_hook.wait()

        worker._run_hooks = run_hooks  # type: ignore[method-assign]
        release_task = asyncio.create_task(worker.release("context-id", []))
        await hook_started.wait()

        with pytest.raises(InstanceError):
            await manager.create(
                "context-id",
                [Website(website_id="web", url="http://127.0.0.1:3000")],
            )
        assert manager.require_context("context-id") is old
        assert browser.new_context_calls == 0

        allow_hook.set()
        await release_task
        assert old_browser_context.closed is True
        assert replacement.closed is False
        assert manager.live_context_ids() == ()

    asyncio.run(scenario())


def test_concurrent_duplicate_create_is_reserved_before_first_await() -> None:
    async def scenario() -> None:
        first_context = _BrowserContext(block_new_page=True)
        unused_context = _BrowserContext()
        browser = _Browser([first_context, unused_context])
        manager = _manager(browser)
        website = Website(website_id="web", url="http://127.0.0.1:3000")

        first = asyncio.create_task(manager.create("context-id", [website]))
        await first_context.new_page_started.wait()
        with pytest.raises(InstanceError):
            await manager.create("context-id", [website])
        assert browser.new_context_calls == 1

        first_context.allow_new_page.set()
        await first
        assert manager._entries["context-id"].phase is ContextPhase.CREATING
        assert manager.require_context("context-id", allow_creating=True).context is first_context
        assert unused_context.closed is False

    asyncio.run(scenario())


def test_delete_compare_and_pop_does_not_remove_late_replacement() -> None:
    async def scenario() -> None:
        manager = _manager()
        old_browser_context = _BrowserContext()
        old_browser_context.allow_close.clear()
        replacement_browser_context = _BrowserContext()
        old = _context("context-id", old_browser_context)
        replacement = _context("context-id", replacement_browser_context)
        manager._contexts["context-id"] = old

        delete_task = asyncio.create_task(manager.delete("context-id"))
        await old_browser_context.close_started.wait()
        manager._contexts["context-id"] = replacement
        old_browser_context.allow_close.set()
        await delete_task

        assert old_browser_context.closed is True
        assert manager.require_context("context-id") is replacement
        assert replacement_browser_context.closed is False

    asyncio.run(scenario())


def test_partial_browser_create_failure_is_retained_until_release_retry_closes_it() -> None:
    async def scenario() -> None:
        partial = _FailingCloseBrowserContext(fail_new_page=True)
        manager = _manager(_Browser([partial]))
        with pytest.raises(RuntimeError, match="first close failed"):
            await manager.create("context-id", [Website(website_id="web", url="http://fixture.test")])
        entry = manager._entries["context-id"]
        assert entry.phase is ContextPhase.CLOSING
        assert entry.partial_browser_context is partial

        worker = PlaywrightBrowserWorker(contexts_per_instance=1)
        worker.ctx_manager = manager
        await worker.release("context-id", [])
        assert partial.close_calls == 2
        assert partial.closed is True
        assert manager._entries["context-id"].phase is ContextPhase.CLOSED

    asyncio.run(scenario())


def test_late_browser_context_after_release_seal_is_closed_without_activation() -> None:
    class DelayedBrowser:
        def __init__(self, context: _BrowserContext) -> None:
            self.context = context
            self.started = asyncio.Event()
            self.allow = asyncio.Event()

        async def new_context(self, **_options: object) -> _BrowserContext:
            self.started.set()
            await self.allow.wait()
            return self.context

    async def scenario() -> None:
        browser_context = _BrowserContext()
        browser = DelayedBrowser(browser_context)
        manager = _manager()
        manager._b = browser  # type: ignore[assignment]
        creating = asyncio.create_task(
            manager.create("context-id", [Website(website_id="web", url="http://fixture.test")])
        )
        await browser.started.wait()
        await manager.seal("context-id")
        browser.allow.set()
        with pytest.raises(InstanceError):
            await creating
        assert browser_context.closed is True
        assert manager.live_context_ids() == ()
        assert manager._entries["context-id"].phase is ContextPhase.CLOSING

    asyncio.run(scenario())


def test_repeated_create_cancellation_drains_late_browser_handle_once() -> None:
    class DelayedBrowser:
        def __init__(self, context: _BrowserContext) -> None:
            self.context = context; self.started = asyncio.Event(); self.allow = asyncio.Event()
        async def new_context(self, **_options: object) -> _BrowserContext:
            self.started.set(); await self.allow.wait(); return self.context
    async def scenario() -> None:
        browser_context = _BrowserContext(); browser = DelayedBrowser(browser_context)
        manager = _manager(); manager._b = browser  # type: ignore[assignment]
        task = asyncio.create_task(manager.create("ctx", [Website(website_id="web", url="http://fixture.test")]))
        await asyncio.wait_for(browser.started.wait(), 1)
        task.cancel(); await asyncio.sleep(0); task.cancel()
        browser.allow.set()
        with pytest.raises(asyncio.CancelledError): await asyncio.wait_for(task, 1)
        entry = manager._entries["ctx"]
        assert browser_context.closed is True
        assert entry.phase is ContextPhase.CLOSING
        assert entry.partial_browser_context is None
        assert manager.live_context_ids() == ()
    asyncio.run(scenario())


def test_closed_tombstone_gc_waits_for_horizon_and_never_evicts_active_cleanup() -> None:
    async def scenario() -> None:
        manager = _manager()
        now = asyncio.get_running_loop().time()
        manager._entries["retained"] = ContextEntry(
            phase=ContextPhase.CLOSED, closed_at=now - 901,
            release_task=asyncio.current_task(),
        )
        manager._gc_closed_locked()
        assert "retained" in manager._entries
        manager._entries["retained"].release_task = None
        manager._gc_closed_locked()
        assert "retained" not in manager._entries
        manager._entries["fresh"] = ContextEntry(phase=ContextPhase.CLOSED, closed_at=now - 899)
        manager._gc_closed_locked()
        assert "fresh" in manager._entries
    asyncio.run(scenario())


def test_cancelled_browser_acquisition_exits_without_spinning_event_loop() -> None:
    class PendingBrowser:
        def __init__(self) -> None: self.started = asyncio.Event(); self.future = asyncio.Future()
        async def new_context(self, **_options: object):
            self.started.set(); return await self.future
    async def scenario() -> None:
        manager = _manager(); browser = PendingBrowser(); manager._b = browser  # type: ignore[assignment]
        creating = asyncio.create_task(manager.create("ctx", [Website(website_id="web", url="http://fixture.test")]))
        await asyncio.wait_for(browser.started.wait(), 1)
        manager._entries["ctx"].browser_acquire_task.cancel()  # type: ignore[union-attr]
        creating.cancel()
        heartbeat = asyncio.Event()
        asyncio.get_running_loop().call_soon(heartbeat.set)
        with pytest.raises(asyncio.CancelledError): await asyncio.wait_for(creating, 1)
        await asyncio.wait_for(heartbeat.wait(), 1)
    asyncio.run(scenario())
