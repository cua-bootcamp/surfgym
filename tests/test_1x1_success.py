"""1 instance x 1 context: happy-path lifecycle (start -> action -> reward -> release).

Every server (gateway, master, instance) is launched as a real subprocess by
the `wavepool_stack` fixture in conftest.py -- no fakes, no source
modification. `pytest tests/test_1x1_success.py` is enough to run this.
"""

from __future__ import annotations

import time

import httpx
import pytest

from conftest import make_task_row

REQUEST_TIMEOUT = 30.0
TASK_ID = "success-1x1"


def _post(gateway_url: str, body: dict) -> dict:
    response = httpx.post(gateway_url, json=body, timeout=REQUEST_TIMEOUT)
    assert response.status_code == 200, response.text
    return response.json()


def test_success_scenario(wavepool_stack, static_site_url):
    gateway_url = wavepool_stack(
        task_rows=[
            make_task_row(task_id=TASK_ID, website_url=static_site_url, title="Test Page")
        ],
        instances=1,
        contexts_per_instance=1,
    )

    # start
    start_body = _post(
        gateway_url, {"session_id": 1, "task_id": TASK_ID, "op": "start"}
    )
    assert start_body["status"] == "ok", start_body

    # action (WAIT is a harmless no-op command, no coordinates needed)
    action_body = _post(
        gateway_url,
        {
            "session_id": 1,
            "task_id": TASK_ID,
            "op": "action",
            "actions": [{"action_type": "WAIT"}],
        },
    )
    assert action_body["status"] == "ok", action_body

    # reward: title criteria should match -> reward 1.0
    reward_body = _post(
        gateway_url, {"session_id": 1, "task_id": TASK_ID, "op": "reward"}
    )
    assert reward_body["status"] == "ok", reward_body
    assert reward_body["reward"] == 1.0, reward_body

    # release happens asynchronously (gateway ReleaseWorker -> master
    # pending-release loop -> instance). Confirm it actually completes by
    # polling a brand-new session until the just-freed slot becomes
    # available again (capacity is 1, so this only succeeds once release
    # has actually gone through).
    _assert_slot_freed_eventually(gateway_url, task_id=TASK_ID, timeout=15.0)


def _assert_slot_freed_eventually(gateway_url: str, *, task_id: str, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    last_body: dict | None = None

    while time.monotonic() < deadline:
        response = httpx.post(
            gateway_url,
            json={"session_id": 2, "task_id": task_id, "op": "start"},
            timeout=REQUEST_TIMEOUT,
        )
        body = response.json()
        last_body = body

        if response.status_code == 200 and body.get("status") == "ok":
            return

        time.sleep(0.5)

    pytest.fail(f"Slot was not freed by release within {timeout}s; last response: {last_body}")
