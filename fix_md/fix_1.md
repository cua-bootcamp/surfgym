# dev 리팩토링 이후 버그 수정 기록

`dev`(`cb46729` "feat: refactor master") 브랜치 위에서 발견하고 수정한 버그들의 기록. 각 항목은 **문제 → 원인 → 수정 → 검증** 순으로 정리했다.

## 수정 이후 검증

아래 "검증" 항목들은 두 레벨로 나뉜다.

- **유닛 테스트**: 실제 서버를 띄우지 않고, "가짜 transport"(gateway가 master/instance와 통신할 때 쓰는 통신 객체를 진짜 네트워크 호출 대신 미리 정해둔 동작만 흉내 내는 대역으로 교체한 것)를 이용해 특정 실패 상황만 재현하고 코드 로직만 빠르게 검증하는 방식. `server-test/tests/test_fixes.py`, `test_evaluator.py`, `test_registry.py`에 들어있다.
- **통합 테스트(실서버)**: 실제 master·instance 서버를 띄우고, gateway만 "고장 주입 버전"(특정 호출 한 가지만 일부러 실패시키고 나머지는 진짜 서버로 그대로 통과시키는 변형 서버, 예: `gateway_release_fault_server.py`)으로 교체해서 진짜 HTTP 통신 위에서 검증하는 방식. 어떤 테스트가 어떤 서버 조합·스크립트를 쓰는지는 [TESTS.md](server-test/TESTS.md)에 정리했다.

## 요약

| # | 문제 | 심각도 | 파일 |
|---|---|---|---|
| 1 | gateway 서버가 아예 기동되지 않음 | 치명적 | `gateway/service.py` |
| 2 | release 실패 시 재시도 없이 자리 영구 누수 | 높음 | `gateway/service.py` |
| 3 | reward 실패 시 세션·자리 영구 stuck | 높음 | `gateway/service.py` |
| 4 | 화면 밖 좌표가 500(서버 오류)으로 오분류 | 낮음 | `wavepool/instance/service.py` |
| 5 | 닫힌 컨텍스트 재사용 시 크래시 | 낮음 (방어적) | `wavepool/instance/service.py` |
| 6 | 관찰 개수 불일치 시 잘못된 만점 처리 가능 | 중간 | `support/evaluator.py` |
| 7 | LLM judge 실패가 로그 없이 0점 처리됨 | 중간 | `support/evaluator.py` |
| 8 | master 자가복구 루프가 예외 한 번에 영구 정지 | 중간 | `wavepool/master/service.py` |
| 9 | 서버 종료 시 백그라운드 태스크 미대기 | 낮음 | `wavepool/master/server.py` |
| 10 | 테스트 검증용 transport 주입 부재 | (인프라) | `gateway/service.py`, `gateway/server.py` |

---

## 1. gateway 서버가 아예 기동되지 않음

**문제**: dev 리팩토링 이후 gateway 서버가 기동 자체를 못 한다.

**원인**: `SessionState` dataclass에 `trace: list[Frame] = []`로 mutable 기본값이 직접 쓰여 있었다. Python `dataclass`는 이런 정의를 클래스 선언 시점에 막는다(모든 인스턴스가 같은 리스트를 공유하는 사고 방지):
```
ValueError: mutable default <class 'list'> for field trace is not allowed: use default_factory
```
모듈 임포트 시점에 이 예외가 터지므로, `gateway/service.py`를 import하는 순간 전체가 죽는다.

**수정**: `field(default_factory=list)`로 교체.
```python
trace: list[Frame] = field(default_factory=list)
```

**검증**: `gateway/service.py`를 직접 import해서 더 이상 죽지 않는지 확인 + `SessionState`를 두 번 만들어서 각 인스턴스의 `trace`가 서로 다른 리스트 객체인지(즉 공유되지 않는지) 확인. (`server-test/tests/test_fixes.py`)

> LGTM

---

## 2. release 실패 시 재시도 없이 자리 영구 누수

**문제**: reward 후 백그라운드로 자리를 반납(release)하는데, 이 반납이 한 번 실패하면 그냥 포기한다. master의 자리는 영구히 사용 불가 상태로 남는다.

