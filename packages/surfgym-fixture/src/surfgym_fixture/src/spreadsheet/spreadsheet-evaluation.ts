// import { ChartTypeBits } from "@univerjs/presets/preset-sheets-advanced";
// import type { SelectionRange, SpreadsheetActions } from "./spreadsheet-actions";

// const markDirtyFilterChangeMutationId = "sheet.mutation.mark-dirty-filter-change";
// const chartUpdateConfigCommandId = "sheet.command.chart-update-config";

// type RowMeta = {
//   filtered: boolean;
//   visible: boolean;
//   rawVisible: boolean;
//   filterRange: string | null;
// };

// type CellMeta = {
//   cell: unknown;
//   style: unknown;
//   row: RowMeta;
// };

// type SheetTarget = {
//   sheetId?: string;
//   sheetName?: string;
//   sheetIndex?: number;
// };

// type CellMetaTarget = SheetTarget & {
//   address: string;
// };

// type SheetMeta = {
//   sheet: {
//     id: string;
//     name: string | null;
//     index: number | null;
//     rowCount: number;
//     columnCount: number;
//     hidden: boolean | null;
//     gridlinesHidden: boolean | null;
//     gridlinesColor: string | null;
//     tabColor: string | null;
//     freeze: unknown;
//     filterRange: string | null;
//   };
// };

// type ChartPositionMeta = {
//   row: number;
//   column: number;
//   offsetX: number;
//   offsetY: number;
// };

// type ChartMeta = {
//   id: string | null;
//   sheetId: string;
//   sheetName: string | null;
//   index: number | null;
//   chartType: unknown;
//   sourceRange: string | null;
//   range: unknown;
//   title: string | null;
//   legendPosition: unknown;
//   dataOrientation: unknown;
//   width: number | null;
//   height: number | null;
//   position: ChartPositionMeta | null;
//   context: unknown;
//   seriesData: unknown;
//   categoryData: unknown;
// };

// type SpreadsheetCellMetaEntry = CellMetaTarget & {
//   cell?: unknown;
//   style?: unknown;
//   row?: Partial<RowMeta>;
// };

// type SpreadsheetSheetMetaEntry = SheetTarget & {
//   name?: string;
//   rowCount?: number;
//   columnCount?: number;
//   hidden?: boolean;
//   gridlinesHidden?: boolean;
//   gridlinesColor?: string | null;
//   tabColor?: string | null;
//   freeze?: unknown;
// };

// type SpreadsheetChartMetaEntry = SheetTarget & {
//   chartType?: unknown;
//   sourceRange?: string;
//   rangeA1?: string;
//   title?: string;
//   legendPosition?: unknown;
//   dataOrientation?: unknown;
//   width?: number;
//   height?: number;
//   position?: Partial<ChartPositionMeta>;
//   context?: unknown;
//   xAxisTitle?: string;
//   yAxisTitle?: string;
//   transposeRowsAndColumns?: boolean;
// };

// type SpreadsheetWorkbook = {
//   getId: () => string;
//   getSheets?: () => SpreadsheetEvaluationWorksheet[];
//   getSheetByName?: (sheetName: string) => SpreadsheetEvaluationWorksheet | null;
//   getSheetBySheetName?: (sheetName: string) => SpreadsheetEvaluationWorksheet | null;
//   getSheetBySheetId?: (sheetId: string) => SpreadsheetEvaluationWorksheet | null;
// };

// type SpreadsheetCellValue = Record<string, unknown>;

// type SpreadsheetEvaluationRange = {
//   createFilter: () => unknown;
//   getCellData: () => unknown;
//   getCellStyleData: (type: string) => unknown;
//   setValueForCell: (value: SpreadsheetCellValue) => unknown;
// };

// type SpreadsheetEvaluationSheet = {
//   getRowManager: () => { getRowOrCreate: (row: number) => { hd?: number } };
//   isRowFiltered: (row: number) => boolean;
//   getRowVisible: (row: number) => boolean;
//   getRowRawVisible: (row: number) => boolean;
//   getName?: () => string;
//   getFreeze?: () => unknown;
//   isSheetHidden?: () => boolean | number;
//   hasHiddenGridlines?: () => boolean;
//   getGridlinesColor?: () => string | undefined;
//   getTabColor?: () => string | null | undefined;
// };

