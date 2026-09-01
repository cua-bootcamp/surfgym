"""Turn a bundle's `initial_setup.py` into static per-app initial state files.

The setup script is executed exactly once here, offline. At episode time the
app just fetches the recorded JSON from `GET /state?sid=`, so no Python setup
runs per rollout and every rollout of a task starts from byte-identical state.

Layout is `<state_dir>/<APP_KEY>/<task_id>.json`. A cross-app task reuses one
sid across several apps but POSTs a *different* state to each, so the app key
has to be part of the path.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from surfgym_task.cua.app_registry import key_from_placeholder
from surfgym_task.cua.bundle_store import Bundle
from surfgym_task.cua.http_stub import JsonValue
from surfgym_task.cua.sandbox import DEFAULT_TIMEOUT_S, run_bundle_script

_PORTABLE_EPISODE_SID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
_WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}


@dataclass(frozen=True)
class RecordedSetup:
    task_id: str
    states: dict[str, JsonValue]
    """APP_KEY -> the state the setup script POSTed to that app."""

    sid: Optional[str]
    stdout: str
    error: Optional[str]

    bases: dict[str, str] = field(default_factory=dict)
    """APP_KEY -> the exact base string the script addressed.

    `states` is keyed by the normalized app key because that is what the state
    directory layout needs. A reward script is routed by byte-exact match on
    the base it carries, and normalizing is lossy: `__CUA_GYM_NOTION_MOCK_URL__`
    and `__CUA_GYM_NOTION_URL__` both collapse to `NOTION`, and the `_HOST`
    variants collapse the same way. Keep the original so no caller has to
    reconstruct it.
    """

    @property
    def ok(self) -> bool:
        return self.error is None and bool(self.states)


def record(bundle: Bundle, *, timeout_s: float = DEFAULT_TIMEOUT_S) -> RecordedSetup:
    if bundle.initial_setup is None:
        return RecordedSetup(bundle.task_id, {}, None, "", "bundle has no initial_setup.py")

    run = run_bundle_script(
        bundle.initial_setup,
        filename=f"{bundle.task_id}/initial_setup.py",
        timeout_s=timeout_s,
    )
    if not run.ok:
        return RecordedSetup(bundle.task_id, {}, None, run.stdout, run.error)

    states: dict[str, JsonValue] = {}
    bases: dict[str, str] = {}
    for base, state in run.recorded.items():
        key = key_from_placeholder(base)
        if key is None:
            return RecordedSetup(
                bundle.task_id, {}, None, run.stdout, f"cannot derive app key from base {base!r}"
            )
        states[key] = state
        bases[key] = base

    if not states:
        return RecordedSetup(bundle.task_id, {}, None, run.stdout, "setup POSTed no state")

    return RecordedSetup(
        task_id=bundle.task_id,
        states=states,
        sid=next(iter(run.sids.values()), None),
        stdout=run.stdout,
        error=None,
        bases=bases,
    )


def write_states(
    recorded: RecordedSetup,
    state_dir: Path,
    *,
    sid: str | None = None,
) -> list[Path]:
    """Write one file per app in the shape `fetchCustomState()` expects."""
    state_sid = recorded.task_id if sid is None else sid
    if sid is None:
        if (
            not state_sid.strip()
            or state_sid != state_sid.strip()
            or state_sid in {".", ".."}
            or "/" in state_sid
            or "\\" in state_sid
        ):
            raise ValueError(f"invalid state SID: {state_sid!r}")
    else:
        validate_episode_sid(state_sid)

    written: list[Path] = []
    for key, state in recorded.states.items():
        target = state_dir / key / f"{state_sid}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(
                {"sid": state_sid, "has_custom_state": True, "stored_state": state},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        written.append(target)
    return written


def validate_episode_sid(sid: str) -> None:
    """Require an explicit run SID that is portable as a Windows filename."""
    reserved_stem = sid.split(".", 1)[0].upper()
    if (
        _PORTABLE_EPISODE_SID.fullmatch(sid) is None
        or sid.endswith(".")
        or reserved_stem in _WINDOWS_RESERVED_NAMES
    ):
        raise ValueError(f"invalid episode SID: {sid!r}")
