#!/usr/bin/env python3
"""Verify the explicit canonical Web cohort in a run-owned task database."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from surfgym_contracts.task import Task
from surfgym_task.cua.state_seed_projection import (
    load_projection_manifest,
    verify_published_state_seeds,
)
from surfgym_task.hoare import HoareStateGenerator
from surfgym_task.io import SeedReader
from surfgym_task.main import _allocate_hooks, _release_hooks
from surfgym_task.seed import CriteriaSeedTask


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--seeds-dir", required=True, type=Path)
    parser.add_argument("--tasks-db", required=True, type=Path)
    parser.add_argument("--reference-report", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    return parser.parse_args()


def _expected_task_ids(seed_entries: list[tuple[object, str]]) -> set[str]:
    generator = HoareStateGenerator(granularity="COARSE")
    task_ids: list[str] = []
    for seed, seed_name in seed_entries:
        if isinstance(seed, CriteriaSeedTask):
            task_ids.extend(
                f"{seed_name}_{window.origin_start_idx}_{window.origin_end_idx}"
                for window in generator.generate(seed)
            )
        else:
            task_ids.append(seed_name)
    if len(task_ids) != len(set(task_ids)):
        raise ValueError("canonical Web seeds generate duplicate task IDs")
    return set(task_ids)


def main() -> None:
    args = parse_args()
    web_source_root = args.seeds_dir.resolve().parent
    try:
        args.tasks_db.resolve().relative_to(web_source_root)
    except ValueError:
        pass
    else:
        raise ValueError("tasks DB must be run-owned and outside canonical Web source data")

    summary = verify_published_state_seeds(
        manifest_path=args.manifest,
        seeds_dir=args.seeds_dir,
    )
    manifest = load_projection_manifest(args.manifest)
    seed_entries = list(SeedReader(args.seeds_dir).get_seed())
    seed_by_name = {name: seed for seed, name in seed_entries}
    expected_task_ids = _expected_task_ids(seed_entries)

    reference_payload = json.loads(args.reference_report.read_text(encoding="utf-8"))
    reference_by_id = {
        result["task_id"]: result
        for result in reference_payload.get("results", [])
        if isinstance(result, dict) and isinstance(result.get("task_id"), str)
    }

    with sqlite3.connect(args.tasks_db) as connection:
        rows = connection.execute("SELECT task_id, payload FROM tasks ORDER BY task_id").fetchall()
    if len(rows) != len({task_id for task_id, _payload in rows}):
        raise ValueError("task database contains duplicate task IDs")
    tasks = {task_id: Task.model_validate_json(payload) for task_id, payload in rows}

    errors: list[str] = []
    if set(tasks) != expected_task_ids:
        missing = sorted(expected_task_ids - set(tasks))
        extra = sorted(set(tasks) - expected_task_ids)
        errors.append(f"task DB cohort mismatch: missing={missing}, extra={extra}")

    results: list[dict[str, object]] = []
    for manifest_task in manifest.tasks:
        seed_name = Path(manifest_task.seed).stem
        seed = seed_by_name.get(seed_name)
        if not isinstance(seed, CriteriaSeedTask) or len(seed.states) != 2:
            errors.append(f"{seed_name}: missing or not a two-state criteria seed")
            continue
        task_id = f"{seed_name}_0_1"
        task = tasks.get(task_id)
        if task is None:
            errors.append(f"{seed_name}: missing task {task_id}")
            continue

        reference = reference_by_id.get(manifest_task.source_task_id)
        expected_evaluation = seed.states[1].to_criteria_evaluation()
        expected_allocate = _allocate_hooks(seed.domain, seed.states[0].atoms)
        expected_release = _release_hooks(seed.domain)
        checks = {
            "instruction": task.instruction == seed.instruction,
            "website": len(task.website) == 1 and task.website[0].url == seed.website,
            "evaluation": task.evaluation == expected_evaluation,
            "allocate": task.lifecycle_hooks.allocate == expected_allocate,
            "release": task.lifecycle_hooks.release == expected_release,
            "reference": bool(reference and reference.get("passed") is True),
        }
        if not all(checks.values()):
            errors.append(
                f"{seed_name}: failed checks "
                + ", ".join(name for name, passed in checks.items() if not passed)
            )
        results.append(
            {
                "seed": seed_name,
                "task_id": task_id,
                "terminal_criteria": len(expected_evaluation.criteria),
                "checks": checks,
            }
        )

    checks = {
        "canonical_web_seeds": len(seed_entries),
        "expected_tasks": len(expected_task_ids),
        "db_tasks": len(tasks),
        "unique_task_ids": len(set(tasks)),
        "verified_projection_tasks": len(results),
        "initial_atoms": summary.initial_atom_count,
        "terminal_criteria": sum(int(result["terminal_criteria"]) for result in results),
        "errors": len(errors),
    }
    status = (
        "PASS"
        if len(tasks) == len(expected_task_ids)
        and len(results) == summary.task_count
        and checks["terminal_criteria"] == summary.terminal_criteria_count
        and not errors
        else "FAIL"
    )
    report = {
        "version": 1,
        "status": status,
        "scope": "RUN_OWNED_WEB_TASK_DB_EXPLICIT_PROJECTION",
        "evidence_class": "STATIC_BINARY_AND_HISTORICAL_REFERENCE_NOT_HEADED",
        "manifest": str(args.manifest.resolve()),
        "seeds_dir": str(args.seeds_dir.resolve()),
        "tasks_db": str(args.tasks_db.resolve()),
        "reference_report": str(args.reference_report.resolve()),
        "checks": checks,
        "errors": errors,
        "results": results,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": status, **checks}, ensure_ascii=False))
    if status != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
