import type { CellMeta, SheetRef, SpreadsheetRuntime, ChartMeta, ChartRef } from "./type";
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

export function _getCellMeta(sheetRef: SheetRef, cellRefStr: string): CellMeta {
  const worksheet = resolveSheet(sheetRef);
  const cellRef = resolveCell(cellRefStr);
  const range = worksheet.getRange(cellRef.row, cellRef.column);

  return {
    cell: clonePlainValue(range.getCellData()),
    style: clonePlainValue(range.getCellStyleData("cell"))
  };
}

export function _getChartMeta(sheetRef: SheetRef, chartRef?: ChartRef): ChartMeta {
  const worksheet = resolveSheet(sheetRef);
  const charts = worksheet.getCharts() ?? [];
  const chart = resolveChart(charts, chartRef);
  const range = chart.getRange?.() ?? null;

  return clonePlainValue({
    id: chart.getChartId?.() ?? null,
    sheetId: worksheet.getSheetId?.() ?? null,
    sheetName: worksheet.getSheetName?.() ?? worksheet.getSheet?.().getName?.() ?? null,
    index: charts.indexOf(chart),
    chartType: null,
    // sourceRange: getChartSourceRangeA1(range),
    range: clonePlainValue(range),
    title: null,
    legendPosition: null,
    dataOrientation: null,
    width: null,
    height: null,
    position: null,
    context: null,
    seriesData: clonePlainValue(chart.getSeriesData?.() ?? null),
    categoryData: clonePlainValue(chart.getCategoryData?.() ?? null)
  });
}

function clonePlainValue<T>(value: T): T {
  if (value == null) return value;

  const json = JSON.stringify(value);
  if (json === undefined) return value;

  return JSON.parse(json) as T;
}
