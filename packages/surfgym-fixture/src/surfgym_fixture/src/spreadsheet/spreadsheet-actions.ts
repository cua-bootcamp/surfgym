import { ChartTypeBits } from '@univerjs/presets/preset-sheets-advanced';

const setFilterRangeCommandId = 'sheet.command.set-filter-range';
const removeSheetFilterCommandId = 'sheet.command.remove-sheet-filter';

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
  build: () => unknown;
};

type SpreadsheetRange = {
  sort: (options: { column: number; ascending: boolean }) => unknown;
  setFontFamily: (fontFamily: string | null) => unknown;
  setFontSize: (fontSize: number | null) => unknown;
  setNumberFormat: (pattern: string) => unknown;
  setValue: (value: string) => unknown;
};

type SpreadsheetSelection = {
  getActiveRange: () => { getRange: () => SelectionRange } | null | undefined;
};

type SpreadsheetWorkbook = {
  getId: () => string;
};

type SpreadsheetWorksheet = {
  getSheetId: () => string;
  getMaxRows: () => number;
  getMaxColumns: () => number;
  getSelection: () => SpreadsheetSelection | null | undefined;
  getRange: (row: number, column: number, numRows: number, numColumns: number) => SpreadsheetRange;
  newChart: () => SpreadsheetChartBuilder;
  insertChart: (chartInfo: unknown) => Promise<unknown> | unknown;
};

type SpreadsheetUniverApi = {
  executeCommand: <P extends object = object, R = boolean>(id: string, params?: P) => Promise<R>;
  getActiveSheet: () => unknown;
};

type SpreadsheetActionsContext = {
  univerAPI: SpreadsheetUniverApi;
  workbook: SpreadsheetWorkbook;
  worksheet: unknown;
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

export function createSpreadsheetActions({ univerAPI, workbook, worksheet }: SpreadsheetActionsContext) {
  const defaultWorksheet = worksheet as SpreadsheetWorksheet;

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
    const targetWorksheet = activeTarget?.worksheet ?? defaultWorksheet;
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

  async function applySelectionChart(config: ChartWizardConfig) {
    const chartTarget = getSelectionRangeTarget({ allowSingleRow: true });
    if (!chartTarget) return false;

    const { range } = chartTarget;
    const maxColumn = chartTarget.worksheet.getMaxColumns() - 1;
    const chartColumn = range.endColumn < maxColumn ? range.endColumn + 1 : range.startColumn;
    const title = config.title?.trim() || config.chartLabel || 'Chart';
    const subtitle = config.subtitle?.trim();
    const xAxisTitle = config.xAxisTitle?.trim();
    const yAxisTitle = config.yAxisTitle?.trim();
    let chartBuilder = chartTarget.worksheet.newChart()
      .setChartType(config.chartType)
      .addRange(config.rangeA1?.trim() || selectionRangeToA1(range))
      .setPosition(range.startRow, chartColumn, 20, 20)
      .setWidth(config.width ?? 560)
      .setHeight(config.height ?? 360);

    chartBuilder = setChartOption(chartBuilder, 'title.content', title);
    chartBuilder = setChartOption(chartBuilder, 'titles.title.content', title);
    chartBuilder = setChartOption(chartBuilder, 'titles.subtitle.content', subtitle);
    chartBuilder = setChartOption(chartBuilder, 'titles.xAxisTitle.content', xAxisTitle);
    chartBuilder = setChartOption(chartBuilder, 'titles.yAxisTitle.content', yAxisTitle);
    chartBuilder = setChartOption(chartBuilder, 'legend.position', config.legendPosition ?? 'right');
    chartBuilder = setChartOption(chartBuilder, 'orient', config.dataOrientation ?? 'Column');

    if (config.useFirstColumnAsLabel) {
      chartBuilder = setChartOption(chartBuilder, 'context.categoryIndex', 0);
      chartBuilder = setChartOption(chartBuilder, 'context.transform.categoryIndex', 0);
    }

    if (config.useFirstRowAsHeader) {
      chartBuilder = setChartOption(chartBuilder, 'context.useFirstRowAsHeader', true);
    }

    const chartInfo = chartBuilder.build();

    await chartTarget.worksheet.insertChart(chartInfo);
    return true;
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
    applySelectionSort,
    columnIndexToName,
    getSelectionRangeTarget,
  };
}

export type SpreadsheetActions = ReturnType<typeof createSpreadsheetActions>;
