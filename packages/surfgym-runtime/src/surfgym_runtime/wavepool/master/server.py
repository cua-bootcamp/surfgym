import asyncio
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Body, FastAPI
from surfgym_contracts.protocol.gateway_to_upstream import AllocateRequest
from surfgym_runtime.support import WavepoolConfig
from surfgym_runtime.wavepool.master.service import MasterService, PortRegistry


def launch(wavepool_config: WavepoolConfig) -> FastAPI:
    registry = PortRegistry(
        instance_start_port=wavepool_config.instance_start_port,
        instance_n=wavepool_config.instances,
    )

    master = MasterService(registry, wavepool_config)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        recover_task = asyncio.create_task(master.recover_loop())
        try:
            yield
        finally:
            recover_task.cancel()
            await master.close()

    async def allocate(request: Annotated[AllocateRequest, Body()]):
        return await master.allocate(request)

    async def release(instance_id: str, instance_port: int):
        return await master.release(instance_id, instance_port)

    async def health():
        return {"status": "ok"}

    app = FastAPI(lifespan=lifespan)
    app.add_api_route("/health", health, methods=["GET"])
    app.add_api_route("/allocate", allocate, methods=["POST"])
    app.add_api_route("/release", release, methods=["POST"])

    return app
