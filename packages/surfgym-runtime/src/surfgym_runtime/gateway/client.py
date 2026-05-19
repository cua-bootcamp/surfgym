from typing import Any, Optional

import requests
from surfgym_contracts.command import Command
from surfgym_contracts.protocol.gateway_to_instance import GetInstanceRequest
from surfgym_contracts.task import Action, Website

from surfgym_runtime.gateway.error import InstanceTransportError


class _RequestsProxy:
    def post(self, *args: Any, **kwargs: Any) -> requests.Response:
        try:
            return requests.post(*args, **kwargs)
        except requests.exceptions.RequestException as exc:
            raise InstanceTransportError(f"requests.post failed: {exc}") from exc

    def get(self, *args: Any, **kwargs: Any) -> requests.Response:
        try:
            return requests.get(*args, **kwargs)
        except requests.exceptions.RequestException as exc:
            raise InstanceTransportError(f"requests.get failed: {exc}") from exc


_requests = _RequestsProxy()


class MasterClient:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port

    def _get_base_url(self):
        return f"http://{self.host}:{self.port}"

    def get_instance(self, websites: list[Website], setup: Optional[Action]):
        request = GetInstanceRequest(websites=websites, setup=setup)
        return _requests.post(
            f"{self._get_base_url()}/get",
            json=request.model_dump(mode="json"),
        )

    def reset(self, instance_id: str, instance_port: int):
        return _requests.post(
            f"{self._get_base_url()}/reset",
            params={"instance_id": instance_id, "instance_port": instance_port},
        )


class InstanceClient:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port

    def _get_base_url(self):
        return f"http://{self.host}:{self.port}"

    def execute(self, instance_id: str, command: Command):
        return _requests.post(
            f"{self._get_base_url()}/execute",
            params={
                "instance_id": instance_id,
            },
            json=command.model_dump(mode="json"),
        )

    def screenshot(self, instance_id: str):
        return _requests.get(
            f"{self._get_base_url()}/screenshot",
            params={"instance_id": instance_id},
        )
