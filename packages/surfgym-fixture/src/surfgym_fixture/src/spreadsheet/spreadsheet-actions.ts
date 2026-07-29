import { ChartTypeBits } from '@univerjs/presets/preset-sheets-advanced';

const setFilterRangeCommandId = 'sheet.command.set-filter-range';
const removeSheetFilterCommandId = 'sheet.command.remove-sheet-filter';
const chartUpdateConfigCommandId = 'sheet.command.chart-update-config';

export type SelectionRange = {
  startRow: number;
  endRow: number;
  startColumn: number;
  endColumn: number;
  __surfgymHeaderless?: boolean;
};

type SpreadsheetChartBuilder = {
  setChartType: (chartType: ChartTypeBits) => SpreadsheetChartBuilder;
  addRange: (range: string) => SpreadsheetChartBuilder;
  setPosition: (row: number, column: number, offsetX: number, offsetY: number) => SpreadsheetChartBuilder;
  setWidth: (width: number) => SpreadsheetChartBuilder;
  setHeight: (height: number) => SpreadsheetChartBuilder;
  setOptions: (path: string, value: unknown) => SpreadsheetChartBuilder;
  setTransposeRowsAndColumns?: (transposeRowsAndColumns: boolean) => SpreadsheetChartBuilder;
  setXAxisTitle?: (title: string) => SpreadsheetChartBuilder;
  setYAxisTitle?: (title: string) => SpreadsheetChartBuilder;
  build: () => unknown;
};

type SpreadsheetChart = {
  getChartId?: () => string;
};

type SpreadsheetChartContext = {
  headers?: string[];
  categoryIndex?: number;
  seriesIndexes?: number[];
  transform?: {
    categoryIndex?: number;
    seriesIndexes?: number[];
  };
};

type SpreadsheetCellValue = string | number | boolean | null;
type SpreadsheetCellData = {
  v: SpreadsheetCellValue;
};
type SpreadsheetSheetData = {
  cellData: Record<number, Record<number, SpreadsheetCellData>>;
};
type SpreadsheetInsertSheetOptions = {
  index?: number;
  sheet?: Partial<SpreadsheetSheetData>;
};

type SpreadsheetRange = {
  sort: (options: { column: number; ascending: boolean }) => unknown;
  setFontFamily: (fontFamily: string | null) => unknown;
  setFontSize: (fontSize: number | null) => unknown;
  setNumberFormat: (pattern: string) => unknown;
  setValue: (value: string | number | boolean | null) => unknown;
  getValue?: () => unknown;
  getValues?: () => unknown[][];
  getCellData?: () => unknown;
};

type SpreadsheetSelection = {
  getActiveRange: () => { getRange: () => SelectionRange } | null | undefined;
};

type SpreadsheetWorkbook = {
  getId: () => string;
  insertSheet?: (name?: string, options?: SpreadsheetInsertSheetOptions) => SpreadsheetWorksheet;
};

type SpreadsheetWorksheet = {
  getSheetId: () => string;
  getSheetName?: () => string;
  getMaxRows: () => number;
  getMaxColumns: () => number;
  getSelection: () => SpreadsheetSelection | null | undefined;
  getRange: (row: number, column: number, numRows: number, numColumns: number) => SpreadsheetRange;
  hideSheet?: () => SpreadsheetWorksheet;
  newChart: () => SpreadsheetChartBuilder;
  insertChart: (chartInfo: unknown) => Promise<SpreadsheetChart | unknown> | SpreadsheetChart | unknown;
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
  chartType: ChartTypeBits;
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
};

export type PivotTableLayoutConfig = {
  filterFields: number[];
  rowFields: number[];
  columnFields: number[];
  dataFields: PivotTableDataFieldConfig[];
  destination: PivotTableDestination;
};

