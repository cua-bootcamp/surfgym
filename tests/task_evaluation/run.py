import argparse
import time
from datetime import datetime
from pathlib import Path

from surfgym_contracts import ConsoleAction
from surfgym_runtime.support import TaskStore

from tests.client import Client
from tests.schema import Manifest, Summary, TaskMeta


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--gateway-url", "--gateway_url", dest="gateway_url", type=str, required=True
    )
    parser.add_argument("--task-path", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")[:-3]

    tests_dir = Path(__file__).resolve().parent
    snapshot_root = tests_dir / "__snapshots__" / f"task_evaluation_{timestamp}"
    snapshot_root.mkdir(parents=True, exist_ok=True)

    manifest_tasks: dict[str, TaskMeta] = {}
    reward_sum = 0.0

    for task in TaskStore.from_file(args.task_path).all_tasks():
        if task.transition is None:
            raise ValueError(f"transition missing in {task.task_id}")

        task_root = snapshot_root / task.task_id

        result = Client(
            task_id=task.task_id,
            session_id=int(time.time() * 1000),
            gateway_url=args.gateway_url,
            actions=[
                [
                    ConsoleAction(
                        action_type="CONSOLE",
                        actions=task.transition,
                    ).model_dump(mode="json")
                ]
            ],
            snapshot_dir=task_root,
        ).run()

        manifest_tasks[result.task_id] = TaskMeta(
            snapshot_dir=Path(task.task_id), reward=result.reward
        )
        reward_sum += result.reward

    manifest = Manifest(
        summary=Summary(
            total=len(manifest_tasks),
            reward_sum=int(reward_sum),
            task_source=str(args.task_path),
        ),
        tasks=manifest_tasks,
    )

    (snapshot_root / "manifest.json").write_text(
        manifest.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
