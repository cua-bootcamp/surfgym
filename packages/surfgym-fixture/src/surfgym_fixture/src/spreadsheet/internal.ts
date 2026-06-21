import { ChartTypeBits, SheetsChartService } from "@univerjs/presets/preset-sheets-advanced";
import type { FChart } from "@univerjs/presets/lib/types/preset-sheets-advanced/index.js";
import type { Path, Value } from "../external";
import { SpreadsheetRuntimeStore } from "./runtime";

type WorksheetLike = ReturnType<typeof resolveSheet>;
type ChartMetaGetter = (chart: FChart, index: number) => ChartMeta;
type InjectorLike = {
  get: <T>(token: unknown) => T;
};
type ChartWithInjector = {
  _injector?: InjectorLike;
};
type ChartModelLike = {
  chartType?: unknown;
  context?: unknown;
  dataSource?: unknown;
  style?: unknown;
};
type RangeLike = {
  startRow: number;
  endRow: number;
  startColumn: number;
  endColumn: number;
};

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

function isRecord(value: unknown): value is Record<PropertyKey, unknown> {
  return value !== null && typeof value === "object";
}

function resolveChart(charts: FChart[], chartRef?: ChartRef, getMeta?: ChartMetaGetter): FChart {
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
    if (
      chartRef.title !== undefined ||
      chartRef.sourceRange !== undefined ||
      chartRef.chartType !== undefined
    ) {
      if (!getMeta) return false;

      const meta = getMeta(chart, index);
      if (chartRef.title !== undefined && meta.title !== chartRef.title) return false;
      if (chartRef.sourceRange !== undefined && meta.sourceRange !== chartRef.sourceRange)
        return false;
      if (
        chartRef.chartType !== undefined &&
        meta.chartType !== normalizeChartType(chartRef.chartType)
      ) {
        return false;
      }
    }
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

function columnIndexToName(columnIndex: number) {
  let columnNumber = columnIndex + 1;
  let columnName = "";

  while (columnNumber > 0) {
    const remainder = (columnNumber - 1) % 26;
    columnName = String.fromCharCode(65 + remainder) + columnName;
    columnNumber = Math.floor((columnNumber - 1) / 26);
  }

  return columnName;
}

function selectionRangeToA1(range: RangeLike) {
  return [
    columnIndexToName(range.startColumn),
    range.startRow + 1,
    ":",
    columnIndexToName(range.endColumn),
    range.endRow + 1
  ].join("");
}

function getSelectionRangeFromUnknown(value: unknown): RangeLike | null {
  if (!isRecord(value)) return null;

  if (
    typeof value.startRow === "number" &&
    typeof value.endRow === "number" &&
    typeof value.startColumn === "number" &&
    typeof value.endColumn === "number"
  ) {
    return value as RangeLike;
  }

  if (isRecord(value.range)) return getSelectionRangeFromUnknown(value.range);

  return null;
}

function quoteSheetNameForA1(sheetName: string) {
  if (/^[A-Za-z_][A-Za-z0-9_]*$/.test(sheetName)) return sheetName;
  return `'${sheetName.replace(/'/g, "''")}'`;
}

function getSheetName(worksheet: WorksheetLike) {
  return worksheet.getSheetName?.() ?? worksheet.getSheet?.().getName?.() ?? null;
}

function getSheetNameById(sheetId: string) {
  const { workbook } = SpreadsheetRuntimeStore.runtime;
  const sheet = workbook.getSheetBySheetId?.(sheetId);

  return sheet ? getSheetName(sheet) : null;
}

function formatChartRangeItemA1(value: unknown, chartSheetId: string | null) {
  if (!isRecord(value)) return null;

  const range = getSelectionRangeFromUnknown(value.range);
  if (!range) return null;

  const rangeA1 = selectionRangeToA1(range);
  const sourceSheetId = typeof value.subUnitId === "string" ? value.subUnitId : null;
  if (!sourceSheetId || !chartSheetId || sourceSheetId === chartSheetId) return rangeA1;

  const sourceSheetName = getSheetNameById(sourceSheetId);
  return sourceSheetName ? `${quoteSheetNameForA1(sourceSheetName)}!${rangeA1}` : rangeA1;
}

function getChartSourceRangeA1(chartRange: unknown, chartSheetId: string | null) {
  if (Array.isArray(chartRange)) {
    const ranges = chartRange
      .flatMap((rangePair) => (Array.isArray(rangePair) ? rangePair : [rangePair]))
      .map((rangeItem) => formatChartRangeItemA1(rangeItem, chartSheetId))
      .filter((rangeItem): rangeItem is string => typeof rangeItem === "string");

    return ranges.length > 0 ? ranges.join(",") : null;
  }

  if (isRecord(chartRange) && isRecord(chartRange.rangeInfo)) {
    return formatChartRangeItemA1(chartRange.rangeInfo, chartSheetId);
  }

  const range = getSelectionRangeFromUnknown(chartRange);
  return range ? selectionRangeToA1(range) : null;
}

function readPath(value: unknown, path: PropertyKey[]): unknown {
  let current = value;

  for (const key of path) {
    if (!isRecord(current)) return undefined;
    current = current[key];
  }

  return current;
}

function readString(value: unknown) {
  return typeof value === "string" ? value : null;
}

function readNumber(value: unknown) {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function normalizeChartType(chartType: unknown) {
  if (typeof chartType === "string") return chartType.trim().toLowerCase();

  switch (chartType) {
    case ChartTypeBits.Line:
      return "line";
    case ChartTypeBits.Column:
      return "column";
    case ChartTypeBits.Bar:
      return "bar";
    case ChartTypeBits.Area:
      return "area";
    case ChartTypeBits.Pie:
      return "pie";
    case ChartTypeBits.Doughnut:
      return "doughnut";
    case ChartTypeBits.Scatter:
      return "scatter";
    case ChartTypeBits.Bubble:
      return "bubble";
    case ChartTypeBits.Radar:
      return "radar";
    default:
      return chartType ?? null;
  }
}

function getChartModel(chart: FChart): ChartModelLike | null {
  const chartId = chart.getChartId?.();
  const injector = (chart as unknown as ChartWithInjector)._injector;
  if (!chartId || typeof injector?.get !== "function") return null;

  try {
    const service = injector.get<SheetsChartService>(SheetsChartService);
    return service.getChartModel(chartId) ?? null;
  } catch {
    return null;
  }
}

function getChartModelRange(model: ChartModelLike | null) {
  const dataSource = model?.dataSource;
  const getRangeInfo = isRecord(dataSource) ? dataSource.getRangeInfo : undefined;

  return typeof getRangeInfo === "function" ? getRangeInfo.call(dataSource) : null;
}

function getDataOrientation(range: unknown, style: unknown) {
  if (isRecord(range) && typeof range.isRowDirection === "boolean") {
    return range.isRowDirection ? "Row" : "Column";
  }

  const orient = readPath(style, ["orient"]);
  return typeof orient === "string" ? orient : null;
}

export function _getCellMeta(sheetRef: SheetRef | undefined, cellRefStr: string) {
  const worksheet = resolveSheet(sheetRef);
  const cellRef = resolveCell(cellRefStr);
  const range = worksheet.getRange(cellRef.row, cellRef.column);
  const data = worksheet.getSheet().getCellRaw(cellRef.row, cellRef.column) ?? {};
  const style = range.getCellStyleData("cell") ?? {};

  return { ...data, s: style };
}

export function _setCellMeta(
  sheetRef: SheetRef | undefined,
  cellRefStr: string,
  path: Path[],
  value: Value
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

  const last = path[path.length - 1] as Path;
  target[last] = value;
  range.setValueForCell(data);
}

export function _getSheetMeta(sheetRef?: SheetRef) {
  const worksheet = resolveSheet(sheetRef);
  const { workbook } = SpreadsheetRuntimeStore.runtime;
  const sheets = workbook.getSheets?.() ?? [];

  return {
    id: worksheet.getSheetId?.() ?? null,
    name: getSheetName(worksheet),
    index: sheets.indexOf(worksheet)
  };
}

function buildChartMeta(worksheet: WorksheetLike, charts: FChart[], chart: FChart): ChartMeta {
  const sheetId = worksheet.getSheetId?.() ?? null;
  const model = getChartModel(chart);
  const style = model?.style;
  const range = getChartModelRange(model) ?? chart.getRange?.() ?? null;

  return {
    id: chart.getChartId?.() ?? null,
    sheetId,
    sheetName: getSheetName(worksheet),
    index: charts.indexOf(chart),
    chartType: normalizeChartType(model?.chartType),
    sourceRange: getChartSourceRangeA1(range, sheetId),
    range,
    title: readString(readPath(style, ["titles", "title", "content"])),
    xAxisTitle: readString(readPath(style, ["titles", "xAxisTitle", "content"])),
    yAxisTitle: readString(readPath(style, ["titles", "yAxisTitle", "content"])),
    legendPosition: readPath(style, ["legend", "position"]) ?? null,
    dataOrientation: getDataOrientation(range, style),
    width: readNumber(readPath(style, ["width"])),
    height: readNumber(readPath(style, ["height"])),
    position: null,
    context: model?.context ?? null,
    seriesData: chart.getSeriesData?.() ?? null,
    categoryData: chart.getCategoryData?.() ?? null
  };
}

export function _getChartMeta(sheetRef?: SheetRef, chartRef?: ChartRef) {
  const worksheet = resolveSheet(sheetRef);
  const charts = worksheet.getCharts() ?? [];
  const chart = resolveChart(charts, chartRef, (item) => buildChartMeta(worksheet, charts, item));

  return buildChartMeta(worksheet, charts, chart);
}

export type SheetRef = string | number;
export type CellRef = {
  row: number;
  column: number;
};
export type ChartRef =
  | number
  | {
      index?: number;
      id?: string;
      title?: string;
      sourceRange?: string;
      chartType?: unknown;
    };

// ######################################
// #                Meta                #
// ######################################

export type ChartMeta = {
  id: string | null;
  sheetId: string | null;
  sheetName: string | null;
  index: number;
  chartType: unknown;
  sourceRange: string | null;
  range: unknown;
  title: string | null;
  xAxisTitle: string | null;
  yAxisTitle: string | null;
  legendPosition: unknown;
  dataOrientation: unknown;
  width: number | null;
  height: number | null;
  position: unknown;
  context: unknown;
  seriesData: unknown;
  categoryData: unknown;
};