**원인**: `_release_worker_loop`가 `self.transport.release(...)`를 **딱 한 번**만 호출한다. allocate·screenshot·observe는 전부 지수 백오프 재시도(`_run_with_retry`)로 감싸져 있는데 release만 빠져 있었다. master가 잠깐 흔들리는 일시적 장애에도 회복 불가능한 자리 누수로 이어진다.

**수정**: 다른 호출과 동일하게 `_run_with_retry`로 감싸고, 예산은 "1회 타임아웃 × 3배"로 설정 (큐에 쌓인 다른 release 작업이 오래 밀리지 않으면서 일시 장애는 흡수).
```python
_RELEASE_RETRY_BUDGET_FACTOR = 3
...
release_deadline = Deadline(
    time.monotonic() + self._release_timeout * _RELEASE_RETRY_BUDGET_FACTOR, "release"
)
self._run_with_retry(
    min_attempt_time=self._release_timeout,
    deadline=release_deadline,
    func=lambda: self.transport.release(
        deadline=release_deadline,
        context_id=state.lease.context_id,
        release_hooks=state.release_hooks,
    ),
)
```

**검증**:
- **유닛 테스트**: 가짜 transport의 release 동작을 "첫 호출은 실패, 두 번째 호출부터는 성공"으로 미리 정해두고, 재시도 로직이 실제로 두 번째 호출까지 가서 성공하는지 확인. (`server-test/tests/test_fixes.py`)
- **통합 테스트(실서버)**: 이 수정이 실제 네트워크 통신 위에서도 똑같이 동작하는지, 아래 시나리오로 확인했다.
  1. master + instance + `gateway_release_fault_server.py`(release 호출을 **처음 1번만 실패**시키고, 그 다음부터는 진짜 master로 그대로 전달하는 gateway) 세 서버를 자리(capacity) 1개짜리로 띄운다.
  2. 세션 A가 정상적으로 시작하고, reward를 요청해서 자리를 반납하려고 시도한다 → 반납 요청이 gateway의 백그라운드 재시도 로직으로 넘어간다.
  3. 이 반납 요청의 첫 시도는 고장 주입 gateway가 일부러 실패시킨다. 재시도 로직이 살아있다면 두 번째 시도에서 진짜 master로 요청이 통과되고, 자리가 정상적으로 반납된다.
  4. 세션 B가 새로 시작을 시도한다 — 자리가 1개뿐이므로, A의 자리가 진짜로 반납됐어야만 B가 시작에 성공할 수 있다.
  - 실제 로그를 보면 "release 실패(1번째 시도)" 다음 줄에 바로 "release 통과(2번째 시도)"가 찍혀 있고, 이게 세션 B가 시작을 시도하기도 전에 이미 끝나 있었다 — 즉 재시도가 실제로 동작해서 B가 시작할 시점엔 이미 자리가 비어 있었다는 뜻이다. 세션 B는 정상적으로 자리를 잡았다. (스크립트: `server-test/gateway_release_fault_server.py` + `server-test/tests/test_gateway_4.py`)

**알려진 한계**: 예산(약 15초)을 넘겨 계속 실패하면 여전히 드랍된다 — master는 이 release 요청을 받은 적이 없어 자체 복구 목록(`broken_lease`)에도 잡히지 않으므로, 그 lease는 master 장부에 영구 잔존한다. 근본 해결은 master 쪽에 반납 안 된 자리를 회수하는 reconciliation이 필요하다 (별도 이슈로 남김).

> 아예 release 아키텍쳐 바꿈. gateway > master | master > instance 를 무한 루프로 돌도록 바꿈

---

## 3. reward 실패 시 세션·자리 영구 stuck

**문제**: 채점(observe)이 실패하면 세션이 정리되지 않고 자리도 풀리지 않는다 — 같은 세션 ID로 재시도조차 못 하는 좀비 상태가 된다.

**원인**: `_handle_reward`는 `observe → reward 계산 → release 큐잉 → 세션 종료` 순서인데, 이 넷이 하나의 `try` 블록 없이 순서대로 나열돼 있었다. observe 도중 예외가 나면 그 아래 두 줄(`_release_queue.put`, `_end_session`)이 통째로 실행되지 않고 함수가 예외로 끝난다. 결과: gateway 장부(`session_states`)에 세션이 계속 "활성"으로 남고, master 자리도 영원히 안 풀린다.

