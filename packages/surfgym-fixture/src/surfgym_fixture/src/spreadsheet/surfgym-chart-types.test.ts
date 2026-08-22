import { afterEach, describe, expect, it, vi } from "vitest";
import { createSpreadsheetActions } from "./spreadsheet-actions";
import { renderSpreadsheetMockToolbar } from "./spreadsheet-ui";
import { renderChartSvg } from "./surfgym-chart-renderer";
import { resetTaskScopedCharts, TaskScopedLineChartRegistry, taskScopedLineCharts } from "./surfgym-chart";
import { mountTaskScopedLineVisuals } from "./surfgym-line-visuals";

afterEach(() => {
  resetTaskScopedCharts();
  document.body.innerHTML = "";
});

describe("task-scoped column and bar chart vertical slice", () => {
  it("stores clustered-column source data and chart type in canonical metadata", () => {
    const charts = new TaskScopedLineChartRegistry();
    const chart = charts.create("Sheet1", {
      chartType: "column",
      sourceRange: "A1:C3",
      dataOrientation: "Column",
      title: "Quarterly sales",
    }, [
      ["Region", "Q1", "Q2"],
      ["North", 12, 18],
      ["South", 9, 15],
    ]);

    expect(chart).toMatchObject({
      id: "surfgym-column-chart-1",
      chartType: "column",
      sourceRange: "A1:C3",
      categoryData: ["Q1", "Q2"],
      seriesData: [
        { name: "North", values: [12, 18] },
        { name: "South", values: [9, 15] },
      ],
    });
  });

  it("renders separate clustered rectangles for every column series and category", () => {
    const svg = renderChartSvg({
      chartType: "column",
      categoryData: ["Q1", "Q2"],
      seriesData: [
        { name: "North", values: [12, 18] },
        { name: "South", values: [9, 15] },
      ],
      title: "Quarterly sales",
      width: 480,
      height: 320,
    });

    expect(svg).toContain('class="surfgym-column-chart"');
    expect(svg.match(/<rect /g)).toHaveLength(4);
    expect(svg).toContain('data-series="North"');
    expect(svg).toContain('data-series="South"');
  });

  it("renders horizontal bars for bar-chart canonical state", () => {
    const svg = renderChartSvg({
      chartType: "bar",
      categoryData: ["Open", "Closed"],
      seriesData: [{ name: "Tickets", values: [8, 13] }],
      title: "Ticket status",
      width: 480,
      height: 320,
    });

    expect(svg).toContain('class="surfgym-bar-chart"');
    expect(svg.match(/<rect /g)).toHaveLength(2);
    expect(svg).toContain('data-series="Tickets"');
  });

  it("passes the selected chart type from the wizard to the chart action", async () => {
    document.body.innerHTML = '<div id="toolbar"></div>';
    const applySelectionChart = vi.fn(async () => true);
    renderSpreadsheetMockToolbar({
      containerId: "toolbar",
      actions: {
        applySelectionChart,
        columnIndexToName: (index: number) => String.fromCharCode(65 + index),
        getChartDestinationSheets: () => ["Sheet1", "Sheet2"],
        getSelectionRangeTarget: () => ({
          range: { startRow: 0, endRow: 2, startColumn: 0, endColumn: 2 },
          worksheet: {},
        }),
      } as never,
    });

    document.querySelector<HTMLButtonElement>("[data-spreadsheet-chart]")!.click();
    document.querySelector<HTMLButtonElement>("[data-chart-wizard-group='column']")!.click();
    document.querySelector<HTMLButtonElement>("[data-chart-wizard-finish]")!.click();
    await Promise.resolve();

    expect(applySelectionChart).toHaveBeenCalledWith(expect.objectContaining({
      chartType: "column",
      chartLabel: "Clustered Column",
      rangeA1: "A1:C3",
    }));
  });

  it("creates column canonical state through the spreadsheet action", async () => {
    const range = { startRow: 0, endRow: 2, startColumn: 0, endColumn: 2 };
    const worksheet = {
      getSheetId: () => "sheet-1",
      getSheetName: () => "Sheet1",
      getMaxRows: () => 100,
      getMaxColumns: () => 26,
      getSelection: () => ({ getActiveRange: () => ({ getRange: () => range }) }),
      getRange: () => ({
        getRange: () => range,
        getValues: () => [["Region", "Q1", "Q2"], ["North", 12, 18], ["South", 9, 15]],
      }),
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
      chartType: "column",
      rangeA1: "A1:C3",
      dataOrientation: "Column",
    })).resolves.toBe(true);

    expect(taskScopedLineCharts.get("Sheet1")).toMatchObject({
      chartType: "column",
      categoryData: ["Q1", "Q2"],
      seriesData: [
        { name: "North", values: [12, 18] },
        { name: "South", values: [9, 15] },
      ],
    });
  });

  it("dispatches canonical column metadata through the existing overlay mount", () => {
    taskScopedLineCharts.create("Sheet1", {
      chartType: "column",
      sourceRange: "A1:C3",
      dataOrientation: "Column",
      position: { row: 1, column: 3 },
    }, [
      ["Region", "Q1", "Q2"],
      ["North", 12, 18],
      ["South", 9, 15],
    ]);
    const root = document.createElement("div");
    document.body.append(root);

    const dispose = mountTaskScopedLineVisuals({
      container: root,
      readValues: () => [],
      getActiveSheetName: () => "Sheet1",
      getGridGeometry: () => ({ originX: 45, originY: 20, columnWidth: 136, rowHeight: 24 }),
      layoutEvents: new EventTarget(),
    });

    expect(root.querySelector("[data-surfgym-chart-type='column'] .surfgym-column-chart")).not.toBeNull();
    expect(root.querySelectorAll(".surfgym-column-chart rect")).toHaveLength(4);
    dispose();
  });
});
