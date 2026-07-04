import base64
import random
import time
from dataclasses import dataclass
from io import BytesIO
from queue import SimpleQueue
from threading import Lock, Thread
from typing import Callable, Literal, TypeVar

from PIL import Image, ImageDraw
from surfgym_contracts.command import Command, ReferenceCommand
from surfgym_contracts.computer13 import ReferenceAction, TerminalAction
from surfgym_contracts.protocol.agent_to_gateway import (
    ActionRequest,
    AgentRequest,
    ReleaseRequest,
    RewardRequest,
    StartRequest,
)
from surfgym_contracts.protocol.gateway_to_agent import (
    ActionResponse,
    ImagePayload,
    ReleaseResponse,
    RewardResponse,
)
from surfgym_contracts.task import CriteriaEvaluation, Hook, LLMJudgeEvaluation, Website

from surfgym_runtime.gateway.error import (
    Deadline,
    GatewayError,
    InvalidRequest,
    RetryableError,
    deadline_for,
)
from surfgym_runtime.gateway.transport import GatewayTransport
from surfgym_runtime.support import Evaluator, Frame, TaskStore, WavepoolConfig, gateway_logger

_T = TypeVar("_T")


@dataclass(frozen=True)
class Lease:
    context_id: str
    port: int


@dataclass(frozen=True)
class SessionState:
    task_id: str
    lease: Lease
    release_hooks: list[Hook]
    trace: list[Frame] = []

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


