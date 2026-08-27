# SurfGym fixture server

## Setup

Install dependencies and build the fixture distribution:

```bash
pnpm install
pnpm run build
```

## Caddy

The fixture server uses Caddy to serve the generated `dist` directory.

### macOS

```bash
brew install caddy
```

### Windows

Install Caddy with Scoop and verify that it is on `PATH`:

```powershell
scoop install caddy
caddy version
```

### Linux

Install Caddy using the package instructions for your distribution, then verify
it with `caddy version`.

## Start

The default fixture port is `3000`. Override it with `MAIN_PORT` when needed:

```bash
pnpm run serve
MAIN_PORT=5173 pnpm run serve
```
