import type { SheetRef, ChartRef, SpreadsheetRuntime, PathPart, JsonValue } from "./type";
import type { FChart } from "@univerjs/presets/lib/types/preset-sheets-advanced/index.js";

export class SpreadsheetRuntimeStore {
  private static _runtime: SpreadsheetRuntime | null = null;

  static set runtime(runtime: SpreadsheetRuntime) {
    SpreadsheetRuntimeStore._runtime = runtime;
  }

  static get runtime(): SpreadsheetRuntime {
    if (!SpreadsheetRuntimeStore._runtime) {
      throw new Error("Spreadsheet get runtime is not installed.");
    }

    return SpreadsheetRuntimeStore._runtime;
  }
}

function resolveSheet(sheetRef?: SheetRef) {
  const { workbook, defaultWorksheet } = SpreadsheetRuntimeStore.runtime;

  if (sheetRef === undefined) return defaultWorksheet;

  if (typeof sheetRef === "string") {
    const sheet = workbook.getSheetByName?.(sheetRef) ?? workbook.getSheetBySheetId?.(sheetRef);
    if (!sheet) throw new Error(`Sheet not found: ${sheetRef}`);
    return sheet;
  }

  const sheet = workbook.getSheets?.()[sheetRef];
  if (!sheet) throw new Error(`Sheet not found: index=${sheetRef}`);
  return sheet;
}

function resolveChart(charts: FChart[], chartRef?: ChartRef): FChart {
  if (chartRef === undefined) {
    if (charts.length !== 1) throw new Error(`Expected exactly one chart, found ${charts.length}.`);
    return charts[0]!;
  }

  if (typeof chartRef === "number") {
    const chart = charts[chartRef];
    if (!chart) throw new Error(`Chart not found: index=${chartRef}`);
    return chart;
  }

  const matched = charts.filter((chart, index) => {
    if (chartRef.index !== undefined && chartRef.index !== index) return false;
    if (chartRef.id !== undefined && chart.getChartId?.() !== chartRef.id) return false;
    return true;
  });

  if (matched.length !== 1)
    throw new Error(`Expected exactly one matching chart, found ${matched.length}.`);
  return matched[0]!;
}

function resolveCell(address: string) {
  const match = address.trim().match(/^\$?([A-Z]+)\$?(\d+)$/i);
  if (!match) throw new Error(`Invalid cell address: ${address}`);

  const [, columnName, rowName] = match;
  if (!columnName || !rowName) throw new Error(`Invalid cell address: ${address}`);

  return {
    row: Number(rowName) - 1,
    column:
      columnName
        .toUpperCase()
        .split("")
        .reduce((sum, char) => sum * 26 + char.charCodeAt(0) - 64, 0) - 1
  };
}

export function _getCellMeta(sheetRef: SheetRef, cellRefStr: string) {
  const worksheet = resolveSheet(sheetRef);
  const cellRef = resolveCell(cellRefStr);
  const range = worksheet.getRange(cellRef.row, cellRef.column);
  const data = worksheet.getSheet().getCellRaw(cellRef.row, cellRef.column) ?? {};
  const style = range.getCellStyleData("cell") ?? {};

  return { ...data, s: style };
}

export function _setCellMeta(
  sheetRef: SheetRef,
  cellRefStr: string,
  path: PathPart[],
  value: JsonValue
) {
  const worksheet = resolveSheet(sheetRef);
  const cellRef = resolveCell(cellRefStr);
  const range = worksheet.getRange(cellRef.row, cellRef.column);

  const data = range.getCellData() ?? {};
  let target = data as Record<PropertyKey, unknown>;

  for (const key of path.slice(0, -1)) {
    if (target[key] == null || typeof target[key] !== "object") target[key] = {};
    target = target[key] as Record<PropertyKey, unknown>;
  }

  const last = path[path.length - 1] as PathPart;
  target[last] = value;
  range.setValueForCell(data);
}

export function _getChartMeta(sheetRef: SheetRef, chartRef?: ChartRef): unknown {
  const worksheet = resolveSheet(sheetRef);
  const charts = worksheet.getCharts() ?? [];
  const chart = resolveChart(charts, chartRef);

  return {
    id: chart.getChartId?.() ?? null,
    sheetId: worksheet.getSheetId?.() ?? null,
    sheetName: worksheet.getSheetName?.() ?? worksheet.getSheet?.().getName?.() ?? null,
    index: charts.indexOf(chart)
  };
}
