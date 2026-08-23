"""The direct CUA-Gym web application selected for the Instacart pilot."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


CUA_GYM_HUB_URL = "https://github.com/xlang-ai/CUA-Gym-Hub.git"
CUA_GYM_HUB_REVISION = "53205689c3d88078c1375f76466d5bd799478828"
CUA_GYM_HUB_LICENSE = "Apache-2.0"


@dataclass(frozen=True)
class CuaWebApp:
    app_key: str
    app_dir: str
    source_path: str
    current_state_key_prefix: str
    initial_state_key_prefix: str
    hub_port_offset: int
    state_endpoint: Literal["/state"] = "/state"
    state_response_field: Literal["stored_state"] = "stored_state"
    category: Literal["web"] = "web"

    def current_state_key(self, source_task_id: str) -> str:
        return f"{self.current_state_key_prefix}_{source_task_id}"

    def initial_state_key(self, source_task_id: str) -> str:
        return f"{self.initial_state_key_prefix}_{source_task_id}"


DIRECT_WEB_APPS: tuple[CuaWebApp, ...] = (
    CuaWebApp(
        app_key="INSTACART",
        app_dir="instacart_mock",
        source_path="instacart_mock/src/data/mockData.js",
        current_state_key_prefix="instacart_mock_state",
        initial_state_key_prefix="instacart_mock_initialState",
        hub_port_offset=51,
    ),
)
DIRECT_WEB_APPS_BY_KEY = {app.app_key: app for app in DIRECT_WEB_APPS}
DIRECT_WEB_APP_KEYS = frozenset(DIRECT_WEB_APPS_BY_KEY)


def get_direct_web_app(app_key: str) -> CuaWebApp:
    try:
        return DIRECT_WEB_APPS_BY_KEY[app_key]
    except KeyError as exc:
        raise ValueError(f"Unsupported CUA direct web app: {app_key!r}") from exc
