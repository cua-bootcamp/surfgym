import asyncio
from typing import Any, cast

import pytest
from surfgym_contracts.command import (
    DragToCommand,
    KeyboardTypeCommand,
    MouseDownCommand,
    MouseMoveCommand,
    MouseWheelCommand,
)
from surfgym_runtime.wavepool.instance.error import InvalidCommand
from surfgym_runtime.wavepool.instance.service import PlaywrightBrowserWorker
from surfgym_runtime.wavepool.instance.session import Context, PageLayout


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


class _Keyboard:
    def __init__(self) -> None:
        self.events: list[tuple[str, str]] = []

    async def type(self, text: str) -> None:
        self.events.append(("type", text))


class _Page:
    def __init__(self) -> None:
        self.mouse = _Mouse()
        self.keyboard = _Keyboard()


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
