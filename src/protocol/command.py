from typing import Annotated, Literal, Optional, TypeAlias, Union

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from src.components.task import Evaluation

###################
# Action Commands #
###################

MouseButtonType: TypeAlias = Literal["left", "right", "middle"]


class _BaseCommand(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


# https://playwright.dev/docs/api/class-mouse#mouse-move
class MouseMoveCommand(_BaseCommand):
    command: Literal["mouse_move"] = "mouse_move"
    x: float
    y: float


class DragToCommand(_BaseCommand):
    command: Literal["drag_to"] = "drag_to"
    x: float
    y: float


# https://playwright.dev/docs/api/class-mouse#mouse-wheel
class MouseWheelCommand(_BaseCommand):
    command: Literal["mouse_wheel"] = "mouse_wheel"
    dx: float
    dy: float


# https://playwright.dev/docs/api/class-mouse#mouse-click
class MouseClickCommand(_BaseCommand):
    command: Literal["mouse_click"] = "mouse_click"
    x: Optional[float] = None
    y: Optional[float] = None
    button: MouseButtonType
    clickCount: int = Field(ge=1)


# https://playwright.dev/docs/api/class-mouse#mouse-down
class MouseDownCommand(_BaseCommand):
    command: Literal["mouse_down"] = "mouse_down"


# https://playwright.dev/docs/api/class-mouse#mouse-up
class MouseUpCommand(_BaseCommand):
    command: Literal["mouse_up"] = "mouse_up"


# https://playwright.dev/docs/api/class-keyboard#keyboard-type
class KeyboardTypeCommand(_BaseCommand):
    command: Literal["typing"] = "typing"
    text: str


class _BaseKeyCommand(_BaseCommand):
    key: str


# https://playwright.dev/docs/api/class-keyboard#keyboard-down
class KeyDownCommand(_BaseKeyCommand):
    command: Literal["key_down"] = "key_down"


# https://playwright.dev/docs/api/class-keyboard#keyboard-up
class KeyUpCommand(_BaseKeyCommand):
    command: Literal["key_up"] = "key_up"


# https://playwright.dev/docs/api/class-keyboard#keyboard-press
class KeyPressCommand(_BaseKeyCommand):
    command: Literal["key_press"] = "key_press"


class HotKeyCommand(_BaseCommand):
    command: Literal["hot_key"] = "hot_key"
    keys: list[str]


class ObserveCommand(_BaseCommand):
    command: Literal["observe"] = "observe"
    evaluation: Evaluation


class InteractiveTreeCommand(_BaseCommand):
    command: Literal["interactive_tree"] = "interactive_tree"


class SleepCommand(_BaseCommand):
    command: Literal["sleep"] = "sleep"
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
    ObserveCommand,
    InteractiveTreeCommand,
]

Command = Annotated[
    CommandPayload,
    Field(discriminator="command"),
]

CommandAdapter: TypeAdapter[Command] = TypeAdapter(Command)
