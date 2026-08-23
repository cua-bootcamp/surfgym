"""One definition of the CUA app key space.

Bundles address a Hub app through a `__CUA_GYM_<KEY>_URL__` placeholder, the
Hub stores that app under `websites/<key>_mock/`, and we store its recorded
initial state under `<state_dir>/<KEY>/`. If the deploy side and the record
side derive the key differently, `GET /state?sid=` 404s -- and a 404 does not
fail loudly: the app quietly boots its own default data and the reward scores a
world the task never described. So both sides call in here.

The released `url_variables.json` carries 32 keys, one of which (`NOTION_MOCK`)
is an alias for an app already named by another key (`NOTION`).
"""

from __future__ import annotations

import re
from pathlib import Path

_PLACEHOLDER = re.compile(r"__CUA_GYM_([A-Z0-9_]+?)_(?:URL|HOST)__")
_ALIAS_SUFFIX = "_MOCK"
_APP_DIR_SUFFIX = "_mock"


def normalize_key(key: str) -> str:
    """`NOTION_MOCK` and `NOTION` name the same app; collapse to one key."""
    upper = key.upper()
    if upper.endswith(_ALIAS_SUFFIX) and len(upper) > len(_ALIAS_SUFFIX):
        return upper[: -len(_ALIAS_SUFFIX)]
    return upper


def key_from_placeholder(text: str) -> str | None:
    match = _PLACEHOLDER.search(text)
    return normalize_key(match.group(1)) if match is not None else None


def key_from_app_dir(app_dir_name: str) -> str:
    """`notion_mock` -> `NOTION`."""
    return normalize_key(app_dir_name.removesuffix(_APP_DIR_SUFFIX))


def app_dir_for_key(key: str) -> str:
    """`NOTION` -> `notion_mock`."""
    return f"{normalize_key(key).lower()}{_APP_DIR_SUFFIX}"


def unmapped_keys(keys: set[str], websites_dir: Path) -> set[str]:
    """Keys with no app directory -- these would 404 at episode time."""
    available = {entry.name.lower() for entry in websites_dir.iterdir() if entry.is_dir()}
    return {key for key in keys if app_dir_for_key(key) not in available}
