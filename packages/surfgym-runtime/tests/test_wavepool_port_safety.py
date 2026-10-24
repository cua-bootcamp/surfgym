from __future__ import annotations

import subprocess
import os
import sys
import time
from pathlib import Path
from unittest.mock import Mock

import pytest
import httpx
from surfgym_runtime.support.config import ProcessTimeout, WavepoolConfig
from surfgym_runtime.wavepool.launch import ManagedProcess, WavepoolSupervisor
from surfgym_runtime.wavepool.owned_process_windows import OwnedProcessWindows


def _supervisor() -> WavepoolSupervisor:
    config = WavepoolConfig(
        host="127.0.0.1",
        master_port=5500,
        instance_start_port=9000,
        instances=1,
        contexts_per_instance=1,
        process_timeout=ProcessTimeout(
            allocate=1.0,
            release=1.0,
            screenshot=1.0,
            observe=1.0,
            execute=1.0,
            layer_gap=0.1,
        ),
    )
    return WavepoolSupervisor(
        config=config,
        config_path=Path("config.json"),
        log_path=Path("logs"),
    )


def test_setup_fails_without_killing_foreign_port_owner(monkeypatch: pytest.MonkeyPatch) -> None:
    run = Mock(
        return_value=subprocess.CompletedProcess(
            args=["lsof", "-ti", "tcp:9000"],
            returncode=0,
            stdout="123\n456\n",
            stderr="",
        )
    )
    kill = Mock()
    monkeypatch.setattr("surfgym_runtime.wavepool.launch.signal.signal", Mock())
    monkeypatch.setattr("surfgym_runtime.wavepool.launch.subprocess.run", run)
    monkeypatch.setattr("surfgym_runtime.wavepool.launch.os.kill", kill)

    with pytest.raises(RuntimeError, match=r"port 9000.*123, 456"):
        _supervisor()._setup()

    kill.assert_not_called()


def test_setup_accepts_available_ports(monkeypatch: pytest.MonkeyPatch) -> None:
    run = Mock(
        return_value=subprocess.CompletedProcess(
            args=["lsof", "-ti", "tcp:9000"],
            returncode=1,
            stdout="",
            stderr="",
        )
    )
    monkeypatch.setattr("surfgym_runtime.wavepool.launch.signal.signal", Mock())
    monkeypatch.setattr("surfgym_runtime.wavepool.launch.subprocess.run", run)

    _supervisor()._setup()

    assert run.call_count == 2


def test_confirmed_instance_exit_notifies_master_once_and_preserves_sibling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    supervisor = _supervisor()
    exited = Mock()
    exited.poll.return_value = 17
    exited.pid = 111
    healthy = Mock()
    healthy.poll.return_value = None
    healthy.pid = 222
    supervisor.processes = [
        ManagedProcess("instance:9000", exited),
        ManagedProcess("master:5500", healthy),
    ]
    response = Mock()
    monkeypatch.setattr("surfgym_runtime.wavepool.launch.httpx.post", Mock(return_value=response))

    supervisor._check_all_child()
    supervisor._check_all_child()

    assert response.raise_for_status.call_count == 2
    assert healthy.send_signal.call_count == 0


