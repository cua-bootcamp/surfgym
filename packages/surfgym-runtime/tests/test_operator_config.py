from __future__ import annotations

import copy
import json
import socket
import sqlite3
from pathlib import Path

import pytest
import surfgym_runtime.support.operator_config as operator_config
from surfgym_runtime.support.config import load_config
from surfgym_runtime.support.operator_config import (
    OperatorConfigError,
    compile_configs,
    main,
    validate_host_ports,
    validate_prerequisites,
    write_configs,
)

SURF_REPO = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG = SURF_REPO / "config" / "runtime.toml"
DOCKER_TEMPLATE = {
    "gateway": {"host": "127.0.0.1", "serving_port": 53001, "control_port": 53002},
    "apps": [
        {
            "app": "impress",
            "image": "example/impress:fixed",
            "base_port": 54001,
            "slot": 4,
            "reset_paths": ["recently-used"],
            "reset_contents": ["Desktop"],
        },
        {
            "app": "vlc",
            "image": "example/vlc:fixed",
            "base_port": 54701,
            "slot": 4,
            "open_command": "vlc {file}",
        },
        {"app": "gimp", "image": "example/gimp:fixed", "base_port": 54801, "slot": 4},
        {"app": "vscode", "image": "example/vscode:fixed", "base_port": 54901, "slot": 4},
        {
            "app": "chrome",
            "image": "example/chrome:fixed",
            "build": {"context": "docker/chrome", "dockerfile": "Dockerfile"},
            "base_port": 55001,
            "slot": 4,
        },
        {
            "app": "workspace",
            "image": "surfgym-workspace:union-canary",
            "build": {
                "context": "docker/workspace",
                "dockerfile": "Dockerfile",
                "args": {
                    "BASE_IMAGE": (
                        "lscr.io/linuxserver/vscode@sha256:"
                        "3c09bd87f951a4a212d26249fd38f3257fbd6b8f9752b370616231f097c1bae3"
                    )
                },
            },
            "base_port": 55101,
            "slot": 1,
            "environment": {"DISABLE_TERMINALS": "false"},
            "fixture_apps": ["gimp", "impress", "vlc", "vscode", "workspace"],
            "launch_commands": {
                "terminal": ["xfce4-terminal", "--disable-server", "{args}"],
                "gimp": ["gimp", "--new-instance", "{args}", "{file}"],
                "vscode": [
                    "code",
                    "--skip-welcome",
                    "--skip-release-notes",
                    "--disable-workspace-trust",
                    "--wait",
                    "{args}",
                    "{file}",
                ],
                "vlc": ["vlc", "{args}", "{file}"],
                "impress": ["libreoffice", "--impress", "{args}", "{file}"],
            },
            "reset_paths": [
                ".config/GIMP/3.0",
                ".config/vlc",
                ".config/Code",
                ".config/libreoffice",
                ".config/xfce4/terminal",
                ".bash_history",
                ".vscode/extensions",
                ".local/share/recently-used.xbel",
            ],
            "reset_contents": ["Desktop"],
        },
    ],
}


def _sandbox(tmp_path: Path) -> tuple[Path, Path]:
    surf_repo = tmp_path / "surf"
    config_dir = surf_repo / "config"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "runtime.toml"
    config_path.write_bytes(DEFAULT_CONFIG.read_bytes())
    docker_repo = tmp_path / "docker"
    docker_repo.mkdir()
    (docker_repo / "config.json").write_text(json.dumps(DOCKER_TEMPLATE), encoding="utf-8")
    docker_src = docker_repo / "src"
    docker_src.mkdir()
    (docker_src / "__init__.py").write_text("", encoding="utf-8")
    (docker_src / "config.py").write_text(
        """import json


class Config:
    @classmethod
    def model_validate_json(cls, payload):
        data = json.loads(payload)
        gateway = data["gateway"]
        if gateway.get("serving_port") != 53001 or "gateway_port" in gateway:
            raise ValueError("invalid gateway alias normalization")
        if any(not isinstance(app.get("image"), str) for app in data["apps"]):
            raise ValueError("image must be a string")
        return cls()
""",
        encoding="utf-8",
    )
    return config_path, docker_repo


