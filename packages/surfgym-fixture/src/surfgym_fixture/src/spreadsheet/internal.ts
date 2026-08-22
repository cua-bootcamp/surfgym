import { checkCellValueType, type FWorksheet } from "@univerjs/preset-sheets-core";
import type { Path, Value } from "../external";
import { resetTaskScopedCharts } from "./surfgym-chart";
import { resetTaskScopedSpreadsheetExportRequest } from "./surfgym-export";
import { resetTaskScopedSparklines } from "./surfgym-sparkline";
import { SpreadsheetRuntimeStore } from "./runtime";

type WorksheetLike = FWorksheet;
const setZoomRatioCommandId = "sheet.command.set-zoom-ratio";

type RangeLike = {
  startRow: number;
  endRow: number;
  startColumn: number;
  endColumn: number;
};
type ResolveSheetOptions = {
  create?: boolean;
};
type WorkbookWithSheetMutation = {
  getSheets?: () => WorksheetLike[];
  getSheetByName?: (sheetName: string) => WorksheetLike | null | undefined;
  getSheetBySheetId?: (sheetId: string) => WorksheetLike | null | undefined;
  insertSheet?: (name?: string, options?: { index?: number }) => WorksheetLike;
  moveSheet?: (sheet: WorksheetLike, index: number) => unknown;
};
type WorksheetWithMutation = WorksheetLike & {
  setName?: (name: string) => unknown;
};

export type PivotMeta = {
  sourceRange: string;
  rowFields: number[];
  columnFields: number[];
  dataFields: { fieldIndex: number; function: string; displayAs: 'value' | 'percentOfGrandTotal' }[];
  targetSheet: string;
  startRow: number;
  startColumn: number;
};

export type SpreadsheetValidationList = {
  values: string[];
  allowBlank: boolean;
};

const pivotMetaRegistry = new Map<string, PivotMeta>();
const validationListRegistry = new Map<string, SpreadsheetValidationList>();

function pivotKey(targetSheet: string, startRow: number, startColumn: number) {
  return `${targetSheet}\u0001${startRow}\u0001${startColumn}`;
}
function validationListKey(worksheet: WorksheetLike, row: number, column: number) {
  return `${worksheet.getSheetId?.() ?? getSheetName(worksheet)}\u0001${row}\u0001${column}`;
}

function cloneValidationList(value: SpreadsheetValidationList | null) {
  return value === null ? null : { values: [...value.values], allowBlank: value.allowBlank };
}

function sameValidationList(left: SpreadsheetValidationList | null, right: SpreadsheetValidationList | null) {
  return left === right || (
    left !== null && right !== null &&
    left.allowBlank === right.allowBlank &&
    left.values.length === right.values.length &&
    left.values.every((value, index) => value === right.values[index])
  );
}

function requireValidationList(value: Value): SpreadsheetValidationList | null {
  if (value === null) return null;
  if (!isRecord(value) || Array.isArray(value) || !Array.isArray(value.values) || typeof value.allowBlank !== "boolean") {
    throw new Error("validationList must be { values: string[], allowBlank: boolean } or null.");
  }

  const values = value.values.map((item) => {
    if (typeof item !== "string") throw new Error("validationList values must be strings.");
    const normalized = item.trim();
    if (!normalized) throw new Error("validationList values cannot be empty or whitespace-only.");
    return normalized;
  });
  if (!values.length) throw new Error("validationList values cannot be empty.");
  if (new Set(values).size !== values.length) throw new Error("validationList values cannot contain duplicates.");
  return { values, allowBlank: value.allowBlank };
}

export function _registerPivotMeta(meta: PivotMeta) {
  pivotMetaRegistry.set(pivotKey(meta.targetSheet, meta.startRow, meta.startColumn), structuredClone(meta));
  return _getPivotMeta(meta.targetSheet, meta.startRow, meta.startColumn);
}

export function _getPivotMeta(targetSheet: string, startRow: number, startColumn: number) {
  const meta = pivotMetaRegistry.get(pivotKey(targetSheet, startRow, startColumn));
  if (!meta) throw new Error(`Pivot not found: ${targetSheet}!R${startRow + 1}C${startColumn + 1}`);
  return structuredClone(meta);
}

