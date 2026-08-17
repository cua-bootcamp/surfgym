import { readFileSync } from "node:fs";
import { join } from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import { get, set, type SpreadsheetSpec } from "./external";
import type { Value } from "../external";
import { createSpreadsheetActions } from "./spreadsheet-actions";
import { SpreadsheetRuntimeStore } from "./runtime";
import { renderSpreadsheetMockToolbar } from "./spreadsheet-ui";

type RuntimeStoreInternals = {
  _runtime: unknown;
};

type SeedAtom = {
  spec: SpreadsheetSpec;
  value: Value;
};

type FreezeSeed = {
  states: [SeedAtom[], SeedAtom[]];
};

const runtimeStoreInternals = SpreadsheetRuntimeStore as unknown as RuntimeStoreInternals;
let restoreSpreadsheetRuntime: (() => void) | undefined;

function readFreezeSeed(): FreezeSeed {
  const seedPath = join(
    process.cwd(),
    "../../../surfgym-task/src/surfgym_task/data/spreadsheet/seeds/freeze_first_row_and_two_columns.json",
  );
  return JSON.parse(readFileSync(seedPath, "utf8")) as FreezeSeed;
}

function installFreezeSeedRuntime() {
  const previousRuntime = runtimeStoreInternals._runtime;
  const cells = new Map<string, Record<string, unknown>>();
  let frozenRows = 0;
  let frozenColumns = 0;
  const selection = { startRow: 1, endRow: 1, startColumn: 2, endColumn: 2 };
  const worksheet = {
    getSheetId: () => "freeze-seed-sheet-1",
    getSheetName: () => "Sheet1",
    getMaxRows: () => 100,
    getMaxColumns: () => 26,
    getFrozenRows: () => frozenRows,
    getFrozenColumns: () => frozenColumns,
    setFrozenRows: (value: number) => {
      frozenRows = value;
    },
    setFrozenColumns: (value: number) => {
      frozenColumns = value;
    },
    getSelection: () => ({
      getActiveRange: () => ({ getRange: () => selection }),
    }),
    getSheet: () => ({
      getCellRaw: (row: number, column: number) => cells.get(`${row}:${column}`),
    }),
    getRange: (row: number, column: number) => ({
      getRange: () => ({ startRow: row, endRow: row, startColumn: column, endColumn: column }),
      getCellStyleData: () => ({}),
      setValueForCell: (value: Record<string, unknown>) => {
        cells.set(`${row}:${column}`, structuredClone(value));
      },
      clearContent: () => {
        cells.delete(`${row}:${column}`);
      },
      setFontFamily: () => undefined,
      setFontSize: () => undefined,
      setNumberFormat: () => undefined,
      setValue: () => undefined,
      sort: () => undefined,
    }),
    newChart: () => {
      throw new Error("chart builder is not used by the freeze seed");
    },
    insertChart: () => {
      throw new Error("chart insertion is not used by the freeze seed");
    },
  };
  const workbook = {
    getId: () => "freeze-seed-workbook",
    getSheets: () => [worksheet],
    getSheetByName: (name: string) => (name === "Sheet1" ? worksheet : null),
    getSheetBySheetId: (id: string) => (id === "freeze-seed-sheet-1" ? worksheet : null),
    setActiveSheet: () => undefined,
  };
  const univerAPI = {
    executeCommand: async () => true as never,
    getActiveSheet: () => ({ workbook, worksheet }),
  };

  SpreadsheetRuntimeStore.runtime = {
    workbook,
    defaultWorksheet: worksheet,
    univerAPI,
    rendered: Promise.resolve(),
    initializeWorksheet: () => undefined,
  } as never;

  return {
    actions: createSpreadsheetActions({
      univerAPI: univerAPI as never,
      workbook: workbook as never,
      getDefaultWorksheet: () => worksheet as never,
    }),
    restore: () => {
      runtimeStoreInternals._runtime = previousRuntime;
    },
  };
}

afterEach(() => {
  document.body.innerHTML = "";
  restoreSpreadsheetRuntime?.();
  restoreSpreadsheetRuntime = undefined;
});

describe("freeze source task seed smoke", () => {
  it("drives the actual 4188 seed setup, Freeze toolbar action, and evaluator atoms", () => {
    const seed = readFreezeSeed();
    const runtime = installFreezeSeedRuntime();
    restoreSpreadsheetRuntime = runtime.restore;

    for (const atom of seed.states[0]) {
      expect(set(atom.spec, atom.value)).toBeUndefined();
      expect(get(atom.spec)).toEqual(atom.value);
    }

    document.body.innerHTML = '<div id="spreadsheet-toolbar"></div>';
    renderSpreadsheetMockToolbar({
      containerId: "spreadsheet-toolbar",
      univerAPI: {
        executeCommand: async <P extends object, R = boolean>(_id: string, _params?: P) => true as R,
      },
      actions: runtime.actions,
    });
    document
      .querySelector<HTMLButtonElement>('[data-spreadsheet-format-action="freeze"]')!
      .click();

    expect(seed.states[1].map((atom) => get(atom.spec))).toEqual(
      seed.states[1].map((atom) => atom.value),
    );
  });
});
