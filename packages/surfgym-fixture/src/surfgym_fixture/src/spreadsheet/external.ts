import type { Path, Value } from "../external";
import {
  _getCellMetaValue,
  _getChartMeta,
  _getIndexedSheetName,
  _getRowHidden,
  _getSheetName,
  _resetSpreadsheetState,
  _setCellMeta,
  _setCellNumberFormat,
  _setChartMeta,
  _setIndexedSheetName,
  _setRowHidden,
  _setSheetName,
  type ChartRef,
  type IndexedSheetRef
} from "./internal";

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

type SheetSelector = string | number | null;
type CellProperty = keyof typeof CELL_PATHS | "rowHidden";
type SheetProperty = "name";
type ChartProperty = (typeof CHART_PROPERTIES)[number];

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

export type SpreadsheetSpec = CellSpec | SheetSpec | ChartSpec;
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
      if (spec.property === "rowHidden") return _getRowHidden(sheetRef(spec.sheet), spec.cell);
      return _getCellMetaValue(sheetRef(spec.sheet), spec.cell, getCellPath(spec.property));
    case "sheet":
      assertSheetProperty(spec.property);
      if (isIndexedSheetRef(spec.sheet)) return _getIndexedSheetName(spec.sheet);
      return _getSheetName(sheetRef(spec.sheet));
    case "chart":
      assertChartProperty(spec.property);
      return _getChartMeta(sheetRef(spec.sheet), spec.chart)[spec.property];
  }

  throw unsupportedSpec(spec);
}

export function set(spec: SpreadsheetSpec, value: Value) {
  switch (spec.kind) {
    case "cell":
      if (spec.property === "rowHidden")
        return _setRowHidden(sheetRef(spec.sheet), spec.cell, value);
      if (spec.property === "numberFormat") {
        return _setCellNumberFormat(sheetRef(spec.sheet), spec.cell, value);
      }
      return _setCellMeta(sheetRef(spec.sheet), spec.cell, getCellPath(spec.property), value);
    case "sheet":
      assertSheetProperty(spec.property);
      if (isIndexedSheetRef(spec.sheet)) return _setIndexedSheetName(spec.sheet, value);
      return _setSheetName(sheetRef(spec.sheet), value);
    case "chart":
      assertChartProperty(spec.property);
      return _setChartMeta(sheetRef(spec.sheet), spec.chart, [spec.property], value);
  }

  throw unsupportedSpec(spec);
}

export async function applyState(atoms: SpreadsheetStateAtom[]) {
  if (!Array.isArray(atoms)) throw new Error("Spreadsheet state must be an array.");

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

function assertChartProperty(property: string): asserts property is ChartProperty {
  if (!CHART_PROPERTIES.includes(property as ChartProperty)) {
    throw new Error(`Unsupported chart property: ${property}`);
  }
}

function assertSheetProperty(property: string): asserts property is SheetProperty {
  if (property !== "name") throw new Error(`Unsupported sheet property: ${property}`);
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
