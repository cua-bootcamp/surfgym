import type { FWorkbook, FWorksheet } from "@univerjs/preset-sheets-core";

declare global {
  interface Window {
    surfgym: {
      get: (payload: SurfgymGetPayload) => unknown;
      set: (payload: SurfgymSetPayload) => unknown;
    };
  }
}

export type SpreadsheetRuntime = {
  workbook: FWorkbook;
  defaultWorksheet: FWorksheet;
};

export const SET = Symbol("surfgym.set");
export type Settable = {
  [SET]: (path: PathPart[], value: JsonValue) => void;
};

export function isSettable(value: unknown): value is Settable {
  return isRecord(value) && typeof value[SET] === "function";
}

// #######################################
// #              Reference              #
// #######################################

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
  //   sourceRange: string | null;
  range: unknown;
  title: string | null;
  legendPosition: unknown;
  dataOrientation: unknown;
  width: number | null;
  height: number | null;
  position: unknown;
  context: unknown;
  seriesData: unknown;
  categoryData: unknown;
};

// #####################################
// #                ETC                #
// #####################################

export type JsonValue =
  | null
  | string
  | number
  | boolean
  | JsonValue[]
  | { [key: string]: JsonValue };

export type QueryStep = [string, JsonValue];
export type PathPart = string | number;

export type SurfgymGetPayload = {
  query: QueryStep[];
  path: PathPart[];
};

export type SurfgymSetPayload = SurfgymGetPayload & {
  value: JsonValue;
};

export function isRecord(value: unknown): value is Record<PropertyKey, unknown> {
  return value !== null && typeof value === "object";
}
