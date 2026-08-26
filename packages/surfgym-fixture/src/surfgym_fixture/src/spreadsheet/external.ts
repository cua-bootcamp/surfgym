import type { Path, Value } from "../external";
import {
  _getCellMetaValue,
  _getCellValidationList,
  _getCellMerged,
  _getFrozenColumns,
  _getFrozenRows,
  _getIndexedSheetName,
  _getPivotMeta,
  _getRowHidden,
  _getSheetName,
  _getSheetZoom,
  _resetSpreadsheetState,
  _setCellMeta,
  _setCellValidationList,
  _setCellMerged,
  _setCellNumberFormat,
  _setFrozenColumns,
  _setFrozenRows,
  _setIndexedSheetName,
  _setPivotMeta,
  _setRowHidden,
  _setSheetName,
  _setSheetZoom,
  type IndexedSheetRef
} from "./internal";
import {
  getTaskScopedChartMeta as _getChartMeta,
  setTaskScopedChartMeta as _setChartMeta,
  taskScopedLineCharts,
  type ChartRef
} from "./surfgym-chart";
import {
  formatQualifiedChartSourceRange,
  resolveAndReadChartSource,
} from "./chart-range";
import {
  getTaskScopedSparklineMeta as _getSparklineMeta,
  setTaskScopedSparklineMeta as _setSparklineMeta
} from "./surfgym-sparkline";
import {
  getTaskScopedSpreadsheetExportRequest as _getExportRequest,
  setTaskScopedSpreadsheetExportRequest as _setExportRequest,
} from "./surfgym-export";
import { SpreadsheetRuntimeStore } from "./runtime";

const CELL_PATHS = {
  backgroundColor: ["s", "bg", "rgb"],
  bold: ["s", "bl"],
  fontColor: ["s", "cl", "rgb"],
  formula: ["f"],
  numberFormat: ["s", "n", "pattern"],
  value: ["v"],
  valueType: ["t"]
} satisfies Record<string, Path[]>;

const CHART_PROPERTIES = [
  "categoryData",
  "chartType",
  "context",
  "dataOrientation",
  "height",
  "legendPosition",
  "position",
  "range",
  "seriesData",
  "sourceRange",
  "title",
  "width",
  "xAxisTitle",
  "yAxisTitle"
] as const;

const SPARKLINE_PROPERTIES = ["sourceRange", "type"] as const;

type SheetSelector = string | number | null;
type CellProperty = keyof typeof CELL_PATHS | "merged" | "rowHidden" | "validationList";
type SheetProperty = "name" | "zoom" | "frozenRows" | "frozenColumns";
type ChartProperty = (typeof CHART_PROPERTIES)[number];
type SparklineProperty = (typeof SPARKLINE_PROPERTIES)[number];

type CellSpec = {
  kind: "cell";
  sheet: SheetSelector;
  cell: string;
  property: CellProperty;
};

type SheetSpec = {
  kind: "sheet";
  sheet: SheetSelector | IndexedSheetRef;
  property: SheetProperty;
};

type ChartSpec = {
  kind: "chart";
  sheet: SheetSelector;
  chart?: ChartRef;
  property: ChartProperty;
};

type SparklineSpec = {
  kind: "sparkline";
  sheet: SheetSelector;
  cell: string;
  property: SparklineProperty;
};

type PivotSpec = {
  kind: "pivot";
  sheet: string;
  startRow: number;
  startColumn: number;
  property: "definition";
};

type ExportSpec = {
  kind: "export";
  property: "request";
};

export type SpreadsheetSpec = CellSpec | SheetSpec | ChartSpec | SparklineSpec | PivotSpec | ExportSpec;
export type SpreadsheetStateAtom = {
  spec: SpreadsheetSpec;
  value: Value;
};
export type Get = typeof get;
export type Set = typeof set;
export type ApplyState = typeof applyState;

