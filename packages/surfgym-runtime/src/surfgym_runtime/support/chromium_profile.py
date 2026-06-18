from __future__ import annotations

import html
import json
import math
import shutil
import sqlite3
import tempfile
import time
from pathlib import Path
from typing import Any

from playwright.async_api import BrowserContext
from surfgym_contracts.task import ChromiumRule, Observation, ProfileCookie, ProfileSetup, Value


def apply_chromium_profile_file_setup(profile_dir: Path, setup: ProfileSetup | None) -> None:
    if setup is None:
        return

    for item in setup.json_values:
        path = safe_profile_path(profile_dir, item.file)
        if path is None:
            raise ValueError(f"Unsafe profile setup file path: {item.file}")
        _set_json_value(path, item.path, item.value)


async def apply_chromium_runtime_profile_setup(
    context: BrowserContext,
    setup: ProfileSetup | None,
) -> None:
    if setup is None:
        return

    if setup.cookies:
        await context.add_cookies([_cookie_payload(cookie) for cookie in setup.cookies])

    if setup.history_entries:
        page = await context.new_page()
        try:
            for entry in setup.history_entries:
                body = _history_entry_body(entry.title)

                async def fulfill_seed(route, request, body=body):
                    await route.fulfill(
                        status=200,
                        content_type="text/html",
                        body=body,
                    )

                await context.route(entry.url, fulfill_seed, times=1)
                await page.goto(entry.url, wait_until="domcontentloaded", timeout=5000)
        finally:
            await page.close()


def profile_setup_requires_persistent_context(setup: ProfileSetup | None) -> bool:
    if setup is None:
        return False
    return bool(setup.json_values or setup.history_entries or setup.cookies)


def evaluate_chromium_profile_rule(profile_dir: Path | None, rule: ChromiumRule) -> Observation:
    if profile_dir is None:
        return None

    if rule.type == "json_value":
        if rule.file is None or rule.path is None:
            return None
        return read_profile_json_value(
            profile_dir=profile_dir,
            relative_file=rule.file,
            dotted_path=rule.path,
        )

    if rule.type == "bookmark_bar_folder":
        if not isinstance(rule.value, str):
            return None
        return find_bookmark_bar_folder(profile_dir, rule.value)

    if rule.type == "bookmark_bar_url":
        if not isinstance(rule.value, str):
            return None
        return find_bookmark_bar_url(profile_dir, rule.value)

    if rule.type == "history_keyword_absent":
        if not rule.query:
            return None
        count = count_history_keyword_matches(profile_dir, rule.query)
        return None if count is None else count == 0

    if rule.type == "cookie_domain_absent":
        if not rule.domain:
            return None
        count = count_cookie_domain_matches(profile_dir, rule.domain)
        return None if count is None else count == 0

    return None


def read_profile_json_value(
    *,
    profile_dir: Path,
    relative_file: str,
    dotted_path: str,
) -> Observation:
    path = safe_profile_path(profile_dir, relative_file)
    if path is None or not path.exists():
        return None

    try:
        data: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    current: Any = data
    for key in dotted_path.split("."):
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]

    return coerce_profile_observation(current)


def find_bookmark_bar_folder(profile_dir: Path, expected_name: str) -> Observation:
    data = read_profile_json_file(profile_dir, "Default/Bookmarks")
    if not isinstance(data, dict):
        return None

    bookmark_bar = _bookmark_bar_root(data)
    if bookmark_bar is None:
        return None

    for child in bookmark_bar.get("children", []):
        if not isinstance(child, dict):
            continue
        if child.get("type") == "folder" and child.get("name") == expected_name:
            return expected_name
    return None


def find_bookmark_bar_url(profile_dir: Path, expected_url: str) -> Observation:
    data = read_profile_json_file(profile_dir, "Default/Bookmarks")
    if not isinstance(data, dict):
        return None

    bookmark_bar = _bookmark_bar_root(data)
    if bookmark_bar is None:
        return None

    for child in walk_bookmark_nodes(bookmark_bar):
        if not isinstance(child, dict):
            continue
        if child.get("type") == "url" and child.get("url") == expected_url:
            return expected_url
    return None


def count_history_keyword_matches(profile_dir: Path, query: str) -> int | None:
    path = safe_profile_path(profile_dir, "Default/History")
    if path is None or not path.exists():
        return None

    pattern = f"%{query.casefold()}%"
    return _query_sqlite_count(
        path,
        """
        SELECT COUNT(*)
        FROM urls
        WHERE lower(coalesce(url, '')) LIKE ?
           OR lower(coalesce(title, '')) LIKE ?
        """,
        (pattern, pattern),
    )


def count_cookie_domain_matches(profile_dir: Path, domain: str) -> int | None:
    for relative_file in ("Default/Network/Cookies", "Default/Cookies"):
        path = safe_profile_path(profile_dir, relative_file)
        if path is None or not path.exists():
            continue

        host_keys = _query_cookie_host_keys(path)
        if host_keys is None:
            continue
        return sum(1 for host_key in host_keys if _host_matches_domain(host_key, domain))

    return None