def test_quiescent_exit_retries_only_master_ack_after_notification_loss(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A proven-dead numeric PGID must never be signalled again after an ack loss."""
    supervisor = _supervisor()
    exited = Mock()
    exited.pid = 111
    response = Mock()
    post = Mock(side_effect=[response, httpx.ConnectError("lost ack"), response])
    terminate = Mock()
    drained = Mock(return_value=True)
    monkeypatch.setattr("surfgym_runtime.wavepool.launch._is_windows", lambda: False)
    monkeypatch.setattr("surfgym_runtime.wavepool.launch.httpx.post", post)
    monkeypatch.setattr(supervisor, "_terminate_owned_process_group", terminate)
    monkeypatch.setattr(supervisor, "_owned_process_group_drained", drained)

    supervisor._notify_instance_exit(ManagedProcess("instance:9000", exited), 17)
    supervisor._notify_instance_exit(ManagedProcess("instance:9000", exited), 17)

    terminate.assert_called_once_with(111)
    drained.assert_called_once_with(111)
    assert post.call_count == 3
    assert exited.pid in supervisor._drained_exited_processes
    assert exited.pid in supervisor._quiescent_exited_processes


def test_cleanup_never_resignals_group_already_proven_by_exit_notification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    supervisor = _supervisor()
    dead = Mock()
    dead.pid = 7070
    dead.poll.return_value = 1
    supervisor.processes = [ManagedProcess("instance:7070", dead)]
    supervisor._drained_exited_processes.add(7070)
    terminate = Mock()
    monkeypatch.setattr("surfgym_runtime.wavepool.launch._is_windows", lambda: False)
    monkeypatch.setattr(supervisor, "_terminate_owned_process_group", terminate)

    supervisor.cleanup()

    terminate.assert_not_called()


def test_cleanup_drains_recorded_group_after_parent_has_exited(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    supervisor = _supervisor()
    dead_parent = Mock()
    dead_parent.poll.return_value = 17
    dead_parent.pid = 111
    live_master = Mock()
    live_master.poll.return_value = None
    live_master.pid = 222
    supervisor.processes = [
        ManagedProcess("instance:9000", dead_parent),
        ManagedProcess("master:5500", live_master),
    ]
    drain = Mock()
    signal_group = Mock()
    monkeypatch.setattr(supervisor, "_terminate_owned_process_group", drain)
    monkeypatch.setattr(supervisor, "_owned_process_group_drained", Mock(return_value=True))
    monkeypatch.setattr(supervisor, "_signal_group", signal_group)
    monkeypatch.setattr("surfgym_runtime.wavepool.launch.time.sleep", Mock())
    monkeypatch.setattr("surfgym_runtime.wavepool.launch._is_windows", lambda: False)

    supervisor.cleanup()

    drain.assert_called_once_with(111)
    assert signal_group.call_args_list[0].args == (live_master, __import__("signal").SIGTERM)


@pytest.mark.skipif(os.name != "nt", reason="Windows Job Object cleanup")
def test_cleanup_terminates_dead_parent_owned_job_without_touching_foreign_job(tmp_path: Path) -> None:
    ready = tmp_path / "child-ready"
    child = f"import pathlib,time; pathlib.Path({str(ready)!r}).write_text('x'); time.sleep(60)"
    parent = f"import subprocess,sys; subprocess.Popen([sys.executable,'-c',{child!r}]); sys.exit(0)"
    owned = OwnedProcessWindows.spawn([sys.executable, "-c", parent])
    foreign = OwnedProcessWindows.spawn([sys.executable, "-c", "import time; time.sleep(60)"])
    supervisor = _supervisor()
    supervisor.processes = [ManagedProcess("instance:9000", owned)]
    quiescence_results: list[bool] = []
    original_terminate = owned.terminate_and_check_quiescent

    def terminate_and_record(*, timeout: float) -> bool:
        result = original_terminate(timeout=timeout)
        quiescence_results.append(result)
        return result

    owned.terminate_and_check_quiescent = terminate_and_record  # type: ignore[method-assign]
    try:
        assert owned.wait(timeout=5) == 0
        deadline = time.monotonic() + 5
        while not ready.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert ready.exists()
        supervisor.cleanup()
        assert quiescence_results == [True]
        with pytest.raises(ValueError, match="closed"):
            owned.active_process_count()
        assert foreign.poll() is None
    finally:
        foreign.terminate_and_check_quiescent(timeout=5)
        foreign.close()


@pytest.mark.parametrize("outcome", [False, RuntimeError("job query failed")])
def test_windows_cleanup_attempts_all_owned_trees_and_is_retryable_on_unknown(
    monkeypatch: pytest.MonkeyPatch, outcome: object
) -> None:
    class Owned:
        def __init__(self, result: object) -> None:
            self.result = result
            self.pid = id(self)
            self.closed = False
        def poll(self): return 1
        def terminate_and_check_quiescent(self, *, timeout: float):
            if isinstance(self.result, BaseException): raise self.result
            return self.result
        def close(self): self.closed = True
        def wait(self, timeout: float): return 1
    supervisor = _supervisor()
    first, second = Owned(outcome), Owned(True)
    supervisor.processes = [ManagedProcess("instance:9000", first), ManagedProcess("master:5500", second)]
    monkeypatch.setattr("surfgym_runtime.wavepool.launch._is_windows", lambda: True)
    with pytest.raises(RuntimeError, match="UNKNOWN"):
        supervisor.cleanup()
    assert not first.closed and second.closed
    assert supervisor._cleaned is False
    first.result = True
    supervisor.cleanup()
    assert first.closed and supervisor._cleaned is True


def test_posix_dead_parent_group_escalates_term_to_kill(monkeypatch: pytest.MonkeyPatch) -> None:
    supervisor = _supervisor()
    dead = Mock()
    dead.poll.return_value = 1
    dead.pid = 9000
    supervisor.processes = [ManagedProcess("instance:9000", dead)]
    drained = Mock(side_effect=[False, True, True])
    term = Mock()
    killpg = Mock()
    monkeypatch.setattr("surfgym_runtime.wavepool.launch._is_windows", lambda: False)
    monkeypatch.setattr(supervisor, "_owned_process_group_drained", drained)
    monkeypatch.setattr(supervisor, "_terminate_owned_process_group", term)
    monkeypatch.setattr("surfgym_runtime.wavepool.launch.os.killpg", killpg, raising=False)
    monkeypatch.setattr("surfgym_runtime.wavepool.launch.SHUTDOWN_TIMEOUT_SECONDS", 0)

    supervisor.cleanup()

    term.assert_called_once_with(9000)
    killpg.assert_called_once_with(9000, getattr(__import__("signal"), "SIGKILL", __import__("signal").SIGTERM))


def test_posix_parent_that_exits_after_term_still_requires_group_drain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    supervisor = _supervisor()
    parent = Mock()
    parent.pid = 9001
    parent.poll.side_effect = [None, 1, 1, 1]
    parent.wait.return_value = 1
    signal_group = Mock()
    killpg = Mock()
    # The leader starts live, exits after TERM, but its owned child keeps the
    # session alive until the bounded SIGKILL path completes.
    drained = Mock(side_effect=[False, True, True])
    supervisor.processes = [ManagedProcess("instance:9001", parent)]
    monkeypatch.setattr("surfgym_runtime.wavepool.launch._is_windows", lambda: False)
    monkeypatch.setattr(supervisor, "_signal_group", signal_group)
    monkeypatch.setattr(supervisor, "_owned_process_group_drained", drained)
    monkeypatch.setattr("surfgym_runtime.wavepool.launch.os.killpg", killpg, raising=False)
    monkeypatch.setattr("surfgym_runtime.wavepool.launch.SHUTDOWN_TIMEOUT_SECONDS", 0)

    supervisor.cleanup()

    signal_group.assert_called_once_with(parent, __import__("signal").SIGTERM)
    killpg.assert_called_once_with(9001, getattr(__import__("signal"), "SIGKILL", __import__("signal").SIGTERM))


def test_posix_cleanup_retry_excludes_already_proven_group(monkeypatch: pytest.MonkeyPatch) -> None:
    supervisor = _supervisor()
    unknown, gone = Mock(), Mock()
    unknown.pid, gone.pid = 9010, 9011
    unknown.poll.return_value = gone.poll.return_value = 1
    unknown.wait.return_value = gone.wait.return_value = 1
    supervisor.processes = [
        ManagedProcess("instance:9010", unknown),
        ManagedProcess("instance:9011", gone),
    ]
    terminate = Mock()
    state = {9010: False, 9011: True}
    monkeypatch.setattr("surfgym_runtime.wavepool.launch._is_windows", lambda: False)
    monkeypatch.setattr(supervisor, "_terminate_owned_process_group", terminate)
    monkeypatch.setattr(supervisor, "_owned_process_group_drained", lambda pgid: state[pgid])
    monkeypatch.setattr(
        "surfgym_runtime.wavepool.launch.os.killpg", Mock(side_effect=PermissionError("unknown")), raising=False
    )
    monkeypatch.setattr("surfgym_runtime.wavepool.launch.SHUTDOWN_TIMEOUT_SECONDS", 0)

    with pytest.raises(RuntimeError, match="UNKNOWN"):
        supervisor.cleanup()
    assert [item.process.pid for item in supervisor.processes] == [9010]

    state[9010] = True
    supervisor.cleanup()

    assert terminate.call_args_list == [((9011,), {}), ((9010,), {}), ((9010,), {})]
    assert supervisor._cleaned is True
