from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
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
        self._creating_context_ids: set[str] = set()

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
        if context_id in self._contexts or context_id in self._creating_context_ids:
            raise InstanceNotIdle("context already exists")
        self._creating_context_ids.add(context_id)

        try:
            browser_context = await self._require_browser().new_context(
                viewport={"width": self.vw, "height": self.vh},
                ignore_https_errors=self.ignore_https_errors,
            )
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
                await browser_context.close()
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

            if context_id in self._contexts:
                await context.close()
                raise InstanceNotIdle("context already exists")
            self._contexts[context_id] = context
        finally:
            self._creating_context_ids.discard(context_id)

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

    def live_context_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._contexts))

    async def delete_all(self) -> None:
        contexts = list(self._contexts.items())
        await asyncio.gather(
            *(self._delete_context(context_id, context) for context_id, context in contexts)
        )

    def require_context(self, context_id: str) -> Context:
        ctx = self._contexts.get(context_id, None)
        if ctx is None:
            raise UnexpectedError("no ctx")

        return ctx

    def require_page(self, context_id: str, websit_id: str):
        ctx = self.require_context(context_id)
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
