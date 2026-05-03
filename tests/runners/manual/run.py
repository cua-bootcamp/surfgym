import argparse
import time
from pathlib import Path
from typing import Any

from .runner import Runner

# ============================================================
# User-defined settings
# Modify only the values below for testing.
# ============================================================

# TASK_ID = "all_commands"
# ACTIONS: list[list[dict[str, Any]]] = [
#     [{"action_type": "MOVE_TO", "x": 855, "y": 100}],
#     [{"action_type": "CLICK", "x": 170, "y": 100}],
#     [{"action_type": "DOUBLE_CLICK", "x": 380, "y": 100}],
#     [{"action_type": "RIGHT_CLICK", "x": 590, "y": 100}],
#     [{"action_type": "MOVE_TO", "x": 185, "y": 238}],
#     [{"action_type": "MOUSE_DOWN"}],
#     [{"action_type": "MOUSE_UP"}],
#     [{"action_type": "MOVE_TO", "x": 638, "y": 230}],
#     [{"action_type": "DRAG_TO", "x": 1015, "y": 230}],
#     [{"action_type": "MOVE_TO", "x": 425, "y": 238}],
#     [{"action_type": "CLICK"}],
#     [{"action_type": "WAIT"}],
#     [{"action_type": "CLICK", "x": 290, "y": 380}],
#     [{"action_type": "TYPING", "text": "Hello"}],
#     [{"action_type": "PRESS", "key": "Enter"}],
#     [{"action_type": "KEY_DOWN", "key": "Shift"}],
#     [{"action_type": "KEY_UP", "key": "Shift"}],
#     [{"action_type": "HOTKEY", "keys": ["ControlOrMeta", "a"]}],
#     [{"action_type": "MOVE_TO", "x": 720, "y": 460}],
#     [{"action_type": "SCROLL", "dx": 0, "dy": 900}],
# ]

TASK_ID = "counter"
ACTIONS: list[list[dict[str, Any]]] = [
    [
        {
            "action_type": "CLICK",
            "x": 696,
            "y": 475,
        },
    ],
    [
        {"action_type": "CLICK", "num_clicks": 4},
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
