from pathlib import Path
from runpy import run_path

import pytest
from surfgym_task.cua.state_contracts import get_state_contract
from surfgym_task.cua.webapp_manifest import (
    CUA_GYM_HUB_REVISION,
    DIRECT_WEB_APP_KEYS,
    get_direct_web_app,
)

PINNED_CUA_GYM_HUB_REVISION = "53205689c3d88078c1375f76466d5bd799478828"
_REPO_ROOT = Path(__file__).resolve().parents[3]
_CADDY_MODULE = run_path(str(_REPO_ROOT / "scripts/cua_hub_deploy/gen_caddyfile.py"))
assign_ports = _CADDY_MODULE["assign_ports"]
render = _CADDY_MODULE["render"]

_BATCH_A_CONTRACTS = {
    "GITHUB": ("github_mock", "src/lib/mockData.js", "gitmock_state", "gitmock_initialState", 36),
    "HUBSPOT": ("hubspot_mock", "src/data/mockData.js", "hubspot_mock_db", "hubspot_mock_db_initial", 50),
    "LINKEDIN": ("linkedin_mock", "src/data/mockData.js", "linkedin_mock_state", "linkedin_mock_initialState", 57),
    "SHOPIFY_ADMIN": ("shopify_admin_mock", "src/lib/seed.js", "shopify_mock_state", "shopify_mock_initialState", 77),
    "TRELLO": ("trello_mock", "src/utils/mockData.js", "trello_clone_state", "trello_clone_initialState", 82),
    "TWITTER": ("twitter_mock", "src/utils/mockData.js", "x_clone_state", "x_clone_initialState", 84),
}

_BATCH_B_CONTRACTS = {
    "GMAIL": ("gmail_mock", "src/data/mockData.js", "xmail-clone-state", "xmail-clone-initialState", 38),
    "JIRA": ("jira_mock", "src/utils/mockData.ts", "jira_clone_state", "jira_clone_initialState", 53),
    "MICROSOFT_TEAMS": ("microsoft_teams_mock", "src/utils/dataManager.js", "teamsState", "teamsInitialState", 62),
    "STRIPE_DASHBOARD": ("stripe_dashboard_mock", "src/utils/dataManager.js", "stripe_dashboard_state", "stripe_dashboard_initialState", 79),
    "WECHAT": ("wechat_mock", "src/utils/storage.js", "wechat_mock_data", "wechat_mock_data_initialState", 88),
}


@pytest.mark.parametrize(
    ("app_key", "expected"),
    _BATCH_A_CONTRACTS.items(),
)
def test_batch_a_manifest_and_state_contract(
    app_key: str,
    expected: tuple[str, str, str, str, int],
) -> None:
    app_dir, relative_source, current_prefix, initial_prefix, port_offset = expected
    app = get_direct_web_app(app_key)
    contract = get_state_contract(app_dir)

    assert app.app_dir == app_dir
    assert app.source_path == f"{app_dir}/{relative_source}"
    assert app.current_state_key("episode-1") == f"{current_prefix}_episode-1"
    assert app.initial_state_key("episode-1") == f"{initial_prefix}_episode-1"
    assert app.hub_port_offset == port_offset
    assert contract.state_backend == "browser_local_storage"
    assert contract.initial_state_endpoint == "/state"
    assert contract.initial_state_response_field == "stored_state"
    assert contract.source_path == app.source_path
    assert contract.in_direct_web_dataset is True


def test_batch_a_uses_pinned_caddy_ports_and_namespaces() -> None:
    app_dirs = [expected[0] for expected in _BATCH_A_CONTRACTS.values()]
    ports = assign_ports(app_dirs, start_port=8000)

    assert ports == {
        expected[0]: 8000 + expected[4]
        for expected in _BATCH_A_CONTRACTS.values()
    }

    caddyfile = render(Path("/apps"), Path("/states"), ports)
    for app_key, expected in _BATCH_A_CONTRACTS.items():
        app_dir, _, _, _, port_offset = expected
        block = caddyfile[caddyfile.index(f":{8000 + port_offset} {{") :]
        assert f"root * /apps/{app_dir}/dist" in block
        assert f"root * /states/{app_key}" in block


@pytest.mark.parametrize(
    ("app_key", "expected"),
    _BATCH_B_CONTRACTS.items(),
)
def test_batch_b_manifest_and_state_contract(
    app_key: str,
    expected: tuple[str, str, str, str, int],
) -> None:
    app_dir, relative_source, current_prefix, initial_prefix, port_offset = expected
    app = get_direct_web_app(app_key)
    contract = get_state_contract(app_dir)

    assert app.app_dir == app_dir
    assert app.source_path == f"{app_dir}/{relative_source}"
    assert app.current_state_key("episode-1") == f"{current_prefix}_episode-1"
    assert app.initial_state_key("episode-1") == f"{initial_prefix}_episode-1"
    assert app.hub_port_offset == port_offset
    assert contract.state_backend == "browser_local_storage"
    assert contract.initial_state_endpoint == "/state"
    assert contract.initial_state_response_field == "stored_state"
    assert contract.source_path == app.source_path
    assert contract.in_direct_web_dataset is True


