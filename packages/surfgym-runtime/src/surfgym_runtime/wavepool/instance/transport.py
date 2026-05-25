from dataclasses import dataclass
from pathlib import Path
from typing import Union

from playwright.async_api import Page
from surfgym_contracts.command import MouseButtonType, PlaywrightKey
from surfgym_contracts.task import ConsoleRule, DomRule

from surfgym_runtime.wavepool.instance.error import (
    UnexpectedError,
)


@dataclass(frozen=True)
class PageLayout:
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class ScreenCursor:
    x: float
    y: float


@dataclass(frozen=True)
class PageCursor:
    x: float
    y: float


class PlaywrightController:
    def __init__(
        self,
    ) -> None:
        self.cursor: PageCursor = PageCursor(0, 0)

        script_path = Path(__file__).parent / "_page_script.js"
        with open(script_path, "rt") as fh:
            self.page_script = fh.read()

    async def on_new_page(self, page: Page, layout: PageLayout):
        await page.set_viewport_size({"width": layout.width, "height": layout.height})
        await page.add_init_script(script=self.page_script)
        await page.evaluate(f"""
        () => {{
            {self.page_script}
        }}
        """)
        await page.wait_for_load_state(timeout=30000)

    async def sleep(self, page: Page, duration_ms: Union[int, float]) -> None:
        await page.wait_for_timeout(duration_ms)

    async def _ensure_page_ready(self, page: Page) -> None:
        if page.is_closed():
            raise UnexpectedError("Page is closed")

    async def get_screenshot(self, page: Page, path: str | None = None) -> bytes:
        await self._ensure_page_ready(page)
        screenshot = await page.screenshot(path=path, timeout=15000)
        return screenshot

    async def visit_page(self, page: Page, url: str):
        await self._ensure_page_ready(page)
        await page.goto(url, wait_until="domcontentloaded")

    async def click_coords(
        self,
        page: Page,
        cursor: PageCursor,
        button: MouseButtonType,
        click_count: int,
    ):
        await self._ensure_page_ready(page)
        option_value = await page.evaluate(
            """([x, y]) => {
                const active = document.activeElement;
                if (!active || active.tagName !== 'SELECT') return null;
                const rect = active.getBoundingClientRect();
                const opts = Array.from(active.options);
                if (!opts.length) return null;
                const relY = y - rect.bottom;
                if (relY < 0) return null;
                const optionHeight = rect.height > 0 ? rect.height : 22;
                const idx = Math.floor(relY / optionHeight);
                if (idx < 0 || idx >= opts.length) return null;
                return opts[idx].value;
            }""",
            [cursor.x, cursor.y],
        )
        if option_value is not None:
            await page.locator("select:focus").select_option(value=option_value)
        else:
            await page.mouse.click(
                cursor.x, cursor.y, delay=10, button=button, click_count=click_count
            )
        self.cursor = cursor

    async def hover_coords(self, page: Page, cursor: PageCursor):
        await self._ensure_page_ready(page)
        await page.mouse.move(cursor.x, cursor.y)
        self.cursor = cursor

    async def scroll_pointer(self, page: Page, dx: float, dy: float):
        await self._ensure_page_ready(page)
        await page.mouse.wheel(dx, dy)

    async def mouse_down(self, page: Page):
        await self._ensure_page_ready(page)
        await page.mouse.down()
        self._mouse_button_down = True

    async def mouse_up(self, page: Page):
        await self._ensure_page_ready(page)
        await page.mouse.up()
        self._mouse_button_down = False

    async def drag_to(self, page: Page, cursor: PageCursor):
        await self._ensure_page_ready(page)
        await page.mouse.down()
        await page.mouse.move(cursor.x, cursor.y, steps=20)
        await page.mouse.up()
        self.cursor = cursor

    async def keyboard_type(self, page: Page, text: str):
        await self._ensure_page_ready(page)
        await page.keyboard.type(text)

    async def key_down(self, page: Page, key: PlaywrightKey):
        await self._ensure_page_ready(page)
        await page.keyboard.down(key)

    async def key_up(self, page: Page, key: PlaywrightKey):
        await self._ensure_page_ready(page)
        await page.keyboard.up(key)

    async def key_press(self, page: Page, key: PlaywrightKey):
        await self._ensure_page_ready(page)
        await page.keyboard.press(key)

    async def hotkey_press(self, page: Page, keys: list[PlaywrightKey]):
        await self._ensure_page_ready(page)
        for key in keys:
            await page.keyboard.down(key)
        for key in reversed(keys):
            await page.keyboard.up(key)

    # async def get_interactive_rects(self, page: Page) -> list[InteractiveRegion]:
    #     await self._ensure_page_ready(page)
    #     return interactive_region_list_adapter.validate_python(
    #         await page.evaluate("Surfgym.getInteractiveRects();")
    #     )

    async def get_console_observation(
        self, page: Page, console_rules: list[ConsoleRule]
    ) -> list[object]:
        await self._ensure_page_ready(page)

        observations: list[object] = []
        for rule in console_rules:
            try:
                observations.append(await page.evaluate(rule.script))
            except Exception:
                observations.append(None)

        return observations

    async def get_dom_observation(self, page: Page, dom_rules: list[DomRule]) -> list[object]:
        await self._ensure_page_ready(page)

        try:
            return await page.evaluate(
                """
        (rules) => {
            return Surfgym.getDomObservation(rules);
        }
        """,
                [rule.model_dump(mode="json") for rule in dom_rules],
            )
        except Exception:
            return [None] * len(dom_rules)
