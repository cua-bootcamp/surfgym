from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

from surfgym_runtime.wavepool.owned_process_windows import OwnedProcessWindows


pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows Job Object test")


def test_spawn_rejects_empty_command_before_allocating_windows_resources() -> None:
    with pytest.raises(ValueError, match="args must not be empty"):
        OwnedProcessWindows.spawn([])


def test_failed_create_process_does_not_poison_a_later_owned_launch(tmp_path: Path) -> None:
    with pytest.raises(OSError, match="CreateProcessW"):
        OwnedProcessWindows.spawn([str(tmp_path / "does-not-exist.exe")])

    process = OwnedProcessWindows.spawn([sys.executable, "-c", "pass"])
    try:
        assert process.wait(timeout=5) == 0
        assert process.wait_for_quiescence(timeout=2)
    finally:
        process.close()


def test_poll_reports_a_completed_process_with_windows_still_active_exit_code() -> None:
    process = OwnedProcessWindows.spawn([sys.executable, "-c", "raise SystemExit(259)"])
    try:
        assert process.wait(timeout=5) == 259
        assert process.poll() == 259
        assert process.wait_for_quiescence(timeout=2)
    finally:
        process.close()


def test_terminate_and_check_quiescent_kills_grandchild_without_touching_sibling(
    tmp_path: Path,
) -> None:
    """The parent exiting is insufficient: job accounting must include its child."""
    ready = tmp_path / "grandchild-ready"
    child = (
        "import pathlib,time; "
        f"pathlib.Path({str(ready)!r}).write_text('ready'); "
        "time.sleep(60)"
    )
    parent = (
        "import subprocess,sys; "
        f"subprocess.Popen([sys.executable, '-c', {child!r}]); "
        "sys.exit(0)"
    )
    process = OwnedProcessWindows.spawn([sys.executable, "-c", parent])
    sibling = OwnedProcessWindows.spawn([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        assert process.wait(timeout=5) == 0
        deadline = time.monotonic() + 5
        while not ready.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert ready.exists(), "the owned child did not start"
        assert process.active_process_count() >= 1
        started = time.monotonic()
        assert process.terminate_and_check_quiescent(timeout=5)
        print(f"tree_join_seconds={time.monotonic() - started:.3f}")
        assert process.active_process_count() == 0
        assert sibling.poll() is None
    finally:
        process.close()
        sibling.terminate_and_check_quiescent(timeout=5)
        sibling.close()
