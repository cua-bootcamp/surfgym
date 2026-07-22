from __future__ import annotations

from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field

from surfgym_contracts.command import (
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
    PlaywrightKey,
    SleepCommand,
)


class _BaseComputerAction(BaseModel):
    model_config = ConfigDict(frozen=True)

    @property
    def parameters(self) -> dict[str, Any]:
        return self.model_dump(exclude={"action_type"})

    def to_commands(self) -> Command:
        raise NotImplementedError(f"{self.__class__.__name__} must implement to_commands()")


class MoveToAction(_BaseComputerAction):
    action_type: Literal["MOVE_TO"]
    x: float
    y: float

    def to_commands(self) -> MouseMoveCommand:
        return MouseMoveCommand(x=self.x, y=self.y)


class DragToAction(_BaseComputerAction):
    action_type: Literal["DRAG_TO"]
    x: float
    y: float

    def to_commands(self) -> DragToCommand:
        return DragToCommand(x=self.x, y=self.y)


class ScrollAction(_BaseComputerAction):
    action_type: Literal["SCROLL"]
    dx: int
    dy: int

    def to_commands(self) -> MouseWheelCommand:
        return MouseWheelCommand(dx=self.dx, dy=self.dy)


class TypingAction(_BaseComputerAction):
    action_type: Literal["TYPING"]
    text: str

    def to_commands(self) -> KeyboardTypeCommand:
        return KeyboardTypeCommand(text=self.text)


class WaitAction(_BaseComputerAction):
    action_type: Literal["WAIT"]

    def to_commands(self) -> SleepCommand:
        return SleepCommand(duration_ms=1000)


###################
# Terminal Action #
###################


class FailAction(_BaseComputerAction):
    action_type: Literal["FAIL"]

    def to_commands(self):
        raise AssertionError(f"{self.__class__.__name__} does not have a corresponding command ")


class DoneAction(_BaseComputerAction):
    action_type: Literal["DONE"]

    def to_commands(self):
        raise AssertionError(f"{self.__class__.__name__} does not have a corresponding command ")


#####################
# Single Key Action #
#####################


class _SingleKeyAction(_BaseComputerAction):
    key: PlaywrightKey


class PressAction(_SingleKeyAction):
    action_type: Literal["PRESS"]

    def to_commands(self) -> KeyPressCommand:
        return KeyPressCommand(key=self.key)


class KeyDownAction(_SingleKeyAction):
    action_type: Literal["KEY_DOWN"]

    def to_commands(self) -> KeyDownCommand:
        return KeyDownCommand(key=self.key)


class KeyUpAction(_SingleKeyAction):
    action_type: Literal["KEY_UP"]

    def to_commands(self) -> KeyUpCommand:
        return KeyUpCommand(key=self.key)


type SingleKeyAction = PressAction | KeyDownAction | KeyUpAction


####################
# Multi Key Action #
####################


class HotkeyAction(_BaseComputerAction):
    action_type: Literal["HOTKEY"]
    keys: list[PlaywrightKey]

    def to_commands(self) -> HotKeyCommand:
        return HotKeyCommand(keys=self.keys)


################
# Mouse Action #
################


class _MouseAction(_BaseComputerAction):
    button: MouseButtonType = "left"


class MouseDownAction(_MouseAction):
    action_type: Literal["MOUSE_DOWN"]

    def to_commands(self) -> MouseDownCommand:
        return MouseDownCommand()


class MouseUpAction(_MouseAction):
    action_type: Literal["MOUSE_UP"]

    def to_commands(self) -> MouseUpCommand:
        return MouseUpCommand()


type MouseAction = MouseDownAction | MouseUpAction


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
    action_type: Literal["CLICK"]
    button: MouseButtonType = "left"
    num_clicks: int = Field(default=1, ge=1)

    def to_commands(self) -> MouseClickCommand:
        return self._to_click_command(
            button=self.button,
            click_count=self.num_clicks,
        )


class RightClickAction(_BaseClickAction):
    action_type: Literal["RIGHT_CLICK"]

    def to_commands(self) -> MouseClickCommand:
        return self._to_click_command(
            button="right",
            click_count=1,
        )


class DoubleClickAction(_BaseClickAction):
    action_type: Literal["DOUBLE_CLICK"]

    def to_commands(self) -> MouseClickCommand:
        return self._to_click_command(
            button="left",
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