// type SpreadsheetChartBuilder = {
//   setChartType: (chartType: unknown) => SpreadsheetChartBuilder;
//   addRange: (range: string) => SpreadsheetChartBuilder;
//   setPosition: (
//     row: number,
//     column: number,
//     offsetX: number,
//     offsetY: number
//   ) => SpreadsheetChartBuilder;
//   setWidth: (width: number) => SpreadsheetChartBuilder;
//   setHeight: (height: number) => SpreadsheetChartBuilder;
//   setOptions: (path: string, value: unknown) => SpreadsheetChartBuilder;
//   setTransposeRowsAndColumns?: (transposeRowsAndColumns: boolean) => SpreadsheetChartBuilder;
//   setXAxisTitle?: (title: string) => SpreadsheetChartBuilder;
//   setYAxisTitle?: (title: string) => SpreadsheetChartBuilder;
//   build: () => unknown;
// };

// type SpreadsheetChart = {
//   getChartId?: () => string;
//   getRange?: () => unknown;
//   getSeriesData?: () => unknown;
//   getCategoryData?: () => unknown;
// };

// type SpreadsheetEvaluationWorksheet = {
//   getSheetId: () => string;
//   getSheetName?: () => string;
//   getMaxRows: () => number;
//   getMaxColumns: () => number;
//   getFilter: () => unknown;
//   getRange: {
//     (address: string): SpreadsheetEvaluationRange;
//     (row: number, column: number): SpreadsheetEvaluationRange;
//   };
//   getSheet: () => SpreadsheetEvaluationSheet;
//   setName?: (name: string) => unknown;
//   setRowCount?: (rowCount: number) => unknown;
//   setColumnCount?: (columnCount: number) => unknown;
//   hideSheet?: () => unknown;
//   showSheet?: () => unknown;
//   isSheetHidden?: () => boolean;
//   hasHiddenGridLines?: () => boolean;
//   setHiddenGridlines?: (hidden: boolean) => unknown;
//   getGridLinesColor?: () => string | undefined;
//   setGridLinesColor?: (color: string | undefined) => unknown;
//   getTabColor?: () => string | undefined;
//   setTabColor?: (color: string | null | undefined) => unknown;
//   getFreeze?: () => unknown;
//   setFreeze?: (freeze: unknown) => unknown;
//   cancelFreeze?: () => unknown;
//   newChart?: () => SpreadsheetChartBuilder;
//   insertChart?: (
//     chartInfo: unknown
//   ) => Promise<SpreadsheetChart | unknown> | SpreadsheetChart | unknown;
//   getCharts?: () => SpreadsheetChart[];
// };

// type SpreadsheetEvaluationContext = {
//   univerAPI: {
//     executeCommand: <P extends object = object, R = boolean>(id: string, params?: P) => Promise<R>;
//   };
//   workbook: SpreadsheetWorkbook;
//   worksheet: unknown;
//   actions: Pick<SpreadsheetActions, "columnIndexToName">;
// };

// type PlainObject = Record<string, unknown>;
// type FilterModelLike = {
//   filteredOutRows: Set<number>;
// };
// type FilterLike = {
//   _filterModel?: FilterModelLike;
//   getRange?: () => {
//     getA1Notation: (withSheet?: boolean) => string;
//     getRange: () => SelectionRange;
//   };
// };

// declare global {
//   interface Window {
//     getCellMeta: (target: string | CellMetaTarget) => CellMeta;
//     getSheetMeta: (target?: SheetTarget) => SheetMeta;
//     getChartMeta: (target?: SheetTarget) => ChartMeta[];
//     applyCellMeta: (entries: SpreadsheetCellMetaEntry[]) => CellMeta[];
//     applySheetMeta: (entry: SpreadsheetSheetMetaEntry) => SheetMeta;
//     applyChartMeta: (entry: SpreadsheetChartMetaEntry) => Promise<ChartMeta>;
//   }
// }