export function _setPivotMeta(targetSheet: string, startRow: number, startColumn: number, value: Value) {
  if (!isRecord(value) || Array.isArray(value)) throw new Error('Pivot metadata must be an object.');
  const meta = value as Partial<PivotMeta>;
  if (meta.targetSheet !== targetSheet || meta.startRow !== startRow || meta.startColumn !== startColumn ||
    typeof meta.sourceRange !== 'string' || !isA1Range(meta.sourceRange) ||
    !isNonNegativeIntegerList(meta.rowFields) || !isNonNegativeIntegerList(meta.columnFields) ||
    !Array.isArray(meta.dataFields) || !meta.dataFields.every(isPivotDataField)) {
    throw new Error('Pivot metadata is invalid or does not match its atom address.');
  }
  return _registerPivotMeta({
    ...meta,
    rowFields: [...meta.rowFields],
    columnFields: [...meta.columnFields],
    dataFields: meta.dataFields.map((field) => ({ ...field, displayAs: field.displayAs ?? 'value' })),
  } as PivotMeta);
}

function isNonNegativeIntegerList(value: unknown): value is number[] {
  return Array.isArray(value) && value.every((item) => Number.isInteger(item) && item >= 0);
}

function isA1Range(value: string) {
  return /^\$?[A-Z]+\$?[1-9]\d*(?::\$?[A-Z]+\$?[1-9]\d*)?$/i.test(value.trim());
}

function isPivotDataField(value: unknown): value is PivotMeta['dataFields'][number] {
  const fieldIndex = isRecord(value) ? value.fieldIndex : undefined;
  if (!isRecord(value) || !Number.isInteger(fieldIndex) || (fieldIndex as number) < 0 ||
    typeof value.function !== 'string' || !pivotDataFunctions.has(value.function)) return false;
  return value.displayAs === undefined || value.displayAs === 'value' || value.displayAs === 'percentOfGrandTotal';
}

const pivotDataFunctions = new Set(['sum', 'count', 'average', 'median', 'max', 'min', 'product', 'countNumbers']);

function getWorkbookSheets() {
  const { workbook, defaultWorksheet } = SpreadsheetRuntimeStore.runtime;
  const sheets = workbook.getSheets?.() ?? [];
  const defaultSheetId = defaultWorksheet.getSheetId?.();

  return sheets.some((sheet) => sheet.getSheetId?.() === defaultSheetId)
    ? sheets
    : [defaultWorksheet, ...sheets];
}

function resolveSheet(sheetRef?: SheetRef, options: ResolveSheetOptions = {}) {
  const { workbook, defaultWorksheet } = SpreadsheetRuntimeStore.runtime;
  const workbookWithSheets = workbook as unknown as WorkbookWithSheetMutation;
  const sheets = getWorkbookSheets();

  if (sheetRef === undefined) return defaultWorksheet;

  if (typeof sheetRef === "string") {
    const sheet =
      sheets.find((item) => getSheetName(item) === sheetRef || item.getSheetId?.() === sheetRef) ??
      workbookWithSheets.getSheetByName?.(sheetRef) ??
      workbookWithSheets.getSheetBySheetId?.(sheetRef);

    if (!sheet && options.create && typeof workbookWithSheets.insertSheet === "function") {
      return workbookWithSheets.insertSheet(sheetRef);
    }

    if (!sheet) throw new Error(`Sheet not found: ${sheetRef}`);
    return sheet;
  }

  if (!Number.isInteger(sheetRef) || sheetRef < 0) {
    throw new Error(`Invalid sheet index: ${sheetRef}`);
  }

  const sheet = sheets[sheetRef];
  if (
    !sheet &&
    options.create &&
    sheetRef === sheets.length &&
    typeof workbookWithSheets.insertSheet === "function"
  ) {
    return workbookWithSheets.insertSheet();
  }

  if (!sheet) throw new Error(`Sheet not found: index=${sheetRef}`);
  return sheet;
}

function activateSheetAfterExplicitSet(sheetRef: SheetRef | undefined, worksheet: WorksheetLike) {
  if (sheetRef === undefined) return;

  SpreadsheetRuntimeStore.runtime.workbook.setActiveSheet(worksheet);
}

function isRecord(value: unknown): value is Record<PropertyKey, unknown> {
  return value !== null && typeof value === "object";
}

function isCellValue(value: Value): value is string | number | boolean {
  return typeof value === "string" || typeof value === "number" || typeof value === "boolean";
}

function isCellMetaPath(path: Path[], expected: Path[]) {
  return path.length === expected.length && path.every((key, index) => key === expected[index]);
}