export function get(spec: SpreadsheetSpec): unknown {
  switch (spec.kind) {
    case "cell":
      if (spec.property === "merged") return _getCellMerged(sheetRef(spec.sheet), spec.cell);
      if (spec.property === "rowHidden") return _getRowHidden(sheetRef(spec.sheet), spec.cell);
      if (spec.property === "validationList") return _getCellValidationList(sheetRef(spec.sheet), spec.cell);
      return _getCellMetaValue(sheetRef(spec.sheet), spec.cell, getCellPath(spec.property));
    case "sheet":
      assertSheetProperty(spec.property);
      if (spec.property === "name") {
        if (isIndexedSheetRef(spec.sheet)) return _getIndexedSheetName(spec.sheet);
        return _getSheetName(sheetRef(spec.sheet));
      }
      if (spec.property === "frozenRows") return _getFrozenRows(resolveSheetRef(spec.sheet));
      if (spec.property === "frozenColumns") return _getFrozenColumns(resolveSheetRef(spec.sheet));
      return _getSheetZoom(resolveSheetRef(spec.sheet));
    case "chart":
      assertChartProperty(spec.property);
      return getChartProperty(sheetRef(spec.sheet), spec.chart, spec.property);
    case "sparkline":
      assertSparklineProperty(spec.property);
      return _getSparklineMeta(sheetRef(spec.sheet), spec.cell)[spec.property];
    case "pivot":
      assertPivotSpec(spec);
      return _getPivotMeta(spec.sheet, spec.startRow, spec.startColumn);
    case "export":
      assertExportSpec(spec);
      return _getExportRequest();
  }

  throw unsupportedSpec(spec);
}
export function set(spec: SpreadsheetSpec, value: Value) {
  switch (spec.kind) {
    case "cell":
      if (spec.property === "merged") return _setCellMerged(sheetRef(spec.sheet), spec.cell, value);
      if (spec.property === "rowHidden")
        return _setRowHidden(sheetRef(spec.sheet), spec.cell, value);
      if (spec.property === "validationList") return _setCellValidationList(sheetRef(spec.sheet), spec.cell, value);
      if (spec.property === "numberFormat") {
        return _setCellNumberFormat(sheetRef(spec.sheet), spec.cell, value);
      }
      return _setCellMeta(sheetRef(spec.sheet), spec.cell, getCellPath(spec.property), value);
    case "sheet":
      assertSheetProperty(spec.property);
      if (spec.property === "name") {
        if (isIndexedSheetRef(spec.sheet)) return _setIndexedSheetName(spec.sheet, value);
        return _setSheetName(sheetRef(spec.sheet), value);
      }
      if (spec.property === "frozenRows") return _setFrozenRows(resolveSheetRef(spec.sheet), value);
      if (spec.property === "frozenColumns") return _setFrozenColumns(resolveSheetRef(spec.sheet), value);
      return _setSheetZoom(resolveSheetRef(spec.sheet), value);
    case "chart":
      assertChartProperty(spec.property);
      return setChartProperty(sheetRef(spec.sheet), spec.chart, spec.property, value);
    case "sparkline":
      assertSparklineProperty(spec.property);
      return _setSparklineMeta(sheetRef(spec.sheet), spec.cell, spec.property, value);
    case "pivot":
      assertPivotSpec(spec);
      return _setPivotMeta(spec.sheet, spec.startRow, spec.startColumn, value);
    case "export":
      assertExportSpec(spec);
      return _setExportRequest(value);
  }

  throw unsupportedSpec(spec);
}

export async function applyState(atoms: SpreadsheetStateAtom[]) {
  if (!Array.isArray(atoms)) throw new Error("Spreadsheet state must be an array.");

  await SpreadsheetRuntimeStore.runtime.rendered;
  await settleSpreadsheetRendering();
  _resetSpreadsheetState();

  for (const atom of atoms) {
    await set(atom.spec, atom.value);
  }

  await settleSpreadsheetRendering();
  return true;
}

async function settleSpreadsheetRendering() {
  await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()));
  await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()));
}

function sheetRef(sheet: SheetSelector): string | number | undefined {
  return sheet ?? undefined;
}

function resolveChart(sheet: string | number | undefined, chartRef?: ChartRef) {
  const charts = taskScopedLineCharts.list(sheet);
  return chartRef?.id
    ? charts.find((chart) => chart.id === chartRef.id)
    : charts[chartRef?.index ?? 0];
}

function readChartSource(sourceRange: string, defaultSheet?: string) {
  return resolveAndReadChartSource(
    sourceRange,
    (sourceSheet) => SpreadsheetRuntimeStore.runtime.workbook.getSheetByName(sourceSheet),
    defaultSheet === undefined ? {} : { defaultSheet },
  );
}

