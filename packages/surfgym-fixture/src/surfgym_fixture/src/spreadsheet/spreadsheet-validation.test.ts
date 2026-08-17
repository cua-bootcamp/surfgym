import { afterEach, describe, expect, it } from "vitest";
import { get, set } from "./external";
import { _resetSpreadsheetState } from "./internal";
import { SpreadsheetRuntimeStore } from "./runtime";
import { createSpreadsheetActions } from "./spreadsheet-actions";

type RuntimeStoreInternals = { _runtime: unknown };

const runtimeStoreInternals = SpreadsheetRuntimeStore as unknown as RuntimeStoreInternals;
let restoreRuntime: (() => void) | undefined;

function installValidationRuntime() {
  const previousRuntime = runtimeStoreInternals._runtime;
  let nextSheetId = 1;
  const sheets: Array<ReturnType<typeof makeSheet>> = [];

  function makeSheet(initialName: string) {
    const id = `sheet-${nextSheetId++}`;
    const values = new Map<string, unknown>();
    let name = initialName;
    const sheet = {
      getSheetId: () => id,
      getSheetName: () => name,
      setName: (nextName: string) => { name = nextName; },
      getMaxRows: () => 100,
      getMaxColumns: () => 26,
      getSelection: () => ({ getActiveRange: () => ({ getRange: () => ({ startRow: 1, endRow: 28, startColumn: 3, endColumn: 3 }) }) }),
      getRange: (row: number, column: number) => ({
        getValue: () => values.get(`${row}:${column}`) ?? "existing value",
        setValue: (value: unknown) => { values.set(`${row}:${column}`, value); },
      }),
      newChart: () => { throw new Error("chart is not used by data validation"); },
      insertChart: () => { throw new Error("chart is not used by data validation"); },
      setFrozenRows: () => undefined,
      setFrozenColumns: () => undefined,
    };
    return sheet;
  }

  const sheet1 = makeSheet("Sheet1");
  sheets.push(sheet1);
  const workbook = {
    getSheets: () => [...sheets],
    getSheetByName: (name: string) => sheets.find((sheet) => sheet.getSheetName() === name) ?? null,
    getSheetBySheetId: (id: string) => sheets.find((sheet) => sheet.getSheetId() === id) ?? null,
    insertSheet: (name = "Sheet") => {
      const sheet = makeSheet(name);
      sheets.push(sheet);
      return sheet;
    },
    deleteSheet: (sheet: ReturnType<typeof makeSheet>) => {
      const index = sheets.indexOf(sheet);
      if (index < 0) return false;
      sheets.splice(index, 1);
      return true;
    },
    setActiveSheet: () => undefined,
  };
  SpreadsheetRuntimeStore.runtime = {
    workbook,
    defaultWorksheet: sheet1,
    univerAPI: { executeCommand: async () => true },
    rendered: Promise.resolve(),
    initializeWorksheet: () => undefined,
  } as never;

  return {
    restore: () => { runtimeStoreInternals._runtime = previousRuntime; },
    worksheet: sheet1,
    workbook,
  };
}

const spec = { kind: "cell" as const, sheet: "Sheet1", cell: "D2:D29", property: "validationList" as const };
const validation = { values: ["Pass", "Fail", "Held"], allowBlank: false };

