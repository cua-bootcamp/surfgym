import argparse
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any

from surfgym_contracts import ConsoleAction
from surfgym_runtime.support import TaskStore

from .client import Client, ClientResult
from .schema import Manifest, Summary, TaskFailure, TaskMeta


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--gateway-url", "--gateway_url", dest="gateway_url", type=str, required=True
    )
    parser.add_argument("--task-path", type=Path, required=True)
    parser.add_argument("--max-parallel", type=int, default=1)
    return parser.parse_args()


def record_task_failure(snapshot_root: Path, task_id: str, exc: BaseException) -> TaskFailure:
    task_root = snapshot_root / task_id
    task_root.mkdir(parents=True, exist_ok=True)

    detail = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    (task_root / "failure.txt").write_text(detail, encoding="utf-8")

    return TaskFailure(
        snapshot_dir=Path(task_id),
        error_type=type(exc).__name__,
        error_message=str(exc),
        traceback=detail,
    )


def build_manifest(
    *,
    tasks: list[Any],
    task_path: Path,
    elapsed_seconds: float,
    results_by_task_id: dict[str, ClientResult],
    failures_by_task_id: dict[str, TaskFailure],
) -> Manifest:
    manifest_tasks: dict[str, TaskMeta] = {}
    reward_sum = 0.0

    for task in tasks:
        result = results_by_task_id.get(task.task_id)
        if result is None:
            continue

        manifest_tasks[result.task_id] = TaskMeta(
            snapshot_dir=Path(task.task_id),
            reward=result.reward,
        )
        reward_sum += result.reward

    return Manifest(
        summary=Summary(
            total=len(tasks),
            succeeded=len(manifest_tasks),
            failed=len(failures_by_task_id),
            reward_sum=reward_sum,
            task_source=str(task_path),
            elapsed_seconds=elapsed_seconds,
        ),
        tasks=manifest_tasks,
        failures=failures_by_task_id,
    )


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
                        hooks=task.transition,
                    ).model_dump(mode="json")
                ]
            ],
            snapshot_dir=task_root,
        ).run()

    results_by_task_id: dict[str, ClientResult] = {}
    failures_by_task_id: dict[str, TaskFailure] = {}

    with ThreadPoolExecutor(max_workers=args.max_parallel) as executor:
        future_by_task_id = {
            executor.submit(run_one, index, task): task.task_id for index, task in enumerate(tasks)
        }

        for future in as_completed(future_by_task_id):
            task_id = future_by_task_id[future]
            try:
                result: ClientResult = future.result()
            except Exception as exc:
                failures_by_task_id[task_id] = record_task_failure(snapshot_root, task_id, exc)
                continue

            results_by_task_id[result.task_id] = result

    elapsed_seconds = time.perf_counter() - run_started_at
    manifest = build_manifest(
        tasks=tasks,
        task_path=args.task_path,
        elapsed_seconds=elapsed_seconds,
        results_by_task_id=results_by_task_id,
        failures_by_task_id=failures_by_task_id,
    )

    manifest_path = snapshot_root / "manifest.json"
    manifest_path.write_text(
        manifest.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )

    if failures_by_task_id:
        raise RuntimeError(
            f"Snapshot generation failed for {len(failures_by_task_id)} "
            f"of {len(tasks)} tasks; manifest written to {manifest_path}"
        )


if __name__ == "__main__":
    main()
