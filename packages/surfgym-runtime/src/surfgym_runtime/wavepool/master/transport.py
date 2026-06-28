from typing import Any, TypeVar

import httpx
from fastapi import status
from pydantic import BaseModel, ValidationError
from surfgym_contracts.protocol.gateway_to_upstream import AllocateRequest, ReleaseRequest
from surfgym_contracts.protocol.upstream_to_gateway import (
    ErrorResponse,
    GetInstanceResponse,
    IdleResponse,
    ReleaseResponse,
)

from surfgym_runtime.support import ProcessTimeout
from surfgym_runtime.wavepool.master.error import (
    InstanceRequestFailed,
    MasterError,
    UnexpectedError,
)

_T = TypeVar("_T", bound=BaseModel)


async def _post(
    client: httpx.AsyncClient,
    url: str,
    *,
    operation: str,
    port: int,
    timeout: float,
    **kwargs: Any,
) -> httpx.Response:
    try:
        return await client.post(url, timeout=timeout, **kwargs)
    except httpx.TimeoutException as exc:
        raise InstanceRequestFailed(
            f"Instance request timed out: operation={operation} port={port} url={url}"
        ) from exc
    except httpx.ConnectError as exc:
        raise InstanceRequestFailed(
            f"Instance connection failed: operation={operation} port={port} url={url}"
        ) from exc
    except httpx.RequestError as exc:
        raise InstanceRequestFailed(
            f"Instance request failed: operation={operation} port={port} "
            f"url={url} error={type(exc).__name__}"
        ) from exc


class InstanceClient:
    def __init__(self, host: str, timeouts: ProcessTimeout):
        self.host = host
        self.timeouts = timeouts
        self.client = httpx.AsyncClient()

    async def close(self) -> None:
        await self.client.aclose()

    def base_url(self, port: int) -> str:
        return f"http://{self.host}:{port}"

    async def allocate(self, port: int, request: AllocateRequest) -> str:
        response = await _post(
            self.client,
            f"{self.base_url(port)}/allocate",
            operation="allocate",
            port=port,
            json=request.model_dump(mode="json"),
            timeout=self.timeouts.allocate - self.timeouts.layer_gap,
        )
        return _handle_response(response, GetInstanceResponse, "allocate", port).instance_id

    async def release(
        self, instance_id: str, port: int, request: ReleaseRequest
    ) -> ReleaseResponse:
        response = await _post(
            self.client,
            f"{self.base_url(port)}/reset",
            operation="release",
            port=port,
            params={"instance_id": instance_id},
            json=request.model_dump(mode="json"),
            timeout=self.timeouts.release - self.timeouts.layer_gap,
        )
        return _handle_response(response, ReleaseResponse, "release", port)

    async def force_release(self, port: int) -> None:
        response = await _post(
            self.client,
            f"{self.base_url(port)}/force_reset",
            operation="force_release",
            port=port,
            timeout=self.timeouts.release - self.timeouts.layer_gap,
        )
        _handle_response(response, ReleaseResponse, "force_release", port)

    async def is_idle(self, port: int) -> bool:
        response = await _post(
            self.client,
            f"{self.base_url(port)}/idle",
            operation="is_idle",
            port=port,
            timeout=self.timeouts.release - self.timeouts.layer_gap,
        )
        return _handle_response(response, IdleResponse, "is_idle", port).idle


################################################
#               Helper Functions               #
################################################


def _handle_response(response: httpx.Response, schema: type[_T], operation: str, port: int) -> _T:
    try:
        body: object = response.json() if response.content.strip() else {}
    except ValueError as exc:
        raise UnexpectedError(
            f"Instance returned invalid JSON response (status={response.status_code})"
        ) from exc
    if response.status_code == status.HTTP_200_OK:
        try:
            return schema.model_validate(body)
        except ValidationError as exc:
            raise UnexpectedError(
                f"Instance returned invalid success response: operation={operation} "
                f"port={port} status={response.status_code}"
            ) from exc

    try:
        payload = ErrorResponse.model_validate(body)
    except ValidationError:
        raise UnexpectedError(
            f"Instance returned invalid error response (status={response.status_code})"
        )

    raise MasterError(
        error_type=payload.error_type,
        message=payload.message,
        status_code=response.status_code,
        retryable=payload.retryable,
    )
