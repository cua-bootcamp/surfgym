"""CUA-Gym web applications registered for direct-web serving."""

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
        app_key="GMAIL",
        app_dir="gmail_mock",
        source_path="gmail_mock/src/data/mockData.js",
        current_state_key_prefix="xmail-clone-state",
        initial_state_key_prefix="xmail-clone-initialState",
        hub_port_offset=38,
    ),
    CuaWebApp(
        app_key="GITHUB",
        app_dir="github_mock",
        source_path="github_mock/src/lib/mockData.js",
        current_state_key_prefix="gitmock_state",
        initial_state_key_prefix="gitmock_initialState",
        hub_port_offset=36,
    ),
    CuaWebApp(
        app_key="HUBSPOT",
        app_dir="hubspot_mock",
        source_path="hubspot_mock/src/data/mockData.js",
        current_state_key_prefix="hubspot_mock_db",
        initial_state_key_prefix="hubspot_mock_db_initial",
        hub_port_offset=50,
    ),
    CuaWebApp(
        app_key="INSTACART",
        app_dir="instacart_mock",
        source_path="instacart_mock/src/data/mockData.js",
        current_state_key_prefix="instacart_mock_state",
        initial_state_key_prefix="instacart_mock_initialState",
        hub_port_offset=51,
    ),
    CuaWebApp(
        app_key="INSTAGRAM",
        app_dir="instagram_mock",
        source_path="instagram_mock/src/utils/mockData.js",
        current_state_key_prefix="instagram_mock_state",
        initial_state_key_prefix="instagram_mock_initialState",
        hub_port_offset=52,
    ),
    CuaWebApp(
        app_key="JIRA",
        app_dir="jira_mock",
        source_path="jira_mock/src/utils/mockData.ts",
        current_state_key_prefix="jira_clone_state",
        initial_state_key_prefix="jira_clone_initialState",
        hub_port_offset=53,
    ),
    CuaWebApp(
        app_key="LINKEDIN",
        app_dir="linkedin_mock",
        source_path="linkedin_mock/src/data/mockData.js",
        current_state_key_prefix="linkedin_mock_state",
        initial_state_key_prefix="linkedin_mock_initialState",
        hub_port_offset=57,
    ),
    CuaWebApp(
        app_key="MICROSOFT_TEAMS",
        app_dir="microsoft_teams_mock",
        source_path="microsoft_teams_mock/src/utils/dataManager.js",
        current_state_key_prefix="teamsState",
        initial_state_key_prefix="teamsInitialState",
        hub_port_offset=62,
    ),
    CuaWebApp(
        app_key="PINTEREST",
        app_dir="pinterest_mock",
        source_path="pinterest_mock/src/store/initialData.js",
        current_state_key_prefix="pinteract_state",
        initial_state_key_prefix="pinteract_initialState",
        hub_port_offset=70,
    ),
    CuaWebApp(
        app_key="SHOPIFY_ADMIN",
        app_dir="shopify_admin_mock",
        source_path="shopify_admin_mock/src/lib/seed.js",
        current_state_key_prefix="shopify_mock_state",
        initial_state_key_prefix="shopify_mock_initialState",
        hub_port_offset=77,
    ),
    CuaWebApp(
        app_key="STRIPE_DASHBOARD",
        app_dir="stripe_dashboard_mock",
        source_path="stripe_dashboard_mock/src/utils/dataManager.js",
        current_state_key_prefix="stripe_dashboard_state",
        initial_state_key_prefix="stripe_dashboard_initialState",
        hub_port_offset=79,
    ),
    CuaWebApp(
        app_key="TRELLO",
        app_dir="trello_mock",
        source_path="trello_mock/src/utils/mockData.js",
        current_state_key_prefix="trello_clone_state",
        initial_state_key_prefix="trello_clone_initialState",
        hub_port_offset=82,
    ),
    CuaWebApp(
        app_key="TWITTER",
        app_dir="twitter_mock",
        source_path="twitter_mock/src/utils/mockData.js",
        current_state_key_prefix="x_clone_state",
        initial_state_key_prefix="x_clone_initialState",
        hub_port_offset=84,
    ),
    CuaWebApp(
        app_key="WECHAT",
        app_dir="wechat_mock",
        source_path="wechat_mock/src/utils/storage.js",
        current_state_key_prefix="wechat_mock_data",
        initial_state_key_prefix="wechat_mock_data_initialState",
        hub_port_offset=88,
    ),
)
DIRECT_WEB_APPS_BY_KEY = {app.app_key: app for app in DIRECT_WEB_APPS}
DIRECT_WEB_APP_KEYS = frozenset(DIRECT_WEB_APPS_BY_KEY)


def get_direct_web_app(app_key: str) -> CuaWebApp:
    try:
        return DIRECT_WEB_APPS_BY_KEY[app_key]
    except KeyError as exc:
        raise ValueError(f"Unsupported CUA direct web app: {app_key!r}") from exc