// export function installSpreadsheetEvaluationHelpers({
//   univerAPI,
//   workbook,
//   worksheet,
//   actions
// }: SpreadsheetEvaluationContext) {
//   const targetWorksheet = worksheet as SpreadsheetEvaluationWorksheet;
//   const chartMetaRegistry: ChartMeta[] = [];

//   function columnNameToIndex(columnName: string) {
//     return (
//       columnName
//         .toUpperCase()
//         .split("")
//         .reduce((sum, char) => sum * 26 + char.charCodeAt(0) - 64, 0) - 1
//     );
//   }

//   function cellNameToPosition(address: string) {
//     const match = address.trim().match(/^\$?([A-Z]+)\$?(\d+)$/i);
//     if (!match) {
//       throw new Error(`Invalid cell address: ${address}`);
//     }

//     const [, columnName, rowName] = match;

//     if (!columnName || !rowName) {
//       throw new Error(`Invalid cell address: ${address}`);
//     }

//     const column = columnNameToIndex(columnName);
//     const row = Number(rowName) - 1;

//     return { row, column };
//   }

//   function isPlainObject(value: unknown): value is PlainObject {
//     return value != null && typeof value === "object" && !Array.isArray(value);
//   }

//   function clonePlainValue<T>(value: T): T {
//     if (value == null) return value;

//     const json = JSON.stringify(value);
//     if (json === undefined) return value;

//     return JSON.parse(json) as T;
//   }

//   function hasOwn(value: object, key: string) {
//     return Object.prototype.hasOwnProperty.call(value, key);
//   }

//   function getFilterModel(filter: unknown): FilterModelLike | null {
//     if (!isPlainObject(filter)) return null;

//     const filterModel = filter._filterModel;
//     if (!isPlainObject(filterModel) || !(filterModel.filteredOutRows instanceof Set)) return null;

//     return filterModel as FilterModelLike;
//   }

//   function getFilterRangeA1(filter: FilterLike | null) {
//     return filter?.getRange?.().getA1Notation(false) ?? null;
//   }

//   function getWorkbookSheets() {
//     return workbook.getSheets?.() ?? [targetWorksheet];
//   }

//   function describeSheetTarget(target: SheetTarget) {
//     if (target.sheetId) return `sheetId=${target.sheetId}`;
//     if (target.sheetName) return `sheetName=${target.sheetName}`;
//     if (typeof target.sheetIndex === "number") return `sheetIndex=${target.sheetIndex}`;

//     return "default sheet";
//   }

//   function resolveWorksheet(target: SheetTarget = {}) {
//     if (!isPlainObject(target)) {
//       throw new Error("Sheet target must be an object.");
//     }

//     const hasExplicitTarget = Boolean(
//       target.sheetId || target.sheetName || typeof target.sheetIndex === "number"
//     );

//     if (target.sheetId) {
//       const sheet = workbook.getSheetBySheetId?.(target.sheetId);
//       if (sheet) return sheet;
//     }

//     if (target.sheetName) {
//       const sheet =
//         workbook.getSheetByName?.(target.sheetName) ??
//         workbook.getSheetBySheetName?.(target.sheetName);
//       if (sheet) return sheet;
//     }

//     if (typeof target.sheetIndex === "number") {
//       if (!Number.isInteger(target.sheetIndex) || target.sheetIndex < 0) {
//         throw new Error(`Invalid sheet index: ${target.sheetIndex}`);
//       }

//       const sheet = getWorkbookSheets()[target.sheetIndex];
//       if (sheet) return sheet;
//     }

//     if (hasExplicitTarget) {
//       throw new Error(`Sheet not found: ${describeSheetTarget(target)}`);
//     }

//     return targetWorksheet;
//   }

//   function getSheetName(worksheet: SpreadsheetEvaluationWorksheet) {
//     return worksheet.getSheetName?.() ?? worksheet.getSheet().getName?.() ?? null;
//   }

//   function getSheetIndex(worksheet: SpreadsheetEvaluationWorksheet) {
//     const sheetId = worksheet.getSheetId();
//     const index = getWorkbookSheets().findIndex((sheet) => sheet.getSheetId() === sheetId);