**수정**: `_handle_start`가 이미 쓰고 있는 "실패해도 정리는 한다" 패턴을 그대로 적용 — `try/finally`로 감싸서 채점 성공/실패와 무관하게 정리(큐잉+세션종료)가 무조건 실행되게 함.
```python
try:
    match task.evaluation:
        case CriteriaEvaluation():
            ...
        case LLMJudgeEvaluation():
            ...
finally:
    # Reward ends the episode even when observation fails; skipping
    # cleanup here leaks both the session entry and the wavepool slot.
    self._release_queue.put(session_state)
    self._end_session(request.session_id)
```

**검증**:
- **유닛 테스트**: 가짜 transport의 observe 동작을 "항상 실패"로 정해두고, 예외가 클라이언트에 그대로 전달되는 것과 **동시에** 세션이 장부에서 지워지고 release가 큐에 들어가는지 확인. 이 수정이 정상적으로 성공하는 케이스를 망가뜨리지 않았는지도 별도로 확인. (`server-test/tests/test_fixes.py`)
- **통합 테스트(실서버)**: master + instance + `gateway_observe_fault_server.py`(observe 호출을 **항상** 실패시키는 gateway)를 띄우고, 세션 A로 시작 → reward 요청(의도적으로 실패) → 같은 session_id로 다시 시작을 시도한다. 수정 전이라면 gateway가 세션 A를 "아직 활성 상태"로 착각해서 재시작을 거부해야 하지만, 수정 후에는 재시작이 정상적으로 성공한다. 이어서 새로운 session_id(B)로도 시작해봐서 자리가 실제로 반납됐는지까지 확인했다. (스크립트: `server-test/gateway_observe_fault_server.py` + `server-test/tests/test_gateway_5.py`)

**트레이드오프**: 이 방식은 관찰이 일시 장애로 실패해도 세션을 즉시 끝낸다 — 즉 그 에피소드의 보상은 재시도로 복구할 수 없다. 자원 누수(capacity 고갈)가 보상 하나 유실보다 훨씬 치명적이므로 감내할 트레이드오프로 판단.

> 원복. 의도된 방향.

---

## 4. 화면 밖 좌표가 500(서버 오류)으로 오분류

**문제**: 에이전트가 화면 범위 밖 좌표로 마우스를 움직이면 "잘못된 입력"(400)이 아니라 "서버 내부 오류"(500)로 응답한다.

**원인**: `_screen_to_page_cursor`가 좌표 변환에 실패하면 bare `RuntimeError`를 던졌다. instance 서버의 명령 실행 경로는 `InstanceError` 계열만 클라이언트 오류(4xx)로 분류하고 나머지는 전부 500으로 감싼다. `RuntimeError`는 `InstanceError`가 아니므로 500 경로를 탔다.

**수정**: 기존 `InvalidCommand`(400, 재시도 불가) 예외로 교체.
```python
raise InvalidCommand(f"screen cursor is outside page layouts: ({x}, {y})")
```

**검증**:
- **유닛 테스트**: 화면 밖 좌표(5000,5000)·음수(-1,-1)를 좌표 변환 함수에 직접 넣어서 `InvalidCommand`(400에 해당하는 예외)가 나는지, 정상 좌표(100,200)는 그대로 통과하는지 확인. (`server-test/tests/test_fixes.py`)
- **통합 테스트(실서버)**: 실제로 띄운 instance 서버에 화면 밖 좌표로 마우스 이동 명령을 보내서, 정말로 400이 오지 응답 코드가 500이 아닌지 확인. (`server-test/tests/test_instance_8.py`)

> LGTM

---

## 5. 닫힌 컨텍스트 재사용 시 크래시

**문제**: 관찰 도중 컨텍스트가 먼저 닫히는 경로(프로필 기반 채점 등) 이후, 같은 세션으로 스크린샷/실행 요청이 오면 "이미 닫힌 페이지" 크래시(500)가 난다.

**원인**: 컨텍스트를 미리 닫는 경로는 `state.context_closed = True`만 세팅하고 `state.closing`은 그대로 두는데, 세션 생존 여부를 확인하는 `_get_state`는 `state.closing`만 확인하고 `context_closed`는 보지 않는다. 이미 닫힌 컨텍스트인데도 "살아있다"고 통과시켜 Playwright가 크래시를 낸다.

**수정**: `_get_state`가 `context_closed`도 함께 확인.
```python
if state is None or state.closing or state.context_closed:
    raise InvalidInstanceId(f"Instance id {instance_id} is not running on this server.")
```

