import hashlib
import json
import subprocess
from pathlib import Path

import pytest
from surfgym_task.cua import onboarding
from surfgym_task.cua.webapp_manifest import CUA_GYM_HUB_REVISION


def _sha256(path: Path) -> str:
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _write_patch_manifest(
    repo_root: Path,
    *,
    app_dir: str = "instagram_mock",
    path: str = "src/App.jsx",
    upstream_sha256: str,
    vendored_sha256: str,
    category: str = "functional",
) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": 1,
        "hash_algorithm": "sha256-lf-v1",
        "upstream_revision": CUA_GYM_HUB_REVISION,
        "source_commits": ["063033ca8f14907399e4297595586f8d713f51a7"],
        "task_ids": ["3355ed6f-3f01-5bf3-99ee-a2f1aaff9717"],
        "files": [
            {
                "path": path,
                "upstream_sha256": upstream_sha256,
                "vendored_sha256": vendored_sha256,
                "category": category,
                "reason": "Preserve the task-required application behavior.",
            }
        ],
    }
    manifest = repo_root / "third_party" / "cua-gym-hub" / "websites" / app_dir / "PATCHES.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    return payload


@pytest.fixture
def onboarding_tree(tmp_path: Path) -> tuple[Path, Path]:
    repo_root = tmp_path / "repo"
    upstream_root = tmp_path / "upstream"
    vendored_app = repo_root / "third_party" / "cua-gym-hub" / "websites" / "instagram_mock"
    upstream_app = upstream_root / "websites" / "instagram_mock"
    source = """
const BASE_STORAGE_KEY = 'instagram_mock_state';
const BASE_INITIAL_KEY = 'instagram_mock_initialState';
export function storageKey(sid) { return `${BASE_STORAGE_KEY}_${sid}`; }
export function initialKey(sid) { return `${BASE_INITIAL_KEY}_${sid}`; }
export const getSessionId = () => 'sid';
export async function saveState() {}
"""
    bridge = """
export async function get(spec) { return spec.$surfgym?.type === 'release'; }
export async function set(spec, value) { return value; }
window.surfgym = { get, set };
"""
    for app_root in (vendored_app, upstream_app):
        (app_root / "src" / "utils").mkdir(parents=True)
        (app_root / "src" / "utils" / "mockData.js").write_text(source, encoding="utf-8")
        (app_root / "index.html").write_text(
            '<script type="module" src="/src/main.jsx"></script>\n',
            encoding="utf-8",
        )
        (app_root / "src" / "App.jsx").write_text("export default {};\n", encoding="utf-8")
    (upstream_app / "src" / "main.jsx").write_text(
        "import React from 'react';\n",
        encoding="utf-8",
    )
    (upstream_app / "package.json").write_text(
        json.dumps({"scripts": {"build": "vite build"}}),
        encoding="utf-8",
    )
    (vendored_app / "src" / "surfgymBridge.js").write_text(bridge, encoding="utf-8")
    (vendored_app / "test").mkdir()
    (vendored_app / "test" / "surfgymBridge.test.js").write_text(
        "// bridge test\n", encoding="utf-8"
    )
    (vendored_app / "test" / "extensionLoader.mjs").write_text(
        "// focused test loader\n", encoding="utf-8"
    )
    (vendored_app / "src" / "main.jsx").write_text(
        "// import './wrong.js';\n"
        "import type { Bridge } from './types.js';\n"
        "import './surfgymBridge.js';\n"
        "import React from 'react';\n",
        encoding="utf-8",
    )
    (vendored_app / "package.json").write_text(
        json.dumps({"scripts": {"test": "node --test", "build": "vite build"}}),
        encoding="utf-8",
    )
    caddy = repo_root / "scripts" / "cua_hub_deploy" / "gen_caddyfile.py"
    caddy.parent.mkdir(parents=True)
    caddy.write_text(
        "offset_by_dir = {app.app_dir: app.hub_port_offset for app in DIRECT_WEB_APPS}\n"
        "port = start_port + offset_by_dir[app]\n",
        encoding="utf-8",
    )
    (upstream_root / "deploy-all.sh").write_text(
        "BASE_PORT=8000\nfind websites -name '*_mock' | sort\n",
        encoding="utf-8",
    )
    return repo_root, upstream_root