//     return index >= 0 ? index : null;
//   }

//   function createFallbackFilterRangeA1(worksheet: SpreadsheetEvaluationWorksheet, row: number) {
//     const maxColumn = Math.max(0, worksheet.getMaxColumns() - 1);
//     const maxRow = Math.max(row, worksheet.getMaxRows() - 1);

//     return `A1:${actions.columnIndexToName(maxColumn)}${maxRow + 1}`;
//   }

//   function getOrCreateFilterForRowMeta(
//     worksheet: SpreadsheetEvaluationWorksheet,
//     row: number,
//     rowMeta: Partial<RowMeta>
//   ): FilterLike | null {
//     const currentFilter = worksheet.getFilter();
//     if (currentFilter) return currentFilter as unknown as FilterLike;

//     const filterRange =
//       typeof rowMeta.filterRange === "string" && rowMeta.filterRange.trim()
//         ? rowMeta.filterRange
//         : createFallbackFilterRangeA1(worksheet, row);

//     return worksheet.getRange(filterRange).createFilter() as unknown as FilterLike | null;
//   }

//   function markFilterRangeDirty(
//     worksheet: SpreadsheetEvaluationWorksheet,
//     filter: FilterLike | null
//   ) {
//     const filterRange = filter?.getRange?.().getRange();
//     if (!filterRange) return;

//     void univerAPI.executeCommand(markDirtyFilterChangeMutationId, {
//       unitId: workbook.getId(),
//       subUnitId: worksheet.getSheetId(),
//       filterRange
//     });
//   }

//   function applyFilteredRowMeta(
//     worksheet: SpreadsheetEvaluationWorksheet,
//     row: number,
//     rowMeta: Partial<RowMeta>
//   ) {
//     if (typeof rowMeta.filtered !== "boolean") return;

//     const filter = getOrCreateFilterForRowMeta(worksheet, row, rowMeta);
//     const filterModel = getFilterModel(filter);
//     if (!filterModel) return;

//     const filteredOutRows = new Set(filterModel.filteredOutRows);

//     if (rowMeta.filtered) {
//       filteredOutRows.add(row);
//     } else {
//       filteredOutRows.delete(row);
//     }

//     filterModel.filteredOutRows = filteredOutRows;
//     markFilterRangeDirty(worksheet, filter);
//   }

//   function applyRowMeta(
//     worksheet: SpreadsheetEvaluationWorksheet,
//     row: number,
//     rowMeta: Partial<RowMeta>
//   ) {
//     const sheet = worksheet.getSheet();
//     const rowData = sheet.getRowManager().getRowOrCreate(row);

//     if (typeof rowMeta.rawVisible === "boolean") {
//       rowData.hd = rowMeta.rawVisible ? 0 : 1;
//     } else if (typeof rowMeta.visible === "boolean" && typeof rowMeta.filtered !== "boolean") {
//       rowData.hd = rowMeta.visible ? 0 : 1;
//     }

//     applyFilteredRowMeta(worksheet, row, rowMeta);
//   }

//   function resolveCellMetaTarget(target: string | CellMetaTarget): CellMetaTarget {
//     if (typeof target === "string") return { address: target };

//     if (!isPlainObject(target) || typeof target.address !== "string") {
//       throw new Error("Cell target must be a cell address string or an object with an address.");
//     }

//     return target;
//   }

//   function getCellMetaForWorksheet(
//     worksheet: SpreadsheetEvaluationWorksheet,
//     address: string
//   ): CellMeta {
//     const { row, column } = cellNameToPosition(address);
//     const range = worksheet.getRange(row, column);
//     const sheet = worksheet.getSheet();
//     const filter = worksheet.getFilter() as unknown as FilterLike | null;

//     return {
//       cell: clonePlainValue(range.getCellData()),
//       style: clonePlainValue(range.getCellStyleData("cell")),
//       row: {
//         filtered: sheet.isRowFiltered(row),
//         visible: sheet.getRowVisible(row),
//         rawVisible: sheet.getRowRawVisible(row),
//         filterRange: getFilterRangeA1(filter)
//       }
//     };
//   }

