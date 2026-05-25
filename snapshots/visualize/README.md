# Snapshot Visualize

React-based viewer/editor for SurfGym snapshot runs.

## Run

```bash
cd snapshots/visualize
pnpm install
pnpm dev
```

Open `http://127.0.0.1:5177`.

The API reads snapshot runs from `snapshots/__snapshots__` and writes instruction edits to:

```text
packages/surfgym-task/src/surfgym_task/data/seed/spreadsheet/instruction.jsonc
```
