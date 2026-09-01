"""CUA-Gym web applications registered for direct-web serving."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Literal

from surfgym_contracts.local_static_sites import get_local_static_site

CUA_GYM_HUB_URL = "https://github.com/xlang-ai/CUA-Gym-Hub.git"
CUA_GYM_HUB_REVISION = "53205689c3d88078c1375f76466d5bd799478828"
CUA_GYM_HUB_LICENSE = "Apache-2.0"


@dataclass(frozen=True)
class CuaWebApp:
    app_key: str
    source_path: str
    current_state_key_prefix: str
    initial_state_key_prefix: str
    state_endpoint: Literal["/state"] = "/state"
    state_response_field: Literal["stored_state"] = "stored_state"
    category: Literal["web"] = "web"

    @property
    def app_dir(self) -> str:
        return PurePosixPath(get_local_static_site(self.app_key).source_dir).name

    @property
    def hub_port_offset(self) -> int:
        return get_local_static_site(self.app_key).port - 8000

    def current_state_key(self, source_task_id: str) -> str:
        return f"{self.current_state_key_prefix}_{source_task_id}"

    def initial_state_key(self, source_task_id: str) -> str:
        return f"{self.initial_state_key_prefix}_{source_task_id}"


DIRECT_WEB_APPS: tuple[CuaWebApp, ...] = (
    CuaWebApp(
        app_key="GMAIL",
        source_path="gmail_mock/src/data/mockData.js",
        current_state_key_prefix="xmail-clone-state",
        initial_state_key_prefix="xmail-clone-initialState",
    ),
    CuaWebApp(
        app_key="GITHUB",
        source_path="github_mock/src/lib/mockData.js",
        current_state_key_prefix="gitmock_state",
        initial_state_key_prefix="gitmock_initialState",
    ),
    CuaWebApp(
        app_key="HUBSPOT",
        source_path="hubspot_mock/src/data/mockData.js",
        current_state_key_prefix="hubspot_mock_db",
        initial_state_key_prefix="hubspot_mock_db_initial",
    ),
    CuaWebApp(
        app_key="INSTACART",
        source_path="instacart_mock/src/data/mockData.js",
        current_state_key_prefix="instacart_mock_state",
        initial_state_key_prefix="instacart_mock_initialState",
    ),
    CuaWebApp(
        app_key="INSTAGRAM",
        source_path="instagram_mock/src/utils/mockData.js",
        current_state_key_prefix="instagram_mock_state",
        initial_state_key_prefix="instagram_mock_initialState",
    ),
    CuaWebApp(
        app_key="JIRA",
        source_path="jira_mock/src/utils/mockData.ts",
        current_state_key_prefix="jira_clone_state",
        initial_state_key_prefix="jira_clone_initialState",
    ),
    CuaWebApp(
        app_key="LINKEDIN",
        source_path="linkedin_mock/src/data/mockData.js",
        current_state_key_prefix="linkedin_mock_state",
        initial_state_key_prefix="linkedin_mock_initialState",
    ),
    CuaWebApp(
        app_key="MICROSOFT_TEAMS",
        source_path="microsoft_teams_mock/src/utils/dataManager.js",
        current_state_key_prefix="teamsState",
        initial_state_key_prefix="teamsInitialState",
    ),
    CuaWebApp(
        app_key="PINTEREST",
        source_path="pinterest_mock/src/store/initialData.js",
        current_state_key_prefix="pinteract_state",
        initial_state_key_prefix="pinteract_initialState",
    ),
    CuaWebApp(
        app_key="SHOPIFY_ADMIN",
        source_path="shopify_admin_mock/src/lib/seed.js",
        current_state_key_prefix="shopify_mock_state",
        initial_state_key_prefix="shopify_mock_initialState",
    ),
    CuaWebApp(
        app_key="STRIPE_DASHBOARD",
        source_path="stripe_dashboard_mock/src/utils/dataManager.js",
        current_state_key_prefix="stripe_dashboard_state",
        initial_state_key_prefix="stripe_dashboard_initialState",
    ),
    CuaWebApp(
        app_key="TRELLO",
        source_path="trello_mock/src/utils/mockData.js",
        current_state_key_prefix="trello_clone_state",
        initial_state_key_prefix="trello_clone_initialState",
    ),
    CuaWebApp(
        app_key="TWITTER",
        source_path="twitter_mock/src/utils/mockData.js",
        current_state_key_prefix="x_clone_state",
        initial_state_key_prefix="x_clone_initialState",
    ),
    CuaWebApp(
        app_key="WECHAT",
        source_path="wechat_mock/src/utils/storage.js",
        current_state_key_prefix="wechat_mock_data",
        initial_state_key_prefix="wechat_mock_data_initialState",
    ),
)
DIRECT_WEB_APPS_BY_KEY = {app.app_key: app for app in DIRECT_WEB_APPS}
DIRECT_WEB_APP_KEYS = frozenset(DIRECT_WEB_APPS_BY_KEY)


def get_direct_web_app(app_key: str) -> CuaWebApp:
    try:
        return DIRECT_WEB_APPS_BY_KEY[app_key]
    except KeyError as exc:
        raise ValueError(f"Unsupported CUA direct web app: {app_key!r}") from exc
