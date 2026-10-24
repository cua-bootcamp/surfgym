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

The shared fixture build is exposed as two origins so browser storage is isolated:

- Spreadsheet: `http://localhost:3000`
- Word: `http://localhost:3001`

`MAIN_PORT` can override Spreadsheet and `WORD_PORT` can override Word for a
direct fixture-only run. The official local stack keeps both fixed.

```bash
pnpm run serve
MAIN_PORT=5173 WORD_PORT=5174 pnpm run serve
```