export type PivotTableApplyResult = {
  ok: boolean;
  message?: string;
  sheetName?: string;
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
    if (!inputTarget) return;

    const { range, worksheet } = inputTarget;

    worksheet.getRange(range.startRow, range.startColumn, 1, 1).setValue(value);
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

  function setChartOption(builder: SpreadsheetChartBuilder, path: string, value: unknown) {
    if (value === undefined || value === null || value === '') return builder;

    return builder.setOptions(path, value);
  }

  function normalizeChartCellValue(value: unknown): SpreadsheetCellValue {
    const rawValue = readCellValue(value);
    if (rawValue === null || rawValue === undefined) return null;
    if (typeof rawValue === 'string' || typeof rawValue === 'number' || typeof rawValue === 'boolean') return rawValue;

    return String(rawValue);
  }

  function buildChartHelperMatrix(values: unknown[][], config: ChartWizardConfig) {
    let matrix = values.map((row) => row.map(normalizeChartCellValue));
    const originalColumnCount = matrix[0]?.length ?? 0;

    if (config.useFirstRowAsHeader === false) {
      const generatedHeader = Array.from({ length: originalColumnCount }, (_, columnIndex) => {
        if (columnIndex === 0 && config.useFirstColumnAsLabel) return 'Category';

        return `Series ${config.useFirstColumnAsLabel ? columnIndex : columnIndex + 1}`;
      });
      matrix = [generatedHeader, ...matrix];
    }

    if (config.useFirstColumnAsLabel === false) {
      matrix = matrix.map((row, rowIndex) => [
        rowIndex === 0 ? 'Category' : `Item ${rowIndex}`,
        ...row,
      ]);
    }

    return matrix;
  }

  function matrixToSheetData(matrix: SpreadsheetCellValue[][]): SpreadsheetSheetData {
    return {
      cellData: matrix.reduce<Record<number, Record<number, SpreadsheetCellData>>>((rows, row, rowIndex) => {
        rows[rowIndex] = row.reduce<Record<number, SpreadsheetCellData>>((columns, value, columnIndex) => {
          columns[columnIndex] = { v: value };

          return columns;
        }, {});

        return rows;
      }, {}),
    };
  }

  function uniqueChartDataSheetName() {
    const suffix = Math.floor(Date.now() % 100_000).toString().padStart(5, '0');

    return `_SurfgymChartData${suffix}`;
  }

  function createChartSourceRange(
    chartTarget: SelectionRangeTarget,
    config: ChartWizardConfig,
    rowCount: number,
    columnCount: number,
  ) {
    const selectionA1 = selectionRangeToA1(chartTarget.range);
    const requestedRangeA1 = config.rangeA1?.trim();
    const canRewriteSource = !requestedRangeA1 || requestedRangeA1 === selectionA1;
    const needsHelperSource = config.useFirstRowAsHeader === false || config.useFirstColumnAsLabel === false;

    if (!canRewriteSource || !needsHelperSource || !chartTarget.workbook.insertSheet) {
      return {
        contextConfig: config,
        columnCount,
        rangeA1: requestedRangeA1 || selectionA1,
        rowCount,
      };
    }

    const helperMatrix = buildChartHelperMatrix(readRangeValues(chartTarget.worksheet, chartTarget.range), config);
    const helperRowCount = helperMatrix.length;
    const helperColumnCount = helperMatrix[0]?.length ?? 0;

    if (helperRowCount === 0 || helperColumnCount === 0) {
      return {
        contextConfig: config,
        columnCount,
        rangeA1: selectionA1,
        rowCount,
      };
    }

    const helperSheetName = uniqueChartDataSheetName();
    const helperWorksheet = chartTarget.workbook.insertSheet(helperSheetName, {
      sheet: matrixToSheetData(helperMatrix),
    });
    helperWorksheet.hideSheet?.();

    return {
      contextConfig: {
        ...config,
        useFirstColumnAsLabel: true,
        useFirstRowAsHeader: true,
      },
      columnCount: helperColumnCount,
      rangeA1: `${helperSheetName}!A1:${columnIndexToName(helperColumnCount - 1)}${helperRowCount}`,
      rowCount: helperRowCount,
    };
  }

  function buildChartContext(
    config: ChartWizardConfig,
    rowCount: number,
    columnCount: number,
    isRowDirection: boolean,
  ): SpreadsheetChartContext {
    const dimensionCount = isRowDirection ? columnCount : rowCount;
    const seriesStartIndex = config.useFirstColumnAsLabel ? 1 : 0;
    const seriesIndexes = Array.from(
      { length: Math.max(0, dimensionCount - seriesStartIndex) },
      (_, index) => index + seriesStartIndex,
    );
    const context: SpreadsheetChartContext = {};

    if (config.useFirstColumnAsLabel) {
      context.categoryIndex = 0;
      context.transform = { categoryIndex: 0 };
    }

    if (seriesIndexes.length > 0) {
      context.seriesIndexes = seriesIndexes;
      context.transform = {
        ...(context.transform ?? {}),
        seriesIndexes,
      };
    }

    if (config.useFirstRowAsHeader === false) {
      context.headers = seriesIndexes.map((_, index) => `Series ${index + 1}`);
    }

    return context;
  }

  function getChartId(chart: SpreadsheetChart | unknown) {
    if (!chart || typeof chart !== 'object') return undefined;

    const getChartIdMethod = (chart as SpreadsheetChart).getChartId;
    if (!getChartIdMethod) return undefined;

    return getChartIdMethod.call(chart);
  }

  async function applySelectionChart(config: ChartWizardConfig) {
    const chartTarget = getSelectionRangeTarget({ allowSingleRow: true });
    if (!chartTarget) return false;

    const { range } = chartTarget;
    const rowCount = range.endRow - range.startRow + 1;
    const columnCount = range.endColumn - range.startColumn + 1;
    const hasOnlyOneCell = rowCount === 1 && columnCount === 1;
    const hasOnlyOneColumn = columnCount === 1;

    if (hasOnlyOneCell || hasOnlyOneColumn) return false;

    const maxColumn = chartTarget.worksheet.getMaxColumns() - 1;
    const chartColumn = range.endColumn < maxColumn ? range.endColumn + 1 : range.startColumn;
    const title = config.title?.trim() || config.chartLabel || 'Chart';
    const xAxisTitle = config.xAxisTitle?.trim();
    const yAxisTitle = config.yAxisTitle?.trim();
    const dataOrientation = config.dataOrientation ?? 'Column';
    const chartSource = createChartSourceRange(chartTarget, config, rowCount, columnCount);
    const isRowDirection = chartSource.rowCount === 1 || dataOrientation === 'Column';
    const chartContext = buildChartContext(
      chartSource.contextConfig,
      chartSource.rowCount,
      chartSource.columnCount,
      isRowDirection,
    );
    let chartBuilder = chartTarget.worksheet.newChart()
      .setChartType(config.chartType)
      .addRange(chartSource.rangeA1)
      .setPosition(range.startRow, chartColumn, 20, 20)
      .setWidth(config.width ?? 560)
      .setHeight(config.height ?? 360);

    chartBuilder = setChartOption(chartBuilder, 'title.content', title);
    chartBuilder = setChartOption(chartBuilder, 'legend.position', config.legendPosition ?? 'right');
    chartBuilder = setChartOption(chartBuilder, 'orient', dataOrientation);

    if (chartBuilder.setTransposeRowsAndColumns) {
      chartBuilder = chartBuilder.setTransposeRowsAndColumns(isRowDirection);
    }

    if (xAxisTitle && chartBuilder.setXAxisTitle) {
      chartBuilder = chartBuilder.setXAxisTitle(xAxisTitle);
    }

    if (yAxisTitle && chartBuilder.setYAxisTitle) {
      chartBuilder = chartBuilder.setYAxisTitle(yAxisTitle);
    }

    const chartInfo = chartBuilder.build();
    const insertedChart = await chartTarget.worksheet.insertChart(chartInfo);
    const chartId = getChartId(insertedChart);

    if (chartId) {
      await univerAPI.executeCommand(chartUpdateConfigCommandId, {
        unitId: chartTarget.workbook.getId(),
        chartModelId: chartId,
        context: chartContext,
      });
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

  function uniquePivotSheetName(baseName = 'Pivot Table') {
    const suffix = Math.floor(Date.now() % 100_000).toString().padStart(5, '0');

    return `${baseName} ${suffix}`;
  }

  function writePivotMatrix(worksheet: SpreadsheetWorksheet, matrix: (string | number)[][], startRow = 0, startColumn = 0) {
    matrix.forEach((row, rowOffset) => {
      row.forEach((value, columnOffset) => {
        worksheet.getRange(startRow + rowOffset, startColumn + columnOffset, 1, 1).setValue(value);
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
    const matrix: (string | number)[][] = [
      [...rowHeaders, ...valueHeaders],
      ...rowGroups.map((rowGroup) => [
        ...rowGroup.labels,
        ...columnGroups.flatMap(([columnKey]) => {
          const matchingRows = columnFields.length > 0
            ? rowGroup.rows.filter((row) => fieldKey(row, columnFields).join('\u0001') === columnKey)
            : rowGroup.rows;

          return dataFields.map((dataField) => aggregatePivotValues(
            matchingRows.map((row) => row[dataField.fieldIndex]),
            dataField.function,
          ));
        }),
      ]),
    ];

    const outputSheetName = config.destination === 'new-sheet' ? uniquePivotSheetName() : sourceWorksheet.getSheetName?.();
    const outputWorksheet = config.destination === 'new-sheet' && workbook.insertSheet
      ? workbook.insertSheet(outputSheetName)
      : sourceWorksheet;
    const startRow = config.destination === 'new-sheet' ? 0 : range.startRow;
    const startColumn = config.destination === 'new-sheet' ? 0 : Math.min(sourceWorksheet.getMaxColumns() - 1, range.endColumn + 2);

    writePivotMatrix(outputWorksheet, matrix, startRow, startColumn);

    return outputSheetName ? { ok: true, sheetName: outputSheetName } : { ok: true };
  }

  async function applySelectionBarChart() {
    await applySelectionChart({
      chartType: ChartTypeBits.Bar,
      chartLabel: 'Bar Chart',
      title: 'Bar Chart',
    });
  }

  return {
    applySelectionBarChart,
    applySelectionChart,
    applySelectionDateFormat,
    applySelectionFilter,
    applySelectionHeaderlessFilter,
    applySelectionFontFamily,
    applySelectionFontSize,
    applySelectionInputValue,
    applySelectionNumberFormat,
    applySelectionPercentFormat,
    applySelectionPivotTable,
    applySelectionSort,
    columnIndexToName,
    getSelectionPivotSource,
    getSelectionRangeTarget,
  };
}

export type SpreadsheetActions = ReturnType<typeof createSpreadsheetActions>;
