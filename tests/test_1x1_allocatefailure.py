"""1 instance x 1 context: Allocate Failure scenario -- instance is ALIVE,
but the specific allocate attempt fails (task's website is unreachable, so
Playwright's page navigation fails inside `PlaywrightBrowserWorker.create()`,
which wraps it as `CreateFailed`, retryable=True).

This is a different failure mode from OutOfInstance: there,
`reserve_lease()` fails before ever touching instance (no side effects at
all). Here, `reserve_lease()` SUCCEEDS (capacity was available) and master
genuinely calls instance, which genuinely tries and fails. Master's
`allocate()` reacts to that failure the same way it does to a normal
`release()`: it calls `enqueue_release()` so the failed lease goes through
the exact same recovery path (`release_all()` -> instance's `/release`).

Because instance is alive, `worker.delete()` on a context_id that was never
actually created just returns cleanly (see instance/service.py's
`_mark_closing`), so `release_all()` succeeds and the slot is freed --
unlike the "instance completely unreachable" variant (not covered here),
where `release_all()`'s own release call would ALSO fail forever, leaking
the slot permanently. The point of this test is to confirm that repeated
allocate failures against a genuinely-alive-but-erroring instance do NOT
accumulate in master's registry, in contrast to that permanent-leak case.

Full visibility, same style as test_1x1_success_3.py: instance is a real
subprocess, gateway+master are both real `uvicorn.Server`s hosted in this
test process (registry + gateway session_states + both transport layers all
inspectable).
"""

from __future__ import annotations

import asyncio
import time

import httpx
import pytest

from conftest import _free_port, make_task_row, patch_gateway_transport_logging

REQUEST_TIMEOUT = 30.0
TASK_ID = "allocatefailure-1x1"

# Same short-deadline setup as the OutOfInstance tests: `CreateFailed` is
# also retryable=True, so gateway retries internally the same way. Every
# process_timeout.X value must stay comfortably below the overall deadline
# (verl_timeout - deadline_margin), or the retry loop's own floor check
# rejects even a legitimate first attempt. See gateway/service.py's
# `_run_with_retry`.
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


GOOD_TASK_ID = "allocatefailure-1x1-recovery"


@pytest.mark.asyncio
async def test_allocate_failure_does_not_leak_capacity(master_and_gateway_stack, static_site_url):
    # A port nobody is listening on: Playwright's page.goto() against this
    # will fail immediately (connection refused), causing
    # PlaywrightBrowserWorker.create() to raise CreateFailed for every
    # attempt -- deterministically, without touching any source file.
    dead_url = f"http://127.0.0.1:{_free_port()}/"

    stack = await master_and_gateway_stack(
        task_rows=[
            make_task_row(task_id=TASK_ID, website_url=dead_url, title="unreachable"),
            make_task_row(
                task_id=GOOD_TASK_ID, website_url=static_site_url, title="Test Page"
            ),
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
            # website가 죽어있어서 매 시도마다 CreateFailed. gateway가 짧게
            # 잡아둔 데드라인(10초) 동안 내부적으로 여러 번 재시도하다가
            # 결국 TimeOutError로 포기한다.
            start1 = await _post(
                client, gateway_url, {"session_id": 1, "task_id": TASK_ID, "op": "start"}
            )
            assert start1.status_code == 200, start1.text
            start1_body = start1.json()
            assert start1_body["status"] == "error", start1_body
            assert start1_body["error_type"] == "TIMEOUT", start1_body
            _dump_registry("세션1 최종 실패 직후", master_service)
            _dump_gateway("세션1 최종 실패 직후", gateway_service)

            # instance는 살아있으므로, 실패한 시도마다 곧바로 release_all이
            # 정리해준다 -- 여러 번 실패했어도 registry에 쌓인 게 없어야 한다
            # (instance가 완전히 죽어있는 경우와 대비되는 지점). release_all은
            # 자기 자신의 wakeup/10초 주기로 도므로, 마지막 실패 직후엔 아직
            # 정리 전일 수 있어 짧게 폴링한다 (await asyncio.sleep이어야 함 --
            # time.sleep을 쓰면 master의 release_loop가 의존하는 이
            # 이벤트루프 자체가 멈춰서 영원히 안 끝난다).
            deadline = time.monotonic() + 15.0
            while time.monotonic() < deadline:
                if (
                    not master_service.registry._lease
                    and not master_service.registry._pending_releases
                ):
                    break
                await asyncio.sleep(0.2)
            else:
                pytest.fail(
                    "registry still holds leftover leases/pending releases "
                    "after repeated allocate failures -- capacity leaked"
                )
            _dump_registry("정리 완료 확인 (누수 없음)", master_service)
            assert master_service.registry._slots[0]._allocated_contexts == 0

            # gateway 쪽도 실패한 세션의 흔적이 안 남아야 한다.
            assert gateway_service._session_registry.session_states == {}

            # 자리가 진짜로 완전히 비었으니, 정상적인(살아있는 website) task로
            # 새 세션을 시작하면 성공해야 한다 -- capacity가 실제로 재사용
            # 가능한 상태임을 확인.
            start2 = await _post(
                client, gateway_url, {"session_id": 2, "task_id": GOOD_TASK_ID, "op": "start"}
            )
            assert start2.status_code == 200, start2.text
            start2_body = start2.json()
            assert start2_body["status"] == "ok", start2_body
            _dump_registry("정상 task로 재사용 성공", master_service)
            _dump_gateway("정상 task로 재사용 성공", gateway_service)
            assert len(master_service.registry._lease) == 1
            assert master_service.registry._slots[0]._allocated_contexts == 1