//   function getCellMeta(target: string | CellMetaTarget): CellMeta {
//     const cellTarget = resolveCellMetaTarget(target);

//     return getCellMetaForWorksheet(resolveWorksheet(cellTarget), cellTarget.address);
//   }

//   function getSheetMetaForWorksheet(worksheet: SpreadsheetEvaluationWorksheet): SheetMeta {
//     const sheet = worksheet.getSheet();
//     const filter = worksheet.getFilter() as unknown as FilterLike | null;

//     return {
//       sheet: {
//         id: worksheet.getSheetId(),
//         name: getSheetName(worksheet),
//         index: getSheetIndex(worksheet),
//         rowCount: worksheet.getMaxRows(),
//         columnCount: worksheet.getMaxColumns(),
//         hidden:
//           worksheet.isSheetHidden?.() ??
//           (typeof sheet.isSheetHidden === "function" ? Boolean(sheet.isSheetHidden()) : null),
//         gridlinesHidden: worksheet.hasHiddenGridLines?.() ?? sheet.hasHiddenGridlines?.() ?? null,
//         gridlinesColor: worksheet.getGridLinesColor?.() ?? sheet.getGridlinesColor?.() ?? null,
//         tabColor: worksheet.getTabColor?.() ?? sheet.getTabColor?.() ?? null,
//         freeze: clonePlainValue(worksheet.getFreeze?.() ?? sheet.getFreeze?.() ?? null),
//         filterRange: getFilterRangeA1(filter)
//       }
//     };
//   }

//   function getSheetMeta(target: SheetTarget = {}): SheetMeta {
//     return getSheetMetaForWorksheet(resolveWorksheet(target));
//   }

//   function assertPositiveInteger(value: unknown, label: string): asserts value is number {
//     if (typeof value !== "number" || !Number.isInteger(value) || value <= 0) {
//       throw new Error(`${label} must be a positive integer.`);
//     }
//   }

//   function applySheetMeta(entry: SpreadsheetSheetMetaEntry): SheetMeta {
//     if (!isPlainObject(entry)) {
//       throw new Error("Sheet meta entry must be an object.");
//     }

//     const worksheet = resolveWorksheet(entry);

//     if (hasOwn(entry, "name")) {
//       if (typeof entry.name !== "string" || entry.name.trim() === "") {
//         throw new Error("Sheet name must be a non-empty string.");
//       }
//       worksheet.setName?.(entry.name);
//     }

//     if (hasOwn(entry, "rowCount")) {
//       const rowCount = entry.rowCount;
//       assertPositiveInteger(rowCount, "rowCount");
//       worksheet.setRowCount?.(rowCount);
//     }

//     if (hasOwn(entry, "columnCount")) {
//       const columnCount = entry.columnCount;
//       assertPositiveInteger(columnCount, "columnCount");
//       worksheet.setColumnCount?.(columnCount);
//     }

//     if (hasOwn(entry, "hidden")) {
//       if (typeof entry.hidden !== "boolean") throw new Error("hidden must be a boolean.");
//       if (entry.hidden) {
//         worksheet.hideSheet?.();
//       } else {
//         worksheet.showSheet?.();
//       }
//     }

//     if (hasOwn(entry, "gridlinesHidden")) {
//       if (typeof entry.gridlinesHidden !== "boolean")
//         throw new Error("gridlinesHidden must be a boolean.");
//       worksheet.setHiddenGridlines?.(entry.gridlinesHidden);
//     }

//     if (hasOwn(entry, "gridlinesColor")) {
//       if (entry.gridlinesColor != null && typeof entry.gridlinesColor !== "string") {
//         throw new Error("gridlinesColor must be a string, null, or undefined.");
//       }
//       worksheet.setGridLinesColor?.(entry.gridlinesColor ?? undefined);
//     }

//     if (hasOwn(entry, "tabColor")) {
//       if (entry.tabColor != null && typeof entry.tabColor !== "string") {
//         throw new Error("tabColor must be a string, null, or undefined.");
//       }
//       worksheet.setTabColor?.(entry.tabColor);
//     }

