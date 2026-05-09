from string import ascii_uppercase
from typing import Annotated, Any, Literal, Optional, TypeAlias, Union

from pydantic import BaseModel, ConfigDict, Field, GetCoreSchemaHandler, TypeAdapter
from pydantic_core import core_schema

from src.components.task import Evaluation

###################
# Action Commands #
###################

MouseButtonType: TypeAlias = Literal["left", "right", "middle"]


_MODIFIER_KEYS = {"Shift", "Control", "Alt", "Meta", "ShiftLeft", "ControlOrMeta"}

_PLAYWRIGHT_KEY_NAMES = {
    *_MODIFIER_KEYS,
    "Backquote",
    "Minus",
    "Equal",
    "Backslash",
    "Backspace",
    "Tab",
    "Delete",
    "Escape",
    "ArrowDown",
    "ArrowLeft",
    "ArrowRight",
    "ArrowUp",
    "End",
    "Enter",
    "Home",
    "Insert",
    "PageDown",
    "PageUp",
    "Space",
    "CapsLock",
    "ContextMenu",
    "PrintScreen",
    "ScrollLock",
    "Pause",
    "BracketLeft",
    "BracketRight",
    "Semicolon",
    "Quote",
    "Comma",
    "Period",
    "Slash",
    "NumpadAdd",
    "NumpadSubtract",
    "NumpadMultiply",
    "NumpadDivide",
    "NumpadDecimal",
    "NumpadEnter",
    *{f"F{i}" for i in range(1, 13)},
    *{f"Digit{i}" for i in range(10)},
    *{f"Key{char}" for char in ascii_uppercase},
    *{f"Numpad{i}" for i in range(10)},
}

KEY_NAME_BY_LOWER = {key.lower(): key for key in _PLAYWRIGHT_KEY_NAMES}


class PlaywrightKey(str):
    @classmethod
    def __get_pydantic_core_schema__(cls, source_type: Any, handler: GetCoreSchemaHandler):
        return core_schema.no_info_after_validator_function(
            cls._validate,
            core_schema.str_schema(),
        )

    @classmethod
    def _validate(cls, value: str) -> "PlaywrightKey":
        if len(value) == 1:
            if "a" <= value <= "z" or "A" <= value <= "Z":
                return cls(value)

        normalized = KEY_NAME_BY_LOWER.get(value.lower())
        if normalized is not None:
            return cls(normalized)

        raise ValueError(f"PlayWright does not support {value} key.")


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
    key: PlaywrightKey


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
    keys: list[PlaywrightKey]


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
