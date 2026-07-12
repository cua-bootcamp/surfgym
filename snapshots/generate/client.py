import base64
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from surfgym_contracts.protocol.gateway_to_agent import (
    ActionResponse,
    DEVRewardResponse,
    ErrorResponse,
    Response,
    ResponseAdapter,
    RewardResponse,
)

SNAPSHOT_GATEWAY_REQUEST_TIMEOUT_SECONDS = 600


@dataclass(frozen=True)
class ClientResult:
    task_id: str
    snapshot_dir: Path
    reward: float


class SnapshotClientError(RuntimeError):
    pass


class SnapshotGatewayError(SnapshotClientError):
    def __init__(self, *, operation: str, response: ErrorResponse):
        self.operation = operation
        self.response = response

        super().__init__(
            "\n".join(
                [
                    "Snapshot gateway returned an error response.",
                    f"(operation) {operation}",
                    f"(session_id) {response.session_id}",
                    f"(task_id) {response.task_id}",
                    f"(error_type) {response.error_type}",
                    f"(message) {response.message}",
                    "(response)",
                    response_json(response).rstrip(),
                ]
            )
        )


class SnapshotHttpError(SnapshotClientError):
    def __init__(self, *, operation: str, url: str, status: int | None, body: str):
        super().__init__(
            "\n".join(
                [
                    "Snapshot gateway HTTP request failed.",
                    f"(operation) {operation}",
                    f"(url) {url}",
                    f"(status) {status}",
                    "(body)",
                    body,
                ]
            )
        )


class Client:
    def __init__(
        self,
        *,
        task_id: str,
        session_id: int,
        actions: list[list[dict[str, Any]]],
        gateway_url: str,
        snapshot_dir: Path,
    ):
        self.task_id = task_id
        self.session_id = session_id

        self.snapshot_dir = snapshot_dir
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)

        self.url = gateway_url

    def run(
        self,
    ):
        step = self._step_gen()

        start_response = post(
            self.url,
            {
                "op": "start",
                "session_id": self.session_id,
                "task_id": self.task_id,
            },
            operation="start",
        )
        self._create_snapshots(next(step), "start", start_response)
        self._raise_if_error("start", start_response)

        reward_response = post(
            self.url,
            {
                "op": "reward",
                "session_id": self.session_id,
                "task_id": self.task_id,
            },
            operation="reward",
        )
        self._create_snapshots(next(step), "reward", reward_response)
        self._raise_if_error("reward", reward_response)
        return self._result_from_reward_response(reward_response)

    def _result_from_reward_response(self, response: Response) -> ClientResult:
        match response:
            case DEVRewardResponse():
                return ClientResult(
                    task_id=self.task_id,
                    snapshot_dir=self.snapshot_dir,
                    reward=response.reward,
                )
            case _:
                raise ValueError(
                    f"Expected DEVRewardResponse with a screenshot, "
                    f"got {type(response).__name__}: "
                    f"{response_json(response)}"
                )

    def _step_gen(self):
        step = 0
        while True:
            yield step
            step += 1

    def _create_snapshots(self, step: int, operation: str, response: Response):
        match response:
            case ActionResponse():
                (self.snapshot_dir / f"screenshot_{step}.png").write_bytes(
                    decode_png_base64(response.image.data)
                )
            case RewardResponse():
                raise ValueError(
                    "Expected DEVRewardResponse with a screenshot for reward snapshots, "
                    "got RewardResponse. Launch the gateway with DEV=1."
                )
            case DEVRewardResponse():
                (self.snapshot_dir / "reward.txt").write_text(str(response.reward))
                (self.snapshot_dir / f"screenshot_{step}.png").write_bytes(
                    decode_png_base64(response.image.data)
                )
            case ErrorResponse():
                (self.snapshot_dir / f"error_{step}_{operation}.json").write_text(
                    response_json(response),
                    encoding="utf-8",
                )
            case _:
                raise ValueError(f"Unexpected response type: {type(response).__name__}")

    def _raise_if_error(self, operation: str, response: Response) -> None:
        if isinstance(response, ErrorResponse):
            raise SnapshotGatewayError(operation=operation, response=response)


def post(url: str, payload: dict[str, object], *, operation: str) -> Response:
    body = json.dumps(payload).encode("utf-8")

    request = Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(
            request,
            timeout=SNAPSHOT_GATEWAY_REQUEST_TIMEOUT_SECONDS,
        ) as http_response:
            return ResponseAdapter.validate_json(http_response.read())
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise SnapshotHttpError(
            operation=operation,
            url=url,
            status=exc.code,
            body=error_body,
        ) from exc
    except URLError as exc:
        raise SnapshotHttpError(
            operation=operation,
            url=url,
            status=None,
            body=str(exc),
        ) from exc


def response_json(response: Response) -> str:
    return (
        json.dumps(
            response.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )


def decode_png_base64(data: str) -> bytes:
    raw = base64.b64decode(data, validate=True)
    if not raw.startswith(b"\x89PNG\r\n\x1a\n"):
        raise AssertionError("image.data is not a PNG payload")
    if len(raw) < 1024:
        raise AssertionError(f"image.data is unexpectedly small: {len(raw)} bytes")
    return raw
