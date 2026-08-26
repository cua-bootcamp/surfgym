import {
  resolveAndReadChartSource,
} from './chart-range';
import { _getCellValidationList, _registerPivotMeta, _setCellValidationList } from './internal';
import { taskScopedLineCharts, type TaskScopedLineChartUpdate } from './surfgym-chart';
import { taskScopedLineSparklines } from './surfgym-sparkline';
import { validationMessageForValue } from './spreadsheet-validation-guard';

const setFilterRangeCommandId = 'sheet.command.set-filter-range';
const removeSheetFilterCommandId = 'sheet.command.remove-sheet-filter';
const mergeCellsCommandId = 'sheet.command.add-worksheet-merge-all';
const unmergeCellsCommandId = 'sheet.command.remove-worksheet-merge';

export type SelectionRange = {
  startRow: number;
  endRow: number;
  startColumn: number;
  endColumn: number;
  __surfgymHeaderless?: boolean;
};


type SpreadsheetRange = {
  sort: (options: { column: number; ascending: boolean }) => unknown;
  setFontFamily: (fontFamily: string | null) => unknown;
  setFontSize: (fontSize: number | null) => unknown;
  setNumberFormat: (pattern: string) => unknown;
  setValue: (value: string | number | boolean | null) => unknown;
  setValues: (values: unknown[][]) => unknown;
  getValue?: () => unknown;
  getValues?: () => unknown[][];
  getCellData?: () => unknown;
  getRange?: () => SelectionRange;
};

type SpreadsheetSelection = {
  getActiveRange: () => { getRange: () => SelectionRange } | null | undefined;
};

type SpreadsheetWorkbook = {
  getId: () => string;
  getSheets?: () => SpreadsheetWorksheet[];
  getSheetByName?: (name: string) => SpreadsheetWorksheet | null;
  insertSheet?: (name?: string) => SpreadsheetWorksheet;
  setActiveSheet?: (worksheet: SpreadsheetWorksheet | string) => unknown;
};

type SpreadsheetWorksheet = {
  getSheetId: () => string;
  getSheetName?: () => string;
  getMaxRows: () => number;
  getMaxColumns: () => number;
  getSelection: () => SpreadsheetSelection | null | undefined;
  getRange(a1Notation: string): SpreadsheetRange;
  getRange(row: number, column: number, numRows: number, numColumns: number): SpreadsheetRange;
  hideSheet?: () => SpreadsheetWorksheet;
  setFrozenRows: (rows: number) => unknown;
  setFrozenColumns: (columns: number) => unknown;
};

type SpreadsheetUniverApi = {
  executeCommand: <P extends object = object, R = boolean>(id: string, params?: P) => Promise<R>;
  getActiveSheet: () => unknown;
};

type SpreadsheetActionsContext = {
  univerAPI: SpreadsheetUniverApi;
  workbook: SpreadsheetWorkbook;
  getDefaultWorksheet: () => unknown;
};

export type SelectionRangeTarget = {
  range: SelectionRange;
  sortColumn: number;
  workbook: SpreadsheetWorkbook;
  worksheet: SpreadsheetWorksheet;
};

type SelectionSortTarget = SelectionRangeTarget & {
  sortRange: SelectionRange;
};

export type ChartWizardLegendPosition = 'top' | 'right' | 'bottom' | 'left' | 'hide';
export type ChartWizardDataOrientation = 'Row' | 'Column';

export type ChartWizardConfig = {
  chartType: 'line' | 'column' | 'bar';
  destinationSheet?: 'current-sheet' | string;
  chartLabel?: string;
  rangeA1?: string;
  title?: string;
  subtitle?: string;
  xAxisTitle?: string;
  yAxisTitle?: string;
  width?: number;
  height?: number;
  legendPosition?: ChartWizardLegendPosition;
  dataOrientation?: ChartWizardDataOrientation;
  useFirstRowAsHeader?: boolean;
  useFirstColumnAsLabel?: boolean;
};

export type PivotTableFieldInfo = {
  index: number;
  name: string;
  isNumeric: boolean;
};

export type PivotTableSourceInfo = {
  fields: PivotTableFieldInfo[];
  rangeA1: string;
  rowCount: number;
  columnCount: number;
};

export type PivotTableDataFunction = 'sum' | 'count' | 'average' | 'median' | 'max' | 'min' | 'product' | 'countNumbers';
export type PivotTableDestination = 'new-sheet' | 'existing-sheet';

