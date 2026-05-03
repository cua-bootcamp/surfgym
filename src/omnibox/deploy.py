import argparse
import os
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import httpx
from pydantic import ValidationError

from src.config import Config


@dataclass
class ManagedProcess:
    name: str
    process: subprocess.Popen[str]


class OmniboxSupervisor:
    def __init__(self, config: Config) -> None:
        self.instance_config = config.omnibox_config
        self.processes: list[ManagedProcess] = []
        self._shutdown = threading.Event()
        self._cleaned = False

    def run(self) -> None:
        self._install_signal_handlers()
        self._free_required_ports()

        try:
            self._start_instances()
            self._start_master()
            self._wait_until_ready()
            self._watch_children()
        finally:
            self.cleanup()

    def cleanup(self) -> None:
        if self._cleaned:
            return
        self._cleaned = True

        managed = list(reversed(self.processes))
        for item in managed:
            self._signal_group(item.process, signal.SIGTERM)

        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            alive = [item for item in managed if item.process.poll() is None]
            if not alive:
                break
            time.sleep(0.1)

        for item in managed:
            if item.process.poll() is None:
                self._signal_group(item.process, signal.SIGKILL)

        for item in managed:
            try:
                item.process.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                pass

    def _install_signal_handlers(self) -> None:
        def _handle_signal(signum, _frame) -> None:
            print(f"\n[omnibox-deploy] received signal {signum}, shutting down...", flush=True)
            self._shutdown.set()

        signal.signal(signal.SIGINT, _handle_signal)
        signal.signal(signal.SIGTERM, _handle_signal)

    def _required_ports(self) -> list[int]:
        cfg = self.instance_config
        ports = [cfg.master_port]
        ports.extend(cfg.instance_start_port + i for i in range(cfg.instances))
        return ports

    def _free_required_ports(self) -> None:
        for port in self._required_ports():
            try:
                result = subprocess.run(
                    ["lsof", "-ti", f"tcp:{port}"],
                    capture_output=True,
                    text=True,
                    timeout=1.0,
                )
            except Exception:
                continue

            if result.returncode != 0 or not result.stdout.strip():
                continue

            for raw_pid in result.stdout.splitlines():
                raw_pid = raw_pid.strip()
                if not raw_pid:
                    continue
                try:
                    os.kill(int(raw_pid), signal.SIGKILL)
                except (ProcessLookupError, ValueError):
                    pass

    def _start_instances(self) -> None:
        cfg = self.instance_config
        for i in range(cfg.instances):
            port = cfg.instance_start_port + i
            self._spawn(
                name=f"instance:{port}",
                cmd=[
                    sys.executable,
                    "-m",
                    "src.omnibox.instance_server",
                    "--port",
                    str(port),
                ],
            )

    def _start_master(self) -> None:
        cfg = self.instance_config
        self._spawn(
            name=f"master:{cfg.master_port}",
            cmd=[
                sys.executable,
                "-m",
                "src.omnibox.master_server",
                "--master_host",
                cfg.host,
                "--master_port",
                str(cfg.master_port),
                "--instance_host",
                cfg.host,
                "--instance_start_port",
                str(cfg.instance_start_port),
                "--instances",
                str(cfg.instances),
            ],
        )

    def _spawn(self, *, name: str, cmd: list[str]) -> None:
        print(f"[omnibox-deploy] starting {name}: {' '.join(cmd)}", flush=True)

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            start_new_session=True,
        )
        self.processes.append(ManagedProcess(name=name, process=process))

        thread = threading.Thread(
            target=self._stream_output,
            args=(name, process),
            daemon=True,
        )
        thread.start()

    def _stream_output(self, name: str, process: subprocess.Popen[str]) -> None:
        stdout = process.stdout
        if stdout is None:
            return

        try:
            for line in stdout:
                print(f"[{name}] {line.rstrip()}", flush=True)
        finally:
            stdout.close()

    def _wait_until_ready(self) -> None:
        cfg = self.instance_config
        instance_urls = [
            f"http://{cfg.host}:{cfg.instance_start_port + i}/idle" for i in range(cfg.instances)
        ]
        master_url = f"http://{cfg.host}:{cfg.master_port}/health"

        with httpx.Client(timeout=1.0) as client:
            deadline = time.monotonic() + 30.0
            while time.monotonic() < deadline:
                self._raise_if_child_died()

                try:
                    instances_ready = all(
                        client.get(url).status_code == 200 for url in instance_urls
                    )
                    master_ready = client.get(master_url).status_code == 200
                    if instances_ready and master_ready:
                        print("[omnibox-deploy] ready", flush=True)
                        return
                except httpx.HTTPError:
                    pass

                if self._shutdown.is_set():
                    raise RuntimeError("shutdown requested during startup")

                time.sleep(0.2)

        raise TimeoutError("timed out waiting for omnibox processes to become ready")

    def _watch_children(self) -> None:
        while not self._shutdown.is_set():
            self._raise_if_child_died()
            time.sleep(0.2)

    def _raise_if_child_died(self) -> None:
        for item in self.processes:
            code = item.process.poll()
            if code is not None:
                raise RuntimeError(f"{item.name} exited unexpectedly with code {code}")

    def _signal_group(self, process: subprocess.Popen[str], sig: int) -> None:
        if process.poll() is not None:
            return
        try:
            os.killpg(process.pid, sig)
        except ProcessLookupError:
            pass


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("config_path", type=Path)
    return parser.parse_args()


def _load_config(config_path: Path) -> Config:
    try:
        return Config.model_validate_json(config_path.read_text())
    except ValidationError as exc:
        raise SystemExit(f"invalid config: {config_path}\n{exc}") from exc


def main() -> None:
    args = _parse_args()
    config = _load_config(args.config_path)
    supervisor = OmniboxSupervisor(config)
    supervisor.run()


if __name__ == "__main__":
    main()
