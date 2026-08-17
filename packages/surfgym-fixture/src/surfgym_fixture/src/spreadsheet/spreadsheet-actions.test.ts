import { describe, expect, it } from "vitest";
import { createSpreadsheetActions, type PivotTableLayoutConfig } from "./spreadsheet-actions";

describe("existing freeze action", () => {
  it("freezes the row and column before a B2 selection", () => {
    let frozenRows: number | undefined;
    let frozenColumns: number | undefined;
    const selectedRange = { startRow: 1, endRow: 1, startColumn: 1, endColumn: 1 };
    const worksheet = {
      getSheetId: () => "sheet-1",
      getMaxRows: () => 100,
      getMaxColumns: () => 26,
      getSelection: () => ({ getActiveRange: () => ({ getRange: () => selectedRange }) }),
      getRange: () => ({
        setFontFamily: () => undefined,
        setFontSize: () => undefined,
        setNumberFormat: () => undefined,
        setValue: () => undefined,
        sort: () => undefined,
      }),
      newChart: () => {
        throw new Error("chart builder is not used by the freeze action");
      },
      insertChart: () => {
        throw new Error("chart insertion is not used by the freeze action");
      },
      setFrozenRows: (rows: number) => {
        frozenRows = rows;
      },
      setFrozenColumns: (columns: number) => {
        frozenColumns = columns;
      },
    };
    const workbook = { getId: () => "workbook-1" };
    const actions = createSpreadsheetActions({
      univerAPI: {
        executeCommand: async <P extends object, R = boolean>(_id: string, _params?: P) => true as R,
        getActiveSheet: () => ({ workbook, worksheet }),
      },
      workbook,
      getDefaultWorksheet: () => worksheet,
    });

    expect(actions.applySelectionFreeze()).toBe(true);
    expect(frozenRows).toBe(1);
    expect(frozenColumns).toBe(1);
  });

  it("freezes the A1:B1 contract from a C2 selection", () => {
    let frozenRows: number | undefined;
    let frozenColumns: number | undefined;
    const selectedRange = { startRow: 1, endRow: 1, startColumn: 2, endColumn: 2 };
    const worksheet = {
      getSheetId: () => "sheet-1",
      getMaxRows: () => 100,
      getMaxColumns: () => 26,
      getSelection: () => ({ getActiveRange: () => ({ getRange: () => selectedRange }) }),
      getRange: () => ({
        setFontFamily: () => undefined,
        setFontSize: () => undefined,
        setNumberFormat: () => undefined,
        setValue: () => undefined,
        sort: () => undefined,
      }),
      newChart: () => {
        throw new Error("chart builder is not used by the freeze action");
      },
      insertChart: () => {
        throw new Error("chart insertion is not used by the freeze action");
      },
      setFrozenRows: (rows: number) => {
        frozenRows = rows;
      },
      setFrozenColumns: (columns: number) => {
        frozenColumns = columns;
      },
    };
    const workbook = { getId: () => "workbook-1" };
    const actions = createSpreadsheetActions({
      univerAPI: {
        executeCommand: async <P extends object, R = boolean>(_id: string, _params?: P) => true as R,
        getActiveSheet: () => ({ workbook, worksheet }),
      },
      workbook,
      getDefaultWorksheet: () => worksheet,
    });

    expect(actions.applySelectionFreeze()).toBe(true);
    expect(frozenRows).toBe(1);
    expect(frozenColumns).toBe(2);
  });
});

type WrittenCell = { row: number; column: number; value: unknown; format?: string };

