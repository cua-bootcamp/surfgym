import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

from surfgym_task.generation.schema import HoareState, SeedTask, State

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def _dump_state(state: State) -> list[dict[str, Any]]:
    return [atom.model_dump(mode="json") for atom in state]


def _normalized_atom_value(atom: dict[str, Any]) -> Any:
    if atom.get("f") == "getCellMeta" and atom.get("property") == ["style", "bl"]:
        return _is_truthy_style_value(atom.get("value"))

    return atom.get("value")


def _atom_key(atom: dict[str, Any]) -> str:
    return json.dumps(
        {
            "f": atom.get("f"),
            "param": atom.get("param"),
            "property": atom.get("property", []),
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


def _format_value(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _is_truthy_style_value(value: Any) -> bool:
    return value in (1, True, "1", "true", "True")


def _describe_spreadsheet_atom(atom: dict[str, Any]) -> str | None:
    address = atom.get("param")
    prop = atom.get("property", [])
    value = atom.get("value")

    if prop == ["cell", "v"]:
        return f"Cell {address} should contain {_format_value(value)}."

    if prop == ["style", "bl"]:
        return (
            f"Cell {address} should be bold."
            if _is_truthy_style_value(value)
            else f"Cell {address} should not be bold."
        )

    if prop == ["style", "bg", "rgb"]:
        return f"Cell {address} should have background color {_format_value(value)}."

    if prop == ["style", "n", "pattern"]:
        return f"Cell {address} should use number format {_format_value(value)}."

    return None


def _describe_atom(atom: dict[str, Any]) -> str:
    if atom.get("f") == "getCellMeta":
        spreadsheet_description = _describe_spreadsheet_atom(atom)
        if spreadsheet_description is not None:
            return spreadsheet_description

    return (
        f"Requirement: {atom.get('f')} at {atom.get('param')} has "
        f"{'.'.join(atom.get('property', []))} = {_format_value(atom.get('value'))}."
    )


def _describe_state(state: list[dict[str, Any]]) -> list[str]:
    return [_describe_atom(atom) for atom in state]


class InstructionGenerator:
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        self.client = OpenAI(api_key=api_key)
        self.model = "gpt-5.4-mini"

    def generate(self, seedTask: SeedTask, hoare_state: HoareState) -> str:
        start_state = (
            None if hoare_state.start_state is None else _dump_state(hoare_state.start_state)
        )
        end_state = _dump_state(hoare_state.end_state)
        required_state = _diff_state(hoare_state.start_state, hoare_state.end_state)

        payload = {
            "seed_instruction": seedTask.instruction,
            "seed_states": [_dump_state(state) for state in seedTask.states],
            "start_state": start_state,
            "end_state": end_state,
            "required_state": required_state,
            "required_facts": _describe_state(required_state),
        }

        response = self.client.responses.create(
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

        instruction = response.output_text.strip()
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
You will generate concise GUI benchmark subtask instructions.

You will receive JSON with:
- seed_instruction: the original full task instruction
- seed_states: ordered internal milestone states from the original task
- start_state: the actual state the user starts from, or null
- end_state: the target state the generated instruction should lead to
- required_state: the exact internal requirements that are present in end_state but not already present in start_state
- required_facts: natural-language descriptions of required_state

Your job is to generate one short user-facing instruction that moves the user from start_state to end_state while staying consistent with seed_instruction.

Critical semantics:
- Only start_state describes what already exists for the user.
- seed_states are reference milestones used only to understand ordering and intent. They are not setup state, and they are not preconditions.
- required_state and required_facts are the authoritative list of work the user must perform.
- Mention only the required change. Do not ask the user to create, edit, format, or verify anything that is already present in start_state but absent from required_state.
- If start_state is null, assume none of the task-specific requirements have been completed yet.
- When start_state is null, required_state will usually match end_state and every user-visible requirement in required_state must be included in the instruction.
- If start_state is not null, repeated facts in both start_state and end_state are context only, not work to perform.
- If required_state is not empty, never output "No changes are needed."
- Output "No changes are needed." only when required_state is empty.
- Never say or imply that something is "existing", "already", or pre-filled unless it is explicitly present in start_state.
- Generate the transition from required_state, not as the difference between adjacent seed_states.

Spreadsheet state interpretation:
- property ["cell", "v"] means the cell's displayed value.
- property ["style", "bl"] with value 1 means the cell is bold.
- property ["style", "bl"] with value 0 or false means the cell is not bold.
- For spreadsheet tasks, convert cell facts into natural instructions. You may mention cell addresses when that is the clearest instruction.
- Include a cell's value or style only if that exact value or style appears in required_state or required_facts.
- If a cell value or style appears only in start_state, do not mention it as an action.

Operation intent preservation:
- Use required_state to decide which final requirements must be satisfied, but use seed_instruction to preserve the user's intended operation.
- If seed_instruction describes a rule-based or derived operation, keep that operation wording instead of rewriting it as direct cell assignments.
- Rule-based or derived operations include: fill blank cells, replace missing values, normalize values, split text into columns, calculate formulas, apply conditional formatting, highlight matching rows, format numbers or dates, sort or filter, remove duplicates, and compute derived values.
- When required_state contains final cell values that are the result of such an operation, describe the operation, not just the resulting cells.
- Keep the range, column, condition, target value, and transformation from seed_instruction when they are available and still relevant to required_state.
- If start_state shows blank cells and required_state changes those cells to a shared value, prefer wording like: Fill every blank cell in [range or column] with "[value]".
- If start_state does not yet show the blank cells, but seed_instruction says to create blanks before filling them, first ask for the remaining table data with those cells left blank, then ask to fill the blank cells using the original rule.
- Do not say "Enter [value] in A3 and A5" when seed_instruction says to fill blank cells with that value.
- Direct cell-entry wording is appropriate only when seed_instruction itself describes direct entry, or when no rule-based or derived operation is implied.

Examples:
- If required_facts are Cell A2 should contain "Alice", Cell A3 should contain "Brian", Cell A4 should contain "Chloe", output: Enter Alice, Brian, and Chloe in A2 through A4.
- If required_facts are Cell B1 should contain "Score", Cell B1 should be bold, Cell B2 should contain 85, Cell B3 should contain 92, Cell B4 should contain 78, output: Enter Score in B1, enter 85, 92, and 78 in B2 through B4, and make B1 bold.
- If required_facts include both the names in A2 through A4 and the scores in B1 through B4, include both groups in the instruction.
- If seed_instruction says to fill every blank cell in column A within A2:A6 with "Unknown", start_state has A3 and A5 blank, and required_facts are Cell A3 should contain "Unknown" and Cell A5 should contain "Unknown", output: Fill every blank cell in column A within A2:A6 with "Unknown".
- If seed_instruction says to create an employee table with blanks in A3 and A5 and then fill every blank cell in column A within A2:A6 with "Unknown", and required_facts include both remaining table rows and Unknown in A3 and A5, output: Complete the remaining employee table rows with the specified blank Name cells, then fill every blank cell in column A within A2:A6 with "Unknown".
- Do not output: Enter Unknown in A3 and A5.
- Do not output instructions for cells or formatting that are absent from required_facts.

Guidelines:
- Focus only on what the user must do to satisfy end_state from start_state.
- If start_state already includes part of the seed task, do not repeat that completed part.
- If end_state appears to be the final goal of the seed task, the instruction may closely match seed_instruction.
- Prefer direct imperative wording such as "Open...", "Navigate to...", "Enter...", "Select...", or "Change...".
- Write the instruction as if you are giving it to a user who will perform the task on their computer.
- Keep it concise, specific, and actionable.

Output rules:
- Output only the instruction text.
- Output exactly one instruction.
- Do not include markdown.
- Do not include quotes around the instruction.
- Do not explain your reasoning.
""".strip()
