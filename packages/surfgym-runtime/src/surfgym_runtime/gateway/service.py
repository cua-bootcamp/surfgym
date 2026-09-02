import base64
import json
import random
import time
from io import BytesIO
from typing import Callable, Optional, TypeVar

from PIL import Image, ImageDraw
from surfgym_contracts.command import Command
from surfgym_contracts.computer13 import DoneAction, FailAction
from surfgym_contracts.protocol.agent_to_gateway import (
    ActionRequest,
    AgentRequest,
    RewardRequest,
    StartRequest,
)
from surfgym_contracts.protocol.artifact import ArtifactPayload, ArtifactSpec
from surfgym_contracts.protocol.gateway_to_agent import (
    ActionResponse,
    ImagePayload,
    RewardBundleResponse,
    RewardResponse,
)
from surfgym_contracts.task import (
    ConsoleCriteria,
    Criteria,
    CriteriaEvaluation,
    CuaEvaluation,
    CuaStateSource,
    Hook,
    InfeasibleEvaluation,
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
from surfgym_runtime.support.config import DOCKER_ARTIFACT_CONTROL_TIMEOUT_SECONDS
from surfgym_runtime.support.cua_evaluator import CuaSnapshot, evaluate_cua_reward

_T = TypeVar("_T")


class Service:
    def __init__(self, *, task_store: TaskStore, wavepool_config: WavepoolConfig) -> None:
        self.task_store = task_store
        self.evaluator = Evaluator()
        self.transport = GatewayTransport(wavepool_config)
        self._session_registry = SessionRegistry()
        self._release_worker = ReleaseWorker(
            transport=self.transport,
            release_timeout=wavepool_config.process_timeout.release,
        )

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
                return self._handle_reward(request, deadline)

    def _handle_start(
        self, request: StartRequest, deadline: Callable[[str], Deadline]
    ) -> ActionResponse:
        self._session_registry.reserve_session(request.session_id)
        session_state = None

        try:
            task = self._require_task(request.task_id)
            context_id, port = self._allocate(
                deadline,
                task.website,
                task.lifecycle_hooks.allocate,
                task.lifecycle_hooks.release,
            )
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
        with self._session_registry.session_operation(
            request.session_id, request.task_id
        ) as operation:
            session_state = operation.state

            if session_state.action_history and session_state.action_history[-1] in {
                "FAIL",
                "DONE",
            }:
                raise InvalidRequest("Cannot submit an action after a terminal action.")

            terminal_actions = [
                action for action in request.actions if isinstance(action, (FailAction, DoneAction))
            ]
            if terminal_actions and len(request.actions) != 1:
                raise InvalidRequest("Terminal action must be the only action in a request.")

            for action in request.actions:
                if isinstance(action, (FailAction, DoneAction)):
                    session_state.action_history.append(action.action_type)
                    continue
                self._execute(deadline, session_state.lease, action.to_commands())
                session_state.action_history.append(action.action_type)

            (screenshot_b64, media_type) = self._screenshot(deadline, session_state.lease)
            session_state.append_frame(
                kind="action", image_b64=screenshot_b64, media_type=media_type
            )

            return ActionResponse(
                session_id=request.session_id,
                task_id=request.task_id,
                image=ImagePayload(data=screenshot_b64, mimeType=media_type),
            )

    def _handle_reward(
        self,
        request: RewardRequest,
        deadline: Callable[[str], Deadline],
    ) -> RewardResponse | RewardBundleResponse:
        task = self._require_task(request.task_id)
        with self._session_registry.session_operation(
            request.session_id,
            request.task_id,
            reward=True,
        ) as operation:
            session_state = operation.state
            try:
                reward = self._compute_reward(
                    task=task,
                    session_state=session_state,
                    deadline=deadline,
                )

                reward_image: Optional[ImagePayload] = None
                if task.include_reward_image:
                    screenshot_b64, media_type = self._screenshot(
                        deadline,
                        session_state.lease,
                    )
                    session_state.append_frame(
                        kind="reward",
                        image_b64=screenshot_b64,
                        media_type=media_type,
                    )
                    reward_image = ImagePayload(
                        data=screenshot_b64,
                        mimeType=media_type,
                    )

                response = RewardResponse(
                    session_id=request.session_id,
                    task_id=request.task_id,
                    reward=reward,
                    image=reward_image,
                )
                if request.artifacts is None:
                    return response

                artifact_deadline = deadline("artifact")
                artifacts = [
                    self._artifact(
                        deadline=artifact_deadline,
                        lease=session_state.lease,
                        artifact=artifact,
                    )
                    for artifact in request.artifacts
                ]
                return RewardBundleResponse(
                    **response.model_dump(),
                    artifacts=artifacts,
                )
            finally:
                try:
                    self._release_worker.enqueue(session_state)
                finally:
                    self._session_registry.end_session_if_current(operation)

    def _compute_reward(
        self,
        *,
        task: Task,
        session_state: SessionState,
        deadline: Callable[[str], Deadline],
    ) -> float:
        last_action = session_state.action_history[-1] if session_state.action_history else None

        if isinstance(task.evaluation, InfeasibleEvaluation):
            return 1.0 if last_action == "FAIL" else 0.0

        if last_action == "FAIL":
            return 0.0

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
            case CuaEvaluation():
                reward = self._compute_cua_reward(
                    evaluation=task.evaluation,
                    session_state=session_state,
                    deadline=deadline,
                )

        return reward

    def _compute_cua_reward(
        self,
        *,
        evaluation: CuaEvaluation,
        session_state: SessionState,
        deadline: Callable[[str], Deadline],
    ) -> float:
        criteria: list[Criteria] = [_cua_snapshot_criteria(state) for state in evaluation.states]
        response = self._observe(
            deadline=deadline,
            lease=session_state.lease,
            criteria=criteria,
            observe_hooks=[],
        )

        snapshots: dict[str, CuaSnapshot] = {}
        for state, observation in zip(evaluation.states, response.observation):
            if not isinstance(observation, dict):
                raise InvalidRequest(
                    f"CUA state observation for {state.app_base} must be an object"
                )
            snapshots[state.app_base] = CuaSnapshot(
                initial_state=observation.get("initial_state"),
                current_state=observation.get("current_state"),
            )

        reward_deadline = deadline("cua_reward")
        result = evaluate_cua_reward(
            evaluation.reward_script,
            source_task_id=evaluation.source_task_id,
            sid=evaluation.states[0].sid,
            snapshots=snapshots,
            timeout=reward_deadline.timeout_for(30.0),
        )
        return result.reward

    def _allocate(
        self,
        deadline: Callable[[str], Deadline],
        websites: list[Website],
        allocate_hooks: list[Hook],
        release_hooks: list[Hook],
    ) -> tuple[str, int]:
        d = deadline("allocate")
        response = self._run_with_retry(
            min_attempt_time=0.0,
            deadline=d,
            func=lambda: self.transport.allocate(
                deadline=d,
                websites=websites,
                allocate_hooks=allocate_hooks,
                release_hooks=release_hooks,
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

    def _artifact(
        self,
        *,
        deadline: Deadline,
        lease: Lease,
        artifact: ArtifactSpec,
    ) -> ArtifactPayload:
        timeout = deadline.timeout_for(
            DOCKER_ARTIFACT_CONTROL_TIMEOUT_SECONDS + self.process_timeout.layer_gap
        )
        return self.transport.artifact(
            context_id=lease.context_id,
            instance_port=lease.port,
            artifact=artifact,
            timeout=timeout,
        )

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


def _cua_snapshot_criteria(state: CuaStateSource) -> ConsoleCriteria:
    current_key = json.dumps(state.current_state_key)
    initial_key = json.dumps(state.initial_state_key)
    return ConsoleCriteria(
        website_id=state.website_id,
        value=None,
        script=(
            "() => {"
            "const read = (key) => { const raw = localStorage.getItem(key); "
            "return raw === null ? null : JSON.parse(raw); };"
            f"return {{initial_state: read({initial_key}), current_state: read({current_key})}};"
            "}"
        ),
    )


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
