from surfgym_contracts.task import CuaStateSource
from surfgym_runtime.gateway.service import _cua_snapshot_criteria


def test_cua_snapshot_criteria_reads_sid_scoped_browser_keys():
    criteria = _cua_snapshot_criteria(
        CuaStateSource(
            app_base="http://127.0.0.1:8151",
            sid="candidate",
            current_state_key="instacart_mock_state_candidate",
            initial_state_key="instacart_mock_initialState_candidate",
        )
    )

    assert criteria.website_id == "_"
    assert criteria.value is None
    assert "localStorage.getItem" in criteria.script
    assert 'read("instacart_mock_state_candidate")' in criteria.script
    assert 'read("instacart_mock_initialState_candidate")' in criteria.script
