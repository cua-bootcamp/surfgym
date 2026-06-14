import type { FWorkbook, FWorksheet } from "@univerjs/preset-sheets-core";

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

type RowMeta = {
  filtered: boolean;
  visible: boolean;
  rawVisible: boolean;
  filterRange: string | null;
};

export type CellMeta = {
  cell: unknown;
  style: unknown;
  //   row: RowMeta;
};

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