function resolveCell(address: string) {
  const match = address.trim().match(/^\$?([A-Z]+)\$?(\d+)$/i);
  if (!match) throw new Error(`Invalid cell address: ${address}`);

  const [, columnName, rowName] = match;
  if (!columnName || !rowName) throw new Error(`Invalid cell address: ${address}`);

  return {
    row: Number(rowName) - 1,
    column:
      columnName
        .toUpperCase()
        .split("")
        .reduce((sum, char) => sum * 26 + char.charCodeAt(0) - 64, 0) - 1
  };
}

function resolveCellRange(address: string): RangeLike {
  const parts = address.trim().split(":");
  if (parts.length < 1 || parts.length > 2) {
    throw new Error(`Invalid cell range address: ${address}`);
  }

  const startAddress = parts[0];
  const endAddress = parts[1] ?? startAddress;
  if (!startAddress || !endAddress) {
    throw new Error(`Invalid cell range address: ${address}`);
  }

  const start = resolveCell(startAddress);
  const end = resolveCell(endAddress);

  return {
    startRow: Math.min(start.row, end.row),
    endRow: Math.max(start.row, end.row),
    startColumn: Math.min(start.column, end.column),
    endColumn: Math.max(start.column, end.column)
  };
}

function getSheetName(worksheet: WorksheetLike) {
  return worksheet.getSheetName?.() ?? worksheet.getSheet?.().getName?.() ?? null;
}

function readPath(value: unknown, path: PropertyKey[]): unknown {
  let current = value;

  for (const key of path) {
    if (!isRecord(current)) return undefined;
    current = current[key];
  }

  return current;
}

export function _getCellMeta(sheetRef: SheetRef | undefined, cellRefStr: string) {
  const worksheet = resolveSheet(sheetRef);
  const cellRef = resolveCell(cellRefStr);
  const range = worksheet.getRange(cellRef.row, cellRef.column);
  const data = worksheet.getSheet().getCellRaw(cellRef.row, cellRef.column) ?? {};
  const style = range.getCellStyleData("cell") ?? {};

  return { ...data, s: style };
}

export function _getCellMetaValue(
  sheetRef: SheetRef | undefined,
  cellRefStr: string,
  path: Path[]
) {
  const worksheet = resolveSheet(sheetRef);
  const cellRange = resolveCellRange(cellRefStr);
  const values: unknown[][] = [];

  for (let row = cellRange.startRow; row <= cellRange.endRow; row += 1) {
    const rowValues: unknown[] = [];

    for (let column = cellRange.startColumn; column <= cellRange.endColumn; column += 1) {
      const range = worksheet.getRange(row, column);
      const data = worksheet.getSheet().getCellRaw(row, column) ?? {};
      const style = range.getCellStyleData("cell") ?? {};

      rowValues.push(readPath({ ...data, s: style }, path));
    }

    values.push(rowValues);
  }

  const firstValue = values[0]?.[0];
  const hasUniformValue = values.every((row) => row.every((value) => Object.is(value, firstValue)));

  return hasUniformValue ? firstValue : values;
}

export function _setCellMeta(
  sheetRef: SheetRef | undefined,
  cellRefStr: string,
  path: Path[],
  value: Value
) {
  const worksheet = resolveSheet(sheetRef);
  const cellRange = resolveCellRange(cellRefStr);

  for (let row = cellRange.startRow; row <= cellRange.endRow; row += 1) {
    for (let column = cellRange.startColumn; column <= cellRange.endColumn; column += 1) {
      const range = worksheet.getRange(row, column);

      if (path.length === 1 && path[0] === "v") {
        if (value === null) {
          range.clearContent();
          continue;
        }

        if (!isCellValue(value)) {
          throw new Error("Cell value must be a scalar.");
        }

        range.setValueForCell({
          v: value,
          t: checkCellValueType(value, null),
          f: null,
          p: null,
          si: null
        });
        continue;
      }

      if (isCellMetaPath(path, ["s", "bg", "rgb"])) {
        if (typeof value !== "string") {
          throw new Error("backgroundColor must be a string.");
        }

        range.setBackgroundColor(value);
        continue;
      }

      if (isCellMetaPath(path, ["s", "cl", "rgb"])) {
        if (value !== null && typeof value !== "string") {
          throw new Error("fontColor must be a string or null.");
        }

        range.setFontColor(value);
        continue;
      }

      if (isCellMetaPath(path, ["s", "bl"])) {
        if (value === true || value === 1) range.setFontWeight("bold");
        else if (value === false || value === 0) range.setFontWeight("normal");
        else if (value === null) range.setFontWeight(null);
        else throw new Error("bold must be 0, 1, true, false, or null.");
        continue;
      }

      const data = { ...(worksheet.getSheet().getCellRaw(row, column) ?? {}) };
      let target = data as Record<PropertyKey, unknown>;

      for (const key of path.slice(0, -1)) {
        if (target[key] == null || typeof target[key] !== "object") target[key] = {};
        target = target[key] as Record<PropertyKey, unknown>;
      }

      const last = path[path.length - 1] as Path;
      target[last] = value;
      range.setValueForCell(data);
    }
  }

  activateSheetAfterExplicitSet(sheetRef, worksheet);
}