def read_profile_json_file(profile_dir: Path, relative_file: str) -> Any:
    path = safe_profile_path(profile_dir, relative_file)
    if path is None or not path.exists():
        return None

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def walk_bookmark_nodes(node: dict[str, Any]):
    children = node.get("children", [])
    if not isinstance(children, list):
        return

    for child in children:
        yield child
        if isinstance(child, dict):
            yield from walk_bookmark_nodes(child)


def safe_profile_path(profile_dir: Path, relative_file: str) -> Path | None:
    profile_root = profile_dir.resolve()
    path = (profile_root / relative_file).resolve()
    if not path.is_relative_to(profile_root):
        return None
    return path


def coerce_profile_observation(value: object) -> Observation:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            return str(value)
        return value
    return None


def _set_json_value(path: Path, dotted_path: str, value: Value) -> None:
    if path.exists():
        try:
            data: Any = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON profile file: {path}") from exc
    else:
        data = {}

    if not isinstance(data, dict):
        raise ValueError(f"Profile JSON root must be an object: {path}")

    current: dict[str, Any] = data
    keys = dotted_path.split(".")
    for key in keys[:-1]:
        child = current.get(key)
        if child is None:
            child = {}
            current[key] = child
        if not isinstance(child, dict):
            raise ValueError(f"Cannot set nested path through non-object key: {key}")
        current = child

    current[keys[-1]] = value
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _cookie_payload(cookie: ProfileCookie) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": cookie.name,
        "value": cookie.value,
        "path": cookie.path,
        "expires": cookie.expires if cookie.expires is not None else time.time() + 31536000,
        "httpOnly": cookie.http_only,
        "secure": cookie.secure,
    }

    if cookie.domain:
        payload["domain"] = cookie.domain
    else:
        payload["url"] = cookie.url

    if cookie.same_site is not None:
        payload["sameSite"] = cookie.same_site

    return payload


def _history_entry_body(title: str) -> str:
    safe_title = html.escape(title or "SurfGym History Fixture")
    return f"<!doctype html><title>{safe_title}</title><body>{safe_title}</body>"


def _bookmark_bar_root(data: dict[str, Any]) -> dict[str, Any] | None:
    roots = data.get("roots")
    if not isinstance(roots, dict):
        return None

    bookmark_bar = roots.get("bookmark_bar")
    return bookmark_bar if isinstance(bookmark_bar, dict) else None


def _query_sqlite_count(path: Path, sql: str, params: tuple[object, ...]) -> int | None:
    value = _query_sqlite_count_direct(path, sql, params)
    if value is not None:
        return value

    return _query_sqlite_count_from_copy(path, sql, params)


def _query_sqlite_count_direct(path: Path, sql: str, params: tuple[object, ...]) -> int | None:
    try:
        uri = f"file:{path}?mode=ro"
        with sqlite3.connect(uri, uri=True, timeout=1.0) as db:
            db.execute("PRAGMA query_only = ON")
            row = db.execute(sql, params).fetchone()
            return int(row[0]) if row is not None else None
    except sqlite3.Error:
        return None


def _query_sqlite_count_from_copy(path: Path, sql: str, params: tuple[object, ...]) -> int | None:
    try:
        with tempfile.TemporaryDirectory(prefix="surfgym-sqlite-read-") as tmpdir:
            copy_path = Path(tmpdir) / path.name
            shutil.copy2(path, copy_path)
            with sqlite3.connect(copy_path) as db:
                db.execute("PRAGMA query_only = ON")
                row = db.execute(sql, params).fetchone()
                return int(row[0]) if row is not None else None
    except (OSError, sqlite3.Error):
        return None


def _query_cookie_host_keys(path: Path) -> list[str] | None:
    direct = _query_cookie_host_keys_direct(path)
    if direct is not None:
        return direct

    return _query_cookie_host_keys_from_copy(path)


def _query_cookie_host_keys_direct(path: Path) -> list[str] | None:
    try:
        uri = f"file:{path}?mode=ro"
        with sqlite3.connect(uri, uri=True, timeout=1.0) as db:
            db.execute("PRAGMA query_only = ON")
            rows = db.execute("SELECT host_key FROM cookies").fetchall()
            return [str(row[0]) for row in rows]
    except sqlite3.Error:
        return None


def _query_cookie_host_keys_from_copy(path: Path) -> list[str] | None:
    try:
        with tempfile.TemporaryDirectory(prefix="surfgym-sqlite-read-") as tmpdir:
            copy_path = Path(tmpdir) / path.name
            shutil.copy2(path, copy_path)
            with sqlite3.connect(copy_path) as db:
                db.execute("PRAGMA query_only = ON")
                rows = db.execute("SELECT host_key FROM cookies").fetchall()
                return [str(row[0]) for row in rows]
    except (OSError, sqlite3.Error):
        return None


def _host_matches_domain(host_key: str, domain: str) -> bool:
    host = host_key.lstrip(".").casefold()
    target = domain.lstrip(".").casefold()
    return host == target or host.endswith(f".{target}")
