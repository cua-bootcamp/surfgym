## Setting

```bash
git clone https://github.com/cua-bootcamp/websites
cd websites

git submodule update --init --recursive
pnpm i
cd prozilla-os
pnpm i

cd ..

pnpm run build
```

## caddy

### For mac

```bash
brew install caddy # for mac
```

### For Linux (Ubuntu/Debian)

### For window

1. Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
2. irm get.scoop.sh | iex

bash 3. scoop install caddy 4. caddy version
4-1. bash에서 caddy가 안뜨면
export PATH="$PATH:$HOME/scoop/shims" 이후 다시 한 번 caddy version

## Start

The default port is for main and prozilla is respectively `3000` and `3100`.

```bash
pnpm run serve
# or
MAIN_PORT=5173 PROZILLA_PORT=5174 pnpm run serve
```
