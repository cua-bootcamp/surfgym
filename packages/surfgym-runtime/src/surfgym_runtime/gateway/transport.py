from functools import lru_cache
from typing import Any, Optional, TypeVar

import requests
from fastapi import status
from pydantic import BaseModel, ValidationError
from surfgym_contracts import Observation
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
from surfgym_contracts.task import Action, Evaluation, Website

from surfgym_runtime.gateway.error import Deadline, RetryableError, Upstream
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

    def allocate(self, deadline: Deadline, websites: list[Website], setup: Optional[list[Action]]):
        timeout = deadline.timeout_for(self._timeouts.allocate)
        response = self._master_client.allocate(websites, setup, timeout)
        payload = _handle_response(response, AllocateResponse)
        return (payload.instance_id, payload.instance_port)

    def release(self, deadline: Deadline, instance_id: str, instance_port: int) -> None:
        timeout = deadline.timeout_for(self._timeouts.release)
        response = self._master_client.release(instance_id, instance_port, timeout)
        _handle_response(response, ReleaseResponse)

    def execute(
        self, deadline: Deadline, instance_id: str, instance_port: int, command: Command
    ) -> None:
        timeout = deadline.timeout_for(self._timeouts.execute)
        response = self._instance_client(port=instance_port).execute(instance_id, command, timeout)
        _handle_response(response, ExecuteResponse)

    def screenshot(self, deadline: Deadline, instance_id: str, instance_port: int):
        timeout = deadline.timeout_for(self._timeouts.screenshot)
        response = self._instance_client(instance_port).screenshot(instance_id, timeout)
        payload = _handle_response(response, ScreenshotResponse)
        return payload.snapshot_b64, payload.media_type, payload.x, payload.y

    def observe(
        self,
        deadline: Deadline,
        instance_id: str,
        instance_port: int,
        evaluation: Evaluation,
    ) -> list[Observation]:
        timeout = deadline.timeout_for(self._timeouts.observe)
        response = self._instance_client(port=instance_port).execute(
            instance_id, ObserveCommand(evaluation=evaluation), timeout
        )
        payload = _handle_response(response, ObservationResponse)
        return payload.observation

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

    def allocate(self, websites: list[Website], setup: Optional[list[Action]], timeout: float):
        request = AllocateRequest(websites=websites, setup=setup)
        return _post(
            f"{self._get_base_url()}/allocate",
            json=request.model_dump(mode="json"),
            timeout=timeout,
        )

    def release(self, instance_id: str, instance_port: int, timeout: float):
        return _post(
            f"{self._get_base_url()}/release",
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
        return _post(
            f"{self._get_base_url()}/execute",
            params={
                "instance_id": instance_id,
            },
            json=command.model_dump(mode="json"),
            timeout=timeout,
        )

    def screenshot(self, instance_id: str, timeout: float):
        return _get(
            f"{self._get_base_url()}/screenshot",
            params={"instance_id": instance_id},
            timeout=timeout,
        )


################################################
#               Helper Functions               #
################################################


def _post(url: str, *, timeout: float, **kwargs: Any) -> requests.Response:
    try:
        return requests.post(url, timeout=timeout, **kwargs)
    except requests.exceptions.Timeout as exc:
        raise RetryableError(f"Upstream request timed out: {url}") from exc
    except requests.exceptions.ConnectionError as exc:
        raise RetryableError(f"Upstream connection failed: {url}") from exc
    except requests.exceptions.RequestException as exc:
        raise RetryableError(f"Upstream request failed: {url}") from exc


def _get(url: str, *, timeout: float, **kwargs: Any) -> requests.Response:
    try:
        return requests.get(url, timeout=timeout, **kwargs)
    except requests.exceptions.Timeout as exc:
        raise RetryableError(f"Upstream request timed out: {url}") from exc
    except requests.exceptions.ConnectionError as exc:
        raise RetryableError(f"Upstream connection failed: {url}") from exc
    except requests.exceptions.RequestException as exc:
        raise RetryableError(f"Upstream request failed: {url}") from exc


def _handle_response(response: requests.Response, schema: type[_T]) -> _T:
    try:
        body: object = response.json() if response.content.strip() else {}
    except ValueError as exc:
        raise Upstream(
            f"Upstream returned invalid JSON response (status={response.status_code})"
        ) from exc

    if response.status_code == status.HTTP_200_OK:
        return schema.model_validate(body)

    try:
        payload = ErrorResponse.model_validate(body)
    except ValidationError as exc:
        raise Upstream(
            f"Upstream returned invalid error response (status={response.status_code})"
        ) from exc

    if payload.retryable:
        raise RetryableError(f"Upstream retryable error: {payload.error_type}: {payload.message}")

    raise Upstream(
        f"""
Upstream failed handling request.
[DETAIL] 
    error_type={payload.error_type}
    message={payload.message}
""".strip()
    )
