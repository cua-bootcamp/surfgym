#!/usr/bin/env python3
"""Verify compilation contracts for the explicit canonical Web seed cohort."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from surfgym_task.cua.state_seed_projection import (
    load_projection_manifest,
    verify_published_state_seeds,
)
from surfgym_task.hoare import HoareStateGenerator
from surfgym_task.io import SeedReader
from surfgym_task.main import _allocate_hooks, _release_hooks, _validate_profile
from surfgym_task.seed import CriteriaSeedTask


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--seeds-dir", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = verify_published_state_seeds(
        manifest_path=args.manifest,
        seeds_dir=args.seeds_dir,
    )
    manifest = load_projection_manifest(args.manifest)
    cohort_names = {Path(task.seed).stem for task in manifest.tasks}
    seed_by_name = {
        name: seed
        for seed, name in SeedReader(args.seeds_dir).get_seed()
        if name in cohort_names
    }

    generator = HoareStateGenerator(granularity="COARSE")
    results: list[dict[str, object]] = []
    errors: list[str] = []
    for task in manifest.tasks:
        seed_name = Path(task.seed).stem
        seed = seed_by_name.get(seed_name)
        if not isinstance(seed, CriteriaSeedTask):
            errors.append(f"{seed_name}: missing or not a criteria seed")
            continue
        try:
            _validate_profile(seed.domain, "ROLLOUT")
            windows = list(generator.generate(seed))
            if len(windows) != 1:
                raise ValueError(f"expected one COARSE window, got {len(windows)}")
            window = windows[0]
            if (window.origin_start_idx, window.origin_end_idx) != (0, 1):
                raise ValueError("expected the full 0->1 transition")

            allocate = _allocate_hooks(seed.domain, window.start_state.atoms)
            release = _release_hooks(seed.domain)
            evaluation = window.end_state.to_criteria_evaluation()
            if len(allocate) != 1 or "location.reload()" not in allocate[0].script:
                raise ValueError("web allocation is not one batched setter plus reload")
            if len(release) != 1:
                raise ValueError("web release hook is missing")
            if evaluation.operator != "and":
                raise ValueError("terminal evaluation is not conjunction")

            results.append(
                {
                    "seed": seed_name,
                    "source_task_id": task.source_task_id,
                    "domain": seed.domain,
                    "website": seed.website,
                    "initial_atoms": len(window.start_state.atoms),
                    "terminal_criteria": len(evaluation.criteria),
                    "evaluation_operator": evaluation.operator,
                    "allocate_hooks": len(allocate),
                    "release_hooks": len(release),
                }
            )
        except Exception as exc:  # noqa: BLE001 - collect every cohort error
            errors.append(f"{seed_name}: {exc}")

    checks = {
        "seeds": len(results),
        "initial_atoms": sum(int(item["initial_atoms"]) for item in results),
        "terminal_criteria": sum(int(item["terminal_criteria"]) for item in results),
        "criteria_and": sum(item["evaluation_operator"] == "and" for item in results),
        "batched_web_allocate": sum(item["allocate_hooks"] == 1 for item in results),
        "web_release": sum(item["release_hooks"] == 1 for item in results),
        "errors": len(errors),
    }
    status = (
        "PASS"
        if checks["seeds"] == summary.task_count
        and checks["initial_atoms"] == summary.initial_atom_count
        and checks["terminal_criteria"] == summary.terminal_criteria_count
        and not errors
        else "FAIL"
    )
    report = {
        "version": 1,
        "status": status,
        "scope": "EXPLICIT_CANONICAL_WEB_PROJECTION",
        "manifest": str(args.manifest.resolve()),
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