def _compile(config_path: Path, docker_repo: Path):
    return compile_configs(config_path, config_path.parent.parent, docker_repo)


def _create_valid_task_database(surf_repo: Path) -> Path:
    task_path = surf_repo / ".runtime" / "tasks" / "tasks.sqlite3"
    task_path.parent.mkdir(parents=True)
    connection = sqlite3.connect(task_path)
    try:
        connection.execute("CREATE TABLE tasks (task_id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
        connection.commit()
    finally:
        connection.close()
    return task_path


def _create_valid_static_site_builds(surf_repo: Path) -> None:
    for site in operator_config.LOCAL_STATIC_SITES:
        index = surf_repo / site.source_dir / "dist" / "index.html"
        index.parent.mkdir(parents=True)
        index.write_text("<!doctype html>", encoding="utf-8")


def _replace(config_path: Path, old: str, new: str) -> None:
    text = config_path.read_text(encoding="utf-8")
    assert old in text
    config_path.write_text(text.replace(old, new, 1), encoding="utf-8")


def test_default_config_preserves_legacy_semantics_and_capabilities(tmp_path: Path):
    config_path, docker_repo = _sandbox(tmp_path)
    generated = _compile(config_path, docker_repo)
    legacy_surf = json.loads((SURF_REPO / "scripts" / "config.json").read_text(encoding="utf-8"))
    template = json.loads((docker_repo / "config.json").read_text(encoding="utf-8"))

    assert generated.surfgym["gateway"] == legacy_surf["gateway"]
    assert generated.surfgym["wavepool"] == legacy_surf["wavepool"]
    assert (
        Path(generated.surfgym["task_file_path"])
        == tmp_path / "surf" / ".runtime/tasks/tasks.sqlite3"
    )
    assert Path(generated.surfgym["log_path"]) == tmp_path / "surf" / "logs"
    assert [app["app"] for app in generated.docker["apps"]] == [
        app["app"] for app in template["apps"]
    ]
    assert len(generated.docker["apps"]) == 6
    assert sum(app["slot"] for app in generated.docker["apps"]) == 21
    workspace = next(app for app in generated.docker["apps"] if app["app"] == "workspace")
    assert workspace["base_port"] == 59501
    expected_docker = copy.deepcopy(template)
    expected_docker["gateway"]["control_port"] = 58001
    expected_docker["runtime"] = {
        "compose_project": "surfgym-local",
        "container_prefix": "surfgym-local",
    }
    for app, base_port in zip(
        expected_docker["apps"],
        [59001, 59101, 59201, 59301, 59401, 59501],
        strict=True,
    ):
        app["base_port"] = base_port
        app["port_step"] = 10
    assert generated.docker == expected_docker

    topology_keys = {"base_port", "slot", "port_step"}
    for actual, expected in zip(generated.docker["apps"], template["apps"], strict=True):
        assert {key: value for key, value in actual.items() if key not in topology_keys} == {
            key: value for key, value in expected.items() if key not in topology_keys
        }


def test_explicit_surf_repo_controls_relative_path_resolution(tmp_path: Path):
    config_path, docker_repo = _sandbox(tmp_path)
    surf_repo = config_path.parent.parent
    external_config = tmp_path / "operator-config.toml"
    external_config.write_bytes(config_path.read_bytes())

    generated = compile_configs(external_config, surf_repo, docker_repo)

    assert Path(generated.surfgym["task_file_path"]).is_relative_to(surf_repo)
    assert Path(generated.surfgym["log_path"]) == surf_repo / "logs"


def test_conflicting_docker_gateway_alias_is_removed(tmp_path: Path):
    config_path, docker_repo = _sandbox(tmp_path)
    template_path = docker_repo / "config.json"
    template = json.loads(template_path.read_text(encoding="utf-8"))
    template["gateway"]["gateway_port"] = 12345
    template_path.write_text(json.dumps(template), encoding="utf-8")

    generated = _compile(config_path, docker_repo)

    assert generated.docker["gateway"]["serving_port"] == 53001
    assert "gateway_port" not in generated.docker["gateway"]


def test_safe_docker_runtime_identity_is_forwarded(tmp_path: Path):
    config_path, docker_repo = _sandbox(tmp_path)
    _replace(
        config_path,
        'compose_project = "surfgym-local"',
        'compose_project = "train_01"',
    )
    _replace(
        config_path,
        'container_prefix = "surfgym-local"',
        'container_prefix = "worker-a"',
    )

    generated = _compile(config_path, docker_repo)

    assert generated.docker["runtime"] == {
        "compose_project": "train_01",
        "container_prefix": "worker-a",
    }


def test_non_default_port_step_is_forwarded_for_multiple_slots(tmp_path: Path):
    config_path, docker_repo = _sandbox(tmp_path)
    _replace(config_path, "slots = 4\nport_step = 10", "slots = 2\nport_step = 37")

    generated = _compile(config_path, docker_repo)

    impress = generated.docker["apps"][0]
    assert impress["slot"] == 2
    assert impress["port_step"] == 37


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("compose_project", "Uppercase"),
        ("compose_project", "-leading"),
        ("container_prefix", "contains.dot"),
        ("container_prefix", "a" * 64),
    ],
)
def test_unsafe_docker_runtime_identity_fails_closed(tmp_path: Path, key: str, value: str):
    config_path, docker_repo = _sandbox(tmp_path)
    _replace(config_path, f'{key} = "surfgym-local"', f'{key} = "{value}"')

    with pytest.raises(OperatorConfigError, match="1 to 63 lowercase characters"):
        _compile(config_path, docker_repo)


