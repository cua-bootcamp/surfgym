"""Verify and stage the explicitly published Web seed projection cohort.

The canonical Web seed directory is the runtime source of truth.  CUA naming
is retained here only for offline lineage and audit.  Cohort membership always
comes from the committed manifest; filename prefixes are never discovery.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

JsonObject = dict[str, Any]


@dataclass(frozen=True)
class ProjectionTask:
    source_task_id: str
    seed: str
    app_key: str
    source_task_name: str
    seed_sha256: str
    initial_atoms: int
    terminal_criteria: int


@dataclass(frozen=True)
class ProjectionManifest:
    path: Path
    tasks: tuple[ProjectionTask, ...]
    expected_initial_atoms: int
    expected_terminal_criteria: int
    expected_app_counts: dict[str, int]
    expected_aggregate_seed_sha256: str
    raw: JsonObject


@dataclass(frozen=True)
class ProjectionSummary:
    task_count: int
    initial_atom_count: int
    terminal_criteria_count: int
    app_counts: dict[str, int]
    aggregate_seed_sha256: str
    seed_names: tuple[str, ...]


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _require_sha256(value: object, field: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError(f"{field} must be a lowercase SHA-256 string")
    try:
        int(value, 16)
    except ValueError as exc:
        raise ValueError(f"{field} must be a lowercase SHA-256 string") from exc
    if value != value.lower():
        raise ValueError(f"{field} must be a lowercase SHA-256 string")
    return value


def _require_count(value: object, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{field} must be a non-negative integer")
    return value


def _safe_relative_path(root: Path, value: object, field: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a relative path")
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"{field} must stay inside {root}")
    resolved = (root / relative).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"{field} must stay inside {root}") from exc
    return resolved


def load_projection_manifest(manifest_path: Path) -> ProjectionManifest:
    """Load and structurally validate an explicit projection manifest."""

    payload = _read_json(manifest_path)
    if not isinstance(payload, dict) or payload.get("version") != 1:
        raise ValueError(f"unsupported projection manifest: {manifest_path}")

    raw_tasks = payload.get("tasks")
    if not isinstance(raw_tasks, list) or not raw_tasks:
        raise ValueError("projection manifest tasks must be a non-empty list")

    tasks: list[ProjectionTask] = []
    task_ids: set[str] = set()
    seed_names: set[str] = set()
    for index, raw_task in enumerate(raw_tasks):
        if not isinstance(raw_task, dict):
            raise ValueError(f"manifest tasks[{index}] must be an object")
        task_id = raw_task.get("source_task_id")
        seed = raw_task.get("seed")
        app_key = raw_task.get("app_key")
        source_task_name = raw_task.get("source_task_name")
        if not isinstance(task_id, str) or not task_id or task_id in task_ids:
            raise ValueError(f"invalid or duplicate source_task_id at tasks[{index}]")
        if (
            not isinstance(seed, str)
            or Path(seed).name != seed
            or Path(seed).suffix != ".json"
            or seed in seed_names
        ):
            raise ValueError(f"invalid or duplicate seed at tasks[{index}]")
        if not isinstance(app_key, str) or not app_key:
            raise ValueError(f"tasks[{index}].app_key must be a non-empty string")
        if not isinstance(source_task_name, str) or not source_task_name:
            raise ValueError(f"tasks[{index}].source_task_name must be a non-empty string")
        tasks.append(
            ProjectionTask(
                source_task_id=task_id,
                seed=seed,
                app_key=app_key,
                source_task_name=source_task_name,
                seed_sha256=_require_sha256(
                    raw_task.get("seed_sha256"), f"tasks[{index}].seed_sha256"
                ),
                initial_atoms=_require_count(
                    raw_task.get("initial_atoms"), f"tasks[{index}].initial_atoms"
                ),
                terminal_criteria=_require_count(
                    raw_task.get("terminal_criteria"),
                    f"tasks[{index}].terminal_criteria",
                ),
            )
        )
        task_ids.add(task_id)
        seed_names.add(seed)

    counts = payload.get("counts")
    if not isinstance(counts, dict):
        raise ValueError("projection manifest counts must be an object")
    expected_tasks = _require_count(counts.get("tasks"), "counts.tasks")
    if expected_tasks != len(tasks):
        raise ValueError(
            f"manifest task count mismatch: expected {expected_tasks}, found {len(tasks)}"
        )
    raw_app_counts = counts.get("apps")
    if not isinstance(raw_app_counts, dict):
        raise ValueError("counts.apps must be an object")
    expected_app_counts = {
        app: _require_count(count, f"counts.apps.{app}")
        for app, count in raw_app_counts.items()
        if isinstance(app, str) and app
    }
    if len(expected_app_counts) != len(raw_app_counts):
        raise ValueError("counts.apps keys must be non-empty strings")

    return ProjectionManifest(
        path=manifest_path,
        tasks=tuple(tasks),
        expected_initial_atoms=_require_count(
            counts.get("initial_atoms"), "counts.initial_atoms"
        ),
        expected_terminal_criteria=_require_count(
            counts.get("terminal_criteria"), "counts.terminal_criteria"
        ),
        expected_app_counts=dict(sorted(expected_app_counts.items())),
        expected_aggregate_seed_sha256=_require_sha256(
            payload.get("aggregate_seed_sha256"), "aggregate_seed_sha256"
        ),
        raw=payload,
    )


def _verify_lineage(manifest: ProjectionManifest) -> None:
    source = manifest.raw.get("source")
    if not isinstance(source, dict):
        raise ValueError("projection manifest source must be an object")
    _require_sha256(
        source.get("import_verification_sha256"), "source.import_verification_sha256"
    )

    cohort = source.get("cohort")
    if not isinstance(cohort, dict):
        raise ValueError("source.cohort must be an object")
    cohort_path = _safe_relative_path(
        manifest.path.parent, cohort.get("path"), "source.cohort.path"
    )
    expected_cohort_hash = _require_sha256(
        cohort.get("sha256"), "source.cohort.sha256"
    )
    if _sha256(cohort_path) != expected_cohort_hash:
        raise ValueError(f"cohort SHA-256 mismatch: {cohort_path}")
    cohort_payload = _read_json(cohort_path)
    cohort_ids = cohort_payload.get("task_ids") if isinstance(cohort_payload, dict) else None
    if not isinstance(cohort_ids, list) or not all(isinstance(item, str) for item in cohort_ids):
        raise ValueError("source cohort task_ids must be a list of strings")
    manifest_ids = {task.source_task_id for task in manifest.tasks}
    if len(cohort_ids) != len(set(cohort_ids)) or set(cohort_ids) != manifest_ids:
        raise ValueError("source cohort task IDs do not match the manifest")

    raw_fragments = source.get("predicate_fragments")
    if not isinstance(raw_fragments, list) or not raw_fragments:
        raise ValueError("source.predicate_fragments must be a non-empty list")
    fragment_tasks: dict[str, JsonObject] = {}
    for index, raw_fragment in enumerate(raw_fragments):
        if not isinstance(raw_fragment, dict):
            raise ValueError(f"source.predicate_fragments[{index}] must be an object")
        fragment_path = _safe_relative_path(
            manifest.path.parent,
            raw_fragment.get("path"),
            f"source.predicate_fragments[{index}].path",
        )
        expected_hash = _require_sha256(
            raw_fragment.get("sha256"),
            f"source.predicate_fragments[{index}].sha256",
        )
        if _sha256(fragment_path) != expected_hash:
            raise ValueError(f"predicate fragment SHA-256 mismatch: {fragment_path}")
        fragment = _read_json(fragment_path)
        entries = fragment.get("tasks") if isinstance(fragment, dict) else None
        if fragment.get("version") != 1 or not isinstance(entries, list):
            raise ValueError(f"unsupported predicate fragment: {fragment_path}")
        for entry in entries:
            task_id = entry.get("task_id") if isinstance(entry, dict) else None
            if not isinstance(task_id, str) or task_id in fragment_tasks:
                raise ValueError(f"invalid or duplicate predicate task in {fragment_path}")
            fragment_tasks[task_id] = entry
    if set(fragment_tasks) != manifest_ids:
        raise ValueError("predicate fragment task IDs do not match the manifest")
    terminal_by_id = {task.source_task_id: task.terminal_criteria for task in manifest.tasks}
    for task_id, entry in fragment_tasks.items():
        atoms = entry.get("atoms")
        if not isinstance(atoms, list) or len(atoms) != terminal_by_id[task_id]:
            raise ValueError(f"predicate atom count mismatch: {task_id}")


def _seed_path(seeds_dir: Path, task: ProjectionTask) -> Path:
    path = (seeds_dir / task.seed).resolve()
    try:
        path.relative_to(seeds_dir.resolve())
    except ValueError as exc:
        raise ValueError(f"manifest seed escapes the canonical directory: {task.seed}") from exc
    return path


def _aggregate_seed_sha256(paths: list[Path]) -> str:
    hashes = "\n".join(_sha256(path) for path in sorted(paths, key=lambda path: path.name))
    return hashlib.sha256(hashes.encode()).hexdigest()


def verify_published_state_seeds(
    *,
    manifest_path: Path,
    seeds_dir: Path,
) -> ProjectionSummary:
    """Verify the exact manifest cohort inside the normal canonical Web seeds."""

    manifest = load_projection_manifest(manifest_path)
    _verify_lineage(manifest)

    paths: list[Path] = []
    initial_atom_count = 0
    terminal_criteria_count = 0
    app_counts: Counter[str] = Counter()
    for task in manifest.tasks:
        path = _seed_path(seeds_dir, task)
        if not path.is_file():
            raise ValueError(f"manifest seed is missing: {path}")
        actual_hash = _sha256(path)
        if actual_hash != task.seed_sha256:
            raise ValueError(
                f"seed SHA-256 mismatch for {task.seed}: "
                f"expected {task.seed_sha256}, found {actual_hash}"
            )

        payload = _read_json(path)
        if not isinstance(payload, dict):
            raise ValueError(f"seed must be an object: {path}")
        states = payload.get("states")
        if not isinstance(states, list) or len(states) != 2:
            raise ValueError(f"seed must contain exactly two states: {path}")
        baseline, terminal = states
        if not isinstance(baseline, list) or not baseline:
            raise ValueError(f"seed baseline must be non-empty: {path}")
        if not isinstance(terminal, list) or not terminal:
            raise ValueError(f"seed terminal criteria must be non-empty: {path}")
        if payload.get("domain") != "web":
            raise ValueError(f"seed domain must be web: {path}")
        if payload.get("empty_start") is not False:
            raise ValueError(f"seed empty_start must be false: {path}")
        if payload.get("accumulation") != "DELTA":
            raise ValueError(f"seed accumulation must be DELTA: {path}")

        website = payload.get("website")
        if not isinstance(website, str):
            raise ValueError(f"seed website must be a URL string: {path}")
        parsed_url = urlsplit(website)
        sid = parse_qs(parsed_url.query).get("sid")
        if parsed_url.scheme not in {"http", "https"} or sid != [task.source_task_id]:
            raise ValueError(f"seed website must carry its exact source SID: {path}")

        for index, atom in enumerate(baseline):
            spec = atom.get("spec") if isinstance(atom, dict) else None
            if (
                not isinstance(spec, dict)
                or spec.get("target") != "app_state"
                or not isinstance(spec.get("path"), str)
                or not spec["path"]
            ):
                raise ValueError(f"invalid baseline atom {index}: {path}")
        for index, atom in enumerate(terminal):
            spec = atom.get("spec") if isinstance(atom, dict) else None
            if (
                not isinstance(spec, dict)
                or not isinstance(spec.get("script"), str)
                or "query" not in spec
                or "path" not in spec
                or "value" not in atom
            ):
                raise ValueError(f"invalid terminal criterion {index}: {path}")

        if len(baseline) != task.initial_atoms:
            raise ValueError(f"initial atom count mismatch: {task.seed}")
        if len(terminal) != task.terminal_criteria:
            raise ValueError(f"terminal criterion count mismatch: {task.seed}")
        initial_atom_count += len(baseline)
        terminal_criteria_count += len(terminal)
        app_counts[task.app_key] += 1
        paths.append(path)

    actual_app_counts = dict(sorted(app_counts.items()))
    aggregate_hash = _aggregate_seed_sha256(paths)
    if initial_atom_count != manifest.expected_initial_atoms:
        raise ValueError("manifest initial atom total does not match the seeds")
    if terminal_criteria_count != manifest.expected_terminal_criteria:
        raise ValueError("manifest terminal criterion total does not match the seeds")
    if actual_app_counts != manifest.expected_app_counts:
        raise ValueError("manifest app counts do not match the seeds")
    if aggregate_hash != manifest.expected_aggregate_seed_sha256:
        raise ValueError(
            "aggregate seed SHA-256 mismatch: "
            f"expected {manifest.expected_aggregate_seed_sha256}, found {aggregate_hash}"
        )

    return ProjectionSummary(
        task_count=len(manifest.tasks),
        initial_atom_count=initial_atom_count,
        terminal_criteria_count=terminal_criteria_count,
        app_counts=actual_app_counts,
        aggregate_seed_sha256=aggregate_hash,
        seed_names=tuple(Path(task.seed).stem for task in manifest.tasks),
    )


def materialize_published_state_seeds(
    *,
    manifest_path: Path,
    seeds_dir: Path,
    output_root: Path,
) -> ProjectionSummary:
    """Copy only the verified manifest cohort into a run-owned staging root."""

    summary = verify_published_state_seeds(
        manifest_path=manifest_path,
        seeds_dir=seeds_dir,
    )
    manifest = load_projection_manifest(manifest_path)
    output_seeds = output_root / "seeds"
    if output_seeds.exists() and any(output_seeds.iterdir()):
        raise ValueError(f"refusing to overwrite non-empty seed directory: {output_seeds}")
    output_seeds.mkdir(parents=True, exist_ok=True)
    for task in manifest.tasks:
        shutil.copyfile(_seed_path(seeds_dir, task), output_seeds / task.seed)

    report = {
        "version": 1,
        "status": "PASS",
        "manifest": str(manifest_path.resolve()),
        "source_seeds": str(seeds_dir.resolve()),
        "counts": {
            "tasks": summary.task_count,
            "initial_atoms": summary.initial_atom_count,
            "terminal_criteria": summary.terminal_criteria_count,
            "apps": summary.app_counts,
        },
        "aggregate_seed_sha256": summary.aggregate_seed_sha256,
        "seeds": [task.seed for task in manifest.tasks],
    }
    (output_root / "projection-verification.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary
