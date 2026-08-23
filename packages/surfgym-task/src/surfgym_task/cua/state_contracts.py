"""Verified state contracts for CUA-Gym-Hub mock apps.

The public direct-web task set currently uses 28 real mock apps.  Those apps
keep their canonical episode state in ``localStorage`` and share one boot
contract: ``GET /state?sid=...`` returns the seed under ``stored_state``.

Apps outside that task set are not assumed to follow the same contract.  The
known exceptions below are registered explicitly so a caller cannot silently
serve the wrong JSON shape.  Unknown apps must be inspected and added here
before they can be migrated.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from surfgym_task.cua.app_registry import normalize_key
from surfgym_task.cua.webapp_manifest import (
    DIRECT_WEB_APP_KEYS as DIRECT_WEB_APP_KEYS,
)
from surfgym_task.cua.webapp_manifest import (
    DIRECT_WEB_APPS,
    CuaWebApp,
)

type StateBackend = Literal["browser_local_storage", "server_memory"]
type ResponseField = Literal["stored_state", "current_state"]


@dataclass(frozen=True)
class AppStateContract:
    """How one CUA mock app boots, stores, and exposes episode state."""

    app_key: str
    state_backend: StateBackend
    initial_state_endpoint: str
    initial_state_response_field: ResponseField | None
    current_state_key_template: str | None
    initial_state_key_template: str | None
    source_path: str
    in_direct_web_dataset: bool = False

    @property
    def requires_server_memory(self) -> bool:
        return self.state_backend == "server_memory"

    def current_state_key(self, sid: str) -> str:
        if self.current_state_key_template is None:
            raise ValueError(f"{self.app_key} does not store current state in localStorage")
        return self.current_state_key_template.format(sid=sid)

    def initial_state_key(self, sid: str) -> str:
        if self.initial_state_key_template is None:
            raise ValueError(f"{self.app_key} does not store initial state in localStorage")
        return self.initial_state_key_template.format(sid=sid)


def _direct_web(app: CuaWebApp) -> AppStateContract:
    return AppStateContract(
        app_key=app.app_key,
        state_backend="browser_local_storage",
        initial_state_endpoint=app.state_endpoint,
        initial_state_response_field=app.state_response_field,
        current_state_key_template=f"{app.current_state_key_prefix}_{{sid}}",
        initial_state_key_template=f"{app.initial_state_key_prefix}_{{sid}}",
        source_path=app.source_path,
        in_direct_web_dataset=True,
    )


_DIRECT_WEB_CONTRACTS = tuple(_direct_web(app) for app in DIRECT_WEB_APPS)

_KNOWN_EXCEPTION_CONTRACTS = (
    AppStateContract(
        app_key="12306",
        state_backend="browser_local_storage",
        initial_state_endpoint="/state",
        initial_state_response_field=None,
        current_state_key_template="12306_mock_state_{sid}",
        initial_state_key_template="12306_mock_initial_state_{sid}",
        source_path="12306_mock/src/utils/dataManager.js",
    ),
    AppStateContract(
        app_key="ADP",
        state_backend="browser_local_storage",
        initial_state_endpoint="/go",
        initial_state_response_field="current_state",
        current_state_key_template="adp_mock_state_{sid}",
        initial_state_key_template="adp_mock_state_{sid}_initial",
        source_path="adp_mock/src/utils/dataManager.js",
    ),
    AppStateContract(
        app_key="WESTLAW",
        state_backend="server_memory",
        initial_state_endpoint="/state",
        initial_state_response_field=None,
        current_state_key_template=None,
        initial_state_key_template=None,
        source_path="westlaw_mock/src/utils/dataManager.js",
    ),
)

APP_STATE_CONTRACTS: dict[str, AppStateContract] = {
    contract.app_key: contract
    for contract in (*_DIRECT_WEB_CONTRACTS, *_KNOWN_EXCEPTION_CONTRACTS)
}

def get_state_contract(app_key: str) -> AppStateContract:
    """Return a verified contract; never guess one for an unknown app."""
    normalized = normalize_key(app_key)
    try:
        return APP_STATE_CONTRACTS[normalized]
    except KeyError as exc:
        raise KeyError(f"no verified CUA state contract for {normalized}") from exc
