from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from collections import Counter
from dataclasses import asdict, dataclass
from itertools import groupby
from pathlib import Path, PurePosixPath


@dataclass(frozen=True, order=True)
class TaskKey:
    domain: str
    seed_stem: str


@dataclass(frozen=True)
class ActiveSeed:
    key: TaskKey
    active_seed_path: str
    instruction: str
    evaluation_mode: str


@dataclass(frozen=True)
class GitEvidence:
    introducing_commit: str
    last_semantic_change_commit: str


def git_evidence(repo_root: Path, relative_path: str) -> GitEvidence:
    result = subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={repo_root.as_posix()}",
            "log",
            "--follow",
            "--format=%h",
            "--",
            relative_path,
        ],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    commits = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not commits:
        raise ValueError(f"no Git history for {relative_path}")
    return GitEvidence(
        introducing_commit=commits[-1],
        last_semantic_change_commit=commits[0],
    )


def collect_git_evidence(
    repo_root: Path, data_root: Path
) -> dict[TaskKey, GitEvidence]:
    evidence: dict[TaskKey, GitEvidence] = {}
    for seed in discover_active_seeds(data_root):
        evidence[seed.key] = git_evidence(repo_root, seed.active_seed_path)
    return evidence


ALLOWED_TRANSFORMATION_STATUSES = frozenset(
    {
        "transformed_from_osworld",
        "independent_original",
        "untransformed_osworld",
        "needs_review",
    }
)
ALLOWED_FIDELITY_CLASSES = frozenset(
    {
        "faithful",
        "capability_adapted",
        "interaction_only",
        "infeasible",
        "not_applicable",
    }
)

OSWORLD_DOMAIN_DIRS = {
    "spreadsheet": "libreoffice_calc",
    "word": "libreoffice_writer",
    "gimp": "gimp",
    "vlc": "vlc",
    "chrome": "chrome",
    "web": "chrome",
}


@dataclass(frozen=True)
class Decision:
    osworld_source_id: str | None
    capability_invariant: str
    transformation_status: str
    fidelity_class: str
    instruction_relation: str
    scenario_relation: str
    data_relation: str
    asset_relation: str
    setup_relation: str
    decision_reason: str
    evidence_locators: tuple[str, ...]
    predecessor_active_seed_path: str | None = None


def git_evidence_for_decision(
    repo_root: Path,
    seed: ActiveSeed,
    decision: Decision,
) -> GitEvidence:
    try:
        return git_evidence(repo_root, seed.active_seed_path)
    except ValueError:
        predecessor = decision.predecessor_active_seed_path
        if predecessor is None:
            raise ValueError(
                f"new active seed requires predecessor_active_seed_path: {seed.key}"
            ) from None
        if Path(predecessor).is_absolute() or PurePosixPath(predecessor).is_absolute():
            raise ValueError(
                "predecessor_active_seed_path must be repository-relative: "
                f"{predecessor}"
            ) from None

        predecessor_path = PurePosixPath(predecessor)
        expected_parent = PurePosixPath(
            "packages/surfgym-task/src/surfgym_task/data"
        ) / seed.key.domain / "seeds"
        if (
            predecessor_path.parent != expected_parent
            or predecessor_path.suffix != ".json"
            or any(part in {"", ".", ".."} for part in predecessor_path.parts)
        ):
            raise ValueError(
                "predecessor_active_seed_path must stay in the active seed directory "
                f"for {seed.key.domain}: {predecessor}"
            ) from None

        predecessor_git = git_evidence(repo_root, predecessor)
        return GitEvidence(
            introducing_commit=predecessor_git.introducing_commit,
            last_semantic_change_commit="WORKTREE",
        )


