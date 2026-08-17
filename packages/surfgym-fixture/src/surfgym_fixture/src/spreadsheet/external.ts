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
  type ChartRef
} from "./surfgym-chart";
import {
  getTaskScopedSparklineMeta as _getSparklineMeta,
  setTaskScopedSparklineMeta as _setSparklineMeta
} from "./surfgym-sparkline";
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

export type SpreadsheetSpec = CellSpec | SheetSpec | ChartSpec | SparklineSpec | PivotSpec;
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
      return _getChartMeta(sheetRef(spec.sheet), spec.chart)[spec.property];
    case "sparkline":
      assertSparklineProperty(spec.property);
      return _getSparklineMeta(sheetRef(spec.sheet), spec.cell)[spec.property];
    case "pivot":
      assertPivotSpec(spec);
      return _getPivotMeta(spec.sheet, spec.startRow, spec.startColumn);
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
      return _setChartMeta(sheetRef(spec.sheet), spec.chart, spec.property, value);
    case "sparkline":
      assertSparklineProperty(spec.property);
      return _setSparklineMeta(sheetRef(spec.sheet), spec.cell, spec.property, value);
    case "pivot":
      assertPivotSpec(spec);
      return _setPivotMeta(spec.sheet, spec.startRow, spec.startColumn, value);
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

function unsupportedSpec(spec: never): Error {
  const kind = (spec as { kind?: unknown }).kind;
  return new Error(`Unsupported spreadsheet spec kind: ${String(kind)}`);
}

function getCellPath(property: keyof typeof CELL_PATHS): Path[] {
  const path = CELL_PATHS[property];
  if (!path) throw new Error(`Unsupported cell property: ${property}`);
  return path;
}
