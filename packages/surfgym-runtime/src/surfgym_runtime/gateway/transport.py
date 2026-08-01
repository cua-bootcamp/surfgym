from functools import lru_cache
from json import JSONDecodeError
from typing import Any, TypeVar

import requests
from fastapi import status
from pydantic import BaseModel, ValidationError
from surfgym_contracts.command import Command
from surfgym_contracts.protocol.gateway_to_upstream import (
    ExecuteRequest,
    GatewayAllocateRequest,
    GatewayReleaseRequest,
    ObserveRequest,
    ScreenshotRequest,
)
from surfgym_contracts.protocol.upstream_to_gateway import (
    ErrorResponse,
    ExecuteResponse,
    MasterAllocateResponse,
    MasterReleaseResponse,
    ObserveResponse,
    ScreenshotResponse,
)
from surfgym_contracts.task import Criteria, Hook, Website

from surfgym_runtime.gateway.error import Deadline, RetryableError, UpstreamError
from surfgym_runtime.support.config import WavepoolConfig

_T = TypeVar("_T", bound=BaseModel)


class GatewayTransport:
    def __init__(
        self,
        wavepool_config: WavepoolConfig,
    ):
        self.host = wavepool_config.host
        self._config = wavepool_config
        self._timeouts = wavepool_config.process_timeout
        self._master_client = MasterClient(
            host=wavepool_config.host, port=wavepool_config.master_port
        )

    @lru_cache(maxsize=None)
    def _instance_client(self, port: int):
        return InstanceClient(host=self.host, port=port)

    def allocate(
        self,
        *,
        deadline: Deadline,
        websites: list[Website],
        allocate_hooks: list[Hook],
    ) -> MasterAllocateResponse:
        timeout = deadline.timeout_for(self._timeouts.allocate)
        return self._master_client.allocate(
            websites=websites, allocate_hooks=allocate_hooks, timeout=timeout
        )

    def release(self, *, deadline: Deadline, context_id: str, release_hooks: list[Hook]):
        timeout = deadline.timeout_for(self._timeouts.release)
        return self._master_client.release(
            context_id=context_id, release_hooks=release_hooks, timeout=timeout
        )

    def execute(
        self, deadline: Deadline, context_id: str, instance_port: int, command: Command
    ) -> ExecuteResponse:
        timeout = deadline.timeout_for(self._timeouts.execute)
        return self._instance_client(instance_port).execute(
            context_id=context_id, command=command, timeout=timeout
        )

    def screenshot(
        self, deadline: Deadline, context_id: str, instance_port: int
    ) -> ScreenshotResponse:
        timeout = deadline.timeout_for(self._timeouts.screenshot)
        return self._instance_client(instance_port).screenshot(
            context_id=context_id, timeout=timeout
        )

    def observe(
        self,
        *,
        deadline: Deadline,
        context_id: str,
        instance_port: int,
        criteria: list[Criteria],
        observe_hooks: list[Hook],
    ) -> ObserveResponse:
        timeout = deadline.timeout_for(self._timeouts.observe)
        return self._instance_client(instance_port).observe(
            context_id=context_id,
            criteria=criteria,
            observe_hooks=observe_hooks,
            timeout=timeout,
        )


class MasterClient:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port

    def _get_base_url(self):
        return f"http://{self.host}:{self.port}"

    def allocate(
        self,
        *,
        websites: list[Website],
        allocate_hooks: list[Hook],
        timeout: float,
    ):
        return _request_model(
            f"{self._get_base_url()}/allocate",
            MasterAllocateResponse,
            operation="master.allocate",
            json=GatewayAllocateRequest(websites=websites, hooks=allocate_hooks).model_dump(
                mode="json"
            ),
            timeout=timeout,
        )

    def release(self, *, context_id: str, release_hooks: list[Hook], timeout: float):
        return _request_model(
            f"{self._get_base_url()}/release",
            MasterReleaseResponse,
            operation="master.release",
            params={"context_id": context_id},
            json=GatewayReleaseRequest(hooks=release_hooks).model_dump(mode="json"),
            timeout=timeout,
        )


class InstanceClient:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port

    def _get_base_url(self):
        return f"http://{self.host}:{self.port}"

    def execute(self, *, context_id: str, command: Command, timeout: float):
        return _request_model(
            f"{self._get_base_url()}/execute",
            ExecuteResponse,
            operation="instance.execute",
            params={"context_id": context_id},
            json=ExecuteRequest(command=command).model_dump(mode="json"),
            timeout=timeout,
        )

    def observe(
        self,
        *,
        context_id: str,
        criteria: list[Criteria],
        observe_hooks: list[Hook],
        timeout: float,
    ):
        return _request_model(
            f"{self._get_base_url()}/observe",
            ObserveResponse,
            operation="instance.observe",
            params={"context_id": context_id},
            json=ObserveRequest(criteria=criteria, hooks=observe_hooks).model_dump(mode="json"),
            timeout=timeout,
        )

    def screenshot(self, *, context_id: str, timeout: float):
        return _request_model(
            f"{self._get_base_url()}/screenshot",
            ScreenshotResponse,
            operation="instance.screenshot",
            params={"context_id": context_id},
            json=ScreenshotRequest().model_dump(mode="json"),
            timeout=timeout,
        )


################################################
#               Helper Functions               #
################################################


def _request_model(
    url: str,
    response_schema: type[_T],
    *,
    operation: str,
    timeout: float,
    **kwargs: Any,
) -> _T:
    response = _request(url, operation=operation, timeout=timeout, **kwargs)
    return _decode_response(response, response_schema, operation=operation)


def _request(
    url: str,
    *,
    operation: str,
    timeout: float,
    **kwargs: Any,
) -> requests.Response:
    try:
        return requests.request("POST", url, timeout=timeout, **kwargs)
    except requests.exceptions.Timeout as exc:
        raise RetryableError(
            f"Upstream request timed out: operation={operation} url={url}"
        ) from exc
    except requests.exceptions.ConnectionError as exc:
        raise RetryableError(
            f"Upstream connection failed: operation={operation} url={url}"
        ) from exc
    except requests.exceptions.RequestException as exc:
        raise RetryableError(
            f"Upstream request failed: operation={operation} url={url} error={type(exc).__name__}"
        ) from exc


def _decode_response(
    response: requests.Response,
    schema: type[_T],
    *,
    operation: str,
) -> _T:
    try:
        body: object = response.json() if response.content.strip() else {}
    except JSONDecodeError:
        raise UpstreamError(
            f"""
Upstream returned invalid JSON response.
(operation) {operation}
(status) {response.status_code}
""".strip()
        )

    if response.status_code == status.HTTP_200_OK:
        try:
            return schema.model_validate(body)
        except ValidationError:
            raise UpstreamError(
                f"""
Upstream returned invalid success response.
(operation) {operation}
(status) {response.status_code}
""".strip()
            )

    try:
        payload = ErrorResponse.model_validate(body)
    except ValidationError:
        raise UpstreamError(
            f"""
Upstream returned invalid error response.
(operation) {operation}
(status) {response.status_code}
""".strip()
        )

    message = f"""
Upstream failed while handling operation.
(operation) {operation}
(message) {payload.message}
(status) {response.status_code} "
""".strip()

    if payload.retryable:
        raise RetryableError(message)

    raise UpstreamError(message)