@dataclass(frozen=True)
class InventoryRow:
    domain: str
    seed_stem: str
    active_seed_path: str
    instruction: str
    evaluation_mode: str
    osworld_source_id: str | None
    lineage_evidence: tuple[str, ...]
    capability_invariant: str
    transformation_status: str
    fidelity_class: str
    instruction_relation: str
    scenario_relation: str
    data_relation: str
    asset_relation: str
    setup_relation: str
    decision_reason: str
    required_action: str
    evidence_locators: tuple[str, ...]
    introducing_commit: str
    last_semantic_change_commit: str

    @classmethod
    def from_parts(
        cls,
        seed: ActiveSeed,
        decision: Decision,
        git: GitEvidence,
    ) -> InventoryRow:
        return cls(
            domain=seed.key.domain,
            seed_stem=seed.key.seed_stem,
            active_seed_path=seed.active_seed_path,
            instruction=seed.instruction,
            evaluation_mode=seed.evaluation_mode,
            osworld_source_id=decision.osworld_source_id,
            lineage_evidence=decision.evidence_locators,
            capability_invariant=decision.capability_invariant,
            transformation_status=decision.transformation_status,
            fidelity_class=decision.fidelity_class,
            instruction_relation=decision.instruction_relation,
            scenario_relation=decision.scenario_relation,
            data_relation=decision.data_relation,
            asset_relation=decision.asset_relation,
            setup_relation=decision.setup_relation,
            decision_reason=decision.decision_reason,
            required_action=REQUIRED_ACTION_BY_STATUS[decision.transformation_status],
            evidence_locators=decision.evidence_locators,
            introducing_commit=git.introducing_commit,
            last_semantic_change_commit=git.last_semantic_change_commit,
        )


def _required_string(item: dict[str, object], field: str) -> str:
    value = item.get(field)
    if not isinstance(value, str):
        raise ValueError(f"decision field must be a string: {field}")
    return value


def load_decisions(path: Path) -> dict[TaskKey, Decision]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("decisions"), list):
        raise ValueError("decision registry must contain a decisions list")

    decisions: dict[TaskKey, Decision] = {}
    for item in payload["decisions"]:
        if not isinstance(item, dict):
            raise ValueError("decision entry must be an object")
        key = TaskKey(
            domain=_required_string(item, "domain"),
            seed_stem=_required_string(item, "seed_stem"),
        )
        if key in decisions:
            raise ValueError(f"duplicate decision: {key.domain}/{key.seed_stem}")

        source_id = item.get("osworld_source_id")
        if source_id is not None and not isinstance(source_id, str):
            raise ValueError("decision field must be a string or null: osworld_source_id")
        locators = item.get("evidence_locators")
        if (
            not isinstance(locators, list)
            or not locators
            or not all(isinstance(locator, str) and locator for locator in locators)
        ):
            raise ValueError("evidence_locators must be a non-empty list of strings")
        predecessor = item.get("predecessor_active_seed_path")
        if predecessor is not None and not isinstance(predecessor, str):
            raise ValueError(
                "decision field must be a string or null: "
                "predecessor_active_seed_path"
            )

        decision = Decision(
            osworld_source_id=source_id,
            capability_invariant=_required_string(item, "capability_invariant"),
            transformation_status=_required_string(item, "transformation_status"),
            fidelity_class=_required_string(item, "fidelity_class"),
            instruction_relation=_required_string(item, "instruction_relation"),
            scenario_relation=_required_string(item, "scenario_relation"),
            data_relation=_required_string(item, "data_relation"),
            asset_relation=_required_string(item, "asset_relation"),
            setup_relation=_required_string(item, "setup_relation"),
            decision_reason=_required_string(item, "decision_reason"),
            evidence_locators=tuple(locators),
            predecessor_active_seed_path=predecessor,
        )
        if decision.transformation_status not in ALLOWED_TRANSFORMATION_STATUSES:
            raise ValueError(
                f"invalid transformation status: {decision.transformation_status}"
            )
        if decision.fidelity_class not in ALLOWED_FIDELITY_CLASSES:
            raise ValueError(f"invalid fidelity class: {decision.fidelity_class}")
        decisions[key] = decision
    return decisions


def _evaluation_mode(payload: dict[str, object]) -> str:
    evaluation = payload.get("evaluation")
    if isinstance(evaluation, dict) and isinstance(evaluation.get("mode"), str):
        return str(evaluation["mode"])
    return "criteria"


def discover_active_seeds(data_root: Path) -> list[ActiveSeed]:
    rows: list[ActiveSeed] = []
    for domain_dir in sorted(path for path in data_root.iterdir() if path.is_dir()):
        seed_dir = domain_dir / "seeds"
        if not seed_dir.is_dir():
            continue
        for seed_path in sorted(seed_dir.glob("*.json")):
            payload = json.loads(seed_path.read_text(encoding="utf-8"))
            mode = _evaluation_mode(payload)
            if domain_dir.name not in {"spreadsheet", "word"} and mode != "infeasible":
                continue
            rows.append(
                ActiveSeed(
                    key=TaskKey(domain_dir.name, seed_path.stem),
                    active_seed_path=seed_path.relative_to(data_root.parents[4]).as_posix(),
                    instruction=str(payload["instruction"]),
                    evaluation_mode=mode,
                )
            )
    return rows


