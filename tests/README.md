# surfgym pytest

`dev` 브랜치의 gateway/master/instance 리팩토링(`cb46729`→`e9adc2d`)을 검증하는
테스트 스위트. **소스 코드는 전혀 수정하지 않는다** — 실제 서버를 real HTTP로
띄우거나, 공개 클래스를 그대로 import해서 구동하는 방식만 쓴다.

## 실행 방법

```bash
# 프로젝트 루트에서
pytest tests/ -v -s
```

### 세팅

- `.venv`가 이미 세팅돼 있고 (`uv sync` 등으로) Playwright 브라우저가 설치돼
  있어야 한다.

### 사용법

- 파일 하나만: `pytest tests/test_1x1_success.py -v -s`
- 로그에서 `[registry:라벨]`은 master 내부 상태(lease/pending_releases/capacity),
  `[gateway:라벨]`은 gateway의 session_states, `[transport→/←...]`는 실제 오간
  HTTP 요청/응답이다. 맨 마지막 줄이 `PASSED`/`FAILED`.

## 파일 구성

| 파일 | 내용 |
|---|---|
| `conftest.py` | 서버 기동 fixture(`wavepool_stack`: 순수 블랙박스용 3-subprocess / `real_instance`: instance만 / `master_and_gateway_stack`: 권장 조합), `make_task_row` 헬퍼, 로거 리셋, transport 로깅 헬퍼 |
| `test_1x1_success.py` | 순수 블랙박스 (3서버 다 subprocess) — HTTP 응답만 확인 |
| `test_1x1_success_2.py` | instance만 subprocess, master는 직접 함수 호출 (gateway 없음) — registry만 확인 |
| `test_1x1_success_3.py` | `master_and_gateway_stack` 사용 — HTTP + registry + transport 동시 확인. 이 스타일이 이후 테스트의 기본 템플릿 |
| `test_1x1_outofinstance_1.py` | capacity 꽉 찬 상태에서 추가 allocate 거절 확인 |
| `test_1x1_outofinstance_2.py` | allocate→release→allocate(성공)→allocate(거절) 순환 확인 |
| `test_1x1_allocatefailure.py` | 죽은 website URL로 `CreateFailed` 반복 유발, registry 누수 없는지 확인 |