**검증**: 컨텍스트가 이미 닫힌(`context_closed=True`) 상태를 인위적으로 만들어두고 `_get_state`를 호출했을 때 "세션이 없다"는 뜻의 `InvalidInstanceId` 예외가 깔끔하게 나는지 확인. (`server-test/tests/test_fixes.py`)

> 참고: 현재 dev 브랜치엔 이 경로를 실제로 유발하는 기능(프로필 기반 관찰)이 없다, 이 문제는 리팩토링 이전 dev 브랜치에서의 수정사항 — 방어적 수정이며, 해당 기능이 다시 추가될 경우를 대비한 것.

> LGTM 이긴 한데 나중에 수정 필요

---

## 6. 관찰 개수 불일치 시 잘못된 만점 처리 가능

**문제**: 관찰값 개수가 채점 기준 개수와 맞지 않으면, 아무것도 관찰하지 못했는데도 reward가 1.0으로 나갈 수 있다.

**원인**: `rule_based_eval`이 `zip(criteria, observations)`로 짝을 맞추는데, `zip`은 길이가 다르면 조용히 짧은 쪽에 맞춰 잘라버린다. `observations`가 빈 리스트면 `checks`도 비고, `all([]) == True`라서 통과 처리된다. 새 관찰 경로(외부 API 채점 등)가 개수를 잘못 주면 이 구멍으로 들어온다 — 보상 무결성 문제.

**수정**: 개수가 다르면 명시적으로 실패시킴.
```python
if len(observations) != len(evaluation.criteria):
    raise ValueError(
        f"Observation count {len(observations)} does not match "
        f"criteria count {len(evaluation.criteria)}"
    )
```

**검증**: 관찰값을 빈 리스트로 주거나 기준 개수와 다르게 줬을 때 `ValueError`가 나는지 확인. 개수가 맞는 정상적인 성공(1.0)·실패(0.0) 케이스는 그대로 동작하는지도 같이 확인해서, 이 수정이 정상 케이스를 망가뜨리지 않았음을 검증. (`server-test/tests/test_evaluator.py`)

> LGTM

---

## 7. LLM judge 실패가 로그 없이 0점 처리됨

**문제**: VLM 채점(judge)이 API 키 누락·네트워크 장애로 실패하면 로그 한 줄 없이 "태스크 실패"와 동일하게 0점 처리된다.

**원인**: `except Exception: return 0.0`이 모든 실패를 뭉갠다. judge 인프라가 죽은 채로 학습이 진행되면, 그 기간의 모든 에피소드가 "진짜 실패"인지 "채점 시스템 고장"인지 구분할 방법이 없다 — 원인 추적 불가능한 오염된 학습 데이터가 조용히 쌓인다.

**수정**: 최소한 로그는 남긴다.
```python
except Exception:
    gateway_logger.exception(
        "LLM judge evaluation failed; returning fallback reward %.1f", _FALLBACK_REWARD
    )
    return _FALLBACK_REWARD
```

**검증**: judge에게 실제로 API 요청을 보내는 부분(httpx 클라이언트)이 강제로 예외를 던지도록 만들어놓고, 이런 인프라 장애 상황에서도 여전히 fallback 값(0.0)이 정상적으로 반환되는지(즉 로그를 추가한 것 때문에 동작이 깨지지 않았는지) 확인. (`server-test/tests/test_evaluator.py`)

**알려진 한계**: 로그는 남지만 API 응답 레벨에서는 여전히 "인프라 실패"와 "태스크 실패"가 구분되지 않는다. 근본 해결(예외 승격 또는 응답 스키마에 "채점 불능" 상태 추가)은 이번 범위 밖.

---

## 8. master 자가복구 루프가 예외 한 번에 영구 정지

**문제**: master가 실패한 자리를 재시도하는 백그라운드 루프가, 그 안에서 예외가 한 번이라도 나면 영원히 멈춘다.

**원인**: `release_loop`가 `while True: await asyncio.sleep(10); await self.release_all()`로 짜여 있어, `release_all()` 내부에서 예외가 새면 asyncio 태스크 자체가 죽고 `while True` 루프도 같이 끝난다. 서버는 계속 떠 있지만 자가복구 기능만 조용히 무력화된다.

