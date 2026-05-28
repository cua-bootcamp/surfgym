import json
import os
from pathlib import Path
from typing import Any, cast

from dotenv import load_dotenv
from openai import OpenAI  # pyright: ignore[reportMissingImports,reportUnknownVariableType]

from surfgym_task.augmentation.schema import HoareState, SeedTask, State

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def _dump_state(state: State) -> list[dict[str, Any]]:
    return [atom.model_dump(mode="json") for atom in state]


def _atom_func(atom: dict[str, Any]) -> str:
    value = atom.get("evalf", atom.get("f"))
    return value if isinstance(value, str) else ""


def _atom_param(atom: dict[str, Any]) -> str | None:
    value = atom.get("param")
    return value if isinstance(value, str) else None


def _atom_property(atom: dict[str, Any]) -> list[str]:
    value = atom.get("property", [])
    if not isinstance(value, list):
        return []

    result: list[str] = []
    for item in cast(list[object], value):
        if isinstance(item, str):
            result.append(item)
    return result


def _atom_identity(atom: dict[str, Any]) -> tuple[str, str | None, tuple[str, ...]]:
    return (_atom_func(atom), _atom_param(atom), tuple(_atom_property(atom)))


def _normalized_atom_value(atom: dict[str, Any]) -> Any:
    if _atom_func(atom) == "getCellMeta" and _atom_property(atom) == ["style", "bl"]:
        return _is_truthy_style_value(atom.get("value"))

    return atom.get("value")


