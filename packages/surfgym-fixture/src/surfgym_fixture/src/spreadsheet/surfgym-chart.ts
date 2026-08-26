import { splitChartSourceRanges } from "./chart-range";

export type ChartRef = { id?: string; index?: number };
export type TaskScopedChartType = "line" | "column" | "bar";
export type TaskScopedChartOrientation = "Row" | "Column";
export type TaskScopedChartLegendPosition = "top" | "right" | "bottom" | "left" | "hide";
export type TaskScopedChartCellValue = string | number | boolean | null;

export type TaskScopedChartSeries = {
  name: string;
  values: TaskScopedChartCellValue[];
};

export type TaskScopedLineChart = {
  id: string;
  index: number;
  sheet: string;
  sourceSheet: string;
  categoryData: TaskScopedChartCellValue[];
  chartType: TaskScopedChartType;
  context: Record<string, unknown>;
  dataOrientation: TaskScopedChartOrientation;
  height: number;
  legendPosition: TaskScopedChartLegendPosition;
  position: { row: number; column: number; offsetX: number; offsetY: number };
  range: string[];
  seriesData: TaskScopedChartSeries[];
  sourceRange: string;
  title: string;
  width: number;
  xAxisTitle: string;
  yAxisTitle: string;
};

export type TaskScopedLineChartConfig = {
  chartType?: TaskScopedChartType;
  sourceRange: string;
  sourceSheet?: string;
  dataOrientation?: TaskScopedChartOrientation;
  title?: string;
  xAxisTitle?: string;
  yAxisTitle?: string;
  legendPosition?: TaskScopedChartLegendPosition;
  position?: Partial<TaskScopedLineChart["position"]>;
  width?: number;
  height?: number;
  context?: Record<string, unknown>;
};

export type TaskScopedLineChartUpdate = Partial<TaskScopedLineChartConfig>;

const CHART_DEFAULTS = {
  dataOrientation: "Column" as const,
  title: "",
  xAxisTitle: "",
  yAxisTitle: "",
  legendPosition: "bottom" as const,
  position: { row: 0, column: 0, offsetX: 0, offsetY: 0 },
  width: 480,
  height: 320,
};
const CHART_PLACEMENT_GAP = 16;

function cloneChart(chart: TaskScopedLineChart): TaskScopedLineChart {
  return {
    ...chart,
    categoryData: [...chart.categoryData],
    context: { ...chart.context },
    position: { ...chart.position },
    range: [...chart.range],
    seriesData: chart.seriesData.map((series) => ({ ...series, values: [...series.values] })),
  };
}

function requireChartType(value: unknown): asserts value is TaskScopedChartType {
  if (value !== "line" && value !== "column" && value !== "bar") {
    throw new Error("Chart type must be line, column, or bar.");
  }
}

function requireOrientation(value: unknown): asserts value is TaskScopedChartOrientation {
  if (value !== "Row" && value !== "Column") throw new Error("Chart data orientation must be Row or Column.");
}

function requireSourceRange(value: unknown): asserts value is string {
  if (typeof value !== "string" || !value.trim()) throw new Error("Chart source range must be a non-empty A1 range.");
}

function normalizeSheet(sheet: string | number | undefined) {
  if (sheet === undefined) return "Sheet1";
  return String(sheet);
}

function normalizeSourceRange(sourceRange: string) {
  return sourceRange.trim();
}

function normalizePosition(position: Partial<TaskScopedLineChart["position"]> | undefined) {
  const next = { ...CHART_DEFAULTS.position, ...position };
  for (const [name, value] of Object.entries(next)) {
    if (!Number.isFinite(value)) throw new Error(`Chart ${name} must be finite.`);
  }
  return next;
}

function placeCreatedChart(
  charts: TaskScopedLineChart[],
  requested: Partial<TaskScopedLineChart["position"]> | undefined,
) {
  const base = normalizePosition(requested);
  const anchored = charts.filter((chart) =>
    chart.position.row === base.row &&
    chart.position.column === base.column &&
    chart.position.offsetX === base.offsetX,
  );
  if (!anchored.length) return base;
  return {
    ...base,
    offsetY: Math.max(
      base.offsetY,
      ...anchored.map((chart) => chart.position.offsetY + chart.height + CHART_PLACEMENT_GAP),
    ),
  };
}

function positiveNumber(value: number | undefined, fallback: number, field: string) {
  const result = value ?? fallback;
  if (!Number.isFinite(result) || result <= 0) throw new Error(`Chart ${field} must be positive.`);
  return result;
}

