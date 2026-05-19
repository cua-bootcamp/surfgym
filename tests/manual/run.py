import argparse
import time
from pathlib import Path
from typing import Any

from .runner import Runner

# ============================================================
# User-defined settings
# Modify only the values below for testing.
# ============================================================

TASK_ID = "spreadsheet_2"
ACTIONS: list[list[dict[str, Any]]] = [
    [
        {"action_type": "WAIT"},
        {"action_type": "WAIT"},
        {"action_type": "CLICK", "x": "1100", "y": "50"},
    ],
    [
        {"action_type": "PRESS", "key": "ArrowRight"},
        {"action_type": "PRESS", "key": "ArrowDown"},
        {"action_type": "PRESS", "key": "ArrowDown"},
        {"action_type": "PRESS", "key": "ArrowDown"},
        {"action_type": "PRESS", "key": "ArrowDown"},
        {"action_type": "TYPING", "text": "5"},
        {"action_type": "PRESS", "key": "Enter"},
    ],
]

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

    runner = Runner(
        task_id=TASK_ID,
        session_id=int(time.time() * 1000),
        actions=ACTIONS,
        config_path=config_path,
    )
    runner.run()


if __name__ == "__main__":
    main()
