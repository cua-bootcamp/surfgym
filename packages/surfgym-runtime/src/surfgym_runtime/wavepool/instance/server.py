import argparse
import base64
import uuid
from contextlib import asynccontextmanager
from functools import wraps
from pathlib import Path
from typing import Annotated, Any, Awaitable, Callable, ParamSpec, TypeVar

import uvicorn
from fastapi import Body, FastAPI, status
from fastapi.responses import JSONResponse
from surfgym_contracts.command import CommandAdapter
from surfgym_contracts.protocol.gateway_to_upstream import AllocateRequest
from surfgym_contracts.protocol.upstream_to_gateway import (
    ErrorResponse,
    ExecuteResponse,
    GetInstanceResponse,
    IdleResponse,
    InstanceErrorType,
    ReleaseResponse,
    ScreenshotResponse,
)

from surfgym_runtime.support import instance_logger, setup_logging
from surfgym_runtime.wavepool.instance.error import InstanceError, InstanceNotIdle
from surfgym_runtime.wavepool.instance.service import PlaywrightBrowserWorker

_P = ParamSpec("_P")
_T = TypeVar("_T")


def create_app(contexts_per_instance: int) -> FastAPI:
    worker = PlaywrightBrowserWorker(contexts_per_instance=contexts_per_instance)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await worker.open()
        try:
            yield
        finally:
            await worker.close()

    async def health():
        return {"status": "ok"}

    @handle_instance_errors
    async def get_instance(
        request: Annotated[AllocateRequest, Body()],
    ):
        if not await worker.has_capacity():
            raise InstanceNotIdle("No available context slot on this instance.")

        new_instance_id = str(uuid.uuid4())
        await worker.create(new_instance_id, request.websites, request.setup)
        return GetInstanceResponse(instance_id=new_instance_id)

    @handle_instance_errors
    async def reset_instance(instance_id: str):
        await worker.delete(instance_id)
        return ReleaseResponse()

    @handle_instance_errors
    async def force_reset():
        await worker.delete_all()
        return ReleaseResponse()

    @handle_instance_errors
    async def screenshot_instance(instance_id: str):
        screenshot, x, y = await worker.screenshot(instance_id)
        screenshot_b64 = base64.b64encode(screenshot.getvalue()).decode("ascii")

        return ScreenshotResponse(
            snapshot_b64=screenshot_b64,
            media_type="image/png",
            x=x,
            y=y,
        )

    @handle_instance_errors
    async def execute_instance(
        instance_id: str,
        command_data: Annotated[dict[str, Any], Body(...)],
    ):
        command = CommandAdapter.validate_python(command_data)
        result = await worker.execute(instance_id, command)

        if result is None:
            return ExecuteResponse()
        return result

    @handle_instance_errors
    async def get_status():
        return IdleResponse(
            idle=await worker.idle(),
        )

    app = FastAPI(lifespan=lifespan)
    app.add_api_route("/health", health, methods=["GET"])
    app.add_api_route("/allocate", get_instance, methods=["POST"])
    app.add_api_route("/reset", reset_instance, methods=["POST"])
    app.add_api_route("/force_reset", force_reset, methods=["POST"])
    app.add_api_route("/screenshot", screenshot_instance, methods=["GET"])
    app.add_api_route("/execute", execute_instance, methods=["POST"])
    app.add_api_route("/idle", get_status, methods=["POST"])
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
                "Instance request failed: op=%s error_type=%s retryable=%s message=%s",
                op,
                exc.error_type,
                exc.retryable,
                exc.message,
            )
            return _error_response(
                status_code=exc.status_code,
                error_type=exc.error_type,
                message=exc.message,
                retryable=exc.retryable,
            )
        except Exception:
            instance_logger.exception("Unexpected instance request failure: op=%s", op)
            return _error_response(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                error_type="INSTANCE_UNEXPECTED",
                message=f"Unexpected instance error during {op}",
                retryable=True,
            )

    return wrapper


def _error_response(
    *,
    status_code: int,
    error_type: InstanceErrorType,
    message: str,
    retryable: bool,
) -> JSONResponse:
    payload = ErrorResponse(
        error_type=error_type,
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
    return parser.parse_args()


def launch():
    args = _parse_args()
    setup_logging(instance_logger, args.log_path, component=f"instances/{args.port}")
    uvicorn.run(
        create_app(args.contexts_per_instance),
        host=args.host,
        port=args.port,
    )


if __name__ == "__main__":
    launch()
