import { taskScopedLineCharts } from "./surfgym-chart";
import type { TaskScopedLineChartUpdate } from "./surfgym-chart";
import { renderChartSvg } from "./surfgym-chart-renderer";
import { taskScopedLineSparklines } from "./surfgym-sparkline";
import { renderLineSparklineSvg } from "./surfgym-sparkline-renderer";

type TaskScopedLineVisualMountOptions = {
  container: HTMLElement;
  readValues: (sheet: string, sourceRange: string) => unknown[][];
  getActiveSheetName: () => string;
  getGridGeometry: () => GridGeometry;
  layoutEvents: EventTarget;
  onEditChart?: (chartId: string, update: TaskScopedLineChartUpdate) => unknown | Promise<unknown>;
  onDeleteChart?: (chartId: string) => unknown | Promise<unknown>;
};

type GridGeometry = {
  originX: number;
  originY: number;
  columnWidth: number;
  rowHeight: number;
};

function a1Coordinates(cell: string) {
  const match = /^([A-Z]+)([1-9]\d*)$/i.exec(cell.trim());
  if (!match) return null;
  const column = match[1]!.toUpperCase().split("").reduce((result, character) => result * 26 + character.charCodeAt(0) - 64, 0) - 1;
  return { column, row: Number(match[2]) - 1 };
}

function numericSourceValues(values: unknown[][]) {
  return values.flat().map((value) => (typeof value === "number" && Number.isFinite(value) ? value : 0));
}

export function mountTaskScopedLineVisuals({
  container,
  readValues,
  getActiveSheetName,
  getGridGeometry,
  layoutEvents,
  onEditChart,
  onDeleteChart,
}: TaskScopedLineVisualMountOptions) {
  const computedContainerPosition = getComputedStyle(container).position;
  if (computedContainerPosition === "static" || (!computedContainerPosition && !container.style.position)) {
    container.style.position = "relative";
  }
  const layer = document.createElement("div");
  layer.dataset.surfgymLineVisuals = "true";
  layer.style.cssText = "position:absolute; inset:0; pointer-events:none; z-index:20; overflow:hidden;";
  container.append(layer);

  const render = () => {
    layer.replaceChildren();
    const geometry = getGridGeometry();

    for (const chart of taskScopedLineCharts.list(getActiveSheetName())) {
      const chartElement = document.createElement("div");
      chartElement.dataset.surfgymLineChart = chart.id;
      chartElement.dataset.surfgymChartType = chart.chartType;
      chartElement.style.cssText = [
        "position:absolute",
        `left:${geometry.originX + chart.position.column * geometry.columnWidth + chart.position.offsetX}px`,
        `top:${geometry.originY + chart.position.row * geometry.rowHeight + chart.position.offsetY}px`,
        `width:${chart.width}px`,
        `height:${chart.height}px`,
        "background:#fff",
        "border:1px solid #94a3b8",
      ].join(";");
      chartElement.innerHTML = `
        <div style="display:flex; justify-content:flex-end; gap:4px; padding:2px; pointer-events:auto;">
          <button type="button" data-surfgym-chart-edit="${chart.id}">Edit</button>
          <button type="button" data-surfgym-chart-delete="${chart.id}">Delete</button>
        </div>
        <div data-surfgym-chart-content>${renderChartSvg(chart)}</div>
      `;
      chartElement.querySelector<HTMLButtonElement>("[data-surfgym-chart-edit]")?.addEventListener("click", () => {
        if (!onEditChart) return;
        const editor = document.createElement("div");
        editor.style.cssText = "position:absolute; inset:28px 8px auto 8px; padding:8px; background:#fff; border:1px solid #64748b; pointer-events:auto;";
        editor.innerHTML = `
          <label>Source <input data-surfgym-chart-editor-source value="${chart.sourceRange}"></label>
          <label>Orientation <select data-surfgym-chart-editor-orientation><option value="Column" ${chart.dataOrientation === "Column" ? "selected" : ""}>Column</option><option value="Row" ${chart.dataOrientation === "Row" ? "selected" : ""}>Row</option></select></label>
          <label>Title <input data-surfgym-chart-editor-title value="${chart.title}"></label>
          <button type="button" data-surfgym-chart-editor-save>Save</button>
        `;
        chartElement.append(editor);
        editor.querySelector<HTMLButtonElement>("[data-surfgym-chart-editor-save]")?.addEventListener("click", async () => {
          const sourceRange = editor.querySelector<HTMLInputElement>("[data-surfgym-chart-editor-source]")?.value.trim();
          const update: TaskScopedLineChartUpdate = {
            dataOrientation: editor.querySelector<HTMLSelectElement>("[data-surfgym-chart-editor-orientation]")?.value as "Row" | "Column",
            title: editor.querySelector<HTMLInputElement>("[data-surfgym-chart-editor-title]")?.value ?? "",
          };
          if (sourceRange) update.sourceRange = sourceRange;
          await onEditChart(chart.id, {
            ...update,
          });
        });
      });
      chartElement.querySelector<HTMLButtonElement>("[data-surfgym-chart-delete]")?.addEventListener("click", () => {
        void onDeleteChart?.(chart.id);
      });
      layer.append(chartElement);
    }

    for (const sparkline of taskScopedLineSparklines.listAll()) {
      if (!sparkline.sourceRange || sparkline.type !== "line") continue;
      const coordinates = a1Coordinates(sparkline.cell);
      if (!coordinates) continue;
      const sparklineElement = document.createElement("span");
      sparklineElement.dataset.surfgymLineSparkline = `${sparkline.sheet}!${sparkline.cell}`;
      sparklineElement.style.cssText = [
        "position:absolute",
        `left:${geometry.originX + coordinates.column * geometry.columnWidth + 2}px`,
        `top:${geometry.originY + coordinates.row * geometry.rowHeight + 2}px`,
        `width:${geometry.columnWidth - 4}px`,
        `height:${geometry.rowHeight - 4}px`,
      ].join(";");
      sparklineElement.innerHTML = renderLineSparklineSvg(
        numericSourceValues(readValues(sparkline.sheet, sparkline.sourceRange)),
      );
      layer.append(sparklineElement);
    }
  };

  const unsubscribeCharts = taskScopedLineCharts.onChange(render);
  const unsubscribeSparklines = taskScopedLineSparklines.onChange(render);
  layoutEvents.addEventListener("scroll", render);
  layoutEvents.addEventListener("active-sheet-change", render);
  window.addEventListener("resize", render);
  render();

  return () => {
    unsubscribeCharts();
    unsubscribeSparklines();
    layoutEvents.removeEventListener("scroll", render);
    layoutEvents.removeEventListener("active-sheet-change", render);
    window.removeEventListener("resize", render);
    layer.remove();
  };
}