class Service:
    def __init__(
        self,
        *,
        task_store: TaskStore,
        wavepool_config: WavepoolConfig,
    ) -> None:
        self.task_store = task_store
        self.evaluator = Evaluator()
        self.transport = GatewayTransport(wavepool_config)
        self.process_timeout = wavepool_config.process_timeout

        self._session_lock = Lock()
        self.session_states: dict[int, SessionState | None] = {}

        # release daemon
        self._release_queue: SimpleQueue[SessionState | None] = SimpleQueue()
        self._release_worker: Thread | None = None
        self._release_timeout = wavepool_config.process_timeout.release

    def open(self) -> None:
        self._release_worker = Thread(
            target=self._release_worker_loop,
            name="surfgym-release-worker",
            daemon=True,
        )
        self._release_worker.start()

    def close(self) -> None:
        self._release_queue.put(None)
        if self._release_worker is not None:
            self._release_worker.join(timeout=1.0)

    def handle_request(self, request: AgentRequest, deadline_at: float):
        deadline = deadline_for(deadline_at)
        match request:
            case StartRequest():
                return self._handle_start(request, deadline)
            case ActionRequest():
                return self._handle_action(request, deadline)
            case RewardRequest():
                return self._handle_reward(request, deadline)
            case ReleaseRequest():
                return self._handle_release(request)

    def _handle_start(
        self, request: StartRequest, deadline: Callable[[str], Deadline]
    ) -> ActionResponse:
        self._reserve_session(request.session_id)
        session_state = None

        try:
            task = self._require_task(request.task_id)
            context_id, port = self._allocate(deadline, task.website, task.lifecycle_hooks.allocate)
            session_state = SessionState(
                task_id=request.task_id,
                lease=Lease(context_id=context_id, port=port),
                release_hooks=task.lifecycle_hooks.release,
            )
            screenshot_b64, media_type = self._screenshot(deadline, session_state.lease)
            session_state.append_frame(
                kind="start", image_b64=screenshot_b64, media_type=media_type
            )
            self._start_session(request.session_id, session_state)

            return ActionResponse(
                session_id=request.session_id,
                task_id=request.task_id,
                image=ImagePayload(data=screenshot_b64, mimeType=media_type),
            )
        except Exception:
            self._end_session(request.session_id)
            if session_state is not None:
                self._release_queue.put(session_state)
            raise

    def _handle_action(
        self,
        request: ActionRequest,
        deadline: Callable[[str], Deadline],
    ) -> ActionResponse:
        task = self._require_task(request.task_id)
        session_state = self._require_session_state(request.session_id, request.task_id)

        for action in request.actions:
            match action:
                case _ if isinstance(action, TerminalAction):
                    continue
                case ReferenceAction():
                    self._execute(
                        deadline,
                        session_state.lease,
                        ReferenceCommand(hooks=task.lifecycle_hooks.reference),
                    )
                case _:
                    self._execute(deadline, session_state.lease, action.to_commands())

        (screenshot_b64, media_type) = self._screenshot(deadline, session_state.lease)
        session_state.append_frame(kind="action", image_b64=screenshot_b64, media_type=media_type)

        return ActionResponse(
            session_id=request.session_id,
            task_id=request.task_id,
            image=ImagePayload(data=screenshot_b64, mimeType=media_type),
        )

    def _handle_reward(
        self, request: RewardRequest, deadline: Callable[[str], Deadline]
    ) -> RewardResponse:
        task = self._require_task(request.task_id)
        session_state = self._require_session_state(request.session_id, request.task_id)

        match task.evaluation:
            case CriteriaEvaluation():
                response = self._observe(
                    deadline=deadline,
                    lease=session_state.lease,
                    evaluation=task.evaluation,
                    evaluation_hooks=task.lifecycle_hooks.evaluate,
                )
                reward = self.evaluator.rule_based_eval(task.evaluation, response.observation)
            case LLMJudgeEvaluation():
                (screenshot_b64, media_type) = self._screenshot(deadline, session_state.lease)
                session_state.append_frame(
                    kind="reward", image_b64=screenshot_b64, media_type=media_type
                )
                judge_deadline = deadline("llm_judge")
                reward = self.evaluator.llm_judge_eval(
                    task.instruction,
                    session_state.trace,
                    task.evaluation,
                    judge_deadline.timeout_for(60.0),
                )

        self._release_queue.put(session_state)
        self._end_session(request.session_id)

        return RewardResponse(
            session_id=request.session_id,
            task_id=request.task_id,
            reward=reward,
        )

    def _handle_release(self, request: ReleaseRequest) -> ReleaseResponse:
        session_state = self._require_session_state(request.session_id, request.task_id)

        self._release_queue.put(session_state)
        self._end_session(request.session_id)

        return ReleaseResponse(
            session_id=request.session_id,
            task_id=request.task_id,
        )

    def _allocate(
        self,
        deadline: Callable[[str], Deadline],
        websites: list[Website],
        allocate_hooks: list[Hook],
    ) -> tuple[str, int]:
        d = deadline("allocate")
        response = self._run_with_retry(
            min_attempt_time=self.process_timeout.allocate,
            deadline=d,
            func=lambda: self.transport.allocate(
                deadline=d, websites=websites, allocate_hooks=allocate_hooks
            ),
        )
        return (response.context_id, response.instance_port)

    def _screenshot(self, deadline: Callable[[str], Deadline], lease: Lease):
        d = deadline("screenshot")
        response = self._run_with_retry(
            min_attempt_time=self.process_timeout.screenshot,
            deadline=d,
            func=lambda: self.transport.screenshot(d, lease.context_id, lease.port),
        )
        return draw_cursor_on_screenshot(
            response.screenshot_b64, int(response.x), int(response.y)
        ), response.media_type

    def _observe(
        self,
        *,
        deadline: Callable[[str], Deadline],
        lease: Lease,
        evaluation: CriteriaEvaluation,
        evaluation_hooks: list[Hook],
    ):
        d = deadline("observe")
        return self._run_with_retry(
            min_attempt_time=self.process_timeout.observe,
            deadline=d,
            func=lambda: self.transport.observe(
                deadline=d,
                context_id=lease.context_id,
                instance_port=lease.port,
                evaluation=evaluation,
                evaluation_hooks=evaluation_hooks,
            ),
        )

    def _execute(self, deadline: Callable[[str], Deadline], lease: Lease, command: Command):
        self.transport.execute(deadline("execute"), lease.context_id, lease.port, command)

    def _run_with_retry(
        self,
        *,
        min_attempt_time: float,
        deadline: Deadline,
        func: Callable[[], _T],
    ) -> _T:
        backoffs = jittered_backoff()

        while True:
            deadline.require_remaining(min_attempt_time)

            try:
                return func()
            except RetryableError:
                sleep_budget = deadline.remaining() - min_attempt_time
                if sleep_budget <= 0:
                    raise deadline.error

                sleep_for = min(next(backoffs), sleep_budget)
                time.sleep(sleep_for)

    def _release_worker_loop(self) -> None:
        while True:
            state = self._release_queue.get()
            if state is None:
                return

            try:
                release_deadline = Deadline(time.monotonic() + self._release_timeout, "release")
                self.transport.release(
                    deadline=release_deadline,
                    context_id=state.lease.context_id,
                    release_hooks=state.release_hooks,
                )
            except GatewayError as exc:
                gateway_logger.warning(
                    """
Failed to release: context_id=%s port=%s
Error Detail: error_type=%s message=%s
""".strip(),
                    state.lease.context_id,
                    state.lease.port,
                    exc.error_type,
                    exc.message,
                )
            except Exception:
                gateway_logger.exception(
                    "Unexpected release worker failure: context_id=%s port=%s",
                    state.lease.context_id,
                    state.lease.port,
                )

    def _reserve_session(self, session_id: int) -> None:
        with self._session_lock:
            if session_id in self.session_states:
                raise InvalidRequest(f"Session {session_id} already active or starting.")
            self.session_states[session_id] = None

    def _start_session(self, session_id: int, state: SessionState) -> None:
        with self._session_lock:
            self.session_states[session_id] = state

    def _end_session(self, session_id: int) -> None:
        with self._session_lock:
            self.session_states.pop(session_id, None)

    def _require_session_state(self, session_id: int, task_id: str) -> SessionState:
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

    def _require_task(self, task_id: str):
        task = self.task_store.get(task_id)
        if task is None:
            raise InvalidRequest(f"Unknown task_id: {task_id}")
        return task


################################################
#               Helper Functions               #
################################################


def jittered_backoff():
    delay_min = 0.0
    delay_max = 1.0
    while True:
        yield random.uniform(delay_min, delay_max)
        delay_min = delay_max
        delay_max = min(delay_max * 2, 8)


def draw_cursor_on_screenshot(
    screenshot_b64: str,
    x: int,
    y: int,
) -> str:
    raw = base64.b64decode(screenshot_b64)

    with Image.open(BytesIO(raw)) as image:
        image = image.convert("RGBA")
        draw = ImageDraw.Draw(image)

        cursor = [
            (x, y),
            (x, y + 24),
            (x + 6, y + 18),
            (x + 10, y + 31),
            (x + 14, y + 29),
            (x + 10, y + 17),
            (x + 20, y + 17),
        ]
        draw.polygon(cursor, fill=(0, 0, 0, 255))

        output = BytesIO()
        image.save(output, format="PNG")

    return base64.b64encode(output.getvalue()).decode("ascii")
