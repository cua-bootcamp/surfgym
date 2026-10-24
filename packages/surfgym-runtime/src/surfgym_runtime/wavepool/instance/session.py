from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Tuple

from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright
from surfgym_contracts.task import Website

from surfgym_runtime.wavepool.instance.error import (
    InstanceNotIdle,
    InvalidCommand,
    UnexpectedError,
)

type Website_ID = str


@dataclass(frozen=True)
class PageLayout:
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class PageCursor:
    x: float
    y: float

    def to_screen_cursor(self, layout: PageLayout) -> ScreenCursor:
        return ScreenCursor(
            layout.x + self.x,
            layout.y + self.y,
        )


@dataclass(frozen=True)
class ScreenCursor:
    x: float
    y: float

    def to_page_cursor(self, layout: PageLayout) -> PageCursor:
        return PageCursor(self.x - layout.x, self.y - layout.y)


type Page_Meta = Tuple[Page, PageLayout]


@dataclass
class Context:
    context_id: str
    context: BrowserContext
    pages: dict[Website_ID, Page_Meta]
    active_page_id: Website_ID
    native_page_ids: tuple[Website_ID, ...] = ()
    entered_page_ids: set[Website_ID] = field(default_factory=lambda: set[Website_ID]())
    operation_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    cursor: PageCursor = PageCursor(0, 0)
    mouse_down_page_id: Website_ID | None = None

    async def close(self):
        for page, _ in self.pages.values():
            await page.close()

        await self.context.close()


class ContextPhase(StrEnum):
    CREATING = "creating"
    ACTIVE = "active"
    CLOSING = "closing"
    CLOSED = "closed"


@dataclass
class ContextEntry:
    """One in-memory lifecycle owner; CLOSED entries are retry tombstones."""

    phase: ContextPhase
    context: Context | None = None
    partial_browser_context: BrowserContext | None = None
    browser_acquire_task: asyncio.Task[BrowserContext] | None = None
    create_task: asyncio.Task[object] | None = None
    active_operation_task: asyncio.Task[object] | None = None
    release_task: asyncio.Task[object] | None = None
    # The Instance owns descriptors until the release task has received every
    # downstream acknowledgement.  BrowserContext lifetime is intentionally
    # shorter than this record's lifetime.
    native_bindings: dict[str, object] = field(default_factory=dict)
    web_bindings: dict[str, object] = field(default_factory=dict)
    closed_at: float | None = None


