// @vitest-environment node

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { mergeChartSourceMatrixInfo, splitChartSourceRanges } from "./chart-range";

type StateAtom = { spec?: { kind?: string; property?: string }; value?: unknown };

const TRACKED_SPREADSHEET_SEED_FILES = [
  "add_warehouse_throughput_sparklines.json",
  "annual_change_rate.json",
  "assign_kiln_load_tags.json",
  "backup_and_modify_sheets.json",
  "calculate_campaign_net_funds.json",
  "calculate_column_sum.json",
  "calculate_hired_year.json",
  "calculate_permit_expiration_dates.json",
  "calculate_probe_drift_per_check.json",
  "calculate_total_parking_fee.json",
  "chart_chronological_dispatch_volume.json",
  "chart_monthly_library_circulation.json",
  "collect_redundant_species.json",
  "complete_climate_chamber_run_summaries.json",
  "complete_fleet_inspection_rollups.json",
  "copy_column_to_new_sheet.json",
  "create_volunteer_coverage_header.json",
  "fill_down_warehouse_inspection_labels.json",
  "format_unit_price_two_decimals.json",
  "hide_unavailable_inventory_audit_rows.json",
  "highlight_weekend_clinic_dates.json",
  "reorder_shipment_columns.json",
  "sort_purchase_orders_by_total_cost.json",
  "standardize_meter_ids.json",
  "standardize_workshop_display_names.json",
  "summarize_monthly_support_tickets.json",
  "unpack_tag.json",
  "zoom_out_equipment_register.json",
] as const;

function collectSeedAtoms(value: unknown): StateAtom[] {
  if (Array.isArray(value)) return value.flatMap(collectSeedAtoms);
  if (!value || typeof value !== "object") return [];

  const record = value as Record<string, unknown>;
  const atom = record.spec && typeof record.spec === "object" ? [record as StateAtom] : [];
  return [...atom, ...Object.values(record).flatMap(collectSeedAtoms)];
}

describe("current chart and sparkline inventory", () => {
  it("requires only line types from tracked Spreadsheet seed atoms", () => {
    const seedDirectory = join(process.cwd(), "../../../surfgym-task/src/surfgym_task/data/spreadsheet/seeds");
    const types = TRACKED_SPREADSHEET_SEED_FILES
      .flatMap((name) => collectSeedAtoms(JSON.parse(readFileSync(join(seedDirectory, name), "utf8"))))
      .filter(({ spec }) =>
        (spec?.kind === "chart" && spec.property === "chartType") ||
        (spec?.kind === "sparkline" && spec.property === "type"),
      )
      .map(({ value }) => value);

    expect(types).not.toHaveLength(0);
    expect([...new Set(types)]).toEqual(["line"]);
  });
});

describe("existing chart multi-range helper", () => {
  it("stacks equally wide ranges and marks column direction", () => {
    expect(mergeChartSourceMatrixInfo([[["Jan", 1]], [["Feb", 2]]])).toEqual({
      isRowDirection: false,
      matrix: [["Jan", 1], ["Feb", 2]],
    });
  });

  it("joins equally tall ranges side-by-side and marks row direction", () => {
    expect(mergeChartSourceMatrixInfo([[["Jan"], ["Feb"]], [[1], [2]]])).toEqual({
      isRowDirection: true,
      matrix: [["Jan", 1], ["Feb", 2]],
    });
  });

  it("keeps commas inside quoted sheet names within one source segment", () => {
    expect(splitChartSourceRanges("'Q1, Q2'!A1:B2, Sheet2!C1:D2")).toEqual([
      "'Q1, Q2'!A1:B2",
      "Sheet2!C1:D2",
    ]);
  });
});
