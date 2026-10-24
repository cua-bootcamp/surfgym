from typing import Any, TypeVar

import httpx
from fastapi import status
from pydantic import BaseModel, ValidationError
from surfgym_contracts.protocol.gateway_to_upstream import (
    GatewayAllocateRequest,
    GatewayReleaseRequest,
    LiveContextsResponse,
    MasterAllocateRequest,
)
from surfgym_contracts.protocol.upstream_to_gateway import (
    ErrorResponse,
    InstanceAllocateResponse,
    MasterReleaseResponse,
)

from surfgym_runtime.support import ProcessTimeout
from surfgym_runtime.wavepool.master.error import (
    InstanceRequestFailed,
    MasterError,
    UnexpectedError,
)
from surfgym_runtime.wavepool.master.registry import Lease, NativeCleanupBinding, WebCleanupBinding
from surfgym_runtime.wavepool.bindings import web_cleanup_cookie
from surfgym_runtime.wavepool.allocation_budget import (
    ALLOCATION_REMAINING_HEADER,
    encode_remaining_seconds,
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

    async def allocate(
        self,
        port: int,
        context_id: str,
        request: MasterAllocateRequest,
        *,
        timeout: float | None = None,
        remaining_seconds: float | None = None,
    ) -> InstanceAllocateResponse:
        configured_timeout = self.timeouts.allocate - self.timeouts.layer_gap
        timeout = configured_timeout if timeout is None else min(configured_timeout, timeout)
        headers = (
            {
                ALLOCATION_REMAINING_HEADER: encode_remaining_seconds(
                    min(remaining_seconds, timeout - self.timeouts.layer_gap)
                )
            }
            if remaining_seconds is not None
            else None
        )
        response = await _post(
            self.client,
            f"{self.base_url(port)}/allocate",
            operation="allocate",
            port=port,
            params={"context_id": context_id},
            json=request.model_dump(mode="json"),
            timeout=timeout,
            headers=headers,
        )
        return _handle_response(response, InstanceAllocateResponse, "allocate", port)

    async def release(self, context_id: str, port: int, request: GatewayReleaseRequest):
        response = await _post(
            self.client,
            f"{self.base_url(port)}/release",
            operation="release",
            port=port,
            params={"context_id": context_id},
            json=request.model_dump(mode="json"),
            timeout=self.timeouts.release - self.timeouts.layer_gap,
        )
        return _handle_response(response, MasterReleaseResponse, "release", port)

    async def live_context_ids(self, port: int) -> tuple[str, ...]:
        try:
            response = await self.client.get(
                f"{self.base_url(port)}/contexts",
                timeout=self.timeouts.release - self.timeouts.layer_gap,
            )
        except httpx.TimeoutException as exc:
            raise InstanceRequestFailed(
                f"Instance request timed out: operation=contexts port={port}"
            ) from exc
        except httpx.RequestError as exc:
            raise InstanceRequestFailed(
                f"Instance request failed: operation=contexts port={port} "
                f"error={type(exc).__name__}"
            ) from exc
        return _handle_response(response, LiveContextsResponse, "contexts", port).context_ids

    async def release_retained_bindings(self, lease: Lease) -> None:
        for binding in lease.native_bindings:
            await self._release_native_binding(lease.context_id, binding)
        for binding in lease.web_bindings:
            await self._finalize_web_binding(lease.context_id, binding)

    async def _release_native_binding(
        self, context_id: str, binding: NativeCleanupBinding
    ) -> None:
        response = await self._retained_request(
            "POST",
            f"{binding.origin}/release-context",
            json={
                "context_id": context_id,
                "website_id": binding.website_id,
                "cleanup_capability": binding.cleanup_capability,
            },
        )
        _require_cleanup_complete(response, "native binding release")

    async def _finalize_web_binding(self, context_id: str, binding: WebCleanupBinding) -> None:
        cookie = web_cleanup_cookie(context_id, binding.origin, binding.cookie_name)
        response = await self._retained_request(
            "DELETE",
            f"{binding.origin}{binding.reset_path}",
            headers={"X-SurfGym-Finalize": "1"},
            cookies={binding.cookie_name: cookie},
        )
        _require_cleanup_complete(response, "web binding finalization")

    async def _retained_request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        try:
            return await self.client.request(
                method,
                url,
                timeout=self.timeouts.release - self.timeouts.layer_gap,
                **kwargs,
            )
        except httpx.RequestError as exc:
            raise InstanceRequestFailed("retained binding cleanup response is UNKNOWN") from exc


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
        message=payload.message,
        status_code=response.status_code,
        retryable=payload.retryable,
    )


def _require_cleanup_complete(response: httpx.Response, operation: str) -> None:
    if response.status_code != status.HTTP_200_OK:
        raise InstanceRequestFailed(f"{operation} is incomplete")
    try:
        body: object = response.json()
    except ValueError as exc:
        raise InstanceRequestFailed(f"{operation} returned invalid JSON") from exc
    if not isinstance(body, dict):
        raise InstanceRequestFailed(f"{operation} returned an invalid response")
    if body.get("ok") is not True or body.get("cleanup_complete") is not True:
        raise InstanceRequestFailed(f"{operation} is incomplete")
