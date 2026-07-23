import type { Path, Value } from "../external";
import {
  _getCellMetaValue,
  _getChartMeta,
  _getRowHidden,
  _getSheetName,
  _getSheetNames,
  _setCellMeta,
  _setCellNumberFormat,
  _setChartMeta,
  _setRowHidden,
  _setSheetName,
  _setSheetNames,
  type ChartRef
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
type WorkbookProperty = "sheetNames";
type ChartProperty = (typeof CHART_PROPERTIES)[number];

type CellSpec = {
  kind: "cell";
  sheet: SheetSelector;
  cell: string;
  property: CellProperty;
};

type SheetSpec = {
  kind: "sheet";
  sheet: SheetSelector;
  property: SheetProperty;
};

type ChartSpec = {
  kind: "chart";
  sheet: SheetSelector;
  chart?: ChartRef;
  property: ChartProperty;
};

type WorkbookSpec = {
  kind: "workbook";
  property: WorkbookProperty;
};

export type SpreadsheetSpec = CellSpec | SheetSpec | ChartSpec | WorkbookSpec;
export type Get = typeof get;
export type Set = typeof set;

export function get(spec: SpreadsheetSpec): unknown {
  switch (spec.kind) {
    case "cell":
      if (spec.property === "rowHidden") return _getRowHidden(sheetRef(spec.sheet), spec.cell);
      return _getCellMetaValue(
        sheetRef(spec.sheet),
        spec.cell,
        getCellPath(spec.property)
      );
    case "sheet":
      assertSheetProperty(spec.property);
      return _getSheetName(sheetRef(spec.sheet));
    case "chart":
      assertChartProperty(spec.property);
      return _getChartMeta(sheetRef(spec.sheet), spec.chart)[spec.property];
    case "workbook":
      assertWorkbookProperty(spec.property);
      return _getSheetNames();
  }

  throw unsupportedSpec(spec);
}

export function set(spec: SpreadsheetSpec, value: Value) {
  switch (spec.kind) {
    case "cell":
      if (spec.property === "rowHidden") return _setRowHidden(sheetRef(spec.sheet), spec.cell, value);
      if (spec.property === "numberFormat") {
        return _setCellNumberFormat(sheetRef(spec.sheet), spec.cell, value);
      }
      return _setCellMeta(sheetRef(spec.sheet), spec.cell, getCellPath(spec.property), value);
    case "sheet":
      assertSheetProperty(spec.property);
      return _setSheetName(sheetRef(spec.sheet), value);
    case "chart":
      assertChartProperty(spec.property);
      return _setChartMeta(sheetRef(spec.sheet), spec.chart, [spec.property], value);
    case "workbook":
      assertWorkbookProperty(spec.property);
      return _setSheetNames(value);
  }

  throw unsupportedSpec(spec);
}

function sheetRef(sheet: SheetSelector): string | number | undefined {
  return sheet ?? undefined;
}

function assertChartProperty(property: string): asserts property is ChartProperty {
  if (!CHART_PROPERTIES.includes(property as ChartProperty)) {
    throw new Error(`Unsupported chart property: ${property}`);
  }
}

function assertSheetProperty(property: string): asserts property is SheetProperty {
  if (property !== "name") throw new Error(`Unsupported sheet property: ${property}`);
}

function assertWorkbookProperty(property: string): asserts property is WorkbookProperty {
  if (property !== "sheetNames") throw new Error(`Unsupported workbook property: ${property}`);
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
