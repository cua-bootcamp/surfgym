import argparse
import base64
from contextlib import asynccontextmanager
from functools import wraps
from pathlib import Path
from typing import Annotated, Awaitable, Callable, ParamSpec, TypeVar

import uvicorn
from fastapi import Body, FastAPI, Header, status
from fastapi.responses import JSONResponse
from surfgym_contracts.protocol.gateway_to_upstream import (
    ArtifactRequest,
    ExecuteRequest,
    LiveContextsResponse,
    MasterAllocateRequest,
    MasterReleaseRequest,
    ObserveRequest,
    ScreenshotRequest,
)
from surfgym_contracts.protocol.upstream_to_gateway import (
    ErrorResponse,
    ExecuteResponse,
    InsatnceReleaseResponse,
    InstanceAllocateResponse,
    ObserveResponse,
    ScreenshotResponse,
)

from surfgym_runtime.support import instance_logger, setup_logging
from surfgym_runtime.wavepool.instance.error import InstanceError
from surfgym_runtime.wavepool.instance.service import PlaywrightBrowserWorker
from surfgym_runtime.wavepool.allocation_budget import parse_remaining_seconds

_P = ParamSpec("_P")
_T = TypeVar("_T")


def create_app(
    contexts_per_instance: int,
    headed: bool = False,
    ignore_https_errors: bool = False,
    binding_cleanup_horizon_seconds: float = 720.0,
    binding_cleanup_request_timeout_seconds: float = 360.0,
    binding_cleanup_retry_interval_seconds: float = 2.0,
) -> FastAPI:
    worker = PlaywrightBrowserWorker(
        contexts_per_instance=contexts_per_instance,
        headed=headed,
        ignore_https_errors=ignore_https_errors,
        binding_cleanup_horizon_seconds=binding_cleanup_horizon_seconds,
        binding_cleanup_request_timeout_seconds=binding_cleanup_request_timeout_seconds,
        binding_cleanup_retry_interval_seconds=binding_cleanup_retry_interval_seconds,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            await worker.open()
            yield
        finally:
            await worker.close()

    async def health():
        return {"status": "ok"}

    async def contexts() -> LiveContextsResponse:
        return LiveContextsResponse(context_ids=worker.ctx_manager.live_context_ids())

    @handle_instance_errors
    async def allocate(
        context_id: str,
        request: Annotated[MasterAllocateRequest, Body()],
        remaining_ms: Annotated[str | None, Header(alias="X-SurfGym-Allocate-Remaining-Ms")] = None,
    ):
        try:
            incoming_remaining_seconds = parse_remaining_seconds(remaining_ms)
        except ValueError as exc:
            raise InstanceError(str(exc), status.HTTP_400_BAD_REQUEST) from exc
        allocate_args = (
            context_id,
            request.websites,
            request.hooks,
            request.cleanup_capability,
        )
        if incoming_remaining_seconds is None:
            await worker.allocate(*allocate_args)
        else:
            await worker.allocate(
                *allocate_args, incoming_remaining_seconds=incoming_remaining_seconds
            )
        return InstanceAllocateResponse()

    @handle_instance_errors
    async def release(
        context_id: str,
        request: Annotated[MasterReleaseRequest, Body()],
    ):
        await worker.release(context_id, request.hooks)
        return InsatnceReleaseResponse()

    @handle_instance_errors
    async def screenshot(
        context_id: str,
        request: Annotated[ScreenshotRequest, Body()],
    ):
        async with worker.operation(context_id):
            screenshot, x, y = await worker.screenshot(context_id)
        screenshot_b64 = base64.b64encode(screenshot.getvalue()).decode("ascii")

        return ScreenshotResponse(
            screenshot_b64=screenshot_b64,
            media_type="image/png",
            x=x,
            y=y,
        )

    @handle_instance_errors
    async def execute(
        context_id: str,
        request: Annotated[ExecuteRequest, Body()],
    ):
        async with worker.operation(context_id):
            await worker.execute(context_id, request.command)
        return ExecuteResponse()

    @handle_instance_errors
    async def observe(
        context_id: str,
        request: Annotated[ObserveRequest, Body()],
    ):

        async with worker.operation(context_id):
            observation = await worker.observe(context_id, request.criteria, request.hooks)
        return ObserveResponse(observation=observation)

    @handle_instance_errors
    async def artifact(
        context_id: str,
        request: Annotated[ArtifactRequest, Body()],
    ):
        return await worker.artifact(context_id, request.artifact)

    app = FastAPI(lifespan=lifespan)
    app.add_api_route("/health", health, methods=["GET"])
    app.add_api_route("/contexts", contexts, methods=["GET"])
    app.add_api_route("/allocate", allocate, methods=["POST"])
    app.add_api_route("/release", release, methods=["POST"])
    app.add_api_route("/execute", execute, methods=["POST"])
    app.add_api_route("/observe", observe, methods=["POST"])
    app.add_api_route("/screenshot", screenshot, methods=["POST"])
    app.add_api_route("/artifact", artifact, methods=["POST"])

    return app


def handle_instance_errors(
    func: Callable[_P, Awaitable[_T]],
) -> Callable[_P, Awaitable[_T | JSONResponse]]:
    @wraps(func)
    async def wrapper(*args: _P.args, **kwargs: _P.kwargs) -> _T | JSONResponse:
        op = func.__name__

        try:
            return await func(*args, **kwargs)
        except InstanceError as exc:
            instance_logger.warning(
                "Instance request failed: op=%s retryable=%s message=%s",
                op,
                exc.retryable,
                exc.message,
            )
            return _error_response(
                status_code=exc.status_code,
                message=exc.message,
                retryable=exc.retryable,
            )
        except Exception:
            instance_logger.exception("Unexpected instance request failure: op=%s", op)
            return _error_response(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message=f"Unexpected instance error during {op}",
                retryable=True,
            )

    return wrapper


def _error_response(
    *,
    status_code: int,
    message: str,
    retryable: bool,
) -> JSONResponse:
    payload = ErrorResponse(
        message=message,
        retryable=retryable,
    )
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(mode="json"),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=str, required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--log-path", type=Path, required=True)
    parser.add_argument("--contexts-per-instance", type=int, default=1)
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--ignore-https-errors", action="store_true")
    parser.add_argument("--binding-cleanup-horizon-seconds", type=float, default=720.0)
    parser.add_argument("--binding-cleanup-request-timeout-seconds", type=float, default=360.0)
    parser.add_argument("--binding-cleanup-retry-interval-seconds", type=float, default=2.0)
    return parser.parse_args()


def launch():
    args = _parse_args()
    setup_logging(instance_logger, args.log_path, component=f"instances/{args.port}")
    uvicorn.run(
        create_app(
            args.contexts_per_instance,
            headed=args.headed,
            ignore_https_errors=args.ignore_https_errors,
            binding_cleanup_horizon_seconds=args.binding_cleanup_horizon_seconds,
            binding_cleanup_request_timeout_seconds=args.binding_cleanup_request_timeout_seconds,
            binding_cleanup_retry_interval_seconds=args.binding_cleanup_retry_interval_seconds,
        ),
        host=args.host,
        port=args.port,
    )


if __name__ == "__main__":
    launch()
