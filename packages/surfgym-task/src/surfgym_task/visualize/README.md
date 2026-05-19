# tasks/visualize

This folder captures screenshots for `tasks/seed/spreadsheet/out/augmented.json`
or, when that file is absent, `tasks/seed/spreadsheet/out/augmented.jsonc`.

## Install

```bash
cd tasks/visualize
pnpm install
pnpm run install:browsers
```

## Capture screenshots

Start the website used by the tasks first. For the current spreadsheet seed data,
the task website is `http://localhost:3000/spreadsheet`.

```bash
pnpm run capture
```

Useful options:

```bash
pnpm run capture -- --limit 2
pnpm run capture -- --only spreadsheet_bold_header_2
pnpm run capture -- --headed
pnpm run capture -- --settle 2000
pnpm run capture -- --viewport 1280x900
```

Screenshots are written to `screenshots/`, and viewer data is written to
`data/tasks.json`.

## View results

```bash
pnpm run view
```

Open the printed URL, then use `ArrowLeft` and `ArrowRight` to move through tasks.