def test_selected_docker_loader_rejects_invalid_generated_config(tmp_path: Path):
    config_path, docker_repo = _sandbox(tmp_path)
    template_path = docker_repo / "config.json"
    template = json.loads(template_path.read_text(encoding="utf-8"))
    template["apps"][0]["image"] = 7
    template_path.write_text(json.dumps(template), encoding="utf-8")

    with pytest.raises(OperatorConfigError, match="Generated Docker config was rejected"):
        _compile(config_path, docker_repo)


def test_generated_surf_json_round_trips_existing_loader(tmp_path: Path):
    config_path, docker_repo = _sandbox(tmp_path)
    generated = _compile(config_path, docker_repo)
    output = tmp_path / "surfgym.json"
    write_configs(generated, output, tmp_path / "docker.json")

    loaded = load_config(output)
    assert loaded.gateway_config.gateway_in_flight == 6
    assert loaded.wavepool_config.contexts_per_instance == 6


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        ("workers = 6", "workers = 6\nunknown = 1", "Unknown key"),
        ("workers = 6", "workers = 5", "greater than or equal"),
        ("contexts_per_instance = 6", "contexts_per_instance = 5", "must not exceed"),
        ("port = 18000", "port = 0", "between 1 and 65535"),
        ("allocate_seconds = 10.0", "allocate_seconds = -1.0", "greater than 0"),
        ("allocate_seconds = 10.0", "allocate_seconds = nan", "greater than 0"),
        ("base_port = 59001", "base_port = 53001", "Port collision"),
        ('name = "impress"', 'name = "unknown"', "Unknown app"),
    ],
)
def test_invalid_operator_values_fail_closed(tmp_path: Path, old: str, new: str, message: str):
    config_path, docker_repo = _sandbox(tmp_path)
    _replace(config_path, old, new)

    with pytest.raises(OperatorConfigError, match=message):
        _compile(config_path, docker_repo)


