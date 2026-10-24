from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from types import FrameType

import httpx

from surfgym_runtime.support import (
    WavepoolConfig,
    deploy_logger,
    load_config,
    setup_logging,
)

STARTUP_TIMEOUT_SECONDS = 30.0
HEALTH_CHECK_INTERVAL_SECONDS = 1.0
SHUTDOWN_TIMEOUT_SECONDS = 3.0


def _is_windows() -> bool:
    return os.name == "nt"


@dataclass(frozen=True)
class ManagedProcess:
    name: str
    process: subprocess.Popen[str]


class WavepoolSupervisor:
    def __init__(self, *, config: WavepoolConfig, config_path: Path, log_path: Path) -> None:
        self.config = config
        self.config_path = config_path.resolve()
        self.log_path = log_path.resolve()

        self.processes: list[ManagedProcess] = []
        self._stream_threads: list[threading.Thread] = []
        self._shutdown = threading.Event()
        self._cleaned = False
        self._reported_exited_processes: set[int] = set()
        # Draining a POSIX numeric process group is a one-shot ownership proof.
        # Once it is gone, a later PID/PGID reuse must never receive another
        # signal merely because Master has not acknowledged the notification.
        self._drained_exited_processes: set[int] = set()
        self._quiescent_exited_processes: set[int] = set()
        self._cleanup_drained_groups: set[int] = set()

        self.master_port = config.master_port
        self.instance_ports: list[int] = [
            *(config.instance_start_port + i for i in range(config.instances)),
        ]

    def run(self) -> None:
        self._setup()

        try:
            self._start_servers()
            self._wait_until_ready()
            self._watch_children()
        finally:
            self.cleanup()

    def _setup(self) -> None:
        # register signal handler
        def _handle_signal(signum: int, _frame: FrameType | None) -> None:
            deploy_logger.info("Received signal %s; shutting down WavePool", signum)
            self._shutdown.set()

        signal.signal(signal.SIGINT, _handle_signal)
        signal.signal(signal.SIGTERM, _handle_signal)

        # Refuse to adopt or terminate processes that this supervisor does not own.
        required_ports: list[int] = self.instance_ports[:]
        required_ports.append(self.master_port)
        for port in required_ports:
            try:
                result = subprocess.run(
                    ["lsof", "-ti", f"tcp:{port}"],
                    capture_output=True,
                    text=True,
                    timeout=1.0,
                )
            except Exception:
                deploy_logger.warning("Failed to inspect port: %s", port)
                continue

            if result.returncode != 0 or not result.stdout.strip():
                continue

            pids = [raw_pid.strip() for raw_pid in result.stdout.splitlines() if raw_pid.strip()]
            raise RuntimeError(
                "Required WavePool port "
                f"{port} is already in use by PID(s): {', '.join(pids)}. "
                "Stop the owning process or choose a different port in config/runtime.toml."
            )

    def cleanup(self) -> None:
        deploy_logger.info("Clean Up")
        if self._cleaned:
            return
        managed = list(
            reversed(
                [
                    item
                    for item in self.processes
                    if _is_windows()
                    or item.process.pid
                    not in (self._cleanup_drained_groups | self._drained_exited_processes)
                ]
            )
        )
        windows_owned: list[ManagedProcess] = []
        cleanup_errors: list[BaseException] = []
        windows_remaining: list[ManagedProcess] = []
        owned_groups: set[int] = set()

        for item in managed:
            process = item.process
            if _is_windows():
                try:
                    if not process.terminate_and_check_quiescent(timeout=SHUTDOWN_TIMEOUT_SECONDS):
                        cleanup_errors.append(RuntimeError(f"owned process tree is not quiescent: {item.name}"))
                        windows_remaining.append(item)
                except BaseException as exc:
                    cleanup_errors.append(exc)
                    windows_remaining.append(item)
                finally:
                    if item not in windows_remaining:
                        windows_owned.append(item)
                continue
            owned_groups.add(process.pid)
            if process.poll() is not None:
                self._terminate_owned_process_group(process.pid)
                continue
            deploy_logger.info("Terminating process: %s", item.name)
            self._signal_group(process, signal.SIGTERM)

        if _is_windows():
            for item in windows_owned:
                try:
                    item.process.close()
                except BaseException as exc:
                    cleanup_errors.append(exc)
                    windows_remaining.append(item)
            self.processes = windows_remaining
            if cleanup_errors:
                raise RuntimeError("WavePool owned cleanup is UNKNOWN") from cleanup_errors[0]
            self._cleaned = True
            return

        deadline = time.monotonic() + SHUTDOWN_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            if all(item.process.poll() is not None for item in managed):
                break
            time.sleep(SHUTDOWN_TIMEOUT_SECONDS / 10)

        for item in managed:
            process = item.process
            if process.poll() is None:
                deploy_logger.warning("Killing unresponsive process: %s", item.name)
                self._signal_group(process, getattr(signal, "SIGKILL", signal.SIGTERM))

        # A dead leader is not proof that its owned session is gone.  Give the
        # TERM sent above a bounded chance to drain, then escalate only that
        # recorded process group.  We retain an UNKNOWN result instead of
        # treating a parent poll as descendant cleanup.
        pending_groups = {
            pgid
            for pgid in owned_groups - self._cleanup_drained_groups
            if not self._owned_process_group_drained(pgid)
        }
        group_deadline = time.monotonic() + SHUTDOWN_TIMEOUT_SECONDS
        while pending_groups and time.monotonic() < group_deadline:
            pending_groups = {
                pgid for pgid in pending_groups if not self._owned_process_group_drained(pgid)
            }
            if pending_groups:
                time.sleep(min(0.05, SHUTDOWN_TIMEOUT_SECONDS))

        self._cleanup_drained_groups.update(owned_groups - pending_groups)

        for pgid in pending_groups:
            try:
                os.killpg(pgid, getattr(signal, "SIGKILL", signal.SIGTERM))
            except ProcessLookupError:
                self._cleanup_drained_groups.add(pgid)
                continue
            except (PermissionError, OSError) as exc:
                cleanup_errors.append(exc)
                continue
            kill_deadline = time.monotonic() + SHUTDOWN_TIMEOUT_SECONDS
            while not self._owned_process_group_drained(pgid) and time.monotonic() < kill_deadline:
                time.sleep(min(0.05, SHUTDOWN_TIMEOUT_SECONDS))
            if not self._owned_process_group_drained(pgid):
                cleanup_errors.append(RuntimeError(f"owned process group remains live: {pgid}"))
            else:
                self._cleanup_drained_groups.add(pgid)

        for item in managed:
            try:
                item.process.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                deploy_logger.warning("Timed out waiting for process: %s", item.name)

        for thread in self._stream_threads:
            thread.join(timeout=1.0)
        for item in windows_owned:
            try:
                item.process.close()
            except BaseException as exc:
                cleanup_errors.append(exc)
        if cleanup_errors:
            # Keep only unknown trees for a later bounded retry.  A proven
            # drained numeric PGID is never touched again, avoiding PID reuse.
            self.processes = [
                item
                for item in self.processes
                if item.process.pid not in self._cleanup_drained_groups
            ]
            raise RuntimeError("WavePool owned cleanup is UNKNOWN") from cleanup_errors[0]
        self._cleaned = True

    def _start_servers(self) -> None:
        self._spawn(
            name=f"master:{self.master_port}",
            cmd=[
                sys.executable,
                "-m",
                "surfgym_runtime.wavepool.master.server",
                str(self.config_path),
            ],
        )

        for port in self.instance_ports:
            self._spawn(
                name=f"instance:{port}",
                cmd=[
                    sys.executable,
                    "-m",
                    "surfgym_runtime.wavepool.instance.server",
                    "--host",
                    str(self.config.host),
                    "--port",
                    str(port),
                    "--log-path",
                    str(self.log_path),
                    "--contexts-per-instance",
                    str(self.config.contexts_per_instance),
                    "--binding-cleanup-horizon-seconds",
                    str(self.config.process_timeout.binding_cleanup_horizon),
                    "--binding-cleanup-request-timeout-seconds",
                    str(self.config.process_timeout.binding_cleanup_request_timeout),
                    "--binding-cleanup-retry-interval-seconds",
                    str(self.config.process_timeout.binding_cleanup_retry_interval),
                ],
            )

    def _spawn(self, *, name: str, cmd: list[str]) -> None:
        deploy_logger.info("Starting %s: %s", name, " ".join(cmd))

        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"

        if _is_windows():
            from surfgym_runtime.wavepool.owned_process_windows import OwnedProcessWindows

            process = OwnedProcessWindows.spawn(cmd, env=env)
        else:
            process = subprocess.Popen(
                cmd,
            # stdout=subprocess.PIPE,
            # stderr=subprocess.STDOUT,
            text=True,
            # bufsize=1,
            start_new_session=True,
                env=env,
            )

        self.processes.append(ManagedProcess(name=name, process=process))

        thread = threading.Thread(
            # target=self._stream_output,
            args=(name, process),
            daemon=False,
        )
        self._stream_threads.append(thread)
        thread.start()

    # def _stream_output(self, name: str, process: subprocess.Popen[str]) -> None:
    #     stdout = process.stdout
    #     if stdout is None:
    #         return

    #     try:
    #         for line in stdout:
    #             line = line.rstrip()
    #             if line:
    #                 deploy_logger.info("[%s] %s", name, line)
    #     finally:
    #         stdout.close()

    def _wait_until_ready(self) -> None:
        health_check_urls: list[str] = [
            f"http://{self.config.host}:{port}/health" for port in self.instance_ports
        ]
        health_check_urls.append(f"http://{self.config.host}:{self.master_port}/health")

        with httpx.Client(timeout=1.0) as client:
            deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS

            while time.monotonic() < deadline:
                self._check_all_child()

                ready = True
                for url in health_check_urls:
                    try:
                        response = client.get(url)
                    except httpx.HTTPError as exc:
                        deploy_logger.warning("%s: %s: %s", url, type(exc).__name__, exc)
                        ready = False
                        continue

                    if response.status_code != 200:
                        deploy_logger.warning("%s: status=%s", url, response.status_code)
                        ready = False

                if ready:
                    deploy_logger.info("WavePool is ready")
                    return

                time.sleep(HEALTH_CHECK_INTERVAL_SECONDS)

        raise TimeoutError("timed out waiting for WavePool processes to become ready")

    def _watch_children(self) -> None:
        while not self._shutdown.is_set():
            self._check_all_child()
            time.sleep(HEALTH_CHECK_INTERVAL_SECONDS)

    def _check_all_child(self) -> None:
        for item in self.processes:
            code = item.process.poll()
            if code is None:
                continue
            if item.name.startswith("instance:"):
                self._notify_instance_exit(item, code)
                continue
            raise RuntimeError(f"{item.name} exited unexpectedly with code {code}")

    def _notify_instance_exit(self, item: ManagedProcess, code: int) -> None:
        """Tell Master about a confirmed owned Instance exit without touching siblings."""
        port = int(item.name.removeprefix("instance:"))
        if item.process.pid not in self._reported_exited_processes:
            try:
                response = httpx.post(
                    f"http://{self.config.host}:{self.master_port}/internal/instances/{port}/exited",
                    params={"quiescent": "false"},
                    timeout=self.config.process_timeout.release - self.config.process_timeout.layer_gap,
                )
                response.raise_for_status()
            except httpx.HTTPError:
                deploy_logger.exception("Failed to retire exited Instance: port=%s code=%s", port, code)
                return
            self._reported_exited_processes.add(item.process.pid)
        process_id = item.process.pid
        if process_id not in self._drained_exited_processes:
            try:
                if _is_windows():
                    quiescent = item.process.terminate_and_check_quiescent(
                        timeout=SHUTDOWN_TIMEOUT_SECONDS
                    )
                else:
                    self._terminate_owned_process_group(process_id)
                    quiescent = self._owned_process_group_drained(process_id)
            except BaseException:
                deploy_logger.exception("Could not prove exited Instance quiescent: port=%s", port)
                return
            if not quiescent:
                return
            self._drained_exited_processes.add(process_id)
        if process_id not in self._quiescent_exited_processes:
            try:
                self._notify_quiescent_instance_exit(port)
            except httpx.HTTPError:
                deploy_logger.exception("Failed to acknowledge quiescent Instance: port=%s", port)
            else:
                self._quiescent_exited_processes.add(process_id)

    def _terminate_owned_process_group(self, pgid: int) -> None:
        if _is_windows():
            return
        try:
            os.killpg(pgid, signal.SIGTERM)
        except ProcessLookupError:
            return
        except (AttributeError, PermissionError, OSError):
            return
        deadline = time.monotonic() + SHUTDOWN_TIMEOUT_SECONDS
        while not self._owned_process_group_drained(pgid) and time.monotonic() < deadline:
            time.sleep(min(0.05, SHUTDOWN_TIMEOUT_SECONDS))
        if self._owned_process_group_drained(pgid):
            return
        try:
            os.killpg(pgid, getattr(signal, "SIGKILL", signal.SIGTERM))
        except (AttributeError, ProcessLookupError, PermissionError, OSError):
            return

    def _owned_process_group_drained(self, pgid: int) -> bool:
        """POSIX can prove the owned session is gone; Windows fails closed pending a Job handle."""
        if _is_windows():
            return False
        try:
            os.killpg(pgid, 0)
        except ProcessLookupError:
            return True
        except OSError:
            return False
        return False

    def _notify_quiescent_instance_exit(self, port: int) -> None:
        response = httpx.post(
            f"http://{self.config.host}:{self.master_port}/internal/instances/{port}/exited",
            params={"quiescent": "true"},
            timeout=self.config.process_timeout.release - self.config.process_timeout.layer_gap,
        )
        response.raise_for_status()

    def _signal_group(self, process: subprocess.Popen[str], sig: int) -> None:
        if _is_windows():
            if sig == signal.SIGKILL:
                process.kill()
            else:
                process.terminate()
            return
        if process.poll() is not None:
            return

        try:
            os.killpg(process.pid, sig)
            return
        except (AttributeError, ProcessLookupError, PermissionError, OSError):
            pass

        try:
            process.send_signal(sig)
        except (ProcessLookupError, PermissionError, OSError):
            pass


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("config_path", type=Path)
    return parser.parse_args()


def launch() -> None:
    args = _parse_args()

    config = load_config(args.config_path)
    setup_logging(deploy_logger, config.log_path, component="deploy")

    supervisor = WavepoolSupervisor(
        config=config.wavepool_config,
        config_path=args.config_path,
        log_path=config.log_path,
    )

    try:
        supervisor.run()
    except Exception:
        deploy_logger.exception("Wavepool Supervisor crashed")
        raise


if __name__ == "__main__":
    launch()
