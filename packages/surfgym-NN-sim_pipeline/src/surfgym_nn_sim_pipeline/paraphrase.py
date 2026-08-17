"""One-off script: generate the naive-paraphrase upper baseline (파이프라인 설계.md §4.3).

Not part of the runtime path. Run once, review a sample by hand, then commit
the output. Re-running overwrites the frozen file -- don't do that casually,
since the upper baseline must stay fixed across runs for results to be
comparable over time.

    python -m surfgym_nn_sim_pipeline.paraphrase

Follows the same OpenAI client pattern as
packages/surfgym-task/src/surfgym_task/instruction_generator.py rather than
inventing a second LLM-call path.
"""

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

from surfgym_nn_sim_pipeline.corpus import load_osworld_instructions

KST = timezone(timedelta(hours=9))
MODULE_DIR = Path(__file__).resolve().parent
OUTPUT_PATH = MODULE_DIR / "data" / "osworld_1_0_paraphrases.json"
VENDORED_OSWORLD_PATH = MODULE_DIR / "data" / "osworld_1_0.json"

load_dotenv(Path(__file__).resolve().parents[5] / ".env")
load_dotenv(Path(__file__).resolve().parent / ".env")

PROMPT_VERSION = "v1"
GENERATION_MODEL = "gpt-5.4-mini"

SYSTEM_PROMPT = """
You rewrite one short benchmark task instruction into 3 naive paraphrases.

A naive paraphrase changes only wording and sentence order. It must NOT change:
- the application or website the instruction refers to
- any file name, number, date, or specific value mentioned
- the underlying goal or action the user must perform

Do not add information, remove information, or make the instruction more or
less specific than the original.

Output rules:
- Output exactly 3 lines, one paraphrase per line.
- No numbering, no bullets, no quotes, no markdown.
- Do not repeat the original instruction verbatim on any line.
""".strip()


class ParaphraseGenerator:
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        self.client: Any = OpenAI(api_key=api_key)
        self.model = GENERATION_MODEL

    def generate(self, instruction: str) -> list[str]:
        response: Any = self.client.responses.create(
            model=self.model,
            input=[
                {"role": "developer", "content": SYSTEM_PROMPT},
                {"role": "user", "content": instruction},
            ],
            max_output_tokens=300,
        )

        lines = [
            line.strip() for line in str(response.output_text).strip().splitlines() if line.strip()
        ]

        if len(lines) != 3:
            raise RuntimeError(
                f"expected 3 paraphrase lines, got {len(lines)} for instruction: {instruction!r}"
            )

        return lines


def main() -> None:
    osworld_tasks = load_osworld_instructions()
    generator = ParaphraseGenerator()

    source_commit = json.loads(VENDORED_OSWORLD_PATH.read_text(encoding="utf-8"))["osworld_commit"]

    paraphrases = []
    for task in osworld_tasks:
        variants = generator.generate(task.text)
        paraphrases.append(
            {
                "osworld_id": task.id,
                "domain": task.domain,
                "source_instruction": task.text,
                "paraphrase": variants[0],  # the one fed into stats/percentiles
                "robustness_variants": variants[1:],  # sanity-check only, not used in stats
            }
        )
        print(f"[{task.domain}] {task.id}: {variants[0]}")

    output = {
        "generation_model": GENERATION_MODEL,
        "prompt_version": PROMPT_VERSION,
        "generated_at": datetime.now(KST).isoformat(),
        "source_osworld_commit": source_commit,
        "paraphrases": paraphrases,
    }

    OUTPUT_PATH.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"\nwrote {len(paraphrases)} paraphrases -> {OUTPUT_PATH}")
    print("Next: review a sample by hand (파이프라인 설계.md §4.3) before relying on this file.")


if __name__ == "__main__":
    main()
