import json
import os
from pathlib import Path
from typing import Any, TypedDict

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import JsonValue
from surfgym_contracts.task import Value

from surfgym_task.hoare import HoareState
from surfgym_task.seed import SeedTask

MODULE_DIR = Path(__file__).resolve().parent
REPO_ROOT = MODULE_DIR.parents[3]

load_dotenv(Path(__file__).resolve().parents[4] / ".env")
load_dotenv(Path(__file__).resolve().parent / ".env")


class CurrentStatePayload(TypedDict):
    target: dict[str, JsonValue]
    current_value: Value


class RequiredStatePayload(TypedDict):
    target: dict[str, JsonValue]
    expected_value: Value


class InstructionPayload(TypedDict):
    source_instruction: str
    domain: str
    current: list[CurrentStatePayload]
    required: list[RequiredStatePayload]


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

            #         print(
            #             f"""### {instruction}

            # ```json
            # {payload}
            # ```

            # <br>

            # """
            #         )
        return instruction

    def _build_instruction_payload(
        self,
        seed_task: SeedTask,
        hoare_state: HoareState,
    ) -> InstructionPayload:
        current: list[CurrentStatePayload] = [
            {
                "target": atom.spec,
                "current_value": atom.value,
            }
            for atom in hoare_state.start_state
        ]
        required: list[RequiredStatePayload] = [
            {
                "target": atom.spec,
                "expected_value": atom.value,
            }
            for atom in hoare_state.diff
        ]

        return {
            "source_instruction": seed_task.instruction,
            "domain": seed_task.domain,
            "current": current,
            "required": required,
        }


SYSTEM_PROMPT = """
You convert a whole-task description and a state transition into one concise, self-contained, user-facing subtask instruction.

Follow these two stages in order.

Stage 1 — Determine scope:

- Build the complete allowed change set from required targets only.
  expected_value does not expand this set.
- Ask for every required target and no other target. source_instruction and
  current must never add targets, contents, ranges, or future work.
- Use required target metadata for exact identities, locations, properties, and
  extent. Mentioning, populating, formatting, or modifying an object counts as
  requesting a change to it.
- A subtask may intentionally stop at an incomplete intermediate state. Do not
  complete more of the whole task to make the instruction more useful.

Stage 2 — Determine content for each allowed target:

- expected_value may be stated only when source_instruction explicitly supplies
  that same content or unambiguously supplies it as part of a literal list,
  sequence, range, or setting that maps to the target.
- Presence in required or current alone never authorizes expected_value to be
  stated as the content the user should produce or apply.
- If source_instruction describes an operation that produces expected_value,
  state the operation and its supported inputs without stating expected_value.
  Use an explicit verb such as calculate, derive, compare, look up, convert,
  generate, or transform.
- Do not replace a producing operation with instructions to enter, fill,
  populate, set, or use its result. Do not call the result given, provided,
  listed, specified, required, expected, corresponding, or shown.
- If neither supplied content nor a producing operation maps unambiguously to a
  required target, omit the unsupported detail instead of guessing.

Use source_instruction only to determine applicable supplied content, purpose,
operations, and relationships inside the Stage 1 boundary. Use current for
exact facts, existing names, and operation inputs; current is read-only unless
the same target is also in required. Do not combine conflicting alternatives or
replace exact supported names with guesses.

Object transitions:

- If required contains only a new object, ask only to create it.
- If required contains a new object and its contents, explicitly create it and
  add only the required contents.
- If a required object identity is absent from current, request creation
  unconditionally. Do not use “ensure,” “rename,” “create or rename,” or
  conditions such as “if needed.”
- Request a rename only when required changes the identity of an object already
  present in current.
- Group targets only when they share the same operation and property. Preserve
  unrelated content and settings.

Before answering, verify:

1. Every required target is covered, and every requested change is in required.
2. Every stated expected_value passes the source_instruction disclosure rule.
3. Every unstated produced result has an explicit operation and supported
   inputs.
4. No future work is requested, and every new required object is explicitly
   created.

Output only one concise instruction. Do not include markdown, labels, quotation marks, input-field names, or reasoning.
""".strip()
