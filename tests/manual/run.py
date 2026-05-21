import argparse
import time
from pathlib import Path
from typing import Any

from tests.client import Client

# ============================================================
# User-defined settings
# Modify only the values below for testing.
# ============================================================

TASK_ID = ""
ACTIONS: list[list[dict[str, Any]]] = [[]]

# ============================================================


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config-path",
        type=Path,
        help="Path to the config JSON file",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config_path = args.config_path.resolve()

    client = Client(
        task_id=TASK_ID,
        session_id=int(time.time() * 1000),
        actions=ACTIONS,
        config_path=config_path,
    )
    client.run()


if __name__ == "__main__":
    main()


# uv run python -m tests.task_evaluation.run \
#   --gateway_url http://127.0.0.1:18000 \
#   --task-path packages/surfgym-task/src/surfgym_task/data/seed/spreadsheet/out/augmented.jsonc