export type PivotTableDataFieldConfig = {
  fieldIndex: number;
  function: PivotTableDataFunction;
  displayAs?: 'value' | 'percentOfGrandTotal';
};

export type PivotTableLayoutConfig = {
  filterFields: number[];
  rowFields: number[];
  columnFields: number[];
  dataFields: PivotTableDataFieldConfig[];
  destination: PivotTableDestination;
  destinationSheetName: string;
  destinationStartRow: number;
  destinationStartColumn: number;
};

export type PivotTableApplyResult = {
  ok: boolean;
  message?: string;
  sheetName?: string;
};

export type LineSparklineConfig = {
  sourceRange: string;
};

export type SpreadsheetTransposeConfig = {
  targetCell: string;
};

export type SpreadsheetValidationListConfig = {
  values: string[];
  allowBlank: boolean;
};

export function createSpreadsheetActions({ univerAPI, workbook, getDefaultWorksheet }: SpreadsheetActionsContext) {
  function normalizeSelectionRange(selectionRange: SelectionRange, maxRow: number, maxColumn: number) {
    const selectedAllRows = selectionRange.startRow <= 0 && selectionRange.endRow >= maxRow;
    const selectedAllColumns = selectionRange.startColumn <= 0 && selectionRange.endColumn >= maxColumn;

    if (selectedAllRows && !selectedAllColumns) {
      return {
        startRow: 0,
        endRow: maxRow,
        startColumn: Math.max(0, selectionRange.startColumn),
        endColumn: Math.min(maxColumn, selectionRange.endColumn),
      };
    }

    if (selectedAllColumns) {
      const startRow = Math.min(Math.max(selectionRange.startRow, 0), maxRow - 1);

      return {
        startRow,
        endRow: maxRow,
        startColumn: 0,
        endColumn: maxColumn,
      };
    }

    const startRow = Math.min(Math.max(selectionRange.startRow, 0), maxRow);
    const endRow = Math.min(Math.max(selectionRange.endRow, startRow), maxRow);
    const startColumn = Math.min(Math.max(selectionRange.startColumn, 0), maxColumn);
    const endColumn = Math.min(Math.max(selectionRange.endColumn, startColumn), maxColumn);

    return { startRow, endRow, startColumn, endColumn };
  }

  function getSelectionRangeTarget({ allowSingleRow = false } = {}): SelectionRangeTarget | null {
    const activeTarget = univerAPI.getActiveSheet() as
      | { workbook: SpreadsheetWorkbook; worksheet: SpreadsheetWorksheet }
      | null
      | undefined;
    const targetWorksheet = activeTarget?.worksheet ?? (getDefaultWorksheet() as SpreadsheetWorksheet);
    const selectionRange = targetWorksheet.getSelection()?.getActiveRange()?.getRange();
    const maxRow = targetWorksheet.getMaxRows() - 1;
    const maxColumn = targetWorksheet.getMaxColumns() - 1;

    if (!selectionRange || maxRow < 1 || maxColumn < 0) return null;

    const range = normalizeSelectionRange(selectionRange, maxRow, maxColumn);
    const hasInvalidRowRange = allowSingleRow ? range.endRow < range.startRow : range.endRow <= range.startRow;
    if (hasInvalidRowRange || range.endColumn < range.startColumn) return null;

    return {
      range,
      sortColumn: Math.min(Math.max(selectionRange.startColumn, range.startColumn), range.endColumn),
      workbook: activeTarget?.workbook ?? workbook,
      worksheet: targetWorksheet,
    };
  }

  function columnIndexToName(columnIndex: number) {
    let columnNumber = columnIndex + 1;
    let columnName = '';

    while (columnNumber > 0) {
      const remainder = (columnNumber - 1) % 26;
      columnName = String.fromCharCode(65 + remainder) + columnName;
      columnNumber = Math.floor((columnNumber - 1) / 26);
    }

    return columnName;
  }

  function selectionRangeToA1(range: SelectionRange) {
    return [
      columnIndexToName(range.startColumn),
      range.startRow + 1,
      ':',
      columnIndexToName(range.endColumn),
      range.endRow + 1,
    ].join('');
  }

  function valueToDisplayName(value: unknown, fallback: string) {
    const rawValue = readCellValue(value);
    if (rawValue === null || rawValue === undefined || rawValue === '') return fallback;

    return String(rawValue);
  }

  function readCellValue(value: unknown): unknown {
    if (!value || typeof value !== 'object') return value;

    const cellData = value as { v?: unknown; p?: unknown; f?: unknown };
    if (cellData.v !== undefined) return cellData.v;
    if (cellData.p !== undefined) return cellData.p;
    if (cellData.f !== undefined) return cellData.f;

    return value;
  }

  function readRangeValues(worksheet: SpreadsheetWorksheet, range: SelectionRange) {
    const rowCount = range.endRow - range.startRow + 1;
    const columnCount = range.endColumn - range.startColumn + 1;
    const facadeRange = worksheet.getRange(range.startRow, range.startColumn, rowCount, columnCount);
    const values = facadeRange.getValues?.();

    if (Array.isArray(values)) {
      return values.map((row) => Array.from({ length: columnCount }, (_, index) => readCellValue(row?.[index])));
    }

    return Array.from({ length: rowCount }, (_, rowOffset) =>
      Array.from({ length: columnCount }, (_, columnOffset) => {
        const cellRange = worksheet.getRange(range.startRow + rowOffset, range.startColumn + columnOffset, 1, 1);
        return readCellValue(cellRange.getValue?.() ?? cellRange.getCellData?.());
      }),
    );
  }

  function isNumericValue(value: unknown) {
    if (typeof value === 'number') return Number.isFinite(value);
    if (typeof value !== 'string' || value.trim() === '') return false;

    return Number.isFinite(Number(value));
  }

  function toNumber(value: unknown) {
    if (typeof value === 'number') return Number.isFinite(value) ? value : null;
    if (typeof value !== 'string' || value.trim() === '') return null;

    const parsedValue = Number(value);
    return Number.isFinite(parsedValue) ? parsedValue : null;
  }

  function getSelectionPivotSource(): PivotTableSourceInfo | null {
    const pivotTarget = getSelectionRangeTarget();
    if (!pivotTarget) return null;

    const { range } = pivotTarget;
    const rowCount = range.endRow - range.startRow + 1;
    const columnCount = range.endColumn - range.startColumn + 1;
    if (rowCount < 2 || columnCount < 1) return null;

    const values = readRangeValues(pivotTarget.worksheet, range);
    const dataRows = values.slice(1);
    const fields = Array.from({ length: columnCount }, (_, columnOffset) => {
      const absoluteColumn = range.startColumn + columnOffset;
      const fallback = `Column ${columnIndexToName(absoluteColumn)}`;
      const name = valueToDisplayName(values[0]?.[columnOffset], fallback);
      const isNumeric = dataRows.some((row) => isNumericValue(row?.[columnOffset]));

      return {
        index: columnOffset,
        name,
        isNumeric,
      };
    });

    return {
      fields,
      rangeA1: selectionRangeToA1(range),
      rowCount,
      columnCount,
    };
  }

  function getSelectionFacadeRange(rangeTarget: SelectionRangeTarget) {
    const { range, worksheet } = rangeTarget;

    return worksheet.getRange(
      range.startRow,
      range.startColumn,
      range.endRow - range.startRow + 1,
      range.endColumn - range.startColumn + 1,
    );
  }

  function applySelectionFontFamily(fontFamily: string) {
    const fontTarget = getSelectionRangeTarget({ allowSingleRow: true });
    if (!fontTarget) return;

    getSelectionFacadeRange(fontTarget).setFontFamily(fontFamily);
  }

  function applySelectionFontSize(fontSize: number) {
    if (!Number.isFinite(fontSize) || fontSize <= 0) return;

    const fontTarget = getSelectionRangeTarget({ allowSingleRow: true });
    if (!fontTarget) return;

    getSelectionFacadeRange(fontTarget).setFontSize(fontSize);
  }

  function applySelectionPercentFormat() {
    const formatTarget = getSelectionRangeTarget({ allowSingleRow: true });
    if (!formatTarget) return;

    getSelectionFacadeRange(formatTarget).setNumberFormat('0%');
  }

  function applySelectionNumberFormat() {
    const formatTarget = getSelectionRangeTarget({ allowSingleRow: true });
    if (!formatTarget) return;

    getSelectionFacadeRange(formatTarget).setNumberFormat('0.00');
  }

  function applySelectionDateFormat() {
    const formatTarget = getSelectionRangeTarget({ allowSingleRow: true });
    if (!formatTarget) return;

    getSelectionFacadeRange(formatTarget).setNumberFormat('yyyy-mm-dd');
  }

  function applySelectionInputValue(value: string) {
    const inputTarget = getSelectionRangeTarget({ allowSingleRow: true });
    if (!inputTarget) return { ok: false, message: 'Select a cell before entering a value.' };

    const { range, worksheet } = inputTarget;
    const cellAddress = `${columnIndexToName(range.startColumn)}${range.startRow + 1}`;
    const validation = _getCellValidationList(worksheet.getSheetId(), cellAddress);
    if (validation !== null && !Array.isArray(validation)) {
      const message = validationMessageForValue(value, validation);
      if (message !== null) return { ok: false, message };
    }

    worksheet.getRange(range.startRow, range.startColumn, 1, 1).setValue(value);
    return { ok: true };
  }

  function applySelectionValidationList(config: SpreadsheetValidationListConfig) {
    const validationTarget = getSelectionRangeTarget({ allowSingleRow: true });
    if (!validationTarget) return null;

    const { range, worksheet } = validationTarget;
    return _setCellValidationList(worksheet.getSheetId(), selectionRangeToA1(range), config);
  }

  function getSelectionValidationList() {
    const validationTarget = getSelectionRangeTarget({ allowSingleRow: true });
    if (!validationTarget) return null;

    const { range, worksheet } = validationTarget;
    return _getCellValidationList(worksheet.getSheetId(), selectionRangeToA1(range));
  }

  function removeSelectionValidationList() {
    const validationTarget = getSelectionRangeTarget({ allowSingleRow: true });
    if (!validationTarget) return null;

    const { range, worksheet } = validationTarget;
    return _setCellValidationList(worksheet.getSheetId(), selectionRangeToA1(range), null);
  }

  async function applySelectionMerge() {
    const mergeTarget = getSelectionRangeTarget({ allowSingleRow: true });
    if (!mergeTarget) return false;

    const { range } = mergeTarget;
    const rowCount = range.endRow - range.startRow + 1;
    const columnCount = range.endColumn - range.startColumn + 1;
    if (rowCount === 1 && columnCount === 1) return false;

    return univerAPI.executeCommand(mergeCellsCommandId);
  }

  async function applySelectionUnmerge() {
    const mergeTarget = getSelectionRangeTarget({ allowSingleRow: true });
    if (!mergeTarget) return false;

    return univerAPI.executeCommand(unmergeCellsCommandId);
  }

  function applySelectionFreeze() {
    const freezeTarget = getSelectionRangeTarget({ allowSingleRow: true });
    if (!freezeTarget) return false;

    const { range, worksheet } = freezeTarget;
    worksheet.setFrozenRows(range.startRow);
    worksheet.setFrozenColumns(range.startColumn);

    return true;
  }

  async function applySelectionFilter(filterTarget: SelectionRangeTarget | null = getSelectionRangeTarget()) {
    if (!filterTarget) return;

    const commandParams = {
      unitId: filterTarget.workbook.getId(),
      subUnitId: filterTarget.worksheet.getSheetId(),
    };

    await Promise.resolve(univerAPI.executeCommand(removeSheetFilterCommandId, commandParams)).catch(() => false);
    await univerAPI.executeCommand(setFilterRangeCommandId, {
      ...commandParams,
      range: filterTarget.range,
    });
  }

  async function applySelectionHeaderlessFilter() {
    const filterTarget = getSelectionRangeTarget();
    if (!filterTarget) return false;

    const { range } = filterTarget;

    await applySelectionFilter({
      ...filterTarget,
      range: {
        ...range,
        __surfgymHeaderless: true,
      },
    });

    return true;
  }

  function getSelectionSortTarget(): SelectionSortTarget | null {
    const filterTarget = getSelectionRangeTarget();
    if (!filterTarget) return null;

    return {
      ...filterTarget,
      sortRange: filterTarget.range,
    };
  }

  async function applySelectionSort(ascending: boolean) {
    const sortTarget = getSelectionSortTarget();
    if (!sortTarget) return;

    await applySelectionFilter(sortTarget);

    const { sortRange } = sortTarget;
    const rowCount = sortRange.endRow - sortRange.startRow + 1;
    const columnCount = sortRange.endColumn - sortRange.startColumn + 1;
    const sortColumn = sortTarget.sortColumn - sortRange.startColumn;

    sortTarget.worksheet
      .getRange(sortRange.startRow, sortRange.startColumn, rowCount, columnCount)
      .sort({ column: sortColumn, ascending });
  }

  async function applySelectionChart(config: ChartWizardConfig) {
    const chartTarget = getSelectionRangeTarget({ allowSingleRow: true });
    if (!chartTarget) return false;

    const requestedSourceRange = config.rangeA1?.trim() || selectionRangeToA1(chartTarget.range);
    const selectedSheet = chartTarget.worksheet.getSheetName?.() ?? chartTarget.worksheet.getSheetId();
    const sourceInfo = resolveAndReadChartSource(
      requestedSourceRange,
      (sourceSheet) => sourceSheet === selectedSheet
        ? chartTarget.worksheet
        : workbook.getSheetByName?.(sourceSheet),
      { defaultSheet: selectedSheet },
    );
    const sourceSheet = sourceInfo.sourceSheet;
    const requestedDestination = config.destinationSheet?.trim();
    const destinationWorksheet = !requestedDestination || requestedDestination === 'current-sheet'
      ? chartTarget.worksheet
      : workbook.getSheetByName?.(requestedDestination);
    if (!destinationWorksheet) return false;
    const destinationSheet = destinationWorksheet.getSheetName?.() ?? destinationWorksheet.getSheetId();
    const maxColumn = chartTarget.worksheet.getMaxColumns() - 1;
    const chartColumn = chartTarget.range.endColumn < maxColumn
      ? chartTarget.range.endColumn + 1
      : chartTarget.range.startColumn;
    const orientation = config.dataOrientation ?? (sourceInfo.isRowDirection ? 'Row' : 'Column');

    taskScopedLineCharts.create(destinationSheet, {
      chartType: config.chartType,
      sourceRange: sourceInfo.sourceRange,
      sourceSheet,
      dataOrientation: orientation,
      title: config.title?.trim() || config.chartLabel || `${config.chartType[0]!.toUpperCase()}${config.chartType.slice(1)} chart`,
      xAxisTitle: config.xAxisTitle?.trim() ?? '',
      yAxisTitle: config.yAxisTitle?.trim() ?? '',
      legendPosition: config.legendPosition ?? 'right',
      position: destinationSheet === sourceSheet
        ? { row: chartTarget.range.startRow, column: chartColumn, offsetX: 20, offsetY: 20 }
        : { row: 0, column: 0, offsetX: 20, offsetY: 20 },
      width: config.width ?? 560,
      height: config.height ?? 360,
      context: {
        useFirstColumnAsLabel: config.useFirstColumnAsLabel ?? true,
        useFirstRowAsHeader: config.useFirstRowAsHeader ?? true,
      },
    }, sourceInfo.matrix);

    return true;
  }

  async function updateTaskScopedChart(chartId: string, config: TaskScopedLineChartUpdate) {
    const current = taskScopedLineCharts.listAll().find((chart) => chart.id === chartId);
    if (!current) throw new Error(`Chart was not found: ${chartId}`);
    const worksheet = workbook.getSheetByName?.(current.sourceSheet)
      ?? getSelectionRangeTarget({ allowSingleRow: true })?.worksheet;
    if (!worksheet) throw new Error(`Chart source sheet was not found: ${current.sourceSheet}`);
    const requestedSourceRange = config.sourceRange ?? current.sourceRange;
    const sourceInfo = resolveAndReadChartSource(
      requestedSourceRange,
      (sourceSheet) => sourceSheet === current.sourceSheet
        ? worksheet
        : workbook.getSheetByName?.(sourceSheet),
      { defaultSheet: current.sourceSheet },
    );
    taskScopedLineCharts.update(current.sheet, { id: chartId }, {
      ...config,
      sourceRange: sourceInfo.sourceRange,
      sourceSheet: sourceInfo.sourceSheet,
    }, sourceInfo.matrix);
    return true;
  }

  function deleteTaskScopedChart(chartId: string) {
    const current = taskScopedLineCharts.listAll().find((chart) => chart.id === chartId);
    return current ? taskScopedLineCharts.delete(current.sheet, { id: chartId }) : false;
  }

  function getChartDestinationSheets() {
    return (workbook.getSheets?.() ?? [])
      .map((sheet) => sheet.getSheetName?.() ?? sheet.getSheetId())
      .filter((name, index, names) => Boolean(name) && names.indexOf(name) === index);
  }

  function columnNameToIndex(columnName: string) {
    return [...columnName].reduce((index, character) => index * 26 + character.charCodeAt(0) - 64, 0) - 1;
  }

  function parseRectangularA1Range(rangeA1: string) {
    const match = /^([A-Z]+)([1-9]\d*):([A-Z]+)([1-9]\d*)$/i.exec(rangeA1.trim());
    if (!match) throw new Error('Sparkline source must be one rectangular A1 range.');
    const startColumn = columnNameToIndex(match[1]!.toUpperCase());
    const endColumn = columnNameToIndex(match[3]!.toUpperCase());
    const startRow = Number(match[2]) - 1;
    const endRow = Number(match[4]) - 1;
    if (endColumn < startColumn || endRow < startRow) {
      throw new Error('Sparkline source range is reversed.');
    }
    return { startColumn, endColumn, startRow, endRow };
  }

  function parseSingleA1Target(targetCell: string) {
    const match = /^([A-Z]+)([1-9]\d*)$/i.exec(targetCell.trim());
    if (!match) throw new Error('Transpose target must be one A1 cell.');
    return { column: columnNameToIndex(match[1]!.toUpperCase()), row: Number(match[2]) - 1 };
  }

  function rangesIntersect(left: SelectionRange, right: SelectionRange) {
    return left.startRow <= right.endRow && right.startRow <= left.endRow &&
      left.startColumn <= right.endColumn && right.startColumn <= left.endColumn;
  }

  async function applySelectionTranspose(config: SpreadsheetTransposeConfig) {
    const source = getSelectionRangeTarget({ allowSingleRow: true });
    if (!source) throw new Error('Select a source range before transposing.');

    const target = parseSingleA1Target(config.targetCell);
    const sourceRowCount = source.range.endRow - source.range.startRow + 1;
    const sourceColumnCount = source.range.endColumn - source.range.startColumn + 1;
    const destinationRange: SelectionRange = {
      startRow: target.row,
      endRow: target.row + sourceColumnCount - 1,
      startColumn: target.column,
      endColumn: target.column + sourceRowCount - 1,
    };
    if (destinationRange.endRow >= source.worksheet.getMaxRows() || destinationRange.endColumn >= source.worksheet.getMaxColumns()) {
      throw new Error('Transpose target is outside the worksheet bounds.');
    }
    if (rangesIntersect(source.range, destinationRange)) {
      throw new Error('Transpose target overlaps the selected source range.');
    }

    const sourceValues = readRangeValues(source.worksheet, source.range);
    const transposed = Array.from(
      { length: sourceColumnCount },
      (_, columnOffset) => Array.from(
        { length: sourceRowCount },
        (_, rowOffset) => sourceValues[rowOffset]?.[columnOffset] ?? null,
      ),
    );
    source.worksheet
      .getRange(target.row, target.column, sourceColumnCount, sourceRowCount)
      .setValues(transposed);
    return true;
  }

  async function applySelectionLineSparklines(config: LineSparklineConfig) {
    const target = getSelectionRangeTarget({ allowSingleRow: true });
    if (!target) return false;
    if (target.range.startColumn !== target.range.endColumn) {
      throw new Error('Select one target column for line sparklines.');
    }
    const source = parseRectangularA1Range(config.sourceRange);
    const targetRowCount = target.range.endRow - target.range.startRow + 1;
    const sourceRowCount = source.endRow - source.startRow + 1;
    if (sourceRowCount !== targetRowCount) {
      throw new Error('Sparkline source and target rows must have matching counts.');
    }
    const sheet = target.worksheet.getSheetName?.() ?? target.worksheet.getSheetId();
    const sourceStartColumn = columnIndexToName(source.startColumn);
    const sourceEndColumn = columnIndexToName(source.endColumn);
    const targetColumn = columnIndexToName(target.range.startColumn);

    for (let offset = 0; offset < targetRowCount; offset += 1) {
      const sourceRow = source.startRow + offset + 1;
      const targetRow = target.range.startRow + offset + 1;
      const targetCell = `${targetColumn}${targetRow}`;
      taskScopedLineSparklines.set(sheet, targetCell, 'sourceRange', `${sourceStartColumn}${sourceRow}:${sourceEndColumn}${sourceRow}`);
      taskScopedLineSparklines.set(sheet, targetCell, 'type', 'line');
    }
    return true;
  }

  function getPivotFunctionLabel(dataFunction: PivotTableDataFunction) {
    const labels: Record<PivotTableDataFunction, string> = {
      average: 'Average',
      count: 'Count',
      countNumbers: 'Count (Numbers only)',
      max: 'Max',
      median: 'Median',
      min: 'Min',
      product: 'Product',
      sum: 'Sum',
    };

    return labels[dataFunction];
  }

  function aggregatePivotValues(values: unknown[], dataFunction: PivotTableDataFunction) {
    const nonEmptyValues = values.filter((value) => value !== null && value !== undefined && value !== '');
    const numbers = nonEmptyValues
      .map(toNumber)
      .filter((value): value is number => value !== null);

    if (dataFunction === 'count') return nonEmptyValues.length;
    if (dataFunction === 'countNumbers') return numbers.length;
    if (numbers.length === 0) return '';
    if (dataFunction === 'sum') return numbers.reduce((total, value) => total + value, 0);
    if (dataFunction === 'average') return numbers.reduce((total, value) => total + value, 0) / numbers.length;
    if (dataFunction === 'max') return Math.max(...numbers);
    if (dataFunction === 'min') return Math.min(...numbers);
    if (dataFunction === 'product') return numbers.reduce((total, value) => total * value, 1);

    const sortedNumbers = [...numbers].sort((a, b) => a - b);
    const middleIndex = Math.floor(sortedNumbers.length / 2);
    if (sortedNumbers.length % 2 === 1) return sortedNumbers[middleIndex] ?? '';

    const leftValue = sortedNumbers[middleIndex - 1] ?? 0;
    const rightValue = sortedNumbers[middleIndex] ?? leftValue;

    return (leftValue + rightValue) / 2;
  }

  function fieldKey(row: unknown[], fieldIndexes: number[]) {
    if (fieldIndexes.length === 0) return ['Total'];

    return fieldIndexes.map((fieldIndex) => {
      const value = row[fieldIndex];
      if (value === null || value === undefined || value === '') return '(empty)';

      return String(value);
    });
  }

  function writePivotMatrix(
    worksheet: SpreadsheetWorksheet,
    matrix: (string | number)[][],
    startRow: number,
    startColumn: number,
    percentageCells: Set<string>,
  ) {
    matrix.forEach((row, rowOffset) => {
      row.forEach((value, columnOffset) => {
        const target = worksheet.getRange(startRow + rowOffset, startColumn + columnOffset, 1, 1);
        target.setValue(value);
        if (percentageCells.has(`${rowOffset}:${columnOffset}`) && value !== '') target.setNumberFormat('0.00%');
      });
    });
  }

  async function applySelectionPivotTable(config: PivotTableLayoutConfig): Promise<PivotTableApplyResult> {
    const pivotTarget = getSelectionRangeTarget();
    if (!pivotTarget) {
      return { ok: false, message: 'Select a source range before creating a pivot table.' };
    }

    const { range, worksheet: sourceWorksheet } = pivotTarget;
    const values = readRangeValues(sourceWorksheet, range);
    const sourceInfo = getSelectionPivotSource();
    if (!sourceInfo || values.length < 2) {
      return { ok: false, message: 'The source range needs a header row and at least one data row.' };
    }

    if (config.dataFields.length === 0) {
      return { ok: false, message: 'Add at least one field to Data Fields.' };
    }

    const destinationSheetName = config.destinationSheetName.trim();
    if (!destinationSheetName) return { ok: false, message: 'Choose a destination sheet.' };
    if (!Number.isInteger(config.destinationStartRow) || config.destinationStartRow < 0 ||
      !Number.isInteger(config.destinationStartColumn) || config.destinationStartColumn < 0) {
      return { ok: false, message: 'Destination cell must be a non-negative A1 position.' };
    }

    const outputWorksheet = config.destination === 'new-sheet'
      ? (workbook.insertSheet?.(destinationSheetName) ?? null)
      : (workbook.getSheetByName?.(destinationSheetName) ?? null);
    if (!outputWorksheet) return { ok: false, message: `Destination sheet not found: ${destinationSheetName}` };
    if (config.destinationStartRow >= outputWorksheet.getMaxRows() || config.destinationStartColumn >= outputWorksheet.getMaxColumns()) {
      return { ok: false, message: 'Destination cell is outside the target sheet.' };
    }

    const dataRows = values.slice(1);
    const rowFields = config.rowFields;
    const columnFields = config.columnFields;
    const dataFields = config.dataFields;
    const rowGroupMap = new Map<string, { labels: string[]; rows: unknown[][] }>();
    const columnGroupMap = new Map<string, string[]>();

    dataRows.forEach((row) => {
      const rowLabels = fieldKey(row, rowFields);
      const rowKey = rowLabels.join('\u0001');
      const existingRowGroup = rowGroupMap.get(rowKey);

      if (existingRowGroup) {
        existingRowGroup.rows.push(row);
      } else {
        rowGroupMap.set(rowKey, { labels: rowLabels, rows: [row] });
      }

      const columnLabels = fieldKey(row, columnFields);
      const columnKey = columnLabels.join('\u0001');
      if (!columnGroupMap.has(columnKey)) columnGroupMap.set(columnKey, columnLabels);
    });

    const rowGroups = [...rowGroupMap.values()];
    const columnGroups: [string, string[]][] = columnFields.length > 0 ? [...columnGroupMap.entries()] : [['', ['']]];
    const rowHeaders = rowFields.length > 0
      ? rowFields.map((fieldIndex) => sourceInfo.fields[fieldIndex]?.name ?? `Field ${fieldIndex + 1}`)
      : ['Total'];
    const valueHeaders = columnGroups.flatMap(([, columnLabels]) =>
      dataFields.map((dataField) => {
        const fieldName = sourceInfo.fields[dataField.fieldIndex]?.name ?? `Field ${dataField.fieldIndex + 1}`;
        const valueName = `${getPivotFunctionLabel(dataField.function)} - ${fieldName}`;
        const columnName = columnFields.length > 0 ? columnLabels.join(' / ') : '';

        return columnName ? `${columnName} ${valueName}` : valueName;
      }),
    );
    const percentageCells = new Set<string>();
    const matrix: (string | number)[][] = [
      [...rowHeaders, ...valueHeaders],
      ...rowGroups.map((rowGroup) => [
        ...rowGroup.labels,
        ...columnGroups.flatMap(([columnKey]) => {
          const matchingRows = columnFields.length > 0
            ? rowGroup.rows.filter((row) => fieldKey(row, columnFields).join('\u0001') === columnKey)
            : rowGroup.rows;

          return dataFields.map((dataField, dataFieldIndex) => {
            const aggregate = aggregatePivotValues(matchingRows.map((row) => row[dataField.fieldIndex]), dataField.function);
            if (dataField.displayAs !== 'percentOfGrandTotal') return aggregate;
            const grandTotal = aggregatePivotValues(dataRows.map((row) => row[dataField.fieldIndex]), dataField.function);
            const matrixColumn = rowFields.length + columnGroups.findIndex(([key]) => key === columnKey) * dataFields.length + dataFieldIndex;
            percentageCells.add(`${rowGroups.indexOf(rowGroup) + 1}:${matrixColumn}`);
            return typeof aggregate === 'number' && typeof grandTotal === 'number' && Number.isFinite(grandTotal) && grandTotal !== 0
              ? aggregate / grandTotal
              : '';
          });
        }),
      ]),
    ];
    const startRow = config.destinationStartRow;
    const startColumn = config.destinationStartColumn;
    const endRow = startRow + matrix.length - 1;
    const endColumn = startColumn + Math.max(...matrix.map((row) => row.length)) - 1;
    if (endRow >= outputWorksheet.getMaxRows() || endColumn >= outputWorksheet.getMaxColumns()) {
      return { ok: false, message: 'Pivot output does not fit in the target sheet.' };
    }
    for (let row = startRow; row <= endRow; row += 1) for (let column = startColumn; column <= endColumn; column += 1) {
      const existingValue = outputWorksheet.getRange(row, column, 1, 1).getValue?.();
      if (existingValue !== undefined && existingValue !== null && existingValue !== '') {
        return { ok: false, message: 'Pivot output would overwrite existing cells.' };
      }
    }
    writePivotMatrix(outputWorksheet, matrix, startRow, startColumn, percentageCells);
    _registerPivotMeta({
      sourceRange: sourceInfo.rangeA1, rowFields, columnFields,
      dataFields: dataFields.map((field) => ({ ...field, displayAs: field.displayAs ?? 'value' })),
      targetSheet: destinationSheetName, startRow, startColumn,
    });
    return { ok: true, sheetName: destinationSheetName };
  }

  async function applySelectionBarChart() {
    await applySelectionChart({
      chartType: 'bar',
      chartLabel: 'Bar Chart',
      title: 'Bar Chart',
    });
  }

  return {
    applySelectionBarChart,
    applySelectionChart,
    applySelectionLineSparklines,
    deleteTaskScopedChart,
    applySelectionDateFormat,
    applySelectionFilter,
    applySelectionFreeze,
    applySelectionHeaderlessFilter,
    applySelectionFontFamily,
    applySelectionFontSize,
    applySelectionInputValue,
    applySelectionMerge,
    applySelectionNumberFormat,
    applySelectionPercentFormat,
    applySelectionPivotTable,
    applySelectionSort,
    applySelectionTranspose,
    applySelectionUnmerge,
    applySelectionValidationList,
    columnIndexToName,
    getSelectionPivotSource,
    getChartDestinationSheets,
    getSelectionRangeTarget,
    getSelectionValidationList,
    removeSelectionValidationList,
    updateTaskScopedChart,
  };
}

export type SpreadsheetActions = ReturnType<typeof createSpreadsheetActions>;