function asLabel(value: TaskScopedChartCellValue, fallback: string) {
  return value === null || value === "" ? fallback : String(value);
}

function asChartValue(value: unknown): TaskScopedChartCellValue {
  return typeof value === "string" || typeof value === "number" || typeof value === "boolean" || value === null
    ? value
    : null;
}

export function deriveLineChartData(
  sourceMatrix: unknown[][],
  orientation: TaskScopedChartOrientation,
): Pick<TaskScopedLineChart, "categoryData" | "seriesData"> {
  const matrix = sourceMatrix.map((row) => row.map(asChartValue));
  if (matrix.length < 2 || matrix.some((row) => row.length < 2)) {
    return { categoryData: [], seriesData: [] };
  }

  if (orientation === "Row") {
    const categoryData = matrix.slice(1).map((row) => row[0] ?? null);
    const seriesData = Array.from({ length: matrix[0]!.length - 1 }, (_, offset) => {
      const column = offset + 1;
      return {
        name: asLabel(matrix[0]![column] ?? null, `Series ${column}`),
        values: matrix.slice(1).map((row) => row[column] ?? null),
      };
    });
    return { categoryData, seriesData };
  }

  const categoryData = matrix[0]!.slice(1);
  const seriesData = matrix.slice(1).map((row, offset) => ({
    name: asLabel(row[0] ?? null, `Series ${offset + 1}`),
    values: row.slice(1),
  }));
  return { categoryData, seriesData };
}

export class TaskScopedLineChartRegistry {
  private readonly chartsBySheet = new Map<string, TaskScopedLineChart[]>();
  private readonly listeners = new Set<() => void>();
  private nextId = 1;

