import { afterEach, describe, expect, it } from "vitest";
import { createSpreadsheetActions } from "./spreadsheet-actions";
import { resetTaskScopedCharts, taskScopedLineCharts } from "./surfgym-chart";

describe("task-scoped line chart action", () => {
  afterEach(() => resetTaskScopedCharts());

  it("creates a line chart from the selected source without a chart builder", async () => {
    const selectedRange = { startRow: 0, endRow: 3, startColumn: 0, endColumn: 1 };
    const worksheet = {
      getSheetId: () => "sheet-1",
      getSheetName: () => "Sheet1",
      getMaxRows: () => 100,
      getMaxColumns: () => 26,
      getSelection: () => ({ getActiveRange: () => ({ getRange: () => selectedRange }) }),
      getRange: (first: string | number) => {
        if (typeof first !== "string") throw new Error("The independent chart action reads A1 source ranges only.");
        const values = first === "A1:A4"
          ? [["Scan Time"], ["08:00"], ["09:00"], ["10:00"]]
          : [["Pallets"], [20], [30], [50]];
        return {
          getRange: () => ({ startRow: 0, endRow: 3, startColumn: 0, endColumn: 0 }),
          getValues: () => values,
        };
      },
      setFrozenRows: () => undefined,
      setFrozenColumns: () => undefined,
    };
    const workbook = { getId: () => "book-1" };
    const actions = createSpreadsheetActions({
      univerAPI: { executeCommand: async () => true, getActiveSheet: () => ({ workbook, worksheet }) },
      workbook,
      getDefaultWorksheet: () => worksheet,
    } as never);

    await expect(actions.applySelectionChart({
      chartType: "line" as never,
      rangeA1: "A1:A4,B1:B4",
      dataOrientation: "Row",
      title: "Dispatch volume",
      xAxisTitle: "Scan Time",
      yAxisTitle: "Pallets",
    })).resolves.toBe(true);

    expect(taskScopedLineCharts.get("Sheet1", { index: 0 })).toMatchObject({
      chartType: "line",
      sourceRange: "A1:A4,B1:B4",
      dataOrientation: "Row",
      title: "Dispatch volume",
      xAxisTitle: "Scan Time",
      yAxisTitle: "Pallets",
      categoryData: ["08:00", "09:00", "10:00"],
      seriesData: [{ name: "Pallets", values: [20, 30, 50] }],
    });

    await expect(actions.applySelectionChart({
      chartType: "line" as never,
      rangeA1: "A1:A4,B1:B4",
      dataOrientation: "Row",
      title: "Second dispatch volume",
    })).resolves.toBe(true);
    expect(taskScopedLineCharts.get("Sheet1", { index: 1 }).position.offsetY)
      .toBeGreaterThan(taskScopedLineCharts.get("Sheet1", { index: 0 }).position.offsetY);
  });

  it("edits supported line-chart metadata and deletes the deterministic chart id", async () => {
    const worksheet = {
      getSheetId: () => "sheet-1",
      getSheetName: () => "Sheet1",
      getMaxRows: () => 100,
      getMaxColumns: () => 26,
      getSelection: () => ({ getActiveRange: () => ({ getRange: () => ({ startRow: 0, endRow: 3, startColumn: 0, endColumn: 1 }) }) }),
      getRange: (rangeA1: string | number) => ({
        getRange: () => ({ startRow: 0, endRow: 3, startColumn: 0, endColumn: 1 }),
        getValues: () => rangeA1 === "A1:B4"
          ? [["Time", "Pallets"], ["08:00", 20], ["09:00", 30], ["10:00", 50]]
          : [["Time", "Pallets"], ["08:00", 25], ["09:00", 35], ["10:00", 55]],
      }),
      setFrozenRows: () => undefined,
      setFrozenColumns: () => undefined,
    };
    const workbook = { getId: () => "book-1", getSheetByName: () => worksheet };
    const actions = createSpreadsheetActions({
      univerAPI: { executeCommand: async () => true, getActiveSheet: () => ({ workbook, worksheet }) },
      workbook,
      getDefaultWorksheet: () => worksheet,
    } as never) as unknown as {
      applySelectionChart: (config: Parameters<ReturnType<typeof createSpreadsheetActions>["applySelectionChart"]>[0]) => Promise<boolean>;
      updateTaskScopedChart: (id: string, config: { sourceRange: string; dataOrientation: "Row"; title: string }) => Promise<boolean>;
      deleteTaskScopedChart: (id: string) => boolean;
    };

    await actions.applySelectionChart({ chartType: "line", rangeA1: "A1:B4" });
    const id = taskScopedLineCharts.get("Sheet1", { index: 0 }).id;

    await expect(actions.updateTaskScopedChart(id, {
      sourceRange: "C1:D4",
      dataOrientation: "Row",
      title: "Edited dispatch",
    })).resolves.toBe(true);
    expect(taskScopedLineCharts.get("Sheet1", { id })).toMatchObject({
      sourceRange: "C1:D4",
      dataOrientation: "Row",
      title: "Edited dispatch",
    });
    expect(actions.deleteTaskScopedChart(id)).toBe(true);
    expect(() => taskScopedLineCharts.get("Sheet1", { id })).toThrow("not found");
  });

  it("creates a canonical chart on an existing destination sheet while retaining its source sheet", async () => {
    const selectedRange = { startRow: 0, endRow: 2, startColumn: 0, endColumn: 1 };
    const sheet1 = {
      getSheetId: () => "sheet-1",
      getSheetName: () => "Sheet1",
      getMaxRows: () => 100,
      getMaxColumns: () => 26,
      getSelection: () => ({ getActiveRange: () => ({ getRange: () => selectedRange }) }),
      getRange: () => ({
        getRange: () => selectedRange,
        getValues: () => [["Month", "Sales"], ["Jan", 10], ["Feb", 20]],
      }),
      setFrozenRows: () => undefined,
      setFrozenColumns: () => undefined,
    };
    const sheet2 = { ...sheet1, getSheetId: () => "sheet-2", getSheetName: () => "Sheet2" };
    const workbook = {
      getId: () => "book-1",
      getSheets: () => [sheet1, sheet2],
      getSheetByName: (name: string) => name === "Sheet1" ? sheet1 : name === "Sheet2" ? sheet2 : null,
    };
    const actions = createSpreadsheetActions({
      univerAPI: { executeCommand: async () => true, getActiveSheet: () => ({ workbook, worksheet: sheet1 }) },
      workbook,
      getDefaultWorksheet: () => sheet1,
    } as never);

    await expect(actions.applySelectionChart({
      chartType: "column",
      rangeA1: "A1:B3",
      destinationSheet: "Sheet2",
    })).resolves.toBe(true);

    expect(taskScopedLineCharts.list("Sheet1")).toEqual([]);
    expect(taskScopedLineCharts.get("Sheet2", { index: 0 })).toMatchObject({
      chartType: "column",
      sheet: "Sheet2",
      sourceSheet: "Sheet1",
      sourceRange: "A1:B3",
      position: { row: 0, column: 0, offsetX: 20, offsetY: 20 },
    });
    await expect(actions.applySelectionChart({ chartType: "line", destinationSheet: "Missing" })).resolves.toBe(false);
    expect(taskScopedLineCharts.listAll()).toHaveLength(1);
  });
});
