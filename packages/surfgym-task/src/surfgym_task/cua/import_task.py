"""Import one CUA-Gym direct-web bundle into a runnable SurfGym task."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from surfgym_contracts.task import CuaEvaluation, CuaStateSource, Task, Website

from surfgym_task.cua.app_registry import key_from_app_dir
from surfgym_task.cua.bundle_store import Bundle, read_bundles
from surfgym_task.cua.record_setup import RecordedSetup, record, write_states
from surfgym_task.cua.state_contracts import get_state_contract
from surfgym_task.io import JsonIO, TaskWriter


@dataclass(frozen=True)
class ImportedTask:
    task: Task
    setup: RecordedSetup
    app_key: str


def import_direct_web_task(bundle: Bundle, *, app_url: str) -> ImportedTask:
    if not bundle.complete:
        raise ValueError(f"CUA bundle {bundle.task_id} is incomplete")

    metadata = json.loads(bundle.task_json)
    app_type = metadata.get("app_type")
    instruction = metadata.get("instruction")
    if not isinstance(app_type, str) or not isinstance(instruction, str):
        raise ValueError(f"CUA bundle {bundle.task_id} has invalid task.json")

    app_key = key_from_app_dir(app_type)
    contract = get_state_contract(app_key)
    if not contract.in_direct_web_dataset or contract.requires_server_memory:
        raise ValueError(f"{app_key} is not a direct localStorage web app")

    setup = record(bundle)
    if not setup.ok:
        raise RuntimeError(f"failed to record {bundle.task_id}: {setup.error}")
    if set(setup.states) != {app_key}:
        raise ValueError(
            f"recorded app keys {sorted(setup.states)} do not match task app {app_key}"
        )

    sid = bundle.task_id
    app_base = app_url.rstrip("/")
    task = Task(
        task_id=bundle.task_id,
        instruction=instruction,
        website=[Website(url=_with_sid(app_url, sid))],
        evaluation=CuaEvaluation(
            source_task_id=bundle.task_id,
            reward_script=(bundle.reward or "").replace(setup.bases[app_key], app_base),
            states=[
                CuaStateSource(
                    app_base=app_base,
                    sid=sid,
                    current_state_key=contract.current_state_key(sid),
                    initial_state_key=contract.initial_state_key(sid),
                )
            ],
        ),
    )
    return ImportedTask(task=task, setup=setup, app_key=app_key)


def write_task_assets(imported: ImportedTask, tasks_dir: Path) -> Path:
    """Write one task's initial states and task.json under `tasks_dir/<task_id>/`.

    Does not write the shared task store -- a batch import opens one
    `TaskWriter` across every task in the run, same as the seed pipeline in
    `main.py`. Writing a `tasks.sqlite3` per task here would make it
    impossible to import more than one task into a single servable store,
    since `TaskWriter.__enter__` truncates the table on every open.
    """
    task_dir = tasks_dir / imported.task.task_id
    write_states(imported.setup, task_dir / "initial_states")
    JsonIO.write(task_dir / "task.json", imported.task)
    return task_dir


def _with_sid(url: str, sid: str) -> str:
    parsed = urlsplit(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["sid"] = sid
    return urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path or "/", urlencode(query), parsed.fragment)
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--task-id", required=True, nargs="+", help="one or more bundle task ids")
    parser.add_argument(
        "--ports-file",
        type=Path,
        required=True,
        help="APP_KEY -> base URL, e.g. output/cua-webapps/ports.json from gen_caddyfile.py",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ports: dict[str, str] = json.loads(args.ports_file.read_text(encoding="utf-8"))

    bundles = read_bundles(args.archive, args.task_id)
    missing = [task_id for task_id in args.task_id if task_id not in bundles]
    if missing:
        raise SystemExit(f"tasks not found in {args.archive}: {', '.join(missing)}")

    imported_tasks: list[ImportedTask] = []
    for task_id in args.task_id:
        bundle = bundles[task_id]
        app_key = key_from_app_dir(json.loads(bundle.task_json).get("app_type", ""))
        app_url = ports.get(app_key)
        if app_url is None:
            raise SystemExit(f"no URL for app {app_key} (task {task_id}) in {args.ports_file}")

        imported = import_direct_web_task(bundle, app_url=app_url)
        task_dir = write_task_assets(imported, args.output_dir)
        imported_tasks.append(imported)
        print(f"imported {imported.task.task_id} ({imported.app_key}) -> {task_dir}")

    tasks_db = args.output_dir / "tasks.sqlite3"
    with TaskWriter(tasks_db) as writer:
        for imported in imported_tasks:
            writer.write(imported.task)
    print(f"wrote {len(imported_tasks)} task(s) -> {tasks_db}")


if __name__ == "__main__":
    main()
