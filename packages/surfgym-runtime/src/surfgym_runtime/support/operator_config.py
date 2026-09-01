from __future__ import annotations

import argparse
import copy
import json
import math
import os
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NoReturn, cast

from pydantic import ValidationError
from surfgym_contracts.local_static_sites import LOCAL_STATIC_SITES

from surfgym_runtime.support.config import Config as SurfConfig
from surfgym_runtime.support.task_store import TaskStore

DOCKER_GATEWAY_PORT = 53001
FIXTURE_CONTENT_PORT = 3000
FIXTURE_INDEX_PATH = Path("packages/surfgym-fixture/src/surfgym_fixture/dist/index.html")
MAX_COUNT = 10_000
MAX_TIMEOUT_SECONDS = 86_400.0
MAX_PORT = 65_535
SAFE_RUNTIME_NAME = re.compile(r"^[a-z0-9][a-z0-9_-]{0,62}$")


class OperatorConfigError(ValueError):
    """Raised when the operator config or Docker capability template is invalid."""


@dataclass(frozen=True)
class GeneratedConfigs:
    surfgym: dict[str, Any]
    docker: dict[str, Any]


def _error(message: str) -> NoReturn:
    raise OperatorConfigError(message)


def _table(value: object, location: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _error(f"{location} must be a table.")
    return cast(dict[str, Any], value)


def _exact_keys(table: Mapping[str, Any], expected: set[str], location: str) -> None:
    unknown = sorted(set(table) - expected)
    missing = sorted(expected - set(table))
    if unknown:
        _error(f"Unknown key(s) in {location}: {', '.join(unknown)}.")
    if missing:
        _error(f"Missing key(s) in {location}: {', '.join(missing)}.")


def _string(value: object, location: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _error(f"{location} must be a non-empty string.")
    return value


def _integer(value: object, location: str, *, maximum: int = MAX_COUNT) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        _error(f"{location} must be an integer.")
    if not 1 <= value <= maximum:
        _error(f"{location} must be between 1 and {maximum}.")
    return value


def _port(value: object, location: str) -> int:
    return _integer(value, location, maximum=MAX_PORT)


def _timeout(value: object, location: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _error(f"{location} must be a number.")
    result = float(value)
    if not math.isfinite(result) or not 0.0 < result <= MAX_TIMEOUT_SECONDS:
        _error(f"{location} must be greater than 0 and at most {MAX_TIMEOUT_SECONDS:g}.")
    return result


def _runtime_name(value: object, location: str) -> str:
    name = _string(value, location)
    if SAFE_RUNTIME_NAME.fullmatch(name) is None:
        _error(
            f"{location} must be 1 to 63 lowercase characters, start with a letter or "
            "digit, and contain only letters, digits, underscores, or hyphens."
        )
    return name


def _reserve_port(ports: dict[int, str], port: int, owner: str) -> None:
    if port > MAX_PORT:
        _error(f"Computed port for {owner} exceeds {MAX_PORT}: {port}.")
    previous = ports.get(port)
    if previous is not None:
        _error(f"Port collision on {port}: {owner} conflicts with {previous}.")
    ports[port] = owner


def _load_toml(path: Path) -> Mapping[str, Any]:
    try:
        with path.open("rb") as stream:
            value = tomllib.load(stream)
    except FileNotFoundError:
        _error(f"Operator config does not exist: {path}.")
    except tomllib.TOMLDecodeError as exc:
        _error(f"Operator config is not valid TOML: {exc}.")
    return _table(value, "operator config")


def _load_json(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        _error(f"Docker capability template does not exist: {path}.")
    except json.JSONDecodeError as exc:
        _error(f"Docker capability template is not valid JSON: {exc}.")
    return _table(value, "Docker capability template")


def _app_names(apps: Sequence[object], location: str, name_key: str) -> list[str]:
    names: list[str] = []
    for index, raw_app in enumerate(apps):
        app = _table(raw_app, f"{location}[{index}]")
        names.append(_string(app.get(name_key), f"{location}[{index}].{name_key}"))
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        _error(f"Duplicate app name(s) in {location}: {', '.join(duplicates)}.")
    return names


def compile_configs(config_path: Path, surf_repo: Path, docker_repo: Path) -> GeneratedConfigs:
    """Compile one operator TOML file into the two existing runtime JSON contracts."""

    config_path = config_path.resolve()
    surf_repo = surf_repo.resolve()
    docker_repo = docker_repo.resolve()
    if not surf_repo.is_dir():
        _error(f"SurfGym repository does not exist: {surf_repo}.")
    source = _load_toml(config_path)
    _exact_keys(
        source,
        {"paths", "gateway", "wavepool", "docker"},
        "operator config",
    )

    paths = _table(source["paths"], "paths")
    _exact_keys(paths, {"task_file", "log_dir"}, "paths")
    task_file = _string(paths["task_file"], "paths.task_file")
    log_dir = _string(paths["log_dir"], "paths.log_dir")

    gateway = _table(source["gateway"], "gateway")
    _exact_keys(
        gateway,
        {
            "host",
            "port",
            "workers",
            "max_in_flight",
            "verl_timeout_seconds",
            "in_flight_timeout_seconds",
            "deadline_margin_seconds",
        },
        "gateway",
    )
    gateway_host = _string(gateway["host"], "gateway.host")
    if gateway_host != "127.0.0.1":
        _error("gateway.host must be 127.0.0.1 for the local runtime.")
    gateway_port = _port(gateway["port"], "gateway.port")
    workers = _integer(gateway["workers"], "gateway.workers")
    max_in_flight = _integer(gateway["max_in_flight"], "gateway.max_in_flight")
    if workers < max_in_flight:
        _error("gateway.workers must be greater than or equal to gateway.max_in_flight.")

    wavepool = _table(source["wavepool"], "wavepool")
    _exact_keys(
        wavepool,
        {
            "host",
            "master_port",
            "instance_start_port",
            "instances",
            "contexts_per_instance",
            "timeouts",
        },
        "wavepool",
    )
    wavepool_host = _string(wavepool["host"], "wavepool.host")
    if wavepool_host != "127.0.0.1":
        _error("wavepool.host must be 127.0.0.1 for the local runtime.")
    master_port = _port(wavepool["master_port"], "wavepool.master_port")
    instance_start_port = _port(wavepool["instance_start_port"], "wavepool.instance_start_port")
    instances = _integer(wavepool["instances"], "wavepool.instances")
    contexts_per_instance = _integer(
        wavepool["contexts_per_instance"], "wavepool.contexts_per_instance"
    )
    if max_in_flight > instances * contexts_per_instance:
        _error(
            "gateway.max_in_flight must not exceed "
            "wavepool.instances * wavepool.contexts_per_instance."
        )
    timeouts = _table(wavepool["timeouts"], "wavepool.timeouts")
    timeout_keys = {
        "allocate_seconds",
        "release_seconds",
        "screenshot_seconds",
        "observe_seconds",
        "execute_seconds",
        "layer_gap_seconds",
    }
    _exact_keys(timeouts, timeout_keys, "wavepool.timeouts")
    parsed_timeouts = {
        key: _timeout(timeouts[key], f"wavepool.timeouts.{key}") for key in timeout_keys
    }

    docker = _table(source["docker"], "docker")
    _exact_keys(
        docker,
        {"compose_project", "container_prefix", "control_start_port", "apps"},
        "docker",
    )
    compose_project = _runtime_name(docker["compose_project"], "docker.compose_project")
    container_prefix = _runtime_name(docker["container_prefix"], "docker.container_prefix")
    control_start_port = _port(docker["control_start_port"], "docker.control_start_port")
    raw_operator_apps_value = docker["apps"]
    if not isinstance(raw_operator_apps_value, list) or not raw_operator_apps_value:
        _error("docker.apps must be a non-empty array of tables.")
    raw_operator_apps = cast(list[object], raw_operator_apps_value)
    operator_names = _app_names(raw_operator_apps, "operator docker.apps", "name")

    template_path = docker_repo / "config.json"
    template = _load_json(template_path)
    raw_template_apps_value = template.get("apps")
    if not isinstance(raw_template_apps_value, list) or not raw_template_apps_value:
        _error("Docker capability template apps must be a non-empty array.")
    raw_template_apps = cast(list[object], raw_template_apps_value)
    template_names = _app_names(raw_template_apps, "Docker capability template apps", "app")
    unknown_apps = sorted(set(operator_names) - set(template_names))
    missing_apps = sorted(set(template_names) - set(operator_names))
    if unknown_apps:
        _error(f"Unknown app(s) in operator config: {', '.join(unknown_apps)}.")
    if missing_apps:
        _error(f"Missing app(s) in operator config: {', '.join(missing_apps)}.")

    app_topology: dict[str, tuple[int, int, int]] = {}
    for index, raw_app in enumerate(raw_operator_apps):
        app = _table(raw_app, f"docker.apps[{index}]")
        _exact_keys(app, {"name", "base_port", "slots", "port_step"}, f"docker.apps[{index}]")
        name = _string(app["name"], f"docker.apps[{index}].name")
        app_topology[name] = (
            _port(app["base_port"], f"docker.apps[{index}].base_port"),
            _integer(app["slots"], f"docker.apps[{index}].slots"),
            _port(app["port_step"], f"docker.apps[{index}].port_step"),
        )

    ports: dict[int, str] = {}
    for fixed_port, owner in (
        (FIXTURE_CONTENT_PORT, "fixed fixture content endpoint"),
        (DOCKER_GATEWAY_PORT, "fixed Docker gateway endpoint"),
        (gateway_port, "SurfGym gateway"),
        (master_port, "WavePool master"),
    ):
        _reserve_port(ports, fixed_port, owner)
    for site in LOCAL_STATIC_SITES:
        _reserve_port(ports, site.port, f"local static site {site.key}")
    for index in range(instances):
        _reserve_port(ports, instance_start_port + index, f"WavePool instance {index}")

    total_slots = sum(slots for _, slots, _ in app_topology.values())
    if total_slots > MAX_COUNT:
        _error(f"Total Docker slots must be at most {MAX_COUNT}.")
    if control_start_port + total_slots - 1 > MAX_PORT:
        _error("Computed Docker control port exceeds 65535.")
    for index in range(total_slots):
        _reserve_port(ports, control_start_port + index, f"Docker control slot {index}")
    for name in template_names:
        base_port, slots, port_step = app_topology[name]
        for index in range(slots):
            _reserve_port(ports, base_port + index * port_step, f"Docker app {name} slot {index}")

    generated_apps: list[dict[str, Any]] = []
    for raw_template_app in raw_template_apps:
        template_app = copy.deepcopy(_table(raw_template_app, "Docker capability template app"))
        name = str(template_app["app"])
        base_port, slots, port_step = app_topology[name]
        template_app["base_port"] = base_port
        template_app["slot"] = slots
        template_app["port_step"] = port_step
        generated_apps.append(dict(template_app))

    template_gateway = copy.deepcopy(
        _table(template.get("gateway"), "Docker capability template gateway")
    )
    template_gateway.pop("gateway_port", None)
    template_gateway["serving_port"] = DOCKER_GATEWAY_PORT
    template_gateway["control_port"] = control_start_port
    template_gateway["host"] = "127.0.0.1"
    docker_output = copy.deepcopy(dict(template))
    docker_output["runtime"] = {
        "compose_project": compose_project,
        "container_prefix": container_prefix,
    }
    docker_output["gateway"] = dict(template_gateway)
    docker_output["apps"] = generated_apps

    surfgym_output = {
        "task_file_path": str((surf_repo / task_file).resolve())
        if not Path(task_file).is_absolute()
        else str(Path(task_file).resolve()),
        "log_path": str((surf_repo / log_dir).resolve())
        if not Path(log_dir).is_absolute()
        else str(Path(log_dir).resolve()),
        "gateway": {
            "host": gateway_host,
            "port": gateway_port,
            "gateway_workers": workers,
            "gateway_in_flight": max_in_flight,
            "verl_timeout": _timeout(
                gateway["verl_timeout_seconds"], "gateway.verl_timeout_seconds"
            ),
            "in_flight_timeout": _timeout(
                gateway["in_flight_timeout_seconds"], "gateway.in_flight_timeout_seconds"
            ),
            "deadline_margin": _timeout(
                gateway["deadline_margin_seconds"], "gateway.deadline_margin_seconds"
            ),
        },
        "wavepool": {
            "host": wavepool_host,
            "master_port": master_port,
            "instance_start_port": instance_start_port,
            "instances": instances,
            "contexts_per_instance": contexts_per_instance,
            "process_timeout": {
                "allocate": parsed_timeouts["allocate_seconds"],
                "release": parsed_timeouts["release_seconds"],
                "screenshot": parsed_timeouts["screenshot_seconds"],
                "observe": parsed_timeouts["observe_seconds"],
                "execute": parsed_timeouts["execute_seconds"],
                "layer_gap": parsed_timeouts["layer_gap_seconds"],
            },
        },
    }
    generated = GeneratedConfigs(surfgym=surfgym_output, docker=docker_output)
    _validate_generated_configs(generated, docker_repo)
    return generated


def _validate_generated_configs(generated: GeneratedConfigs, docker_repo: Path) -> None:
    try:
        SurfConfig.model_validate(generated.surfgym)
    except ValidationError as exc:
        _error(f"Generated SurfGym config was rejected by its Config model: {exc}.")

    docker_config_module = docker_repo / "src" / "config.py"
    if not docker_config_module.is_file():
        _error(f"Docker config loader does not exist: {docker_config_module}.")
    validator = """import sys
from src.config import Config

try:
    Config.model_validate_json(sys.stdin.read())
except Exception as exc:
    details = str(exc).replace("\\n", " | ")
    print(f"{type(exc).__name__}: {details}", file=sys.stderr)
    raise SystemExit(2)
"""
    try:
        result = subprocess.run(
            [sys.executable, "-c", validator],
            cwd=docker_repo,
            input=json.dumps(generated.docker),
            text=True,
            capture_output=True,
            check=False,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        _error(f"Docker config loader timed out: {docker_config_module}.")
    except OSError as exc:
        _error(f"Docker config loader could not run: {exc}.")
    if result.returncode != 0:
        details = next(
            (line.strip() for line in reversed(result.stderr.splitlines()) if line.strip()),
            "unknown validation error",
        )
        _error(f"Generated Docker config was rejected by {docker_config_module}: {details}.")


def validate_prerequisites(generated: GeneratedConfigs, surf_repo: Path) -> None:
    """Validate artifacts required before the local stack can start."""

    task_file = Path(str(generated.surfgym["task_file_path"]))
    try:
        task_store = TaskStore(task_file)
    except (FileNotFoundError, ValueError, sqlite3.Error) as exc:
        _error(f"Task database prerequisite is invalid: {exc}.")
    else:
        task_store.close()

    fixture_index = surf_repo.resolve() / FIXTURE_INDEX_PATH
    if not fixture_index.is_file():
        _error(f"Fixture build prerequisite is missing: {fixture_index}.")
    for site in LOCAL_STATIC_SITES:
        site_index = surf_repo.resolve() / site.source_dir / "dist" / "index.html"
        if not site_index.is_file():
            _error(f"Local static site build prerequisite is missing for {site.key}: {site_index}.")
    if shutil.which("caddy") is None:
        _error("Caddy executable prerequisite is missing from PATH.")


def _generated_host_ports(generated: GeneratedConfigs) -> list[tuple[int, str]]:
    surf_gateway = _table(generated.surfgym["gateway"], "generated SurfGym gateway")
    wavepool = _table(generated.surfgym["wavepool"], "generated SurfGym wavepool")
    docker_gateway = _table(generated.docker["gateway"], "generated Docker gateway")
    docker_apps_value = generated.docker["apps"]
    if not isinstance(docker_apps_value, list):
        _error("Generated Docker apps must be an array.")
    docker_apps = cast(list[object], docker_apps_value)

    ports: list[tuple[int, str]] = [
        (FIXTURE_CONTENT_PORT, "fixed fixture content endpoint"),
        (_port(surf_gateway["port"], "generated SurfGym gateway port"), "SurfGym gateway"),
        (_port(wavepool["master_port"], "generated WavePool master port"), "WavePool master"),
        (
            _port(docker_gateway["serving_port"], "generated Docker gateway port"),
            "Docker gateway",
        ),
    ]
    ports.extend((site.port, f"local static site {site.key}") for site in LOCAL_STATIC_SITES)
    instance_start = _port(
        wavepool["instance_start_port"], "generated WavePool instance start port"
    )
    instances = _integer(wavepool["instances"], "generated WavePool instances")
    ports.extend(
        (instance_start + index, f"WavePool instance {index}") for index in range(instances)
    )

    control_start = _port(docker_gateway["control_port"], "generated Docker control start port")
    control_index = 0
    for app_index, raw_app in enumerate(docker_apps):
        app = _table(raw_app, f"generated Docker apps[{app_index}]")
        name = _string(app["app"], f"generated Docker apps[{app_index}].app")
        base_port = _port(app["base_port"], f"generated Docker app {name} base port")
        slots = _integer(app["slot"], f"generated Docker app {name} slots")
        port_step = _port(app.get("port_step", 10), f"generated Docker app {name} port step")
        for slot_index in range(slots):
            ports.append((control_start + control_index, f"Docker control slot {control_index}"))
            ports.append(
                (base_port + slot_index * port_step, f"Docker app {name} slot {slot_index}")
            )
            control_index += 1
    return ports


def validate_host_ports(generated: GeneratedConfigs) -> None:
    """Fail unless every generated loopback host port can be bound now."""

    bound_sockets: list[socket.socket] = []
    try:
        for port, owner in _generated_host_ports(generated):
            candidate = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                    candidate.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
                candidate.bind(("127.0.0.1", port))
            except OSError as exc:
                candidate.close()
                _error(f"Host port {port} is unavailable for {owner} on 127.0.0.1: {exc}.")
            bound_sockets.append(candidate)
    finally:
        for candidate in bound_sockets:
            candidate.close()


def _json_bytes(value: Mapping[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def _stage_output(path: Path, content: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise
    return temporary_path


def write_configs(generated: GeneratedConfigs, surf_output: Path, docker_output: Path) -> None:
    """Stage both documents, then atomically replace each destination individually.

    The two files are not a transactional pair. Callers must consume neither file
    unless this function returns successfully.
    """

    if surf_output.resolve() == docker_output.resolve():
        _error("SurfGym and Docker output paths must be different.")
    staged: list[tuple[Path, Path]] = []
    try:
        staged.append((_stage_output(surf_output, _json_bytes(generated.surfgym)), surf_output))
        staged.append((_stage_output(docker_output, _json_bytes(generated.docker)), docker_output))
        for temporary_path, destination in staged:
            os.replace(temporary_path, destination)
    finally:
        for temporary_path, _ in staged:
            temporary_path.unlink(missing_ok=True)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compile the SurfGym local runtime configuration.")
    parser.add_argument("--config", type=Path, required=True, help="Path to config/runtime.toml.")
    parser.add_argument(
        "--surf-repo", type=Path, required=True, help="Path to the SurfGym repository."
    )
    parser.add_argument(
        "--docker-repo", type=Path, required=True, help="Path to the Docker repository."
    )
    parser.add_argument(
        "--surf-output", type=Path, required=True, help="Generated SurfGym JSON path."
    )
    parser.add_argument(
        "--docker-output", type=Path, required=True, help="Generated Docker JSON path."
    )
    parser.add_argument(
        "--check", action="store_true", help="Validate and render in memory without writing files."
    )
    parser.add_argument(
        "--check-prerequisites",
        action="store_true",
        help="Require a valid task database and built fixture index before succeeding.",
    )
    parser.add_argument(
        "--check-host-ports",
        action="store_true",
        help="Require every generated 127.0.0.1 host port to be bindable now.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        generated = compile_configs(args.config, args.surf_repo, args.docker_repo)
        if args.check_prerequisites:
            validate_prerequisites(generated, args.surf_repo)
        if args.check_host_ports:
            validate_host_ports(generated)
        if not args.check:
            write_configs(generated, args.surf_output, args.docker_output)
    except (OperatorConfigError, OSError) as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2
    mode = "validated" if args.check else "generated"
    print(f"Runtime configuration {mode}: {len(generated.docker['apps'])} apps.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
