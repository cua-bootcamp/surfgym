import base64
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from surfgym_contracts.protocol.gateway_to_agent import (
    ActionResponse,
    ErrorResponse,
    ReleaseResponse,
    Response,
    ResponseAdapter,
    RewardResponse,
)


@dataclass(frozen=True)
class ClientResult:
    task_id: str
    snapshot_dir: Path
    reward: float


class Client:
    def __init__(
        self,
        *,
        task_id: str,
        session_id: int,
        actions: list[list[dict[str, Any]]],
        gateway_url: str,
        snapshot_dir: Path,
        snapshot_only: bool = False,
    ):
        self.task_id = task_id
        self.session_id = session_id
        self.actions = actions
        self.snapshot_only = snapshot_only

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
        )
        self._create_snapshots(next(step), start_response)

        if self.snapshot_only:
            release_response = post(
                self.url,
                {
                    "op": "release",
                    "session_id": self.session_id,
                    "task_id": self.task_id,
                },
            )
            self._create_snapshots(next(step), release_response)

            match release_response:
                case ReleaseResponse():
                    return ClientResult(
                        task_id=self.task_id,
                        snapshot_dir=self.snapshot_dir,
                        reward=0.0,
                    )
                case _:
                    raise ValueError("Release failed.")

        for action_batch in self.actions:
            action_response = post(
                self.url,
                {
                    "op": "action",
                    "session_id": self.session_id,
                    "task_id": self.task_id,
                    "actions": action_batch,
                },
            )
            self._create_snapshots(next(step), action_response)

        reward_response = post(
            self.url,
            {
                "op": "reward",
                "session_id": self.session_id,
                "task_id": self.task_id,
            },
        )
        self._create_snapshots(next(step), reward_response)

        match reward_response:
            case RewardResponse():
                return ClientResult(
                    task_id=self.task_id,
                    snapshot_dir=self.snapshot_dir,
                    reward=reward_response.reward,
                )
            case _:
                raise ValueError("Somethings wrooooong!")

    def _step_gen(self):
        step = 0
        while True:
            yield step
            step += 1

    def _create_snapshots(self, step: int, response: Response):
        match response:
            case ActionResponse():
                (self.snapshot_dir / f"screenshot_{step}.png").write_bytes(
                    decode_png_base64(response.image.data)
                )
            case RewardResponse():
                (self.snapshot_dir / "reward.txt").write_text(str(response.reward))
            case ReleaseResponse():
                (self.snapshot_dir / "release.txt").write_text("released\n")
            case ErrorResponse():
                pass


def post(url: str, payload: dict[str, object]) -> Response:
    body = json.dumps(payload).encode("utf-8")

    request = Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urlopen(request, timeout=90) as http_response:
        return ResponseAdapter.validate_json(http_response.read())


def decode_png_base64(data: str) -> bytes:
    raw = base64.b64decode(data, validate=True)
    if not raw.startswith(b"\x89PNG\r\n\x1a\n"):
        raise AssertionError("image.data is not a PNG payload")
    if len(raw) < 1024:
        raise AssertionError(f"image.data is unexpectedly small: {len(raw)} bytes")
    return raw
