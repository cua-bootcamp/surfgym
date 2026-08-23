import json

from surfgym_contracts.task import CuaEvaluation
from surfgym_task.cua.bundle_store import Bundle, read_bundles
from surfgym_task.cua.import_task import import_direct_web_task, write_task_assets


def test_instacart_import_records_sid_scoped_browser_state(tmp_path):
    bundle = Bundle(
        task_id="instacart-candidate",
        task_json=json.dumps(
            {
                "id": "instacart-candidate",
                "instruction": "Add two products and choose a delivery slot.",
                "app_type": "instacart_mock",
            }
        ),
        initial_setup="""
import requests
requests.post(
    '__CUA_GYM_INSTACART_URL__/post?sid=source-sid',
    json={'action': 'set', 'state': {'cart': [], 'deliveryAddressId': 'addr_1'}},
)
""",
        reward="BASE_URL = '__CUA_GYM_INSTACART_URL__'\nprint('REWARD: 0.0')",
    )

    imported = import_direct_web_task(bundle, app_url="http://127.0.0.1:8051/")
    task_dir = write_task_assets(imported, tmp_path)

    assert imported.task.website[0].url == "http://127.0.0.1:8051/?sid=instacart-candidate"
    assert isinstance(imported.task.evaluation, CuaEvaluation)
    assert imported.task.evaluation.states[0].current_state_key == (
        "instacart_mock_state_instacart-candidate"
    )
    assert imported.task.evaluation.states[0].app_base == "http://127.0.0.1:8051"
    assert "__CUA_GYM_INSTACART_URL__" not in imported.task.evaluation.reward_script
    assert "http://127.0.0.1:8051" in imported.task.evaluation.reward_script
    stored = json.loads(
        (task_dir / "initial_states" / "INSTACART" / "instacart-candidate.json").read_text()
    )
    assert stored["stored_state"] == {"cart": [], "deliveryAddressId": "addr_1"}


def test_bundle_store_reads_extracted_json_bundle_map(tmp_path):
    archive = tmp_path / "bundles.json"
    archive.write_text(
        json.dumps(
            {
                "instacart-candidate": {
                    "task.json": '{"app_type": "instacart_mock"}',
                    "initial_setup.py": "print('setup')",
                    "reward.py": "print('REWARD: 0.0')",
                }
            }
        ),
        encoding="utf-8",
    )

    bundles = read_bundles(archive, ["instacart-candidate"])

    assert bundles["instacart-candidate"].complete
    assert bundles["instacart-candidate"].reward == "print('REWARD: 0.0')"
