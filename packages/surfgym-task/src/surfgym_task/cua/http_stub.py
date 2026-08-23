"""In-memory stand-in for the CUA-Gym-Hub HTTP state API.

CUA task bundles talk to a Hub app over HTTP in two places:

    initial_setup.py   POST {BASE}/post?sid=  {"action": "set", "state": {...}}
    reward.py          GET  {BASE}/go?sid=    -> {initial_state, current_state, state_diff}

Neither needs a live server. The setup script's POST body *is* the task's
initial state, and the reward script only reads a snapshot SurfGym already
holds. Installing this stub as `requests` lets both run unmodified with no
network access at all.

`BASE` is whatever the bundle carried -- usually an unmaterialized placeholder
like `__CUA_GYM_INSTAGRAM_URL__`. Routing keys off the trailing endpoint
segment, so placeholders and real URLs both work.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Mapping, Optional, cast
from urllib.parse import parse_qsl, urlsplit

type JsonValue = None | str | bool | int | float | list[JsonValue] | dict[str, JsonValue]


class RequestException(IOError):
    """Base class mirroring `requests.exceptions.RequestException`."""


class ConnectionError(RequestException):  # noqa: A001 - mirrors requests' name
    pass


class Timeout(RequestException):
    pass


class HTTPError(RequestException):
    pass


class BlockedRequest(RequestException):
    """Raised when a bundle reaches for a host or endpoint we do not emulate."""


def _empty_diff() -> dict[str, JsonValue]:
    return {}


@dataclass(frozen=True)
class Snapshot:
    """What `GET /go?sid=` returns for one app."""

    initial_state: JsonValue
    current_state: JsonValue
    state_diff: dict[str, JsonValue] = field(default_factory=_empty_diff)

    def to_payload(self, sid: str) -> dict[str, JsonValue]:
        return {
            "sid": sid,
            "initial_state": self.initial_state,
            "current_state": self.current_state,
            "state_diff": self.state_diff,
        }


class StubResponse:
    def __init__(self, status_code: int, payload: JsonValue):
        self.status_code = status_code
        self._payload = payload

    @property
    def ok(self) -> bool:
        return self.status_code < 400

    @property
    def text(self) -> str:
        return json.dumps(self._payload, ensure_ascii=False)

    @property
    def content(self) -> bytes:
        return self.text.encode("utf-8")

    def json(self, **_: object) -> JsonValue:
        return self._payload

    def raise_for_status(self) -> None:
        if not self.ok:
            raise HTTPError(f"stub response status {self.status_code}")


@dataclass(frozen=True)
class _Route:
    base: str
    endpoint: str
    sid: Optional[str]


def _route(url: str) -> _Route:
    parts = urlsplit(url)
    path = parts.path
    head, _, endpoint = path.rpartition("/")
    base = f"{parts.scheme}://{parts.netloc}{head}" if parts.netloc else head
    sid = dict(parse_qsl(parts.query)).get("sid")
    return _Route(base=base.rstrip("/"), endpoint=endpoint, sid=sid)


class HubStub:
    """Serves `/go` and `/state` from `snapshots`; records `/post` bodies.

    A single stub instance covers every app in a task: cross-app bundles use a
    different `BASE` per app, and `recorded` keys those apart by base.
    """

    def __init__(self, snapshots: Optional[Mapping[str, Snapshot]] = None):
        self._snapshots: dict[str, Snapshot] = dict(snapshots or {})
        self.recorded: dict[str, JsonValue] = {}
        self.sids: dict[str, str] = {}

    # -- installed as the `requests` module surface -------------------------

    def get(self, url: str, **_: object) -> StubResponse:
        route = _route(url)
        match route.endpoint:
            case "go":
                snapshot = self._require_snapshot(route)
                return StubResponse(200, snapshot.to_payload(route.sid or ""))
            case "state":
                snapshot = self._require_snapshot(route)
                return StubResponse(
                    200,
                    {
                        "sid": route.sid,
                        "has_custom_state": snapshot.initial_state is not None,
                        "stored_state": snapshot.initial_state,
                    },
                )
            case _:
                raise BlockedRequest(f"GET {url} is not emulated")

    def post(
        self,
        url: str,
        json: Optional[JsonValue] = None,  # noqa: A002 - mirrors requests' kwarg
        data: Optional[object] = None,
        **_: object,
    ) -> StubResponse:
        route = _route(url)
        if route.endpoint != "post":
            raise BlockedRequest(f"POST {url} is not emulated")

        body = json if json is not None else _decode_body(data)
        if not isinstance(body, dict):
            raise BlockedRequest(f"POST {url} body must be a JSON object")

        action = body.get("action")
        match action:
            case "set" | "set_current":
                state: JsonValue = body.get("state")
                self.recorded[route.base] = state
                if route.sid is not None:
                    self.sids[route.base] = route.sid
                existing = self._snapshots.get(route.base)
                initial: JsonValue = (
                    state if action == "set" else (existing.initial_state if existing else state)
                )
                self._snapshots[route.base] = Snapshot(
                    initial_state=initial,
                    current_state=state,
                )
                return StubResponse(200, {"status": "ok", "sid": route.sid})
            case "reset":
                existing = self._snapshots.get(route.base)
                if existing is not None:
                    self._snapshots[route.base] = Snapshot(
                        initial_state=existing.initial_state,
                        current_state=existing.initial_state,
                    )
                return StubResponse(200, {"status": "ok", "sid": route.sid})
            case _:
                raise BlockedRequest(f"POST {url} action={action!r} is not emulated")

    def put(self, url: str, **_: object) -> StubResponse:
        raise BlockedRequest(f"PUT {url} is not emulated")

    def patch(self, url: str, **_: object) -> StubResponse:
        raise BlockedRequest(f"PATCH {url} is not emulated")

    def delete(self, url: str, **_: object) -> StubResponse:
        raise BlockedRequest(f"DELETE {url} is not emulated")

    # -- helpers -----------------------------------------------------------

    def _require_snapshot(self, route: _Route) -> Snapshot:
        snapshot = self._snapshots.get(route.base)
        if snapshot is None:
            # A reward that reads an app we captured nothing for is a porting
            # bug, not a zero score. Surface it instead of silently scoring 0.
            raise BlockedRequest(
                f"no snapshot for base {route.base!r}; have {sorted(self._snapshots)}"
            )
        return snapshot


def _decode_body(data: object) -> JsonValue:
    match data:
        case None:
            return None
        case bytes():
            return cast(JsonValue, json.loads(data.decode("utf-8")))
        case str():
            return cast(JsonValue, json.loads(data))
        case dict():
            return cast(JsonValue, data)
        case _:
            raise BlockedRequest(f"unsupported request body type {type(data).__name__}")
