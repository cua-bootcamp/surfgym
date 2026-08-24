"""Run host-only Chrome CUA validation against an already-running local SurfGym gateway."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPOSITORY_ROOT / "snapshots" / "generate"))

from chrome_cua import (  # noqa: E402
    ChromeCuaRunner,
    ChromeProvenance,
    ValidationPlan,
    default_validation_plan,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gateway-url", required=True)
    parser.add_argument(
        "--fixture-health-url",
        required=True,
        help="Docker fixture Gateway /health endpoint for release reconciliation.",
    )
    parser.add_argument("--timeout-seconds", type=float, default=600.0)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--provenance",
        type=Path,
        required=True,
        help="Canonical Docker chrome-provenance.json; it is recorded unchanged in the manifest.",
    )
    parser.add_argument(
        "--plan",
        type=Path,
        help="Optional JSON ValidationPlan. Defaults to password-manager plus infeasible controls.",
    )
    parser.add_argument(
        "--base-session-id",
        type=int,
        default=time.time_ns() // 1_000_000,
        help="Only used by the built-in default plan.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    provenance = ChromeProvenance.model_validate_json(args.provenance.read_text(encoding="utf-8"))
    plan = (
        ValidationPlan.model_validate_json(args.plan.read_text(encoding="utf-8"))
        if args.plan is not None
        else default_validation_plan(base_session_id=args.base_session_id)
    )
    manifest_path = ChromeCuaRunner(
        gateway_url=args.gateway_url,
        fixture_health_url=args.fixture_health_url,
        timeout_seconds=args.timeout_seconds,
        output_dir=args.output_dir,
    ).run(plan=plan, provenance=provenance)
    print(manifest_path)


if __name__ == "__main__":
    main()
