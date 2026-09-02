from contextlib import contextmanager
from dataclasses import dataclass, field
from threading import Lock
from typing import Iterator, Literal

from surfgym_contracts.task import Hook

from surfgym_runtime.gateway.error import InvalidRequest
from surfgym_runtime.support import Frame


@dataclass(frozen=True)
class Lease:
    context_id: str
    port: int


def empty_trace() -> list[Frame]:
    return []


def empty_action_history() -> list[str]:
    return []


@dataclass(frozen=True)
class SessionState:
    task_id: str
    lease: Lease
    release_hooks: list[Hook]
    trace: list[Frame] = field(default_factory=empty_trace)
    action_history: list[str] = field(default_factory=empty_action_history)

    def append_frame(
        self,
        *,
        kind: Literal["start", "action", "reward"],
        image_b64: str,
        media_type: str,
    ) -> Frame:
        frame = Frame(
            step=self._next_trace_step(),
            kind=kind,
            image_b64=image_b64,
            media_type=media_type,
        )
        self.trace.append(frame)
        self._trim_trace()

        return frame

    def _next_trace_step(self) -> int:
        if not self.trace:
            return 0
        return self.trace[-1].step + 1

    def _trim_trace(self) -> None:
        _TRACE_BUFFER_LIMIT = 50
        while len(self.trace) > _TRACE_BUFFER_LIMIT:
            for index, frame in enumerate(self.trace):
                if frame.kind == "action":
                    del self.trace[index]
                    break
            else:
                return


@dataclass
class _SessionRecord:
    state: SessionState
    operation_lock: Lock = field(default_factory=Lock)
    reward_claimed: bool = False


@dataclass(frozen=True)
class SessionOperation:
    session_id: int
    state: SessionState
    _record: _SessionRecord


class SessionRegistry:
    def __init__(self):
        self._session_lock = Lock()
        self.session_states: dict[int, _SessionRecord | None] = {}

    def reserve_session(self, session_id: int) -> None:
        with self._session_lock:
            if session_id in self.session_states:
                raise InvalidRequest(f"Session {session_id} already active or starting.")
            self.session_states[session_id] = None

    def start_session(self, session_id: int, state: SessionState) -> None:
        with self._session_lock:
            self.session_states[session_id] = _SessionRecord(state=state)

    def end_session(self, session_id: int) -> None:
        with self._session_lock:
            self.session_states.pop(session_id, None)

    def require_session_state(self, session_id: int, task_id: str) -> SessionState:
        with self._session_lock:
            record = self._require_record(session_id, task_id)
            return record.state

    @contextmanager
    def session_operation(
        self,
        session_id: int,
        task_id: str,
        *,
        reward: bool = False,
    ) -> Iterator[SessionOperation]:
        with self._session_lock:
            record = self._require_record(session_id, task_id)

        with record.operation_lock:
            with self._session_lock:
                current = self.session_states.get(session_id)
                if current is not record:
                    raise InvalidRequest(
                        f"Session {session_id} is not active. Please request a start action first."
                    )
                if record.state.task_id != task_id:
                    self._raise_task_mismatch(session_id, record.state.task_id, task_id)
                if record.reward_claimed:
                    raise InvalidRequest(f"Session {session_id} reward is already claimed.")
                if reward:
                    record.reward_claimed = True
                operation = SessionOperation(
                    session_id=session_id,
                    state=record.state,
                    _record=record,
                )
            yield operation

    def end_session_if_current(self, operation: SessionOperation) -> None:
        with self._session_lock:
            if self.session_states.get(operation.session_id) is operation._record:
                self.session_states.pop(operation.session_id, None)

    def _require_record(self, session_id: int, task_id: str) -> _SessionRecord:
        record = self.session_states.get(session_id)
        if record is None:
            raise InvalidRequest(
                f"Session {session_id} is not active. Please request a start action first."
            )
        if record.state.task_id != task_id:
            self._raise_task_mismatch(session_id, record.state.task_id, task_id)
        return record

    @staticmethod
    def _raise_task_mismatch(session_id: int, expected: str, actual: str) -> None:
        raise InvalidRequest(
            f"Task mismatch for session {session_id}: "
            f"expected task_id={expected}, got task_id={actual}."
        )
