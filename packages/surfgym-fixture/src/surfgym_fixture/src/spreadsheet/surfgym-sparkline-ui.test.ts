// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { renderSpreadsheetMockToolbar, setupSpreadsheetUi } from "./spreadsheet-ui";

describe("task-scoped line sparkline UI", () => {
  afterEach(() => {
    vi.useRealTimers();
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

  it("does not append Sparkline to the actual Start toolbar", () => {
    vi.useFakeTimers();
    document.body.innerHTML = '<div id="spreadsheet-body"></div><div data-u-comp="ribbon-toolbar" aria-label="Start"></div>';
    const appendTo = vi.fn();

    setupSpreadsheetUi({
      univerAPI: {
        createMenu: vi.fn(() => ({ appendTo })),
        executeCommand: vi.fn(async () => true) as never,
      },
      actions: { getSelectionRangeTarget: vi.fn(() => null) } as never,
      conditionalFormattingCommandId: "test.conditional-formatting",
    });
    vi.runAllTimers();

    const startToolbar = document.querySelector('[data-u-comp="ribbon-toolbar"]');
    expect(startToolbar?.querySelector('[aria-label="Chart Wizard"]')).not.toBeNull();
    expect(startToolbar?.querySelector('[aria-label="Sparkline"]')).toBeNull();
  });
});
