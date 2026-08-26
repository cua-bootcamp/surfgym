import asyncio
from io import BytesIO
from typing import Any, cast

import pytest
from PIL import Image
from surfgym_contracts.command import (
    DragToCommand,
    HotKeyCommand,
    KeyboardTypeCommand,
    KeyDownCommand,
    KeyPressCommand,
    KeyUpCommand,
    MouseClickCommand,
    MouseDownCommand,
    MouseMoveCommand,
    MouseUpCommand,
    MouseWheelCommand,
    SleepCommand,
)
from surfgym_runtime.wavepool.instance.error import InvalidCommand
from surfgym_runtime.wavepool.instance.service import PlaywrightBrowserWorker
from surfgym_runtime.wavepool.instance.session import (
    Context,
    ContextManager,
    PageCursor,
    PageLayout,
    ScreenCursor,
)


class _Mouse:
    def __init__(self) -> None:
        self.events: list[tuple[object, ...]] = []

    async def move(self, x: float, y: float, *, steps: int | None = None) -> None:
        self.events.append(("move", x, y, steps))

    async def down(self) -> None:
        self.events.append(("down",))

    async def up(self) -> None:
        self.events.append(("up",))

    async def wheel(self, dx: float, dy: float) -> None:
        self.events.append(("wheel", dx, dy))

    async def click(
        self,
        x: float,
        y: float,
        *,
        delay: int,
        button: str,
        click_count: int,
    ) -> None:
        self.events.append(("click", x, y, delay, button, click_count))


class _Keyboard:
    def __init__(self) -> None:
        self.events: list[tuple[str, str]] = []

    async def type(self, text: str) -> None:
        self.events.append(("type", text))

    async def down(self, key: str) -> None:
        self.events.append(("down", key))

    async def up(self, key: str) -> None:
        self.events.append(("up", key))

    async def press(self, key: str) -> None:
        self.events.append(("press", key))


class _Page:
    def __init__(self) -> None:
        self.mouse = _Mouse()
        self.keyboard = _Keyboard()
        self.waits: list[int] = []

    async def wait_for_timeout(self, duration_ms: int) -> None:
        self.waits.append(duration_ms)

    async def evaluate(self, _script: str, _argument: object) -> None:
        return None


class _ContextManager:
    def __init__(self) -> None:
        self.left = _Page()
        self.right = _Page()
        self.context = Context(
            context_id="context-id",
            context=cast(Any, object()),
            pages={
                "left": (cast(Any, self.left), PageLayout(x=0, y=0, width=960, height=1080)),
                "right": (
                    cast(Any, self.right),
                    PageLayout(x=960, y=0, width=960, height=1080),
                ),
            },
            active_page_id="left",
        )

    def require_context(self, _context_id: str) -> Context:
        return self.context

    def require_page(self, _context_id: str, website_id: str):
        return self.context.pages[website_id]

    def focus_page_at_screen_cursor(self, ctx: Context, cursor):
        from surfgym_runtime.wavepool.instance.session import ContextManager

        return ContextManager.focus_page_at_screen_cursor(ctx, cursor)

    def page_at_screen_cursor(self, ctx: Context, cursor):
        from surfgym_runtime.wavepool.instance.session import ContextManager

        return ContextManager.page_at_screen_cursor(ctx, cursor)


def _worker() -> tuple[PlaywrightBrowserWorker, _ContextManager]:
    worker = PlaywrightBrowserWorker(contexts_per_instance=1)
    manager = _ContextManager()
    worker.ctx_manager = cast(Any, manager)
    return worker, manager


def test_screen_pointer_focuses_the_matching_surface_and_translates_coordinates() -> None:
    worker, manager = _worker()

    asyncio.run(worker.execute("context-id", MouseMoveCommand(x=1000, y=25)))

    assert manager.context.active_page_id == "right"
    assert manager.context.cursor.x == 40
    assert manager.context.cursor.y == 25
    assert manager.left.mouse.events == []
    assert manager.right.mouse.events == [("move", 40, 25, None)]


def test_keyboard_and_wheel_follow_the_surface_selected_by_pointer_focus() -> None:
    worker, manager = _worker()

    async def scenario() -> None:
        await worker.execute("context-id", MouseMoveCommand(x=1200, y=10))
        await worker.execute("context-id", MouseWheelCommand(dx=0, dy=80))
        await worker.execute("context-id", KeyboardTypeCommand(text="hello"))

    asyncio.run(scenario())

    assert manager.left.mouse.events == []
    assert manager.left.keyboard.events == []
    assert manager.right.mouse.events == [("move", 240, 10, None), ("wheel", 0, 80)]
    assert manager.right.keyboard.events == [("type", "hello")]


def test_wait_uses_the_active_surface_without_changing_focus() -> None:
    worker, manager = _worker()

    async def scenario() -> None:
        await worker.execute("context-id", MouseMoveCommand(x=1200, y=10))
        await worker.execute("context-id", SleepCommand(duration_ms=250))

    asyncio.run(scenario())

    assert manager.context.active_page_id == "right"
    assert manager.left.waits == []
    assert manager.right.waits == [250]


def test_click_focuses_target_surface_and_translates_coordinates() -> None:
    worker, manager = _worker()

    asyncio.run(
        worker.execute(
            "context-id",
            MouseClickCommand(x=1000, y=25, button="left", clickCount=2),
        )
    )

    assert manager.context.active_page_id == "right"
    assert manager.right.mouse.events == [("click", 40, 25, 10, "left", 2)]


