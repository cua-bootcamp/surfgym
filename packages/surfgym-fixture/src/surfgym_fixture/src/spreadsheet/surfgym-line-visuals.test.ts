import { afterEach, describe, expect, it } from "vitest";
import { resetTaskScopedCharts, taskScopedLineCharts } from "./surfgym-chart";
import { resetTaskScopedSparklines, taskScopedLineSparklines } from "./surfgym-sparkline";
import { mountTaskScopedLineVisuals } from "./surfgym-line-visuals";

afterEach(() => {
  resetTaskScopedCharts();
  resetTaskScopedSparklines();
  document.body.innerHTML = "";
});

describe("task-scoped line visual mount", () => {
  it("renders fixture-owned chart and sparkline SVG from canonical state and source cell values", () => {
    taskScopedLineCharts.create("Sheet1", {
      sourceRange: "A1:B4",
      dataOrientation: "Row",
      title: "Dispatch volume",
      position: { row: 2, column: 3 },
    }, [
      ["Time", "Pallets"],
      ["08:00", 20],
      ["09:00", 30],
      ["10:00", 50],
    ]);
    taskScopedLineSparklines.set("Sheet1", "F2", "sourceRange", "C2:E2");

    const root = document.createElement("div");
    document.body.append(root);
    const layoutEvents = new EventTarget();
    const dispose = mountTaskScopedLineVisuals({
      container: root,
      readValues: (_sheet, sourceRange) => sourceRange === "C2:E2" ? [[2, 4, 3]] : [],
      getGridGeometry: () => ({ originX: 45, originY: 20, columnWidth: 136, rowHeight: 24 }),
      layoutEvents,
    });

    expect(root.style.position).toBe("relative");
    expect(root.querySelector("[data-surfgym-line-chart='surfgym-line-chart-1']"))
      .not.toBeNull();
    expect(root.querySelector(".surfgym-line-chart polyline")?.getAttribute("points"))
      .toContain(",");
    expect(root.querySelector("[data-surfgym-line-sparkline='Sheet1!F2'] .surfgym-line-sparkline"))
      .not.toBeNull();
    expect(root.querySelector<HTMLElement>("[data-surfgym-line-chart]")?.style.left).toBe("453px");
    expect(root.querySelector<HTMLElement>("[data-surfgym-line-chart]")?.style.top).toBe("68px");
    expect(root.querySelector<HTMLElement>("[data-surfgym-line-sparkline='Sheet1!F2']")?.style.left).toBe("727px");
    expect(root.querySelector<HTMLElement>("[data-surfgym-line-sparkline='Sheet1!F2']")?.style.top).toBe("46px");

    taskScopedLineCharts.reset();
    expect(root.querySelector(".surfgym-line-chart")).toBeNull();
    dispose();
  });

  it("routes the chart overlay Edit and Delete controls through the fixture action callbacks", () => {
    const chart = taskScopedLineCharts.create("Sheet1", {
      sourceRange: "A1:B4",
      dataOrientation: "Column",
      title: "Original",
    }, [["Time", "Pallets"], ["08:00", 20]]);
    const edited: Array<{ id: string; title: string }> = [];
    const deleted: string[] = [];
    const root = document.createElement("div");
    document.body.append(root);
    mountTaskScopedLineVisuals({
      container: root,
      readValues: () => [],
      getGridGeometry: () => ({ originX: 45, originY: 20, columnWidth: 136, rowHeight: 24 }),
      layoutEvents: new EventTarget(),
      onEditChart: (id, update) => edited.push({ id, title: String(update.title) }),
      onDeleteChart: (id) => deleted.push(id),
    });

    root.querySelector<HTMLButtonElement>("[data-surfgym-chart-edit]")!.click();
    const title = root.querySelector<HTMLInputElement>("[data-surfgym-chart-editor-title]")!;
    title.value = "Edited";
    root.querySelector<HTMLButtonElement>("[data-surfgym-chart-editor-save]")!.click();
    root.querySelector<HTMLButtonElement>("[data-surfgym-chart-delete]")!.click();

    expect(edited).toEqual([{ id: chart.id, title: "Edited" }]);
    expect(deleted).toEqual([chart.id]);
  });

  it("repositions charts and sparklines from the supplied scroll geometry", () => {
    taskScopedLineCharts.create("Sheet1", {
      sourceRange: "A1:B4",
      dataOrientation: "Row",
      title: "Dispatch volume",
      position: { row: 2, column: 3 },
    }, [["Time", "Pallets"], ["08:00", 20]]);
    taskScopedLineSparklines.set("Sheet1", "F2", "sourceRange", "C2:E2");

    let originX = 45;
    const layoutEvents = new EventTarget();
    const root = document.createElement("div");
    document.body.append(root);
    mountTaskScopedLineVisuals({
      container: root,
      readValues: () => [[2, 4, 3]],
      getGridGeometry: () => ({ originX, originY: 20, columnWidth: 136, rowHeight: 24 }),
      layoutEvents,
    } as never);

    expect(root.querySelector<HTMLElement>("[data-surfgym-line-chart]")?.style.left).toBe("453px");
    expect(root.querySelector<HTMLElement>("[data-surfgym-line-sparkline]")?.style.left).toBe("727px");

    originX -= 544;
    layoutEvents.dispatchEvent(new Event("scroll"));

    expect(root.querySelector<HTMLElement>("[data-surfgym-line-chart]")?.style.left).toBe("-91px");
    expect(root.querySelector<HTMLElement>("[data-surfgym-line-sparkline]")?.style.left).toBe("183px");
  });
});
