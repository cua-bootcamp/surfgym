import { afterEach, describe, expect, it } from "vitest";
import { get, set } from "./external";
import { SpreadsheetRuntimeStore } from "./runtime";
import { _resetSpreadsheetState } from "./internal";

type SparklineGroup = {
  config: { type: "line" };
  sourceRange: { startRow: number; endRow: number; startColumn: number; endColumn: number } | null;
};

type RuntimeStoreInternals = {
  _runtime: unknown;
};

const runtimeStoreInternals = SpreadsheetRuntimeStore as unknown as RuntimeStoreInternals;
let restoreSpreadsheetRuntime: (() => void) | undefined;

function installSpreadsheetRuntime() {
  const previousRuntime = runtimeStoreInternals._runtime;
  let frozenRows = 0;
  let frozenColumns = 0;
  const sparkline: SparklineGroup = { config: { type: "line" }, sourceRange: null };
  const worksheet = {
    getSheetId: () => "sheet-1",
    getSheetName: () => "Sheet1",
    getFrozenRows: () => frozenRows,
    getFrozenColumns: () => frozenColumns,
    setFrozenRows: (value: number) => {
      frozenRows = value;
    },
    setFrozenColumns: (value: number) => {
      frozenColumns = value;
    },
    getRange: (...args: number[]) => {
      const [startRow, startColumn, rowCount = 1, columnCount = 1] = args;
      if (startRow === undefined || startColumn === undefined) throw new Error("numeric ranges are expected");
      const range = {
        startRow,
        endRow: startRow + rowCount - 1,
        startColumn,
        endColumn: startColumn + columnCount - 1,
      };
      return { getRange: () => range };
    },
    addSparkline: (sourceRanges: typeof sparkline.sourceRange[], _targetRanges: unknown[], type: "line") => {
      sparkline.sourceRange = sourceRanges[0] ?? null;
      sparkline.config.type = type;
      return {};
    },
    getAllSubSparkline: () => new Map([["warehouse", {
      config: sparkline.config,
      sparklines: {
        getValue: (row: number, column: number) => row === 1 && column === 5 ? sparkline.sourceRange : null,
      },
    }]]),
    getSparklineGroupByCell: () => ({
      setConfig: ({ type }: { type: "line" }) => {
        sparkline.config.type = type;
      },
    }),
  };
  const workbook = {
    getSheets: () => [worksheet],
    getSheetByName: (name: string) => name === "Sheet1" ? worksheet : null,
    getSheetBySheetId: (id: string) => id === "sheet-1" ? worksheet : null,
    setActiveSheet: () => undefined,
    insertSheet: () => ({ ...worksheet, setName: () => undefined }),
    deleteSheet: () => true,
  };

  SpreadsheetRuntimeStore.runtime = {
    workbook,
    defaultWorksheet: worksheet,
    univerAPI: { executeCommand: async () => true },
    rendered: Promise.resolve(),
    initializeWorksheet: () => undefined,
  } as never;

  return () => {
    runtimeStoreInternals._runtime = previousRuntime;
  };
}