//     if (hasOwn(entry, "freeze")) {
//       if (entry.freeze == null) {
//         worksheet.cancelFreeze?.();
//       } else {
//         if (!isPlainObject(entry.freeze))
//           throw new Error("freeze must be an object, null, or undefined.");
//         worksheet.setFreeze?.(clonePlainValue(entry.freeze));
//       }
//     }

//     return getSheetMetaForWorksheet(worksheet);
//   }

//   function normalizeChartType(chartType: unknown) {
//     if (typeof chartType !== "string") return chartType ?? ChartTypeBits.Column;

//     const normalizedChartType = chartType.trim().toLowerCase();
//     const chartTypes: Record<string, ChartTypeBits> = {
//       area: ChartTypeBits.Area,
//       bar: ChartTypeBits.Bar,
//       bubble: ChartTypeBits.Bubble,
//       column: ChartTypeBits.Column,
//       doughnut: ChartTypeBits.Doughnut,
//       line: ChartTypeBits.Line,
//       pie: ChartTypeBits.Pie,
//       radar: ChartTypeBits.Radar,
//       scatter: ChartTypeBits.Scatter
//     };

//     const resolvedChartType = chartTypes[normalizedChartType];
//     if (resolvedChartType == null) throw new Error(`Unsupported chart type: ${chartType}`);

//     return resolvedChartType;
//   }

//   function setChartOption(builder: SpreadsheetChartBuilder, path: string, value: unknown) {
//     if (value === undefined || value === null || value === "") return builder;

//     return builder.setOptions(path, value);
//   }

//   function getChartId(chart: SpreadsheetChart | unknown) {
//     if (!chart || typeof chart !== "object") return null;

//     const getChartIdMethod = (chart as SpreadsheetChart).getChartId;
//     if (!getChartIdMethod) return null;

//     return getChartIdMethod.call(chart);
//   }

//   function selectionRangeToA1(range: SelectionRange) {
//     return [
//       actions.columnIndexToName(range.startColumn),
//       range.startRow + 1,
//       ":",
//       actions.columnIndexToName(range.endColumn),
//       range.endRow + 1
//     ].join("");
//   }

//   function getSelectionRangeFromUnknown(value: unknown): SelectionRange | null {
//     if (!isPlainObject(value)) return null;

//     if (
//       typeof value.startRow === "number" &&
//       typeof value.endRow === "number" &&
//       typeof value.startColumn === "number" &&
//       typeof value.endColumn === "number"
//     ) {
//       return value as SelectionRange;
//     }

//     if (isPlainObject(value.range)) {
//       return getSelectionRangeFromUnknown(value.range);
//     }

//     return null;
//   }

//   function getChartSourceRangeA1(chartRange: unknown) {
//     const range = getSelectionRangeFromUnknown(chartRange);

//     return range ? selectionRangeToA1(range) : null;
//   }

//   function upsertChartMeta(meta: ChartMeta) {
//     if (meta.id) {
//       const existingIndex = chartMetaRegistry.findIndex((item) => item.id === meta.id);
//       if (existingIndex >= 0) {
//         chartMetaRegistry[existingIndex] = meta;
//         return;
//       }
//     }

//     chartMetaRegistry.push(meta);
//   }

//   function getChartMetaForWorksheet(worksheet: SpreadsheetEvaluationWorksheet): ChartMeta[] {
//     const sheetId = worksheet.getSheetId();
//     const sheetName = getSheetName(worksheet);
//     const registeredById = new Map(
//       chartMetaRegistry
//         .filter((item) => item.sheetId === sheetId && item.id)
//         .map((item) => [item.id, item])
//     );
//     const charts = worksheet.getCharts?.() ?? [];
//     const chartMetas = charts.map((chart, index) => {
//       const id = getChartId(chart);
//       const registered = id ? registeredById.get(id) : undefined;
//       const range = chart.getRange?.();