function makePivotActions({
  sourceValues,
  sheet2 = true,
  blankTargetCellValue = undefined,
}: {
  sourceValues: unknown[][];
  sheet2?: boolean;
  blankTargetCellValue?: null | undefined;
}) {
  const writes: Record<'Sheet1' | 'Sheet2', WrittenCell[]> = { Sheet1: [], Sheet2: [] };
  const cells: Record<'Sheet1' | 'Sheet2', Map<string, unknown>> = { Sheet1: new Map(), Sheet2: new Map() };
  const makeSheet = (name: 'Sheet1' | 'Sheet2') => ({
    getSheetId: () => name,
    getSheetName: () => name,
    getMaxRows: () => 20,
    getMaxColumns: () => 10,
    getSelection: () => ({ getActiveRange: () => ({ getRange: () => ({ startRow: 0, endRow: sourceValues.length - 1, startColumn: 0, endColumn: sourceValues[0]!.length - 1 }) }) }),
    getRange: (...args: unknown[]) => {
      if (typeof args[0] === "string") throw new Error("A1 reads are not expected");
      const [row, column, rowCount = 1, columnCount = 1] = args as [number, number, number?, number?];
      return {
        getValues: () => row === 0 && column === 0 ? sourceValues : [],
        getValue: () => name === "Sheet1" ? sourceValues[row]?.[column] : cells[name].get(`${row}:${column}`) ?? blankTargetCellValue,
        getRange: () => ({ startRow: row, endRow: row + rowCount - 1, startColumn: column, endColumn: column + columnCount - 1 }),
        setValue: (value: unknown) => { cells[name].set(`${row}:${column}`, value); writes[name].push({ row, column, value }); },
        setNumberFormat: (format: string) => { writes[name]!.at(-1)!.format = format; },
        setFontFamily: () => undefined,
        setFontSize: () => undefined,
        sort: () => undefined,
      };
    },
    newChart: () => { throw new Error("chart is not expected"); },
    insertChart: () => { throw new Error("chart is not expected"); },
    setFrozenRows: () => undefined,
    setFrozenColumns: () => undefined,
  });
  const sheet1 = makeSheet("Sheet1");
  const sheetTwo = makeSheet("Sheet2");
  const workbook = {
    getId: () => "workbook-1",
    getSheetByName: (name: string) => name === "Sheet1" ? sheet1 : name === "Sheet2" && sheet2 ? sheetTwo : null,
    insertSheet: (name = "Pivot Table") => makeSheet(name as 'Sheet1' | 'Sheet2'),
  };
  return {
    writes,
    actions: createSpreadsheetActions({
      univerAPI: { executeCommand: async () => true as never, getActiveSheet: () => ({ workbook, worksheet: sheet1 }) },
      workbook: workbook as never,
      getDefaultWorksheet: () => sheet1,
    }),
  };
}

