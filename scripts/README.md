# Local development scripts

Use `local_dev.bash` as the official local stack entrypoint:

```bash
bash scripts/local_dev.bash check
bash scripts/local_dev.bash up
bash scripts/local_dev.bash down
```

The command reads the human-edited `config/runtime.toml`, validates it, and
generates `.runtime/config/surfgym.json` and `.runtime/config/docker.json`.
`up` always regenerates these files before it starts any component. Generated
files are runtime artifacts and must not be edited.

The Docker repository is selected in this order:

1. `--docker-repo PATH`
2. `SURFGYM_DOCKER_REPO`
3. the sibling directory `surfgym-docker-dev`

`PYTHON_BIN` selects the interpreter for the SurfGym compiler and SurfGym
runtime. `DOCKER_PYTHON_BIN` selects the interpreter passed to the Docker
renderer, control supervisor, and gateway supervisor. If it is unset, it uses
an explicitly supplied `PYTHON_BIN`, or `python3` when neither variable is set.
Set both variables when the two repositories use different virtual
environments.

Docker Compose, slot directories, logs, and PID files remain under the Docker
repository. The generated Docker config is passed through `CONFIG_PATH`; the
generated SurfGym config is passed through `SURFGYM_CONFIG`.

The existing component launchers remain available for debugging. They use an
explicit `SURFGYM_CONFIG` when provided and otherwise use the legacy
`scripts/config.json`. They never select a generated config by file existence.

Configuration is loaded at process startup. Restart the stack after changing
`config/runtime.toml`; hot reload is not supported.

`down` stops only the SurfGym processes and Docker supervisors recorded by the
local launch flow, then stops the Docker-owned Compose pool. It does not search
for or terminate arbitrary processes by configured port.

Both `check` and `up` validate required local artifacts, including the selected
task database and fixture distribution, and fail before launch when a required
host port is unavailable. The generated Docker config also owns the local
Compose project name and container prefix. `down` reads the exact project name
from that generated config and never falls back to an inferred directory name.
`up` reports success only after the Docker supervisors, SurfGym gateway,
WavePool, and fixture HTTP endpoints are ready. This is local service readiness;
it is not headed-GUI or CUA acceptance.

On Windows, an old WSL `portproxy` rule can reserve the fixed Docker gateway
endpoint even when no WSL service is running. Inspect it with
`netsh interface portproxy show v4tov4`. Remove a `127.0.0.1:53001` rule from an
elevated terminal only when its WSL owner is no longer used; `local_dev.bash
check` remains the authoritative preflight after any host-network change.