def test_duplicate_and_missing_apps_fail_closed(tmp_path: Path):
    config_path, docker_repo = _sandbox(tmp_path)
    _replace(config_path, 'name = "vlc"', 'name = "impress"')
    with pytest.raises(OperatorConfigError, match="Duplicate app"):
        _compile(config_path, docker_repo)

    config_path, docker_repo = _sandbox(tmp_path / "missing")
    text = config_path.read_text(encoding="utf-8")
    start = text.index('[[docker.apps]]\nname = "chrome"')
    config_path.write_text(text[:start], encoding="utf-8")
    with pytest.raises(OperatorConfigError, match="Missing app"):
        _compile(config_path, docker_repo)


def test_duplicate_apps_in_capability_template_fail_closed(tmp_path: Path):
    config_path, docker_repo = _sandbox(tmp_path)
    template_path = docker_repo / "config.json"
    template = json.loads(template_path.read_text(encoding="utf-8"))
    template["apps"][1]["app"] = "impress"
    template_path.write_text(json.dumps(template), encoding="utf-8")

    with pytest.raises(OperatorConfigError, match="Duplicate app"):
        _compile(config_path, docker_repo)


def test_output_is_deterministic_and_replaces_each_file_atomically(tmp_path: Path):
    config_path, docker_repo = _sandbox(tmp_path)
    first = _compile(config_path, docker_repo)
    second = _compile(config_path, docker_repo)
    surf_output = tmp_path / "out" / "surfgym.json"
    docker_output = tmp_path / "out" / "docker.json"
    surf_output.parent.mkdir()
    surf_output.write_text("stale", encoding="utf-8")
    docker_output.write_text("stale", encoding="utf-8")

    write_configs(first, surf_output, docker_output)
    first_bytes = (surf_output.read_bytes(), docker_output.read_bytes())
    write_configs(second, surf_output, docker_output)

    assert (surf_output.read_bytes(), docker_output.read_bytes()) == first_bytes
    assert not list(surf_output.parent.glob("*.tmp"))


def test_output_paths_must_be_different(tmp_path: Path):
    config_path, docker_repo = _sandbox(tmp_path)
    generated = _compile(config_path, docker_repo)
    output = tmp_path / "runtime.json"

    with pytest.raises(OperatorConfigError, match="must be different"):
        write_configs(generated, output, output)