def test_batch_b_uses_pinned_caddy_ports_and_namespaces() -> None:
    app_dirs = [expected[0] for expected in _BATCH_B_CONTRACTS.values()]
    ports = assign_ports(app_dirs, start_port=8000)

    assert ports == {
        expected[0]: 8000 + expected[4]
        for expected in _BATCH_B_CONTRACTS.values()
    }

    caddyfile = render(Path("/apps"), Path("/states"), ports)
    for app_key, expected in _BATCH_B_CONTRACTS.items():
        app_dir, _, _, _, port_offset = expected
        block = caddyfile[caddyfile.index(f":{8000 + port_offset} {{") :]
        assert f"root * /apps/{app_dir}/dist" in block
        assert f"root * /states/{app_key}" in block


def test_instagram_manifest_uses_verified_upstream_contract() -> None:
    app = get_direct_web_app("INSTAGRAM")

    assert CUA_GYM_HUB_REVISION == PINNED_CUA_GYM_HUB_REVISION
    assert app.app_dir == "instagram_mock"
    assert app.source_path == "instagram_mock/src/utils/mockData.js"
    assert app.current_state_key("episode-1") == "instagram_mock_state_episode-1"
    assert app.initial_state_key("episode-1") == "instagram_mock_initialState_episode-1"
    assert app.hub_port_offset == 52
    assert {"INSTACART", "INSTAGRAM"} <= DIRECT_WEB_APP_KEYS


def test_instagram_state_contract_is_sid_scoped_browser_storage() -> None:
    contract = get_state_contract("instagram_mock")

    assert contract.state_backend == "browser_local_storage"
    assert contract.initial_state_endpoint == "/state"
    assert contract.initial_state_response_field == "stored_state"
    assert contract.current_state_key("episode-1") == "instagram_mock_state_episode-1"
    assert contract.initial_state_key("episode-1") == "instagram_mock_initialState_episode-1"
    assert contract.source_path == "instagram_mock/src/utils/mockData.js"
    assert contract.in_direct_web_dataset is True


def test_instagram_uses_pinned_caddy_port_and_state_namespace() -> None:
    ports = assign_ports(["instacart_mock", "instagram_mock"], start_port=8000)

    assert ports == {"instacart_mock": 8051, "instagram_mock": 8052}

    caddyfile = render(Path("/apps"), Path("/states"), ports)
    instagram_block = caddyfile[caddyfile.index(":8052 {") :]

    assert "root * /apps/instagram_mock/dist" in instagram_block
    assert "root * /states/INSTAGRAM" in instagram_block
    assert "rewrite * /{http.request.uri.query.sid}.json" in instagram_block


def test_pinterest_manifest_uses_verified_upstream_contract() -> None:
    app = get_direct_web_app("PINTEREST")

    assert CUA_GYM_HUB_REVISION == PINNED_CUA_GYM_HUB_REVISION
    assert app.app_dir == "pinterest_mock"
    assert app.source_path == "pinterest_mock/src/store/initialData.js"
    assert app.current_state_key("episode-1") == "pinteract_state_episode-1"
    assert app.initial_state_key("episode-1") == "pinteract_initialState_episode-1"
    assert app.hub_port_offset == 70
    assert {"INSTACART", "INSTAGRAM", "PINTEREST"} <= DIRECT_WEB_APP_KEYS


def test_pinterest_state_contract_is_sid_scoped_browser_storage() -> None:
    contract = get_state_contract("pinterest_mock")

    assert contract.state_backend == "browser_local_storage"
    assert contract.initial_state_endpoint == "/state"
    assert contract.initial_state_response_field == "stored_state"
    assert contract.current_state_key("episode-1") == "pinteract_state_episode-1"
    assert contract.initial_state_key("episode-1") == "pinteract_initialState_episode-1"
    assert contract.source_path == "pinterest_mock/src/store/initialData.js"
    assert contract.in_direct_web_dataset is True


def test_pinterest_uses_pinned_caddy_port_and_state_namespace() -> None:
    ports = assign_ports(
        ["instacart_mock", "instagram_mock", "pinterest_mock"], start_port=8000
    )

    assert ports == {
        "instacart_mock": 8051,
        "instagram_mock": 8052,
        "pinterest_mock": 8070,
    }

    caddyfile = render(Path("/apps"), Path("/states"), ports)
    pinterest_block = caddyfile[caddyfile.index(":8070 {") :]

    assert "root * /apps/pinterest_mock/dist" in pinterest_block
    assert "root * /states/PINTEREST" in pinterest_block
    assert "rewrite * /{http.request.uri.query.sid}.json" in pinterest_block
