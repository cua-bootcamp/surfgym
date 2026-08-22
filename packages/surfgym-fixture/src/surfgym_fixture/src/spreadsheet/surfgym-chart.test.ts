import { describe, expect, it } from "vitest";
import {
  TaskScopedLineChartRegistry,
  deriveLineChartData,
  type TaskScopedLineChart,
} from "./surfgym-chart";

const canonicalChart = {
  sourceRange: "A1:A11,E1:E11",
  dataOrientation: "Row" as const,
  title: "Dispatch volume",
  xAxisTitle: "Scan Time",
  yAxisTitle: "Pallets",
  legendPosition: "bottom" as const,
  position: { row: 12, column: 0, offsetX: 0, offsetY: 0 },
  width: 480,
  height: 320,
};

describe("task-scoped line chart canonical state", () => {
  it("creates a line chart with every evaluator-facing canonical property", () => {
    const charts = new TaskScopedLineChartRegistry();

    const chart = charts.create("Sheet1", canonicalChart, [
      ["Scan Time", "Pallets"],
      ["08:00", 20],
      ["09:00", 30],
      ["10:00", 50],
    ]);

    expect(chart).toMatchObject({
      categoryData: ["08:00", "09:00", "10:00"],
      chartType: "line",
      context: expect.any(Object),
      dataOrientation: "Row",
      height: 320,
      legendPosition: "bottom",
      position: { row: 12, column: 0, offsetX: 0, offsetY: 0 },
      range: ["A1:A11", "E1:E11"],
      seriesData: [{ name: "Pallets", values: [20, 30, 50] }],
      sourceRange: "A1:A11,E1:E11",
      title: "Dispatch volume",
      width: 480,
      xAxisTitle: "Scan Time",
      yAxisTitle: "Pallets",
    });
  });

  it("places a later chart below an occupied initial anchor", () => {
    const charts = new TaskScopedLineChartRegistry();

    const first = charts.create("Sheet1", canonicalChart);
    const second = charts.create("Sheet1", { ...canonicalChart, title: "Second" });
    const otherSheet = charts.create("Sheet2", { ...canonicalChart, title: "Other sheet" });

    expect(first.position).toEqual({ row: 12, column: 0, offsetX: 0, offsetY: 0 });
    expect(second.position).toEqual({ row: 12, column: 0, offsetX: 0, offsetY: 336 });
    expect(otherSheet.position).toEqual({ row: 12, column: 0, offsetX: 0, offsetY: 0 });
  });

  it("updates and deletes only the indexed chart on a sheet", () => {
    const charts = new TaskScopedLineChartRegistry();
    charts.create("Sheet1", canonicalChart, [["Scan Time", "Pallets"], ["08:00", 20]]);
    charts.create("Sheet1", { ...canonicalChart, title: "Second" }, [["Scan Time", "Pallets"], ["09:00", 30]]);

    const updated = charts.set("Sheet1", { index: 1 }, "title", "Edited") as TaskScopedLineChart;
    expect(updated.title).toBe("Edited");
    expect(charts.get("Sheet1", { index: 0 }).title).toBe("Dispatch volume");

    expect(charts.delete("Sheet1", { index: 0 })).toBe(true);
    expect(charts.get("Sheet1", { index: 0 }).title).toBe("Edited");
  });

  it("derives the monthly Column-orientation chart from its source matrix", () => {
    expect(deriveLineChartData(
      [["Branch", "Jan", "Feb", "Mar"], ["Total", 12, 18, 25]],
      "Column",
    )).toEqual({
      categoryData: ["Jan", "Feb", "Mar"],
      seriesData: [{ name: "Total", values: [12, 18, 25] }],
    });
  });
});