export function _setCellNumberFormat(
  sheetRef: SheetRef | undefined,
  cellRefStr: string,
  value: Value
) {
  if (typeof value !== "string") throw new Error("numberFormat must be a string.");

  const worksheet = resolveSheet(sheetRef);
  const cellRange = resolveCellRange(cellRefStr);

  for (let row = cellRange.startRow; row <= cellRange.endRow; row += 1) {
    for (let column = cellRange.startColumn; column <= cellRange.endColumn; column += 1) {
      worksheet.getRange(row, column).setNumberFormat(value);
    }
  }

  activateSheetAfterExplicitSet(sheetRef, worksheet);
}

export function _getCellValidationList(sheetRef: SheetRef | undefined, cellRefStr: string) {
  const worksheet = resolveSheet(sheetRef);
  const cellRange = resolveCellRange(cellRefStr);
  const values: (SpreadsheetValidationList | null)[][] = [];

  for (let row = cellRange.startRow; row <= cellRange.endRow; row += 1) {
    const rowValues: (SpreadsheetValidationList | null)[] = [];
    for (let column = cellRange.startColumn; column <= cellRange.endColumn; column += 1) {
      rowValues.push(cloneValidationList(validationListRegistry.get(validationListKey(worksheet, row, column)) ?? null));
    }
    values.push(rowValues);
  }

  const firstValue = values[0]?.[0] ?? null;
  const hasUniformValue = values.every((row) => row.every((value) => sameValidationList(value, firstValue)));
  return hasUniformValue ? cloneValidationList(firstValue) : values;
}

export function _setCellValidationList(
  sheetRef: SheetRef | undefined,
  cellRefStr: string,
  value: Value,
) {
  const validationList = requireValidationList(value);
  const worksheet = resolveSheet(sheetRef);
  const cellRange = resolveCellRange(cellRefStr);

  for (let row = cellRange.startRow; row <= cellRange.endRow; row += 1) {
    for (let column = cellRange.startColumn; column <= cellRange.endColumn; column += 1) {
      const key = validationListKey(worksheet, row, column);
      if (validationList === null) validationListRegistry.delete(key);
      else validationListRegistry.set(key, cloneValidationList(validationList)!);
    }
  }

  activateSheetAfterExplicitSet(sheetRef, worksheet);
  return _getCellValidationList(sheetRef, cellRefStr);
}

export function _getCellMerged(sheetRef: SheetRef | undefined, cellRefStr: string) {
  const worksheet = resolveSheet(sheetRef);
  const cellRange = resolveCellRange(cellRefStr);
  const rowCount = cellRange.endRow - cellRange.startRow + 1;
  const columnCount = cellRange.endColumn - cellRange.startColumn + 1;

  return worksheet
    .getRange(cellRange.startRow, cellRange.startColumn, rowCount, columnCount)
    .isMerged();
}

export function _setCellMerged(sheetRef: SheetRef | undefined, cellRefStr: string, value: Value) {
  if (typeof value !== "boolean") throw new Error("merged must be a boolean.");

  const worksheet = resolveSheet(sheetRef);
  const cellRange = resolveCellRange(cellRefStr);
  const rowCount = cellRange.endRow - cellRange.startRow + 1;
  const columnCount = cellRange.endColumn - cellRange.startColumn + 1;
  const range = worksheet.getRange(
    cellRange.startRow,
    cellRange.startColumn,
    rowCount,
    columnCount
  );

  if (value) range.merge({ defaultMerge: true, isForceMerge: true });
  else range.breakApart();

  activateSheetAfterExplicitSet(sheetRef, worksheet);

  const actual = range.isMerged();
  if (actual !== value) {
    throw new Error(`Merged range mismatch after set: expected=${value}, actual=${actual}.`);
  }

  return actual;
}

