import { ChartTypeBits, SheetsChartService } from "@univerjs/presets/preset-sheets-advanced";
import { checkCellValueType, type FWorksheet } from "@univerjs/preset-sheets-core";
import type { FChart } from "@univerjs/presets/lib/types/preset-sheets-advanced/index.js";
import type { Path, Value } from "../external";
import { SpreadsheetRuntimeStore } from "./runtime";

type WorksheetLike = FWorksheet;
const chartUpdateConfigCommandId = "sheet.command.chart-update-config";

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
type ResolveSheetOptions = {
  create?: boolean;
};
type WorkbookWithSheetMutation = {
  getSheets?: () => WorksheetLike[];
  getSheetByName?: (sheetName: string) => WorksheetLike | null | undefined;
  getSheetBySheetId?: (sheetId: string) => WorksheetLike | null | undefined;
  insertSheet?: (name?: string, options?: { index?: number }) => WorksheetLike;
  moveSheet?: (sheet: WorksheetLike, index: number) => unknown;
};
type ChartBuilderLike = {
  setChartType: (chartType: ChartTypeBits) => ChartBuilderLike;
  addRange: (range: string) => ChartBuilderLike;
  setPosition: (row: number, column: number, offsetX: number, offsetY: number) => ChartBuilderLike;
  setWidth: (width: number) => ChartBuilderLike;
  setHeight: (height: number) => ChartBuilderLike;
  setOptions: (path: string, value: unknown) => ChartBuilderLike;
  setTransposeRowsAndColumns?: (transposeRowsAndColumns: boolean) => ChartBuilderLike;
  setXAxisTitle?: (title: string) => ChartBuilderLike;
  setYAxisTitle?: (title: string) => ChartBuilderLike;
  build: () => unknown;
};
type WorksheetWithCharts = WorksheetLike & {
  getCharts?: () => FChart[];
  newChart?: () => ChartBuilderLike;
  insertChart?: (chartInfo: unknown) => Promise<unknown> | unknown;
  setName?: (name: string) => unknown;
  getMaxColumns?: () => number;
};
type ChartRuntimeConfig = {
  unitId: string;
  chartModelId: string;
  chartType?: ChartTypeBits;
  style?: Record<string, unknown>;
  context?: unknown;
};

const chartMetaRegistry: ChartMeta[] = [];

function getWorkbookSheets() {
  const { workbook, defaultWorksheet } = SpreadsheetRuntimeStore.runtime;
  const sheets = workbook.getSheets?.() ?? [];
  const defaultSheetId = defaultWorksheet.getSheetId?.();

  return sheets.some((sheet) => sheet.getSheetId?.() === defaultSheetId)
    ? sheets
    : [defaultWorksheet, ...sheets];
}

function resolveSheet(sheetRef?: SheetRef, options: ResolveSheetOptions = {}) {
  const { workbook, defaultWorksheet } = SpreadsheetRuntimeStore.runtime;
  const workbookWithSheets = workbook as unknown as WorkbookWithSheetMutation;
  const sheets = getWorkbookSheets();

  if (sheetRef === undefined) return defaultWorksheet;

  if (typeof sheetRef === "string") {
    const sheet =
      sheets.find((item) => getSheetName(item) === sheetRef || item.getSheetId?.() === sheetRef) ??
      workbookWithSheets.getSheetByName?.(sheetRef) ??
      workbookWithSheets.getSheetBySheetId?.(sheetRef);

    if (!sheet && options.create && typeof workbookWithSheets.insertSheet === "function") {
      return workbookWithSheets.insertSheet(sheetRef);
    }

    if (!sheet) throw new Error(`Sheet not found: ${sheetRef}`);
    return sheet;
  }

  if (!Number.isInteger(sheetRef) || sheetRef < 0) {
    throw new Error(`Invalid sheet index: ${sheetRef}`);
  }

  const sheet = sheets[sheetRef];
  if (
    !sheet &&
    options.create &&
    sheetRef === sheets.length &&
    typeof workbookWithSheets.insertSheet === "function"
  ) {
    return workbookWithSheets.insertSheet();
  }

  if (!sheet) throw new Error(`Sheet not found: index=${sheetRef}`);
  return sheet;
}

