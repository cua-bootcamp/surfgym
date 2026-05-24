from typing import TypeVar

import httpx
from fastapi import status
from pydantic import BaseModel
from surfgym_contracts.protocol.gateway_to_upstream import AllocateRequest
from surfgym_contracts.protocol.upstream_to_gateway import (
    AllocateResponse,
    ErrorResponse,
    IdleResponse,
    ReleaseResponse,
)
from surfgym_runtime.support import ProcessTimeout, wavepool_logger

_T = TypeVar("_T", bound=BaseModel)


class InstanceClient:
    def __init__(self, host: str, timeouts: ProcessTimeout):
        self.host = host
        self.timeouts = timeouts
        self.client = httpx.AsyncClient()

    async def close(self) -> None:
        await self.client.aclose()

    def base_url(self, port: int) -> str:
        return f"http://{self.host}:{port}"

    async def allocate(
        self, port: int, request: AllocateRequest
    ) -> AllocateResponse | ErrorResponse:
        response = await self.client.post(
            f"{self.base_url(port)}/allocate",
            json=request.model_dump(mode="json"),
            timeout=self.timeouts.allocate - self.timeouts.layer_gap,
        )
        return _handle_response(response, AllocateResponse, "allocate", port)

    async def release(self, instance_id: str, port: int):
        response = await self.client.post(
            f"{self.base_url(port)}/reset",
            params={"instance_id": instance_id},
            timeout=self.timeouts.release - self.timeouts.layer_gap,
        )
        return _handle_response(response, ReleaseResponse, "release", port)

    async def force_release(self, port: int):
        response = await self.client.post(
            f"{self.base_url(port)}/force_reset",
            timeout=self.timeouts.release - self.timeouts.layer_gap,
        )
        response.raise_for_status()

    async def is_idle(self, port: int) -> bool:
        response = await self.client.post(
            f"{self.base_url(port)}/idle",
            timeout=self.timeouts.release - self.timeouts.layer_gap,
        )
        response.raise_for_status()
        return IdleResponse.model_validate(response.json()).idle


################################################
#               Helper Functions               #
################################################


def _handle_response(
    response: httpx.Response, schema: type[_T], operation: str, port: int
) -> _T | ErrorResponse:
    if response.status_code == status.HTTP_200_OK:
        return schema.model_validate(response.json())

    try:
        return ErrorResponse.model_validate(response.json())
    except Exception:
        body = response.text.strip()

        wavepool_logger.exception(
            "Unknown instance response: operation=%s port=%s status_code=%s body=%r",
            operation,
            port,
            response.status_code,
            body or "<empty body>",
        )

        return ErrorResponse(
            error_type="UNKNOWN_INSTANCE_RESPONSE",
            message=(
                f"Instance returned an unrecognized error response during {operation} "
                f"on port {port} (status={response.status_code})."
            ),
            retryable=True,
        )
