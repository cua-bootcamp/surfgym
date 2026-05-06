from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Union, cast

from PIL import Image
from playwright.async_api import Page, async_playwright
from typing_extensions import assert_never

from src.gateway.rule_evaluator import ObservationRequest
from src.gateway.task_store import Website
from src.protocol.command import Command, CommandType, MouseButtonType
from src.protocol.instance_to_gateway import (
    InteractiveRegion,
    InteractiveTreeResponse,
    MousePosition,
    SnapshotResponse,
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
        await page.wait_for_load_state(timeout=30000)

    async def sleep(self, page: Page, duration_ms: Union[int, float]) -> None:
        await page.wait_for_timeout(duration_ms)

    async def get_interactive_rects(self, page: Page) -> Dict[str, InteractiveRegion]:
        await self._ensure_page_ready(page)
        # Read the regions from the DOM
        try:
            await page.evaluate(self.page_script)
        except Exception:
            pass
        result = cast(
            Dict[str, Dict[str, Any]],
            await page.evaluate("MultimodalWebSurfer.getInteractiveRects();"),
        )

        # Convert the results into appropriate types
        assert isinstance(result, dict)
        result = cast(
            dict[str, dict[str, Any]],
            await page.evaluate("MultimodalWebSurfer.getInteractiveRects();"),
        )

        typed_results: dict[str, InteractiveRegion] = {}
        for key, region in result.items():
            typed_results[key] = InteractiveRegion.model_validate(region)

        return typed_results

    async def _ensure_page_ready(self, page: Page) -> None:
        assert page is not None
        if page.is_closed():
            raise RuntimeError("Page is closed")

    async def get_screenshot(self, page: Page, path: str | None = None) -> bytes:
        await self._ensure_page_ready(page)
        screenshot = await page.screenshot(path=path, timeout=15000)
        return screenshot

    async def visit_page(self, page: Page, url: str):
        await self._ensure_page_ready(page)
        await page.goto(url)
        await page.wait_for_load_state()

    async def click_coords(
        self,
        page: Page,
        cursor: PageCursor,
        button: MouseButtonType,
        click_count: int,
    ):
        await self._ensure_page_ready(page)
        await page.mouse.click(
            cursor.x, cursor.y, delay=10, button=button.value, click_count=click_count
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

    async def key_down(self, page: Page, key: str):
        await self._ensure_page_ready(page)
        await page.keyboard.down(key)

    async def key_up(self, page: Page, key: str):
        await self._ensure_page_ready(page)
        await page.keyboard.up(key)

    async def key_press(self, page: Page, key: str):
        await self._ensure_page_ready(page)
        await page.keyboard.press(key)

    async def hotkey_press(self, page: Page, keys: list[str]):
        """
        Press specified keys in sequence.
        """
        await self._ensure_page_ready(page)
        for key in keys:
            await page.keyboard.down(key)
        for key in reversed(keys):
            await page.keyboard.up(key)

    async def get_page_snapshot(
        self,
        page: Page,
        rules: list[ObservationRequest],
    ) -> dict[int, str]:
        await self._ensure_page_ready(page)

        observation_requests = [rule.model_dump(mode="json") for rule in rules]

        raw_observations = cast(
            dict[str, str],
            await page.evaluate(
                """(rules) => {
                    function readText(element) {
                        return element.innerText || element.textContent || "";
                    }

                    function readAttr(element, attr) {
                        if (!attr) {
                            return "";
                        }

                        if (attr in element) {
                            const value = element[attr];
                            return value === undefined || value === null ? "" : String(value);
                        }

                        return element.getAttribute(attr) || "";
                    }

                    function readFromElement(rule) {
                        if (!rule.selector) {
                            return "";
                        }

                        let element = null;
                        try {
                            element = document.querySelector(rule.selector);
                        } catch {
                            return "";
                        }

                        if (!element) {
                            return "";
                        }

                        if (rule.target === "text") {
                            return readText(element);
                        }
                        if (rule.target === "html") {
                            return element.outerHTML || "";
                        }
                        if (rule.target === "attr") {
                            return readAttr(element, rule.attr);
                        }

                        return "";
                    }

                    function readFromPage(rule) {
                        if (rule.target === "url") {
                            return window.location.href;
                        }
                        if (rule.target === "title") {
                            return document.title || "";
                        }
                        if (rule.target === "text") {
                            return document.body ? document.body.innerText || "" : "";
                        }
                        if (rule.target === "html") {
                            return document.documentElement
                                ? document.documentElement.outerHTML || ""
                                : "";
                        }

                        return "";
                    }

                    const observations = {};
                    for (const rule of rules) {
                        observations[rule.id] = rule.selector
                            ? readFromElement(rule)
                            : readFromPage(rule);
                    }

                    return observations;
                }""",
                observation_requests,
            ),
        )

        return {int(rule_id): value for rule_id, value in raw_observations.items()}


class PlaywrightInstance:
    def __init__(
        self,
        *,
        viewport_width: int,
        viewport_height: int,
    ):
        self.id = None

        self.viewport_width = viewport_width
        self.viewport_height = viewport_height
        self.active_page_id: str | None = None

        self.pages: dict[str, Page] = {}
        self.page_layouts: dict[str, PageLayout] = {}
        self.context = None
        self.browser = None
        self.p = None

        self.controller = PlaywrightController()

    async def create(self, id: str, websites: list[Website]) -> None:
        self.id = id

        self.p = await async_playwright().start()
        self.browser = await self.p.chromium.launch()
        self.context = await self.browser.new_context(
            viewport={"width": self.viewport_width, "height": self.viewport_height}
        )

        layouts = build_page_layouts(
            page_count=len(websites),
            total_width=self.viewport_width,
            total_height=self.viewport_height,
        )

        for website, layout in zip(websites, layouts):
            page = await self.context.new_page()
            await self.controller.on_new_page(page, layout)
            await self.controller.visit_page(page, website.url)

            self.pages[website.id] = page
            self.page_layouts[website.id] = layout
            if self.active_page_id is None:
                self.active_page_id = website.id

    async def delete(self) -> None:
        for page in self.pages.values():
            if not page.is_closed():
                await page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.p:
            await self.p.stop()

        self.id = None
        self.context = None
        self.browser = None
        self.p = None

        self.pages = {}
        self.page_layouts = {}
        self.active_page_id = None
        self.controller.cursor = PageCursor(0, 0)

    async def idle(self) -> bool:
        states = {
            "page": not self.pages,
            "context": self.context is None,
            "browser": self.browser is None,
            "playwright": self.p is None,
            "id": self.id is None,
        }

        if all(states.values()):
            return True

        if not any(states.values()):
            return False

        raise RuntimeError(f"Inconsistent PlaywrightInstance state: {states}")

    async def screenshot(self) -> tuple[BytesIO, float, float]:
        canvas = Image.new(
            "RGB",
            (self.viewport_width, self.viewport_height),
            color=(255, 255, 255),
        )

        for website_id, page in self.pages.items():
            layout = self.page_layouts[website_id]

            screenshot_bytes = await self.controller.get_screenshot(page)
            page_image = Image.open(BytesIO(screenshot_bytes)).convert("RGB")

            canvas.paste(page_image, (layout.x, layout.y))

        output = BytesIO()
        canvas.save(output, format="PNG")
        output.seek(0)

        screen_cursor = self._page_to_screen_cursor()
        return output, screen_cursor.x, screen_cursor.y

    async def execute(self, command: Command):
        if self.active_page_id is None:
            raise RuntimeError("active_page_id should be initialized at this time")
        page = self.pages[self.active_page_id]

        match command.command:
            case CommandType.NAVIGATE:
                raise ValueError("Deprecated")

            case CommandType.MOUSE_MOVE:
                page_cursor = self._screen_to_page_cursor(command.x, command.y)
                page = self.pages[self.active_page_id]
                return await self.controller.hover_coords(page, page_cursor)

            case CommandType.MOUSE_CLICK:
                page_cursor = self._screen_to_page_cursor(command.x, command.y)
                page = self.pages[self.active_page_id]
                return await self.controller.click_coords(
                    page,
                    page_cursor,
                    command.button,
                    click_count=command.clickCount,
                )

            case CommandType.MOUSE_DOWN:
                return await self.controller.mouse_down(page)

            case CommandType.MOUSE_UP:
                return await self.controller.mouse_up(page)

            case CommandType.MOUSE_WHEEL:
                return await self.controller.scroll_pointer(page, command.dx, command.dy)

            case CommandType.DRAG_TO:
                page_cursor = self._screen_to_page_cursor(command.x, command.y)
                page = self.pages[self.active_page_id]
                return await self.controller.drag_to(page, page_cursor)

            case CommandType.KEYBOARD_TYPE:
                return await self.controller.keyboard_type(page, command.text)

            case CommandType.KEY_DOWN:
                return await self.controller.key_down(page, command.key)

            case CommandType.KEY_UP:
                return await self.controller.key_up(page, command.key)

            case CommandType.KEY_PRESS:
                return await self.controller.key_press(page, command.key)

            case CommandType.HOT_KEY:
                return await self.controller.hotkey_press(page, command.keys)

            case CommandType.SNAPSHOT:
                return await self._get_snapshot(command.rules)

            case CommandType.INTERACTIVE_TREE:
                return await self._get_interactive_tree()

            case CommandType.SLEEP:
                await self.controller.sleep(page, command.duration_ms)

            case _ as unreachable:
                assert_never(unreachable)

    def _offset_region(self, region: InteractiveRegion, layout: PageLayout) -> InteractiveRegion:
        rects = [
            rect.model_copy(
                update={
                    "x": rect.x + layout.x,
                    "y": rect.y + layout.y,
                    "top": rect.top + layout.y,
                    "right": rect.right + layout.x,
                    "bottom": rect.bottom + layout.y,
                    "left": rect.left + layout.x,
                }
            )
            for rect in region.rects
        ]

        return region.model_copy(update={"rects": rects})

    async def _get_interactive_tree(self) -> InteractiveTreeResponse:
        regions: dict[str, InteractiveRegion] = {}

        for website_id, page in self.pages.items():
            layout = self.page_layouts[website_id]
            page_regions = await self.controller.get_interactive_rects(page)

            for region_id, region in page_regions.items():
                regions[f"{website_id}:{region_id}"] = self._offset_region(region, layout)

        screen_cursor = self._page_to_screen_cursor()

        return InteractiveTreeResponse(
            mouse_position=MousePosition(x=int(screen_cursor.x), y=int(screen_cursor.y)),
            regions=regions,
        )

    async def _get_snapshot(self, rules: list[ObservationRequest]) -> SnapshotResponse:
        grouped: dict[str, list[ObservationRequest]] = {}

        for rule in rules:
            grouped.setdefault(rule.website_id, []).append(rule)

        snapshot: dict[int, str] = {}

        for website_id, page_rules in grouped.items():
            page = self.pages.get(website_id)
            if page is None:
                raise RuntimeError(f"unknown website_id in snapshot rules: {website_id}")

            page_snapshot = await self.controller.get_page_snapshot(page, page_rules)
            snapshot.update(page_snapshot)

        return SnapshotResponse(snapshot=snapshot)

    def _screen_to_page_cursor(self, x: float | None, y: float | None) -> PageCursor:
        if x is None or y is None:
            return self.controller.cursor

        for website_id, layout in self.page_layouts.items():
            if layout.x <= x < layout.x + layout.width and layout.y <= y < layout.y + layout.height:
                self.active_page_id = website_id
                return PageCursor(x - layout.x, y - layout.y)

        raise RuntimeError(f"screen cursor is outside page layouts: ({x}, {y})")

    def _page_to_screen_cursor(self) -> ScreenCursor:
        page_id = self.active_page_id
        if page_id is None:
            return ScreenCursor(0.0, 0.0)

        layout = self.page_layouts.get(page_id)
        if layout is None:
            return ScreenCursor(0.0, 0.0)

        return ScreenCursor(
            layout.x + self.controller.cursor.x, layout.y + self.controller.cursor.y
        )


def build_page_layouts(
    *,
    page_count: int,
    total_width: int,
    total_height: int,
) -> list[PageLayout]:
    half_width = total_width // 2
    half_height = total_height // 2

    # +-----+-----+
    # |           |
    # |     1     |
    # |           |
    # +-----+-----+
    if page_count == 1:
        return [
            PageLayout(x=0, y=0, width=total_width, height=total_height),
        ]

    # +-----+-----+
    # |     |     |
    # |  1  |  2  |
    # |     |     |
    # +-----+-----+
    if page_count == 2:
        return [
            PageLayout(x=0, y=0, width=half_width, height=total_height),
            PageLayout(x=half_width, y=0, width=half_width, height=total_height),
        ]

    # +-----+-----+
    # |     |  2  |
    # |  1  +-----+
    # |     |  3  |
    # +-----+-----+
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

    # +-----+-----+
    # |  1  |  2  |
    # +-----+-----+
    # |  3  |  4  |
    # +-----+-----+
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
