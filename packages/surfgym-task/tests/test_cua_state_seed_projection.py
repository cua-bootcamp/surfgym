import hashlib
import json
from pathlib import Path

import pytest
from surfgym_task.cua.state_seed_projection import (
    materialize_published_state_seeds,
    verify_published_state_seeds,
)
from surfgym_task.hoare import HoareStateGenerator
from surfgym_task.io import SeedReader
from surfgym_task.seed import CriteriaSeedTask

DATA_ROOT = Path(__file__).parents[1] / "src" / "surfgym_task" / "data"
CANONICAL_SEEDS = DATA_ROOT / "web" / "seeds"
CANONICAL_MANIFEST = (
    DATA_ROOT / "web" / "provenance" / "cua_gym_cohort42" / "manifest.json"
)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _aggregate_seed_sha256(paths: list[Path]) -> str:
    hashes = "\n".join(_sha256(path) for path in sorted(paths))
    return hashlib.sha256(hashes.encode()).hexdigest()


def _seed_payload(task_id: str) -> dict[str, object]:
    return {
        "instruction": "Mark the notification as read.",
        "website": f"http://127.0.0.1:8038/?sid={task_id}",
        "domain": "web",
        "states": [
            [
                {
                    "spec": {"target": "app_state", "path": "notifications"},
                    "value": [{"id": "n1", "read": False}],
                },
                {
                    "spec": {"target": "app_state", "path": "user"},
                    "value": "u1",
                },
            ],
            [
                {
                    "spec": {
                        "query": {"collection": "notifications", "id": "n1"},
                        "path": "read",
                        "script": "state.notifications.find(x => x.id === 'n1')?.read === true",
                    },
                    "value": True,
                }
            ],
        ],
        "empty_start": False,
        "accumulation": "DELTA",
    }


def _fixture(tmp_path: Path) -> tuple[Path, Path]:
    task_id = "task-1"
    seeds_dir = tmp_path / "web" / "seeds"
    selected_seed = seeds_dir / f"cua_{task_id}.json"
    _write_json(selected_seed, _seed_payload(task_id))
    (seeds_dir / "cua_not_in_cohort.json").write_text("not json", encoding="utf-8")

    provenance_dir = tmp_path / "provenance"
    cohort_path = provenance_dir / "cohort.json"
    fragment_path = provenance_dir / "predicate-fragments" / "mail.json"
    _write_json(cohort_path, {"schema_version": 1, "task_ids": [task_id]})
    _write_json(
        fragment_path,
        {
            "version": 1,
            "tasks": [
                {
                    "task_id": task_id,
                    "atoms": [
                        {
                            "id": "notification_read",
                            "spec": {
                                "query": {"collection": "notifications", "id": "n1"},
                                "path": "read",
                                "script": (
                                    "state.notifications.find(x => x.id === 'n1')?.read === true"
                                ),
                            },
                            "value": True,
                        }
                    ],
                }
            ],
        },
    )
    manifest_path = provenance_dir / "manifest.json"
    _write_json(
        manifest_path,
        {
            "version": 1,
            "cohort": "test-cohort",
            "status": "PUBLISHED",
            "source": {
                "cohort": {"path": "cohort.json", "sha256": _sha256(cohort_path)},
                "import_verification_sha256": "0" * 64,
                "predicate_fragments": [
                    {
                        "path": "predicate-fragments/mail.json",
                        "sha256": _sha256(fragment_path),
                    }
                ],
            },
            "counts": {
                "tasks": 1,
                "initial_atoms": 2,
                "terminal_criteria": 1,
                "apps": {"MAIL": 1},
            },
            "aggregate_seed_sha256": _aggregate_seed_sha256([selected_seed]),
            "tasks": [
                {
                    "source_task_id": task_id,
                    "seed": selected_seed.name,
                    "app_key": "MAIL",
                    "source_task_name": "mail_basic_001",
                    "seed_sha256": _sha256(selected_seed),
                    "initial_atoms": 2,
                    "terminal_criteria": 1,
                }
            ],
        },
    )
    return manifest_path, seeds_dir


def test_manifest_selects_exact_cohort_without_prefix_glob(tmp_path: Path) -> None:
    manifest_path, seeds_dir = _fixture(tmp_path)

    summary = verify_published_state_seeds(
        manifest_path=manifest_path,
        seeds_dir=seeds_dir,
    )

    assert summary.task_count == 1
    assert summary.initial_atom_count == 2
    assert summary.terminal_criteria_count == 1
    assert summary.seed_names == ("cua_task-1",)


def test_rejects_selected_seed_hash_drift(tmp_path: Path) -> None:
    manifest_path, seeds_dir = _fixture(tmp_path)
    selected_seed = seeds_dir / "cua_task-1.json"
    selected_seed.write_text(selected_seed.read_text(encoding="utf-8") + " ", encoding="utf-8")

    with pytest.raises(ValueError, match="seed SHA-256 mismatch"):
        verify_published_state_seeds(manifest_path=manifest_path, seeds_dir=seeds_dir)


def test_materializes_only_manifest_cohort(tmp_path: Path) -> None:
    manifest_path, seeds_dir = _fixture(tmp_path)
    output_root = tmp_path / "materialized"

    summary = materialize_published_state_seeds(
        manifest_path=manifest_path,
        seeds_dir=seeds_dir,
        output_root=output_root,
    )

    assert summary.task_count == 1
    assert [path.name for path in (output_root / "seeds").iterdir()] == ["cua_task-1.json"]
    assert (output_root / "projection-verification.json").is_file()


def test_published_cohort_has_expected_contract_and_hashes() -> None:
    summary = verify_published_state_seeds(
        manifest_path=CANONICAL_MANIFEST,
        seeds_dir=CANONICAL_SEEDS,
    )

    assert summary.task_count == 42
    assert summary.initial_atom_count == 366
    assert summary.terminal_criteria_count == 157
    assert summary.aggregate_seed_sha256 == (
        "b9a34c451ce7577b16d05fb3adf7b7583e5c3e309a4684881cb18a50e7022fa1"
    )
    assert len(summary.seed_names) == len(set(summary.seed_names)) == 42
    assert not (DATA_ROOT / "web" / "out" / "tasks.sqlite3").exists()


def test_canonical_corpus_has_expected_unique_seed_and_task_totals() -> None:
    generator = HoareStateGenerator(granularity="COARSE")
    seed_count = 0
    task_ids: list[str] = []
    for domain_dir in sorted(DATA_ROOT.iterdir()):
        seeds_dir = domain_dir / "seeds"
        if not seeds_dir.is_dir():
            continue
        entries = list(SeedReader(seeds_dir).get_seed())
        seed_count += len(entries)
        for seed, seed_name in entries:
            if isinstance(seed, CriteriaSeedTask):
                task_ids.extend(
                    f"{seed_name}_{window.origin_start_idx}_{window.origin_end_idx}"
                    for window in generator.generate(seed)
                )
            else:
                task_ids.append(seed_name)

    assert seed_count == 401
    assert len(task_ids) == len(set(task_ids)) == 502
