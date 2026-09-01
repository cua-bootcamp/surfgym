from __future__ import annotations

import json
from pathlib import Path

import pytest
from surfgym_contracts.local_static_sites import LOCAL_STATIC_SITES
from surfgym_fixture import local_static_host
from surfgym_fixture.local_static_host import (
    RenderInputs,
    render_caddyfile,
    render_ports,
    validate_builds,
    write_runtime_files,
)


def _built_tree(root: Path) -> RenderInputs:
    fixture_dist = root / "fixture" / "dist"
    fixture_dist.mkdir(parents=True)
    (fixture_dist / "index.html").write_text("fixture", encoding="utf-8")
    for site in LOCAL_STATIC_SITES:
        dist = root / site.source_dir / "dist"
        dist.mkdir(parents=True)
        (dist / "index.html").write_text(site.key, encoding="utf-8")
    return RenderInputs(repo_root=root, fixture_dist=fixture_dist, state_dir=root / "states")


def test_renderer_combines_fixture_and_distinct_static_origins(tmp_path: Path) -> None:
    inputs = _built_tree(tmp_path)

    caddyfile = render_caddyfile(inputs)
    ports = render_ports()

    assert "admin off" in caddyfile
    assert "http://127.0.0.1:3000" in caddyfile
    assert "http://127.0.0.1:8051" in caddyfile
    assert "http://127.0.0.1:8052" in caddyfile
    assert ":8051 {" not in caddyfile.replace("http://127.0.0.1:8051 {", "")
    assert "handle /post" in caddyfile
    assert "respond 204" in caddyfile
    assert "{query.sid}.matches('^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$')" in caddyfile
    assert "handle @valid_state" in caddyfile
    assert "handle /state" in caddyfile
    assert "respond 400" in caddyfile
    assert "rewrite * /{http.request.uri.query.sid}.json" in caddyfile
    assert "try_files {path} /default.json" in caddyfile
    assert "try_files {path} /index.html" in caddyfile
    assert ports["INSTACART"] == "http://127.0.0.1:8051"
    assert ports["INSTAGRAM"] == "http://127.0.0.1:8052"
    assert len(ports) == 14


def test_missing_site_build_fails_closed(tmp_path: Path) -> None:
    inputs = _built_tree(tmp_path)
    missing = tmp_path / LOCAL_STATIC_SITES[-1].source_dir / "dist" / "index.html"
    missing.unlink()

    with pytest.raises(FileNotFoundError, match=LOCAL_STATIC_SITES[-1].key):
        validate_builds(inputs)


def test_runtime_files_are_written_together_and_check_can_remain_non_mutating(
    tmp_path: Path,
) -> None:
    inputs = _built_tree(tmp_path)
    output_dir = tmp_path / "runtime"

    validate_builds(inputs)
    assert not output_dir.exists()

    write_runtime_files(inputs, output_dir)

    assert (output_dir / "Caddyfile").read_text(encoding="utf-8") == render_caddyfile(inputs)
    assert json.loads((output_dir / "ports.json").read_text(encoding="utf-8")) == render_ports()
    assert not list(output_dir.glob("*.tmp"))


def test_second_replace_failure_restores_the_previous_generation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs = _built_tree(tmp_path)
    output_dir = tmp_path / "runtime"
    output_dir.mkdir()
    caddyfile = output_dir / "Caddyfile"
    ports_file = output_dir / "ports.json"
    caddyfile.write_bytes(b"old caddy generation\n")
    ports_file.write_bytes(b'{"OLD":"http://127.0.0.1:1"}\n')
    previous = (caddyfile.read_bytes(), ports_file.read_bytes())
    real_replace = local_static_host.os.replace
    calls = 0

    def fail_second_replace(source: Path, destination: Path) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected second replace failure")
        real_replace(source, destination)

    monkeypatch.setattr(local_static_host.os, "replace", fail_second_replace)

    with pytest.raises(OSError, match="injected second replace failure"):
        write_runtime_files(inputs, output_dir)

    assert (caddyfile.read_bytes(), ports_file.read_bytes()) == previous
    assert not list(output_dir.glob("*.tmp"))
