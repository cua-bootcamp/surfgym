import asyncio
import json
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from json import JSONDecodeError
from typing import Awaitable, Callable, TypeVar, cast

from fastapi import FastAPI, Request
from pydantic import ValidationError
from surfgym_contracts.protocol.agent_to_gateway import (
    AgentRequestAdapter,
)
from surfgym_contracts.protocol.gateway_to_agent import ErrorResponse, Response

from surfgym_runtime.gateway.error import GatewayError, InvalidRequest, TimeOutError
from surfgym_runtime.gateway.service import Service
from surfgym_runtime.support import Config, TaskStore, gateway_logger

_T = TypeVar("_T")
_R = TypeVar("_R")


def create_app(config: Config):
    gateway_config = config.gateway_config
    wavepool_config = config.wavepool_config

    executor = ThreadPoolExecutor(max_workers=gateway_config.gateway_workers)
    in_flight = asyncio.Semaphore(gateway_config.gateway_in_flight)
    service = Service(
        task_store=TaskStore.from_file(config.task_file_path),
        wavepool_config=wavepool_config,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            service.open()
            yield
        finally:
            service.close()
            executor.shutdown(wait=True, cancel_futures=True)

    app = FastAPI(
        lifespan=lifespan,
    )

    async def health():
        return {"status": "ok"}

    @gateway_boundary
    async def handle_request(request_body: object) -> Response:
        try:
            agent_request = AgentRequestAdapter.validate_python(request_body)
        except ValidationError as exc:
            raise InvalidRequest("Invalid agent request.") from exc

        return await run_with_gateway_limit(
            service.handle_request,
            agent_request,
        )

    async def run_with_gateway_limit(
        func: Callable[..., _T],
        *args: object,
    ) -> _T:
        request_started_at = time.monotonic()

        try:
            await asyncio.wait_for(
                in_flight.acquire(),
                timeout=gateway_config.in_flight_timeout,
            )
        except asyncio.TimeoutError as exc:
            raise TimeOutError(
                "Gateway in-flight timeout. The gateway is too busy to accept this request."
            ) from exc

        try:
            loop = asyncio.get_running_loop()
            deadline_at = request_started_at + (
                gateway_config.verl_timeout - gateway_config.deadline_margin
            )
            return await loop.run_in_executor(
                executor,
                lambda: func(*args, deadline_at),
            )
        finally:
            in_flight.release()

    app.add_api_route("/health", health, methods=["GET"])
    app.add_api_route("/", handle_request, methods=["POST"])
    return app


######################################
#          Helper Functions          #
######################################


def gateway_boundary(
    func: Callable[[object], Awaitable[_R]],
) -> Callable[[Request], Awaitable[_R | ErrorResponse]]:
    async def wrapper(raw_request: Request):
        session_id, task_id, op = -1, "", ""

        try:
            try:
                body = json.loads(await raw_request.body())
            except JSONDecodeError:
                raise InvalidRequest("Invalid JSON body.")

            session_id, task_id, op = _extract_request_meta(body)
            return await func(body)
        except GatewayError as exc:
            gateway_logger.warning(
                """
[session_id=%s task_id=%s op=%s]  Gateway failed handling request for following reason.
(error_type) %s
(message) %s
""".strip(),
                session_id,
                task_id,
                op,
                exc.error_type,
                exc.message,
            )
            return ErrorResponse(
                session_id=session_id,
                task_id=task_id,
                error_type=exc.error_type,
                message=exc.message,
            )
        except Exception:
            gateway_logger.exception(
                """
[session_id=%s task_id=%s op=%s] Unexpected gateway failure.
""".strip(),
                session_id,
                task_id,
                op,
            )
            return ErrorResponse(
                session_id=session_id,
                task_id=task_id,
                error_type="UNEXPECTED",
                message="Unexpected gateway error.",
            )

    return wrapper


def _extract_request_meta(body: object) -> tuple[int, str, str]:
    if not isinstance(body, dict):
        return -1, "", ""

    body = cast(dict[object, object], body)
    raw_session_id = body.get("session_id", -1)
    raw_task_id = body.get("task_id", "")
    raw_op = body.get("op", "")

    session_id = raw_session_id if isinstance(raw_session_id, int) else -1
    task_id = raw_task_id if isinstance(raw_task_id, str) else str(raw_task_id)
    op = raw_op if isinstance(raw_op, str) else str(raw_op)

    return session_id, task_id, op
