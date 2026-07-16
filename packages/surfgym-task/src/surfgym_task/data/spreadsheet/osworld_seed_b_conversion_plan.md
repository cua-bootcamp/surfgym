# OSWorld B-Grade Seed Conversion Implementation Plan

> **For agentic workers:** Execute inline in the current workspace. Do not create a worktree, commit, stage, or modify files outside `spreadsheet/seeds/` and `spreadsheet/reference/`.

**Goal:** Convert the 14 B-grade candidate tasks into pure OSWorld-equivalent seed JSON files, add them to `spreadsheet/seeds/`, and remove their 14 matched OSWorld references.

**Architecture:** Each seed remains a standalone `{empty_start, instruction, states}` JSON task. `states[0]` defines source data; later state groups define formulas, values, styles, charts, sheets, or pivot metadata. Existing task-state conventions are reused without changing evaluator code.

**Tech Stack:** JSON task fixtures, spreadsheet fixture metadata (`getCellMeta`, `getSheetMeta`, `getChartMeta`, `getPivotMeta`).

## Global Constraints

- Keep the existing 25 A-grade seed files unchanged.
- Overwrite the existing `create_total_growth_rates.json`; add the other 13 converted B-grade files.
- Use the existing B-grade filenames so the mapping document remains traceable.
- Do not add `_refine_*` variants.
- Delete exactly the 14 B-grade reference JSON files only after all converted seeds validate.
- Final counts must be 39 JSON files in `spreadsheet/seeds/` and 8 JSON files in `spreadsheet/reference/`.
- Every JSON file must parse and include non-empty `instruction` and `states` fields.

---

### Task 1: Convert calculation and chart seeds

**Files:**
- Modify: `spreadsheet/seeds/create_total_growth_rates.json`
- Create: `spreadsheet/seeds/calculate_product_prices.json`
- Create: `spreadsheet/seeds/calculate_profit_margin.json`
- Create: `spreadsheet/seeds/calculate_period_rate_percentage.json`
- Create: `spreadsheet/seeds/represent_values_in_thousands_and_millions.json`
- Create: `spreadsheet/seeds/fixed_decimal_values_in_text.json`
- Create: `spreadsheet/seeds/format_spent_column_two_decimal_places.json`
- Create: `spreadsheet/seeds/fill_employee_ids.json`
- Create: `spreadsheet/seeds/change_sunday_color.json`

- [ ] Replace each instruction and state set with the approved B-conversion design.
- [ ] Include formulas or exact result values for derived cells.
- [ ] Include both required charts, green maximum font, direct `0.00` formatting, sequence text, and Saturday/Sunday red fills.
- [ ] Parse all nine files with `jq empty`.

### Task 2: Convert sheet and pivot seeds

**Files:**
- Create: `spreadsheet/seeds/sheet_backup_copy_not_move.json`
- Create: `spreadsheet/seeds/pivot_promotion_summary_no_manual_values.json`
- Create: `spreadsheet/seeds/create_demographic_proportion_summary_tables.json`
- Create: `spreadsheet/seeds/calculate_revenue_and_summarize.json`
- Create: `spreadsheet/seeds/pivot_multi_summary_stacked.json`

- [ ] Encode expected sheet names and copied data for the LARS backup task.
- [ ] Encode promotion as a pivot column field with Revenue sum only.
- [ ] Encode three demographic percentage pivots, title value, title colors, and bold style.
- [ ] Encode cross-sheet retail price lookup plus a product revenue pivot.
- [ ] Encode Channel Revenue and Product Revenue pivots using Revenue sum for both.
- [ ] Parse all five files with `jq empty`.

### Task 3: Validate converted seeds

- [ ] Confirm the 14 expected filenames exist exactly once in `spreadsheet/seeds/`.
- [ ] Confirm task-specific metadata: two charts, five converted pivot tasks, new-sheet checks, style checks, and number formats.
- [ ] Confirm expected calculations and summary totals with an independent validation script.
- [ ] Confirm `spreadsheet/seeds/` contains 39 JSON files.

### Task 4: Remove matched references and perform final verification

**Files:**
- Delete the 14 B-grade reference JSON files listed in `osworld_seed_1to1_mapping.md`.

- [ ] Delete exactly the B-grade references.
- [ ] Confirm the remaining references equal the eight C-grade IDs.
- [ ] Confirm `spreadsheet/reference/` contains 8 JSON files.
- [ ] Parse all 47 remaining seed/reference JSON files.
