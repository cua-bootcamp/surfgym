from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple
from urllib.parse import urlsplit

from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright
from surfgym_contracts.task import Website

from surfgym_runtime.wavepool.instance.error import UnexpectedError

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
    cursor: PageCursor = PageCursor(0, 0)

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
        browser_context = await self._require_browser().new_context(
            viewport={"width": self.vw, "height": self.vh},
            ignore_https_errors=self.ignore_https_errors,
        )
        if self.should_inject_page_script([website.url for website in websites]):
            await browser_context.add_init_script(script=self.page_script)
        try:
            pages = {
                website.website_id: (
                    await browser_context.new_page(),
                    layout,
                )
                for website, layout in zip(websites, self._build_page_layouts(len(websites)))
            }
        except Exception:
            await browser_context.close()
            raise

        context = Context(
            context_id=context_id,
            context=browser_context,
            pages=pages,
            active_page_id=websites[0].website_id,
        )

        self._contexts[context_id] = context

    async def delete(self, context_id: str):
        ctx = self.require_context(context_id)
        await ctx.close()
        self._contexts.pop(context_id, None)

    def live_context_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._contexts))

    async def delete_all(self) -> None:
        context_ids = list(self._contexts)
        await asyncio.gather(*(self.delete(context_id) for context_id in context_ids))

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
    def should_inject_page_script(urls: list[str]) -> bool:
        return all(urlsplit(url).port != 53001 for url in urls)

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
