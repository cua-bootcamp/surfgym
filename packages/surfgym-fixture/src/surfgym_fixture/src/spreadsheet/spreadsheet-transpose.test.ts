import { describe, expect, it, vi } from "vitest";
import { createSpreadsheetActions } from "./spreadsheet-actions";

describe("selection transpose action", () => {
  function createActionsForSelection({
    selectedRange,
    values = [[1, null, true], ["x", 2.5, false]],
    maxRows = 100,
    maxColumns = 26,
  }: {
    selectedRange: { startRow: number; endRow: number; startColumn: number; endColumn: number };
    values?: unknown[][];
    maxRows?: number;
    maxColumns?: number;
  }) {
    const setValues = vi.fn();
    const getRange = vi.fn((row: number, column: number, rows: number, columns: number) => {
      if (row === selectedRange.startRow && column === selectedRange.startColumn &&
        rows === selectedRange.endRow - selectedRange.startRow + 1 && columns === selectedRange.endColumn - selectedRange.startColumn + 1) {
        return { getValues: () => values };
      }
      return { setValues };
    });
    const worksheet = {
      getSheetId: () => "sheet-1",
      getSheetName: () => "Sheet1",
      getMaxRows: () => maxRows,
      getMaxColumns: () => maxColumns,
      getSelection: () => ({ getActiveRange: () => ({ getRange: () => selectedRange }) }),
      getRange,
      setFrozenRows: () => undefined,
      setFrozenColumns: () => undefined,
    };
    const workbook = { getId: () => "book-1" };
    return {
      actions: createSpreadsheetActions({
        univerAPI: { executeCommand: async () => true, getActiveSheet: () => ({ workbook, worksheet }) },
        workbook,
        getDefaultWorksheet: () => worksheet,
      } as never),
      getRange,
      setValues,
    };
  }

  it("writes a selected 4x5 matrix as 5x4 at B8 without mutating the source", async () => {
    const originalSourceValues = [
      ["Name", "Math", "Science", "English", "Class"],
      ["Ari", 82, 91, 77, "10A"],
      ["Bo", 74, 88, 85, "10B"],
      ["Cleo", 95, 89, 93, "10A"],
    ];
    const destinationSetValues = vi.fn();
    const selectedRange = { startRow: 1, endRow: 4, startColumn: 1, endColumn: 5 };
    const worksheet = {
      getSheetId: () => "sheet-1",
      getSheetName: () => "Sheet1",
      getMaxRows: () => 100,
      getMaxColumns: () => 26,
      getSelection: () => ({ getActiveRange: () => ({ getRange: () => selectedRange }) }),
      getRange: (row: string | number, column?: number, rows?: number, columns?: number) => {
        if (typeof row === "string") throw new Error("Transpose reads the native selected range.");
        if (row === 1 && column === 1 && rows === 4 && columns === 5) {
          return { getValues: () => originalSourceValues };
        }
        if (row === 7 && column === 1 && rows === 5 && columns === 4) {
          return { setValues: destinationSetValues };
        }
        throw new Error(`Unexpected range ${row},${column},${rows},${columns}`);
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

    await expect(actions.applySelectionTranspose({ targetCell: "B8" })).resolves.toBe(true);
    expect(destinationSetValues).toHaveBeenCalledWith([
      ["Name", "Ari", "Bo", "Cleo"],
      ["Math", 82, 74, 95],
      ["Science", 91, 88, 89],
      ["English", 77, 85, 93],
      ["Class", "10A", "10B", "10A"],
    ]);
    expect(originalSourceValues).toEqual([
      ["Name", "Math", "Science", "English", "Class"],
      ["Ari", 82, 91, 77, "10A"],
      ["Bo", 74, 88, 85, "10B"],
      ["Cleo", 95, 89, 93, "10A"],
    ]);
  });

  it.each(["A0", "1A", "ZZ9999"])("rejects invalid or out-of-bounds target %s before any write", async (targetCell) => {
    const { actions, setValues } = createActionsForSelection({
      selectedRange: { startRow: 1, endRow: 2, startColumn: 1, endColumn: 3 },
      maxRows: 10,
      maxColumns: 10,
    });

    await expect(actions.applySelectionTranspose({ targetCell })).rejects.toThrow(/target|bounds/i);
    expect(setValues).not.toHaveBeenCalled();
  });

  it("rejects an overlapping destination before reading or writing the source", async () => {
    const { actions, getRange, setValues } = createActionsForSelection({
      selectedRange: { startRow: 1, endRow: 4, startColumn: 1, endColumn: 5 },
    });

    await expect(actions.applySelectionTranspose({ targetCell: "C3" })).rejects.toThrow(/overlaps/i);
    expect(getRange).not.toHaveBeenCalled();
    expect(setValues).not.toHaveBeenCalled();
  });

  it("preserves scalar number, string, boolean, and blank values", async () => {
    const { actions, setValues } = createActionsForSelection({
      selectedRange: { startRow: 1, endRow: 2, startColumn: 1, endColumn: 3 },
    });

    await expect(actions.applySelectionTranspose({ targetCell: "H2" })).resolves.toBe(true);
    expect(setValues).toHaveBeenCalledWith([
      [1, "x"],
      [null, 2.5],
      [true, false],
    ]);
  });
});
