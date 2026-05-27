import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from functools import wraps
from typing import Annotated, Awaitable, Callable, TypeVar, cast

from fastapi import Body, FastAPI
from pydantic import ValidationError
from surfgym_contracts.protocol.agent_to_gateway import (
    RequestAdapter,
)
from surfgym_contracts.protocol.gateway_to_agent import ErrorResponse, Response

from surfgym_runtime.gateway.error import GatewayError, TimeOutError
from surfgym_runtime.gateway.service import Service
from surfgym_runtime.support import GatewayConfig, TaskStore, WavepoolConfig, gateway_logger

_T = TypeVar("_T")
_R = TypeVar("_R")


# [TODO] Gateway can still crash due to invalid json request, as FastAPI automatically parses the request due to "Annotated[object, Body()]"
def create_app(
    *, gateway_config: GatewayConfig, wavepool_config: WavepoolConfig, task_store: TaskStore
):
    executor = ThreadPoolExecutor(max_workers=gateway_config.gateway_workers)
    in_flight = asyncio.Semaphore(gateway_config.gateway_in_flight)
    service = Service(
        task_store=task_store,
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

    @error_boundary
    async def handle_request(
        body: Annotated[object, Body()],
    ) -> Response:
        request = RequestAdapter.validate_python(body)
        return await run_with_gateway_limit(
            service.handle_request,
            request,
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


def error_boundary(
    func: Callable[[object], Awaitable[_R]],
) -> Callable[[object], Awaitable[_R | ErrorResponse]]:
    @wraps(func)
    async def wrapper(body: object = Body()):
        session_id, task_id, op = _extract_request_metadata(body)
        try:
            return await func(body)
        except ValidationError as exc:
            message = _format_validation_error(exc)
            gateway_logger.warning(
                "[session_id=%s task_id=%s op=%s] Invalid gateway request: %s",
                session_id,
                task_id,
                op,
                message,
            )
            return ErrorResponse(
                session_id=session_id,
                task_id=task_id,
                error_type="INVALID_REQUEST",
                message=message,
            )

        except GatewayError as exc:
            gateway_logger.warning(
                """
[session_id=%s task_id=%s op=%s]  Gateway failed handling request.
[Detail] %s : %s
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
                "[session_id=%s task_id=%s op=%s] Unexpected gateway failure while handling request.",
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


def _extract_request_metadata(body: object) -> tuple[int, str, str]:
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


def _format_validation_error(exc: ValidationError) -> str:
    errors = exc.errors()
    details: list[str] = []

    for error in errors[:3]:
        loc = ".".join(str(part) for part in error.get("loc", []) if part != "body")
        msg = str(error.get("msg", "Invalid request."))
        msg = msg.removeprefix("Value error, ")

        if loc:
            details.append(f"{loc}: {msg}")
        else:
            details.append(msg)

    suffix = f" (+{len(errors) - 3} more)" if len(errors) > 3 else ""
    return f"Invalid request. {'; '.join(details)}{suffix}"
