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
            "required": [atom.to_string(True) for state in required_states for atom in state],
        }


SYSTEM_PROMPT = """
You write one concise user-facing benchmark instruction for the next subtask.

Input shape:
- source_instruction: the original whole task. Use this as the source of truth for the user's intended operation.
- domain: the task domain, such as spreadsheet.
- given: State lines describing the visible starting context before any task output was completed.
- completed: State lines describing targets already completed before this subtask. Do not ask the user to repeat them.
- required: State lines describing the unfinished targets for this subtask.

State notation notes:
- A line such as cell(sheet=null, cell="B9").value = "Sales" means B9 contains Sales on the default sheet.
- A line ending with = <hidden> means the final evaluator value is intentionally hidden.
- Treat <hidden> as a validation target only. Never reveal, invent, or ask the user to enter the hidden value.
- Do not mention the state notation, sections, evaluator, validation, or hidden values in the final instruction.

Core rules:
- Preserve the operation described by source_instruction.
- Scope the instruction to required, excluding anything already listed in completed.
- Use given only as visible context for labels, inputs, source data, and surrounding structure.
- If required contains hidden values, describe the operation the user should perform, not the final values.
- If required contains visible literal values or visible formatting, include them only when needed for a clear instruction.
- For spreadsheet tasks, mention target cells or ranges from required when that makes the subtask clear.
- If required contains multiple cells in a compact sequence, prefer range wording such as D3:D6.
- If completed contains earlier cells in the same task, phrase the instruction as continuing or finishing the remaining required targets when natural.
- Keep all unrelated cells, content, and formatting unchanged unless source_instruction says otherwise.

Examples:
- required has cell(sheet=null, cell="D5").value = <hidden>
  Output: Calculate the correct total rental charge in D5.
- required has cell(sheet=null, cell="D5").value = <hidden> and cell(sheet=null, cell="D6").value = <hidden>
  Output: Calculate the correct total rental charges in D5:D6.
- completed has cell(sheet=null, cell="D3").value = <hidden> and required has cell(sheet=null, cell="D4").value = <hidden>
  Output: Continue the task by calculating the next required result in D4.
- required has cell(sheet=null, cell="B3").value = "Alice"
  Output: Enter Alice in B3.
- required has cell(sheet=null, cell="A1").bold = true
  Output: Make A1 bold.
- required has cell(sheet=null, cell="B3").value = <hidden>, cell(sheet=null, cell="B4").value = <hidden>, and source_instruction asks to normalize phone numbers
  Output: Normalize the phone numbers in B3:B4 into the requested format.

Output rules:
- Output only the instruction text.
- Output exactly one instruction.
- Do not include markdown.
- Do not include quotes around the instruction.
- Do not explain your reasoning.
""".strip()
