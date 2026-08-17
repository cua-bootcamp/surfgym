// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { renderSpreadsheetMockToolbar } from "./spreadsheet-ui";

describe("task-scoped line sparkline UI", () => {
  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("does not expose the infeasible line sparkline action in the agent-facing toolbar", () => {
    document.body.innerHTML = '<div id="toolbar"></div>';
    const applySelectionLineSparklines = vi.fn(async () => true);
    renderSpreadsheetMockToolbar({
      containerId: "toolbar",
      actions: {
        applySelectionLineSparklines,
        getSelectionRangeTarget: () => ({
          range: { startRow: 1, endRow: 8, startColumn: 5, endColumn: 5 },
          worksheet: {},
        }),
        columnIndexToName: (index: number) => String.fromCharCode(65 + index),
      } as never,
    });

    expect(document.querySelector('[data-spreadsheet-sparkline]')).toBeNull();
    expect(applySelectionLineSparklines).not.toHaveBeenCalled();
  });
});
