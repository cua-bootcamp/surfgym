"""Stage the explicit published Web seed cohort outside canonical source data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from surfgym_task.cua.state_seed_projection import materialize_published_state_seeds


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--seeds-dir", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = materialize_published_state_seeds(
        manifest_path=args.manifest,
        seeds_dir=args.seeds_dir,
        output_root=args.output_root,
    )
    print(
        json.dumps(
            {
                "tasks": summary.task_count,
                "initial_atoms": summary.initial_atom_count,
                "terminal_criteria": summary.terminal_criteria_count,
                "apps": summary.app_counts,
                "aggregate_seed_sha256": summary.aggregate_seed_sha256,
                "output_root": str(args.output_root.resolve()),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
