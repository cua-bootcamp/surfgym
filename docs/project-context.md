# Project context

## Local runtime configuration ownership

SurfGym is the composition root for the local training stack. Operators change topology only in `config/runtime.toml`. The file covers SurfGym capacity and ports plus Docker application slot topology. Its keys and comments are deliberately written in English for a stable operator contract.

`gateway.artifact_reward_timeout_seconds` is the public budget for any reward request that explicitly declares artifacts. Selection is based on the generic request contract, not on a workspace or application identity. The compiler keeps its usable budget large enough to cover the fixed 35-second Docker artifact bridge plus the configured WavePool layer gap; reward requests without artifacts retain `verl_timeout_seconds`.

The compiler receives explicit SurfGym and Docker repository paths; it never infers the SurfGym root from the location of the operator config. It reads the Docker repository's `config.json` as an opaque capability template, preserves application order and capability fields, and overlays only the whitelisted topology fields. Relative SurfGym task and log paths resolve from the explicit SurfGym repository root. The `[docker]` `compose_project` and `container_prefix` keys provide the lowercase runtime identity forwarded as the generated Docker JSON `runtime` object.

Before writing, the compiler validates the complete port and capacity plan in memory and submits the generated dictionaries to SurfGym's current `Config` model and the selected Docker repository's current `src.config.Config` model. This makes schema drift a launch-time error instead of producing an incompatible runtime file. Docker gateway aliases are normalized so a capability template cannot preserve a conflicting `gateway_port` value over fixed serving port `53001`.

Generated `.runtime/config/surfgym.json` and `.runtime/config/docker.json` files are disposable runtime artifacts. They must not be edited or treated as configuration sources. Each destination is replaced atomically after both complete documents have been staged, but the pair is not a transactional unit. The official launcher regenerates them before every launch, consumes neither output after a compiler error, and passes them to existing consumers through `CONFIG_PATH` only after success.

The combined runtime task database is a run-owned `.runtime/tasks/tasks.sqlite3` artifact. Build it explicitly with `python -m surfgym_task.main publish --output .runtime/tasks/tasks.sqlite3`; repeat `--domain` to select a subset, or omit it for the approved eight-domain COARSE/ROLLOUT corpus. The publisher rejects duplicate task IDs before it opens the output database, writes all selected domains through one `TaskWriter`, and keeps instruction caches and task detail JSON under their owning domain directories.

The official local entrypoint provides `check`, `up`, and `down`. Both `check` and `up` require the already-built configured task SQLite database to open through `TaskStore` with the expected schema and require `packages/surfgym-fixture/src/surfgym_fixture/dist/index.html` to exist. `check` never publishes task data or writes generated runtime configuration. Shutdown uses recorded SurfGym and Docker supervisor PIDs and the Docker-owned Compose file; it does not search for processes by configured port.

Docker gateway port `53001` and fixture content port `3000` are fixed because existing task data and runtime integration code depend on them. There is no separate fixture process-port setting in the operator config.

The compiler's optional `--check-host-ports` gate attempts to bind every generated SurfGym, WavePool, Docker gateway, Docker control, Docker application, and fixed fixture port on `127.0.0.1`. Any bind failure, including an occupied or Windows-excluded port, fails closed. This check is independent of `--check`: `--check` still controls whether generated files are written.

The compiler fails closed on unknown or missing keys, invalid numeric bounds, insufficient worker or WavePool capacity, duplicate/missing/unknown applications, and collisions among fixed, SurfGym, WavePool, Docker control, and application ports.

## Hybrid task surfaces

SurfGym supports up to four tiled browser surfaces in one task. `Website.surface`
declares how each surface integrates with the runtime:

- `web` receives SurfGym's generic page bridge and remains the default.
- `native` uses the bridge supplied by the Docker desktop gateway.
- Existing URLs on port `53001` are inferred as `native` for compatibility. A Docker
  gateway on any other port must declare `"surface": "native"` explicitly.

A task may contain at most one native surface. In a hybrid task, the native hostname
must differ from every web hostname because browser cookies are scoped by hostname,
not port. Use names such as `web.localhost` and `desktop.localhost`.

Task loading retargets and deduplicates the standard release hook for every surface:
web surfaces reset their state and the native surface acknowledges Docker slot reset.
Explicit nonstandard release hooks are preserved in addition to these lifecycle
defaults.

| Combination | Supported |
| --- | --- |
| One to four web surfaces | Yes |
| Web surfaces plus one Docker-native surface | Yes |
| Two Docker-native surfaces | No |
| Cross-surface screen and keyboard workflows | Yes |
| Cross-surface drag, shared filesystem, VM/OS backend | No |

The hybrid path intentionally reuses the existing allocate, observe, evaluate, and
release lifecycle. It does not introduce provider, VM, or capability abstractions.
