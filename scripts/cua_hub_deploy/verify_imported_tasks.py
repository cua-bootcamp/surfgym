"""Verify imported single-app CUA tasks at their untouched initial state."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from pydantic import TypeAdapter
from surfgym_contracts.task import CuaEvaluation, Task
from surfgym_runtime.support.cua_evaluator import CuaSnapshot, evaluate_cua_reward
from surfgym_task.cua.state_contracts import get_state_contract
from surfgym_task.web import WEB_STATE_RESET_HOOK


def verify_task_dir(
    task_dir: Path,
    *,
    timeout: float,
    expected_sources: Mapping[str, str] | None = None,
) -> dict[str, object]:
    task = TypeAdapter(Task).validate_json(
        (task_dir / "task.json").read_text(encoding="utf-8")
    )
    if task.task_id != task_dir.name:
        raise ValueError(
            f"{task_dir.name} directory does not match runtime task id {task.task_id}"
        )
    if not isinstance(task.evaluation, CuaEvaluation):
        raise ValueError(f"{task.task_id} is not a CUA task")
    if len(task.evaluation.states) != 1:
        raise ValueError(f"{task.task_id} is not a single-app CUA task")

    source = task.evaluation.states[0]
    expected_source_task_id = (
        task.task_id if expected_sources is None else expected_sources.get(task.task_id)
    )
    if expected_source_task_id is None:
        raise ValueError(f"{task.task_id} has no expected source lineage mapping")
    if task.evaluation.source_task_id != expected_source_task_id:
        raise ValueError(
            f"{task.task_id} source lineage {task.evaluation.source_task_id} does not "
            f"match expected {expected_source_task_id}"
        )
    if source.sid != task.task_id:
        raise ValueError(f"{task.task_id} does not use its runtime task id as episode SID")
    if task.lifecycle_hooks.release != [WEB_STATE_RESET_HOOK]:
        raise ValueError(f"{task.task_id} does not use exactly the direct-web release hook")
    if len(task.website) != 1:
        raise ValueError(f"{task.task_id} does not have exactly one website")
    website = urlsplit(task.website[0].url)
    website_base = f"{website.scheme}://{website.netloc}"
    if website_base != source.app_base or parse_qs(website.query).get("sid") != [source.sid]:
        raise ValueError(f"{task.task_id} website URL does not match its state source")
    if "__CUA_GYM_" in task.evaluation.reward_script:
        raise ValueError(f"{task.task_id} reward script retains a CUA-Gym URL placeholder")

    matches = list((task_dir / "initial_states").glob(f"*/{source.sid}.json"))
    if len(matches) != 1:
        raise ValueError(
            f"{task.task_id} expected one initial state for {source.sid}, found {len(matches)}"
        )
    app_key = matches[0].parent.name
    contract = get_state_contract(app_key)
    if source.current_state_key != contract.current_state_key(source.sid):
        raise ValueError(f"{task.task_id} current-state key does not match {app_key}")
    if source.initial_state_key != contract.initial_state_key(source.sid):
        raise ValueError(f"{task.task_id} initial-state key does not match {app_key}")

    payload = json.loads(matches[0].read_text(encoding="utf-8"))
    if payload.get("sid") != source.sid or payload.get("has_custom_state") is not True:
        raise ValueError(f"{task.task_id} initial-state envelope is not SID scoped")
    if "stored_state" not in payload:
        raise ValueError(f"{task.task_id} initial-state envelope has no stored_state")
    host_state = task_dir.parent / "initial_states" / app_key / f"{source.sid}.json"
    if not host_state.is_file():
        raise ValueError(f"{task.task_id} has no shared host state for {source.sid}")
    if host_state.read_bytes() != matches[0].read_bytes():
        raise ValueError(
            f"{task.task_id} shared host state does not match task-local envelope"
        )
    initial_state = payload["stored_state"]
    result = evaluate_cua_reward(
        task.evaluation.reward_script,
        source_task_id=task.evaluation.source_task_id,
        sid=source.sid,
        snapshots={
            source.app_base: CuaSnapshot(
                initial_state=initial_state,
                current_state=initial_state,
            )
        },
        timeout=timeout,
    )
    return {
        "task_id": task.task_id,
        "source_task_id": task.evaluation.source_task_id,
        "expected_source_task_id": expected_source_task_id,
        "episode_sid": source.sid,
        "app_key": app_key,
        "app_base": source.app_base,
        "current_state_key": source.current_state_key,
        "initial_state_key": source.initial_state_key,
        "initial_reward": result.reward,
        "contract_checks": {
            "source_lineage": "PASS",
            "runtime_task_episode_sid": "PASS",
            "website_sid_and_base": "PASS",
            "state_key_templates": "PASS",
            "initial_state_envelope": "PASS",
            "shared_host_state": "PASS",
            "reward_placeholders_removed": "PASS",
            "direct_web_release_hook": "PASS",
        },
        "status": "PASS" if result.reward == 0.0 else "FAIL",
    }


def verify_imported_tasks(
    input_dir: Path,
    *,
    timeout: float,
    expected_sources: Mapping[str, str] | None = None,
) -> dict[str, object]:
    task_dirs = sorted(
        path for path in input_dir.iterdir() if path.is_dir() and (path / "task.json").is_file()
    )
    results: list[dict[str, object]] = []
    errors: list[dict[str, str]] = []
    for task_dir in task_dirs:
        try:
            results.append(
                verify_task_dir(
                    task_dir,
                    timeout=timeout,
                    expected_sources=expected_sources,
                )
            )
        except Exception as exc:  # keep a complete batch report
            errors.append({"task_id": task_dir.name, "error": str(exc)})

    passed = sum(result["status"] == "PASS" for result in results)
    return {
        "schema_version": 1,
        "stage": "TASK_IMPORT_INITIAL_REWARD",
        "status": "PASS" if task_dirs and passed == len(task_dirs) and not errors else "FAIL",
        "counts": {
            "discovered": len(task_dirs),
            "evaluated": len(results),
            "passed": passed,
            "errors": len(errors),
        },
        "results": results,
        "errors": errors,
        "note": "Initial reward only; historical or fresh headed evidence is a separate gate.",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--json-out", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=10.0)
    parser.add_argument(
        "--expected-sources-file",
        type=Path,
        help="optional JSON object mapping runtime episode task ids to source task ids",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    expected_sources: dict[str, str] | None = None
    if args.expected_sources_file is not None:
        payload = json.loads(args.expected_sources_file.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in payload.items()
        ):
            raise SystemExit("--expected-sources-file must contain a JSON string map")
        expected_sources = payload
    report = verify_imported_tasks(
        args.input_dir,
        timeout=args.timeout_seconds,
        expected_sources=expected_sources,
    )
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if report["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
