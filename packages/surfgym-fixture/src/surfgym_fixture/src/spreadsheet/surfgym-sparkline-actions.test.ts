import { afterEach, describe, expect, it } from "vitest";
import { createSpreadsheetActions } from "./spreadsheet-actions";
import { resetTaskScopedSparklines, taskScopedLineSparklines } from "./surfgym-sparkline";

describe("task-scoped line sparkline action", () => {
  afterEach(() => resetTaskScopedSparklines());

  it("maps the F2:F9 selection to the corresponding C:E source rows without a runtime command", async () => {
    const selectedRange = { startRow: 1, endRow: 8, startColumn: 5, endColumn: 5 };
    const worksheet = {
      getSheetId: () => "sheet-1",
      getSheetName: () => "Sheet1",
      getMaxRows: () => 100,
      getMaxColumns: () => 26,
      getSelection: () => ({ getActiveRange: () => ({ getRange: () => selectedRange }) }),
      getRange: () => ({ getRange: () => selectedRange }),
      setFrozenRows: () => undefined,
      setFrozenColumns: () => undefined,
    };
    const workbook = { getId: () => "book-1" };
    const actions = createSpreadsheetActions({
      univerAPI: { executeCommand: async () => true, getActiveSheet: () => ({ workbook, worksheet }) },
      workbook,
      getDefaultWorksheet: () => worksheet,
    } as never) as unknown as {
      applySelectionLineSparklines: (config: { sourceRange: string }) => Promise<boolean>;
    };

    await expect(actions.applySelectionLineSparklines({ sourceRange: "C2:E9" })).resolves.toBe(true);
    expect(taskScopedLineSparklines.get("Sheet1", "F2")).toEqual({ sourceRange: "C2:E2", type: "line" });
    expect(taskScopedLineSparklines.get("Sheet1", "F9")).toEqual({ sourceRange: "C9:E9", type: "line" });
  });
});
