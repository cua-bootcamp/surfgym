from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union, cast

from playwright.async_api import Page, async_playwright
from typing_extensions import assert_never

from src.gateway.rule_evaluator import ObservationRequest
from src.protocol.command import Command, CommandType, MouseButtonType
from src.protocol.instance_to_gateway import (
    InteractiveRegion,
    InteractiveTreeResponse,
    MousePosition,
    SnapshotResponse,
)


class PlaywrightController:
    def __init__(
        self,
        veiwport_width: int,
        vewport_height: int,
    ) -> None:
        self.viewport_width = veiwport_width
        self.viewport_height = vewport_height

        self.pointer_position: Tuple[float, float] = (0.0, 0.0)

        script_path = Path(__file__).parent / "_page_script.js"
        with open(script_path, "rt") as fh:
            self.page_script = fh.read()

    def _set_pointer_position(self, x: float, y: float) -> None:
        self.pointer_position = (float(x), float(y))

    def _resolve_coords(
        self,
        x: float | None,
        y: float | None,
    ) -> tuple[float, float]:
        if x is None or y is None:
            return self.pointer_position
        return x, y

    async def on_new_page(self, page: Page):
        await page.set_viewport_size({"width": self.viewport_width, "height": self.viewport_height})
        # await self.sleep(page, 0.2)
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
        x: Optional[float],
        y: Optional[float],
        button: MouseButtonType,
        click_count: int,
    ):
        await self._ensure_page_ready(page)

        x, y = self._resolve_coords(x, y)
        await page.mouse.click(x, y, delay=10, button=button.value, click_count=click_count)

        self._set_pointer_position(x, y)

    async def hover_coords(self, page: Page, x: float, y: float):
        await self._ensure_page_ready(page)
        await page.mouse.move(x, y)
        self._set_pointer_position(x, y)

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

    async def drag_to(self, page: Page, x: float, y: float):
        await self._ensure_page_ready(page)
        await page.mouse.down()
        await page.mouse.move(x, y, steps=20)
        await page.mouse.up()
        self._set_pointer_position(x, y)

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

        self.page: Page | None = None
        self.context = None
        self.browser = None
        self.p = None

        self.controller = PlaywrightController(
            veiwport_width=self.viewport_width, vewport_height=self.viewport_height
        )

    async def create(self, id: str) -> None:
        self.id = id

        self.p = await async_playwright().start()
        self.browser = await self.p.chromium.launch()
        self.context = await self.browser.new_context(
            viewport={"width": self.viewport_width, "height": self.viewport_height}
        )
        self.page = await self.context.new_page()
        await self.controller.on_new_page(self.page)

    async def delete(self) -> None:
        if self.page:
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.p:
            await self.p.stop()

        self.id = None
        self.page = None
        self.context = None
        self.browser = None
        self.p = None

    async def idle(self) -> bool:
        states = {
            "page": self.page is None,
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
        if self.page is None:
            raise RuntimeError("[FATAL] page is none")

        screenshot_bytes = await self.controller.get_screenshot(self.page)
        mouse_x, mouse_y = self.controller.pointer_position
        return BytesIO(screenshot_bytes), mouse_x, mouse_y

    async def execute(self, command: Command):
        if self.page is None:
            raise RuntimeError("[FATAL] page is none")

        match command.command:
            case CommandType.NAVIGATE:
                return await self.controller.visit_page(self.page, command.url)

            case CommandType.MOUSE_MOVE:
                return await self.controller.hover_coords(self.page, command.x, command.y)

            case CommandType.MOUSE_CLICK:
                return await self.controller.click_coords(
                    self.page,
                    command.x,
                    command.y,
                    command.button,
                    click_count=command.clickCount,
                )

            case CommandType.MOUSE_DOWN:
                return await self.controller.mouse_down(self.page)

            case CommandType.MOUSE_UP:
                return await self.controller.mouse_up(self.page)

            case CommandType.MOUSE_WHEEL:
                return await self.controller.scroll_pointer(self.page, command.dx, command.dy)

            case CommandType.DRAG_TO:
                return await self.controller.drag_to(self.page, command.x, command.y)

            case CommandType.KEYBOARD_TYPE:
                return await self.controller.keyboard_type(self.page, command.text)

            case CommandType.KEY_DOWN:
                return await self.controller.key_down(self.page, command.key)

            case CommandType.KEY_UP:
                return await self.controller.key_up(self.page, command.key)

            case CommandType.KEY_PRESS:
                return await self.controller.key_press(self.page, command.key)

            case CommandType.HOT_KEY:
                return await self.controller.hotkey_press(self.page, command.keys)

            case CommandType.SNAPSHOT:
                snapshot = await self.controller.get_page_snapshot(
                    self.page,
                    command.rules,
                )
                return SnapshotResponse(snapshot=snapshot)

            case CommandType.INTERACTIVE_TREE:
                rects = await self.controller.get_interactive_rects(self.page)
                mouse_x, mouse_y = self.controller.pointer_position
                return InteractiveTreeResponse(
                    mouse_position=MousePosition(x=int(mouse_x), y=int(mouse_y)),
                    regions=rects,
                )

            case CommandType.SLEEP:
                await self.controller.sleep(self.page, command.duration_ms)

            case _ as unreachable:
                assert_never(unreachable)
