from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def _bash() -> str:
    candidate = Path(r"D:\Program Files\Git\bin\bash.exe")
    if candidate.is_file():
        return str(candidate)
    found = shutil.which("bash")
    if found:
        return found
    raise RuntimeError("Git Bash is required for the verification-script contract")


def _write_fake_python(path: Path) -> None:
    path.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
[[ -z "${PYTHON_BIN:-}" ]] || { echo 'public PYTHON_BIN leaked into pytest' >&2; exit 91; }
[[ -f scripts/local_dev.bash ]] || { echo 'verifier did not change to repository root' >&2; exit 92; }
for argument in \"$@\"; do
  case \"$argument\" in
    --junitxml=*) mkdir -p \"$(dirname \"${argument#--junitxml=}\")\"; printf '<testsuite/>\\n' > \"${argument#--junitxml=}\" ;;
    --log-file=*) mkdir -p \"$(dirname \"${argument#--log-file=}\")\"; printf 'fake pytest log\\n' > \"${argument#--log-file=}\" ;;
  esac
done
exit \"${FAKE_PYTHON_EXIT:-0}\"
""",
        encoding="utf-8",
        newline="\n",
    )
    path.chmod(0o755)


def _run_verify(tmp_path: Path, *, exit_code: int) -> tuple[subprocess.CompletedProcess[str], Path]:
    fake_python = tmp_path / "fake-python.bash"
    _write_fake_python(fake_python)
    output_root = tmp_path / "reports"
    environment = os.environ | {
        "PYTHON_BIN": str(fake_python),
        "VERIFY_OUTPUT_ROOT": str(output_root),
        "VERIFY_RUN_ID": "contract-run",
        "VERIFY_BASETEMP": str(tmp_path / "basetemp"),
        "FAKE_PYTHON_EXIT": str(exit_code),
    }
    completed = subprocess.run(
        [_bash(), str(ROOT / "scripts" / "verify.sh")],
        cwd=tmp_path,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return completed, output_root / "contract-run"


def test_verify_script_writes_reports_for_each_selected_suite(tmp_path: Path) -> None:
    """Fails if the verifier stops emitting durable JUnit and pytest logs for a suite."""
    completed, run_root = _run_verify(tmp_path, exit_code=0)

    assert completed.returncode == 0, completed.stderr
    assert sorted(path.name for path in (run_root / "junit").glob("*.xml")) == [
        "contracts.xml",
        "fixture.xml",
        "runtime.xml",
        "snapshots-chrome-cua.xml",
        "task.xml",
    ]
    assert sorted(path.name for path in (run_root / "logs").glob("*.log")) == [
        "console.log",
        "contracts.log",
        "fixture.log",
        "runtime.log",
        "snapshots-chrome-cua.log",
        "task.log",
    ]


def test_verify_script_keeps_pytest_failure_exit_after_writing_reports(tmp_path: Path) -> None:
    """Fails if the shell wrapper masks a pytest failure while producing a green-looking report."""
    completed, run_root = _run_verify(tmp_path, exit_code=7)

    assert completed.returncode == 7
    assert (run_root / "junit" / "contracts.xml").is_file()
    assert (run_root / "logs" / "contracts.log").is_file()
