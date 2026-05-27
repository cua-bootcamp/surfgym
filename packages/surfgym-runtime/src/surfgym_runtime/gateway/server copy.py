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

from surfgym_runtime.gateway.error import GatewayError, TimeOutError
from surfgym_runtime.gateway.service import Service
from surfgym_runtime.support import GatewayConfig, TaskStore, WavepoolConfig, gateway_logger


def create_app(
    *, gateway_config: GatewayConfig, wavepool_config: WavepoolConfig, task_store: TaskStore
):
    executor = ThreadPoolExecutor(max_workers=gateway_config.gateway_workers)
    service = Service(
        task_store=task_store,
        wavepool_config=wavepool_config,
    )
    gateway_handler = GatewayHandler(
        service=service, executor=executor, gateway_config=gateway_config
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

    async def handle_request(
        request: Annotated[Request, Body(discriminator="op")],
    ) -> Response:
        return await gateway_handler.handle(request)

    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_api_route("/health", health, methods=["GET"])
    app.add_api_route("/", handle_request, methods=["POST"])
    return app


######################################
#          Helper Functions          #
######################################


class GatewayHandler:
    def __init__(
        self,
        *,
        service: Service,
        gateway_config: GatewayConfig,
        executor: ThreadPoolExecutor,
    ) -> None:
        self.service = service
        self.config = gateway_config
        self.executor = executor
        self.in_flight = asyncio.Semaphore(gateway_config.gateway_in_flight)

    async def handle(self, request: Request) -> Response:
        try:
            return await self._handle(request)
        except GatewayError as exc:
            gateway_logger.warning(
                """
[session_id=%s task_id=%s op=%s]  Gateway failed handling request.
[Detail] %s : %s
""".strip(),
                request.session_id,
                request.task_id,
                request.op,
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
            gateway_logger.exception(
                "[session_id=%s task_id=%s op=%s] Unexpected gateway failure while handling request.",
                request.session_id,
                request.task_id,
                request.op,
            )
            return ErrorResponse(
                session_id=request.session_id,
                task_id=request.task_id,
                error_type="UNEXPECTED",
                message="Unexpected gateway error.",
            )

    async def _handle(self, request: Request) -> Response:
        request_started_at = time.monotonic()

        try:
            await asyncio.wait_for(
                self.in_flight.acquire(),
                timeout=self.config.in_flight_timeout,
            )
        except asyncio.TimeoutError as exc:
            raise TimeOutError(
                "Gateway in-flight timeout. The gateway is too busy to accept this request."
            ) from exc

        try:
            loop = asyncio.get_running_loop()
            deadline_at = request_started_at + (
                self.config.verl_timeout - self.config.deadline_margin
            )
            return await loop.run_in_executor(
                self.executor,
                self.service.handle_request,
                request,
                deadline_at,
            )
        finally:
            self.in_flight.release()


async def handle_validation_error(
    _request: FastAPIRequest,
    exc: Exception,
) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):
        raise exc

    (session_id, task_id) = _extract_request_ids(exc.body)

    message = _format_validation_error(exc)
    payload = ErrorResponse(
        session_id=session_id,
        task_id=task_id,
        error_type="INVALID_REQUEST",
        message=message,
    )
    gateway_logger.warning(
        "Invalid request: session_id=%s task_id=%s",
        session_id,
        task_id,
    )
    return JSONResponse(status_code=200, content=payload.model_dump(mode="json"))


def _extract_request_ids(body: object) -> tuple[int, str]:
    if not isinstance(body, dict):
        return -1, ""

    request_body = cast(Mapping[str, object], body)

    raw_session_id = request_body.get("session_id", -1)
    raw_task_id = request_body.get("task_id", "")
    return (
        raw_session_id if isinstance(raw_session_id, int) else -1,
        raw_task_id if isinstance(raw_task_id, str) else str(raw_task_id),
    )


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
