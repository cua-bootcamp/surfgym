from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "scripts"


def read_script(name: str) -> str:
    return (SCRIPTS / name).read_text(encoding="utf-8")


def bash_executable() -> str:
    bash = shutil.which("bash")
    git = shutil.which("git")
    if os.name == "nt" and git:
        git_bash = Path(git).resolve().parent.parent / "bin" / "bash.exe"
        if git_bash.is_file():
            return str(git_bash)
    if bash:
        return bash
    pytest.skip("bash is not available")


def write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8", newline="\n")
    path.chmod(0o755)


def run_bash(
    cwd: Path, command: str, *, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    return subprocess.run(
        [bash_executable(), "-lc", command],
        cwd=cwd,
        env=merged_env,
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )


def copy_scripts(destination: Path, *names: str) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for name in names:
        shutil.copy2(SCRIPTS / name, destination / name)


def wait_for_file(path: Path, timeout: float = 5) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.exists() and path.stat().st_size:
            return
        time.sleep(0.05)
    raise AssertionError(f"timed out waiting for {path}")


def minimal_surf_config(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "task_file_path": "unused.sqlite3",
                "log_path": "logs",
                "gateway": {"host": "127.0.0.1", "port": 18000},
                "wavepool": {
                    "host": "127.0.0.1",
                    "master_port": 5500,
                    "instance_start_port": 9000,
                    "instances": 1,
                },
            }
        ),
        encoding="utf-8",
    )


def test_setting_uses_only_explicit_or_legacy_config() -> None:
    script = read_script("setting.sh")

    assert 'if [[ -n "${SURFGYM_CONFIG:-}" ]]' in script
    assert 'readonly SURFGYM_CONFIG="$LEGACY_SURFGYM_CONFIG"' in script
    assert 'elif [[ -f "$GENERATED_SURFGYM_CONFIG" ]]' not in script


def test_local_dev_restores_git_bash_tool_path() -> None:
    script = read_script("local_dev.bash")

    assert 'export PATH="${BASH%/*}:$PATH"' in script


def test_local_dev_aligns_docker_supervisor_readiness_timeout() -> None:
    script = read_script("local_dev.bash")

    assert 'READY_TIMEOUT_SECONDS="${SURFGYM_LOCAL_READY_TIMEOUT_SECONDS:-360}"' in script
    assert 'STACK_READY_TIMEOUT_SECONDS="$READY_TIMEOUT_SECONDS"' in script


def test_component_launchers_use_configured_runtime_python() -> None:
    for name in ("gateway_launch.bash", "wavepool_launch.bash"):
        script = read_script(name)
        assert 'exec env PYTHONUNBUFFERED=1 "$RUNTIME_PYTHON" -m' in script
        assert "exec env PYTHONUNBUFFERED=1 python -m" not in script