def test_second_atomic_replace_failure_returns_nonzero(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    config_path, docker_repo = _sandbox(tmp_path)
    surf_output = tmp_path / "out" / "surfgym.json"
    docker_output = tmp_path / "out" / "docker.json"
    real_replace = operator_config.os.replace
    calls = 0

    def fail_second_replace(source: Path, destination: Path) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("simulated second replace failure")
        real_replace(source, destination)

    monkeypatch.setattr(operator_config.os, "replace", fail_second_replace)
    result = main(
        [
            "--config",
            str(config_path),
            "--surf-repo",
            str(config_path.parent.parent),
            "--docker-repo",
            str(docker_repo),
            "--surf-output",
            str(surf_output),
            "--docker-output",
            str(docker_output),
        ]
    )

    assert result == 2
    assert "simulated second replace failure" in capsys.readouterr().err
    assert surf_output.is_file()
    assert not docker_output.exists()
    assert not list(surf_output.parent.glob("*.tmp"))


def test_prerequisites_reject_missing_task_database(tmp_path: Path):
    config_path, docker_repo = _sandbox(tmp_path)
    generated = _compile(config_path, docker_repo)

    with pytest.raises(OperatorConfigError, match="Task database prerequisite is invalid"):
        validate_prerequisites(generated, config_path.parent.parent)


def test_prerequisites_reject_invalid_task_database_schema(tmp_path: Path):
    config_path, docker_repo = _sandbox(tmp_path)
    surf_repo = config_path.parent.parent
    task_path = surf_repo / ".runtime" / "tasks" / "tasks.sqlite3"
    task_path.parent.mkdir(parents=True)
    connection = sqlite3.connect(task_path)
    try:
        connection.execute("CREATE TABLE wrong_table (value TEXT)")
        connection.commit()
    finally:
        connection.close()
    generated = _compile(config_path, docker_repo)

    with pytest.raises(OperatorConfigError, match="missing columns: payload, task_id"):
        validate_prerequisites(generated, surf_repo)


def test_prerequisites_reject_missing_fixture_build(tmp_path: Path):
    config_path, docker_repo = _sandbox(tmp_path)
    surf_repo = config_path.parent.parent
    _create_valid_task_database(surf_repo)
    generated = _compile(config_path, docker_repo)

    with pytest.raises(OperatorConfigError, match="Fixture build prerequisite is missing"):
        validate_prerequisites(generated, surf_repo)


def test_prerequisites_reject_missing_static_site_build(tmp_path: Path) -> None:
    config_path, docker_repo = _sandbox(tmp_path)
    surf_repo = config_path.parent.parent
    _create_valid_task_database(surf_repo)
    fixture_index = surf_repo / operator_config.FIXTURE_INDEX_PATH
    fixture_index.parent.mkdir(parents=True)
    fixture_index.write_text("<!doctype html>", encoding="utf-8")
    generated = _compile(config_path, docker_repo)

    with pytest.raises(OperatorConfigError, match="Local static site build prerequisite"):
        validate_prerequisites(generated, surf_repo)


def test_prerequisites_accept_valid_task_database_and_fixture_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    config_path, docker_repo = _sandbox(tmp_path)
    surf_repo = config_path.parent.parent
    _create_valid_task_database(surf_repo)
    fixture_index = surf_repo / operator_config.FIXTURE_INDEX_PATH
    fixture_index.parent.mkdir(parents=True)
    fixture_index.write_text("<!doctype html>", encoding="utf-8")
    _create_valid_static_site_builds(surf_repo)
    monkeypatch.setattr(operator_config.shutil, "which", lambda _name: "caddy")
    generated = _compile(config_path, docker_repo)

    validate_prerequisites(generated, surf_repo)


def test_host_port_check_includes_all_generated_topology_and_fixed_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    config_path, docker_repo = _sandbox(tmp_path)
    generated = _compile(config_path, docker_repo)
    bound: list[tuple[str, int]] = []
    closed: list[bool] = []

    class RecordingSocket:
        def setsockopt(self, *_args: object) -> None:
            pass

        def bind(self, address: tuple[str, int]) -> None:
            bound.append(address)

        def close(self) -> None:
            closed.append(True)

    monkeypatch.setattr(operator_config.socket, "socket", lambda *_args: RecordingSocket())

    validate_host_ports(generated)

    assert len(bound) == 61
    assert ("127.0.0.1", 3000) in bound
    assert ("127.0.0.1", 18000) in bound
    assert ("127.0.0.1", 53001) in bound
    assert ("127.0.0.1", 58021) in bound
    assert ("127.0.0.1", 59431) in bound
    assert ("127.0.0.1", 59501) in bound
    assert ("127.0.0.1", 8051) in bound
    assert ("127.0.0.1", 8088) in bound
    assert len(closed) == len(bound)


def test_static_site_port_collision_fails_during_compile(tmp_path: Path) -> None:
    config_path, docker_repo = _sandbox(tmp_path)
    _replace(config_path, "port = 18000", "port = 8052")

    with pytest.raises(OperatorConfigError, match="Port collision on 8052"):
        _compile(config_path, docker_repo)


def test_host_port_check_rejects_an_occupied_loopback_port(tmp_path: Path):
    config_path, docker_repo = _sandbox(tmp_path)
    occupied = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            occupied.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        occupied.bind(("127.0.0.1", 0))
        occupied_port = int(occupied.getsockname()[1])
        _replace(config_path, "port = 18000", f"port = {occupied_port}")
        generated = _compile(config_path, docker_repo)

        with pytest.raises(OperatorConfigError, match=f"Host port {occupied_port} is unavailable"):
            validate_host_ports(generated)
    finally:
        occupied.close()


def test_failed_check_does_not_write_outputs(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    config_path, docker_repo = _sandbox(tmp_path)
    _replace(config_path, "workers = 6", "workers = 0")
    surf_output = tmp_path / "surfgym.json"
    docker_output = tmp_path / "docker.json"

    result = main(
        [
            "--config",
            str(config_path),
            "--surf-repo",
            str(config_path.parent.parent),
            "--docker-repo",
            str(docker_repo),
            "--surf-output",
            str(surf_output),
            "--docker-output",
            str(docker_output),
            "--check",
        ]
    )

    assert result == 2
    assert "Configuration error" in capsys.readouterr().err
    assert not surf_output.exists()
    assert not docker_output.exists()


def test_successful_check_reports_summary_without_writing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    config_path, docker_repo = _sandbox(tmp_path)
    surf_output = tmp_path / "surfgym.json"
    docker_output = tmp_path / "docker.json"

    result = main(
        [
            "--config",
            str(config_path),
            "--surf-repo",
            str(config_path.parent.parent),
            "--docker-repo",
            str(docker_repo),
            "--surf-output",
            str(surf_output),
            "--docker-output",
            str(docker_output),
            "--check",
        ]
    )

    assert result == 0
    assert capsys.readouterr().out == "Runtime configuration validated: 6 apps.\n"
    assert not surf_output.exists()
    assert not docker_output.exists()


def test_cli_host_port_failure_does_not_write_outputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    config_path, docker_repo = _sandbox(tmp_path)
    surf_output = tmp_path / "surfgym.json"
    docker_output = tmp_path / "docker.json"

    def reject_ports(_generated: object) -> None:
        raise OperatorConfigError("simulated occupied host port")

    monkeypatch.setattr(operator_config, "validate_host_ports", reject_ports)
    result = main(
        [
            "--config",
            str(config_path),
            "--surf-repo",
            str(config_path.parent.parent),
            "--docker-repo",
            str(docker_repo),
            "--surf-output",
            str(surf_output),
            "--docker-output",
            str(docker_output),
            "--check",
            "--check-host-ports",
        ]
    )

    assert result == 2
    assert "simulated occupied host port" in capsys.readouterr().err
    assert not surf_output.exists()
    assert not docker_output.exists()


def test_cli_check_prerequisites_validates_without_writing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    config_path, docker_repo = _sandbox(tmp_path)
    surf_repo = config_path.parent.parent
    _create_valid_task_database(surf_repo)
    fixture_index = surf_repo / operator_config.FIXTURE_INDEX_PATH
    fixture_index.parent.mkdir(parents=True)
    fixture_index.write_text("<!doctype html>", encoding="utf-8")
    _create_valid_static_site_builds(surf_repo)
    monkeypatch.setattr(operator_config.shutil, "which", lambda _name: "caddy")
    surf_output = tmp_path / "surfgym.json"
    docker_output = tmp_path / "docker.json"

    result = main(
        [
            "--config",
            str(config_path),
            "--surf-repo",
            str(surf_repo),
            "--docker-repo",
            str(docker_repo),
            "--surf-output",
            str(surf_output),
            "--docker-output",
            str(docker_output),
            "--check",
            "--check-prerequisites",
        ]
    )

    assert result == 0
    assert capsys.readouterr().out == "Runtime configuration validated: 6 apps.\n"
    assert not surf_output.exists()
    assert not docker_output.exists()


def test_topology_overlay_does_not_mutate_template(tmp_path: Path):
    config_path, docker_repo = _sandbox(tmp_path)
    template_path = docker_repo / "config.json"
    template = json.loads(template_path.read_text(encoding="utf-8"))
    template["apps"][0]["custom_capability"] = {"opaque": [1, 2, 3]}
    original = copy.deepcopy(template)
    template_path.write_text(json.dumps(template), encoding="utf-8")
    _replace(config_path, "slots = 4", "slots = 3")

    generated = _compile(config_path, docker_repo)

    assert json.loads(template_path.read_text(encoding="utf-8")) == original
    assert generated.docker["apps"][0]["slot"] == 3
    assert generated.docker["apps"][0]["custom_capability"] == {"opaque": [1, 2, 3]}