function getChartProperty(
  sheet: string | number | undefined,
  chartRef: ChartRef | undefined,
  property: ChartProperty,
) {
  const chart = _getChartMeta(sheet, chartRef);
  return property === "sourceRange"
    ? formatQualifiedChartSourceRange(chart.sourceSheet, chart.sourceRange)
    : chart[property];
}

function setChartSourceRange(
  sheet: string | number | undefined,
  chartRef: ChartRef | undefined,
  value: Value,
) {
  if (typeof value !== "string") {
    throw new Error("Chart source range must be a sheet-qualified A1 range.");
  }
  const source = readChartSource(value);
  const current = resolveChart(sheet, chartRef);
  if (current) {
    if (current.sourceSheet.toLocaleLowerCase() !== source.sourceSheet.toLocaleLowerCase()) {
      throw new Error("Chart source sheet is immutable after initialization.");
    }
    return taskScopedLineCharts.update(
      sheet,
      { id: current.id },
      { sourceRange: source.sourceRange },
      source.matrix,
    );
  }

  const nextIndex = taskScopedLineCharts.list(sheet).length;
  if (chartRef?.id || (chartRef?.index !== undefined && chartRef.index !== nextIndex)) {
    throw new Error("Chart sourceRange must initialize the next chart index.");
  }
  return taskScopedLineCharts.create(
    sheet,
    { sourceRange: source.sourceRange, sourceSheet: source.sourceSheet },
    source.matrix,
  );
}

function setChartProperty(
  sheet: string | number | undefined,
  chartRef: ChartRef | undefined,
  property: ChartProperty,
  value: Value,
) {
  if (property === "sourceRange") return setChartSourceRange(sheet, chartRef, value);
  const current = resolveChart(sheet, chartRef);
  if (!current) {
    throw new Error("Chart sourceRange must be set first to initialize a chart.");
  }
  if (property === "dataOrientation") {
    const source = readChartSource(current.sourceRange, current.sourceSheet);
    return taskScopedLineCharts.update(
      sheet,
      { id: current.id },
      { dataOrientation: value as never },
      source.matrix,
    );
  }
  return _setChartMeta(sheet, chartRef, property, value);
}

function isIndexedSheetRef(sheet: SheetSelector | IndexedSheetRef): sheet is IndexedSheetRef {
  return typeof sheet === "object" && sheet !== null;
}

function resolveSheetRef(sheet: SheetSelector | IndexedSheetRef): string | number | undefined {
  if (!isIndexedSheetRef(sheet)) return sheetRef(sheet);

  _getIndexedSheetName(sheet);
  return sheet.index;
}

function assertChartProperty(property: string): asserts property is ChartProperty {
  if (!CHART_PROPERTIES.includes(property as ChartProperty)) {
    throw new Error(`Unsupported chart property: ${property}`);
  }
}

function assertSparklineProperty(property: string): asserts property is SparklineProperty {
  if (!SPARKLINE_PROPERTIES.includes(property as SparklineProperty)) {
    throw new Error(`Unsupported sparkline property: ${property}`);
  }
}

function assertSheetProperty(property: string): asserts property is SheetProperty {
  if (
    property !== "name" &&
    property !== "zoom" &&
    property !== "frozenRows" &&
    property !== "frozenColumns"
  ) {
    throw new Error(`Unsupported sheet property: ${property}`);
  }
}

function assertPivotSpec(spec: PivotSpec) {
  if (spec.property !== "definition" || !spec.sheet.trim() || !Number.isInteger(spec.startRow) || spec.startRow < 0 ||
    !Number.isInteger(spec.startColumn) || spec.startColumn < 0) {
    throw new Error("Invalid pivot atom address.");
  }
}

function assertExportSpec(spec: ExportSpec) {
  if (spec.property !== "request") throw new Error("Invalid export atom property.");
}

function unsupportedSpec(spec: never): Error {
  const kind = (spec as { kind?: unknown }).kind;
  return new Error(`Unsupported spreadsheet spec kind: ${String(kind)}`);
}

function getCellPath(property: keyof typeof CELL_PATHS): Path[] {
  const path = CELL_PATHS[property];
  if (!path) throw new Error(`Unsupported cell property: ${property}`);
  return path;
}
