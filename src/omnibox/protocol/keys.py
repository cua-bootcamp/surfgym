from typing import Annotated

from pydantic import AfterValidator

LETTER_KEYS = {f"Key{chr(code)}" for code in range(ord("A"), ord("Z") + 1)}
DIGIT_KEYS = {f"Digit{i}" for i in range(10)}
FUNCTION_KEYS = {f"F{i}" for i in range(1, 13)}

NAMED_KEYS = (
    LETTER_KEYS
    | DIGIT_KEYS
    | FUNCTION_KEYS
    | {
        # modifiers
        "Shift",
        "ShiftLeft",
        "Control",
        "Alt",
        "Meta",
        "ControlOrMeta",
        # navigation
        "ArrowUp",
        "ArrowDown",
        "ArrowLeft",
        "ArrowRight",
        "Home",
        "End",
        "PageUp",
        "PageDown",
        # editing / control
        "Enter",
        "Tab",
        "Escape",
        "Backspace",
        "Delete",
        "Insert",
        # symbols / misc
        "Backquote",
        "Minus",
        "Equal",
        "Backslash",
        "Space",
    }
)


def _validate_key(value: str) -> str:
    if len(value) == 1:
        return value

    if value in NAMED_KEYS:
        return value

    raise ValueError(
        f"Unsupported key: {value!r}. "
        "Expected a named Playwright key (e.g. Enter, ArrowDown, KeyA) "
        "or a single character (e.g. 'a', 'A', '1', '$')."
    )


Key = Annotated[str, AfterValidator(_validate_key)]