class ContextManager:
    def __init__(
        self,
        *,
        contexts_per_instance: int,
        vw: int,
        vh: int,
        headed: bool = False,
        ignore_https_errors: bool = False,
    ):
        self.contexts_per_instance = contexts_per_instance
        self.vw = vw
        self.vh = vh
        self.headed = headed
        self.ignore_https_errors = ignore_https_errors

        self._p: Playwright | None = None
        self._b: Browser | None = None
        self._contexts: dict[str, Context] = {}
        self._entries: dict[str, ContextEntry] = {}
        self._entry_lock = asyncio.Lock()

        with open(
            Path(__file__).parent / "_page_script.js",
            "rt",
            encoding="utf-8",
        ) as fh:
            self.page_script = fh.read()

    async def open(self) -> None:
        self._p = await async_playwright().start()
        self._b = await self._p.chromium.launch(headless=not self.headed)

    async def close(self) -> None:
        await self.delete_all()
        if self._b is not None:
            await self._b.close()
            self._b = None

        if self._p is not None:
            await self._p.stop()
            self._p = None

    async def create(self, context_id: str, websites: list[Website]):
        async with self._entry_lock:
            self._gc_closed_locked()
            if context_id in self._entries:
                raise InstanceNotIdle("context already exists or is retained closed")
            self._entries[context_id] = ContextEntry(
                phase=ContextPhase.CREATING,
                create_task=asyncio.current_task(),
            )

        try:
            acquire_task = asyncio.create_task(
                self._require_browser().new_context(
                    viewport={"width": self.vw, "height": self.vh},
                    ignore_https_errors=self.ignore_https_errors,
                )
            )
            async with self._entry_lock:
                self._entries[context_id].browser_acquire_task = acquire_task
            try:
                browser_context = await asyncio.shield(acquire_task)
            except asyncio.CancelledError:
                # The remote browser may still finish creation after the local
                # request was cancelled.  Drain it, retain its handle, and let
                # release close it before the cancellation escapes.
                while True:
                    try:
                        browser_context = await asyncio.shield(acquire_task)
                        break
                    except asyncio.CancelledError:
                        # Cleanup ownership is stronger than repeated request
                        # cancellation: keep draining until the remote create
                        # yields a handle that can be closed.
                        if acquire_task.done():
                            # This cancellation originated in the acquisition
                            # primitive itself (for example browser shutdown),
                            # not another caller cancellation.  Propagate once
                            # instead of spinning forever on shield().
                            acquire_task.result()
                        continue
                    except BaseException:
                        raise
                async with self._entry_lock:
                    self._entries[context_id].partial_browser_context = browser_context
                    self._entries[context_id].browser_acquire_task = None
                await self.close_partial_browser_context(context_id)
                raise
            async with self._entry_lock:
                entry = self._entries[context_id]
                entry.partial_browser_context = browser_context
                entry.browser_acquire_task = None
                sealed_after_browser = entry.phase is ContextPhase.CLOSING
            if sealed_after_browser:
                await self.close_partial_browser_context(context_id)
                raise InstanceNotIdle("context was sealed during browser creation")
            try:
                pages: dict[Website_ID, Page_Meta] = {}
                for website, layout in zip(
                    websites,
                    self._build_page_layouts(len(websites)),
                    strict=True,
                ):
                    page = await browser_context.new_page()
                    await page.set_viewport_size(
                        {"width": layout.width, "height": layout.height},
                    )
                    if self.should_inject_page_script(website):
                        await page.add_init_script(script=self.page_script)
                    pages[website.website_id] = (page, layout)
            except BaseException:
                # Keep the returned browser handle on close failure so release
                # can retry it instead of declaring a partial create closed.
                await self.close_partial_browser_context(context_id)
                raise

            context = Context(
                context_id=context_id,
                context=browser_context,
                pages=pages,
                active_page_id=websites[0].website_id,
                native_page_ids=tuple(
                    website.website_id for website in websites if website.surface == "native"
                ),
            )

            async with self._entry_lock:
                entry = self._entries[context_id]
                if entry.phase is ContextPhase.CLOSING:
                    entry.context = None
                    close_after_seal = True
                else:
                    close_after_seal = False
                if context_id in self._contexts:
                    raise InstanceNotIdle("context already exists")
                if not close_after_seal:
                    entry.context = context
                    entry.partial_browser_context = None
                    # Navigation/setup is part of creation and is activated by
                    # the worker only after it succeeds.
                    self._contexts[context_id] = context
            if close_after_seal:
                # The complete Context is not published, but retain its
                # BrowserContext through the same partial-close path.
                async with self._entry_lock:
                    self._entries[context_id].partial_browser_context = browser_context
                await self.close_partial_browser_context(context_id)
                raise InstanceNotIdle("context was sealed during creation")
        except BaseException:
            async with self._entry_lock:
                entry = self._entries.get(context_id)
                if entry is not None and entry.phase is not ContextPhase.ACTIVE:
                    entry.create_task = None
                    entry.phase = ContextPhase.CLOSING
            raise

    async def activate(self, context_id: str) -> None:
        async with self._entry_lock:
            entry = self._entries.get(context_id)
            if entry is None or entry.phase is not ContextPhase.CREATING:
                raise InstanceNotIdle("context cannot become active after closing")
            entry.phase = ContextPhase.ACTIVE
            entry.create_task = None

    async def mark_closed(self, context_id: str) -> None:
        async with self._entry_lock:
            entry = self._entries.get(context_id)
            if entry is not None:
                entry.context = None
                if entry.partial_browser_context is not None:
                    raise InstanceNotIdle("partial browser context remains open")
                if entry.browser_acquire_task is not None:
                    raise InstanceNotIdle("browser creation remains unresolved")
                entry.phase = ContextPhase.CLOSED
                entry.create_task = None
                entry.active_operation_task = None
                entry.release_task = None
                entry.closed_at = asyncio.get_running_loop().time()

    async def delete(self, context_id: str):
        ctx = self.require_context(context_id)
        await self._delete_context(context_id, ctx)

    async def _delete_context(self, context_id: str, expected_context: Context) -> None:
        async with expected_context.operation_lock:
            await self._delete_locked(context_id, expected_context)

    async def _delete_locked(self, context_id: str, expected_context: Context) -> None:
        if self._contexts.get(context_id) is not expected_context:
            raise InvalidCommand("context identity changed before deletion")

        await expected_context.close()
        if self._contexts.get(context_id) is expected_context:
            self._contexts.pop(context_id)
        # Browser resources are gone, but the lifecycle entry deliberately
        # remains CLOSING until retained bindings acknowledge cleanup.
        entry = self._entries.get(context_id)
        if entry is not None and entry.context is expected_context:
            entry.context = None

    async def close_partial_browser_context(self, context_id: str) -> None:
        """Close a browser handle retained before full Context publication."""
        async with self._entry_lock:
            entry = self._entries.get(context_id)
            browser_context = entry.partial_browser_context if entry is not None else None
            acquire_task = entry.browser_acquire_task if entry is not None else None
        if browser_context is None and acquire_task is not None:
            try:
                browser_context = await asyncio.shield(acquire_task)
            except BaseException:
                # A completed failed acquisition has no returned browser handle;
                # consume it so CLOSED is not blocked by a stale task record.
                if acquire_task.done():
                    async with self._entry_lock:
                        entry = self._entries.get(context_id)
                        if entry is not None and entry.browser_acquire_task is acquire_task:
                            entry.browser_acquire_task = None
                raise
            async with self._entry_lock:
                entry = self._entries.get(context_id)
                if entry is not None:
                    entry.browser_acquire_task = None
                    entry.partial_browser_context = browser_context
        if browser_context is None:
            return
        await browser_context.close()
        async with self._entry_lock:
            entry = self._entries.get(context_id)
            if entry is not None and entry.partial_browser_context is browser_context:
                entry.partial_browser_context = None

    async def seal(self, context_id: str) -> ContextEntry:
        """Fence later setup before release starts; network cleanup happens outside."""
        async with self._entry_lock:
            entry = self._entries.get(context_id)
            # Compatibility for contexts created by pre-lifecycle callers and
            # lightweight in-process tests.  Production allocation always
            # creates the entry before the first browser await.
            if entry is None and context_id in self._contexts:
                entry = ContextEntry(phase=ContextPhase.ACTIVE, context=self._contexts[context_id])
                self._entries[context_id] = entry
            if entry is None:
                # Release can beat Instance allocation after Master reserved
                # the UUID.  Fence it before acknowledging release so a late
                # create cannot start browser/navigation work.
                entry = ContextEntry(phase=ContextPhase.CLOSING)
                self._entries[context_id] = entry
            if entry.phase is ContextPhase.CLOSED:
                return entry
            entry.phase = ContextPhase.CLOSING
            return entry

    async def begin_release(self, context_id: str) -> tuple[ContextEntry, bool]:
        """Return the one release owner for a context.

        Callers must create and store the task while holding no network lock;
        the placeholder task is the request task which is replaced immediately
        by ``set_release_task``.  A CLOSED tombstone replays success.
        """
        async with self._entry_lock:
            entry = self._entries.get(context_id)
            if entry is None:
                entry = ContextEntry(phase=ContextPhase.CLOSING)
                self._entries[context_id] = entry
            if entry is None and context_id in self._contexts:
                entry = ContextEntry(phase=ContextPhase.ACTIVE, context=self._contexts[context_id])
                self._entries[context_id] = entry
            if entry is None:
                raise UnexpectedError("no ctx")
            if entry.phase is ContextPhase.CLOSED:
                return entry, False
            entry.phase = ContextPhase.CLOSING
            if entry.release_task is not None:
                return entry, False
            return entry, True

    async def set_release_task(self, context_id: str, task: asyncio.Task[object]) -> None:
        async with self._entry_lock:
            entry = self._entries.get(context_id)
            if entry is None or entry.phase is ContextPhase.CLOSED:
                raise UnexpectedError("context closed before release task registration")
            entry.release_task = task

    async def get_or_start_release_task(
        self, context_id: str, factory
    ) -> asyncio.Task[object] | None:
        """Atomically return the shared release task or start it while sealed.

        The task is created while the lifecycle lock is held, so two HTTP
        callers cannot start separate cleanup before either publishes ownership.
        ``None`` represents a CLOSED tombstone and replays completed success.
        """
        async with self._entry_lock:
            entry = self._entries.get(context_id)
            if entry is None and context_id in self._contexts:
                entry = ContextEntry(phase=ContextPhase.ACTIVE, context=self._contexts[context_id])
                self._entries[context_id] = entry
            if entry is None:
                # Master can own and release a reserved UUID before this
                # Instance has published its CREATE entry.  The retained
                # release task itself must install the fence atomically, or a
                # late allocate could otherwise start browser work after the
                # release response.
                entry = ContextEntry(phase=ContextPhase.CLOSING)
                self._entries[context_id] = entry
            if entry.phase is ContextPhase.CLOSED:
                return None
            entry.phase = ContextPhase.CLOSING
            if entry.release_task is not None:
                return entry.release_task
            task = asyncio.create_task(factory())
            entry.release_task = task
            return task

    async def clear_release_task(self, context_id: str, task: asyncio.Task[object]) -> None:
        async with self._entry_lock:
            entry = self._entries.get(context_id)
            if entry is not None and entry.release_task is task:
                entry.release_task = None

    async def operation_started(self, context_id: str) -> Context:
        async with self._entry_lock:
            entry = self._entries.get(context_id)
            if entry is None or entry.phase is not ContextPhase.ACTIVE or entry.context is None:
                raise UnexpectedError("context is not active")
            if (
                entry.active_operation_task is not None
                and entry.active_operation_task is not asyncio.current_task()
            ):
                raise InstanceNotIdle("another operation owns this context")
            entry.active_operation_task = asyncio.current_task()
            return entry.context

    async def operation_finished(self, context_id: str) -> None:
        async with self._entry_lock:
            entry = self._entries.get(context_id)
            if entry is not None and entry.active_operation_task is asyncio.current_task():
                entry.active_operation_task = None

    async def operation_still_owned(self, context_id: str, context: Context) -> None:
        async with self._entry_lock:
            entry = self._entries.get(context_id)
            if (
                entry is None
                or entry.phase is not ContextPhase.ACTIVE
                or entry.context is not context
                or entry.active_operation_task is not asyncio.current_task()
            ):
                raise UnexpectedError("context operation was fenced")

    def live_context_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._contexts))

    def _gc_closed_locked(self) -> None:
        # Deliberately no size-pressure eviction. Admission rejects instead of
        # reusing a UUID during the supported release retry horizon.
        horizon = 15 * 60
        now = asyncio.get_running_loop().time()
        for context_id, entry in tuple(self._entries.items()):
            if (
                entry.phase is ContextPhase.CLOSED
                and entry.closed_at is not None
                and now - entry.closed_at > horizon
                and entry.create_task is None
                and entry.active_operation_task is None
                and entry.release_task is None
            ):
                del self._entries[context_id]

    async def delete_all(self) -> None:
        contexts = list(self._contexts.items())
        await asyncio.gather(
            *(self._delete_context(context_id, context) for context_id, context in contexts)
        )

    def require_context(
        self,
        context_id: str,
        *,
        allow_creating: bool = False,
        allow_closing: bool = False,
    ) -> Context:
        ctx = self._contexts.get(context_id, None)
        entry = self._entries.get(context_id)
        if entry is None and ctx is not None:
            # Compatibility for legacy in-memory contexts; normal allocation
            # creates the entry before any browser await.
            entry = ContextEntry(phase=ContextPhase.ACTIVE, context=ctx)
            self._entries[context_id] = entry
        if (
            ctx is None
            or entry is None
            or (
                entry.phase is not ContextPhase.ACTIVE
                and not (allow_creating and entry.phase is ContextPhase.CREATING)
                # Manager-internal callers retain visibility while release
                # drains; public operations use operation_started(), which
                # requires ACTIVE.
                and entry.phase is not ContextPhase.CLOSING
            )
        ):
            raise UnexpectedError("no ctx")

        return ctx

    def require_page(
        self, context_id: str, websit_id: str, *, allow_creating: bool = False, allow_closing: bool = False
    ):
        ctx = self.require_context(
            context_id, allow_creating=allow_creating, allow_closing=allow_closing
        )
        page = ctx.pages.get(websit_id, None)
        if page is None:
            raise UnexpectedError("no page")
        return page

    def _require_browser(self) -> Browser:
        if self._b is None:
            raise UnexpectedError("?")
        return self._b

    @staticmethod
    def should_inject_page_script(website: Website) -> bool:
        """Return whether this individual page needs the generic web fixture bridge.

        Docker desktop pages provide their own bridge through the Docker gateway.
        Other pages in the same browser context must still receive the web bridge.
        """
        return website.surface == "web"

    @staticmethod
    def page_at_screen_cursor(
        ctx: Context,
        cursor: ScreenCursor,
    ) -> tuple[Website_ID, Page, PageCursor]:
        """Resolve a composite-screen pointer coordinate without changing focus."""
        for website_id, (page, layout) in ctx.pages.items():
            if (
                layout.x <= cursor.x < layout.x + layout.width
                and layout.y <= cursor.y < layout.y + layout.height
            ):
                return website_id, page, cursor.to_page_cursor(layout)

        raise InvalidCommand("pointer coordinate is outside every page surface")

    @classmethod
    def focus_page_at_screen_cursor(
        cls, ctx: Context, cursor: ScreenCursor
    ) -> tuple[Page, PageCursor]:
        """Focus the surface containing a composite-screen pointer coordinate."""
        website_id, page, page_cursor = cls.page_at_screen_cursor(ctx, cursor)
        if ctx.mouse_down_page_id is not None and ctx.mouse_down_page_id != website_id:
            raise InvalidCommand("cannot drag across independent page surfaces")

        ctx.active_page_id = website_id
        ctx.cursor = page_cursor
        return page, page_cursor

    #  * Single                * Double
    #  +-----+-----+           +-----+-----+
    #  |           |           |     |     |
    #  |     1     |           |  1  |  2  |
    #  |           |           |     |     |
    #  +-----+-----+           +-----+-----+

    #  * Triple                * Quadruple
    #  +-----+-----+           +-----+-----+
    #  |     |  2  |           |  1  |  2  |
    #  |  1  +-----+           +-----+-----+
    #  |     |  3  |           |  3  |  4  |
    #  +-----+-----+           +-----+-----+

    def _build_page_layouts(self, page_count: int) -> list[PageLayout]:
        total_width = self.vw
        total_height = self.vh
        half_width = total_width // 2
        half_height = total_height // 2

        if page_count == 1:
            return [
                PageLayout(x=0, y=0, width=total_width, height=total_height),
            ]

        if page_count == 2:
            return [
                PageLayout(x=0, y=0, width=half_width, height=total_height),
                PageLayout(x=half_width, y=0, width=half_width, height=total_height),
            ]

        if page_count == 3:
            return [
                PageLayout(x=0, y=0, width=half_width, height=total_height),
                PageLayout(x=half_width, y=0, width=half_width, height=half_height),
                PageLayout(
                    x=half_width,
                    y=half_height,
                    width=half_width,
                    height=half_height,
                ),
            ]

        return [
            PageLayout(x=0, y=0, width=half_width, height=half_height),
            PageLayout(x=half_width, y=0, width=half_width, height=half_height),
            PageLayout(x=0, y=half_height, width=half_width, height=half_height),
            PageLayout(
                x=half_width,
                y=half_height,
                width=half_width,
                height=half_height,
            ),
        ]
