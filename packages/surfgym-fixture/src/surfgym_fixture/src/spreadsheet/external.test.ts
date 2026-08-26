import { afterEach, describe, expect, it } from "vitest";
import { get, set } from "./external";
import { SpreadsheetRuntimeStore } from "./runtime";
import { _resetSpreadsheetState } from "./internal";
import { resetTaskScopedCharts } from "./surfgym-chart";

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
      getRange: (_rangeA1: string) => ({
        getValues: () => [["Scan Time", "Pallets"], ["08:00", 20]],
      }),
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

function installChartRuntime() {
  const previousRuntime = runtimeStoreInternals._runtime;
  const rangeValues = new Map<string, unknown[][]>([
    ["Sheet1:A1:B3", [["Date", "Tickets"], ["Mon", 4], ["Tue", 7]]],
    ["Sheet1:A1:A3", [["Date"], ["Mon"], ["Tue"]]],
    ["Sheet1:C1:C3", [["Tickets"], [4], [7]]],
    ["Report, O'Brien:A1:B3", [["Date", "Tickets"], ["Mon", 4], ["Tue", 7]]],
  ]);

  function createWorksheet(name: string, id: string) {
    return {
      getSheetId: () => id,
      getSheetName: () => name,
      getRange: (rangeA1: string) => ({
        getRange: () => ({ startRow: 0, endRow: 2, startColumn: 0, endColumn: 1 }),
        getValues: () => rangeValues.get(`${name}:${rangeA1}`) ?? [],
      }),
    };
  }

  const sheet1 = createWorksheet("Sheet1", "sheet-1");
  const sheet2 = createWorksheet("Sheet2", "sheet-2");
  const quoted = createWorksheet("Report, O'Brien", "sheet-quoted");
  const sheets = [sheet1, sheet2, quoted];
  SpreadsheetRuntimeStore.runtime = {
    workbook: {
      getSheets: () => sheets,
      getSheetByName: (name: string) => sheets.find((sheet) => sheet.getSheetName() === name) ?? null,
      getSheetBySheetId: (id: string) => sheets.find((sheet) => sheet.getSheetId() === id) ?? null,
    },
    defaultWorksheet: sheet1,
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
    resetTaskScopedCharts();
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

    set(chartSource, "Sheet1!A1:A11,Sheet1!E1:E11");
    set(chartType, "line");
    set(orientation, "Row");
    set(sparklineSource, "C2:E2");
    set(sparklineType, "line");

    expect(get(chartSource)).toBe("Sheet1!A1:A11,Sheet1!E1:E11");
    expect(get(chartType)).toBe("line");
    expect(get(orientation)).toBe("Row");
    expect(get(sparklineSource)).toBe("C2:E2");
    expect(get(sparklineType)).toBe("line");

    _resetSpreadsheetState();
    expect(() => get(chartSource)).toThrow("Chart was not found");
    expect(get(sparklineSource)).toBeNull();
  });

  it("catches an external source setter that leaks qualified ranges into runtime state", () => {
    restoreSpreadsheetRuntime = installChartRuntime();
    const source = { kind: "chart" as const, sheet: "Sheet2", chart: { index: 0 }, property: "sourceRange" as const };

    const chart = set(source, "Sheet1!A1:B3") as { sourceSheet: string; sourceRange: string };

    expect(chart).toMatchObject({ sourceSheet: "Sheet1", sourceRange: "A1:B3" });
    expect(get(source)).toBe("Sheet1!A1:B3");
  });

  it("catches source materialization that does not read cells or rederive data after orientation", () => {
    restoreSpreadsheetRuntime = installChartRuntime();
    const source = { kind: "chart" as const, sheet: "Sheet2", chart: { index: 0 }, property: "sourceRange" as const };
    const orientation = { kind: "chart" as const, sheet: "Sheet2", chart: { index: 0 }, property: "dataOrientation" as const };

    set(source, "Sheet1!A1:B3");
    const chart = set(orientation, "Row") as { categoryData: unknown[]; seriesData: unknown[] };

    expect(chart.categoryData).toEqual(["Mon", "Tue"]);
    expect(chart.seriesData).toEqual([{ name: "Tickets", values: [4, 7] }]);
  });

  it("catches a parser that accepts unqualified or mixed-sheet external chart sources", () => {
    restoreSpreadsheetRuntime = installChartRuntime();
    const source = { kind: "chart" as const, sheet: "Sheet2", chart: { index: 0 }, property: "sourceRange" as const };

    expect(() => set(source, "A1:B3")).toThrow(/qualified/i);
    expect(() => set(source, "Sheet1!A1:A3,Sheet2!C1:C3")).toThrow(/one source sheet/i);
  });

  it("catches canonical formatting that loses commas or doubled apostrophes in sheet names", () => {
    restoreSpreadsheetRuntime = installChartRuntime();
    const source = { kind: "chart" as const, sheet: "Sheet2", chart: { index: 0 }, property: "sourceRange" as const };

    const chart = set(source, "'Report, O''Brien'!A1:B3") as { sourceSheet: string; sourceRange: string };

    expect(chart).toMatchObject({ sourceSheet: "Report, O'Brien", sourceRange: "A1:B3" });
    expect(get(source)).toBe("'Report, O''Brien'!A1:B3");
  });

  it("catches same-sheet multi-range parsing that retains logical qualifiers in physical ranges", () => {
    restoreSpreadsheetRuntime = installChartRuntime();
    const source = { kind: "chart" as const, sheet: "Sheet1", chart: { index: 0 }, property: "sourceRange" as const };

    const chart = set(source, "Sheet1!A1:A3,Sheet1!C1:C3") as {
      sourceRange: string;
      categoryData: unknown[];
      seriesData: unknown[];
    };

    expect(chart.sourceRange).toBe("A1:A3,C1:C3");
    expect(chart.categoryData).toEqual(["Tickets"]);
    expect(chart.seriesData).toEqual([
      { name: "Mon", values: [4] },
      { name: "Tue", values: [7] },
    ]);
    expect(get(source)).toBe("Sheet1!A1:A3,Sheet1!C1:C3");
  });

  it("catches the arbitrary A1:B2 fallback when a non-source atom initializes a chart", () => {
    const title = { kind: "chart" as const, sheet: "Sheet1", chart: { index: 0 }, property: "title" as const };

    expect(() => set(title, "Not initialized")).toThrow(/sourceRange.*first/i);
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
