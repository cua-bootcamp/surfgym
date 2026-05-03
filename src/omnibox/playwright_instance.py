from io import BytesIO

from playwright.async_api import Page, async_playwright
from typing_extensions import assert_never

from src.omnibox.playwright_controller import PlaywrightController
from src.omnibox.protocol.instance_server_response import (
    InteractiveTreeResponse,
    MousePosition,
    PageSnapshot,
    SnapshotResponse,
)
from src.omnibox.protocol.omnibox_command import CommandType, OmniboxCommand


class PlaywrightInstance:
    def __init__(self):
        self.id = None

        self.VIEWPORT_WIDTH = 1920
        self.VIEWPORT_HEIGHT = 1080

        self.page: Page | None = None
        self.context = None
        self.browser = None
        self.p = None

        self.controller = PlaywrightController(
            veiwport_width=self.VIEWPORT_WIDTH, vewport_height=self.VIEWPORT_HEIGHT
        )

    async def create(self, id: str) -> None:
        self.id = id

        self.p = await async_playwright().start()
        self.browser = await self.p.chromium.launch()
        self.context = await self.browser.new_context(
            viewport={"width": self.VIEWPORT_WIDTH, "height": self.VIEWPORT_HEIGHT}
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

    async def execute(self, command: OmniboxCommand):
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
                    command.selectors,
                    command.include_html,
                )
                return SnapshotResponse(snapshot=PageSnapshot.model_validate(snapshot))

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