function installResettableFreezeRuntime() {
  const previousRuntime = runtimeStoreInternals._runtime;
  let nextId = 0;
  let sheets: Array<ReturnType<typeof createWorksheet>> = [];

  function createWorksheet(initialName: string) {
    const id = `freeze-sheet-${nextId++}`;
    let name = initialName;
    let frozenRows = 0;
    let frozenColumns = 0;

    return {
      getSheetId: () => id,
      getSheetName: () => name,
      setName: (nextName: string) => {
        name = nextName;
      },
      getFrozenRows: () => frozenRows,
      getFrozenColumns: () => frozenColumns,
      setFrozenRows: (value: number) => {
        frozenRows = value;
      },
      setFrozenColumns: (value: number) => {
        frozenColumns = value;
      },
    };
  }

  sheets = [createWorksheet("Sheet1")];
  const workbook = {
    getSheets: () => sheets,
    getSheetByName: (name: string) => sheets.find((sheet) => sheet.getSheetName() === name) ?? null,
    getSheetBySheetId: (id: string) => sheets.find((sheet) => sheet.getSheetId() === id) ?? null,
    setActiveSheet: () => undefined,
    insertSheet: (name: string, options?: { index?: number }) => {
      const sheet = createWorksheet(name);
      sheets.splice(options?.index ?? sheets.length, 0, sheet);
      return sheet;
    },
    deleteSheet: (sheet: ReturnType<typeof createWorksheet>) => {
      sheets = sheets.filter((candidate) => candidate !== sheet);
      return true;
    },
  };

  SpreadsheetRuntimeStore.runtime = {
    workbook,
    defaultWorksheet: sheets[0]!,
    univerAPI: { executeCommand: async () => true },
    rendered: Promise.resolve(),
    initializeWorksheet: () => undefined,
  } as never;

  return () => {
    runtimeStoreInternals._runtime = previousRuntime;
  };
}

