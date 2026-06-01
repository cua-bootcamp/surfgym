import type { SelectionRange, SpreadsheetActions } from './spreadsheet-actions';

const markDirtyFilterChangeMutationId = 'sheet.mutation.mark-dirty-filter-change';

type RowMeta = {
  filtered: boolean;
  visible: boolean;
  rawVisible: boolean;
  filterRange: string | null;
};

type CellMeta = {
  cell: unknown;
  style: unknown;
  row: RowMeta;
};

type SheetMeta = {
  sheet: unknown;
};

type SpreadsheetCellMetaEntry = {
  address: string;
  cell?: unknown;
  style?: unknown;
  row?: Partial<RowMeta>;
};

type SpreadsheetWorkbook = {
  getId: () => string;
};

type SpreadsheetCellValue = Record<string, unknown>;

type SpreadsheetEvaluationRange = {
  createFilter: () => unknown;
  getCellData: () => unknown;
  getCellStyleData: (type: string) => unknown;
  setValueForCell: (value: SpreadsheetCellValue) => unknown;
};

type SpreadsheetEvaluationSheet = {
  getRowManager: () => { getRowOrCreate: (row: number) => { hd?: number } };
  isRowFiltered: (row: number) => boolean;
  getRowVisible: (row: number) => boolean;
  getRowRawVisible: (row: number) => boolean;
};

type SpreadsheetEvaluationWorksheet = {
  getSheetId: () => string;
  getMaxRows: () => number;
  getMaxColumns: () => number;
  getFilter: () => unknown;
  getRange: {
    (address: string): SpreadsheetEvaluationRange;
    (row: number, column: number): SpreadsheetEvaluationRange;
  };
  getSheet: () => SpreadsheetEvaluationSheet;
};

type SpreadsheetEvaluationContext = {
  univerAPI: {
    executeCommand: <P extends object = object, R = boolean>(id: string, params?: P) => Promise<R>;
  };
  workbook: SpreadsheetWorkbook;
  worksheet: unknown;
  actions: Pick<SpreadsheetActions, 'columnIndexToName'>;
};

type PlainObject = Record<string, unknown>;
type FilterModelLike = {
  filteredOutRows: Set<number>;
};
type FilterLike = {
  _filterModel?: FilterModelLike;
  getRange?: () => { getA1Notation: (withSheet?: boolean) => string; getRange: () => SelectionRange };
};

declare global {
  interface Window {
    getCellMeta: (address: string) => CellMeta;
    getSheetMeta: () => SheetMeta;
    applyCellMeta: (entries: SpreadsheetCellMetaEntry[]) => CellMeta[];
  }
}

