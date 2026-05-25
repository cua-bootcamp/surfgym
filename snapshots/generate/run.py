import argparse
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any

from surfgym_contracts import ConsoleAction
from surfgym_runtime.support import TaskStore

from .client import Client, ClientResult
from .schema import Manifest, Summary, TaskMeta


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--gateway-url", "--gateway_url", dest="gateway_url", type=str, required=True
    )
    parser.add_argument("--task-path", type=Path, required=True)
    parser.add_argument("--max-parallel", type=int, default=1)
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.max_parallel < 1:
        raise ValueError("--max-parallel must be >= 1")

    run_started_at = time.perf_counter()
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")[:-3]

    snapshots_dir = Path(__file__).resolve().parent.parent
    snapshot_root = snapshots_dir / "__snapshots__" / timestamp
    snapshot_root.mkdir(parents=True, exist_ok=True)

    tasks = TaskStore.from_file(args.task_path).all_tasks()
    base_session_id = time.time_ns() // 1_000_000

    def run_one(index: int, task: Any):
        if task.transition is None:
            raise ValueError(f"transition missing in {task.task_id}")

        task_root = snapshot_root / task.task_id

        return Client(
            task_id=task.task_id,
            session_id=base_session_id + index,
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

    results_by_task_id: dict[str, ClientResult] = {}

    with ThreadPoolExecutor(max_workers=args.max_parallel) as executor:
        future_by_task_id = {
            executor.submit(run_one, index, task): task.task_id for index, task in enumerate(tasks)
        }

        for future in as_completed(future_by_task_id):
            task_id = future_by_task_id[future]
            try:
                result: ClientResult = future.result()
            except Exception as exc:
                raise RuntimeError(f"Snapshot generation failed for task_id={task_id}") from exc

            results_by_task_id[result.task_id] = result

    manifest_tasks: dict[str, TaskMeta] = {}
    reward_sum = 0.0

    for task in tasks:
        result: ClientResult = results_by_task_id[task.task_id]
        manifest_tasks[result.task_id] = TaskMeta(
            snapshot_dir=Path(task.task_id),
            reward=result.reward,
        )
        reward_sum += result.reward

    elapsed_seconds = time.perf_counter() - run_started_at
    manifest = Manifest(
        summary=Summary(
            total=len(manifest_tasks),
            reward_sum=reward_sum,
            task_source=str(args.task_path),
            elapsed_seconds=elapsed_seconds,
        ),
        tasks=manifest_tasks,
    )

    (snapshot_root / "manifest.json").write_text(
        manifest.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
