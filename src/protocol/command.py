from enum import Enum
from typing import Annotated, Literal, Optional, TypeAlias, Union

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from src.gateway.rule_evaluator import ObservationRequest
from src.gateway.task_store import Website

###################
# Action Commands #
###################


class MouseButtonType(str, Enum):
    LEFT = "left"
    RIGHT = "right"
    MIDDLE = "middle"


class CommandType(str, Enum):
    MOUSE_MOVE = "mouse_move"
    MOUSE_CLICK = "mouse_click"
    MOUSE_DOWN = "mouse_down"
    MOUSE_UP = "mouse_up"
    MOUSE_WHEEL = "mouse_wheel"
    DRAG_TO = "drag_to"

    KEYBOARD_TYPE = "keyboard_type"

    KEY_DOWN = "key_down"
    KEY_UP = "key_up"
    KEY_PRESS = "key_press"
    HOT_KEY = "hot_key"

    SLEEP = "SLEEP"

    SNAPSHOT = "SNAPSHOT"
    INTERACTIVE_TREE = "INTERACTIVE_TREE"
    NAVIGATE = "NAVIGATE"


class _BaseCommand(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


# https://playwright.dev/docs/api/class-mouse#mouse-move
class MouseMoveCommand(_BaseCommand):
    command: Literal[CommandType.MOUSE_MOVE] = CommandType.MOUSE_MOVE
    x: float
    y: float


class DragToCommand(_BaseCommand):
    command: Literal[CommandType.DRAG_TO] = CommandType.DRAG_TO
    x: float
    y: float


# https://playwright.dev/docs/api/class-mouse#mouse-wheel
class MouseWheelCommand(_BaseCommand):
    command: Literal[CommandType.MOUSE_WHEEL] = CommandType.MOUSE_WHEEL
    dx: float
    dy: float


# https://playwright.dev/docs/api/class-mouse#mouse-click
class MouseClickCommand(_BaseCommand):
    command: Literal[CommandType.MOUSE_CLICK] = CommandType.MOUSE_CLICK
    x: Optional[float] = None
    y: Optional[float] = None
    button: MouseButtonType
    clickCount: int = Field(ge=1)


# https://playwright.dev/docs/api/class-mouse#mouse-down
class MouseDownCommand(_BaseCommand):
    command: Literal[CommandType.MOUSE_DOWN] = CommandType.MOUSE_DOWN


# https://playwright.dev/docs/api/class-mouse#mouse-up
class MouseUpCommand(_BaseCommand):
    command: Literal[CommandType.MOUSE_UP] = CommandType.MOUSE_UP


# https://playwright.dev/docs/api/class-keyboard#keyboard-type
class KeyboardTypeCommand(_BaseCommand):
    command: Literal[CommandType.KEYBOARD_TYPE] = CommandType.KEYBOARD_TYPE
    text: str


class _BaseKeyCommand(_BaseCommand):
    key: str


# https://playwright.dev/docs/api/class-keyboard#keyboard-down
class KeyDownCommand(_BaseKeyCommand):
    command: Literal[CommandType.KEY_DOWN] = CommandType.KEY_DOWN


# https://playwright.dev/docs/api/class-keyboard#keyboard-up
class KeyUpCommand(_BaseKeyCommand):
    command: Literal[CommandType.KEY_UP] = CommandType.KEY_UP


# https://playwright.dev/docs/api/class-keyboard#keyboard-press
class KeyPressCommand(_BaseKeyCommand):
    command: Literal[CommandType.KEY_PRESS] = CommandType.KEY_PRESS


class HotKeyCommand(_BaseCommand):
    command: Literal[CommandType.HOT_KEY] = CommandType.HOT_KEY
    keys: list[str]


class SnapShotCommand(_BaseCommand):
    command: Literal[CommandType.SNAPSHOT] = CommandType.SNAPSHOT
    rules: list[ObservationRequest]


class NavigateCommand(_BaseCommand):
    command: Literal[CommandType.NAVIGATE] = CommandType.NAVIGATE
    websites: list[Website]


class InteractiveTreeCommand(_BaseCommand):
    command: Literal[CommandType.INTERACTIVE_TREE] = CommandType.INTERACTIVE_TREE


class SleepCommand(_BaseCommand):
    command: Literal[CommandType.SLEEP] = CommandType.SLEEP
    duration_ms: int


CommandPayload: TypeAlias = Union[
    MouseMoveCommand,
    DragToCommand,
    MouseWheelCommand,
    MouseClickCommand,
    MouseDownCommand,
    MouseUpCommand,
    KeyboardTypeCommand,
    KeyDownCommand,
    KeyUpCommand,
    KeyPressCommand,
    HotKeyCommand,
    SleepCommand,
    SnapShotCommand,
    NavigateCommand,
    InteractiveTreeCommand,
]

Command = Annotated[
    CommandPayload,
    Field(discriminator="command"),
]

CommandAdapter: TypeAdapter[Command] = TypeAdapter(Command)
