import asyncio
import time
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from typing import Annotated, cast

from fastapi import Body, FastAPI
from fastapi import Request as FastAPIRequest
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from surfgym_contracts.protocol.agent_to_gateway import Request
from surfgym_contracts.protocol.gateway_to_agent import ErrorResponse, Response

from surfgym_runtime.gateway.error import GatewayError
from surfgym_runtime.gateway.service import Service
from surfgym_runtime.support import Config, TaskStore, surfgym_logger


def launch(config: Config):
    gc = config.gateway_config

    executor = ThreadPoolExecutor(max_workers=gc.gateway_workers)
    in_flight = asyncio.Semaphore(gc.gateway_in_flight)
    task_store = TaskStore.from_file(config.task_file_path)
    gateway = Service(
        pool_workers=gc.pool_workers,
        task_store=task_store,
        instance_config=config.wavepool_config,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            gateway.open()
            yield
        finally:
            gateway.close()
            executor.shutdown(wait=True, cancel_futures=True)

    app = FastAPI(
        lifespan=lifespan,
    )

    async def health():
        return {"status": "ok"}

    async def handle_validation_error(
        _request: FastAPIRequest,
        exc: Exception,
    ) -> JSONResponse:
        if not isinstance(exc, RequestValidationError):
            raise exc

        session_id, task_id = _extract_request_ids(exc.body)
        message = _format_validation_error(exc)
        payload = ErrorResponse(
            session_id=session_id,
            task_id=task_id,
            error_type="INVALID_REQUEST",
            message=message,
        )

        surfgym_logger.warning(
            "Invalid request: session_id=%s task_id=%s",
            session_id,
            task_id,
        )
        surfgym_logger.warning("Invalid gateway request: %s", payload)
        return JSONResponse(status_code=200, content=payload.model_dump(mode="json"))

    async def handle_request(
        request: Annotated[Request, Body(discriminator="op")],
    ) -> Response:
        request_started_at = time.monotonic()

        try:
            await asyncio.wait_for(
                in_flight.acquire(),
                timeout=gc.in_flight_timeout,
            )
        except asyncio.TimeoutError:
            return ErrorResponse(
                session_id=request.session_id,
                task_id=request.task_id,
                error_type="TIMEOUT",
                message="Gateway in_flight timeout occured. The gateway worker may be too busy.",
            )

        try:
            loop = asyncio.get_running_loop()
            gateway_deadline = request_started_at + (gc.verl_timeout - gc.deadline_margin)
            return await loop.run_in_executor(
                executor, gateway.handle_request, request, gateway_deadline
            )
        except GatewayError as exc:
            surfgym_logger.warning(
                "Gateway failed handling request: session_id=%s task_id=%s error_type=%s message=%s",
                request.session_id,
                request.task_id,
                exc.error_type,
                exc.message,
            )
            return ErrorResponse(
                session_id=request.session_id,
                task_id=request.task_id,
                error_type=exc.error_type,
                message=exc.message,
            )
        except Exception:
            surfgym_logger.exception(
                "Unexpected gateway failure while handling request : %s", request
            )
            raise
        finally:
            in_flight.release()

    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_api_route("/health", health, methods=["GET"])
    app.add_api_route("/", handle_request, methods=["POST"])
    return app


######################################
#          Helper Functions          #
######################################


def _extract_request_ids(body: object) -> tuple[int, str]:
    if not isinstance(body, Mapping):
        return -1, ""

    request_body = cast(Mapping[str, object], body)
    raw_session_id = request_body.get("session_id", -1)
    raw_task_id = request_body.get("task_id", "")

    return raw_session_id if isinstance(raw_session_id, int) else -1, raw_task_id if isinstance(
        raw_task_id, str
    ) else str(raw_task_id)


def _format_validation_error(exc: RequestValidationError) -> str:
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