def _atom_key(atom: dict[str, Any]) -> str:
    return json.dumps(
        {
            "evalf": _atom_func(atom),
            "param": _atom_param(atom),
            "property": _atom_property(atom),
            "value": _normalized_atom_value(atom),
        },
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _diff_state(start_state: State | None, end_state: State) -> list[dict[str, Any]]:
    end_atoms = _dump_state(end_state)

    if start_state is None:
        return end_atoms

    start_atom_keys = {_atom_key(atom) for atom in _dump_state(start_state)}
    return [atom for atom in end_atoms if _atom_key(atom) not in start_atom_keys]


def _is_truthy_style_value(value: Any) -> bool:
    return value in (1, True, "1", "true", "True")


def _property_label(prop: list[str]) -> str:
    if prop == ["cell", "v"]:
        return "cell.value"
    if prop == ["style", "bl"]:
        return "style.bold"
    if prop == ["style", "bg", "rgb"]:
        return "style.background_color"
    if prop == ["style", "n", "pattern"]:
        return "style.number_format"
    if prop == ["row", "visible"]:
        return "row.visible"
    if prop == ["row", "rawVisible"]:
        return "row.raw_visible"
    if prop == ["row", "filtered"]:
        return "row.filtered"
    return ".".join(prop) if prop else "object"


def _column_name_to_index(column_name: str) -> int:
    result = 0
    for char in column_name.upper():
        if not ("A" <= char <= "Z"):
            return 10**9
        result = result * 26 + ord(char) - 64
    return result - 1


def _cell_sort_key(address: str | None) -> tuple[int, int, str]:
    if address is None:
        return (10**9, 10**9, "")

    letters = ""
    digits = ""
    for char in address.strip().upper():
        if char == "$":
            continue
        if char.isalpha() and not digits:
            letters += char
        elif char.isdigit():
            digits += char
        else:
            return (10**9, 10**9, address)

    if not letters or not digits:
        return (10**9, 10**9, address)

    return (int(digits), _column_name_to_index(letters), address)


def _infer_operation_kind(instruction: str) -> str:
    text = instruction.lower()

    if "sort" in text:
        return "structural_sort"
    if "hide" in text or "visible" in text:
        return "structural_visibility"
    if "conditional" in text or ("duplicate" in text and ("bold" in text or "highlight" in text)):
        return "conditional_format"

    computed_terms = (
        "calculate",
        "computed",
        "compute",
        "sum",
        "summarize",
        "summary",
        "total",
        "count",
        "revenue",
        "tax",
        "charge",
        "rate",
        "lookup",
        "according to",
        "manager",
    )
    if any(term in text for term in computed_terms):
        return "computed_output"

    transformed_terms = (
        "split",
        "normalize",
        "round",
        "convert",
        "format the date",
        "phone number",
        "padding",
        "pad ",
        "padded",
    )
    if any(term in text for term in transformed_terms):
        return "transformed_output"

    format_terms = ("format", "bold", "background", "color", "highlight", "currency")
    if any(term in text for term in format_terms):
        return "direct_format"

    return "literal_entry"


def _hides_evaluator_values(operation_kind: str) -> bool:
    return operation_kind in {
        "computed_output",
        "transformed_output",
        "conditional_format",
        "structural_sort",
        "structural_visibility",
    }


def _value_is_named_in_source(value: Any, source_instruction: str) -> bool:
    if not isinstance(value, str):
        return False

    normalized = value.strip().lower()
    return bool(normalized) and normalized in source_instruction.lower()


def _include_value_in_prompt(atom: dict[str, Any], operation_kind: str, source_instruction: str) -> bool:
    if not _hides_evaluator_values(operation_kind):
        return True
    return _value_is_named_in_source(atom.get("value"), source_instruction)


def _requirement_role(atom: dict[str, Any], operation_kind: str, source_instruction: str) -> str:
    prop = _atom_property(atom)

    if prop == ["cell", "v"]:
        if _include_value_in_prompt(atom, operation_kind, source_instruction):
            return "literal_value"
        return "operation_result"

    if prop[:1] == ["style"]:
        if operation_kind == "conditional_format":
            return "conditional_format_effect"
        return "formatting"

    if prop[:1] == ["row"]:
        return "row_state"

    return "state_requirement"


def _public_requirement(
    atom: dict[str, Any],
    operation_kind: str,
    source_instruction: str,
) -> dict[str, Any]:
    prop = _atom_property(atom)
    value_visible = _include_value_in_prompt(atom, operation_kind, source_instruction)
    requirement = {
        "address": _atom_param(atom),
        "property": _property_label(prop),
        "role": _requirement_role(atom, operation_kind, source_instruction),
        "value_visible": value_visible,
    }

    if value_visible:
        requirement["value"] = atom.get("value")

    return requirement


def _public_context_atom(atom: dict[str, Any]) -> dict[str, Any]:
    prop = _atom_property(atom)
    return {
        "address": _atom_param(atom),
        "property": _property_label(prop),
        "value": atom.get("value"),
    }


def _flatten_states(states: list[State]) -> list[dict[str, Any]]:
    return [atom for state in states for atom in _dump_state(state)]


def _task_output_identities(seed_task: SeedTask) -> set[tuple[str, str | None, tuple[str, ...]]]:
    output_states = seed_task.states if seed_task.empty_start else seed_task.states[1:]
    return {_atom_identity(atom) for atom in _flatten_states(output_states)}


def _public_context(
    start_state: State | None,
    output_identities: set[tuple[str, str | None, tuple[str, ...]]],
    operation_kind: str,
    source_instruction: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if start_state is None:
        return ([], [])

    visible_context: list[dict[str, Any]] = []
    completed_targets: list[dict[str, Any]] = []

    for atom in _dump_state(start_state):
        is_output = _atom_identity(atom) in output_identities
        show_value = not is_output or _include_value_in_prompt(atom, operation_kind, source_instruction)

        if show_value:
            visible_context.append(_public_context_atom(atom))
        else:
            completed_targets.append(_public_requirement(atom, operation_kind, source_instruction))

    visible_context.sort(key=lambda item: (_cell_sort_key(item.get("address")), item["property"]))
    completed_targets.sort(key=lambda item: (_cell_sort_key(item.get("address")), item["property"]))
    return (visible_context, completed_targets)


def _build_instruction_payload(seed_task: SeedTask, hoare_state: HoareState) -> dict[str, Any]:
    required_state = _diff_state(hoare_state.start_state, hoare_state.end_state)
    operation_kind = _infer_operation_kind(seed_task.instruction)
    output_identities = _task_output_identities(seed_task)
    visible_context, completed_targets = _public_context(
        hoare_state.start_state,
        output_identities,
        operation_kind,
        seed_task.instruction,
    )

    pending_requirements = [
        _public_requirement(atom, operation_kind, seed_task.instruction) for atom in required_state
    ]
    pending_requirements.sort(key=lambda item: (_cell_sort_key(item.get("address")), item["property"]))

    return {
        "source_instruction": seed_task.instruction,
        "operation_contract": {
            "domain": "spreadsheet",
            "kind": operation_kind,
            "value_policy": (
                "hide_evaluator_values"
                if _hides_evaluator_values(operation_kind)
                else "literal_values_allowed"
            ),
        },
        "progress": {
            "completed_targets": completed_targets,
        },
        "pending": {
            "requirements": pending_requirements,
            "target_addresses": sorted(
                {
                    address
                    for address in (
                        item.get("address")
                        for item in pending_requirements
                        if not item["value_visible"]
                    )
                    if isinstance(address, str)
                },
                key=_cell_sort_key,
            ),
        },
        "visible_start_context": visible_context,
    }


class InstructionGenerator:
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        self.client: Any = OpenAI(api_key=api_key)
        self.model = "gpt-5.4-mini"

    def generate(self, seedTask: SeedTask, hoare_state: HoareState) -> str:
        payload = _build_instruction_payload(seedTask, hoare_state)

        response: Any = self.client.responses.create(
            model=self.model,
            input=[
                {
                    "role": "developer",
                    "content": SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": json.dumps(payload, ensure_ascii=False, indent=2),
                },
            ],
            max_output_tokens=120,
        )

        instruction = str(response.output_text).strip()
        instruction = self._normalize_instruction(instruction)

        if not instruction:
            raise RuntimeError("Instruction generator returned an empty instruction.")

        print(f"instruction generated: {instruction}")
        return instruction

    def _normalize_instruction(self, instruction: str) -> str:
        instruction = instruction.strip()

        if (
            len(instruction) >= 2
            and instruction[0] == instruction[-1]
            and instruction[0] in {'"', "'"}
        ):
            instruction = instruction[1:-1].strip()

        return instruction


SYSTEM_PROMPT = """
You write one concise user-facing spreadsheet benchmark instruction from an operation contract.

Input shape:
- source_instruction: the original whole task, used to preserve the user's intended operation.
- operation_contract.kind: the operation category inferred from the original task.
- operation_contract.value_policy: whether evaluator-only values are hidden.
- progress.completed_targets: target cells/properties that were completed before this subtask. Their hidden values are not user instructions.
- pending.requirements: the exact unfinished targets for this subtask. Requirements with value_visible=false are destinations/evaluator checks only.
- pending.target_addresses: unfinished destination cells whose final values were intentionally hidden.
- visible_start_context: values and formatting the user can already see at the start of this subtask.

Core rules:
- Treat source_instruction and operation_contract.kind as the source of truth for the user's action.
- Treat hidden pending requirements as validation targets, not literal values to type.
- Never reveal, invent, or ask the user to enter a final value for a requirement where value_visible=false.
- For computed_output, transformed_output, structural_sort, structural_visibility, and conditional_format tasks, describe the operation to perform, scoped to the pending targets.
- For literal_value and formatting requirements where value_visible=true, include the visible literal value or style if it is needed for a clear instruction.
- Use completed_targets only to avoid repeating finished work.
- Use visible_start_context only as context for the user-visible inputs and labels.
- Mention target cells or ranges when that makes the subtask clear.
- If there are multiple pending target cells in the same column, prefer compact range wording such as D5:D7.

Examples:
- For a computed_output task with pending target D5, output: Calculate the correct total rental charge in D5.
- Do not output: Enter 300 in D5.
- For a computed_output task with pending targets D5 and D6, output: Calculate the correct total rental charges in D5 and D6.
- Do not output: Enter 300 in D5 and 220 in D6.
- For a transformed_output task that normalizes phone numbers in pending targets B3:B5, output: Normalize the phone numbers in B3:B5 into the requested format.
- For a literal_entry task with visible literal requirements A2="Alice", A3="Brian", and A4="Chloe", output: Enter Alice, Brian, and Chloe in A2 through A4.
- For a direct_format task with visible formatting requirements, output the formatting action, such as: Make A1 bold.

Output rules:
- Output only the instruction text.
- Output exactly one instruction.
- Do not include markdown.
- Do not include quotes around the instruction.
- Do not explain your reasoning.
""".strip()
