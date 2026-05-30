import base64
import random
import time
from dataclasses import dataclass
from io import BytesIO
from queue import SimpleQueue
from threading import Lock, Thread
from typing import Callable, TypeVar

from PIL import Image, ImageDraw
from surfgym_contracts.command import Command
from surfgym_contracts.computer13 import TerminalAction
from surfgym_contracts.protocol.agent_to_gateway import (
    ActionRequest,
    AgentRequest,
    RewardRequest,
    StartRequest,
)
from surfgym_contracts.protocol.gateway_to_agent import ActionResponse, ImagePayload, RewardResponse
from surfgym_contracts.task import Action, Evaluation, Website
from typing_extensions import Optional

from surfgym_runtime.gateway.error import (
    Deadline,
    GatewayError,
    InvalidRequest,
    RetryableError,
    deadline_for,
)
from surfgym_runtime.gateway.transport import GatewayTransport
from surfgym_runtime.support import TaskStore, WavepoolConfig, evaluate_page_rules, gateway_logger

_T = TypeVar("_T")


@dataclass(frozen=True)
class SessionState:
    task_id: str
    instance_id: str
    port: int


class Service:
    def __init__(
        self,
        *,
        task_store: TaskStore,
        wavepool_config: WavepoolConfig,
    ) -> None:
        self.task_store = task_store
        self.transport = GatewayTransport(wavepool_config)
        self.process_timeout = wavepool_config.process_timeout

        self._session_lock = Lock()
        self.session_states: dict[
            int, SessionState | None
        ] = {}  # None value is used for termination

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

    def _handle_start(
        self, request: StartRequest, deadline: Callable[[str], Deadline]
    ) -> ActionResponse:
        self._reserve_session(request.session_id)
        session_state = None
        try:
            task = self._require_task(request.task_id)
            instance_id, port = self._allocate(deadline, task.website, task.setup)
            session_state = SessionState(
                task_id=request.task_id, instance_id=instance_id, port=port
            )
            screenshot_b64, media_type = self._screenshot(deadline, session_state)
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
        session_state = self._require_session_state(request.session_id, request.task_id)

        for action in request.actions:
            if not isinstance(action, TerminalAction):
                self._execute(deadline, session_state, action.to_commands())

        (screenshot_b64, media_type) = self._screenshot(deadline, session_state)
        # text = self._interactive_tree(deadline, lease) if request.include_a11y else None

        return ActionResponse(
            session_id=request.session_id,
            task_id=request.task_id,
            # text=text,
            image=ImagePayload(data=screenshot_b64, mimeType=media_type),
        )

    def _handle_reward(
        self, request: RewardRequest, deadline: Callable[[str], Deadline]
    ) -> RewardResponse:
        task = self._require_task(request.task_id)
        session_state = self._require_session_state(request.session_id, request.task_id)

        response = self._observe(
            deadline=deadline,
            state=session_state,
            evaluation=task.evaluation,
        )

        reward = evaluate_page_rules(task.evaluation, response.observation)

        self._release_queue.put(session_state)
        self._end_session(request.session_id)

        return RewardResponse(
            session_id=request.session_id,
            task_id=request.task_id,
            reward=reward,
        )

    def _allocate(
        self,
        deadline: Callable[[str], Deadline],
        websites: list[Website],
        setup: Optional[list[Action]],
    ) -> tuple[str, int]:
        d = deadline("allocate")
        response = self._run_with_retry(
            min_attempt_time=self.process_timeout.allocate,
            deadline=d,
            func=lambda: self.transport.allocate(d, websites, setup),
        )
        return (response.instance_id, response.instance_port)

    def _screenshot(self, deadline: Callable[[str], Deadline], state: SessionState):
        d = deadline("screenshot")
        response = self._run_with_retry(
            min_attempt_time=self.process_timeout.screenshot,
            deadline=d,
            func=lambda: self.transport.screenshot(d, state.instance_id, state.port),
        )
        return draw_cursor_on_screenshot(
            response.screenshot_b64, int(response.x), int(response.y)
        ), response.media_type

    def _observe(
        self, *, deadline: Callable[[str], Deadline], state: SessionState, evaluation: Evaluation
    ):
        d = deadline("observe")
        return self._run_with_retry(
            min_attempt_time=self.process_timeout.observe,
            deadline=d,
            func=lambda: self.transport.observe(d, state.instance_id, state.port, evaluation),
        )

    def _execute(self, deadline: Callable[[str], Deadline], state: SessionState, command: Command):
        self.transport.execute(deadline("execute"), state.instance_id, state.port, command)

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
                self.transport.release(release_deadline, state.instance_id, state.port)
            except GatewayError as exc:
                gateway_logger.warning(
                    """
Failed to release: instance_id=%s port=%s
Error Detail: error_type=%s message=%s
""".strip(),
                    state.instance_id,
                    state.port,
                    exc.error_type,
                    exc.message,
                )
            except Exception:
                gateway_logger.exception(
                    "Unexpected release worker failure: instance_id=%s port=%s",
                    state.instance_id,
                    state.port,
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

    # def _interactive_tree(self, deadline: Deadline, lease: Lease):
    #     response = self._run_with_retry(
    #         context="_interactive_tree",
    #         deadline=deadline,
    #         func=lambda: self.pool.get_interactive_tree(deadline, lease.instance_id, lease.port),
    #     )
    #     return parse_interactive_tree_text(
    #         response, viewport_width=self.viewport_width, viewport_height=self.viewport_height
    #     )


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


# NORMALIZED_COORD_SPACE = 1000

# def _normalize_value(value: float, *, source_size: int) -> int:
#     if source_size <= 0:
#         raise ValueError(f"source_size must be positive, got {source_size}")

#     normalized = round((float(value) / float(source_size)) * NORMALIZED_COORD_SPACE)
#     return max(0, min(NORMALIZED_COORD_SPACE, normalized))


# def _normalize_point(
#     x: float,
#     y: float,
#     *,
#     viewport_width: int,
#     viewport_height: int,
# ) -> tuple[int, int]:
#     return (
#         _normalize_value(x, source_size=viewport_width),
#         _normalize_value(y, source_size=viewport_height),
#     )


# def parse_interactive_tree_text(
#     response: InteractiveTreeResponse,
#     *,
#     viewport_width: int,
#     viewport_height: int,
# ) -> str:
#     lines: list[str] = []

#     mouse_position = response.mouse_position
#     mouse_x, mouse_y = _normalize_point(
#         mouse_position.x,
#         mouse_position.y,
#         viewport_width=viewport_width,
#         viewport_height=viewport_height,
#     )
#     lines.append(f"mouse_position: ({mouse_x}, {mouse_y})")

#     for region in response.regions:
#         (left, top, width, height) = region.bbox

#         (left, top) = _normalize_point(
#             left, top, viewport_width=viewport_width, viewport_height=viewport_height
#         )
#         (width, height) = _normalize_point(
#             width, height, viewport_width=viewport_width, viewport_height=viewport_height
#         )

#         lines.append(
#             f"role: {region.role}, text: {region.visible_text}, bbox: [{left}, {top}, {width}, {height}]"
#         )
#     return "\n".join(lines)
