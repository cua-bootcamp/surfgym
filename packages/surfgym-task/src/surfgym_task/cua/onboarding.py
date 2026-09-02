"""Read-only inspection and verification for registered CUA direct-web apps."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass
from fnmatch import fnmatchcase
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from typing import Any, Sequence
from urllib.parse import urlsplit

from surfgym_task.cua.app_registry import normalize_key
from surfgym_task.cua.webapp_manifest import (
    CUA_GYM_HUB_LICENSE,
    CUA_GYM_HUB_REVISION,
    CUA_GYM_HUB_URL,
    DIRECT_WEB_APPS,
    CuaWebApp,
    get_direct_web_app,
)

DEFAULT_COMMAND_TIMEOUT_SECONDS = 120.0
DEFAULT_CADDY_START_PORT = 8000
REPORT_SCHEMA_VERSION = 1
PATCH_MANIFEST_SCHEMA_VERSION = 1

_REQUIRED_HELPERS = ("getSessionId", "storageKey", "initialKey", "saveState")
_EXPORT_PATTERN = (
    r"\bexport\s+(?:(?:const|let|var)\s+{name}\b|(?:async\s+)?function\s+{name}\b|"
    r"\{{[^}}]*\b{name}\b[^}}]*\}})"
)
_GENERATED_DIRS = frozenset({"node_modules", "dist", ".mock-files", ".mock-states"})
_ALLOWED_NEW_PATHS = frozenset(
    {
        "src/surfgymBridge.js",
        "test/extensionLoader.mjs",
        "test/surfgymBridge.test.js",
    }
)
_ALLOWED_UPSTREAM_ONLY_FILES = frozenset(
    {
        ".gitignore",
        "API.md",
        "DESIGN.md",
        "README.md",
        "SCHEMA.md",
        "TODO.md",
        "playwright.config.js",
        "playwright.config.ts",
    }
)
_ALLOWED_UPSTREAM_ONLY_ROOT_GLOBS = frozenset(
    {
        "debug*.cjs",
        "take_*screenshots.mjs",
        "test*.cjs",
    }
)
_ALLOWED_UPSTREAM_ONLY_PREFIXES = ("tests/",)
_RUNTIME_IMPORT_PATTERN = re.compile(
    r"(?ms)^[ \t]*import[ \t]+(?!type\b)(?:"
    r"(?P<side_quote>['\"])(?P<side>[^'\"]+)(?P=side_quote)|"
    r"(?:(?!;).)*?\bfrom[ \t]*(?P<from_quote>['\"])(?P<from>[^'\"]+)(?P=from_quote)"
    r")"
)
_FULL_COMMIT_PATTERN = re.compile(r"[0-9a-f]{40}\Z")
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
_PATCH_CATEGORIES = frozenset(
    {
        "build_chain",
        "formatting_only",
        "functional",
        "package_dependency",
    }
)
_PATCH_ROOT_FIELDS = frozenset(
    {
        "schema_version",
        "hash_algorithm",
        "upstream_revision",
        "source_commits",
        "task_ids",
        "files",
    }
)
_PATCH_FILE_FIELDS = frozenset({"path", "upstream_sha256", "vendored_sha256", "category", "reason"})


@dataclass(frozen=True)
class CommandResult:
    argv: list[str]
    returncode: int | None
    stdout: str
    stderr: str
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out


class _ModuleScriptParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.sources: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "script":
            return
        attributes = {name.lower(): value for name, value in attrs}
        if attributes.get("type", "").lower() == "module" and attributes.get("src"):
            self.sources.append(attributes["src"] or "")


def _run_process(
    argv: Sequence[str],
    *,
    cwd: Path,
    timeout_seconds: float,
) -> CommandResult:
    command = list(argv)
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            shell=False,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return CommandResult(
            argv=command,
            returncode=None,
            stdout=_text(exc.stdout),
            stderr=_text(exc.stderr) or f"timed out after {timeout_seconds:g}s",
            timed_out=True,
        )
    except OSError as exc:
        return CommandResult(
            argv=command,
            returncode=None,
            stdout="",
            stderr=str(exc),
        )
    return CommandResult(
        argv=command,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def _text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    return value.decode(errors="replace") if isinstance(value, bytes) else value


def _check(name: str, passed: bool, detail: str, **evidence: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "name": name,
        "status": "PASS" if passed else "FAIL",
        "detail": detail,
    }
    if evidence:
        result["evidence"] = evidence
    return result


def _sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _utf8_text(path: Path) -> str | None:
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None
    if any(ord(char) < 32 and char not in "\t\n\r" for char in text):
        return None
    return text


def _sha256_lf(path: Path) -> str | None:
    text = _utf8_text(path)
    if text is None:
        return None
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _portable_tree_sha256(path: Path) -> str | None:
    return _sha256_lf(path) or _sha256(path)


def _entry_from_index(app_root: Path) -> tuple[Path | None, str | None]:
    index = app_root / "index.html"
    if not index.is_file():
        return None, None
    parser = _ModuleScriptParser()
    parser.feed(index.read_text(encoding="utf-8"))
    for source in parser.sources:
        path = urlsplit(source).path
        if path.startswith("/"):
            path = path[1:]
        elif path.startswith("./"):
            path = path[2:]
        candidate = app_root / Path(path)
        if candidate.is_file():
            return candidate, source
    return None, parser.sources[0] if parser.sources else None


def _strip_js_comments(source: str) -> str:
    output: list[str] = []
    state = "code"
    escaped = False
    index = 0
    while index < len(source):
        char = source[index]
        next_char = source[index + 1] if index + 1 < len(source) else ""
        if state == "line_comment":
            if char == "\n":
                output.append(char)
                state = "code"
            else:
                output.append(" ")
        elif state == "block_comment":
            if char == "*" and next_char == "/":
                output.extend((" ", " "))
                index += 1
                state = "code"
            else:
                output.append("\n" if char == "\n" else " ")
        elif state == "code":
            if char == "/" and next_char == "/":
                output.extend((" ", " "))
                index += 1
                state = "line_comment"
            elif char == "/" and next_char == "*":
                output.extend((" ", " "))
                index += 1
                state = "block_comment"
            else:
                output.append(char)
                if char == "'":
                    state = "single_quote"
                elif char == '"':
                    state = "double_quote"
                elif char == "`":
                    state = "template"
        else:
            output.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif (
                (state == "single_quote" and char == "'")
                or (state == "double_quote" and char == '"')
                or (state == "template" and char == "`")
            ):
                state = "code"
        index += 1
    return "".join(output)


def _runtime_imports(entry_text: str) -> list[str]:
    source = _strip_js_comments(entry_text)
    return [
        match.group("side") or match.group("from")
        for match in _RUNTIME_IMPORT_PATTERN.finditer(source)
    ]


def _tree_hashes(root: Path) -> dict[str, str]:
    if not root.is_dir():
        return {}
    hashes: dict[str, str] = {}
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if any(part in _GENERATED_DIRS for part in relative.parts):
            continue
        if relative.as_posix() == "PATCHES.json":
            continue
        if path.is_file():
            digest = _portable_tree_sha256(path)
            if digest is not None:
                hashes[relative.as_posix()] = digest
    return hashes


def _is_allowed_upstream_only(path: str) -> bool:
    if path in _ALLOWED_UPSTREAM_ONLY_FILES:
        return True
    if path.startswith(_ALLOWED_UPSTREAM_ONLY_PREFIXES):
        return True
    return "/" not in path and any(
        fnmatchcase(path, pattern) for pattern in _ALLOWED_UPSTREAM_ONLY_ROOT_GLOBS
    )


def _exact_fields(value: dict[str, Any], expected: frozenset[str], label: str) -> list[str]:
    actual = set(value)
    errors: list[str] = []
    if missing := sorted(expected - actual):
        errors.append(f"{label} is missing fields: {', '.join(missing)}")
    if extra := sorted(actual - expected):
        errors.append(f"{label} has unknown fields: {', '.join(extra)}")
    return errors


def _bounded_text(value: Any, *, maximum: int) -> bool:
    return (
        isinstance(value, str)
        and 0 < len(value) <= maximum
        and bool(value.strip())
        and all(ord(char) >= 32 and ord(char) != 127 for char in value)
    )


def _safe_patch_path(value: Any) -> str | None:
    if (
        not _bounded_text(value, maximum=256)
        or "\\" in value
        or ":" in value
        or value.casefold() == "patches.json"
    ):
        return None
    candidate = PurePosixPath(value)
    if candidate.is_absolute() or any(part in {"", ".", ".."} for part in candidate.parts):
        return None
    return candidate.as_posix() if candidate.as_posix() == value else None


def _patch_manifest_for_app(
    *,
    vendored_app: Path,
    upstream_app: Path,
    generic_modified_paths: set[str],
) -> tuple[bool, dict[str, Any], dict[str, dict[str, str]]]:
    manifest_path = vendored_app / "PATCHES.json"
    if not manifest_path.is_file():
        return True, {"path": str(manifest_path), "files": [], "errors": []}, {}

    errors: list[str] = []
    selected_files: list[dict[str, str]] = []

    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON object key: {key}")
            result[key] = value
        return result

    try:
        raw = json.loads(
            manifest_path.read_text(encoding="utf-8"),
            object_pairs_hook=reject_duplicate_keys,
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return False, {"path": str(manifest_path), "files": [], "errors": [str(exc)]}, {}
    if not isinstance(raw, dict):
        return (
            False,
            {
                "path": str(manifest_path),
                "files": [],
                "errors": ["patch manifest root must be an object"],
            },
            {},
        )
    label = "patch manifest root"
    errors.extend(_exact_fields(raw, _PATCH_ROOT_FIELDS, label))
    if (
        type(raw.get("schema_version")) is not int
        or raw.get("schema_version") != PATCH_MANIFEST_SCHEMA_VERSION
    ):
        errors.append(f"schema_version must be {PATCH_MANIFEST_SCHEMA_VERSION}")
    if raw.get("hash_algorithm") != "sha256-lf-v1":
        errors.append("hash_algorithm must be sha256-lf-v1")
    if raw.get("upstream_revision") != CUA_GYM_HUB_REVISION:
        errors.append(f"upstream_revision must be {CUA_GYM_HUB_REVISION}")
    source_commits = raw.get("source_commits")
    if (
        not isinstance(source_commits, list)
        or not source_commits
        or any(
            not isinstance(commit, str) or _FULL_COMMIT_PATTERN.fullmatch(commit) is None
            for commit in source_commits
        )
        or len(source_commits) != len(set(source_commits))
    ):
        errors.append("source_commits must contain unique full commit hashes")
    task_ids = raw.get("task_ids")
    if (
        not isinstance(task_ids, list)
        or not task_ids
        or any(not _bounded_text(task_id, maximum=256) for task_id in task_ids)
        or len(task_ids) != len(set(task_ids))
    ):
        errors.append("task_ids must contain unique bounded task identifiers")

    files = raw.get("files")
    if not isinstance(files, list) or not files:
        errors.append("files must be a non-empty array")
        files = []
    selected_records: dict[str, dict[str, str]] = {}
    seen_paths: set[str] = set()
    for file_index, record in enumerate(files):
        file_label = f"files[{file_index}]"
        if not isinstance(record, dict):
            errors.append(f"{file_label} must be an object")
            continue
        errors.extend(_exact_fields(record, _PATCH_FILE_FIELDS, file_label))
        path = _safe_patch_path(record.get("path"))
        if path is None:
            errors.append(f"{file_label}.path must be a normalized relative POSIX path")
            continue
        if any(part in _GENERATED_DIRS for part in PurePosixPath(path).parts):
            errors.append(f"{file_label}.path cannot name a generated file")
        if path in seen_paths:
            errors.append(f"{file_label}.path duplicates {path}")
        seen_paths.add(path)
        if path in generic_modified_paths:
            errors.append(f"{file_label}.path overlaps the generic onboarding allowance: {path}")
        upstream_hash = record.get("upstream_sha256")
        vendored_hash = record.get("vendored_sha256")
        if not isinstance(upstream_hash, str) or _SHA256_PATTERN.fullmatch(upstream_hash) is None:
            errors.append(f"{file_label}.upstream_sha256 must be a lowercase SHA-256")
        if not isinstance(vendored_hash, str) or _SHA256_PATTERN.fullmatch(vendored_hash) is None:
            errors.append(f"{file_label}.vendored_sha256 must be a lowercase SHA-256")
        category = record.get("category")
        if not _bounded_text(category, maximum=64) or category not in _PATCH_CATEGORIES:
            errors.append(f"{file_label}.category is not recognized")
        if not _bounded_text(record.get("reason"), maximum=512):
            errors.append(f"{file_label}.reason must be bounded non-empty text")
        selected_files.append(record)
        selected_records[path] = record

    errors.extend(
        _validate_selected_patch_files(
            records=selected_records,
            vendored_app=vendored_app,
            upstream_app=upstream_app,
        )
    )

    evidence = {
        "path": str(manifest_path),
        "schema_version": raw.get("schema_version"),
        "hash_algorithm": raw.get("hash_algorithm"),
        "upstream_revision": raw.get("upstream_revision"),
        "files": selected_files,
        "errors": errors,
    }
    return not errors, evidence, selected_records


def _validate_selected_patch_files(
    *,
    records: dict[str, dict[str, str]],
    vendored_app: Path,
    upstream_app: Path,
) -> list[str]:
    def normalized_hash(path: Path) -> str | None:
        return _sha256_lf(path)

    errors: list[str] = []
    for path, record in records.items():
        upstream_actual = normalized_hash(upstream_app / Path(path))
        vendored_actual = normalized_hash(vendored_app / Path(path))
        if upstream_actual is None or vendored_actual is None:
            errors.append(f"{path} must exist in both upstream and vendored trees")
            continue
        if upstream_actual != record.get("upstream_sha256"):
            errors.append(f"{path} upstream_sha256 does not match the pinned checkout")
        if vendored_actual != record.get("vendored_sha256"):
            errors.append(f"{path} vendored_sha256 does not match the vendored file")
        if upstream_actual == vendored_actual:
            errors.append(f"{path} is unchanged and cannot be an exceptional patch")
    return errors


def _vendored_hash_audit(
    *,
    vendored_app: Path,
    upstream_app: Path,
    state_source: Path,
    entry: Path | None,
    exceptional_modified: dict[str, dict[str, str]] | None = None,
) -> tuple[bool, dict[str, Any]]:
    vendored = _tree_hashes(vendored_app)
    upstream = _tree_hashes(upstream_app)
    allowed_modified = {
        state_source.relative_to(vendored_app).as_posix(),
        "package.json",
    }
    if entry is not None:
        allowed_modified.add(entry.relative_to(vendored_app).as_posix())

    exceptional_modified = exceptional_modified or {}
    common = sorted(set(vendored) & set(upstream))
    changed = [path for path in common if vendored[path] != upstream[path]]
    allowed_exceptional = sorted(path for path in changed if path in exceptional_modified)
    allowed_changed = sorted(
        path for path in changed if path in allowed_modified and path not in exceptional_modified
    )
    unexpected_changed = sorted(
        path
        for path in changed
        if path not in allowed_modified and path not in exceptional_modified
    )
    new_paths = sorted(set(vendored) - set(upstream))
    allowed_new = sorted(path for path in new_paths if path in _ALLOWED_NEW_PATHS)
    unexpected_new = sorted(path for path in new_paths if path not in _ALLOWED_NEW_PATHS)
    upstream_only = sorted(set(upstream) - set(vendored))
    allowed_upstream_only = sorted(
        path for path in upstream_only if _is_allowed_upstream_only(path)
    )
    unexpected_upstream_only = sorted(set(upstream_only) - set(allowed_upstream_only))

    def hashes(paths: list[str]) -> list[dict[str, str]]:
        return [
            {
                "path": path,
                "upstream_sha256": upstream[path],
                "vendored_sha256": vendored[path],
            }
            for path in paths
        ]

    evidence: dict[str, Any] = {
        "hash_algorithm": "sha256-lf-v1 for UTF-8 text; sha256-raw-v1 otherwise",
        "excluded_directories": sorted(_GENERATED_DIRS),
        "excluded_audit_metadata": ["PATCHES.json"],
        "allowlist": {
            "modified": sorted(allowed_modified),
            "new": sorted(_ALLOWED_NEW_PATHS),
            "upstream_only_files": sorted(_ALLOWED_UPSTREAM_ONLY_FILES),
            "upstream_only_root_globs": sorted(_ALLOWED_UPSTREAM_ONLY_ROOT_GLOBS),
            "upstream_only_prefixes": list(_ALLOWED_UPSTREAM_ONLY_PREFIXES),
        },
        "common_file_count": len(common),
        "allowed_modified": hashes(allowed_changed),
        "allowed_exceptional_modified": hashes(allowed_exceptional),
        "unexpected_modified": hashes(unexpected_changed),
        "allowed_new": [{"path": path, "vendored_sha256": vendored[path]} for path in allowed_new],
        "unexpected_new": [
            {"path": path, "vendored_sha256": vendored[path]} for path in unexpected_new
        ],
        "allowed_upstream_only": allowed_upstream_only,
        "unexpected_upstream_only": unexpected_upstream_only,
    }
    return (
        not unexpected_changed and not unexpected_new and not unexpected_upstream_only
    ), evidence


def _git(upstream_root: Path, *args: str) -> CommandResult:
    return _run_process(
        (
            "git",
            "-c",
            f"safe.directory={upstream_root.as_posix()}",
            "-C",
            str(upstream_root),
            *args,
        ),
        cwd=upstream_root,
        timeout_seconds=30.0,
    )


def _manifest_app(app_key: str) -> tuple[CuaWebApp | None, dict[str, Any]]:
    normalized = normalize_key(app_key)
    try:
        app = get_direct_web_app(normalized)
    except ValueError as exc:
        return None, _check("manifest_registration", False, str(exc), app_key=normalized)
    return app, _check(
        "manifest_registration",
        True,
        f"{normalized} is registered as {app.app_dir}",
        app_key=normalized,
        app_dir=app.app_dir,
    )


def inspect_app(*, app_key: str, repo_root: Path, upstream_root: Path) -> dict[str, Any]:
    """Inspect one manifest-listed app without modifying either checkout."""
    repo_root = repo_root.resolve()
    upstream_root = upstream_root.resolve()
    checks: list[dict[str, Any]] = []

    app, registration = _manifest_app(app_key)
    checks.append(registration)
    if app is None:
        return _report(
            command="inspect-app",
            app_key=normalize_key(app_key),
            checks=checks,
            provenance=_base_provenance(),
        )

    revision_result = _git(upstream_root, "rev-parse", "HEAD")
    actual_revision = revision_result.stdout.strip() if revision_result.ok else None
    checks.append(
        _check(
            "pinned_upstream_revision",
            actual_revision == CUA_GYM_HUB_REVISION,
            (
                f"upstream HEAD matches {CUA_GYM_HUB_REVISION}"
                if actual_revision == CUA_GYM_HUB_REVISION
                else f"expected {CUA_GYM_HUB_REVISION}, got {actual_revision or revision_result.stderr}"
            ),
            expected=CUA_GYM_HUB_REVISION,
            actual=actual_revision,
        )
    )

    vendored_websites = repo_root / "third_party" / "cua-gym-hub" / "websites"
    vendored_app = vendored_websites / app.app_dir
    vendored_source = vendored_websites / app.source_path
    upstream_app = upstream_root / "websites" / app.app_dir
    upstream_source = upstream_root / "websites" / app.source_path
    entry, entry_specifier = _entry_from_index(vendored_app)
    bridge = vendored_app / "src" / "surfgymBridge.js"

    app_tree_result = _git(
        upstream_root,
        "rev-parse",
        f"{CUA_GYM_HUB_REVISION}:websites/{app.app_dir}",
    )
    app_tree_oid = app_tree_result.stdout.strip() if app_tree_result.ok else None
    checks.append(
        _check(
            "pinned_upstream_app_tree",
            bool(app_tree_oid),
            (
                f"pinned app tree is {app_tree_oid}"
                if app_tree_oid
                else f"could not resolve pinned app tree: {app_tree_result.stderr.strip()}"
            ),
            revision=CUA_GYM_HUB_REVISION,
            path=f"websites/{app.app_dir}",
            oid=app_tree_oid,
        )
    )
    upstream_status_result = _git(
        upstream_root,
        "status",
        "--porcelain",
        "--untracked-files=all",
        "--",
        f"websites/{app.app_dir}",
    )
    upstream_status = upstream_status_result.stdout.splitlines()
    upstream_clean = upstream_status_result.ok and not upstream_status
    checks.append(
        _check(
            "upstream_app_checkout_clean",
            upstream_clean,
            (
                "upstream app path has no tracked or untracked changes"
                if upstream_clean
                else "upstream app path is dirty or could not be inspected"
            ),
            path=f"websites/{app.app_dir}",
            porcelain=upstream_status,
            error=upstream_status_result.stderr.strip(),
        )
    )

    for name, path, kind in (
        ("vendored_app", vendored_app, "dir"),
        ("vendored_state_source", vendored_source, "file"),
        ("upstream_app", upstream_app, "dir"),
        ("upstream_state_source", upstream_source, "file"),
        ("bridge", bridge, "file"),
    ):
        exists = path.is_dir() if kind == "dir" else path.is_file()
        checks.append(
            _check(
                name,
                exists,
                f"{path} {'exists' if exists else 'is missing'}",
                path=str(path),
                sha256=_sha256(path) if kind == "file" else None,
            )
        )

    checks.append(
        _check(
            "entry",
            entry is not None,
            (
                f"index module {entry_specifier!r} resolves to {entry}"
                if entry is not None
                else f"index module entry {entry_specifier!r} could not be resolved"
            ),
            path=str(entry) if entry is not None else None,
            module_specifier=entry_specifier,
        )
    )
    if entry is not None:
        runtime_imports = _runtime_imports(entry.read_text(encoding="utf-8"))
        first_import = runtime_imports[0] if runtime_imports else None
        checks.append(
            _check(
                "bridge_first_import",
                first_import == "./surfgymBridge.js",
                f"first runtime import module is {first_import!r}",
                first_import=first_import,
                runtime_imports=runtime_imports,
            )
        )

    if vendored_source.is_file():
        source_text = vendored_source.read_text(encoding="utf-8")
        prefixes_present = (
            app.current_state_key_prefix in source_text
            and app.initial_state_key_prefix in source_text
        )
        checks.append(
            _check(
                "declared_state_prefixes",
                prefixes_present,
                "declared current and initial state prefixes are present in the state source",
                current=app.current_state_key_prefix,
                initial=app.initial_state_key_prefix,
            )
        )
        missing_helpers = [
            name
            for name in _REQUIRED_HELPERS
            if re.search(_EXPORT_PATTERN.format(name=re.escape(name)), source_text, re.DOTALL)
            is None
        ]
        checks.append(
            _check(
                "state_helper_exports",
                not missing_helpers,
                (
                    "all state helpers are exported"
                    if not missing_helpers
                    else f"missing exports: {', '.join(missing_helpers)}"
                ),
                required=list(_REQUIRED_HELPERS),
                missing=missing_helpers,
            )
        )

    if bridge.is_file():
        bridge_text = bridge.read_text(encoding="utf-8")
        required_tokens = ("window.surfgym", "get", "set", "$surfgym", "release")
        missing_tokens = [token for token in required_tokens if token not in bridge_text]
        checks.append(
            _check(
                "bridge_contract",
                not missing_tokens,
                (
                    "bridge exposes get/set and the release sentinel"
                    if not missing_tokens
                    else f"bridge is missing tokens: {', '.join(missing_tokens)}"
                ),
                missing=missing_tokens,
            )
        )

    package_json = vendored_app / "package.json"
    package_data: dict[str, Any] | None = None
    package_error: str | None = None
    try:
        package_data = json.loads(package_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        package_error = str(exc)
    raw_scripts = package_data.get("scripts") if isinstance(package_data, dict) else None
    if package_error is None and not isinstance(raw_scripts, dict):
        package_error = "package.json scripts must be an object"
    scripts = raw_scripts if isinstance(raw_scripts, dict) else {}
    required_scripts = {"test", "build"}
    missing_scripts = sorted(
        name
        for name in required_scripts
        if not isinstance(scripts.get(name), str) or not scripts[name].strip()
    )
    checks.append(
        _check(
            "package_scripts",
            not missing_scripts and package_error is None,
            (
                "package declares test and build scripts"
                if not missing_scripts and package_error is None
                else package_error or f"missing scripts: {', '.join(missing_scripts)}"
            ),
            path=str(package_json),
            scripts={name: scripts.get(name) for name in sorted(required_scripts)},
        )
    )

    generic_modified_paths = {
        vendored_source.relative_to(vendored_app).as_posix(),
        "package.json",
    }
    if entry is not None:
        generic_modified_paths.add(entry.relative_to(vendored_app).as_posix())
    patch_manifest_ok, patch_manifest, exceptional_modified = _patch_manifest_for_app(
        vendored_app=vendored_app,
        upstream_app=upstream_app,
        generic_modified_paths=generic_modified_paths,
    )
    checks.append(
        _check(
            "patch_manifest",
            patch_manifest_ok,
            (
                "app-local exceptional patch provenance is exact"
                if patch_manifest_ok
                else "app-local exceptional patch provenance is invalid or stale"
            ),
            **patch_manifest,
        )
    )
    hash_audit_ok, hash_audit = _vendored_hash_audit(
        vendored_app=vendored_app,
        upstream_app=upstream_app,
        state_source=vendored_source,
        entry=entry,
        exceptional_modified=exceptional_modified if patch_manifest_ok else {},
    )
    checks.append(
        _check(
            "vendored_hash_audit",
            hash_audit_ok,
            (
                "vendored differences are limited to the onboarding allowlist"
                if hash_audit_ok
                else "vendored tree has non-allowlisted modifications or new files"
            ),
            **hash_audit,
        )
    )

    deploy_script = upstream_root / "deploy-all.sh"
    deploy_text = deploy_script.read_text(encoding="utf-8") if deploy_script.is_file() else ""
    deploy_rule_ok = all(
        token in deploy_text for token in ("BASE_PORT=8000", "-name '*_mock'", "| sort")
    )
    checks.append(
        _check(
            "upstream_port_rule",
            deploy_rule_ok,
            "upstream deploy rule uses base port 8000 and lexical *_mock ordering",
            path=str(deploy_script),
        )
    )

    tree_result = _git(
        upstream_root,
        "ls-tree",
        "--name-only",
        f"{CUA_GYM_HUB_REVISION}:websites",
    )
    tree_names = sorted(
        name.strip() for name in tree_result.stdout.splitlines() if name.strip().endswith("_mock")
    )
    tree_payload = "\n".join(tree_names).encode()
    tree_hash = hashlib.sha256(tree_payload).hexdigest() if tree_names else None
    computed_offset = tree_names.index(app.app_dir) if app.app_dir in tree_names else None
    unique_offsets = len({item.hub_port_offset for item in DIRECT_WEB_APPS}) == len(DIRECT_WEB_APPS)
    port_ok = tree_result.ok and computed_offset == app.hub_port_offset and unique_offsets
    checks.append(
        _check(
            "fixed_caddy_offset",
            port_ok,
            (
                f"validated offset {app.hub_port_offset} maps to port "
                f"{DEFAULT_CADDY_START_PORT + app.hub_port_offset}"
                if port_ok
                else (
                    f"declared offset {app.hub_port_offset}, computed offset {computed_offset}; "
                    f"git error: {tree_result.stderr.strip()}"
                )
            ),
            declared_offset=app.hub_port_offset,
            computed_offset=computed_offset,
            base_port=DEFAULT_CADDY_START_PORT,
            caddy_port=DEFAULT_CADDY_START_PORT + app.hub_port_offset,
            offsets_unique=unique_offsets,
        )
    )

    provenance = _base_provenance()
    provenance.update(
        {
            "upstream_revision_actual": actual_revision,
            "upstream_app_tree": {
                "path": f"websites/{app.app_dir}",
                "oid": app_tree_oid,
                "checkout_clean": upstream_clean,
                "checkout_porcelain": upstream_status,
            },
            "vendored_source_sha256": _sha256(vendored_source),
            "upstream_source_sha256": _sha256(upstream_source),
            "vendored_hash_audit": hash_audit,
            "fixed_port": {
                "base_port": DEFAULT_CADDY_START_PORT,
                "declared_offset": app.hub_port_offset,
                "computed_offset": computed_offset,
                "port": DEFAULT_CADDY_START_PORT + app.hub_port_offset,
                "rule": "pinned revision websites/*_mock lexical index",
                "tree_listing_sha256": tree_hash,
                "tree_entry_count": len(tree_names),
            },
        }
    )
    return _report(
        command="inspect-app",
        app_key=app.app_key,
        checks=checks,
        provenance=provenance,
    )


def verify_app(
    *,
    app_key: str,
    repo_root: Path,
    upstream_root: Path,
    run_unit: bool = False,
    run_build: bool = False,
    timeout_seconds: float = DEFAULT_COMMAND_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Verify inspection plus explicitly requested existing package scripts."""
    inspection = inspect_app(
        app_key=app_key,
        repo_root=repo_root,
        upstream_root=upstream_root,
    )
    inspect_passed = inspection["status"] == "PASS"
    app: CuaWebApp | None
    try:
        app = get_direct_web_app(normalize_key(app_key))
    except ValueError:
        app = None
    app_root = (
        repo_root.resolve() / "third_party" / "cua-gym-hub" / "websites" / app.app_dir
        if app is not None
        else repo_root.resolve()
    )

    stages: dict[str, dict[str, Any]] = {
        "INSPECT": {"status": inspection["status"], "checks": inspection["checks"]},
        "STATIC": {
            "status": "PASS" if inspect_passed else "FAIL",
            "detail": "manifest, source, bridge, package, and Caddy contracts",
        },
    }
    for stage, requested, argv in (
        ("UNIT", run_unit, (_npm_executable(), "test")),
        ("BUILD", run_build, (_npm_executable(), "run", "build")),
    ):
        if not requested:
            stages[stage] = {"status": "SKIPPED", "detail": "not requested"}
        elif not inspect_passed:
            stages[stage] = {"status": "BLOCKED", "detail": "inspect-app failed"}
        else:
            result = _run_process(argv, cwd=app_root, timeout_seconds=timeout_seconds)
            stages[stage] = {
                "status": "PASS" if result.ok else "FAIL",
                **asdict(result),
            }

    verification_statuses = [
        stages[stage]["status"] for stage in ("INSPECT", "STATIC", "UNIT", "BUILD")
    ]
    passed = all(status == "PASS" for status in verification_statuses)
    incomplete = inspect_passed and "SKIPPED" in verification_statuses
    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "command": "verify-app",
        "app_key": normalize_key(app_key),
        "status": "PASS" if passed else "INCOMPLETE" if incomplete else "FAIL",
        "stages": stages,
        "provenance": inspection["provenance"],
    }
    report["next_step"] = _task_import_next_step(ready=passed)
    return report


