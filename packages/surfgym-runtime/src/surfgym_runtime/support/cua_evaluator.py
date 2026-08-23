"""Execute an imported CUA-Gym reward script against supplied JSON snapshots.

The original scripts read ``/tmp/task_web_sid`` and call the mock app's
``GET /go?sid=...`` endpoint. SurfGym already owns the browser state, so this
adapter supplies both dependencies in memory and blocks real HTTP requests.

This subprocess boundary is sufficient for migration parity testing. It is not
a security boundary for arbitrary third-party Python; production ingestion must
add OS-level isolation before accepting unreviewed bundles.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass
from typing import Mapping, Optional, cast

from surfgym_contracts.task import Value

_REWARD_PATTERN = re.compile(r"^REWARD:\s*(-?(?:\d+(?:\.\d*)?|\.\d+))\s*$", re.MULTILINE)
_RUNNER = r'''
import io, json, sys, types
from urllib.parse import urlsplit

request = json.loads(sys.stdin.read())
snapshots = request["snapshots"]

class RequestException(IOError): pass
class ConnectionError(RequestException): pass
class Timeout(RequestException): pass
class HTTPError(RequestException): pass

class Response:
    def __init__(self, payload):
        self.status_code = 200
        self._payload = payload
    @property
    def ok(self): return True
    @property
    def text(self): return json.dumps(self._payload, ensure_ascii=False)
    @property
    def content(self): return self.text.encode("utf-8")
    def json(self, **_kwargs): return self._payload
    def raise_for_status(self): return None

def base_from_url(url):
    parts = urlsplit(url)
    head, _, endpoint = parts.path.rpartition("/")
    if endpoint not in ("go", "state"):
        raise RequestException(f"GET endpoint is not emulated: {url}")
    return (f"{parts.scheme}://{parts.netloc}{head}" if parts.netloc else head).rstrip("/")

def get(url, **_kwargs):
    base = base_from_url(url)
    if base not in snapshots:
        raise RequestException(f"no snapshot for app base {base!r}")
    return Response(snapshots[base])

def blocked(method):
    def call(url, **_kwargs):
        raise RequestException(f"{method} is not available during reward evaluation: {url}")
    return call

requests_module = types.ModuleType("requests")
requests_module.get = get
requests_module.post = blocked("POST")
requests_module.put = blocked("PUT")
requests_module.patch = blocked("PATCH")
requests_module.delete = blocked("DELETE")
exceptions_module = types.ModuleType("requests.exceptions")
for name, exc in (("RequestException", RequestException), ("ConnectionError", ConnectionError),
                  ("Timeout", Timeout), ("HTTPError", HTTPError)):
    setattr(requests_module, name, exc)
    setattr(exceptions_module, name, exc)
requests_module.exceptions = exceptions_module
sys.modules["requests"] = requests_module
sys.modules["requests.exceptions"] = exceptions_module

def task_open(file, mode="r", *_args, **_kwargs):
    name = str(file).replace("\\", "/")
    if name == "/tmp/task_web_sid" and "r" in mode:
        return io.StringIO(request["sid"])
    raise PermissionError(f"reward file access is blocked: {name}")

captured = io.StringIO()
real_stdout = sys.stdout
sys.stdout = captured
error = None
try:
    namespace = {
        "__name__": "__main__",
        "__file__": f"{request['source_task_id']}/reward.py",
        "open": task_open,
    }
    exec(compile(request["source"], namespace["__file__"], "exec"), namespace)
except SystemExit as exc:
    if exc.code not in (0, None):
        error = f"SystemExit: {exc.code}"
except BaseException as exc:
    error = f"{type(exc).__name__}: {exc}"
finally:
    sys.stdout = real_stdout

json.dump({"stdout": captured.getvalue(), "error": error}, real_stdout)
'''


@dataclass(frozen=True)
class CuaSnapshot:
    initial_state: Value
    current_state: Value

    def payload(self, sid: str) -> dict[str, Value]:
        return {
            "sid": sid,
            "initial_state": self.initial_state,
            "current_state": self.current_state,
            "state_diff": _state_diff(self.initial_state, self.current_state),
        }


@dataclass(frozen=True)
class CuaRewardResult:
    reward: float
    stdout: str


def evaluate_cua_reward(
    source: str,
    *,
    source_task_id: str,
    sid: str,
    snapshots: Mapping[str, CuaSnapshot],
    timeout: float,
) -> CuaRewardResult:
    request = {
        "source": source,
        "source_task_id": source_task_id,
        "sid": sid,
        "snapshots": {base: snapshot.payload(sid) for base, snapshot in snapshots.items()},
    }
    completed = subprocess.run(
        [sys.executable, "-I", "-c", _RUNNER],
        input=json.dumps(request),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    if completed.returncode != 0 or not completed.stdout.strip():
        detail = (completed.stderr or completed.stdout).strip()[-2000:]
        raise RuntimeError(f"CUA reward runner failed (rc={completed.returncode}): {detail}")

    payload = cast(dict[str, Optional[str]], json.loads(completed.stdout))
    if payload.get("error"):
        raise RuntimeError(f"CUA reward script failed: {payload['error']}")

    stdout = payload.get("stdout") or ""
    matches = _REWARD_PATTERN.findall(stdout)
    if matches:
        return CuaRewardResult(reward=max(0.0, min(1.0, float(matches[-1]))), stdout=stdout)

    # Some original scripts never print a `REWARD:` label -- they just
    # `print(result)` as their last line. Confirmed against the real dataset:
    # of the tasks with no `REWARD:` label anywhere, the ones that are genuine
    # single-app Hub scripts (not empty, not desktop-only) overwhelmingly take
    # this shape. Only accept it when the last non-blank line is nothing but
    # a bare number, so a descriptive final line still fails loudly instead of
    # being misread as a reward.
    last_line = stdout.strip().splitlines()[-1].strip() if stdout.strip() else ""
    try:
        bare_value = float(last_line)
    except ValueError:
        raise RuntimeError("CUA reward script did not print a REWARD value")

    return CuaRewardResult(reward=max(0.0, min(1.0, bare_value)), stdout=stdout)


def _state_diff(initial: Value, current: Value) -> dict[str, Value]:
    """Match the Hub mocks' top-level state-diff shape."""
    if not isinstance(current, dict):
        return {}
    initial_dict = initial if isinstance(initial, dict) else {}
    diff: dict[str, Value] = {}
    for key, value in current.items():
        if key not in initial_dict:
            diff[key] = {"added": value}
        elif initial_dict[key] != value:
            diff[key] = {"modified": value}
    return diff
