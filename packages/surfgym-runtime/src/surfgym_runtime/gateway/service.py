"""
Service layer of the gateway.
- Define works to do bout the
"""

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
    Request,
    RequestAdapter,
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
from surfgym_runtime.support import TaskStore, WavepoolConfig, evaluate_page_rules, surfgym_logger

_T = TypeVar("_T")


@dataclass(frozen=True)
class Lease:
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
        self.pool = GatewayTransport(wavepool_config)
        self.process_timeout = wavepool_config.process_timeout

        # session_id -> (instance_id, port)
        self.active_sessions: dict[int, Lease] = {}

        # release daemon
        self._release_queue: SimpleQueue[Lease | None] = SimpleQueue()
        self._release_worker: Thread | None = None
        self._release_timeout = wavepool_config.process_timeout.release

        # allocation lock
        self._session_lock = Lock()
        self._starting_sessions: set[int] = set()

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

    def handle_request(self, request: Request, deadline_at: float):
        request = RequestAdapter.validate_python(request)
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
        lease = None

        try:
            task = self._get_task_safe(request.task_id)
            lease = self._allocate(deadline, task.website, task.setup)

            screenshot_b64, media_type = self._screenshot(deadline, lease)
            self._commit_session(request.session_id, lease)

            return ActionResponse(
                session_id=request.session_id,
                task_id=request.task_id,
                image=ImagePayload(data=screenshot_b64, mimeType=media_type),
            )
        except Exception:
            self._abort_session(request.session_id)
            if lease:
                self._enqueue_release(lease)
            raise

    def _handle_action(
        self,
        request: ActionRequest,
        deadline: Callable[[str], Deadline],
    ) -> ActionResponse:
        lease = self._get_lease_safe(request.session_id)

        for action in request.actions:
            if not isinstance(action, TerminalAction):
                self._execute(deadline, lease, action.to_commands())

        (screenshot_b64, media_type) = self._screenshot(deadline, lease)
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
        lease = self._get_lease_safe(request.session_id)
        task = self._get_task_safe(request.task_id)

        try:
            observations = self._observe(
                deadline=deadline,
                lease=lease,
                evaluation=task.evaluation,
            )

            reward = evaluate_page_rules(task.evaluation, observations)
            return RewardResponse(
                session_id=request.session_id,
                task_id=request.task_id,
                reward=reward,
            )
        finally:
            self._enqueue_release(lease)
            self.active_sessions.pop(request.session_id, None)

    def _allocate(
        self,
        deadline: Callable[[str], Deadline],
        websites: list[Website],
        setup: Optional[list[Action]],
    ) -> Lease:
        d = deadline("allocate")
        instance_id, _, port = self._run_with_retry(
            min_attempt_time=self.process_timeout.allocate,
            deadline=d,
            func=lambda: self.pool.allocate(d, websites, setup),
        )
        return Lease(instance_id=instance_id, port=port)

    def _screenshot(self, deadline: Callable[[str], Deadline], lease: Lease):
        d = deadline("screenshot")
        (screenshot_b64, media_type, x, y) = self._run_with_retry(
            min_attempt_time=self.process_timeout.screenshot,
            deadline=d,
            func=lambda: self.pool.screenshot(d, lease.instance_id, lease.port),
        )
        return draw_cursor_on_screenshot(screenshot_b64, int(x), int(y)), media_type

    def _observe(
        self, *, deadline: Callable[[str], Deadline], lease: Lease, evaluation: Evaluation
    ):
        d = deadline("observe")
        return self._run_with_retry(
            min_attempt_time=self.process_timeout.observe,
            deadline=d,
            func=lambda: self.pool.observe(d, lease.instance_id, lease.port, evaluation),
        )

    def _execute(self, deadline: Callable[[str], Deadline], lease: Lease, command: Command):
        self.pool.execute(deadline("execute"), lease.instance_id, lease.port, command)

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

    def _get_lease_safe(self, session_id: int) -> Lease:
        lease = self.active_sessions.get(session_id)
        if lease is None:
            raise InvalidRequest(f"Session {session_id} does not exist")
        return lease

    def _get_task_safe(self, task_id: str):
        try:
            return self.task_store.get(task_id)
        except KeyError as exc:
            raise InvalidRequest(f"Unknown task_id: {task_id}") from exc

    def _enqueue_release(self, lease: Lease) -> None:
        self._release_queue.put(lease)

    def _release_worker_loop(self) -> None:
        while True:
            lease = self._release_queue.get()
            if lease is None:
                return

            try:
                release_deadline = Deadline(time.monotonic() + self._release_timeout, "release")
                self.pool.release(release_deadline, lease.instance_id, lease.port)
            except GatewayError as exc:
                surfgym_logger.warning(
                    """
Failed to release: instance_id=%s port=%s
Error Detail: error_type=%s message=%s
""".strip(),
                    lease.instance_id,
                    lease.port,
                    exc.error_type,
                    exc.message,
                )
            except Exception:
                surfgym_logger.exception(
                    "Unexpected release worker failure: instance_id=%s port=%s",
                    lease.instance_id,
                    lease.port,
                )

    def _reserve_session(self, session_id: int) -> None:
        with self._session_lock:
            if session_id in self.active_sessions or session_id in self._starting_sessions:
                raise InvalidRequest(f"Session {session_id} already exists")
            self._starting_sessions.add(session_id)

    def _commit_session(self, session_id: int, lease: Lease) -> None:
        with self._session_lock:
            self._starting_sessions.discard(session_id)
            self.active_sessions[session_id] = lease

    def _abort_session(self, session_id: int) -> None:
        with self._session_lock:
            self._starting_sessions.discard(session_id)

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