def _npm_executable() -> str:
    return shutil.which("npm") or "npm"


def _base_provenance() -> dict[str, Any]:
    return {
        "upstream_url": CUA_GYM_HUB_URL,
        "upstream_revision_expected": CUA_GYM_HUB_REVISION,
        "license": CUA_GYM_HUB_LICENSE,
    }


def _task_import_next_step(*, ready: bool) -> dict[str, Any]:
    return {
        "stage": "TASK_IMPORT",
        "status": "READY" if ready else "BLOCKED",
        "command": "python -m surfgym_task.cua.import_task",
        "detail": "Task import is a separate staging step and is not executed by this command.",
    }


def _verify_app_next_step(*, ready: bool) -> dict[str, Any]:
    return {
        "stage": "VERIFY_APP",
        "status": "READY" if ready else "BLOCKED",
        "command": "python scripts/cua_hub_deploy/onboard_webapp.py verify-app",
        "detail": "Run both existing package unit tests and the package build before task import.",
    }


def _report(
    *,
    command: str,
    app_key: str,
    checks: list[dict[str, Any]],
    provenance: dict[str, Any],
) -> dict[str, Any]:
    passed = all(check["status"] == "PASS" for check in checks)
    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "command": command,
        "app_key": app_key,
        "status": "PASS" if passed else "FAIL",
        "checks": checks,
        "provenance": provenance,
    }
    report["next_step"] = _verify_app_next_step(ready=passed)
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("inspect-app", "verify-app"):
        child = subparsers.add_parser(name)
        child.add_argument("--app-key", required=True)
        child.add_argument("--repo-root", type=Path, required=True)
        child.add_argument("--upstream-root", type=Path, required=True)
        child.add_argument("--json-out", type=Path)
        if name == "verify-app":
            child.add_argument("--run-unit", action="store_true")
            child.add_argument("--run-build", action="store_true")
            child.add_argument(
                "--timeout-seconds",
                type=float,
                default=DEFAULT_COMMAND_TIMEOUT_SECONDS,
            )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "inspect-app":
        report = inspect_app(
            app_key=args.app_key,
            repo_root=args.repo_root,
            upstream_root=args.upstream_root,
        )
    else:
        report = verify_app(
            app_key=args.app_key,
            repo_root=args.repo_root,
            upstream_root=args.upstream_root,
            run_unit=args.run_unit,
            run_build=args.run_build,
            timeout_seconds=args.timeout_seconds,
        )
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report["status"] == "PASS" else 1