function activateSheetAfterExplicitSet(sheetRef: SheetRef | undefined, worksheet: WorksheetLike) {
  if (sheetRef === undefined) return;

  SpreadsheetRuntimeStore.runtime.workbook.setActiveSheet(worksheet);
}

function isRecord(value: unknown): value is Record<PropertyKey, unknown> {
  return value !== null && typeof value === "object";
}

function isCellValue(value: Value): value is string | number | boolean {
  return typeof value === "string" || typeof value === "number" || typeof value === "boolean";
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

function resolveCellRange(address: string): RangeLike {
  const parts = address.trim().split(":");
  if (parts.length < 1 || parts.length > 2) {
    throw new Error(`Invalid cell range address: ${address}`);
  }

  const startAddress = parts[0];
  const endAddress = parts[1] ?? startAddress;
  if (!startAddress || !endAddress) {
    throw new Error(`Invalid cell range address: ${address}`);
  }

  const start = resolveCell(startAddress);
  const end = resolveCell(endAddress);

  return {
    startRow: Math.min(start.row, end.row),
    endRow: Math.max(start.row, end.row),
    startColumn: Math.min(start.column, end.column),
    endColumn: Math.max(start.column, end.column)
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

function readFirstString(value: unknown, paths: PropertyKey[][]) {
  for (const path of paths) {
    const pathValue = readString(readPath(value, path));
    if (pathValue !== null) return pathValue;
  }

  return null;
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

function resolveChartTypeBits(chartType: unknown, fallback = ChartTypeBits.Column): ChartTypeBits {
  if (chartType == null) return fallback;
  if (typeof chartType === "number") return chartType as ChartTypeBits;

  switch (normalizeChartType(chartType)) {
    case "line":
      return ChartTypeBits.Line;
    case "column":
      return ChartTypeBits.Column;
    case "bar":
      return ChartTypeBits.Bar;
    case "area":
      return ChartTypeBits.Area;
    case "pie":
      return ChartTypeBits.Pie;
    case "doughnut":
      return ChartTypeBits.Doughnut;
    case "scatter":
      return ChartTypeBits.Scatter;
    case "bubble":
      return ChartTypeBits.Bubble;
    case "radar":
      return ChartTypeBits.Radar;
    default:
      throw new Error(`Unsupported chart type: ${String(chartType)}`);
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

function writePath(target: Record<PropertyKey, unknown>, path: Path[], value: unknown) {
  if (path.length === 0) throw new Error("Path must not be empty.");

  let current = target;
  for (const key of path.slice(0, -1)) {
    if (!isRecord(current[key])) current[key] = {};
    current = current[key] as Record<PropertyKey, unknown>;
  }

  current[path[path.length - 1]!] = value;
}

function writeStringPath(target: Record<string, unknown>, path: string[], value: unknown) {
  if (value === undefined || value === null || value === "") return;

  let current = target;
  for (const key of path.slice(0, -1)) {
    if (!isRecord(current[key])) current[key] = {};
    current = current[key] as Record<string, unknown>;
  }

  current[path[path.length - 1]!] = value;
}

function normalizeChartSetValue(path: Path[], value: Value) {
  const last = path[path.length - 1];

  if (last === "chartType") return normalizeChartType(value);
  if (last === "sourceRange" && typeof value === "string") return value.trim();
  if (
    (last === "title" || last === "xAxisTitle" || last === "yAxisTitle") &&
    typeof value === "string"
  ) {
    return value.trim();
  }

  return value;
}

function getChartId(chart: unknown) {
  if (!isRecord(chart)) return null;

  const getChartIdMethod = chart.getChartId;
  if (typeof getChartIdMethod !== "function") return null;

  const id = getChartIdMethod.call(chart);
  return typeof id === "string" ? id : null;
}

function getWorksheetCharts(worksheet: WorksheetLike): FChart[] {
  const getCharts = (worksheet as WorksheetWithCharts).getCharts;
  if (typeof getCharts !== "function") return [];

  try {
    const charts = getCharts.call(worksheet);
    return Array.isArray(charts) ? charts : [];
  } catch {
    return [];
  }
}

function mergeChartMeta(base: ChartMeta, registered?: ChartMeta): ChartMeta {
  if (!registered) return base;

  return {
    ...base,
    chartType: registered.chartType ?? base.chartType,
    sourceRange: registered.sourceRange ?? base.sourceRange,
    range: registered.range ?? base.range,
    title: registered.title ?? base.title,
    xAxisTitle: registered.xAxisTitle ?? base.xAxisTitle,
    yAxisTitle: registered.yAxisTitle ?? base.yAxisTitle,
    legendPosition: registered.legendPosition ?? base.legendPosition,
    dataOrientation: registered.dataOrientation ?? base.dataOrientation,
    width: registered.width ?? base.width,
    height: registered.height ?? base.height,
    position: registered.position ?? base.position,
    context: registered.context ?? base.context,
    seriesData: registered.seriesData ?? base.seriesData,
    categoryData: registered.categoryData ?? base.categoryData
  };
}

function getChartMetasForWorksheet(worksheet: WorksheetLike) {
  const sheetId = worksheet.getSheetId?.() ?? null;
  const charts = getWorksheetCharts(worksheet);
  const registeredForSheet = chartMetaRegistry.filter((item) => item.sheetId === sheetId);
  const registeredById = new Map(
    registeredForSheet
      .filter((item) => item.id)
      .map((item) => [item.id, item] as [string, ChartMeta])
  );
  const actualMetas = charts.map((chart) =>
    mergeChartMeta(
      buildChartMeta(worksheet, charts, chart),
      registeredById.get(chart.getChartId?.() ?? "")
    )
  );
  const actualIds = new Set(actualMetas.map((item) => item.id).filter(Boolean));
  const registeredOnly = registeredForSheet.filter((item) => !item.id || !actualIds.has(item.id));

  return [...actualMetas, ...registeredOnly].map((item, index) => ({ ...item, index }));
}

function chartMetaMatches(meta: ChartMeta, index: number, chartRef: ChartRef) {
  if (typeof chartRef === "number") return index === chartRef || meta.index === chartRef;

  if (chartRef.index !== undefined && chartRef.index !== index && chartRef.index !== meta.index)
    return false;
  if (chartRef.id !== undefined && meta.id !== chartRef.id) return false;
  if (chartRef.title !== undefined && meta.title !== chartRef.title) return false;
  if (chartRef.sourceRange !== undefined && meta.sourceRange !== chartRef.sourceRange) return false;
  if (
    chartRef.chartType !== undefined &&
    meta.chartType !== normalizeChartType(chartRef.chartType)
  ) {
    return false;
  }

  return true;
}

function findMatchingChartMetas(chartMetas: ChartMeta[], chartRef?: ChartRef) {
  if (chartRef === undefined) return chartMetas;

  return chartMetas.filter((meta, index) => chartMetaMatches(meta, index, chartRef));
}

function resolveChartMeta(chartMetas: ChartMeta[], chartRef?: ChartRef) {
  const matched = findMatchingChartMetas(chartMetas, chartRef);

  if (matched.length !== 1)
    throw new Error(`Expected exactly one matching chart, found ${matched.length}.`);

  return matched[0]!;
}

function createChartMeta(worksheet: WorksheetLike, chartRef?: ChartRef): ChartMeta {
  const sheetId = worksheet.getSheetId?.() ?? null;
  const chartRefRecord = isRecord(chartRef) ? chartRef : {};
  const index =
    typeof chartRef === "number" ? chartRef : getChartMetasForWorksheet(worksheet).length;
  const chartType =
    chartRefRecord.chartType !== undefined ? normalizeChartType(chartRefRecord.chartType) : null;

  return {
    id: typeof chartRefRecord.id === "string" ? chartRefRecord.id : null,
    sheetId,
    sheetName: getSheetName(worksheet),
    index,
    chartType,
    sourceRange:
      typeof chartRefRecord.sourceRange === "string" ? chartRefRecord.sourceRange.trim() : null,
    range: null,
    title: typeof chartRefRecord.title === "string" ? chartRefRecord.title.trim() : null,
    xAxisTitle: null,
    yAxisTitle: null,
    legendPosition: null,
    dataOrientation: null,
    width: null,
    height: null,
    position: null,
    context: null,
    seriesData: null,
    categoryData: null
  };
}

function upsertChartMeta(meta: ChartMeta) {
  let existingIndex = -1;

  if (meta.id) {
    existingIndex = chartMetaRegistry.findIndex(
      (item) => item.sheetId === meta.sheetId && item.id === meta.id
    );
  }

  if (existingIndex < 0 && meta.sourceRange) {
    existingIndex = chartMetaRegistry.findIndex(
      (item) => item.sheetId === meta.sheetId && item.sourceRange === meta.sourceRange
    );
  }

  if (existingIndex < 0 && meta.title) {
    existingIndex = chartMetaRegistry.findIndex(
      (item) => item.sheetId === meta.sheetId && item.title === meta.title
    );
  }

  if (existingIndex >= 0) {
    Object.assign(chartMetaRegistry[existingIndex]!, meta);
  } else {
    chartMetaRegistry.push(meta);
  }
}

function getMutableChartMeta(worksheet: WorksheetLike, chartRef?: ChartRef) {
  const sheetId = worksheet.getSheetId?.() ?? null;
  const registeredMatches = findMatchingChartMetas(
    chartMetaRegistry.filter((item) => item.sheetId === sheetId),
    chartRef
  );

  if (registeredMatches.length === 1) return registeredMatches[0]!;
  if (registeredMatches.length > 1)
    throw new Error(
      `Expected exactly one matching registered chart, found ${registeredMatches.length}.`
    );

  const existingMatches = findMatchingChartMetas(getChartMetasForWorksheet(worksheet), chartRef);
  if (existingMatches.length > 1)
    throw new Error(`Expected exactly one matching chart, found ${existingMatches.length}.`);

  const meta = existingMatches[0]
    ? { ...existingMatches[0] }
    : createChartMeta(worksheet, chartRef);
  upsertChartMeta(meta);

  return meta;
}

function readPositiveNumber(value: unknown, fallback: number) {
  return typeof value === "number" && Number.isFinite(value) && value > 0 ? value : fallback;
}

function getChartPosition(meta: ChartMeta, worksheet: WorksheetWithCharts) {
  const position = isRecord(meta.position) ? meta.position : {};
  const maxColumns =
    typeof worksheet.getMaxColumns === "function" ? Math.max(1, worksheet.getMaxColumns()) : 2;

  return {
    row: readNumber(position.row) ?? 0,
    column: readNumber(position.column) ?? Math.min(1, maxColumns - 1),
    offsetX: readNumber(position.offsetX) ?? 20,
    offsetY: readNumber(position.offsetY) ?? 20
  };
}

function setChartOption(builder: ChartBuilderLike, path: string, value: unknown) {
  if (value === undefined || value === null || value === "") return builder;

  return builder.setOptions(path, value);
}

function applyChartBuilderOptions(builder: ChartBuilderLike, meta: ChartMeta) {
  let nextBuilder = setChartOption(builder, "title.content", meta.title);
  nextBuilder = setChartOption(nextBuilder, "legend.position", meta.legendPosition);
  nextBuilder = setChartOption(nextBuilder, "orient", meta.dataOrientation);

  if (typeof meta.xAxisTitle === "string" && meta.xAxisTitle && nextBuilder.setXAxisTitle) {
    nextBuilder = nextBuilder.setXAxisTitle(meta.xAxisTitle);
  }

  if (typeof meta.yAxisTitle === "string" && meta.yAxisTitle && nextBuilder.setYAxisTitle) {
    nextBuilder = nextBuilder.setYAxisTitle(meta.yAxisTitle);
  }

  return nextBuilder;
}

function buildChartStyle(meta: ChartMeta) {
  const style: Record<string, unknown> = {};

  writeStringPath(style, ["title", "content"], meta.title);
  writeStringPath(style, ["titles", "title", "content"], meta.title);
  writeStringPath(style, ["xAxisTitle", "content"], meta.xAxisTitle);
  writeStringPath(style, ["titles", "xAxisTitle", "content"], meta.xAxisTitle);
  writeStringPath(style, ["yAxisTitle", "content"], meta.yAxisTitle);
  writeStringPath(style, ["titles", "yAxisTitle", "content"], meta.yAxisTitle);
  writeStringPath(style, ["legend", "position"], meta.legendPosition);
  writeStringPath(style, ["orient"], meta.dataOrientation);

  return style;
}

async function updateChartRuntimeConfig(meta: ChartMeta) {
  if (!meta.id) return;

  const { workbook, univerAPI } = SpreadsheetRuntimeStore.runtime;
  const style = buildChartStyle(meta);
  const params: ChartRuntimeConfig = {
    unitId: workbook.getId(),
    chartModelId: meta.id
  };

  if (meta.chartType != null) params.chartType = resolveChartTypeBits(meta.chartType);
  if (Object.keys(style).length > 0) params.style = style;
  if (meta.context !== null) params.context = meta.context;

  await univerAPI.executeCommand(chartUpdateConfigCommandId, params);
}

async function syncChartMetaToWorksheet(worksheet: WorksheetLike, meta: ChartMeta) {
  const worksheetWithCharts = worksheet as WorksheetWithCharts;

  if (meta.id) {
    try {
      await updateChartRuntimeConfig(meta);
    } catch {
      // Registry-backed evaluation should still work if visual chart update is unavailable.
    }
    return;
  }

  if (
    !meta.sourceRange ||
    meta.chartType == null ||
    typeof worksheetWithCharts.newChart !== "function" ||
    typeof worksheetWithCharts.insertChart !== "function"
  ) {
    return;
  }

  try {
    const position = getChartPosition(meta, worksheetWithCharts);
    const width = readPositiveNumber(meta.width, 560);
    const height = readPositiveNumber(meta.height, 360);
    let builder: ChartBuilderLike = worksheetWithCharts
      .newChart()
      .setChartType(resolveChartTypeBits(meta.chartType))
      .addRange(meta.sourceRange)
      .setPosition(position.row, position.column, position.offsetX, position.offsetY)
      .setWidth(width)
      .setHeight(height);

    builder = applyChartBuilderOptions(builder, meta);

    const insertedChart = await worksheetWithCharts.insertChart(builder.build());
    const id = getChartId(insertedChart);

    if (id) {
      meta.id = id;
      meta.range = (insertedChart as FChart | undefined)?.getRange?.() ?? meta.range;
      meta.seriesData = (insertedChart as FChart | undefined)?.getSeriesData?.() ?? meta.seriesData;
      meta.categoryData =
        (insertedChart as FChart | undefined)?.getCategoryData?.() ?? meta.categoryData;
      upsertChartMeta(meta);
      await updateChartRuntimeConfig(meta);
    }
  } catch {
    // Some chart APIs are unavailable on headless/older worksheet facades; keep meta for evaluation.
  }
}

export function _getCellMeta(sheetRef: SheetRef | undefined, cellRefStr: string) {
  const worksheet = resolveSheet(sheetRef);
  const cellRef = resolveCell(cellRefStr);
  const range = worksheet.getRange(cellRef.row, cellRef.column);
  const data = worksheet.getSheet().getCellRaw(cellRef.row, cellRef.column) ?? {};
  const style = range.getCellStyleData("cell") ?? {};

  return { ...data, s: style };
}

export function _getCellMetaValue(
  sheetRef: SheetRef | undefined,
  cellRefStr: string,
  path: Path[]
) {
  const worksheet = resolveSheet(sheetRef);
  const cellRange = resolveCellRange(cellRefStr);
  const values: unknown[][] = [];

  for (let row = cellRange.startRow; row <= cellRange.endRow; row += 1) {
    const rowValues: unknown[] = [];

    for (let column = cellRange.startColumn; column <= cellRange.endColumn; column += 1) {
      const range = worksheet.getRange(row, column);
      const data = worksheet.getSheet().getCellRaw(row, column) ?? {};
      const style = range.getCellStyleData("cell") ?? {};

      rowValues.push(readPath({ ...data, s: style }, path));
    }

    values.push(rowValues);
  }

  const firstValue = values[0]?.[0];
  const hasUniformValue = values.every((row) => row.every((value) => Object.is(value, firstValue)));

  return hasUniformValue ? firstValue : values;
}

export function _setCellMeta(
  sheetRef: SheetRef | undefined,
  cellRefStr: string,
  path: Path[],
  value: Value
) {
  const worksheet = resolveSheet(sheetRef);
  const cellRange = resolveCellRange(cellRefStr);

  for (let row = cellRange.startRow; row <= cellRange.endRow; row += 1) {
    for (let column = cellRange.startColumn; column <= cellRange.endColumn; column += 1) {
      const range = worksheet.getRange(row, column);

      if (path.length === 1 && path[0] === "v") {
        if (value === null) {
          range.clearContent();
          continue;
        }

        if (!isCellValue(value)) {
          throw new Error("Cell value must be a scalar.");
        }

        range.setValueForCell({
          v: value,
          t: checkCellValueType(value, null),
          f: null,
          p: null,
          si: null
        });
        continue;
      }

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
  }

  activateSheetAfterExplicitSet(sheetRef, worksheet);
}

export function _setCellNumberFormat(
  sheetRef: SheetRef | undefined,
  cellRefStr: string,
  value: Value
) {
  if (typeof value !== "string") throw new Error("numberFormat must be a string.");

  const worksheet = resolveSheet(sheetRef);
  const cellRange = resolveCellRange(cellRefStr);

  for (let row = cellRange.startRow; row <= cellRange.endRow; row += 1) {
    for (let column = cellRange.startColumn; column <= cellRange.endColumn; column += 1) {
      worksheet.getRange(row, column).setNumberFormat(value);
    }
  }

  activateSheetAfterExplicitSet(sheetRef, worksheet);
}

export function _getRowHidden(sheetRef: SheetRef | undefined, cellRefStr: string) {
  const worksheet = resolveSheet(sheetRef);
  const cellRange = resolveCellRange(cellRefStr);
  const values: boolean[] = [];

  for (let row = cellRange.startRow; row <= cellRange.endRow; row += 1) {
    values.push(!worksheet.getSheet().getRowRawVisible(row));
  }

  const firstValue = values[0];
  return values.every((value) => value === firstValue) ? firstValue : values;
}

export function _setRowHidden(sheetRef: SheetRef | undefined, cellRefStr: string, value: Value) {
  if (typeof value !== "boolean") throw new Error("rowHidden must be a boolean.");

  const worksheet = resolveSheet(sheetRef);
  const cellRange = resolveCellRange(cellRefStr);
  const rowCount = cellRange.endRow - cellRange.startRow + 1;

  if (value) worksheet.hideRows(cellRange.startRow, rowCount);
  else worksheet.showRows(cellRange.startRow, rowCount);
  activateSheetAfterExplicitSet(sheetRef, worksheet);
}

export function _getSheetName(sheetRef?: SheetRef) {
  return getSheetName(resolveSheet(sheetRef));
}

export function _resetSpreadsheetState() {
  const runtime = SpreadsheetRuntimeStore.runtime;
  const { workbook } = runtime;
  const previousSheets = workbook.getSheets();
  const existingNames = new Set(previousSheets.map((sheet) => sheet.getSheetName()));
  let resetSheetName = "__surfgym_reset__";

  while (existingNames.has(resetSheetName)) resetSheetName += "_";

  const resetWorksheet = workbook.insertSheet(resetSheetName, { index: 0 });
  workbook.setActiveSheet(resetWorksheet);

  for (const sheet of previousSheets) {
    if (!workbook.deleteSheet(sheet)) {
      throw new Error(`Failed to remove sheet while resetting state: ${sheet.getSheetName()}`);
    }
  }

  resetWorksheet.setName("Sheet1");
  workbook.setActiveSheet(resetWorksheet);
  runtime.defaultWorksheet = resetWorksheet;
  runtime.initializeWorksheet(resetWorksheet);
  chartMetaRegistry.length = 0;

  return resetWorksheet;
}

export function _setSheetName(sheetRef: SheetRef | undefined, value: Value) {
  const name = requireSheetName(value);
  const worksheet = resolveSheet(sheetRef, { create: true });

  const setName = (worksheet as WorksheetWithCharts).setName;
  if (typeof setName === "function" && getSheetName(worksheet) !== name) {
    setName.call(worksheet, name);
  }

  activateSheetAfterExplicitSet(sheetRef, worksheet);
  return getSheetName(worksheet);
}

export function _getIndexedSheetName(sheetRef: IndexedSheetRef) {
  const { index, name } = normalizeIndexedSheetRef(sheetRef);
  const worksheet = getWorkbookSheets()[index];

  if (!worksheet) throw new Error(`Sheet not found: index=${index}, name=${name}`);

  const actualName = getSheetName(worksheet);
  if (actualName !== name) {
    throw new Error(
      `Sheet mismatch at index ${index}: expected ${name}, actual ${String(actualName)}`
    );
  }

  return actualName;
}

export function _setIndexedSheetName(sheetRef: IndexedSheetRef, value: Value) {
  const normalized = normalizeIndexedSheetRef(sheetRef);
  const valueName = requireSheetName(value);

  if (valueName !== normalized.name) {
    throw new Error(
      `Indexed sheet name must match set value: selector=${normalized.name}, value=${valueName}`
    );
  }

  const { workbook } = SpreadsheetRuntimeStore.runtime;
  const mutableWorkbook = workbook as unknown as WorkbookWithSheetMutation;
  let sheets = getWorkbookSheets();

  if (normalized.index > sheets.length) {
    throw new Error(
      `Cannot place sheet at index ${normalized.index}; sheet count is ${sheets.length}.`
    );
  }

  let worksheet = sheets.find((sheet) => getSheetName(sheet) === normalized.name);

  if (worksheet) {
    const currentIndex = sheets.indexOf(worksheet);
    if (currentIndex !== normalized.index) {
      if (normalized.index >= sheets.length) {
        throw new Error(
          `Cannot move existing sheet ${normalized.name} to index ${normalized.index}.`
        );
      }
      if (typeof mutableWorkbook.moveSheet !== "function") {
        throw new Error("Moving sheets is not supported.");
      }
      mutableWorkbook.moveSheet(worksheet, normalized.index);
    }
  } else {
    worksheet = sheets[normalized.index];
    if (worksheet) {
      const setName = (worksheet as WorksheetWithCharts).setName;
      if (typeof setName !== "function") throw new Error("Renaming sheets is not supported.");
      setName.call(worksheet, normalized.name);
    } else {
      if (typeof mutableWorkbook.insertSheet !== "function") {
        throw new Error("Creating sheets is not supported.");
      }
      worksheet = mutableWorkbook.insertSheet(normalized.name, {
        index: normalized.index
      });
    }
  }

  sheets = getWorkbookSheets();
  const indexedWorksheet = sheets[normalized.index];
  const actualName = indexedWorksheet ? getSheetName(indexedWorksheet) : null;
  if (!indexedWorksheet || actualName !== normalized.name) {
    throw new Error(
      `Failed to place sheet ${normalized.name} at index ${normalized.index}; actual=${String(
        actualName
      )}`
    );
  }

  activateSheetAfterExplicitSet(normalized.index, indexedWorksheet);
  return actualName;
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
    title: readFirstString(style, [
      ["titles", "title", "content"],
      ["title", "content"]
    ]),
    xAxisTitle: readFirstString(style, [
      ["titles", "xAxisTitle", "content"],
      ["xAxisTitle", "content"]
    ]),
    yAxisTitle: readFirstString(style, [
      ["titles", "yAxisTitle", "content"],
      ["yAxisTitle", "content"]
    ]),
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

  return resolveChartMeta(getChartMetasForWorksheet(worksheet), chartRef);
}

export async function _setChartMeta(
  sheetRef: SheetRef | undefined,
  chartRef: ChartRef | undefined,
  path: Path[],
  value: Value
) {
  const worksheet = resolveSheet(sheetRef, { create: true });
  const meta = getMutableChartMeta(worksheet, chartRef);

  writePath(
    meta as unknown as Record<PropertyKey, unknown>,
    path,
    normalizeChartSetValue(path, value)
  );
  meta.sheetId = worksheet.getSheetId?.() ?? meta.sheetId;
  meta.sheetName = getSheetName(worksheet);
  upsertChartMeta(meta);

  await syncChartMetaToWorksheet(worksheet, meta);

  activateSheetAfterExplicitSet(sheetRef, worksheet);
  return meta;
}

export type SheetRef = string | number;
export type IndexedSheetRef = {
  index: number;
  name: string;
};
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

type NormalizedIndexedSheetRef = {
  index: number;
  name: string;
};

function requireSheetName(value: Value): string {
  if (typeof value !== "string" || value.trim() === "") {
    throw new Error("Sheet name must be a non-empty string.");
  }
  return value;
}

function normalizeIndexedSheetRef(sheetRef: IndexedSheetRef): NormalizedIndexedSheetRef {
  if (!Number.isInteger(sheetRef.index) || sheetRef.index < 0) {
    throw new Error(`Sheet index must be a non-negative integer: ${String(sheetRef.index)}`);
  }
  if (typeof sheetRef.name !== "string" || sheetRef.name.trim() === "") {
    throw new Error("Indexed sheet name must be a non-empty string.");
  }

  return {
    index: sheetRef.index,
    name: sheetRef.name
  };
}

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
