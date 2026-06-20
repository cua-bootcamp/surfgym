import type { FWorkbook, FWorksheet } from "@univerjs/preset-sheets-core";
import type { Get, Set } from "../external";

declare global {
  interface Window {
    surfgym: {
      get: Get;
      set: Set;
    };
  }
}

export type SpreadsheetRuntime = {
  workbook: FWorkbook;
  defaultWorksheet: FWorksheet;
};

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