export function installSpreadsheetEvaluationHelpers({
  univerAPI,
  workbook,
  worksheet,
  actions,
}: SpreadsheetEvaluationContext) {
  const targetWorksheet = worksheet as SpreadsheetEvaluationWorksheet;

  function columnNameToIndex(columnName: string) {
    return columnName
      .toUpperCase()
      .split('')
      .reduce((sum, char) => sum * 26 + char.charCodeAt(0) - 64, 0) - 1;
  }

  function cellNameToPosition(address: string) {
    const match = address.trim().match(/^\$?([A-Z]+)\$?(\d+)$/i);
    if (!match) {
      throw new Error(`Invalid cell address: ${address}`);
    }

    const [, columnName, rowName] = match;

    if (!columnName || !rowName) {
      throw new Error(`Invalid cell address: ${address}`);
    }

    const column = columnNameToIndex(columnName);
    const row = Number(rowName) - 1;

    return { row, column };
  }

  function isPlainObject(value: unknown): value is PlainObject {
    return value != null && typeof value === 'object' && !Array.isArray(value);
  }

  function clonePlainValue<T>(value: T): T {
    if (value == null) return value;
    return JSON.parse(JSON.stringify(value)) as T;
  }

  function getFilterModel(filter: unknown): FilterModelLike | null {
    if (!isPlainObject(filter)) return null;

    const filterModel = filter._filterModel;
    if (!isPlainObject(filterModel) || !(filterModel.filteredOutRows instanceof Set)) return null;

    return filterModel as FilterModelLike;
  }

  function getFilterRangeA1(filter: FilterLike | null) {
    return filter?.getRange?.().getA1Notation(false) ?? null;
  }

  function createFallbackFilterRangeA1(row: number) {
    const maxColumn = Math.max(0, targetWorksheet.getMaxColumns() - 1);
    const maxRow = Math.max(row, targetWorksheet.getMaxRows() - 1);

    return `A1:${actions.columnIndexToName(maxColumn)}${maxRow + 1}`;
  }

  function getOrCreateFilterForRowMeta(row: number, rowMeta: Partial<RowMeta>): FilterLike | null {
    const currentFilter = targetWorksheet.getFilter();
    if (currentFilter) return currentFilter as unknown as FilterLike;

    const filterRange = typeof rowMeta.filterRange === 'string' && rowMeta.filterRange.trim()
      ? rowMeta.filterRange
      : createFallbackFilterRangeA1(row);

    return targetWorksheet.getRange(filterRange).createFilter() as unknown as FilterLike | null;
  }

  function markFilterRangeDirty(filter: FilterLike | null) {
    const filterRange = filter?.getRange?.().getRange();
    if (!filterRange) return;

    void univerAPI.executeCommand(markDirtyFilterChangeMutationId, {
      unitId: workbook.getId(),
      subUnitId: targetWorksheet.getSheetId(),
      filterRange,
    });
  }

  function applyFilteredRowMeta(row: number, rowMeta: Partial<RowMeta>) {
    if (typeof rowMeta.filtered !== 'boolean') return;

    const filter = getOrCreateFilterForRowMeta(row, rowMeta);
    const filterModel = getFilterModel(filter);
    if (!filterModel) return;

    const filteredOutRows = new Set(filterModel.filteredOutRows);

    if (rowMeta.filtered) {
      filteredOutRows.add(row);
    } else {
      filteredOutRows.delete(row);
    }

    filterModel.filteredOutRows = filteredOutRows;
    markFilterRangeDirty(filter);
  }

  function applyRowMeta(row: number, rowMeta: Partial<RowMeta>) {
    const sheet = targetWorksheet.getSheet();
    const rowData = sheet.getRowManager().getRowOrCreate(row);

    if (typeof rowMeta.rawVisible === 'boolean') {
      rowData.hd = rowMeta.rawVisible ? 0 : 1;
    } else if (typeof rowMeta.visible === 'boolean' && typeof rowMeta.filtered !== 'boolean') {
      rowData.hd = rowMeta.visible ? 0 : 1;
    }

    applyFilteredRowMeta(row, rowMeta);
  }

  function getCellMeta(address: string): CellMeta {
    const { row, column } = cellNameToPosition(address);
    const range = targetWorksheet.getRange(row, column);
    const sheet = targetWorksheet.getSheet();
    const filter = targetWorksheet.getFilter() as unknown as FilterLike | null;

    return {
      cell: clonePlainValue(range.getCellData()),
      style: clonePlainValue(range.getCellStyleData('cell')),
      row: {
        filtered: sheet.isRowFiltered(row),
        visible: sheet.getRowVisible(row),
        rawVisible: sheet.getRowRawVisible(row),
        filterRange: getFilterRangeA1(filter),
      },
    };
  }

  function applyCellMeta(entries: SpreadsheetCellMetaEntry[]): CellMeta[] {
    for (const entry of entries) {
      const { row, column } = cellNameToPosition(entry.address);
      const range = targetWorksheet.getRange(row, column);

      if (entry.cell != null && !isPlainObject(entry.cell)) {
        throw new Error(`Invalid cell object for ${entry.address}`);
      }

      if (entry.row != null && !isPlainObject(entry.row)) {
        throw new Error(`Invalid row object for ${entry.address}`);
      }

      const hasCell = Object.prototype.hasOwnProperty.call(entry, 'cell');
      const hasStyle = Object.prototype.hasOwnProperty.call(entry, 'style');

      if (hasCell || hasStyle) {
        const nextCellData = isPlainObject(entry.cell)
          ? clonePlainValue(entry.cell)
          : hasCell
            ? {}
            : clonePlainValue(range.getCellData() ?? {});

        if (!isPlainObject(nextCellData)) {
          throw new Error(`Invalid current cell object for ${entry.address}`);
        }

        if (hasStyle) {
          if (isPlainObject(entry.style)) {
            nextCellData.s = clonePlainValue(entry.style);
          } else {
            delete nextCellData.s;
          }
        }

        range.setValueForCell(nextCellData as SpreadsheetCellValue);
      }

      if (isPlainObject(entry.row)) {
        applyRowMeta(row, entry.row as Partial<RowMeta>);
      }
    }

    return entries.map((entry) => getCellMeta(entry.address));
  }

  window.getCellMeta = getCellMeta;
  window.applyCellMeta = applyCellMeta;
}
