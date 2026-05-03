from typing import Any

import requests

from src.gateway.error import OmniBoxTransportError
from src.omnibox.protocol.omnibox_command import OmniboxCommand


class _RequestsProxy:
    def post(self, *args: Any, **kwargs: Any) -> requests.Response:
        try:
            return requests.post(*args, **kwargs)
        except requests.exceptions.RequestException as exc:
            raise OmniBoxTransportError(f"requests.post failed: {exc}") from exc

    def get(self, *args: Any, **kwargs: Any) -> requests.Response:
        try:
            return requests.get(*args, **kwargs)
        except requests.exceptions.RequestException as exc:
            raise OmniBoxTransportError(f"requests.get failed: {exc}") from exc


_requests = _RequestsProxy()


class MasterClient:
    def __init__(self, host, port):
        self.host = host
        self.port = port

    def _get_base_url(self):
        return f"http://{self.host}:{self.port}"

    def get_instance(self):
        url = f"{self._get_base_url()}/get"
        return _requests.post(
            url,
        )

    def reset(self, instance_id: str, instance_port: int):
        return _requests.post(
            f"{self._get_base_url()}/reset",
            params={"instance_id": instance_id, "instance_port": instance_port},
        )


class InstanceClient:
    def __init__(self, host, port):
        self.host = host
        self.port = port

    def _get_base_url(self):
        return f"http://{self.host}:{self.port}"

    def execute(self, instance_id: str, command: OmniboxCommand):
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