describe("pivot destination and percentage contract", () => {
  const sourceValues = [["Category", "Amount"], ["A", 20], ["B", 30], ["C", 50]];

  it("writes an existing Sheet2 destination at A1 instead of falling back to the source sheet", async () => {
    const { actions, writes } = makePivotActions({ sourceValues });

    await expect(actions.applySelectionPivotTable({
      filterFields: [], rowFields: [0], columnFields: [], dataFields: [{ fieldIndex: 1, function: "sum" }],
      destination: "existing-sheet", destinationSheetName: "Sheet2", destinationStartRow: 0, destinationStartColumn: 0,
    })).resolves.toMatchObject({ ok: true, sheetName: "Sheet2" });

    expect(writes.Sheet2.map(({ row, column, value }) => [row, column, value])).toContainEqual([2, 1, 30]);
    expect(writes.Sheet1).toEqual([]);
  });

  it("writes finite percent-of-grand-total values and percentage formats", async () => {
    const { actions, writes } = makePivotActions({ sourceValues });

    await actions.applySelectionPivotTable({
      filterFields: [], rowFields: [0], columnFields: [],
      dataFields: [{ fieldIndex: 1, function: "sum", displayAs: "percentOfGrandTotal" }],
      destination: "existing-sheet", destinationSheetName: "Sheet2", destinationStartRow: 0, destinationStartColumn: 0,
    });

    expect(writes.Sheet2.map(({ row, column, value }) => [row, column, value])).toContainEqual([1, 1, 0.2]);
    expect(writes.Sheet2.map(({ row, column, value }) => [row, column, value])).toContainEqual([2, 1, 0.3]);
    expect(writes.Sheet2.map(({ row, column, value }) => [row, column, value])).toContainEqual([3, 1, 0.5]);
    expect(writes.Sheet2.filter((cell) => cell.format).every((cell) => cell.format === "0.00%")).toBe(true);
  });

  it("rejects blank, missing, and invalid existing destinations without source fallback", async () => {
    const { actions, writes } = makePivotActions({ sourceValues, sheet2: false });
    const base: Omit<PivotTableLayoutConfig, 'destinationSheetName'> = { filterFields: [], rowFields: [0], columnFields: [], dataFields: [{ fieldIndex: 1, function: "sum" }], destination: "existing-sheet", destinationStartRow: 0, destinationStartColumn: 0 };

    await expect(actions.applySelectionPivotTable({ ...base, destinationSheetName: " " })).resolves.toMatchObject({ ok: false });
    await expect(actions.applySelectionPivotTable({ ...base, destinationSheetName: "Missing" })).resolves.toMatchObject({ ok: false });
    await expect(actions.applySelectionPivotTable({ ...base, destinationSheetName: "Sheet1", destinationStartRow: -1 })).resolves.toMatchObject({ ok: false });
    expect(writes.Sheet1).toEqual([]);
  });

  it("keeps distinct Sheet2 pivot starts separate and renders a zero grand total as blanks", async () => {
    const { actions, writes } = makePivotActions({ sourceValues: [["Category", "Amount"], ["A", 0], ["B", 0]] });
    const config: PivotTableLayoutConfig = {
      filterFields: [], rowFields: [0], columnFields: [],
      dataFields: [{ fieldIndex: 1, function: 'sum', displayAs: 'percentOfGrandTotal' }],
      destination: 'existing-sheet', destinationSheetName: 'Sheet2', destinationStartRow: 0, destinationStartColumn: 0,
    };
    await expect(actions.applySelectionPivotTable(config)).resolves.toMatchObject({ ok: true });
    await expect(actions.applySelectionPivotTable({ ...config, destinationStartRow: 6 })).resolves.toMatchObject({ ok: true });

    expect(writes.Sheet2.map(({ row, column, value }) => [row, column, value])).toContainEqual([1, 1, '']);
    expect(writes.Sheet2.map(({ row, column, value }) => [row, column, value])).toContainEqual([7, 1, '']);
  });

  it("rejects a second pivot at the same persistent Sheet2 target cell", async () => {
    const { actions } = makePivotActions({ sourceValues });
    const config: PivotTableLayoutConfig = { filterFields: [], rowFields: [0], columnFields: [], dataFields: [{ fieldIndex: 1, function: 'sum' }], destination: 'existing-sheet', destinationSheetName: 'Sheet2', destinationStartRow: 0, destinationStartColumn: 0 };
    await expect(actions.applySelectionPivotTable(config)).resolves.toMatchObject({ ok: true });
    await expect(actions.applySelectionPivotTable(config)).resolves.toMatchObject({ ok: false, message: 'Pivot output would overwrite existing cells.' });
  });

  it("accepts a blank Sheet2 whose real worksheet facade reports null cell values", async () => {
    const { actions } = makePivotActions({ sourceValues, blankTargetCellValue: null });
    await expect(actions.applySelectionPivotTable({
      filterFields: [], rowFields: [], columnFields: [], dataFields: [{ fieldIndex: 1, function: 'sum', displayAs: 'percentOfGrandTotal' }],
      destination: 'existing-sheet', destinationSheetName: 'Sheet2', destinationStartRow: 0, destinationStartColumn: 0,
    })).resolves.toMatchObject({ ok: true, sheetName: 'Sheet2' });
  });
});
