# SurfGym Repository Rules

## Local runtime configuration

- `config/runtime.toml` is the only operator-edited source for local runtime topology.
- Keep all keys, comments, validation messages, and operator-facing output in English.
- Never edit generated `.runtime/config/surfgym.json` or `.runtime/config/docker.json` files.
- The official launcher must run the operator config compiler before starting either repository and pass the generated files through the existing `CONFIG_PATH` contracts.
- The compiler must receive explicit SurfGym and Docker repository paths. Never infer the SurfGym root from the operator config location.
- Official `check` and `up` operations must validate the task database schema and built fixture index before succeeding.
- Generated SurfGym and Docker JSON files are each replaced atomically, but they are not a transactional pair. Launchers must consume neither file unless compilation returns successfully.
- Docker application images, build declarations, reset policies, and open commands remain owned by the Docker repository capability template.
- Docker gateway port `53001` and fixture content port `3000` are fixed integration endpoints.
- Preserve strict validation for unknown keys, numeric bounds, capacity relationships, app-set equality, all computed port collisions, and acceptance by both repositories' actual config models.

# Repository guidance

Architecture and runtime behavior are documented in `docs/project-context.md`.
Keep SurfGym web-first: native surfaces are a bounded fallback, not a general OS or
provider abstraction.
