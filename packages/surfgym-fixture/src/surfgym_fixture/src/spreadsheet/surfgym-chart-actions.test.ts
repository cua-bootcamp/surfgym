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
});
