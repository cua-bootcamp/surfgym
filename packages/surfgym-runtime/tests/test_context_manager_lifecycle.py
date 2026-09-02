from __future__ import annotations

import asyncio

import pytest
from surfgym_contracts.task import Website
from surfgym_runtime.wavepool.instance.error import InstanceError
from surfgym_runtime.wavepool.instance.service import PlaywrightBrowserWorker
from surfgym_runtime.wavepool.instance.session import Context, ContextManager


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
        assert manager.require_context("context-id").context is first_context
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
