import argparse
import asyncio
from contextlib import asynccontextmanager
from typing import Annotated, Optional

import httpx
import uvicorn
from fastapi import Body, FastAPI
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from surfgym_contracts import Action, Website
from surfgym_contracts.protocol.gateway_to_upstream import AllocateRequest
from surfgym_contracts.protocol.master_to_gateway import (
    GetInstanceResponse as MasterGetInstanceResponse,
)
from surfgym_contracts.protocol.master_to_gateway import MasterServerErrorType
from surfgym_contracts.protocol.upstream_to_gateway import GetInstanceResponse, StatusResponse
from surfgym_runtime.wavepool.master.error import error_response

parser = argparse.ArgumentParser()
parser.add_argument("--master_host", type=str)
parser.add_argument("--master_port", type=int)

parser.add_argument("--instance_host", type=str)
parser.add_argument("--instance_start_port", type=int)
parser.add_argument("--instances", type=int)
args = parser.parse_args()


class PortRegistry:
    def __init__(self, instance_host: str, instance_start_port: int, instance_n: int):
        self.instance_host = instance_host

        ports = [instance_start_port + i for i in range(instance_n)]
        self.available_ports: set[int] = set(ports)
        self.broken_ports: set[int] = set()
        self.recovering_ports: set[int] = set()

        self.lock = asyncio.Lock()

        # [TODO] timeout 처리 어떻게하지..? 길게 해서 나중에 gateway에서 알아서 끊게..?
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        await self.client.aclose()

    async def allocate(self, websites: list[Website], setup: Optional[list[Action]]):
        async with self.lock:
            port = self.available_ports.pop() if self.available_ports else None

        if port is None and self.broken_ports:
            await self._attempt_recover_batch()
            async with self.lock:
                port = self.available_ports.pop() if self.available_ports else None

        if port is None:
            return error_response(
                MasterServerErrorType.NO_INSTANCES_AVAILABLE,
                "no available instances at the moment.",
            )

        try:
            request = AllocateRequest(websites=websites, setup=setup)
            response = await self.client.post(
                f"{self._get_base_url(port)}/get", json=request.model_dump(mode="json")
            )

            if response.status_code != 200:
                await self._mark_broken(port)
                return JSONResponse(
                    status_code=response.status_code,
                    content=response.json(),
                )

            try:
                payload = GetInstanceResponse.model_validate(response.json())
            except (ValidationError, ValueError) as exc:
                await self._mark_broken(port)
                return error_response(
                    MasterServerErrorType.INVALID_PAYLOAD,
                    (
                        f"Invalid /get payload from instance server on port {port}: {exc}. "
                        f"Body: {response.text.strip() or '<empty body>'}"
                    ),
                )
            return MasterGetInstanceResponse(
                instance_id=payload.instance_id,
                instance_host=self.instance_host,
                instance_port=port,
            )

        except Exception:
            await self._mark_broken(port)
            raise

    async def reset(self, instance_id: str, port: int):
        try:
            response = await self.client.post(
                self._get_base_url(port) + "/reset",
                params={"instance_id": instance_id},
            )

            if response.status_code != 200:
                await self._mark_broken(port)
                return self._proxy_instance_error(response, port=port, context="/get")

            async with self.lock:
                self.available_ports.add(port)

        except Exception:
            await self._mark_broken(port)
            raise

    def _get_base_url(self, port: int):
        return f"http://{self.instance_host}:{port}"

    async def _attempt_recover_once(self, port: int):
        base_url = self._get_base_url(port)

        try:
            res = await self.client.get(base_url + "/idle")
            if res.status_code == 200:
                payload = StatusResponse.model_validate(res.json())
                if payload.idle:
                    await self._mark_available_from_broken(port)
                    return True

            if (await self.client.post(base_url + "/force_reset")).status_code != 200:
                return False

            res = await self.client.get(base_url + "/idle")
            if res.status_code != 200:
                await self._mark_broken(port)
                return self._proxy_instance_error(res, port=port, context="/reset")

            payload = StatusResponse.model_validate(res.json())
            if payload.idle:
                await self._mark_available_from_broken(port)
                return True

            return False
        except (httpx.HTTPError, ValueError, ValidationError):
            return False
        finally:
            await self._finish_recovery_attempt(port)

    def _proxy_instance_error(
        self,
        response: httpx.Response,
        *,
        port: int,
        context: str,
    ) -> JSONResponse:
        try:
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError(f"expected JSON object, got {type(payload).__name__}")
        except ValueError:
            payload = {
                "error_type": MasterServerErrorType.INVALID_PAYLOAD.value,
                "message": (
                    f"Instance server {context} failed on port {port} "
                    f"(status={response.status_code}). "
                    f"Body: {response.text.strip() or '<empty body>'}"
                ),
            }

        return JSONResponse(status_code=response.status_code, content=payload)

    async def _attempt_recover_batch(self) -> int:
        async with self.lock:
            candidates = list(self.broken_ports - self.recovering_ports)
            for port in candidates:
                self.recovering_ports.add(port)

        recovered = 0
        for port in candidates:
            ok = await self._attempt_recover_once(port)
            if ok:
                recovered += 1

        return recovered

    async def _mark_broken(self, port: int) -> None:
        async with self.lock:
            self.available_ports.discard(port)
            self.broken_ports.add(port)

    async def _mark_available_from_broken(self, port: int) -> None:
        async with self.lock:
            self.broken_ports.discard(port)
            self.recovering_ports.discard(port)
            self.available_ports.add(port)

    async def _finish_recovery_attempt(self, port: int) -> None:
        async with self.lock:
            self.recovering_ports.discard(port)

    async def recover_loop(self):
        while True:
            await asyncio.sleep(5)
            await self._attempt_recover_batch()


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(port_registry.recover_loop())
    try:
        yield
    finally:
        task.cancel()
        await port_registry.close()


app = FastAPI(lifespan=lifespan)
port_registry = PortRegistry(args.instance_host, args.instance_start_port, args.instances)


@app.post("/get")
async def get_instance(
    request: Annotated[AllocateRequest, Body()],
):
    return await port_registry.allocate(request.websites, request.setup)


@app.post("/reset")
async def reset_instance(instance_id: str, instance_port: int):
    return await port_registry.reset(instance_id, instance_port)


@app.get("/health")
async def health():
    return {"status": "ok"}


# [TODO] Support multi worker
if __name__ == "__main__":
    uvicorn.run(
        app,
        host=args.master_host,
        port=args.master_port,
    )