export function _getRowHidden(sheetRef: SheetRef | undefined, cellRefStr: string) {
  const worksheet = resolveSheet(sheetRef);
  const cellRange = resolveCellRange(cellRefStr);
  const values: boolean[] = [];

  for (let row = cellRange.startRow; row <= cellRange.endRow; row += 1) {
    values.push(!worksheet.getSheet().getRowRawVisible(row));
  }

  const firstValue = values[0];
  return values.every((value) => value === firstValue) ? firstValue : values;
}

export function _setRowHidden(sheetRef: SheetRef | undefined, cellRefStr: string, value: Value) {
  if (typeof value !== "boolean") throw new Error("rowHidden must be a boolean.");

  const worksheet = resolveSheet(sheetRef);
  const cellRange = resolveCellRange(cellRefStr);
  const rowCount = cellRange.endRow - cellRange.startRow + 1;

  if (value) worksheet.hideRows(cellRange.startRow, rowCount);
  else worksheet.showRows(cellRange.startRow, rowCount);
  activateSheetAfterExplicitSet(sheetRef, worksheet);
}

export function _getSheetName(sheetRef?: SheetRef) {
  return getSheetName(resolveSheet(sheetRef));
}

export function _getSheetZoom(sheetRef?: SheetRef) {
  return resolveSheet(sheetRef).getZoom();
}

export function _getFrozenRows(sheetRef?: SheetRef) {
  return resolveSheet(sheetRef).getFrozenRows();
}

export function _setFrozenRows(sheetRef: SheetRef | undefined, value: Value) {
  if (typeof value !== "number" || !Number.isFinite(value) || value < 0) {
    throw new Error("Frozen row count must be a non-negative finite number.");
  }

  const worksheet = resolveSheet(sheetRef, { create: true });
  activateSheetAfterExplicitSet(sheetRef, worksheet);
  worksheet.setFrozenRows(value);

  return worksheet.getFrozenRows();
}

export function _getFrozenColumns(sheetRef?: SheetRef) {
  return resolveSheet(sheetRef).getFrozenColumns();
}

export function _setFrozenColumns(sheetRef: SheetRef | undefined, value: Value) {
  if (typeof value !== "number" || !Number.isFinite(value) || value < 0) {
    throw new Error("Frozen column count must be a non-negative finite number.");
  }

  const worksheet = resolveSheet(sheetRef, { create: true });
  activateSheetAfterExplicitSet(sheetRef, worksheet);
  worksheet.setFrozenColumns(value);

  return worksheet.getFrozenColumns();
}

export function _resetSpreadsheetState() {
  const runtime = SpreadsheetRuntimeStore.runtime;
  const { workbook } = runtime;
  const previousSheets = workbook.getSheets();
  const existingNames = new Set(previousSheets.map((sheet) => sheet.getSheetName()));
  let resetSheetName = "__surfgym_reset__";

  while (existingNames.has(resetSheetName)) resetSheetName += "_";

  const resetWorksheet = workbook.insertSheet(resetSheetName, { index: 0 });
  workbook.setActiveSheet(resetWorksheet);

  for (const sheet of previousSheets) {
    if (!workbook.deleteSheet(sheet)) {
      throw new Error(`Failed to remove sheet while resetting state: ${sheet.getSheetName()}`);
    }
  }

  resetWorksheet.setName("Sheet1");
  workbook.setActiveSheet(resetWorksheet);
  runtime.defaultWorksheet = resetWorksheet;
  runtime.initializeWorksheet(resetWorksheet);
  pivotMetaRegistry.clear();
  validationListRegistry.clear();
  resetTaskScopedCharts();
  resetTaskScopedSpreadsheetExportRequest();
  resetTaskScopedSparklines();

  return resetWorksheet;
}

export function _setSheetName(sheetRef: SheetRef | undefined, value: Value) {
  const name = requireSheetName(value);
  const worksheet = resolveSheet(sheetRef, { create: true });

  const setName = (worksheet as WorksheetWithMutation).setName;
  if (typeof setName === "function" && getSheetName(worksheet) !== name) {
    setName.call(worksheet, name);
  }

  activateSheetAfterExplicitSet(sheetRef, worksheet);
  return getSheetName(worksheet);
}

