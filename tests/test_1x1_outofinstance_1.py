"""1 instance x 1 context: OutOfInstance scenario #1 -- capacity(=1) full ->
one more start is rejected, cleanly, with no side effects on the registry.

Full visibility, same style as test_1x1_success_3.py: gateway/instance are
real subprocesses, master is a single real `uvicorn.Server` hosted in this
test process so its registry can be inspected directly, plus a transport
hook showing the real master<->instance HTTP calls.

`OutOfInstanceError` is retryable=True (503), so gateway retries internally
before giving up. To keep the rejected case fast, this test uses a SHORT
overall per-request deadline (`gateway.verl_timeout - deadline_margin`)
while keeping `process_timeout.allocate` generous enough for a real
Playwright allocate to still succeed on the first (successful) session.
"""

from __future__ import annotations

import httpx
import pytest

from conftest import make_task_row, patch_gateway_transport_logging

REQUEST_TIMEOUT = 30.0
TASK_ID = "outofinstance-1x1-1"

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
async def test_out_of_instance_rejects_when_full(master_and_gateway_stack, static_site_url):
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

    _dump_registry("초기 상태", master_service)
    _dump_gateway("초기 상태", gateway_service)

    with patch_gateway_transport_logging():
        async with httpx.AsyncClient() as client:
            # 세션 1이 capacity(=1)를 다 채움
            start1 = await _post(
                client, gateway_url, {"session_id": 1, "task_id": TASK_ID, "op": "start"}
            )
            assert start1.status_code == 200, start1.text
            start1_body = start1.json()
            assert start1_body["status"] == "ok", start1_body
            _dump_registry("세션1 start 이후 (자리 다 참)", master_service)
            _dump_gateway("세션1 start 이후", gateway_service)

            # 세션 2는 자리가 없어서 거절되어야 한다. OutOfInstanceError는
            # retryable=True라 gateway가 내부적으로 재시도하다가, 짧게 잡아둔
            # 전체 데드라인(verl_timeout - deadline_margin = 10초)을 넘기면
            # TimeOutError로 포기하고 에러 응답을 돌려준다.
            start2 = await _post(
                client, gateway_url, {"session_id": 2, "task_id": TASK_ID, "op": "start"}
            )
            assert start2.status_code == 200, start2.text  # gateway는 항상 200, 결과는 body의 status로 구분
            start2_body = start2.json()
            assert start2_body["status"] == "error", start2_body
            assert start2_body["error_type"] == "TIMEOUT", start2_body
            _dump_registry("세션2 거절 이후 (부작용 없는지 확인)", master_service)
            _dump_gateway("세션2 거절 이후 (세션2 흔적 없는지 확인)", gateway_service)

            # 거절된 시도가 registry에 흔적을 안 남겨야 한다: 여전히 세션1의
            # lease 하나만 있어야 하고, capacity도 그대로 1이어야 함.
            assert len(master_service.registry._lease) == 1
            assert master_service.registry._slots[0]._allocated_contexts == 1
            assert len(master_service.registry._pending_releases) == 0
            # gateway 쪽 session_states에도 세션2의 흔적이 남으면 안 됨
            # (reserve_session 이후 실패 시 end_session으로 정리되는지 확인).
            assert list(gateway_service._session_registry.session_states.keys()) == [1]