def test_key_commands_and_mouse_up_follow_active_surface() -> None:
    worker, manager = _worker()

    async def scenario() -> None:
        await worker.execute("context-id", MouseMoveCommand(x=1200, y=10))
        await worker.execute("context-id", KeyDownCommand(key="Control"))
        await worker.execute("context-id", KeyUpCommand(key="Control"))
        await worker.execute("context-id", KeyPressCommand(key="Enter"))
        await worker.execute("context-id", HotKeyCommand(keys=["Control", "A"]))
        await worker.execute("context-id", MouseDownCommand())
        await worker.execute("context-id", MouseUpCommand())

    asyncio.run(scenario())

    assert manager.right.keyboard.events == [
        ("down", "Control"),
        ("up", "Control"),
        ("press", "Enter"),
        ("down", "Control"),
        ("down", "A"),
        ("up", "A"),
        ("up", "Control"),
    ]
    assert manager.right.mouse.events[-2:] == [("down",), ("up",)]
    assert manager.context.mouse_down_page_id is None


def test_drag_to_rejects_cross_surface_destination_without_input_side_effects() -> None:
    worker, manager = _worker()

    with pytest.raises(InvalidCommand, match="cannot drag across independent page surfaces"):
        asyncio.run(worker.execute("context-id", DragToCommand(x=1000, y=25)))

    assert manager.context.active_page_id == "left"
    assert manager.left.mouse.events == []
    assert manager.right.mouse.events == []


def test_pointer_move_rejects_cross_surface_motion_while_mouse_is_down() -> None:
    worker, manager = _worker()

    async def scenario() -> None:
        await worker.execute("context-id", MouseDownCommand())
        with pytest.raises(InvalidCommand, match="cannot drag across independent page surfaces"):
            await worker.execute("context-id", MouseMoveCommand(x=1000, y=25))

    asyncio.run(scenario())

    assert manager.context.mouse_down_page_id is None
    assert manager.left.mouse.events == [("down",), ("up",)]
    assert manager.right.mouse.events == []


def test_drag_to_rejection_releases_an_explicit_origin_mouse_down() -> None:
    worker, manager = _worker()

    async def scenario() -> None:
        await worker.execute("context-id", MouseDownCommand())
        with pytest.raises(InvalidCommand, match="cannot drag across independent page surfaces"):
            await worker.execute("context-id", DragToCommand(x=1000, y=25))

    asyncio.run(scenario())

    assert manager.context.mouse_down_page_id is None
    assert manager.left.mouse.events == [("down",), ("up",)]
    assert manager.right.mouse.events == []


def test_drag_to_preserves_single_surface_behavior() -> None:
    worker, manager = _worker()

    asyncio.run(worker.execute("context-id", DragToCommand(x=100, y=25)))

    assert manager.context.active_page_id == "left"
    assert manager.context.mouse_down_page_id is None
    assert manager.left.mouse.events == [
        ("down",),
        ("move", 100, 25, 20),
        ("up",),
    ]


@pytest.mark.parametrize(
    ("page_count", "points"),
    [
        (3, [(100, 100, "p0"), (1000, 100, "p1"), (1000, 700, "p2")]),
        (
            4,
            [
                (100, 100, "p0"),
                (1000, 100, "p1"),
                (100, 700, "p2"),
                (1000, 700, "p3"),
            ],
        ),
    ],
)
def test_three_and_four_surface_layout_boundaries_route_to_expected_pages(
    page_count: int,
    points: list[tuple[int, int, str]],
) -> None:
    manager = ContextManager(contexts_per_instance=1, vw=1920, vh=1080)
    layouts = manager._build_page_layouts(page_count)
    ctx = Context(
        context_id="context-id",
        context=cast(Any, object()),
        pages={f"p{index}": (cast(Any, object()), layout) for index, layout in enumerate(layouts)},
        active_page_id="p0",
    )

    assert sum(layout.width * layout.height for layout in layouts) == 1920 * 1080
    for x, y, expected_page_id in points:
        page_id, _, _ = manager.page_at_screen_cursor(ctx, ScreenCursor(x, y))
        assert page_id == expected_page_id


def test_screenshot_composes_four_surfaces_without_gaps(monkeypatch: Any) -> None:
    colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]

    class ScreenshotPage:
        def __init__(self, color: tuple[int, int, int]) -> None:
            self.color = color

        async def screenshot(self) -> bytes:
            image = Image.new("RGB", (960, 540), self.color)
            output = BytesIO()
            image.save(output, format="PNG")
            return output.getvalue()

    worker = PlaywrightBrowserWorker(contexts_per_instance=1)
    manager = _ContextManager()
    layouts = ContextManager(
        contexts_per_instance=1,
        vw=1920,
        vh=1080,
    )._build_page_layouts(4)
    manager.context.pages = {
        f"p{index}": (cast(Any, ScreenshotPage(color)), layout)
        for index, (color, layout) in enumerate(zip(colors, layouts, strict=True))
    }
    manager.context.active_page_id = "p3"
    manager.context.cursor = PageCursor(10, 10)
    worker.ctx_manager = cast(Any, manager)

    async def no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr("surfgym_runtime.wavepool.instance.service.asyncio.sleep", no_sleep)
    screenshot, cursor_x, cursor_y = asyncio.run(worker.screenshot("context-id"))

    with Image.open(screenshot) as image:
        assert image.size == (1920, 1080)
        assert image.getpixel((100, 100)) == colors[0]
        assert image.getpixel((1000, 100)) == colors[1]
        assert image.getpixel((100, 700)) == colors[2]
        assert image.getpixel((1000, 700)) == colors[3]
    assert (cursor_x, cursor_y) == (970, 550)