export async function _setSheetZoom(sheetRef: SheetRef | undefined, value: Value) {
  if (typeof value !== "number" || !Number.isFinite(value) || value < 0.1 || value > 4) {
    throw new Error("Sheet zoom must be a finite number between 0.1 and 4.");
  }

  const runtime = SpreadsheetRuntimeStore.runtime;
  await runtime.rendered;

  const worksheet = resolveSheet(sheetRef, { create: true });
  activateSheetAfterExplicitSet(sheetRef, worksheet);

  const applied = await runtime.univerAPI.executeCommand(setZoomRatioCommandId, {
    unitId: runtime.workbook.getId(),
    subUnitId: worksheet.getSheetId(),
    zoomRatio: value
  });

  if (!applied) {
    throw new Error(`Failed to set sheet zoom to ${value}.`);
  }

  const actual = worksheet.getZoom();
  if (!Number.isFinite(actual) || Math.abs(actual - value) > 1e-9) {
    throw new Error(`Sheet zoom mismatch after set: expected=${value}, actual=${actual}.`);
  }

  return actual;
}

export function _getIndexedSheetName(sheetRef: IndexedSheetRef) {
  const { index, name } = normalizeIndexedSheetRef(sheetRef);
  const worksheet = getWorkbookSheets()[index];

  if (!worksheet) throw new Error(`Sheet not found: index=${index}, name=${name}`);

  const actualName = getSheetName(worksheet);
  if (actualName !== name) {
    throw new Error(
      `Sheet mismatch at index ${index}: expected ${name}, actual ${String(actualName)}`
    );
  }

  return actualName;
}

export function _setIndexedSheetName(sheetRef: IndexedSheetRef, value: Value) {
  const normalized = normalizeIndexedSheetRef(sheetRef);
  const valueName = requireSheetName(value);

  if (valueName !== normalized.name) {
    throw new Error(
      `Indexed sheet name must match set value: selector=${normalized.name}, value=${valueName}`
    );
  }

  const { workbook } = SpreadsheetRuntimeStore.runtime;
  const mutableWorkbook = workbook as unknown as WorkbookWithSheetMutation;
  let sheets = getWorkbookSheets();

  if (normalized.index > sheets.length) {
    throw new Error(
      `Cannot place sheet at index ${normalized.index}; sheet count is ${sheets.length}.`
    );
  }

  let worksheet = sheets.find((sheet) => getSheetName(sheet) === normalized.name);

  if (worksheet) {
    const currentIndex = sheets.indexOf(worksheet);
    if (currentIndex !== normalized.index) {
      if (normalized.index >= sheets.length) {
        throw new Error(
          `Cannot move existing sheet ${normalized.name} to index ${normalized.index}.`
        );
      }
      if (typeof mutableWorkbook.moveSheet !== "function") {
        throw new Error("Moving sheets is not supported.");
      }
      mutableWorkbook.moveSheet(worksheet, normalized.index);
    }
  } else {
    worksheet = sheets[normalized.index];
    if (worksheet) {
      const setName = (worksheet as WorksheetWithMutation).setName;
      if (typeof setName !== "function") throw new Error("Renaming sheets is not supported.");
      setName.call(worksheet, normalized.name);
    } else {
      if (typeof mutableWorkbook.insertSheet !== "function") {
        throw new Error("Creating sheets is not supported.");
      }
      worksheet = mutableWorkbook.insertSheet(normalized.name, {
        index: normalized.index
      });
    }
  }

  sheets = getWorkbookSheets();
  const indexedWorksheet = sheets[normalized.index];
  const actualName = indexedWorksheet ? getSheetName(indexedWorksheet) : null;
  if (!indexedWorksheet || actualName !== normalized.name) {
    throw new Error(
      `Failed to place sheet ${normalized.name} at index ${normalized.index}; actual=${String(
        actualName
      )}`
    );
  }

  activateSheetAfterExplicitSet(normalized.index, indexedWorksheet);
  return actualName;
}

export type SheetRef = string | number;
export type IndexedSheetRef = {
  index: number;
  name: string;
};
export type CellRef = {
  row: number;
  column: number;
};

type NormalizedIndexedSheetRef = {
  index: number;
  name: string;
};

function requireSheetName(value: Value): string {
  if (typeof value !== "string" || value.trim() === "") {
    throw new Error("Sheet name must be a non-empty string.");
  }
  return value;
}

function normalizeIndexedSheetRef(sheetRef: IndexedSheetRef): NormalizedIndexedSheetRef {
  if (!Number.isInteger(sheetRef.index) || sheetRef.index < 0) {
    throw new Error(`Sheet index must be a non-negative integer: ${String(sheetRef.index)}`);
  }
  if (typeof sheetRef.name !== "string" || sheetRef.name.trim() === "") {
    throw new Error("Indexed sheet name must be a non-empty string.");
  }

  return {
    index: sheetRef.index,
    name: sheetRef.name
  };
}
