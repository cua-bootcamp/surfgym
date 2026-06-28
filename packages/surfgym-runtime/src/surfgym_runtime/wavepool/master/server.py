import argparse
import asyncio
from contextlib import asynccontextmanager
from functools import wraps
from pathlib import Path
from typing import Annotated, Awaitable, Callable, ParamSpec, TypeVar

import uvicorn
from fastapi import Body, FastAPI, status
from fastapi.responses import JSONResponse
from surfgym_contracts.protocol.gateway_to_upstream import AllocateRequest, ReleaseRequest
from surfgym_contracts.protocol.upstream_to_gateway import ErrorResponse, UpstreamErrorType

from surfgym_runtime.support import WavepoolConfig, load_config, master_logger, setup_logging
from surfgym_runtime.wavepool.master.error import MasterError
from surfgym_runtime.wavepool.master.service import MasterService, SlotRegistry

_P = ParamSpec("_P")
_T = TypeVar("_T")


def create_app(config: WavepoolConfig) -> FastAPI:
    registry = SlotRegistry(
        instance_start_port=config.instance_start_port,
        instance_n=config.instances,
        contexts_per_instance=config.contexts_per_instance,
    )

    master = MasterService(registry, config)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        recover_task = asyncio.create_task(master.recover_loop())
        try:
            yield
        finally:
            recover_task.cancel()
            await master.close()

    @handle_master_errors
    async def allocate(request: Annotated[AllocateRequest, Body()]):
        return await master.allocate(request)

    @handle_master_errors
    async def release(
        instance_id: str,
        instance_port: int,
        request: Annotated[ReleaseRequest, Body()],
    ):
        return await master.release(instance_id, instance_port, request)

    async def health():
        return {"status": "ok"}

    app = FastAPI(lifespan=lifespan)
    app.add_api_route("/health", health, methods=["GET"])
    app.add_api_route("/allocate", allocate, methods=["POST"])
    app.add_api_route("/release", release, methods=["POST"])

    return app


def handle_master_errors(
    func: Callable[_P, Awaitable[_T]],
) -> Callable[_P, Awaitable[_T | JSONResponse]]:
    @wraps(func)
    async def wrapper(*args: _P.args, **kwargs: _P.kwargs) -> _T | JSONResponse:
        op = func.__name__

        try:
            return await func(*args, **kwargs)
        except MasterError as exc:
            master_logger.warning(
                "Master request failed: op=%s error_type=%s retryable=%s message=%s",
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
            master_logger.exception("Unexpected master request failure: op=%s", op)
            return _error_response(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                error_type="UNEXPECTED",
                message=f"Unexpected master error during {op}",
                retryable=True,
            )

    return wrapper


def _error_response(
    *,
    status_code: int,
    error_type: UpstreamErrorType,
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
    parser.add_argument("config_path", type=Path)
    return parser.parse_args()


def launch() -> None:
    args = _parse_args()
    config = load_config(args.config_path)
    setup_logging(master_logger, config.log_path, component="master")

    uvicorn.run(
        create_app(config.wavepool_config),
        host=config.wavepool_config.host,
        port=config.wavepool_config.master_port,
    )


if __name__ == "__main__":
    launch()