**수정**: 루프 본문을 `try/except`로 감싸서 한 번의 실패가 다음 사이클을 막지 못하게 함.
```python
async def release_loop(self):
    while True:
        await asyncio.sleep(10)
        try:
            await self.release_all()
        except Exception:
            master_logger.exception("Release loop iteration failed")
```

**검증**: 컴파일/임포트 확인. (asyncio 백그라운드 루프의 장시간 동작 검증은 유닛 레벨보다 통합 레벨이 적합하다고 판단, 별도 유닛 테스트는 작성하지 않음.)

> LGTM

---

## 9. 서버 종료 시 백그라운드 태스크 미대기

**문제**: 서버 종료 시 백그라운드 루프를 취소만 하고 실제로 끝나길 기다리지 않는다.

**원인**: `lifespan` 종료 처리가 `recover_task.cancel()`만 호출하고 바로 다음(`master.close()`)으로 넘어간다. `cancel()`은 취소 "요청"일 뿐 즉시 종료를 보장하지 않아, 취소 처리 중인 태스크가 이미 닫힌 자원을 건드릴 여지가 있다.

**수정**: `cancel()` 후 `await`로 실제 종료를 기다림.
```python
finally:
    recover_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await recover_task
    await master.close()
```

**검증**: 컴파일/임포트 확인. (SIGTERM/lifespan shutdown을 실제로 트리거하는 자동화 테스트는 이번 범위 밖.)

> LGTM

---

## 10. 테스트 검증용 transport 주입 부재

**문제**: dev의 `Service`/`create_app`엔 fake transport를 주입할 방법이 없어서, 실서버 없이는 위 버그들을 유닛 레벨로 검증할 방법이 없었다.

**수정**: `Service.__init__`과 `create_app` 양쪽에 선택적 주입 파라미터 추가 (버그 수정이 아니라 테스트 인프라).
```python
def __init__(self, *, task_store, wavepool_config, transport: GatewayTransport | None = None):
    ...
    self.transport = transport or GatewayTransport(wavepool_config)
```

이 주입점 덕분에 항목 2·3의 유닛 테스트, 그리고 fault-injection 실서버 스크립트(release/observe/screenshot/execute 각각을 선택적으로 실패시키는 gateway 변형)가 가능해졌다. 프로덕션 경로(주입 없이 호출하는 경우)는 기존과 동일하게 동작한다.

> 우선 제거

---

## 그 외 정리성 변경 (버그 아님)

- `support/config.py`: `FrozenBaseModel` 중복 정의를 `surfgym_contracts.task`의 것을 import하도록 정리.
- `wavepool/instance/transport.py`: 아무도 읽지 않는 `_mouse_button_down` 속성 제거 (전체 grep으로 read 지점 0건 확인 후 삭제).
- `wavepool/instance/service.py`: 80% 동일했던 `_run_api_hook`/`_run_api_observation_hook`을 공용 `_call_hook_api(hook, context_id, *, context, require_json)`로 통합.

## 테스트

`server-test/` 아래에 유닛 테스트 18개와 실서버 통합 테스트 27개(+ 이식 불가로 skip 1개), 총 48개 테스트가 포함되어 있다. 전체 47 PASS, 1 SKIP, 실패 0. 테스트별로 정확히 뭘 검증하고 어떤 서버·스크립트 조합이 필요한지는 [server-test/TESTS.md](server-test/TESTS.md)에 정리했다.

## 알려진 이슈 (이번 수정 범위 밖)

- **`broken_lease` 처리 후 미청소**: master의 재시도 성공/실패와 무관하게 `broken_lease` 리스트 항목이 지워지지 않는다. instance 장애가 길어지면 `release_all`이 실패 항목을 같은 리스트에 재추가하는 구조라 무한 루프(livelock)로 이어질 수 있음 — 다음 라운드 최우선 수정 후보.
- **release_hooks가 instance `/release`에서 무시됨**: master는 release_hooks를 전달하지만 instance의 `/release` 라우트가 이를 읽지 않아, release 시점 외부 훅(예: `/impress/release`)이 실행되지 않는다.
- **master 재시작 시 instance 컨텍스트 정리 경로 없음**: 옛 설계의 `force_release`(포트 전체 강제 초기화)가 삭제되어, master 장부가 날아간 뒤 instance에 남은 컨텍스트를 정리할 방법이 없다.
