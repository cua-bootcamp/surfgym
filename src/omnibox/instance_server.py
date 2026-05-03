import argparse
import base64
import logging
import uuid
from contextlib import asynccontextmanager
from typing import Annotated, Any

import uvicorn
from fastapi import Body, FastAPI
from fastapi.responses import JSONResponse
from pydantic import TypeAdapter, ValidationError

from src.omnibox.playwright_instance import PlaywrightInstance
from src.omnibox.protocol.instance_server_response import (
    GetInstanceResponse,
    InstanceServerErrorType,
    ScreenshotResponse,
    StatusResponse,
    error_response,
)
from src.omnibox.protocol.omnibox_command import OmniboxCommand

parser = argparse.ArgumentParser()
parser.add_argument("--port", type=int, required=True)
args = parser.parse_args()

command_adapter = TypeAdapter(OmniboxCommand)
instance = PlaywrightInstance()

logger = logging.getLogger(__name__)


async def _validate_instance_id(instance_id: str) -> JSONResponse | None:
    if await instance.idle():
        return error_response(
            InstanceServerErrorType.INSTANCE_IDLE,
            "instance is idle. cannot perform the actions that require an active instance.",
        )

    if instance.id != instance_id:
        return error_response(
            InstanceServerErrorType.INVALID_INSTANCE_ID,
            f"instance id #{instance_id} is not running on port #{args.port}.",
        )

    return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await instance.delete()


app = FastAPI(lifespan=lifespan)


@app.post("/get")
async def get_instance():
    if not await instance.idle():
        return error_response(
            InstanceServerErrorType.INSTANCE_NOT_IDLE,
            "cannot create a new instance when the instance is not idle.",
        )

    new_instance_id = str(uuid.uuid4())

    try:
        await instance.create(new_instance_id)
    except Exception as exc:
        logger.exception("Playwright instance creation failed on port %s", args.port)

        try:
            await instance.delete()
        except Exception:
            logger.exception("Failed to cleanup partially created instance on port %s", args.port)

        return error_response(
            InstanceServerErrorType.CREATE_FAILED,
            (
                f"Playwright instance creation failed on port {args.port}: "
                f"{type(exc).__name__}: {exc}"
            ),
        )

    return GetInstanceResponse(instance_id=new_instance_id)


@app.post(
    "/reset",
)
async def reset_instance(instance_id: str):
    invalid = await _validate_instance_id(instance_id)
    if invalid is not None:
        return invalid

    await instance.delete()


@app.get(
    "/screenshot",
)
async def screenshot_instance(instance_id: str):
    invalid = await _validate_instance_id(instance_id)
    if invalid is not None:
        return invalid

    screenshot = await instance.screenshot()
    screenshot_b64 = base64.b64encode(screenshot.getvalue()).decode("ascii")

    return ScreenshotResponse(
        snapshot_b64=screenshot_b64,
        media_type="image/png",
    )


@app.post("/execute")
async def execute_instance(
    instance_id: str,
    command_data: Annotated[dict[str, Any], Body(...)],
):
    invalid = await _validate_instance_id(instance_id)
    if invalid is not None:
        return invalid

    try:
        command = command_adapter.validate_python(command_data)
    except ValidationError as exc:
        return error_response(
            InstanceServerErrorType.INVALID_COMMAND,
            msg=f"Invalid command data.\n{exc}",
        )

    return await instance.execute(command)


@app.get("/idle")
async def get_status():
    return StatusResponse(
        idle=await instance.idle(),
    )


@app.post("/force_reset")
async def force_reset():
    if not await instance.idle():
        await instance.delete()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    uvicorn.run(app, host="0.0.0.0", port=args.port)