//       return {
//         id,
//         sheetId,
//         sheetName,
//         index,
//         chartType: registered?.chartType ?? null,
//         sourceRange: registered?.sourceRange ?? getChartSourceRangeA1(range),
//         range: clonePlainValue(range ?? null),
//         title: registered?.title ?? null,
//         legendPosition: registered?.legendPosition ?? null,
//         dataOrientation: registered?.dataOrientation ?? null,
//         width: registered?.width ?? null,
//         height: registered?.height ?? null,
//         position: registered?.position ?? null,
//         context: registered?.context ?? null,
//         seriesData: clonePlainValue(chart.getSeriesData?.() ?? null),
//         categoryData: clonePlainValue(chart.getCategoryData?.() ?? null)
//       };
//     });
//     const chartMetaIds = new Set(chartMetas.map((item) => item.id).filter(Boolean));
//     const registeredOnly = chartMetaRegistry.filter(
//       (item) => item.sheetId === sheetId && (!item.id || !chartMetaIds.has(item.id))
//     );

//     return [...chartMetas, ...registeredOnly].map(clonePlainValue);
//   }

//   function getChartMeta(target: SheetTarget = {}): ChartMeta[] {
//     return getChartMetaForWorksheet(resolveWorksheet(target));
//   }

//   function getChartPositionMeta(
//     entry: SpreadsheetChartMetaEntry,
//     worksheet: SpreadsheetEvaluationWorksheet
//   ): ChartPositionMeta {
//     const position = isPlainObject(entry.position) ? entry.position : {};

//     return {
//       row: typeof position.row === "number" ? position.row : 0,
//       column:
//         typeof position.column === "number"
//           ? position.column
//           : Math.min(1, Math.max(0, worksheet.getMaxColumns() - 1)),
//       offsetX: typeof position.offsetX === "number" ? position.offsetX : 20,
//       offsetY: typeof position.offsetY === "number" ? position.offsetY : 20
//     };
//   }

//   function getPositiveNumber(value: unknown, fallback: number, label: string) {
//     if (value == null) return fallback;
//     if (typeof value !== "number" || !Number.isFinite(value) || value <= 0) {
//       throw new Error(`${label} must be a positive number.`);
//     }

//     return value;
//   }

//   async function applyChartMeta(entry: SpreadsheetChartMetaEntry): Promise<ChartMeta> {
//     if (!isPlainObject(entry)) {
//       throw new Error("Chart meta entry must be an object.");
//     }

//     const worksheet = resolveWorksheet(entry);
//     if (!worksheet.newChart || !worksheet.insertChart) {
//       throw new Error("Charts are not available for this worksheet.");
//     }

//     const sourceRange = (entry.sourceRange ?? entry.rangeA1)?.trim();
//     if (!sourceRange) throw new Error("Chart sourceRange is required.");

//     const chartType = normalizeChartType(entry.chartType);
//     const title = typeof entry.title === "string" && entry.title.trim() ? entry.title.trim() : null;
//     const width = getPositiveNumber(entry.width, 560, "width");
//     const height = getPositiveNumber(entry.height, 360, "height");
//     const position = getChartPositionMeta(entry, worksheet);
//     let chartBuilder = worksheet
//       .newChart()
//       .setChartType(chartType)
//       .addRange(sourceRange)
//       .setPosition(position.row, position.column, position.offsetX, position.offsetY)
//       .setWidth(width)
//       .setHeight(height);

//     chartBuilder = setChartOption(chartBuilder, "title.content", title);
//     chartBuilder = setChartOption(chartBuilder, "legend.position", entry.legendPosition);
//     chartBuilder = setChartOption(chartBuilder, "orient", entry.dataOrientation);

//     if (
//       typeof entry.transposeRowsAndColumns === "boolean" &&
//       chartBuilder.setTransposeRowsAndColumns
//     ) {
//       chartBuilder = chartBuilder.setTransposeRowsAndColumns(entry.transposeRowsAndColumns);
//     }

//     if (
//       typeof entry.xAxisTitle === "string" &&
//       entry.xAxisTitle.trim() &&
//       chartBuilder.setXAxisTitle
//     ) {
//       chartBuilder = chartBuilder.setXAxisTitle(entry.xAxisTitle.trim());
//     }

