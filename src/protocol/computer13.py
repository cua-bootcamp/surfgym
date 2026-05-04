from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, Literal, TypeAlias, Union

from pydantic import BaseModel, ConfigDict, Field

from src.protocol.command import (
    Command,
    DragToCommand,
    HotKeyCommand,
    KeyboardTypeCommand,
    KeyDownCommand,
    KeyPressCommand,
    KeyUpCommand,
    MouseButtonType,
    MouseClickCommand,
    MouseDownCommand,
    MouseMoveCommand,
    MouseUpCommand,
    MouseWheelCommand,
    SleepCommand,
)


class ActionType(str, Enum):
    MOVE_TO = "MOVE_TO"
    CLICK = "CLICK"
    MOUSE_DOWN = "MOUSE_DOWN"
    MOUSE_UP = "MOUSE_UP"
    RIGHT_CLICK = "RIGHT_CLICK"
    DOUBLE_CLICK = "DOUBLE_CLICK"
    DRAG_TO = "DRAG_TO"
    SCROLL = "SCROLL"
    TYPING = "TYPING"
    PRESS = "PRESS"
    KEY_DOWN = "KEY_DOWN"
    KEY_UP = "KEY_UP"
    HOTKEY = "HOTKEY"
    WAIT = "WAIT"
    FAIL = "FAIL"
    DONE = "DONE"


class _BaseComputerAction(BaseModel):
    model_config = ConfigDict(frozen=True)

    @property
    def parameters(self) -> dict[str, Any]:
        return self.model_dump(exclude={"action_type"})

    def to_commands(self) -> Command:
        raise NotImplementedError(f"{self.__class__.__name__} must implement to_commands()")


class MoveToAction(_BaseComputerAction):
    action_type: Literal[ActionType.MOVE_TO] = ActionType.MOVE_TO
    x: float
    y: float

    def to_commands(self) -> MouseMoveCommand:
        return MouseMoveCommand(x=self.x, y=self.y)


class DragToAction(_BaseComputerAction):
    action_type: Literal[ActionType.DRAG_TO]
    x: float
    y: float

    def to_commands(self) -> DragToCommand:
        return DragToCommand(x=self.x, y=self.y)


class ScrollAction(_BaseComputerAction):
    action_type: Literal[ActionType.SCROLL]
    dx: int
    dy: int

    def to_commands(self) -> MouseWheelCommand:
        return MouseWheelCommand(dx=self.dx, dy=self.dy)


class TypingAction(_BaseComputerAction):
    action_type: Literal[ActionType.TYPING]
    text: str

    def to_commands(self) -> KeyboardTypeCommand:
        return KeyboardTypeCommand(text=self.text)


class WaitAction(_BaseComputerAction):
    action_type: Literal[ActionType.WAIT]

    def to_commands(self) -> SleepCommand:
        return SleepCommand(duration_ms=1000)


###################
# Terminal Action #
###################


class FailAction(_BaseComputerAction):
    action_type: Literal[ActionType.FAIL]

    def to_commands(self):
        raise AssertionError(f"{self.__class__.__name__} does not have a corresponding command ")


class DoneAction(_BaseComputerAction):
    action_type: Literal[ActionType.DONE]

    def to_commands(self):
        raise AssertionError(f"{self.__class__.__name__} does not have a corresponding command ")


TerminalAction: TypeAlias = FailAction | DoneAction

#####################
# Single Key Action #
#####################


class _SingleKeyAction(_BaseComputerAction):
    key: str


class PressAction(_SingleKeyAction):
    action_type: Literal[ActionType.PRESS]

    def to_commands(self) -> KeyPressCommand:
        return KeyPressCommand(key=self.key)


class KeyDownAction(_SingleKeyAction):
    action_type: Literal[ActionType.KEY_DOWN]

    def to_commands(self) -> KeyDownCommand:
        return KeyDownCommand(key=self.key)


class KeyUpAction(_SingleKeyAction):
    action_type: Literal[ActionType.KEY_UP]

    def to_commands(self) -> KeyUpCommand:
        return KeyUpCommand(key=self.key)


SingleKeyAction: TypeAlias = PressAction | KeyDownAction | KeyUpAction


####################
# Multi Key Action #
####################


class HotkeyAction(_BaseComputerAction):
    action_type: Literal[ActionType.HOTKEY]
    keys: list[str]

    def to_commands(self) -> HotKeyCommand:
        return HotKeyCommand(keys=self.keys)


MultiKeyAction: TypeAlias = HotkeyAction


################
# Mouse Action #
################


class _MouseAction(_BaseComputerAction):
    button: MouseButtonType = MouseButtonType.LEFT


class MouseDownAction(_MouseAction):
    action_type: Literal[ActionType.MOUSE_DOWN]

    def to_commands(self) -> MouseDownCommand:
        return MouseDownCommand()


class MouseUpAction(_MouseAction):
    action_type: Literal[ActionType.MOUSE_UP]

    def to_commands(self) -> MouseUpCommand:
        return MouseUpCommand()


MouseAction: TypeAlias = MouseDownAction | MouseUpAction


################
# Click Action #
################


class _BaseClickAction(_BaseComputerAction):
    x: int | None = None
    y: int | None = None

    def _to_click_command(
        self,
        *,
        button: MouseButtonType,
        click_count: int,
    ) -> MouseClickCommand:
        return MouseClickCommand(
            x=self.x,
            y=self.y,
            button=button,
            clickCount=click_count,
        )


class ClickAction(_BaseClickAction):
    action_type: Literal[ActionType.CLICK] = ActionType.CLICK
    button: MouseButtonType = MouseButtonType.LEFT
    num_clicks: int = Field(default=1, ge=1)

    def to_commands(self) -> MouseClickCommand:
        return self._to_click_command(
            button=self.button,
            click_count=self.num_clicks,
        )


class RightClickAction(_BaseClickAction):
    action_type: Literal[ActionType.RIGHT_CLICK] = ActionType.RIGHT_CLICK

    def to_commands(self) -> MouseClickCommand:
        return self._to_click_command(
            button=MouseButtonType.RIGHT,
            click_count=1,
        )


class DoubleClickAction(_BaseClickAction):
    action_type: Literal[ActionType.DOUBLE_CLICK] = ActionType.DOUBLE_CLICK

    def to_commands(self) -> MouseClickCommand:
        return self._to_click_command(
            button=MouseButtonType.LEFT,
            click_count=2,
        )


Computer13 = Annotated[
    Union[
        MoveToAction,
        ClickAction,
        MouseDownAction,
        MouseUpAction,
        RightClickAction,
        DoubleClickAction,
        DragToAction,
        ScrollAction,
        TypingAction,
        PressAction,
        KeyDownAction,
        KeyUpAction,
        HotkeyAction,
        WaitAction,
        FailAction,
        DoneAction,
    ],
    Field(discriminator="action_type"),
]