describe("spreadsheet list data validation atoms", () => {
  afterEach(() => {
    restoreRuntime?.();
    restoreRuntime = undefined;
  });

  it("applies one list validation to every cell in D2:D29 and rejects malformed replacement without mutation", () => {
    const runtime = installValidationRuntime();
    restoreRuntime = runtime.restore;

    expect(() => set(spec, validation)).not.toThrow();
    expect(get(spec)).toEqual(validation);
    expect(() => set(spec, { values: [], allowBlank: false })).toThrow();
    expect(() => set(spec, { values: ["Pass", "  ", "Held"], allowBlank: false })).toThrow();
    expect(() => set(spec, { values: ["Pass", "Pass"], allowBlank: false })).toThrow();
    expect(get(spec)).toEqual(validation);
  });

  it("clears validation on reset and restores it from the atom contract", () => {
    const runtime = installValidationRuntime();
    restoreRuntime = runtime.restore;

    set(spec, validation);
    _resetSpreadsheetState();
    expect(get(spec)).toBeNull();
    expect(set(spec, validation)).toEqual(validation);
    expect(get(spec)).toEqual(validation);
  });

  it("rejects a disallowed or required-blank input without replacing the current cell value", () => {
    const runtime = installValidationRuntime();
    restoreRuntime = runtime.restore;
    set({ ...spec, cell: "D2" }, validation);
    const actions = createSpreadsheetActions({
      univerAPI: {
        executeCommand: async () => true as never,
        getActiveSheet: () => ({ workbook: runtime.workbook, worksheet: runtime.worksheet }),
      },
      workbook: runtime.workbook as never,
      getDefaultWorksheet: () => runtime.worksheet,
    });

    expect(actions.applySelectionInputValue("Pass")).toEqual({ ok: true });
    expect(runtime.worksheet.getRange(1, 3).getValue()).toBe("Pass");
    expect(actions.applySelectionInputValue("Rejected")).toEqual({ ok: false, message: "Choose a value from the validation list." });
    expect(runtime.worksheet.getRange(1, 3).getValue()).toBe("Pass");
    expect(actions.applySelectionInputValue("")).toEqual({ ok: false, message: "A value is required by the validation list." });
    expect(runtime.worksheet.getRange(1, 3).getValue()).toBe("Pass");
  });

  it("allows a blank input only when the list permits blanks", () => {
    const runtime = installValidationRuntime();
    restoreRuntime = runtime.restore;
    set({ ...spec, cell: "D2" }, { ...validation, allowBlank: true });
    const actions = createSpreadsheetActions({
      univerAPI: {
        executeCommand: async () => true as never,
        getActiveSheet: () => ({ workbook: runtime.workbook, worksheet: runtime.worksheet }),
      },
      workbook: runtime.workbook as never,
      getDefaultWorksheet: () => runtime.worksheet,
    });

    expect(actions.applySelectionInputValue("")).toEqual({ ok: true });
    expect(runtime.worksheet.getRange(1, 3).getValue()).toBe("");
  });

  it("applies and removes one validation list across the selected D2:D29 range", () => {
    const runtime = installValidationRuntime();
    restoreRuntime = runtime.restore;
    const actions = createSpreadsheetActions({
      univerAPI: {
        executeCommand: async () => true as never,
        getActiveSheet: () => ({ workbook: runtime.workbook, worksheet: runtime.worksheet }),
      },
      workbook: runtime.workbook as never,
      getDefaultWorksheet: () => runtime.worksheet,
    }) as unknown as {
      applySelectionValidationList?: (value: { values: string[]; allowBlank: boolean }) => unknown;
      removeSelectionValidationList?: () => unknown;
    };

    expect(actions.applySelectionValidationList).toEqual(expect.any(Function));
    expect(actions.applySelectionValidationList!({ values: ["Pass", "Fail", "Held"], allowBlank: true }))
      .toEqual({ values: ["Pass", "Fail", "Held"], allowBlank: true });
    expect(get(spec)).toEqual({ values: ["Pass", "Fail", "Held"], allowBlank: true });
    expect(actions.removeSelectionValidationList).toEqual(expect.any(Function));
    expect(actions.removeSelectionValidationList!()).toBeNull();
    expect(get(spec)).toBeNull();
  });

  it("reads the uniform validation list for the current selection", () => {
    const runtime = installValidationRuntime();
    restoreRuntime = runtime.restore;
    set(spec, validation);
    const actions = createSpreadsheetActions({
      univerAPI: {
        executeCommand: async () => true as never,
        getActiveSheet: () => ({ workbook: runtime.workbook, worksheet: runtime.worksheet }),
      },
      workbook: runtime.workbook as never,
      getDefaultWorksheet: () => runtime.worksheet,
    });

    expect(actions.getSelectionValidationList()).toEqual(validation);
  });
});