//     if (
//       typeof entry.yAxisTitle === "string" &&
//       entry.yAxisTitle.trim() &&
//       chartBuilder.setYAxisTitle
//     ) {
//       chartBuilder = chartBuilder.setYAxisTitle(entry.yAxisTitle.trim());
//     }

//     const insertedChart = await worksheet.insertChart(chartBuilder.build());
//     const id = getChartId(insertedChart);

//     if (id && entry.context != null) {
//       await univerAPI.executeCommand(chartUpdateConfigCommandId, {
//         unitId: workbook.getId(),
//         chartModelId: id,
//         context: entry.context
//       });
//     }

//     const charts = worksheet.getCharts?.() ?? [];
//     const meta: ChartMeta = {
//       id,
//       sheetId: worksheet.getSheetId(),
//       sheetName: getSheetName(worksheet),
//       index: id ? charts.findIndex((chart) => getChartId(chart) === id) : null,
//       chartType,
//       sourceRange,
//       range: clonePlainValue((insertedChart as SpreadsheetChart | undefined)?.getRange?.() ?? null),
//       title,
//       legendPosition: entry.legendPosition ?? null,
//       dataOrientation: entry.dataOrientation ?? null,
//       width,
//       height,
//       position,
//       context: clonePlainValue(entry.context ?? null),
//       seriesData: clonePlainValue(
//         (insertedChart as SpreadsheetChart | undefined)?.getSeriesData?.() ?? null
//       ),
//       categoryData: clonePlainValue(
//         (insertedChart as SpreadsheetChart | undefined)?.getCategoryData?.() ?? null
//       )
//     };

//     upsertChartMeta(meta);

//     return clonePlainValue(
//       id ? (getChartMetaForWorksheet(worksheet).find((chart) => chart.id === id) ?? meta) : meta
//     );
//   }

//   function applyCellMeta(entries: SpreadsheetCellMetaEntry[]): CellMeta[] {
//     if (!Array.isArray(entries)) {
//       throw new Error("Cell meta entries must be an array.");
//     }

//     for (const entry of entries) {
//       if (!isPlainObject(entry) || typeof entry.address !== "string") {
//         throw new Error("Each cell meta entry must be an object with an address.");
//       }

//       const worksheet = resolveWorksheet(entry);
//       const { row, column } = cellNameToPosition(entry.address);
//       const range = worksheet.getRange(row, column);

//       if (entry.cell != null && !isPlainObject(entry.cell)) {
//         throw new Error(`Invalid cell object for ${entry.address}`);
//       }

//       if (entry.row != null && !isPlainObject(entry.row)) {
//         throw new Error(`Invalid row object for ${entry.address}`);
//       }

//       const hasCell = hasOwn(entry, "cell");
//       const hasStyle = hasOwn(entry, "style");

//       if (hasCell || hasStyle) {
//         const nextCellData = isPlainObject(entry.cell)
//           ? clonePlainValue(entry.cell)
//           : hasCell
//             ? {}
//             : clonePlainValue(range.getCellData() ?? {});

//         if (!isPlainObject(nextCellData)) {
//           throw new Error(`Invalid current cell object for ${entry.address}`);
//         }

//         if (hasStyle) {
//           if (isPlainObject(entry.style)) {
//             nextCellData.s = clonePlainValue(entry.style);
//           } else {
//             delete nextCellData.s;
//           }
//         }

//         range.setValueForCell(nextCellData as SpreadsheetCellValue);
//       }

//       if (isPlainObject(entry.row)) {
//         applyRowMeta(worksheet, row, entry.row as Partial<RowMeta>);
//       }
//     }

//     return entries.map((entry) => getCellMetaForWorksheet(resolveWorksheet(entry), entry.address));
//   }

//   window.getCellMeta = getCellMeta;
//   window.getSheetMeta = getSheetMeta;
//   window.getChartMeta = getChartMeta;
//   window.applyCellMeta = applyCellMeta;
//   window.applySheetMeta = applySheetMeta;
//   window.applyChartMeta = applyChartMeta;
// }