@pytest.mark.skipif(os.name != "nt", reason="PowerShell to Git Bash is Windows-specific")
def test_powershell_enters_local_dev_with_a_windows_only_path(tmp_path: Path) -> None:
    surf, docker, env = make_local_dev_sandbox(tmp_path)
    powershell = shutil.which("powershell.exe")
    if not powershell:
        pytest.skip("powershell.exe is not available")

    bash = bash_executable()
    windows_system = Path(os.environ["SystemRoot"]) / "System32"
    entry_env = os.environ.copy()
    entry_env.update(env)
    entry_env.update(
        {
            # Reproduce a PowerShell-owned PATH without Git's usr/bin tools.
            "PATH": str(windows_system),
            "PYTHON_BIN": (surf / "bin" / "python-stub").as_posix(),
            "STUB_COMPILER_ARGS": (surf / "compiler.args").as_posix(),
            "STUB_DOCKER_ARGS": (surf / "docker.args").as_posix(),
            "STUB_PROPAGATION": (surf / "propagation.log").as_posix(),
            "ENTRY_BASH": bash,
            "ENTRY_SCRIPT": (surf / "scripts" / "local_dev.bash").as_posix(),
            "ENTRY_DOCKER": docker.as_posix(),
        }
    )

    result = subprocess.run(
        [
            powershell,
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "& $env:ENTRY_BASH $env:ENTRY_SCRIPT check --docker-repo $env:ENTRY_DOCKER",
        ],
        cwd=surf,
        env=entry_env,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Configuration check passed" in result.stdout
    compiler_args = (surf / "compiler.args").read_text(encoding="utf-8")
    assert "--check-prerequisites" in compiler_args
    assert "--check-host-ports" in compiler_args
    assert "--check" in compiler_args.split()


def test_all_launch_records_identity_and_all_stop_consumes_pid_file(tmp_path: Path) -> None:
    surf = tmp_path / "surf"
    scripts = surf / "scripts"
    copy_scripts(
        scripts,
        "all_launch.bash",
        "all_stop.bash",
        "process_identity.sh",
        "setting.sh",
    )
    for component in ("gateway", "wavepool", "fixture"):
        write_executable(
            scripts / f"{component}_launch.bash", "#!/usr/bin/env bash\nexec sleep 60\n"
        )
    config = surf / "config.json"
    minimal_surf_config(config)
    pid_file = surf / "run.pids"
    env = {
        "SURFGYM_CONFIG": str(config),
        "SURFGYM_PID_FILE": str(pid_file),
        "SURFGYM_STOP_GRACE_SECONDS": "1",
    }

    launched = run_bash(surf, "bash scripts/all_launch.bash", env=env)
    assert launched.returncode == 0, launched.stderr
    records = [line.split(maxsplit=3) for line in pid_file.read_text().splitlines()]
    assert len(records) == 3
    assert all(len(record) == 4 for record in records)
    assert all(record[2].startswith(("linux:", "windows:")) for record in records)

    stopped = run_bash(surf, "bash scripts/all_stop.bash run.pids", env=env)
    assert stopped.returncode == 0, stopped.stderr
    assert not pid_file.exists()


@pytest.mark.skipif(os.name != "nt", reason="MSYS native PID transitions are Windows-specific")
def test_windows_delayed_native_exec_records_final_identity_and_stops_safely(
    tmp_path: Path,
) -> None:
    assert "capture_process_identity_after_exec" in read_script("all_launch.bash")
    surf = tmp_path / "surf"
    scripts = surf / "scripts"
    copy_scripts(scripts, "all_stop.bash", "process_identity.sh")
    write_executable(
        scripts / "delayed_native.bash",
        """#!/usr/bin/env bash
set -euo pipefail
ps -p "$$" | awk 'NR == 2 {print $4}' > "$INITIAL_WINPID_FILE"
sleep 3
exec "$NATIVE_PYTHON" -c 'import os, time; from pathlib import Path; Path(os.environ["FINAL_WINPID_FILE"]).write_text(str(os.getpid()), encoding="utf-8"); time.sleep(60)'
""",
    )
    pid_file = surf / "run.pids"
    initial_winpid_file = surf / "initial-winpid.txt"
    final_winpid_file = surf / "final-winpid.txt"
    env = {
        "NATIVE_PYTHON": Path(os.sys.executable).as_posix(),
        "INITIAL_WINPID_FILE": initial_winpid_file.as_posix(),
        "FINAL_WINPID_FILE": final_winpid_file.as_posix(),
        "SURFGYM_STOP_GRACE_SECONDS": "1",
    }

    launched = run_bash(
        surf,
        """source scripts/process_identity.sh
nohup bash scripts/delayed_native.bash >/dev/null 2>&1 &
pid=$!
identity=$(capture_process_identity_after_exec "$pid")
printf 'gateway %s %s ignored.log\n' "$pid" "$identity" > run.pids
""",
        env=env,
    )

    assert launched.returncode == 0, launched.stderr
    wait_for_file(final_winpid_file)
    initial_winpid = initial_winpid_file.read_text(encoding="utf-8").strip()
    final_winpid = final_winpid_file.read_text(encoding="utf-8").strip()
    record = pid_file.read_text(encoding="utf-8").split()
    assert initial_winpid != final_winpid
    matched = run_bash(
        surf,
        f'source scripts/process_identity.sh; process_identity_matches "{record[1]}" "{record[2]}"',
        env=env,
    )
    assert matched.returncode == 0, matched.stderr

    stopped = run_bash(surf, "bash scripts/all_stop.bash run.pids", env=env)
    assert stopped.returncode == 0, stopped.stderr
    assert not pid_file.exists()


def test_all_stop_refuses_live_pid_with_wrong_identity(tmp_path: Path) -> None:
    surf = tmp_path / "surf"
    scripts = surf / "scripts"
    copy_scripts(scripts, "all_stop.bash", "process_identity.sh")
    child_record = surf / "child.pid"
    owner = subprocess.Popen(
        [
            bash_executable(),
            "-lc",
            f"sleep 60 & child=$!; printf '%s' \"$child\" > '{child_record.as_posix()}'; wait \"$child\"",
        ],
        cwd=surf,
    )
    try:
        wait_for_file(child_record)
        child_pid = child_record.read_text(encoding="utf-8")
        pid_file = surf / "stale.pids"
        pid_file.write_text(f"gateway {child_pid} wrong-token ignored.log\n", encoding="utf-8")

        stopped = run_bash(
            surf,
            "bash scripts/all_stop.bash stale.pids",
            env={"SURFGYM_STOP_GRACE_SECONDS": "1"},
        )
        assert stopped.returncode != 0
        assert "identity does not match" in stopped.stderr
        assert pid_file.exists()
        assert run_bash(surf, f"kill -0 {child_pid}").returncode == 0
    finally:
        if child_record.exists():
            child_pid = child_record.read_text(encoding="utf-8")
            run_bash(surf, f"kill -TERM {child_pid} 2>/dev/null || true")
        owner.wait(timeout=5)


def make_local_dev_sandbox(
    tmp_path: Path, *, fail_gateway: bool = False, fail_surf_readiness: bool = False
) -> tuple[Path, Path, dict[str, str]]:
    surf = tmp_path / "surf"
    docker = tmp_path / "docker"
    scripts = surf / "scripts"
    copy_scripts(scripts, "local_dev.bash", "all_stop.bash", "process_identity.sh")
    (surf / "config").mkdir(parents=True)
    (surf / "config" / "runtime.toml").write_text("# test operator config\n", encoding="utf-8")
    (docker / "scripts").mkdir(parents=True)
    (docker / "config.json").write_text('{"apps": []}', encoding="utf-8")

    write_executable(
        docker / "scripts" / "01_render_compose_up.sh",
        """#!/usr/bin/env bash
cd "$(dirname "$0")/.."
printf 'compose=%s\n' "$CONFIG_PATH" >> "$STUB_PROPAGATION"
printf 'compose_python=%s\n' "$PYTHON_BIN" >> "$STUB_PROPAGATION"
mkdir -p src/runtime
printf 'services: {}\n' > src/runtime/docker-compose.yml
""",
    )
    write_executable(
        docker / "scripts" / "02_launch_docker_control.sh",
        """#!/usr/bin/env bash
set -euo pipefail
printf 'controls=%s\n' "$CONFIG_PATH" >> "$STUB_PROPAGATION"
printf 'controls_python=%s\n' "$PYTHON_BIN" >> "$STUB_PROPAGATION"
printf 'controls_timeout=%s\n' "$STACK_READY_TIMEOUT_SECONDS" >> "$STUB_PROPAGATION"
if [[ -n "${STUB_INITIAL_WINPID_FILE:-}" ]]; then
  ps -p "$$" | awk 'NR == 2 {print $4}' > "$STUB_INITIAL_WINPID_FILE"
fi
sleep "${STUB_CONTROLS_EXEC_DELAY:-0}"
exec "$STUB_NATIVE_PYTHON" -u -c 'import os, time; from pathlib import Path; path = os.environ.get("STUB_FINAL_WINPID_FILE"); path and Path(path).write_text(str(os.getpid()), encoding="utf-8"); print("docker_control supervisor is running.", flush=True); time.sleep(60)'
""",
    )
    gateway_body = (
        """exec "$STUB_NATIVE_PYTHON" -c 'import time; time.sleep(1.5); raise SystemExit(9)'"""
        if fail_gateway
        else """exec "$STUB_NATIVE_PYTHON" -u -c 'import time; print("gateway supervisor is running.", flush=True); time.sleep(60)'"""
    )
    write_executable(
        docker / "scripts" / "03_launch_gateway.sh",
        f"""#!/usr/bin/env bash
set -euo pipefail
printf 'gateway=%s\n' "$CONFIG_PATH" >> "$STUB_PROPAGATION"
printf 'gateway_python=%s\n' "$PYTHON_BIN" >> "$STUB_PROPAGATION"
printf 'gateway_timeout=%s\n' "$STACK_READY_TIMEOUT_SECONDS" >> "$STUB_PROPAGATION"
{gateway_body}
""",
    )
    write_executable(
        docker / "scripts" / "05_reconcile_runtime_pids.sh",
        """#!/usr/bin/env bash
set -euo pipefail
printf 'config=%s\nruntime=%s\npid_dir=%s\npython=%s\n' \
  "$CONFIG_PATH" "$SURFGYM_RUNTIME_DIR" "$STACK_PID_DIR" "$PYTHON_BIN" \
  >> "$STUB_RECONCILE_ARGS"
if [[ "${STUB_RECONCILE_FAIL:-0}" == "1" ]]; then
  echo 'runtime PID identity mismatch' >&2
  exit 9
fi
rm -f -- "$STACK_PID_DIR/gateway.pid" "$STACK_PID_DIR"/docker-control-*.pid
""",
    )

    write_executable(
        scripts / "all_launch.bash",
        """#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/process_identity.sh"
mkdir -p "$(dirname "$SURFGYM_PID_FILE")"
: > "$SURFGYM_PID_FILE"
printf 'surf=%s\n' "$SURFGYM_CONFIG" >> "$STUB_PROPAGATION"
for name in gateway wavepool fixture; do
  sleep 60 >/dev/null 2>&1 &
  pid=$!
  token=$(process_identity_token "$pid")
  printf '%s %s %s %s.log\n' "$name" "$pid" "$token" "$name" >> "$SURFGYM_PID_FILE"
done
""",
    )
    write_executable(scripts / "health_check.bash", "#!/usr/bin/env bash\nexit 0\n")

    bin_dir = surf / "bin"
    bin_dir.mkdir()
    write_executable(
        bin_dir / "python-stub",
        """#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" == "-" ]]; then
  config_path="$2"
  grep -q '"compose_project": "test-stack"' "$config_path"
  echo test-stack
  exit 0
fi
printf '%s\n' "$*" >> "$STUB_COMPILER_ARGS"
if [[ "${STUB_COMPILER_FAIL:-0}" == "1" ]]; then
  exit 7
fi
surf_output=""
docker_output=""
check_only=0
while (($#)); do
  case "$1" in
    --surf-output) surf_output="$2"; shift 2 ;;
    --docker-output) docker_output="$2"; shift 2 ;;
    --check) check_only=1; shift ;;
    *) shift ;;
  esac
done
if ((check_only == 0)); then
  mkdir -p "$(dirname "$surf_output")" "$(dirname "$docker_output")"
  printf '{}\n' > "$surf_output"
  printf '{"runtime": {"compose_project": "test-stack", "container_prefix": "test-stack"}}\n' > "$docker_output"
fi
""",
    )
    curl_status = 1 if fail_surf_readiness else 0
    write_executable(bin_dir / "curl", f"#!/usr/bin/env bash\nexit {curl_status}\n")
    write_executable(
        bin_dir / "docker",
        '#!/usr/bin/env bash\nprintf \'%s\n\' "$*" >> "$STUB_DOCKER_ARGS"\n',
    )
    # These sandbox tests exercise orchestration. Keep PowerShell process-start
    # latency out of their deadline; dedicated Windows tests above use the real
    # executable to cover MSYS-to-native PID transitions and identity matching.
    write_executable(
        bin_dir / "powershell.exe",
        """#!/usr/bin/env bash
set -euo pipefail
command_text="${*: -1}"
if [[ "$command_text" =~ Get-Process[[:space:]]-Id[[:space:]]([0-9]+) ]]; then
  printf '%s0000000\n' "${BASH_REMATCH[1]}"
  exit 0
fi
exit 2
""",
    )
    env = {
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "PYTHON_BIN": "python-stub",
        "DOCKER_PYTHON_BIN": "docker-python-stub",
        "STUB_NATIVE_PYTHON": Path(os.sys.executable).as_posix(),
        "STUB_COMPILER_ARGS": str(surf / "compiler.args"),
        "STUB_DOCKER_ARGS": str(surf / "docker.args"),
        "STUB_PROPAGATION": str(surf / "propagation.log"),
        "STUB_RECONCILE_ARGS": str(surf / "reconcile.args"),
        "SURFGYM_LOCAL_READY_TIMEOUT_SECONDS": "5",
        "SURFGYM_LOCAL_READY_POLL_SECONDS": "0.05",
        "SURFGYM_STOP_GRACE_SECONDS": "1",
    }
    return surf, docker, env


def test_local_dev_up_waits_for_readiness_and_down_stops_recorded_processes(tmp_path: Path) -> None:
    surf, docker, env = make_local_dev_sandbox(tmp_path)
    alternate_config = surf / "config" / "alternate.toml"
    alternate_config.write_text("# alternate operator config\n", encoding="utf-8")

    started = run_bash(
        surf,
        'export PATH="$PWD/bin:$PATH"; bash scripts/local_dev.bash up '
        "--config config/alternate.toml --docker-repo ../docker",
        env=env,
    )
    assert started.returncode == 0, started.stderr
    assert "Local stack is ready for local requests." in started.stdout
    compiler_args = (surf / "compiler.args").read_text(encoding="utf-8")
    assert "--surf-repo" in compiler_args
    assert "--check-prerequisites" in compiler_args
    assert "--check-host-ports" in compiler_args
    assert "--check" not in compiler_args.split()
    assert "--config config/alternate.toml" in compiler_args
    propagation = (surf / "propagation.log").read_text(encoding="utf-8").splitlines()
    values = dict(line.split("=", 1) for line in propagation)
    assert values["compose"] == values["controls"] == values["gateway"]
    assert (
        values["compose_python"]
        == values["controls_python"]
        == values["gateway_python"]
        == "docker-python-stub"
    )
    assert values["compose"].endswith("/.runtime/config/docker.json")
    assert values["surf"].endswith("/.runtime/config/surfgym.json")
    assert values["controls_timeout"] == values["gateway_timeout"] == "5"

    stopped = run_bash(
        surf,
        'export PATH="$PWD/bin:$PATH"; bash scripts/local_dev.bash down --docker-repo ../docker',
        env=env,
    )
    assert stopped.returncode == 0, stopped.stderr
    docker_args = (surf / "docker.args").read_text(encoding="utf-8")
    assert "compose --project-name test-stack" in docker_args
    assert "down --remove-orphans" in docker_args
    assert not (surf / "logs" / "nohup" / "all_launch_local_dev.pids").exists()
    assert not (docker / "src" / "runtime" / "pids" / "integrated_controls.pid").exists()
    assert not (docker / "src" / "runtime" / "pids" / "integrated_gateway.pid").exists()


@pytest.mark.skipif(os.name != "nt", reason="MSYS native PID transitions are Windows-specific")
def test_local_dev_down_stops_delayed_native_docker_supervisor(tmp_path: Path) -> None:
    surf, docker, env = make_local_dev_sandbox(tmp_path)
    initial_winpid_file = surf / "docker-initial-winpid.txt"
    final_winpid_file = surf / "docker-final-winpid.txt"
    env.update(
        {
            "STUB_CONTROLS_EXEC_DELAY": "3",
            "STUB_INITIAL_WINPID_FILE": initial_winpid_file.as_posix(),
            "STUB_FINAL_WINPID_FILE": final_winpid_file.as_posix(),
        }
    )

    started = run_bash(
        surf,
        'export PATH="$PWD/bin:$PATH"; bash scripts/local_dev.bash up --docker-repo ../docker',
        env=env,
    )

    assert started.returncode == 0, started.stderr
    controls_pid_file = docker / "src" / "runtime" / "pids" / "integrated_controls.pid"
    controls_pid, controls_identity = controls_pid_file.read_text(encoding="utf-8").split()
    initial_winpid = initial_winpid_file.read_text(encoding="utf-8").strip()
    final_winpid = final_winpid_file.read_text(encoding="utf-8").strip()
    assert initial_winpid != final_winpid
    matched = run_bash(
        surf,
        f'source scripts/process_identity.sh; process_identity_matches "{controls_pid}" "{controls_identity}"',
        env=env,
    )
    assert matched.returncode == 0, matched.stderr

    stopped = run_bash(
        surf,
        'export PATH="$PWD/bin:$PATH"; bash scripts/local_dev.bash down --docker-repo ../docker',
        env=env,
    )

    assert stopped.returncode == 0, stopped.stderr
    assert not controls_pid_file.exists()
    assert run_bash(surf, f"kill -0 {controls_pid} 2>/dev/null").returncode != 0


def test_local_dev_rolls_back_when_supervisor_exits_before_readiness(tmp_path: Path) -> None:
    surf, docker, env = make_local_dev_sandbox(tmp_path, fail_gateway=True)

    started = run_bash(
        surf,
        'export PATH="$PWD/bin:$PATH"; bash scripts/local_dev.bash up --docker-repo ../docker',
        env=env,
    )
    assert started.returncode != 0
    assert (
        "exited before readiness" in started.stderr
        or "could not capture identity" in started.stderr
    )
    assert "rolling back recorded resources" in started.stderr
    assert not (docker / "src" / "runtime" / "pids" / "integrated_controls.pid").exists()
    assert not (docker / "src" / "runtime" / "pids" / "integrated_gateway.pid").exists()
    assert "down --remove-orphans" in (surf / "docker.args").read_text(encoding="utf-8")


@pytest.mark.skipif(os.name != "nt", reason="WinError 193 is Windows-specific")
def test_local_dev_surfaces_git_bash_wrapper_exec_failure(tmp_path: Path) -> None:
    surf, docker, env = make_local_dev_sandbox(tmp_path)
    write_executable(
        docker / "scripts" / "02_launch_docker_control.sh",
        """#!/usr/bin/env bash
set -euo pipefail
docker_bin="$(command -v docker)"
echo 'attempting Python execution of the Git Bash docker wrapper'
"$PYTHON_BIN" - "$docker_bin" <<'PY'
import subprocess
import sys

subprocess.run([sys.argv[1]], check=True)
PY
""",
    )
    env["DOCKER_PYTHON_BIN"] = Path(os.sys.executable).as_posix()

    started = run_bash(
        surf,
        'export PATH="$PWD/bin:$PATH"; bash scripts/local_dev.bash up --docker-repo ../docker',
        env=env,
    )

    assert started.returncode != 0
    assert "could not capture identity" in started.stderr
    assert "attempting Python execution of the Git Bash docker wrapper" in started.stderr
    assert "WinError 193" in (
        docker / "src" / "runtime" / "logs" / "integrated_controls.log"
    ).read_text(encoding="utf-8", errors="replace")
    assert "rolling back recorded resources" in started.stderr
    assert not (docker / "src" / "runtime" / "pids" / "integrated_controls.pid").exists()
    assert "down --remove-orphans" in (surf / "docker.args").read_text(encoding="utf-8")


def test_local_dev_rolls_back_when_http_readiness_never_succeeds(tmp_path: Path) -> None:
    surf, docker, env = make_local_dev_sandbox(tmp_path, fail_surf_readiness=True)
    env["SURFGYM_LOCAL_READY_TIMEOUT_SECONDS"] = "5"

    started = run_bash(
        surf,
        'export PATH="$PWD/bin:$PATH"; bash scripts/local_dev.bash up --docker-repo ../docker',
        env=env,
    )

    assert started.returncode != 0
    assert (
        "Timed out waiting for SurfGym gateway, WavePool, and fixture endpoints" in started.stderr
    )
    assert "rolling back recorded resources" in started.stderr
    assert not (surf / "logs" / "nohup" / "all_launch_local_dev.pids").exists()
    assert not (docker / "src" / "runtime" / "pids" / "integrated_controls.pid").exists()
    assert not (docker / "src" / "runtime" / "pids" / "integrated_gateway.pid").exists()
    assert "down --remove-orphans" in (surf / "docker.args").read_text(encoding="utf-8")


def test_local_dev_does_not_launch_from_stale_outputs_after_compiler_failure(
    tmp_path: Path,
) -> None:
    surf, docker, env = make_local_dev_sandbox(tmp_path)
    generated = surf / ".runtime" / "config"
    generated.mkdir(parents=True)
    (generated / "surfgym.json").write_text("stale", encoding="utf-8")
    (generated / "docker.json").write_text("stale", encoding="utf-8")
    env["STUB_COMPILER_FAIL"] = "1"

    started = run_bash(
        surf,
        'export PATH="$PWD/bin:$PATH"; bash scripts/local_dev.bash up --docker-repo ../docker',
        env=env,
    )

    assert started.returncode == 7
    assert not (docker / "src" / "runtime" / "docker-compose.yml").exists()
    assert not (surf / "docker.args").exists()
    assert not (surf / "logs" / "nohup" / "all_launch_local_dev.pids").exists()


def test_local_dev_down_attempts_every_owned_cleanup_after_errors(tmp_path: Path) -> None:
    surf, docker, env = make_local_dev_sandbox(tmp_path)
    actions = surf / "actions.log"
    write_executable(
        surf / "scripts" / "all_stop.bash",
        "#!/usr/bin/env bash\nprintf 'surf\\n' >> \"$STUB_ACTIONS\"\nexit 3\n",
    )
    runtime = docker / "src" / "runtime"
    (runtime / "pids").mkdir(parents=True)
    (runtime / "pids" / "integrated_gateway.pid").write_text("invalid\n", encoding="utf-8")
    (runtime / "pids" / "integrated_controls.pid").write_text("invalid\n", encoding="utf-8")
    (runtime / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")
    generated = surf / ".runtime" / "config"
    generated.mkdir(parents=True)
    (generated / "docker.json").write_text(
        '{"runtime": {"compose_project": "test-stack", "container_prefix": "test-stack"}}\n',
        encoding="utf-8",
    )
    env["STUB_ACTIONS"] = str(actions)

    stopped = run_bash(
        surf,
        'export PATH="$PWD/bin:$PATH"; bash scripts/local_dev.bash down --docker-repo ../docker',
        env=env,
    )

    assert stopped.returncode == 1
    assert actions.read_text(encoding="utf-8") == "surf\n"
    assert "gateway supervisor PID record" in stopped.stderr
    assert "controls supervisor PID record" in stopped.stderr
    assert "down --remove-orphans" in (surf / "docker.args").read_text(encoding="utf-8")
    assert "shutdown completed with errors" in stopped.stderr


def prepare_stale_docker_child_records(surf: Path, docker: Path) -> tuple[Path, Path]:
    runtime = docker / "src" / "runtime"
    pid_dir = runtime / "pids"
    pid_dir.mkdir(parents=True)
    (runtime / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")
    gateway_pid = pid_dir / "gateway.pid"
    control_pid = pid_dir / "docker-control-impress-0.pid"
    gateway_pid.write_text("dead-record\n", encoding="utf-8")
    control_pid.write_text("dead-record\n", encoding="utf-8")
    generated = surf / ".runtime" / "config"
    generated.mkdir(parents=True)
    (generated / "docker.json").write_text(
        '{"runtime": {"compose_project": "test-stack", "container_prefix": "test-stack"}}\n',
        encoding="utf-8",
    )
    return gateway_pid, control_pid


def test_local_dev_down_reconciles_stale_docker_child_records(tmp_path: Path) -> None:
    surf, docker, env = make_local_dev_sandbox(tmp_path)
    gateway_pid, control_pid = prepare_stale_docker_child_records(surf, docker)

    stopped = run_bash(
        surf,
        'export PATH="$PWD/bin:$PATH"; bash scripts/local_dev.bash down --docker-repo ../docker',
        env=env,
    )

    assert stopped.returncode == 0, stopped.stderr
    assert not gateway_pid.exists()
    assert not control_pid.exists()
    reconcile_values = dict(
        line.split("=", 1)
        for line in (surf / "reconcile.args").read_text(encoding="utf-8").splitlines()
    )
    assert reconcile_values["config"].endswith("/surf/.runtime/config/docker.json")
    assert reconcile_values["runtime"].endswith("/docker/src/runtime")
    assert reconcile_values["pid_dir"].endswith("/docker/src/runtime/pids")
    assert reconcile_values["python"] == "docker-python-stub"


def test_local_dev_down_fails_closed_when_child_pid_reconcile_fails(tmp_path: Path) -> None:
    surf, docker, env = make_local_dev_sandbox(tmp_path)
    gateway_pid, control_pid = prepare_stale_docker_child_records(surf, docker)
    env["STUB_RECONCILE_FAIL"] = "1"

    stopped = run_bash(
        surf,
        'export PATH="$PWD/bin:$PATH"; bash scripts/local_dev.bash down --docker-repo ../docker',
        env=env,
    )

    assert stopped.returncode == 1
    assert "runtime PID identity mismatch" in stopped.stderr
    assert gateway_pid.exists()
    assert control_pid.exists()
    assert "down --remove-orphans" in (surf / "docker.args").read_text(encoding="utf-8")
    assert "shutdown completed with errors" in stopped.stderr


def test_local_dev_down_refuses_compose_without_generated_project_identity(tmp_path: Path) -> None:
    surf, docker, env = make_local_dev_sandbox(tmp_path)
    runtime = docker / "src" / "runtime"
    runtime.mkdir(parents=True)
    (runtime / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")

    stopped = run_bash(
        surf,
        'export PATH="$PWD/bin:$PATH"; bash scripts/local_dev.bash down --docker-repo ../docker',
        env=env,
    )

    assert stopped.returncode == 1
    assert "cannot prove the Compose project from generated config" in stopped.stderr
    assert not (surf / "docker.args").exists()
