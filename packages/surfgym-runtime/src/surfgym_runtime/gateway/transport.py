from functools import lru_cache
from json import JSONDecodeError
from typing import Any, Literal, Optional, TypeVar

import requests
from fastapi import status
from pydantic import BaseModel, ValidationError
from surfgym_contracts.command import Command, ObserveCommand
from surfgym_contracts.protocol.gateway_to_upstream import AllocateRequest
from surfgym_contracts.protocol.upstream_to_gateway import (
    AllocateResponse,
    ErrorResponse,
    ExecuteResponse,
    ObservationResponse,
    ReleaseResponse,
    ScreenshotResponse,
)
from surfgym_contracts.task import Action, Evaluation, ProfileSetup, Website

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
        deadline: Deadline,
        websites: list[Website],
        setup: Optional[list[Action]],
        profile_setup: Optional[ProfileSetup],
    ) -> AllocateResponse:
        timeout = deadline.timeout_for(self._timeouts.allocate)
        return self._master_client.allocate(websites, setup, profile_setup, timeout)

    def release(self, deadline: Deadline, instance_id: str, instance_port: int) -> ReleaseResponse:
        timeout = deadline.timeout_for(self._timeouts.release)
        return self._master_client.release(instance_id, instance_port, timeout)

    def execute(
        self, deadline: Deadline, instance_id: str, instance_port: int, command: Command
    ) -> ExecuteResponse:
        timeout = deadline.timeout_for(self._timeouts.execute)
        return self._instance_client(port=instance_port).execute(instance_id, command, timeout)

    def screenshot(
        self, deadline: Deadline, instance_id: str, instance_port: int
    ) -> ScreenshotResponse:
        timeout = deadline.timeout_for(self._timeouts.screenshot)
        return self._instance_client(instance_port).screenshot(instance_id, timeout)

    def observe(
        self,
        deadline: Deadline,
        instance_id: str,
        instance_port: int,
        evaluation: Evaluation,
    ) -> ObservationResponse:
        timeout = deadline.timeout_for(self._timeouts.observe)
        return self._instance_client(port=instance_port).observe(
            instance_id, ObserveCommand(evaluation=evaluation), timeout
        )

    # def get_interactive_tree(
    #     self, deadline: Deadline, instance_id: str, instance_port: int
    # ) -> InteractiveTreeResponse:
    #     return self.execute(deadline, instance_id, instance_port, InteractiveTreeCommand())


class MasterClient:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port

    def _get_base_url(self):
        return f"http://{self.host}:{self.port}"

    def allocate(
        self,
        websites: list[Website],
        setup: Optional[list[Action]],
        profile_setup: Optional[ProfileSetup],
        timeout: float,
    ):
        request = AllocateRequest(websites=websites, setup=setup, profile_setup=profile_setup)
        return _request_model(
            "POST",
            f"{self._get_base_url()}/allocate",
            AllocateResponse,
            operation="master.allocate",
            json=request.model_dump(mode="json"),
            timeout=timeout,
        )

    def release(self, instance_id: str, instance_port: int, timeout: float):
        return _request_model(
            "POST",
            f"{self._get_base_url()}/release",
            ReleaseResponse,
            operation="master.release",
            params={"instance_id": instance_id, "instance_port": instance_port},
            timeout=timeout,
        )


class InstanceClient:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port

    def _get_base_url(self):
        return f"http://{self.host}:{self.port}"

    def execute(self, instance_id: str, command: Command, timeout: float):
        return _request_model(
            "POST",
            f"{self._get_base_url()}/execute",
            ExecuteResponse,
            operation="instance.execute",
            params={"instance_id": instance_id},
            json=command.model_dump(mode="json"),
            timeout=timeout,
        )

    def observe(self, instance_id: str, command: Command, timeout: float):
        return _request_model(
            "POST",
            f"{self._get_base_url()}/execute",
            ObservationResponse,
            operation="instance.observe",
            params={"instance_id": instance_id},
            json=command.model_dump(mode="json"),
            timeout=timeout,
        )

    def screenshot(self, instance_id: str, timeout: float):
        return _request_model(
            "GET",
            f"{self._get_base_url()}/screenshot",
            ScreenshotResponse,
            operation="instance.screenshot",
            params={"instance_id": instance_id},
            timeout=timeout,
        )


################################################
#               Helper Functions               #
################################################

HttpMethod = Literal["GET", "POST"]


def _request_model(
    method: HttpMethod,
    url: str,
    schema: type[_T],
    *,
    operation: str,
    timeout: float,
    **kwargs: Any,
) -> _T:
    response = _request(method, url, operation=operation, timeout=timeout, **kwargs)
    return _decode_response(response, schema, operation=operation)


def _request(
    method: HttpMethod,
    url: str,
    *,
    operation: str,
    timeout: float,
    **kwargs: Any,
) -> requests.Response:
    try:
        return requests.request(method, url, timeout=timeout, **kwargs)
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
(error_type) {payload.error_type}
(message) {payload.message}
(status) {response.status_code} "
""".strip()

    if payload.retryable:
        raise RetryableError(message)

    raise UpstreamError(message)
