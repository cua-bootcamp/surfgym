"""
FastAPI app factory for the SurfGym Gateway.

- regulate request in_flight and worker number
- generate global deadline
"""

from __future__ import annotations

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

from src.components.log import logger, setup_logging
from src.components.task import TaskStore
from src.config import Config
from src.gateway.service import Service
from src.protocol.agent_to_gateway import Request
from src.protocol.gateway_to_agent import ErrorResponse, ErrorResponseType, Response


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
    setup_logging(config.log_path)

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

        logger.info("Invalid gateway request: %s", message)

        payload = ErrorResponse(
            session_id=session_id,
            task_id=task_id,
            error_type=ErrorResponseType.INVALID_REQUEST,
            message=message,
        )
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
            return ErrorResponse.from_type(
                session_id=request.session_id,
                task_id=request.task_id,
                error_type=ErrorResponseType.GATEWAY_BUSY,
            )

        try:
            loop = asyncio.get_running_loop()
            gateway_deadline = request_started_at + (gc.verl_timeout - gc.deadline_margin)
            return await loop.run_in_executor(
                executor, gateway.handle_request, request, gateway_deadline
            )
        except Exception:
            logger.exception("Failed while handling %s", request)
            return ErrorResponse.from_type(
                session_id=request.session_id,
                task_id=request.task_id,
                error_type=ErrorResponseType.FAIL_REQUEST_HANDLE,
            )
        finally:
            in_flight.release()

    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_api_route("/health", health, methods=["GET"])
    app.add_api_route("/", handle_request, methods=["POST"])
    return app


def _extract_request_ids(body: object) -> tuple[int, str]:
    if not isinstance(body, Mapping):
        return -1, ""

    request_body = cast(Mapping[str, object], body)
    raw_session_id = request_body.get("session_id", -1)
    raw_task_id = request_body.get("task_id", "")

    return _coerce_session_id(raw_session_id), _coerce_task_id(raw_task_id)


def _coerce_session_id(value: object) -> int:
    if isinstance(value, bool):
        return -1
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return -1
    return -1


def _coerce_task_id(value: object) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    return str(value)


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
