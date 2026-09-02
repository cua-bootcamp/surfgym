import argparse
import base64
from contextlib import asynccontextmanager
from functools import wraps
from pathlib import Path
from typing import Annotated, Awaitable, Callable, ParamSpec, TypeVar

import uvicorn
from fastapi import Body, FastAPI, status
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

_P = ParamSpec("_P")
_T = TypeVar("_T")


def create_app(
    contexts_per_instance: int,
    headed: bool = False,
    ignore_https_errors: bool = False,
) -> FastAPI:
    worker = PlaywrightBrowserWorker(
        contexts_per_instance=contexts_per_instance,
        headed=headed,
        ignore_https_errors=ignore_https_errors,
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
    ):
        await worker.allocate(context_id, request.websites, request.hooks)
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
        await worker.execute(context_id, request.command)
        return ExecuteResponse()

    @handle_instance_errors
    async def observe(
        context_id: str,
        request: Annotated[ObserveRequest, Body()],
    ):

        return ObserveResponse(
            observation=await worker.observe(context_id, request.criteria, request.hooks)
        )

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
    return parser.parse_args()


def launch():
    args = _parse_args()
    setup_logging(instance_logger, args.log_path, component=f"instances/{args.port}")
    uvicorn.run(
        create_app(
            args.contexts_per_instance,
            headed=args.headed,
            ignore_https_errors=args.ignore_https_errors,
        ),
        host=args.host,
        port=args.port,
    )


if __name__ == "__main__":
    launch()
