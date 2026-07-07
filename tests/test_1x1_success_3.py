"""1 instance x 1 context: happy-path lifecycle, with full visibility --
gateway's real HTTP responses, gateway's own internal session_states,
master's internal registry, master<->instance transport, and gateway<->
upstream transport, all at once.

- instance: real subprocess (real Playwright)
- gateway AND master: both hosted as real `uvicorn.Server`s in-process
  (asyncio tasks on this test's own event loop), so both are inspectable
  directly via closure reflection.

An earlier attempt ran all three servers in-process (gateway+master+instance,
including Playwright) and segfaulted on Windows. Keeping instance as a
subprocess (no Playwright in this process) while hosting gateway+master
in-process was validated separately and is what `master_and_gateway_stack`
now does. No source file is modified.

IMPORTANT: because gateway/master share this test's own event loop (their
background tasks -- gateway's nothing async-loop-bound directly, but
master's `release_loop` -- need that loop to ever run), every call this test
makes must be non-blocking (`await asyncio.sleep`, `httpx.AsyncClient`),
never a blocking call (`time.sleep`, sync `httpx.post`).
"""

from __future__ import annotations

import asyncio
import time

import httpx
import pytest

from conftest import make_task_row, patch_gateway_transport_logging

REQUEST_TIMEOUT = 30.0
TASK_ID = "success-1x1-gateway-and-registry"


async def _post(client: httpx.AsyncClient, gateway_url: str, body: dict) -> dict:
    response = await client.post(gateway_url, json=body, timeout=REQUEST_TIMEOUT)
    assert response.status_code == 200, response.text
    return response.json()


async def _log_transport_request(request) -> None:
    print(f"[transport→instance] {request.method} {request.url}")


async def _log_transport_response(response) -> None:
    await response.aread()
    print(f"[transport←instance] {response.status_code} {response.text}")


def _dump_registry(label: str, master_service) -> None:
    registry = master_service.registry
    print(
        f"[registry:{label}] "
        f"lease={list(registry._lease.keys())} "
        f"pending_releases={list(registry._pending_releases.keys())} "
        f"slot0.allocated={registry._slots[0]._allocated_contexts}"
    )


def _dump_gateway(label: str, gateway_service) -> None:
    session_states = gateway_service._session_registry.session_states
    queue_size = gateway_service._release_worker._queue.qsize()
    print(
        f"[gateway:{label}] "
        f"session_states={list(session_states.keys())} "
        f"release_queue_size={queue_size}"
    )


@pytest.mark.asyncio
async def test_success_scenario_gateway_and_registry(master_and_gateway_stack, static_site_url):
    stack = await master_and_gateway_stack(
        task_rows=[
            make_task_row(task_id=TASK_ID, website_url=static_site_url, title="Test Page")
        ],
        contexts_per_instance=1,
    )
    gateway_url = stack["gateway_url"]
    master_service = stack["master_service"]
    gateway_service = stack["gateway_service"]
    # master.client is InstanceClient, which holds the real httpx.AsyncClient
    # actually talking to the real instance subprocess. Hooking it here is
    # only possible because master runs in *this* process, not a subprocess.
    master_service.client.client.event_hooks = {
        "request": [_log_transport_request],
        "response": [_log_transport_response],
    }

    # registry.enqueue_release() is the exact line that adds an entry to
    # _pending_releases. None of our _dump_registry() snapshots happen to
    # land on that precise moment (it's a brief window between "gateway sent
    # /release" and "our next dump"), so wrap it here to log the instant it
    # actually runs. Only possible because registry lives in this process.
    _original_enqueue_release = master_service.registry.enqueue_release

    async def _logged_enqueue_release(context_id, request=None):
        _dump_registry(f"enqueue_release({context_id}) 호출 직전", master_service)
        result = await _original_enqueue_release(context_id, request)
        _dump_registry(f"enqueue_release({context_id}) 완료 직후", master_service)
        return result

    master_service.registry.enqueue_release = _logged_enqueue_release

    _dump_registry("초기 상태", master_service)
    _dump_gateway("초기 상태", gateway_service)

    with patch_gateway_transport_logging():
        async with httpx.AsyncClient() as client:
            start_body = await _post(
                client, gateway_url, {"session_id": 1, "task_id": TASK_ID, "op": "start"}
            )
            assert start_body["status"] == "ok", start_body
            _dump_registry("start 이후", master_service)
            _dump_gateway("start 이후", gateway_service)

            action_body = await _post(
                client,
                gateway_url,
                {
                    "session_id": 1,
                    "task_id": TASK_ID,
                    "op": "action",
                    "actions": [{"action_type": "WAIT"}],
                },
            )
            assert action_body["status"] == "ok", action_body

            reward_body = await _post(
                client, gateway_url, {"session_id": 1, "task_id": TASK_ID, "op": "reward"}
            )
            assert reward_body["status"] == "ok", reward_body
            assert reward_body["reward"] == 1.0, reward_body
            _dump_registry("reward 이후 (release 큐잉 직후)", master_service)
            _dump_gateway("reward 이후 (session은 이미 지워짐)", gateway_service)

            # release는 gateway ReleaseWorker -> master pending_releases ->
            # release_loop 순으로 비동기 처리된다. registry를 직접 폴링해서
            # 끝났는지 확인한다 (await asyncio.sleep이어야 함 -- time.sleep을
            # 쓰면 master의 release_loop가 의존하는 이 이벤트루프 자체가 멈춰서
            # 영원히 안 끝남).
            deadline = time.monotonic() + 15.0
            while time.monotonic() < deadline:
                if (
                    not master_service.registry._lease
                    and not master_service.registry._pending_releases
                ):
                    break
                await asyncio.sleep(0.2)
            else:
                pytest.fail("release did not complete within 15s (registry never cleared)")
            _dump_registry("release 완료 확인", master_service)
            assert master_service.registry._slots[0]._allocated_contexts == 0

            start2_body = await _post(
                client, gateway_url, {"session_id": 2, "task_id": TASK_ID, "op": "start"}
            )
            assert start2_body["status"] == "ok", start2_body
            _dump_registry("두 번째 start 성공", master_service)
            _dump_gateway("두 번째 start 성공", gateway_service)
            assert len(master_service.registry._lease) == 1
