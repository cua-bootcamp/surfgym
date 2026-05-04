from __future__ import annotations

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Body, FastAPI

from src.config import Config
from src.gateway.protocol.request import Request
from src.gateway.protocol.response import ErrorResponse, ErrorResponseType, Response
from src.gateway.service import Service
from src.gateway.task_store import TaskStore
from src.log import file_logger, setup_logging


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

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.post("/")
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
            file_logger.exception("Failed while handling %s", request)
            return ErrorResponse.from_type(
                session_id=request.session_id,
                task_id=request.task_id,
                error_type=ErrorResponseType.FAIL_REQUEST_HANDLE,
            )
        finally:
            in_flight.release()

    return app
