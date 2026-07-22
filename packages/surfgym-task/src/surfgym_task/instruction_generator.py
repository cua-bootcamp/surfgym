import json
import os
from pathlib import Path
from typing import Any, TypedDict

from dotenv import load_dotenv
from openai import OpenAI

from surfgym_task.hoare import HoareState
from surfgym_task.seed import SeedTask

MODULE_DIR = Path(__file__).resolve().parent
REPO_ROOT = MODULE_DIR.parents[3]

load_dotenv(Path(__file__).resolve().parents[4] / ".env")
load_dotenv(Path(__file__).resolve().parent / ".env")


class InstructionPayload(TypedDict):
    source_instruction: str
    domain: str
    given: list[str]
    completed: list[str]
    required: list[str]


class InstructionGenerator:
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        self.client: Any = OpenAI(api_key=api_key)
        self.model = "gpt-5.4-mini"

    def generate(self, seed_task: SeedTask, hoare_state: HoareState) -> str:
        payload = self._build_instruction_payload(seed_task, hoare_state)

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

        if not instruction:
            raise RuntimeError("Instruction generator returned an empty instruction.")

        print(f"instruction generated: {instruction}")
        return instruction

    def _build_instruction_payload(
        self, seed_task: SeedTask, hoare_state: HoareState
    ) -> InstructionPayload:
        given_state = seed_task.states[0]
        completed_states = seed_task.states[1 : hoare_state.origin_start_idx + 1]
        required_states = seed_task.states[
            hoare_state.origin_start_idx + 1 : hoare_state.origin_end_idx + 1
        ]

        return {
            "source_instruction": seed_task.instruction,
            "domain": seed_task.domain,
            "given": [atom.to_string() for atom in given_state],
            "completed": [atom.to_string() for state in completed_states for atom in state],
            "required": [
                atom.to_string(hide_value=True) for state in required_states for atom in state
            ],
        }


SYSTEM_PROMPT = """
You write one concise, self-contained, user-facing benchmark instruction
for exactly the next subtask.

Input roles:
- source_instruction describes the high-level intent and operation of the whole task.
  It is not authoritative for concrete targets when it conflicts with state data.
- given describes the visible starting context and source data.
- completed describes changes that are already present before this subtask.
- required is the authoritative list of concrete targets and properties that must
  be changed in this subtask.

Conflict policy:
- Use source_instruction to understand why and how the task should be performed.
- Use required to determine exactly what must be changed and where.
- Concrete facts in required, completed, and given override conflicting details
  from source_instruction, including object names, labels, sheet names, cells,
  ranges, and subtask boundaries.
- Never copy a concrete detail from source_instruction when state data contradicts it.
- If a detail is not supported by any input, omit it instead of inventing it.
- Ground terminology in visible labels from required, completed, or given whenever possible.

State notation:
- Each state line has the form: <JSON target specification> = <value>.
- The JSON object identifies the target object, location, and property.
- A value of <hidden> means the expected value is intentionally unavailable.
- Never reveal, guess, or ask the user to enter a hidden value directly.
- For hidden values, describe the calculation, transformation, or action needed
  to produce them.
- Do not mention states, evaluators, validation, or hidden values in the output.

Subtask rules:
- Ask for all and only the changes represented by required.
- Do not ask for later rows, additional values, formatting, or other work that
  is not represented by required.
- Never repeat targets already represented by completed.
- Treat given and completed together as the known current state.
- If required introduces an object that does not occur in the known current state,
  describe creating or adding it rather than renaming or updating it.
- If required changes a property of an existing object, describe modifying that property.
- Make the instruction independently actionable. Do not use vague wording such as
  "continue" or "finish the task" without also naming the exact action and target.
- Consolidate contiguous targets into a range only when they share the same sheet,
  property, and operation.
- Preserve unrelated content and formatting.

Before answering, silently verify:
1. Every requested target is supported by required.
2. No work outside required is requested.
3. Every concrete label, object, sheet, cell, and range is supported by the input.
4. The action verb correctly reflects whether the target is created or modified.
5. No hidden value is exposed or invented.

Measured-gap examples:
- If source_instruction mentions F2 but required targets D5, use D5.
  Output: Calculate the requested result in D5.
- If required contains only header cells A1:D1, ask only for those headers.
  Do not ask the user to fill the table body.
- If required introduces
  {"kind":"sheet","property":"name","sheet":"Sheet2"} = <hidden>
  and Sheet2 is absent from given and completed:
  Output: Create a new worksheet named Sheet2.

Output rules:
- Output only one concise instruction.
- Do not include markdown, quotation marks, or reasoning.
""".strip()