  onChange(listener: () => void) {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  private notify() {
    for (const listener of this.listeners) listener();
  }

  private chartsFor(sheet: string | number | undefined, create = false) {
    const key = normalizeSheet(sheet);
    const current = this.chartsBySheet.get(key);
    if (current || !create) return current ?? [];
    const charts: TaskScopedLineChart[] = [];
    this.chartsBySheet.set(key, charts);
    return charts;
  }

  private reindex(charts: TaskScopedLineChart[]) {
    charts.forEach((chart, index) => { chart.index = index; });
  }

  private resolve(sheet: string | number | undefined, chartRef?: ChartRef) {
    const charts = this.chartsFor(sheet);
    if (chartRef?.id) return charts.find((chart) => chart.id === chartRef.id);
    return charts[chartRef?.index ?? 0];
  }

  create(sheet: string | number | undefined, config: TaskScopedLineChartConfig, sourceMatrix: unknown[][] = []) {
    requireSourceRange(config.sourceRange);
    const chartType = config.chartType ?? "line";
    requireChartType(chartType);
    const dataOrientation = config.dataOrientation ?? CHART_DEFAULTS.dataOrientation;
    requireOrientation(dataOrientation);
    const sourceRange = normalizeSourceRange(config.sourceRange);
    const { categoryData, seriesData } = deriveLineChartData(sourceMatrix, dataOrientation);
    const charts = this.chartsFor(sheet, true);
    const chart: TaskScopedLineChart = {
      id: `surfgym-${chartType}-chart-${this.nextId++}`,
      index: charts.length,
      sheet: normalizeSheet(sheet),
      sourceSheet: normalizeSheet(config.sourceSheet ?? sheet),
      categoryData,
      chartType,
      context: { sourceRange, ...(config.context ?? {}) },
      dataOrientation,
      height: positiveNumber(config.height, CHART_DEFAULTS.height, "height"),
      legendPosition: config.legendPosition ?? CHART_DEFAULTS.legendPosition,
      position: placeCreatedChart(charts, config.position),
      range: splitChartSourceRanges(sourceRange),
      seriesData,
      sourceRange,
      title: config.title ?? CHART_DEFAULTS.title,
      width: positiveNumber(config.width, CHART_DEFAULTS.width, "width"),
      xAxisTitle: config.xAxisTitle ?? CHART_DEFAULTS.xAxisTitle,
      yAxisTitle: config.yAxisTitle ?? CHART_DEFAULTS.yAxisTitle,
    };
    charts.push(chart);
    this.notify();
    return cloneChart(chart);
  }

  get(sheet: string | number | undefined, chartRef?: ChartRef) {
    const chart = this.resolve(sheet, chartRef);
    if (!chart) throw new Error("Chart was not found.");
    return cloneChart(chart);
  }

  list(sheet: string | number | undefined) {
    return this.chartsFor(sheet).map(cloneChart);
  }

  listAll() {
    return [...this.chartsBySheet.values()].flatMap((charts) => charts.map(cloneChart));
  }

  set(
    sheet: string | number | undefined,
    chartRef: ChartRef | undefined,
    property: keyof TaskScopedLineChart,
    value: unknown,
  ) {
    let chart = this.resolve(sheet, chartRef);
    if (!chart) {
      if (property !== "sourceRange" || typeof value !== "string") {
        throw new Error("Chart sourceRange must be set first to initialize a chart.");
      }
      this.create(sheet, { sourceRange: value });
      chart = this.resolve(sheet, chartRef);
    }
    if (!chart) throw new Error("Chart was not found.");
    if (property === "id" || property === "index" || property === "sheet" || property === "sourceSheet") {
      throw new Error(`Chart ${property} is immutable.`);
    }
    if (property === "chartType") requireChartType(value);
    if (property === "dataOrientation") requireOrientation(value);
    if (property === "sourceRange") {
      requireSourceRange(value);
      chart.sourceRange = normalizeSourceRange(value);
      chart.range = splitChartSourceRanges(chart.sourceRange);
      chart.context = { ...chart.context, sourceRange: chart.sourceRange };
    } else if (property === "width" || property === "height") {
      (chart[property] as number) = positiveNumber(value as number, chart[property] as number, property);
    } else if (property === "position") {
      chart.position = normalizePosition(value as Partial<TaskScopedLineChart["position"]>);
    } else {
      (chart[property] as unknown) = value;
    }
    this.notify();
    return cloneChart(chart);
  }

  update(
    sheet: string | number | undefined,
    chartRef: ChartRef,
    config: TaskScopedLineChartUpdate,
    sourceMatrix?: unknown[][],
  ) {
    const chart = this.resolve(sheet, chartRef);
    if (!chart) throw new Error("Chart was not found.");
    if (config.sourceRange !== undefined) {
      requireSourceRange(config.sourceRange);
      chart.sourceRange = normalizeSourceRange(config.sourceRange);
      chart.range = splitChartSourceRanges(chart.sourceRange);
      chart.context = { ...chart.context, sourceRange: chart.sourceRange };
    }
    if (config.sourceSheet !== undefined && normalizeSheet(config.sourceSheet) !== chart.sourceSheet) {
      throw new Error("Chart sourceSheet is immutable.");
    }
    if (config.chartType !== undefined) {
      requireChartType(config.chartType);
      chart.chartType = config.chartType;
    }
    if (config.dataOrientation !== undefined) {
      requireOrientation(config.dataOrientation);
      chart.dataOrientation = config.dataOrientation;
    }
    if (config.title !== undefined) chart.title = config.title;
    if (config.xAxisTitle !== undefined) chart.xAxisTitle = config.xAxisTitle;
    if (config.yAxisTitle !== undefined) chart.yAxisTitle = config.yAxisTitle;
    if (config.legendPosition !== undefined) chart.legendPosition = config.legendPosition;
    if (config.position !== undefined) chart.position = normalizePosition(config.position);
    if (config.width !== undefined) chart.width = positiveNumber(config.width, chart.width, "width");
    if (config.height !== undefined) chart.height = positiveNumber(config.height, chart.height, "height");
    if (config.context !== undefined) chart.context = { ...chart.context, ...config.context };
    if (sourceMatrix !== undefined) {
      const data = deriveLineChartData(sourceMatrix, chart.dataOrientation);
      chart.categoryData = data.categoryData;
      chart.seriesData = data.seriesData;
    }
    this.notify();
    return cloneChart(chart);
  }

  delete(sheet: string | number | undefined, chartRef?: ChartRef) {
    const charts = this.chartsFor(sheet);
    const chart = this.resolve(sheet, chartRef);
    if (!chart) return false;
    charts.splice(charts.indexOf(chart), 1);
    this.reindex(charts);
    this.notify();
    return true;
  }

  reset() {
    this.chartsBySheet.clear();
    this.nextId = 1;
    this.notify();
  }
}

export const taskScopedLineCharts = new TaskScopedLineChartRegistry();

export function getTaskScopedChartMeta(sheet: string | number | undefined, chartRef?: ChartRef) {
  return taskScopedLineCharts.get(sheet, chartRef);
}

export function setTaskScopedChartMeta(
  sheet: string | number | undefined,
  chartRef: ChartRef | undefined,
  property: keyof TaskScopedLineChart,
  value: unknown,
) {
  return taskScopedLineCharts.set(sheet, chartRef, property, value);
}

export function resetTaskScopedCharts() {
  taskScopedLineCharts.reset();
}
