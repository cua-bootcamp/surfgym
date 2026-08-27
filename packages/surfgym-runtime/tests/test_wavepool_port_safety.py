from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest
from surfgym_runtime.support.config import ProcessTimeout, WavepoolConfig
from surfgym_runtime.wavepool.launch import WavepoolSupervisor


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
