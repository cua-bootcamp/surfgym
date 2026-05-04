import base64
import time
from dataclasses import dataclass
from io import BytesIO
from typing import Callable, TypeVar

from PIL import Image, ImageDraw
from typing_extensions import assert_never

from src.config import WavepoolConfig
from src.gateway.error import Deadline, DeadlineExceeded, SGRetryableError
from src.gateway.pool import GatewayPool
from src.gateway.protocol.computer13 import TerminalAction
from src.gateway.protocol.request import (
    ActionRequest,
    Request,
    RequestAdapter,
    RewardRequest,
    StartRequest,
)
from src.gateway.protocol.response import ActionResponse, ImagePayload, RewardResponse
from src.gateway.rule_evaluator import (
    collect_selectors,
    evaluate_page_rules,
    uses_page_html,
)
from src.gateway.task_store import Task, TaskStore
from wavepool.instance.protocol.response import InteractiveTreeResponse

_T = TypeVar("_T")


@dataclass(frozen=True)
class Lease:
    instance_id: str
    port: int


class Service:
    def __init__(
        self,
        *,
        pool_workers: int,
        task_store: TaskStore,
        instance_config: WavepoolConfig,
    ) -> None:
        self.task_store = task_store
        self.pool = GatewayPool(pool_workers=pool_workers, instance_config=instance_config)

        # session_id -> (instance_id, port)
        self.active_sessions: dict[int, Lease] = {}

        self.BACKOFF_MAX_SEC = 8
        self.RELEASE_TIMEOUT_SEC = 5.0

    def open(self) -> None:
        self.pool.start()

    def close(self) -> None:
        self.pool.stop()

    def handle_request(self, request: Request, deadline_at: float):
        request = RequestAdapter.validate_python(request)

        deadline = Deadline(deadline_at)
        if isinstance(request, StartRequest):
            return self._handle_start(request, deadline)
        if isinstance(request, ActionRequest):
            return self._handle_action(request, deadline)
        if isinstance(request, RewardRequest):
            return self._handle_reward(request, deadline)

        assert_never(request)

    def _handle_start(self, request: StartRequest, deadline: Deadline) -> ActionResponse:
        if request.session_id in self.active_sessions:
            raise RuntimeError(f"Session {request.session_id} already exists")

        task = self.task_store.get(request.task_id)

        lease = self._allocate(deadline)
        self._navigate(deadline, lease, task.website)
        (screenshot_b64, media_type) = self._screenshot(deadline, lease)
        text = self._interactive_tree(deadline, lease) if request.include_a11y else None

        self.active_sessions[request.session_id] = lease

        return ActionResponse(
            session_id=request.session_id,
            task_id=request.task_id,
            text=text,
            image=ImagePayload(data=screenshot_b64, mimeType=media_type),
        )

    def _handle_action(
        self,
        request: ActionRequest,
        deadline: Deadline,
    ) -> ActionResponse:
        lease = self.active_sessions.get(request.session_id)
        if lease is None:
            raise RuntimeError(f"Session {request.session_id} does not exist")

        for action in request.actions:
            if not isinstance(action, TerminalAction):
                self._execute_browser_command(deadline, lease, action.to_commands())

        (screenshot_b64, media_type) = self._screenshot(deadline, lease)
        text = self._interactive_tree(deadline, lease) if request.include_a11y else None

        return ActionResponse(
            session_id=request.session_id,
            task_id=request.task_id,
            text=text,
            image=ImagePayload(data=screenshot_b64, mimeType=media_type),
        )

    def _handle_reward(self, request: RewardRequest, deadline: Deadline) -> RewardResponse:
        lease = self.active_sessions.get(request.session_id)
        if lease is None:
            raise RuntimeError(f"Session {request.session_id} does not exist")

        task = self.task_store.get(request.task_id)
        reward = self._evaluate(task, lease, deadline)

        self._release(lease)
        self.active_sessions.pop(request.session_id, None)

        return RewardResponse(
            session_id=request.session_id,
            task_id=request.task_id,
            reward=reward,
        )

    def _allocate(self, deadline: Deadline) -> Lease:
        instance_id, _, port = self._run_with_retry(
            context="_allocate_instance",
            deadline=deadline,
            func=lambda: self.pool.allocate(deadline),
        )

        return Lease(instance_id=instance_id, port=port)

    def _navigate(self, deadline: Deadline, lease: Lease, url: str):
        return self._run_with_retry(
            context="_navigate",
            deadline=deadline,
            func=lambda: self.pool.navigate(deadline, lease.instance_id, lease.port, url),
        )

    def _execute_browser_command(self, deadline: Deadline, lease: Lease, command):
        return self._run_with_retry(
            context="_execute_browser_command",
            deadline=deadline,
            func=lambda: self.pool.execute_browser_command(
                deadline, lease.instance_id, lease.port, command
            ),
        )

    def _screenshot(self, deadline: Deadline, lease: Lease):
        (screenshot_b64, media_type, x, y) = self._run_with_retry(
            context="_screenshot",
            deadline=deadline,
            func=lambda: self.pool.screenshot(deadline, lease.instance_id, lease.port),
        )

        return draw_cursor_on_screenshot(screenshot_b64, int(x), int(y)), media_type

    def _snapshot(
        self,
        *,
        deadline: Deadline,
        lease: Lease,
        selectors: list[str],
        include_html: bool,
    ):
        return self._run_with_retry(
            context="_snapshot",
            deadline=deadline,
            func=lambda: self.pool.get_snapshot(
                deadline, lease.instance_id, lease.port, selectors, include_html
            ),
        )

    def _interactive_tree(self, deadline: Deadline, lease: Lease):
        response = self._run_with_retry(
            context="_interactive_tree",
            deadline=deadline,
            func=lambda: self.pool.get_interactive_tree(deadline, lease.instance_id, lease.port),
        )
        return parse_interactive_tree_text(response)

    def _evaluate(self, task: Task, lease: Lease, deadline: Deadline) -> float:
        if task.evaluation is None:
            print(f"Rule evaluation for task {task.task_id}: reward=0.0 (no rules)")
            return 0.0

        try:
            selectors = collect_selectors(task.evaluation)
            snapshot = self._snapshot(
                deadline=deadline,
                lease=lease,
                selectors=selectors,
                include_html=uses_page_html(task.evaluation),
            )
            result = evaluate_page_rules(task.evaluation, snapshot.snapshot)
            print(
                f"Rule evaluation for task {task.task_id}: "
                f"reward={result.reward} ({result.summary()})"
            )
            return result.reward
        except DeadlineExceeded:
            raise
        except Exception as exc:
            print(f"Rule evaluation for task {task.task_id} failed: {exc}")
            return 0.0

    def _release(self, lease: Lease):
        release_deadline = Deadline(time.monotonic() + self.RELEASE_TIMEOUT_SEC)
        self.pool.release(release_deadline, lease.instance_id, lease.port)

    def _run_with_retry(
        self,
        *,
        context: str,
        deadline: Deadline,
        func: Callable[[], _T],
    ) -> _T:
        backoffs = self._backoff_delays()

        while True:
            deadline.check(context)

            try:
                return func()
            except Exception as exc:
                if not isinstance(exc, SGRetryableError):
                    raise

                sleep_for = min(next(backoffs), max(0.0, deadline.remaining()))
                if sleep_for <= 0:
                    raise DeadlineExceeded(
                        f"Gateway request deadline exceeded in {context}"
                    ) from exc
                time.sleep(sleep_for)

    def _backoff_delays(self):
        delay = 1.0
        while True:
            yield delay
            delay = min(delay * 2, self.BACKOFF_MAX_SEC)


####################
# Helper Functions #
####################


def parse_interactive_tree_text(response: InteractiveTreeResponse) -> str:
    lines: list[str] = []

    mouse_position = response.mouse_position
    lines.append(f"mouse_position: ({mouse_position.x}, {mouse_position.y})")

    for region in response.regions.values():
        if not region.rects:
            continue

        coords: list[str] = []
        for rect in region.rects:
            x = int((rect.left + rect.right) / 2)
            y = int((rect.top + rect.bottom) / 2)
            coords.append(f"({x}, {y})")

        lines.append(
            f"tag: {region.tag_name}, role: {region.role}, "
            f"text: {region.aria_name}, coords: {', '.join(coords)}"
        )

    return "\n".join(lines)


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