def _git_result(argv: list[str]) -> onboarding.CommandResult:
    if argv[:2] == ["rev-parse", "HEAD"]:
        stdout = CUA_GYM_HUB_REVISION + "\n"
    elif argv and argv[0] == "rev-parse":
        stdout = "41c8672854f0411347c5799c28f57f2c2b535fcd\n"
    elif "ls-tree" in argv:
        apps = [f"a{i:02d}_mock" for i in range(52)] + ["instagram_mock"]
        stdout = "\n".join(apps) + "\n"
    elif argv and argv[0] == "status":
        stdout = ""
    else:
        raise AssertionError(argv)
    return onboarding.CommandResult(argv=argv, returncode=0, stdout=stdout, stderr="")


def test_inspect_app_reports_pinned_static_contract(
    onboarding_tree: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root, upstream_root = onboarding_tree
    monkeypatch.setattr(onboarding, "_git", lambda root, *args: _git_result(list(args)))

    report = onboarding.inspect_app(
        app_key="INSTAGRAM",
        repo_root=repo_root,
        upstream_root=upstream_root,
    )

    assert report["status"] == "PASS", [
        check for check in report["checks"] if check["status"] == "FAIL"
    ]
    assert report["next_step"]["stage"] == "VERIFY_APP"
    assert report["next_step"]["status"] == "READY"
    assert report["provenance"]["upstream_revision_actual"] == CUA_GYM_HUB_REVISION
    assert report["provenance"]["upstream_app_tree"]["oid"] == (
        "41c8672854f0411347c5799c28f57f2c2b535fcd"
    )
    assert report["provenance"]["upstream_app_tree"]["checkout_clean"] is True
    hash_audit = report["provenance"]["vendored_hash_audit"]
    assert not hash_audit["unexpected_modified"]
    assert not hash_audit["unexpected_new"]
    assert [item["path"] for item in hash_audit["allowed_new"]] == [
        "src/surfgymBridge.js",
        "test/extensionLoader.mjs",
        "test/surfgymBridge.test.js",
    ]
    fixed_port = report["provenance"]["fixed_port"]
    assert fixed_port["declared_offset"] == 52
    assert fixed_port["computed_offset"] == 52
    assert fixed_port["port"] == 8052
    assert fixed_port["tree_listing_sha256"]


def test_inspect_app_rejects_late_bridge_import(
    onboarding_tree: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root, upstream_root = onboarding_tree
    entry = (
        repo_root
        / "third_party"
        / "cua-gym-hub"
        / "websites"
        / "instagram_mock"
        / "src"
        / "main.jsx"
    )
    entry.write_text(
        "import './not-surfgymBridge.js';\nimport './surfgymBridge.js';\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(onboarding, "_git", lambda root, *args: _git_result(list(args)))

    report = onboarding.inspect_app(
        app_key="INSTAGRAM",
        repo_root=repo_root,
        upstream_root=upstream_root,
    )

    assert report["status"] == "FAIL"
    bridge_check = next(
        check for check in report["checks"] if check["name"] == "bridge_first_import"
    )
    assert bridge_check["status"] == "FAIL"
    assert bridge_check["evidence"]["first_import"] == "./not-surfgymBridge.js"
    assert report["next_step"]["stage"] == "VERIFY_APP"
    assert report["next_step"]["status"] == "BLOCKED"


def test_inspect_app_rejects_dirty_upstream_app_path(
    onboarding_tree: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root, upstream_root = onboarding_tree

    def dirty_git(root: Path, *args: str) -> onboarding.CommandResult:
        if args and args[0] == "status":
            return onboarding.CommandResult(
                argv=list(args),
                returncode=0,
                stdout=" M websites/instagram_mock/src/App.jsx\n",
                stderr="",
            )
        return _git_result(list(args))

    monkeypatch.setattr(onboarding, "_git", dirty_git)

    report = onboarding.inspect_app(
        app_key="INSTAGRAM", repo_root=repo_root, upstream_root=upstream_root
    )

    check = next(item for item in report["checks"] if item["name"] == "upstream_app_checkout_clean")
    assert report["status"] == "FAIL"
    assert check["status"] == "FAIL"
    assert check["evidence"]["porcelain"] == [" M websites/instagram_mock/src/App.jsx"]


def test_inspect_app_rejects_non_allowlisted_vendor_differences(
    onboarding_tree: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root, upstream_root = onboarding_tree
    vendored_app = repo_root / "third_party" / "cua-gym-hub" / "websites" / "instagram_mock"
    (vendored_app / "src" / "App.jsx").write_text("changed\n", encoding="utf-8")
    (vendored_app / "src" / "extra.js").write_text("extra\n", encoding="utf-8")
    monkeypatch.setattr(onboarding, "_git", lambda root, *args: _git_result(list(args)))

    report = onboarding.inspect_app(
        app_key="INSTAGRAM", repo_root=repo_root, upstream_root=upstream_root
    )

    check = next(item for item in report["checks"] if item["name"] == "vendored_hash_audit")
    assert report["status"] == "FAIL"
    assert check["status"] == "FAIL"
    assert [item["path"] for item in check["evidence"]["unexpected_modified"]] == ["src/App.jsx"]
    assert [item["path"] for item in check["evidence"]["unexpected_new"]] == ["src/extra.js"]
    assert check["evidence"]["allowlist"]["new"] == [
        "src/surfgymBridge.js",
        "test/extensionLoader.mjs",
        "test/surfgymBridge.test.js",
    ]


def test_inspect_app_accepts_exact_audit_only_patch_provenance(
    onboarding_tree: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root, upstream_root = onboarding_tree
    vendored = (
        repo_root
        / "third_party"
        / "cua-gym-hub"
        / "websites"
        / "instagram_mock"
        / "src"
        / "App.jsx"
    )
    upstream = upstream_root / "websites" / "instagram_mock" / "src" / "App.jsx"
    vendored.write_bytes(b"export default { patched: true };\r\n")
    _write_patch_manifest(
        repo_root,
        upstream_sha256=_sha256(upstream),
        vendored_sha256=_sha256(vendored),
    )
    monkeypatch.setattr(onboarding, "_git", lambda root, *args: _git_result(list(args)))

    report = onboarding.inspect_app(
        app_key="INSTAGRAM", repo_root=repo_root, upstream_root=upstream_root
    )

    assert report["status"] == "PASS"
    patch_check = next(item for item in report["checks"] if item["name"] == "patch_manifest")
    assert patch_check["status"] == "PASS"
    assert patch_check["evidence"]["files"] == [
        {
            "path": "src/App.jsx",
            "upstream_sha256": _sha256(upstream),
            "vendored_sha256": _sha256(vendored),
            "category": "functional",
            "reason": "Preserve the task-required application behavior.",
        }
    ]
    audit = report["provenance"]["vendored_hash_audit"]
    assert [item["path"] for item in audit["allowed_exceptional_modified"]] == ["src/App.jsx"]
    assert audit["unexpected_modified"] == []


def test_inspect_app_accepts_exact_formatting_only_patch_provenance(
    onboarding_tree: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root, upstream_root = onboarding_tree
    vendored = (
        repo_root
        / "third_party"
        / "cua-gym-hub"
        / "websites"
        / "instagram_mock"
        / "src"
        / "App.jsx"
    )
    upstream = upstream_root / "websites" / "instagram_mock" / "src" / "App.jsx"
    vendored.write_text("export  default {};\n", encoding="utf-8")
    _write_patch_manifest(
        repo_root,
        upstream_sha256=_sha256(upstream),
        vendored_sha256=_sha256(vendored),
        category="formatting_only",
    )
    monkeypatch.setattr(onboarding, "_git", lambda root, *args: _git_result(list(args)))

    report = onboarding.inspect_app(
        app_key="INSTAGRAM", repo_root=repo_root, upstream_root=upstream_root
    )

    assert report["status"] == "PASS"


@pytest.mark.parametrize(
    "case",
    [
        "extra_root_field",
        "wrong_schema",
        "boolean_schema",
        "wrong_revision",
        "wrong_hash_algorithm",
        "short_source_commit",
        "invalid_task_id",
        "duplicate_source_commit",
        "duplicate_task_id",
        "extra_file_field",
        "missing_file_field",
        "unknown_file",
        "wrong_upstream_hash",
        "wrong_vendored_hash",
        "wrong_category",
        "empty_reason",
        "control_reason",
        "self_path",
        "generic_overlap",
        "duplicate_file",
        "unchanged_file",
    ],
)
def test_inspect_app_rejects_malformed_or_inexact_patch_provenance(
    onboarding_tree: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    repo_root, upstream_root = onboarding_tree
    vendored = (
        repo_root
        / "third_party"
        / "cua-gym-hub"
        / "websites"
        / "instagram_mock"
        / "src"
        / "App.jsx"
    )
    upstream = upstream_root / "websites" / "instagram_mock" / "src" / "App.jsx"
    vendored.write_bytes(b"export default { patched: true };\r\n")
    payload = _write_patch_manifest(
        repo_root,
        upstream_sha256=_sha256(upstream),
        vendored_sha256=_sha256(vendored),
    )
    files = payload["files"]
    assert isinstance(files, list)
    file_record = files[0]
    assert isinstance(file_record, dict)
    if case == "extra_root_field":
        payload["unexpected"] = True
    elif case == "wrong_schema":
        payload["schema_version"] = 2
    elif case == "boolean_schema":
        payload["schema_version"] = True
    elif case == "wrong_revision":
        payload["upstream_revision"] = "0" * 40
    elif case == "wrong_hash_algorithm":
        payload["hash_algorithm"] = "sha256"
    elif case == "short_source_commit":
        payload["source_commits"] = ["063033c"]
    elif case == "invalid_task_id":
        payload["task_ids"] = [""]
    elif case == "duplicate_source_commit":
        payload["source_commits"] = [
            "063033ca8f14907399e4297595586f8d713f51a7",
            "063033ca8f14907399e4297595586f8d713f51a7",
        ]
    elif case == "duplicate_task_id":
        payload["task_ids"] = [
            "prepare_instacart_health_items_order",
            "prepare_instacart_health_items_order",
        ]
    elif case == "extra_file_field":
        file_record["unexpected"] = True
    elif case == "missing_file_field":
        del file_record["vendored_sha256"]
    elif case == "unknown_file":
        file_record["path"] = "src/unknown.jsx"
    elif case == "wrong_upstream_hash":
        file_record["upstream_sha256"] = "0" * 64
    elif case == "wrong_vendored_hash":
        file_record["vendored_sha256"] = "0" * 64
    elif case == "wrong_category":
        file_record["category"] = "runtime_axis"
    elif case == "empty_reason":
        file_record["reason"] = "   "
    elif case == "control_reason":
        file_record["reason"] = "bad\nreason"
    elif case == "self_path":
        file_record["path"] = "PATCHES.json"
    elif case == "generic_overlap":
        generic_upstream = upstream_root / "websites" / "instagram_mock" / "package.json"
        generic_vendored = (
            repo_root
            / "third_party"
            / "cua-gym-hub"
            / "websites"
            / "instagram_mock"
            / "package.json"
        )
        file_record.update(
            {
                "path": "package.json",
                "upstream_sha256": _sha256(generic_upstream),
                "vendored_sha256": _sha256(generic_vendored),
                "category": "package_dependency",
            }
        )
    elif case == "duplicate_file":
        files.append(dict(file_record))
    elif case == "unchanged_file":
        unchanged = upstream_root / "websites" / "instagram_mock" / "index.html"
        file_record.update(
            {
                "path": "index.html",
                "upstream_sha256": _sha256(unchanged),
                "vendored_sha256": _sha256(
                    repo_root
                    / "third_party"
                    / "cua-gym-hub"
                    / "websites"
                    / "instagram_mock"
                    / "index.html"
                ),
            }
        )
    manifest = (
        repo_root / "third_party" / "cua-gym-hub" / "websites" / "instagram_mock" / "PATCHES.json"
    )
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(onboarding, "_git", lambda root, *args: _git_result(list(args)))

    report = onboarding.inspect_app(
        app_key="INSTAGRAM", repo_root=repo_root, upstream_root=upstream_root
    )

    assert report["status"] == "FAIL"
    patch_check = next(item for item in report["checks"] if item["name"] == "patch_manifest")
    assert patch_check["status"] == "FAIL"
    assert patch_check["evidence"]["errors"]


@pytest.mark.parametrize(
    "raw_manifest, expected_error",
    [
        ('{"schema_version":1,"schema_version":1}', "duplicate"),
        ('{"schema_version":', "Expecting value"),
    ],
)
def test_inspect_app_rejects_malformed_json(
    onboarding_tree: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    raw_manifest: str,
    expected_error: str,
) -> None:
    repo_root, upstream_root = onboarding_tree
    manifest = (
        repo_root / "third_party" / "cua-gym-hub" / "websites" / "instagram_mock" / "PATCHES.json"
    )
    manifest.write_text(raw_manifest, encoding="utf-8")
    monkeypatch.setattr(onboarding, "_git", lambda root, *args: _git_result(list(args)))

    report = onboarding.inspect_app(
        app_key="INSTAGRAM", repo_root=repo_root, upstream_root=upstream_root
    )

    check = next(item for item in report["checks"] if item["name"] == "patch_manifest")
    assert report["status"] == "FAIL"
    assert check["status"] == "FAIL"
    assert any(expected_error in error for error in check["evidence"]["errors"])


def test_patch_allowance_does_not_leak_to_another_app(
    onboarding_tree: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root, upstream_root = onboarding_tree
    vendored = (
        repo_root
        / "third_party"
        / "cua-gym-hub"
        / "websites"
        / "instagram_mock"
        / "src"
        / "App.jsx"
    )
    upstream = upstream_root / "websites" / "instagram_mock" / "src" / "App.jsx"
    vendored.write_text("export default { patched: true };\n", encoding="utf-8")
    _write_patch_manifest(
        repo_root,
        app_dir="instacart_mock",
        upstream_sha256=_sha256(upstream),
        vendored_sha256=_sha256(vendored),
    )
    monkeypatch.setattr(onboarding, "_git", lambda root, *args: _git_result(list(args)))

    report = onboarding.inspect_app(
        app_key="INSTAGRAM", repo_root=repo_root, upstream_root=upstream_root
    )

    assert report["status"] == "FAIL"
    audit = report["provenance"]["vendored_hash_audit"]
    assert [item["path"] for item in audit["unexpected_modified"]] == ["src/App.jsx"]


def test_tree_audit_canonicalizes_text_line_endings(
    onboarding_tree: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root, upstream_root = onboarding_tree
    vendored_index = (
        repo_root / "third_party" / "cua-gym-hub" / "websites" / "instagram_mock" / "index.html"
    )
    original = vendored_index.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    vendored_index.write_bytes(original.replace(b"\n", b"\r\n"))
    monkeypatch.setattr(onboarding, "_git", lambda root, *args: _git_result(list(args)))

    report = onboarding.inspect_app(
        app_key="INSTAGRAM", repo_root=repo_root, upstream_root=upstream_root
    )

    assert report["provenance"]["vendored_hash_audit"]["unexpected_modified"] == []
    assert report["status"] == "PASS", [
        check for check in report["checks"] if check["status"] == "FAIL"
    ]
    assert report["provenance"]["vendored_hash_audit"]["hash_algorithm"] == (
        "sha256-lf-v1 for UTF-8 text; sha256-raw-v1 otherwise"
    )


def test_tree_audit_keeps_binary_differences_byte_exact(
    onboarding_tree: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root, upstream_root = onboarding_tree
    vendored_app = repo_root / "third_party" / "cua-gym-hub" / "websites" / "instagram_mock"
    upstream_app = upstream_root / "websites" / "instagram_mock"
    (vendored_app / "public").mkdir()
    (upstream_app / "public").mkdir()
    (vendored_app / "public" / "logo.bin").write_bytes(b"\xff\x00vendored")
    (upstream_app / "public" / "logo.bin").write_bytes(b"\xff\x00upstream")
    monkeypatch.setattr(onboarding, "_git", lambda root, *args: _git_result(list(args)))

    report = onboarding.inspect_app(
        app_key="INSTAGRAM", repo_root=repo_root, upstream_root=upstream_root
    )

    assert report["status"] == "FAIL"
    audit = report["provenance"]["vendored_hash_audit"]
    assert [item["path"] for item in audit["unexpected_modified"]] == ["public/logo.bin"]


def test_inspect_app_allows_nonruntime_omissions_but_rejects_runtime_omissions(
    onboarding_tree: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root, upstream_root = onboarding_tree
    upstream_app = upstream_root / "websites" / "instagram_mock"
    (upstream_app / "tests").mkdir()
    (upstream_app / "tests" / "headed.spec.js").write_text(
        "// upstream-only test\n", encoding="utf-8"
    )
    (upstream_app / "tests" / "screenshots").mkdir()
    (upstream_app / "tests" / "screenshots" / "final.png").write_bytes(b"png")
    (upstream_app / "src" / "runtimeOnly.js").write_text(
        "export const required = true;\n", encoding="utf-8"
    )
    monkeypatch.setattr(onboarding, "_git", lambda root, *args: _git_result(list(args)))

    report = onboarding.inspect_app(
        app_key="INSTAGRAM", repo_root=repo_root, upstream_root=upstream_root
    )

    check = next(item for item in report["checks"] if item["name"] == "vendored_hash_audit")
    assert report["status"] == "FAIL"
    assert check["status"] == "FAIL"
    assert check["evidence"]["allowed_upstream_only"] == [
        "tests/headed.spec.js",
        "tests/screenshots/final.png",
    ]
    assert check["evidence"]["unexpected_upstream_only"] == ["src/runtimeOnly.js"]


def test_inspect_app_reports_non_object_package_scripts_as_failure(
    onboarding_tree: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root, upstream_root = onboarding_tree
    package_json = (
        repo_root / "third_party" / "cua-gym-hub" / "websites" / "instagram_mock" / "package.json"
    )
    package_json.write_text(json.dumps({"scripts": []}), encoding="utf-8")
    monkeypatch.setattr(onboarding, "_git", lambda root, *args: _git_result(list(args)))

    report = onboarding.inspect_app(
        app_key="INSTAGRAM", repo_root=repo_root, upstream_root=upstream_root
    )

    check = next(item for item in report["checks"] if item["name"] == "package_scripts")
    assert report["status"] == "FAIL"
    assert check["status"] == "FAIL"
    assert check["detail"] == "package.json scripts must be an object"


def test_verify_app_keeps_unit_static_and_build_separate(
    onboarding_tree: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root, upstream_root = onboarding_tree
    monkeypatch.setattr(onboarding, "_git", lambda root, *args: _git_result(list(args)))
    commands: list[list[str]] = []

    def fake_run(
        argv: tuple[str, ...], *, cwd: Path, timeout_seconds: float
    ) -> onboarding.CommandResult:
        commands.append(list(argv))
        return onboarding.CommandResult(argv=list(argv), returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(onboarding, "_run_process", fake_run)
    monkeypatch.setattr(onboarding, "_npm_executable", lambda: "npm")

    report = onboarding.verify_app(
        app_key="INSTAGRAM",
        repo_root=repo_root,
        upstream_root=upstream_root,
        run_unit=True,
        run_build=True,
        timeout_seconds=45,
    )

    assert report["status"] == "PASS"
    assert report["stages"]["STATIC"]["status"] == "PASS"
    assert report["stages"]["UNIT"]["status"] == "PASS"
    assert report["stages"]["BUILD"]["status"] == "PASS"
    assert commands == [["npm", "test"], ["npm", "run", "build"]]
    assert report["next_step"]["stage"] == "TASK_IMPORT"
    assert "PROMOTABLE" not in json.dumps(report)
    assert "HEADED" not in json.dumps(report)


def test_verify_app_is_incomplete_when_unit_or_build_is_skipped(
    onboarding_tree: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root, upstream_root = onboarding_tree
    monkeypatch.setattr(onboarding, "_git", lambda root, *args: _git_result(list(args)))

    report = onboarding.verify_app(
        app_key="INSTAGRAM",
        repo_root=repo_root,
        upstream_root=upstream_root,
    )

    assert report["stages"]["INSPECT"]["status"] == "PASS"
    assert report["stages"]["STATIC"]["status"] == "PASS"
    assert report["stages"]["UNIT"]["status"] == "SKIPPED"
    assert report["stages"]["BUILD"]["status"] == "SKIPPED"
    assert report["status"] == "INCOMPLETE"
    assert report["next_step"]["status"] == "BLOCKED"
    assert (
        onboarding.main(
            [
                "verify-app",
                "--app-key",
                "INSTAGRAM",
                "--repo-root",
                str(repo_root),
                "--upstream-root",
                str(upstream_root),
            ]
        )
        == 1
    )


def test_process_runner_uses_argv_timeout_and_no_shell(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    observed: dict[str, object] = {}

    def fake_subprocess_run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        observed["argv"] = argv
        observed.update(kwargs)
        return subprocess.CompletedProcess(argv, 0, stdout="done", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_subprocess_run)

    result = onboarding._run_process(["npm", "test"], cwd=tmp_path, timeout_seconds=17)

    assert result.ok
    assert observed["argv"] == ["npm", "test"]
    assert observed["timeout"] == 17
    assert observed["shell"] is False
    assert observed["check"] is False
    assert observed["encoding"] == "utf-8"
    assert observed["errors"] == "replace"


def test_cli_returns_nonzero_and_writes_json_on_failure(
    onboarding_tree: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    repo_root, upstream_root = onboarding_tree
    monkeypatch.setattr(
        onboarding,
        "_git",
        lambda root, *args: onboarding.CommandResult(
            argv=list(args), returncode=1, stdout="", stderr="bad revision"
        ),
    )
    json_out = tmp_path / "report.json"

    exit_code = onboarding.main(
        [
            "inspect-app",
            "--app-key",
            "INSTAGRAM",
            "--repo-root",
            str(repo_root),
            "--upstream-root",
            str(upstream_root),
            "--json-out",
            str(json_out),
        ]
    )

    assert exit_code == 1
    assert json.loads(json_out.read_text(encoding="utf-8"))["status"] == "FAIL"