describe("existing spreadsheet state atoms", () => {
  afterEach(() => {
    restoreSpreadsheetRuntime?.();
    restoreSpreadsheetRuntime = undefined;
  });

  it("restores the spreadsheet runtime that was installed before a fixture", () => {
    const previousRuntime = runtimeStoreInternals._runtime;
    const restore = installSpreadsheetRuntime();

    restore();

    expect(runtimeStoreInternals._runtime).toBe(previousRuntime);
  });

  it("round-trips frozen row and column counts through external sheet atoms", () => {
    restoreSpreadsheetRuntime = installSpreadsheetRuntime();

    expect(set({ kind: "sheet", sheet: "Sheet1", property: "frozenRows" }, 1)).toBe(1);
    expect(set({ kind: "sheet", sheet: "Sheet1", property: "frozenColumns" }, 2)).toBe(2);
    expect(get({ kind: "sheet", sheet: "Sheet1", property: "frozenRows" })).toBe(1);
    expect(get({ kind: "sheet", sheet: "Sheet1", property: "frozenColumns" })).toBe(2);
  });

  it("round-trips the A1:B1 freeze contract after reset through existing sheet atoms", () => {
    restoreSpreadsheetRuntime = installResettableFreezeRuntime();
    const rowsSpec = { kind: "sheet" as const, sheet: "Sheet1", property: "frozenRows" as const };
    const columnsSpec = { kind: "sheet" as const, sheet: "Sheet1", property: "frozenColumns" as const };

    expect(set(rowsSpec, 1)).toBe(1);
    expect(set(columnsSpec, 2)).toBe(2);
    expect([get(rowsSpec), get(columnsSpec)]).toEqual([1, 2]);

    _resetSpreadsheetState();
    expect([get(rowsSpec), get(columnsSpec)]).toEqual([0, 0]);

    expect(set(rowsSpec, 1)).toBe(1);
    expect(set(columnsSpec, 2)).toBe(2);
    expect([get(rowsSpec), get(columnsSpec)]).toEqual([1, 2]);
  });

  it("records a line sparkline source and type through existing atoms", () => {
    restoreSpreadsheetRuntime = installSpreadsheetRuntime();

    expect(set({ kind: "sparkline", sheet: "Sheet1", cell: "F2", property: "sourceRange" }, "C2:E2"))
      .toEqual({ sourceRange: "C2:E2", type: "line" });
    expect(set({ kind: "sparkline", sheet: "Sheet1", cell: "F2", property: "type" }, "line"))
      .toEqual({ sourceRange: "C2:E2", type: "line" });
    expect(get({ kind: "sparkline", sheet: "Sheet1", cell: "F2", property: "sourceRange" })).toBe("C2:E2");
    expect(get({ kind: "sparkline", sheet: "Sheet1", cell: "F2", property: "type" })).toBe("line");
  });

  it("uses fixture-owned chart and sparkline atoms without a chart or sparkline facade", () => {
    restoreSpreadsheetRuntime = installResettableFreezeRuntime();
    const chartSource = { kind: "chart" as const, sheet: "Sheet1", chart: { index: 0 }, property: "sourceRange" as const };
    const chartType = { kind: "chart" as const, sheet: "Sheet1", chart: { index: 0 }, property: "chartType" as const };
    const orientation = { kind: "chart" as const, sheet: "Sheet1", chart: { index: 0 }, property: "dataOrientation" as const };
    const sparklineSource = { kind: "sparkline" as const, sheet: "Sheet1", cell: "F2", property: "sourceRange" as const };
    const sparklineType = { kind: "sparkline" as const, sheet: "Sheet1", cell: "F2", property: "type" as const };

    set(chartSource, "A1:A11,E1:E11");
    set(chartType, "line");
    set(orientation, "Row");
    set(sparklineSource, "C2:E2");
    set(sparklineType, "line");

    expect(get(chartSource)).toBe("A1:A11,E1:E11");
    expect(get(chartType)).toBe("line");
    expect(get(orientation)).toBe("Row");
    expect(get(sparklineSource)).toBe("C2:E2");
    expect(get(sparklineType)).toBe("line");

    _resetSpreadsheetState();
    expect(() => get(chartSource)).toThrow("Chart was not found");
    expect(get(sparklineSource)).toBeNull();
  });

  it("round-trips a typed pivot definition through the canonical atom surface", () => {
    const pivot = {
      sourceRange: "A1:B4", rowFields: [0], columnFields: [],
      dataFields: [{ fieldIndex: 1, function: "sum", displayAs: "percentOfGrandTotal" }],
      targetSheet: "Sheet2", startRow: 0, startColumn: 0,
    };
    const spec = { kind: "pivot" as const, sheet: "Sheet2", startRow: 0, startColumn: 0, property: "definition" as const };

    expect(set(spec, pivot)).toEqual(pivot);
    expect(get(spec)).toEqual(pivot);
    expect(() => set({ ...spec, startRow: -1 }, pivot)).toThrow("Invalid pivot atom address");
  });

  it("rejects malformed pivot metadata instead of registering evaluator-controlled payloads", () => {
    const spec = { kind: "pivot" as const, sheet: "Sheet2", startRow: 0, startColumn: 0, property: "definition" as const };
    const valid = { sourceRange: "A1:B4", rowFields: [0], columnFields: [], dataFields: [{ fieldIndex: 1, function: "sum", displayAs: "value" }], targetSheet: "Sheet2", startRow: 0, startColumn: 0 };
    set(spec, valid);
    expect(() => set(spec, { ...valid, rowFields: [-1] })).toThrow("Pivot metadata");
    expect(() => set(spec, { ...valid, dataFields: [{ fieldIndex: 1, function: "bogus", displayAs: "value" }] })).toThrow("Pivot metadata");
    expect(() => set(spec, { ...valid, dataFields: [{ fieldIndex: 1, function: "sum", displayAs: "bogus" }] })).toThrow("Pivot metadata");
    expect(() => set(spec, { ...valid, sourceRange: "not-a-range" })).toThrow("Pivot metadata");
    expect(get(spec)).toEqual(valid);
  });

  it("clears pivot metadata on reset before a later atom write/read roundtrip", () => {
    restoreSpreadsheetRuntime = installSpreadsheetRuntime();
    const spec = { kind: "pivot" as const, sheet: "Sheet2", startRow: 0, startColumn: 0, property: "definition" as const };
    const pivot = { sourceRange: "A1:B4", rowFields: [0], columnFields: [], dataFields: [{ fieldIndex: 1, function: "sum", displayAs: "value" }], targetSheet: "Sheet2", startRow: 0, startColumn: 0 };
    set(spec, pivot);
    expect(get(spec)).toEqual(pivot);
    _resetSpreadsheetState();
    expect(() => get(spec)).toThrow("Pivot not found");
    expect(set(spec, pivot)).toEqual(pivot);
    expect(get(spec)).toEqual(pivot);
  });
});