def validate_decisions(
    active: list[ActiveSeed],
    decisions: dict[TaskKey, Decision],
    osworld_examples_root: Path,
) -> None:
    active_by_key = {row.key: row for row in active}
    if len(active_by_key) != len(active):
        raise ValueError("active seeds contain duplicate keys")
    if set(active_by_key) != set(decisions):
        missing = sorted(set(active_by_key) - set(decisions))
        extra = sorted(set(decisions) - set(active_by_key))
        raise ValueError(
            f"decision coverage mismatch: missing={missing}, extra={extra}"
        )

    for key, decision in decisions.items():
        if decision.transformation_status == "independent_original":
            if decision.osworld_source_id is not None:
                raise ValueError(f"independent original has OSWorld ID: {key}")
            continue
        if not decision.osworld_source_id:
            raise ValueError(f"OSWorld-derived row lacks source ID: {key}")
        try:
            osworld_domain = OSWORLD_DOMAIN_DIRS[key.domain]
        except KeyError as error:
            raise ValueError(f"no OSWorld domain mapping: {key.domain}") from error
        original_path = (
            osworld_examples_root
            / osworld_domain
            / f"{decision.osworld_source_id}.json"
        )
        if not original_path.is_file():
            raise ValueError(f"missing OSWorld original: {original_path}")
        original = json.loads(original_path.read_text(encoding="utf-8"))
        original_id = original.get("id")
        if original_id != decision.osworld_source_id:
            raise ValueError(
                "OSWorld ID mismatch: "
                f"expected={decision.osworld_source_id}, actual={original_id}, "
                f"path={original_path}"
            )
        if decision.instruction_relation == "exact":
            if active_by_key[key].instruction != original.get("instruction"):
                raise ValueError(f"false exact-instruction decision: {key}")


def build_inventory(
    repo_root: Path,
    data_root: Path,
    decision_path: Path,
) -> list[InventoryRow]:
    active = discover_active_seeds(data_root)
    decisions = load_decisions(decision_path)
    validate_decisions(
        active,
        decisions,
        repo_root.parent / "OSWorld" / "evaluation_examples" / "examples",
    )
    rows = [
        InventoryRow.from_parts(
            seed,
            decisions[seed.key],
            git_evidence_for_decision(repo_root, seed, decisions[seed.key]),
        )
        for seed in active
    ]
    return sorted(rows, key=lambda row: (row.domain, row.seed_stem))


STATUS_ORDER = (
    "transformed_from_osworld",
    "independent_original",
    "untransformed_osworld",
    "needs_review",
)

REQUIRED_ACTION_BY_STATUS = {
    "transformed_from_osworld": "Keep unchanged.",
    "independent_original": "Keep unchanged.",
    "untransformed_osworld": "Replace with a transformed seed.",
    "needs_review": "Resolve before any seed edit.",
}


def _ordered_inventory_rows(rows: list[InventoryRow]) -> list[InventoryRow]:
    return sorted(rows, key=lambda row: (row.domain, row.seed_stem))


def _status_counts(rows: list[InventoryRow]) -> dict[str, int]:
    counts = Counter(row.transformation_status for row in rows)
    return {status: counts[status] for status in STATUS_ORDER}


