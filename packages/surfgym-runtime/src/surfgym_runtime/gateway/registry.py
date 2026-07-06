from dataclasses import dataclass, field
from threading import Lock
from typing import Literal

from surfgym_contracts.task import Hook

from surfgym_runtime.gateway.error import InvalidRequest
from surfgym_runtime.support import Frame


@dataclass(frozen=True)
class Lease:
    context_id: str
    port: int


def empty_trace() -> list[Frame]:
    return []


@dataclass(frozen=True)
class SessionState:
    task_id: str
    lease: Lease
    release_hooks: list[Hook]
    trace: list[Frame] = field(default_factory=empty_trace)

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


class SessionRegistry:
    def __init__(self):
        self._session_lock = Lock()
        self.session_states: dict[int, SessionState | None] = {}

    def reserve_session(self, session_id: int) -> None:
        with self._session_lock:
            if session_id in self.session_states:
                raise InvalidRequest(f"Session {session_id} already active or starting.")
            self.session_states[session_id] = None

    def start_session(self, session_id: int, state: SessionState) -> None:
        with self._session_lock:
            self.session_states[session_id] = state

    def end_session(self, session_id: int) -> None:
        with self._session_lock:
            self.session_states.pop(session_id, None)

    def require_session_state(self, session_id: int, task_id: str) -> SessionState:
        session_state = self.session_states.get(session_id)
        if session_state is None:
            raise InvalidRequest(
                f"Session {session_id} is not active. Please request a start action first."
            )
        if session_state.task_id != task_id:
            raise InvalidRequest(
                f"Task mismatch for session {session_id}: "
                f"expected task_id={session_state.task_id}, got task_id={task_id}."
            )
        return session_state
