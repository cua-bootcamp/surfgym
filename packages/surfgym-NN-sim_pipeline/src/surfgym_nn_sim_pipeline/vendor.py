"""One-off script: extract OSWorld 1.0 instructions into a committed snapshot.

Not part of the runtime path. Run manually whenever the reference commit changes:

    python -m surfgym_nn_sim_pipeline.vendor --osworld-repo /path/to/OSWorld

The output feeds corpus.load_osworld_instructions() so a teammate can reproduce
a run without a local OSWorld clone.

Cross-check: packages/surfgym-travel-ad-hub's
surfgym_task/data/travel-ad-hub/reference/osworld/COVERAGE.md vendors a separate,
unmodified copy of the 22 chrome tasks it audited for coverage, pinned to the same
xlang-ai/OSWorld commit recorded below. If that file's commit ever disagrees with
OSWORLD_COMMIT here, the two vendored snapshots have drifted apart and both should
be refreshed together.
"""

import argparse
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

KST = timezone(timedelta(hours=9))
DOMAINS = ("gimp", "vlc", "chrome")

MODULE_DIR = Path(__file__).resolve().parent
OUTPUT_PATH = MODULE_DIR / "data" / "osworld_1_0.json"

OSWORLD_REPO_URL = "https://github.com/xlang-ai/OSWorld.git"


def _git_commit(repo_dir: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_dir), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _extract_domain(examples_dir: Path, domain: str) -> list[dict]:
    domain_dir = examples_dir / domain
    items = []
    for path in sorted(domain_dir.glob("*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        items.append(
            {
                "id": raw["id"],
                "instruction": raw["instruction"],
                "domain": domain,
            }
        )
    return items


def extract(osworld_repo: Path) -> dict:
    examples_dir = osworld_repo / "evaluation_examples" / "examples"
    tasks = []
    for domain in DOMAINS:
        tasks.extend(_extract_domain(examples_dir, domain))

    return {
        "osworld_repo": OSWORLD_REPO_URL,
        "osworld_commit": _git_commit(osworld_repo),
        "extracted_at": datetime.now(KST).isoformat(),
        "domains": list(DOMAINS),
        "tasks": tasks,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--osworld-repo", required=True, type=Path)
    args = parser.parse_args()

    snapshot = extract(args.osworld_repo)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    counts = {
        domain: sum(1 for t in snapshot["tasks"] if t["domain"] == domain) for domain in DOMAINS
    }
    print(f"wrote {len(snapshot['tasks'])} instructions -> {OUTPUT_PATH}")
    print(f"commit: {snapshot['osworld_commit']}")
    print(f"per domain: {counts}")


if __name__ == "__main__":
    main()
