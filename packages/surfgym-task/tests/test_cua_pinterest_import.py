import copy
import json

from surfgym_contracts.task import CuaEvaluation
from surfgym_runtime.support.cua_evaluator import CuaSnapshot, evaluate_cua_reward
from surfgym_task.cua.bundle_store import Bundle
from surfgym_task.cua.import_task import import_direct_web_task, write_task_assets
from surfgym_task.web import WEB_STATE_RESET_HOOK

CANARY_TASK_ID = "fcdc1975-e1e6-5b5d-a35a-1d96824f752e"


def test_pinterest_search_canary_import_preserves_evaluator_contract(tmp_path):
    bundle = Bundle(
        task_id=CANARY_TASK_ID,
        task_json=json.dumps(
            {
                "id": CANARY_TASK_ID,
                "instruction": "Search for some pasta recipe ideas.",
                "app_type": "pinterest_mock",
            }
        ),
        initial_setup="""
import requests
requests.post(
    '__CUA_GYM_PINTEREST_URL__/post?sid=source-sid',
    json={
        'action': 'set',
        'state': {
            'searchQuery': '',
            'searchFilters': [],
            'selectedCategory': None,
        },
    },
)
""",
        reward="""
import requests
with open('/tmp/task_web_sid') as sid_file:
    sid = sid_file.read().strip()
data = requests.get(f'__CUA_GYM_PINTEREST_URL__/go?sid={sid}').json()
current_query = (data.get('current_state') or {}).get('searchQuery', '')
contains_pasta = bool(current_query) and 'pasta' in current_query.lower()
changed_from_baseline = current_query != '' and bool(current_query)
score = (0.6 if contains_pasta else 0.0) + (0.4 if changed_from_baseline else 0.0)
print(f"REWARD: {score}")
""",
    )

    imported = import_direct_web_task(bundle, app_url="http://127.0.0.1:8070/")
    task_dir = write_task_assets(imported, tmp_path)

    assert imported.app_key == "PINTEREST"
    assert imported.task.task_id == CANARY_TASK_ID
    assert imported.task.website[0].url == (
        f"http://127.0.0.1:8070/?sid={CANARY_TASK_ID}"
    )
    assert isinstance(imported.task.evaluation, CuaEvaluation)
    assert imported.task.evaluation.source_task_id == CANARY_TASK_ID
    assert imported.task.lifecycle_hooks.release == [WEB_STATE_RESET_HOOK]
    state_source = imported.task.evaluation.states[0]
    assert state_source.sid == CANARY_TASK_ID
    assert state_source.current_state_key == f"pinteract_state_{CANARY_TASK_ID}"
    assert state_source.initial_state_key == f"pinteract_initialState_{CANARY_TASK_ID}"
    assert state_source.app_base == "http://127.0.0.1:8070"
    assert "__CUA_GYM_PINTEREST_URL__" not in imported.task.evaluation.reward_script
    assert "http://127.0.0.1:8070/go?sid={sid}" in imported.task.evaluation.reward_script
    assert "0.6 if contains_pasta" in imported.task.evaluation.reward_script
    assert "0.4 if changed_from_baseline" in imported.task.evaluation.reward_script

    stored = json.loads(
        (task_dir / "initial_states" / "PINTEREST" / f"{CANARY_TASK_ID}.json").read_text()
    )
    assert stored["sid"] == CANARY_TASK_ID
    assert stored["stored_state"] == {
        "searchQuery": "",
        "searchFilters": [],
        "selectedCategory": None,
    }

    initial_state = stored["stored_state"]
    success_state = copy.deepcopy(initial_state)
    success_state["searchQuery"] = "pasta"
    initial_result = evaluate_cua_reward(
        imported.task.evaluation.reward_script,
        source_task_id=CANARY_TASK_ID,
        sid=CANARY_TASK_ID,
        snapshots={
            "http://127.0.0.1:8070": CuaSnapshot(
                initial_state=initial_state,
                current_state=initial_state,
            )
        },
        timeout=5.0,
    )
    success_result = evaluate_cua_reward(
        imported.task.evaluation.reward_script,
        source_task_id=CANARY_TASK_ID,
        sid=CANARY_TASK_ID,
        snapshots={
            "http://127.0.0.1:8070": CuaSnapshot(
                initial_state=initial_state,
                current_state=success_state,
            )
        },
        timeout=5.0,
    )
    assert initial_result.reward == 0.0
    assert success_result.reward == 1.0
