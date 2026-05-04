from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union, cast

from playwright.async_api import Page

from src.wavepool.protocol.instance_server_response import InteractiveRegion
from src.wavepool.protocol.omnibox_command import MouseButtonType

# # Some of the Code for clicking coordinates and keypresses adapted from https://github.com/openai/openai-cua-sample-app/blob/main/computers/base_playwright.py
# # Copyright 2025 OpenAI - MIT License
# CUA_KEY_TO_PLAYWRIGHT_KEY = {
#     "/": "Slash",
#     "slash": "Slash",
#     "divide": "NumpadDivide",
#     # "/": "Divide",
#     "\\": "Backslash",
#     "alt": "Alt",
#     "arrowdown": "ArrowDown",
#     "arrowleft": "ArrowLeft",
#     "arrowright": "ArrowRight",
#     "arrowup": "ArrowUp",
#     "backspace": "Backspace",
#     "capslock": "CapsLock",
#     "cmd": "Meta",
#     "ctrl": "Control",
#     "delete": "Delete",
#     "end": "End",
#     "enter": "Enter",
#     "esc": "Escape",
#     "home": "Home",
#     "insert": "Insert",
#     "option": "Alt",
#     "pagedown": "PageDown",
#     "pageup": "PageUp",
#     "shift": "Shift",
#     "space": " ",
#     "super": "Meta",
#     "tab": "Tab",
#     "win": "Meta",
# }


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
        selectors: list[str] | None = None,
        include_html: bool = False,
    ) -> Dict[str, Any]:
        await self._ensure_page_ready(page)
        return cast(
            Dict[str, Any],
            await page.evaluate(
                """({ selectors, includeHtml }) => {
                    const selectorList = Array.isArray(selectors) ? selectors : [];

                    function isVisible(el) {
                        const style = window.getComputedStyle(el);
                        const rect = el.getBoundingClientRect();
                        const hasBox =
                            rect.width > 0 ||
                            rect.height > 0 ||
                            el.getClientRects().length > 0;
                        return hasBox &&
                            style.display !== "none" &&
                            style.visibility !== "hidden" &&
                            style.opacity !== "0";
                    }

                    function attributesFor(el) {
                        const attrs = {};
                        for (const attr of Array.from(el.attributes || [])) {
                            attrs[attr.name] = attr.value;
                        }
                        return attrs;
                    }

                    function elementSnapshot(el) {
                        return {
                            tagName: (el.tagName || "").toLowerCase(),
                            text: el.innerText || el.textContent || "",
                            textContent: el.textContent || "",
                            html: el.outerHTML || "",
                            visible: isVisible(el),
                            attributes: attributesFor(el),
                            value: "value" in el ? String(el.value) : "",
                            checked: "checked" in el ? Boolean(el.checked) : false,
                        };
                    }

                    const elements = {};
                    const selectorErrors = {};
                    for (const selector of selectorList) {
                        try {
                            elements[selector] = Array.from(document.querySelectorAll(selector))
                                .slice(0, 100)
                                .map(elementSnapshot);
                        } catch (error) {
                            selectorErrors[selector] = String(
                                error && error.message ? error.message : error
                            );
                            elements[selector] = [];
                        }
                    }

                    return {
                        url: window.location.href,
                        title: document.title || "",
                        text: document.body ? document.body.innerText || "" : "",
                        html: includeHtml && document.documentElement
                            ? document.documentElement.outerHTML || ""
                            : "",
                        elements,
                        selector_errors: selectorErrors,
                    };
                }""",
                {
                    "selectors": selectors or [],
                    "includeHtml": include_html,
                },
            ),
        )
