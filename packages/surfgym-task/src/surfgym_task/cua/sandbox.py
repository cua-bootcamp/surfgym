"""Run a CUA task bundle script with the network and the desktop stubbed out.

`initial_setup.py` and `reward.py` are third-party scripts written against a
live Hub server, a real `/tmp`, and a real Chrome. We run them unmodified --
they are the porting oracle, so rewriting them would defeat the point -- but in
a child process where:

  * `requests` is `http_stub.HubStub`   (no sockets)
  * `subprocess` is a no-op recorder    (no Chrome, no shell)
  * `time.sleep` returns immediately    (setup scripts wait on the browser)
  * `uuid.uuid4` is fixed               (sid must be reproducible)
  * `open()` on the bundle's scratch paths is served from memory

A child process also bounds the blast radius of a hang or a crash, which an
in-process `exec` would not.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from typing import Mapping, Optional, cast

from surfgym_task.cua.http_stub import JsonValue, Snapshot

DEFAULT_TIMEOUT_S = 60.0
FIXED_UUID = "00000000-0000-4000-8000-000000000000"

_RUNNER = r'''
import io, json, sys, types

request = json.loads(sys.stdin.read())

from surfgym_task.cua.http_stub import (
    BlockedRequest, ConnectionError, HTTPError, HubStub, RequestException,
    Snapshot, Timeout,
)

snapshots = {
    base: Snapshot(
        initial_state=payload.get("initial_state"),
        current_state=payload.get("current_state"),
        state_diff=payload.get("state_diff") or {},
    )
    for base, payload in request["snapshots"].items()
}
stub = HubStub(snapshots)

requests_module = types.ModuleType("requests")
requests_module.get = stub.get
requests_module.post = stub.post
requests_module.put = stub.put
requests_module.patch = stub.patch
requests_module.delete = stub.delete
exceptions = types.ModuleType("requests.exceptions")
for _name, _exc in (
    ("RequestException", RequestException), ("ConnectionError", ConnectionError),
    ("Timeout", Timeout), ("HTTPError", HTTPError), ("BlockedRequest", BlockedRequest),
):
    setattr(exceptions, _name, _exc)
    setattr(requests_module, _name, _exc)
requests_module.exceptions = exceptions
sys.modules["requests"] = requests_module
sys.modules["requests.exceptions"] = exceptions

launched = []
subprocess_module = types.ModuleType("subprocess")
subprocess_module.DEVNULL = -3
subprocess_module.PIPE = -1
subprocess_module.STDOUT = -2
class _Popen:
    def __init__(self, args, *a, **kw):
        launched.append(args)
        self.pid = 0
        self.returncode = 0
    def communicate(self, *a, **kw): return (b"", b"")
    def wait(self, *a, **kw): return 0
    def poll(self): return 0
    def kill(self): pass
    def terminate(self): pass
subprocess_module.Popen = _Popen
def _run(args, *a, **kw):
    launched.append(args)
    return types.SimpleNamespace(returncode=0, stdout=b"", stderr=b"")
subprocess_module.run = _run
subprocess_module.call = lambda args, *a, **kw: (launched.append(args), 0)[1]
subprocess_module.check_call = subprocess_module.call
subprocess_module.check_output = lambda args, *a, **kw: (launched.append(args), b"")[1]
class _CalledProcessError(Exception): pass
subprocess_module.CalledProcessError = _CalledProcessError
sys.modules["subprocess"] = subprocess_module

import time as _time
_time.sleep = lambda *_a, **_kw: None

import uuid as _uuid
_fixed = _uuid.UUID(request["fixed_uuid"])
_uuid.uuid4 = lambda: _fixed

# The bundles keep the sid in a scratch file. Serve those paths from memory so
# nothing touches the real filesystem, and let genuinely unexpected paths fail.
_vfs = dict(request.get("vfs") or {})
_ALLOWED = ("/tmp/", "./tmp/")
_real_open = open
def _open(file, mode="r", *args, **kwargs):
    name = str(file).replace("\\", "/")
    if name.startswith(_ALLOWED):
        if "w" in mode or "a" in mode:
            buf = io.StringIO()
            _close = buf.close
            def _finish(_name=name, _buf=buf, _close=_close):
                _vfs[_name] = _buf.getvalue()
                _close()
            buf.close = _finish
            buf.__exit__ = lambda *exc: _finish()
            return buf
        if name not in _vfs:
            raise FileNotFoundError(name)
        return io.StringIO(_vfs[name])
    return _real_open(file, mode, *args, **kwargs)

stdout = io.StringIO()
_real_stdout = sys.stdout
sys.stdout = stdout

error = None
try:
    namespace = {"__name__": "__main__", "__file__": request["filename"], "open": _open}
    exec(compile(request["source"], request["filename"], "exec"), namespace)
except SystemExit as exc:
    if exc.code not in (0, None):
        error = f"SystemExit: {exc.code}"
except BaseException as exc:
    error = f"{type(exc).__name__}: {exc}"
finally:
    sys.stdout = _real_stdout

json.dump(
    {
        "recorded": stub.recorded,
        "sids": stub.sids,
        "stdout": stdout.getvalue(),
        "vfs": _vfs,
        "launched": [str(item) for item in launched],
        "error": error,
    },
    sys.stdout,
)
'''


@dataclass(frozen=True)
class BundleRun:
    recorded: dict[str, JsonValue]
    """base URL (or placeholder) -> the state the script POSTed."""

    sids: dict[str, str]
    stdout: str
    vfs: dict[str, str]
    launched: list[str]
    error: Optional[str]

    @property
    def ok(self) -> bool:
        return self.error is None


def run_bundle_script(
    source: str,
    *,
    filename: str = "bundle_script.py",
    snapshots: Optional[Mapping[str, Snapshot]] = None,
    vfs: Optional[Mapping[str, str]] = None,
    fixed_uuid: str = FIXED_UUID,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> BundleRun:
    request = {
        "source": source,
        "filename": filename,
        "fixed_uuid": fixed_uuid,
        "vfs": dict(vfs or {}),
        "snapshots": {
            base: {
                "initial_state": snapshot.initial_state,
                "current_state": snapshot.current_state,
                "state_diff": snapshot.state_diff,
            }
            for base, snapshot in (snapshots or {}).items()
        },
    }

    completed = subprocess.run(
        [sys.executable, "-c", _RUNNER],
        input=json.dumps(request),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_s,
    )

    if completed.returncode != 0 or not completed.stdout.strip():
        detail = (completed.stderr or completed.stdout).strip()[-2000:]
        return BundleRun({}, {}, "", {}, [], f"runner failed (rc={completed.returncode}): {detail}")

    payload = cast(dict[str, object], json.loads(completed.stdout))
    return BundleRun(
        recorded=cast(dict[str, JsonValue], payload["recorded"]),
        sids=cast(dict[str, str], payload["sids"]),
        stdout=cast(str, payload["stdout"]),
        vfs=cast(dict[str, str], payload["vfs"]),
        launched=cast(list[str], payload["launched"]),
        error=cast(Optional[str], payload["error"]),
    )
