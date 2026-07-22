import base64
import random
import time
from io import BytesIO
from typing import Callable, TypeVar

from PIL import Image, ImageDraw
from surfgym_contracts.command import Command
from surfgym_contracts.computer13 import DoneAction, FailAction
from surfgym_contracts.protocol.agent_to_gateway import (
    ActionRequest,
    AgentRequest,
    RewardRequest,
    StartRequest,
)
from surfgym_contracts.protocol.gateway_to_agent import (
    ActionResponse,
    DEVRewardResponse,
    ImagePayload,
    RewardResponse,
)
from surfgym_contracts.task import (
    Criteria,
    CriteriaEvaluation,
    Hook,
    LLMJudgeEvaluation,
    Task,
    Website,
)

from surfgym_runtime.gateway.error import (
    Deadline,
    InvalidRequest,
    RetryableError,
    deadline_for,
)
from surfgym_runtime.gateway.registry import Lease, SessionRegistry, SessionState
from surfgym_runtime.gateway.transport import GatewayTransport
from surfgym_runtime.gateway.worker import ReleaseWorker
from surfgym_runtime.support import Evaluator, TaskStore, WavepoolConfig

_T = TypeVar("_T")


class Service:
    def __init__(
        self, *, task_store: TaskStore, wavepool_config: WavepoolConfig, DEV_MODE: bool
    ) -> None:
        self.task_store = task_store
        self.evaluator = Evaluator()
        self.transport = GatewayTransport(wavepool_config)
        self._session_registry = SessionRegistry()
        self._release_worker = ReleaseWorker(
            transport=self.transport,
            release_timeout=wavepool_config.process_timeout.release,
        )
        self.DEV_MODE = DEV_MODE

        self.process_timeout = wavepool_config.process_timeout

    def open(self) -> None:
        self._release_worker.start()

    def close(self) -> None:
        self._release_worker.close()

    def handle_request(self, request: AgentRequest, deadline_at: float):
        deadline = deadline_for(deadline_at)
        match request:
            case StartRequest():
                return self._handle_start(request, deadline)
            case ActionRequest():
                return self._handle_action(request, deadline)
            case RewardRequest():
                if self.DEV_MODE:
                    return self._DEV_handle_reward(request, deadline)
                return self._handle_reward(request, deadline)

    def _handle_start(
        self, request: StartRequest, deadline: Callable[[str], Deadline]
    ) -> ActionResponse:
        self._session_registry.reserve_session(request.session_id)
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
            self._session_registry.start_session(request.session_id, session_state)

            return ActionResponse(
                session_id=request.session_id,
                task_id=request.task_id,
                image=ImagePayload(data=screenshot_b64, mimeType=media_type),
            )
        except Exception:
            self._session_registry.end_session(request.session_id)
            if session_state is not None:
                self._release_worker.enqueue(session_state)
            raise

    def _handle_action(
        self,
        request: ActionRequest,
        deadline: Callable[[str], Deadline],
    ) -> ActionResponse:
        session_state = self._session_registry.require_session_state(
            request.session_id, request.task_id
        )

        for action in request.actions:
            if isinstance(action, (FailAction, DoneAction)):
                continue
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
        session_state = self._session_registry.require_session_state(
            request.session_id, request.task_id
        )

        try:
            reward = self._compute_reward(
                task=task,
                session_state=session_state,
                deadline=deadline,
            )
        finally:
            self._release_worker.enqueue(session_state)
            self._session_registry.end_session(request.session_id)

        return RewardResponse(
            session_id=request.session_id,
            task_id=request.task_id,
            reward=reward,
        )

    def _compute_reward(
        self,
        *,
        task: Task,
        session_state: SessionState,
        deadline: Callable[[str], Deadline],
    ) -> float:
        match task.evaluation:
            case CriteriaEvaluation():
                response = self._observe(
                    deadline=deadline,
                    lease=session_state.lease,
                    criteria=task.evaluation.criteria,
                    observe_hooks=task.lifecycle_hooks.observe,
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

        return reward

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
        criteria: list[Criteria],
        observe_hooks: list[Hook],
    ):
        d = deadline("observe")
        return self._run_with_retry(
            min_attempt_time=self.process_timeout.observe,
            deadline=d,
            func=lambda: self.transport.observe(
                deadline=d,
                context_id=lease.context_id,
                instance_port=lease.port,
                criteria=criteria,
                observe_hooks=observe_hooks,
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

    def _require_task(self, task_id: str):
        task = self.task_store.get(task_id)
        if task is None:
            raise InvalidRequest(f"Unknown task_id: {task_id}")
        return task

    def _DEV_handle_reward(
        self, request: RewardRequest, deadline: Callable[[str], Deadline]
    ) -> DEVRewardResponse:
        task = self._require_task(request.task_id)
        session_state = self._session_registry.require_session_state(
            request.session_id, request.task_id
        )

        try:
            reward = self._compute_reward(
                task=task,
                session_state=session_state,
                deadline=deadline,
            )
            (screenshot_b64, media_type) = self._screenshot(deadline, session_state.lease)
            session_state.append_frame(
                kind="reward", image_b64=screenshot_b64, media_type=media_type
            )

            return DEVRewardResponse(
                session_id=request.session_id,
                task_id=request.task_id,
                reward=reward,
                image=ImagePayload(data=screenshot_b64, mimeType=media_type),
            )
        finally:
            self._release_worker.enqueue(session_state)
            self._session_registry.end_session(request.session_id)


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