def render_json(rows: list[InventoryRow]) -> str:
    ordered_rows = _ordered_inventory_rows(rows)
    payload = {
        "total": len(ordered_rows),
        "counts": _status_counts(ordered_rows),
        "rows": [asdict(row) for row in ordered_rows],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def _markdown_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\r\n", "<br>").replace("\n", "<br>")


def render_markdown(rows: list[InventoryRow]) -> str:
    ordered_rows = _ordered_inventory_rows(rows)
    counts = _status_counts(ordered_rows)
    lines = [
        "# Task transformation inventory",
        "",
        f"Total active seeds: {len(ordered_rows)}",
        "",
        "## Summary",
        "",
        "| transformation_status | count |",
        "| --- | ---: |",
    ]
    lines.extend(f"| {status} | {counts[status]} |" for status in STATUS_ORDER)

    for domain, domain_rows in groupby(ordered_rows, key=lambda row: row.domain):
        lines.extend(
            [
                "",
                f"## {domain}",
                "",
                "| seed_stem | source ID | status | fidelity | introducing commit | last semantic change | reason | lineage evidence | required action | evidence locators |",
                "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for row in domain_rows:
            source_id = row.osworld_source_id or "—"
            lineage_evidence = "<br>".join(row.lineage_evidence)
            locators = "<br>".join(row.evidence_locators)
            lines.append(
                "| "
                + " | ".join(
                    (
                        _markdown_cell(row.seed_stem),
                        _markdown_cell(source_id),
                        _markdown_cell(row.transformation_status),
                        _markdown_cell(row.fidelity_class),
                        _markdown_cell(row.introducing_commit),
                        _markdown_cell(row.last_semantic_change_commit),
                        _markdown_cell(row.decision_reason),
                        _markdown_cell(lineage_evidence),
                        _markdown_cell(row.required_action),
                        _markdown_cell(locators),
                    )
                )
                + " |"
            )
    return "\n".join(lines) + "\n"


def _temporary_output_path(target: Path, suffix: str) -> Path:
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=suffix,
        dir=target.parent,
    )
    os.close(descriptor)
    return Path(temporary)


def _stage_report(target: Path, content: str) -> Path:
    staged = _temporary_output_path(target, ".tmp")
    try:
        staged.write_text(content, encoding="utf-8")
    except BaseException:
        staged.unlink(missing_ok=True)
        raise
    return staged


def _backup_report(target: Path) -> Path | None:
    if not target.exists():
        return None
    backup = _temporary_output_path(target, ".bak")
    try:
        backup.write_bytes(target.read_bytes())
    except BaseException:
        backup.unlink(missing_ok=True)
        raise
    return backup


def _restore_report(target: Path, backup: Path | None) -> None:
    if backup is None:
        target.unlink(missing_ok=True)
    else:
        backup.replace(target)


def _discard_temporary(path: Path | None) -> None:
    if path is not None:
        path.unlink(missing_ok=True)


def publish_report_pair(
    json_path: Path,
    json_text: str,
    markdown_path: Path,
    markdown_text: str,
) -> None:
    staged_json = _stage_report(json_path, json_text)
    staged_markdown: Path | None = None
    json_backup: Path | None = None
    markdown_backup: Path | None = None
    backups_ready = False
    try:
        staged_markdown = _stage_report(markdown_path, markdown_text)
        json_backup = _backup_report(json_path)
        markdown_backup = _backup_report(markdown_path)
        backups_ready = True
        staged_json.replace(json_path)
        staged_json = None
        staged_markdown.replace(markdown_path)
        staged_markdown = None
    except BaseException:
        if backups_ready:
            _restore_report(json_path, json_backup)
            json_backup = None
            _restore_report(markdown_path, markdown_backup)
            markdown_backup = None
        raise
    finally:
        _discard_temporary(staged_json)
        _discard_temporary(staged_markdown)
        _discard_temporary(json_backup)
        _discard_temporary(markdown_backup)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit local Git history for active seeds")
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--decisions", type=Path)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--markdown-out", type=Path)
    args = parser.parse_args(argv)

    report_paths = (args.decisions, args.json_out, args.markdown_out)
    if any(path is not None for path in report_paths):
        if any(path is None for path in report_paths):
            parser.error(
                "--decisions, --json-out, and --markdown-out must be provided together"
            )
        rows = build_inventory(
            args.repo_root.resolve(),
            args.data_root.resolve(),
            args.decisions.resolve(),
        )
        json_text = render_json(rows)
        markdown_text = render_markdown(rows)
        publish_report_pair(
            args.json_out,
            json_text,
            args.markdown_out,
            markdown_text,
        )
        counts = _status_counts(rows)
        print(
            f"audited={len(rows)} "
            + " ".join(f"{status}={counts[status]}" for status in STATUS_ORDER)
        )
        return 0

    evidence = collect_git_evidence(args.repo_root, args.data_root)
    for key in sorted(evidence):
        item = evidence[key]
        print(
            f"{key.domain}/{key.seed_stem}: "
            f"introducing={item.introducing_commit} "
            f"last_semantic_change={item.last_semantic_change_commit}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
