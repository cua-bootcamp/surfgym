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

    def _setup(self):
        # register signal handler
        def _handle_signal(signum: int, _frame: FrameType | None) -> None:
            deploy_logger.info("Received signal %s; shutting down WavePool", signum)
            self._shutdown.set()

        signal.signal(signal.SIGINT, _handle_signal)
        signal.signal(signal.SIGTERM, _handle_signal)

        # cleanup existing ports
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

            for raw_pid in result.stdout.splitlines():
                raw_pid = raw_pid.strip()
                if not raw_pid:
                    continue

                try:
                    pid = int(raw_pid)
                except ValueError:
                    continue

                try:
                    deploy_logger.warning("Killing process %s occupying port %s", pid, port)
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                except PermissionError:
                    deploy_logger.exception(
                        "No permission to kill process %s on port %s", pid, port
                    )

    def cleanup(self) -> None:
        deploy_logger.info("Clean Up")
        if self._cleaned:
            return
        self._cleaned = True

        managed = list(reversed(self.processes))

        for item in managed:
            process = item.process
            if process.poll() is not None:
                continue
            deploy_logger.info("Terminating process: %s", item.name)
            self._signal_group(process, signal.SIGTERM)

        deadline = time.monotonic() + SHUTDOWN_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            if all(item.process.poll() is not None for item in managed):
                break
            time.sleep(SHUTDOWN_TIMEOUT_SECONDS / 10)

        for item in managed:
            process = item.process
            if process.poll() is None:
                deploy_logger.warning("Killing unresponsive process: %s", item.name)
                self._signal_group(process, signal.SIGKILL)

        for item in managed:
            try:
                item.process.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                deploy_logger.warning("Timed out waiting for process: %s", item.name)

        for thread in self._stream_threads:
            thread.join(timeout=1.0)

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
                ],
            )

    def _spawn(self, *, name: str, cmd: list[str]) -> None:
        deploy_logger.info("Starting %s: %s", name, " ".join(cmd))

        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            start_new_session=True,
            env=env,
        )

        self.processes.append(ManagedProcess(name=name, process=process))

        thread = threading.Thread(
            target=self._stream_output,
            args=(name, process),
            daemon=False,
        )
        self._stream_threads.append(thread)
        thread.start()

    def _stream_output(self, name: str, process: subprocess.Popen[str]) -> None:
        stdout = process.stdout
        if stdout is None:
            return

        try:
            for line in stdout:
                line = line.rstrip()
                if line:
                    deploy_logger.info("[%s] %s", name, line)
        finally:
            stdout.close()

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
            if code is not None:
                raise RuntimeError(f"{item.name} exited unexpectedly with code {code}")

    def _signal_group(self, process: subprocess.Popen[str], sig: int) -> None:
        if process.poll() is not None:
            return

        try:
            os.killpg(process.pid, sig)
            return
        except (ProcessLookupError, PermissionError, OSError):
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
    setup_logging(deploy_logger, config.log_path)

    supervisor = WavepoolSupervisor(
        config=config.wavepool_config, config_path=args.config_path, log_path=config.log_path
    )

    try:
        supervisor.run()
    except Exception:
        deploy_logger.exception("Wavepool Supervisor crashed")
        raise


if __name__ == "__main__":
    launch()
