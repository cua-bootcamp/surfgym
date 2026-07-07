"""1 instance x 1 context: OutOfInstance scenario #2.

1. start (session 1) -> allocate 성공
2. release (session 1의 reward -> 실제 반납 완료까지 확인)
3. allocate (session 2) -> 성공 (자리가 정말 비었는지)
4. allocate (session 3) -> OutOfInstance (capacity=1이라 session 2가 이미 그
   자리를 다시 채웠으므로, release->allocate 한 번으로 자리가 두 번 이상
   내줘지지 않는지 확인)

Full visibility, same style as test_1x1_success_3.py: gateway/instance are
real subprocesses, master is a single real `uvicorn.Server` hosted in this
test process so its registry can be inspected directly, plus a transport
hook showing the real master<->instance HTTP calls.
"""

from __future__ import annotations

import asyncio
import time

import httpx
import pytest

from conftest import make_task_row, patch_gateway_transport_logging

REQUEST_TIMEOUT = 30.0
TASK_ID = "outofinstance-1x1-2"

# Every process_timeout.X value here doubles as `min_attempt_time` for that
# operation's own retry loop (see gateway/service.py's `_run_with_retry`):
# `deadline.require_remaining(min_attempt_time)` fails immediately, before
# even trying once, unless the request's overall remaining budget
# (verl_timeout - deadline_margin) is still bigger than that value. A single
# `start` request spends this SAME overall budget across allocate *and*
# screenshot back to back, so every value here must stay comfortably below
# the overall deadline -- not just `allocate`.
PROCESS_TIMEOUT = {
    "allocate": 3.0,
    "release": 8.0,
    "screenshot": 2.0,
    "observe": 2.0,
    "execute": 2.0,
    "layer_gap": 0.5,
}
GATEWAY_OVERRIDES = {"verl_timeout": 11.0, "deadline_margin": 1.0}  # overall deadline = 10.0s


async def _post(client: httpx.AsyncClient, gateway_url: str, body: dict) -> httpx.Response:
    return await client.post(gateway_url, json=body, timeout=REQUEST_TIMEOUT)


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
    print(f"[gateway:{label}] session_states={list(session_states.keys())}")


@pytest.mark.asyncio
async def test_out_of_instance_recovers_after_release(master_and_gateway_stack, static_site_url):
    stack = await master_and_gateway_stack(
        task_rows=[
            make_task_row(task_id=TASK_ID, website_url=static_site_url, title="Test Page")
        ],
        contexts_per_instance=1,
        process_timeout=PROCESS_TIMEOUT,
        gateway_overrides=GATEWAY_OVERRIDES,
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

    # registry.enqueue_release()가 실제로 _pending_releases에 추가하는 바로 그
    # 순간을 잡는다. 우리가 고른 _dump_registry 시점들은 이 찰나를 놓칠 수
    # 있어서 (gateway가 release 요청을 보낸 것과 master가 그걸 처리 완료하는
    # 것 사이엔 진짜 시간차가 있음), enqueue_release 자체를 감싸서 직전/직후를
    # 찍는다. master가 in-process라서 가능.
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
            # 1. start -> allocate 성공
            start1 = await _post(
                client, gateway_url, {"session_id": 1, "task_id": TASK_ID, "op": "start"}
            )
            start1_body = start1.json()
            assert start1_body["status"] == "ok", start1_body
            _dump_registry("1. 세션1 start 성공 (자리 다 참)", master_service)
            _dump_gateway("1. 세션1 start 성공", gateway_service)
            assert len(master_service.registry._lease) == 1
            assert master_service.registry._slots[0]._allocated_contexts == 1

            # 2. release: reward로 세션1을 끝내서 실제 반납을 트리거하고,
            # registry를 직접 폴링해서 진짜로 끝났는지 확인한다 (await
            # asyncio.sleep이어야 함 -- time.sleep을 쓰면 master의 release_loop가
            # 의존하는 이 이벤트루프 자체가 멈춰서 영원히 안 끝난다).
            reward1 = await _post(
                client, gateway_url, {"session_id": 1, "task_id": TASK_ID, "op": "reward"}
            )
            reward1_body = reward1.json()
            assert reward1_body["status"] == "ok", reward1_body
            assert reward1_body["reward"] == 1.0, reward1_body
            _dump_registry("2. 세션1 reward 이후 (release 큐잉 직후)", master_service)
            _dump_gateway("2. 세션1 reward 이후 (session은 이미 지워짐)", gateway_service)

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
            _dump_registry("2. release 완료 확인 (자리 진짜로 비워짐)", master_service)
            assert master_service.registry._slots[0]._allocated_contexts == 0

            # 3. allocate (session 2) -> 성공
            start2 = await _post(
                client, gateway_url, {"session_id": 2, "task_id": TASK_ID, "op": "start"}
            )
            start2_body = start2.json()
            assert start2_body["status"] == "ok", start2_body
            _dump_registry("3. 세션2 start 성공", master_service)
            _dump_gateway("3. 세션2 start 성공", gateway_service)
            assert len(master_service.registry._lease) == 1
            assert master_service.registry._slots[0]._allocated_contexts == 1

            # 4. allocate (session 3) -> OutOfInstance. capacity=1이라 세션2가
            # 그 자리를 다시 채웠으므로, release->allocate 한 번으로 자리가 두
            # 번 이상 내줘지지 않는지 확인.
            start3 = await _post(
                client, gateway_url, {"session_id": 3, "task_id": TASK_ID, "op": "start"}
            )
            start3_body = start3.json()
            assert start3_body["status"] == "error", start3_body
            assert start3_body["error_type"] == "TIMEOUT", start3_body
            _dump_registry("4. 세션3 거절 확인 (OutOfInstance)", master_service)
            _dump_gateway("4. 세션3 거절 확인 (세션3 흔적 없는지)", gateway_service)
            assert len(master_service.registry._lease) == 1
            assert master_service.registry._slots[0]._allocated_contexts == 1
            assert list(gateway_service._session_registry.session_states.keys()) == [2]
