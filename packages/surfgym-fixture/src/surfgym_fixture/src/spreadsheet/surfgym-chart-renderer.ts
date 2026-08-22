import type { TaskScopedChartType } from "./surfgym-chart";

type ChartRenderInput = {
  chartType: TaskScopedChartType;
  categoryData: unknown[];
  seriesData: Array<{ name: string; values: unknown[] }>;
  title: string;
  width: number;
  height: number;
};

type LineChartRenderInput = Omit<ChartRenderInput, "chartType">;

const SERIES_COLORS = ["#2563eb", "#dc2626", "#16a34a", "#d97706", "#7c3aed"];

function escapeSvgText(value: unknown) {
  return String(value).replace(/[&<>\"]/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[character]!);
}

function numericValues(values: unknown[]) {
  return values.map((value) => typeof value === "number" && Number.isFinite(value) ? value : 0);
}

function chartDomain(seriesData: ChartRenderInput["seriesData"]) {
  const allValues = seriesData.flatMap((series) => numericValues(series.values));
  const max = Math.max(1, ...allValues);
  const min = Math.min(0, ...allValues);
  return { min, range: Math.max(1, max - min) };
}

function renderLineChart({ categoryData, seriesData, title, width, height }: LineChartRenderInput) {
  const { min, range } = chartDomain(seriesData);
  const x = (index: number, total: number) => 32 + (total <= 1 ? 0 : index * ((width - 44) / (total - 1)));
  const y = (value: number) => 20 + (height - 42) * (1 - ((value - min) / range));
  const paths = seriesData.map((series, seriesIndex) => {
    const values = numericValues(series.values);
    const points = values.map((value, index) => `${x(index, values.length)},${y(value)}`).join(" ");
    const color = SERIES_COLORS[seriesIndex % SERIES_COLORS.length]!;
    const marker = values.length === 1
      ? `<circle data-series-marker="${escapeSvgText(series.name)}" cx="${x(0, values.length)}" cy="${y(values[0]!)}" r="3" fill="${color}"/>`
      : "";
    return `<polyline data-series="${escapeSvgText(series.name)}" fill="none" stroke="${color}" stroke-width="2" points="${points}"/>${marker}`;
  }).join("");
  const labels = categoryData.map((category, index) => `<text x="${x(index, categoryData.length)}" y="${height - 6}" text-anchor="middle">${escapeSvgText(category)}</text>`).join("");
  return `<svg class="surfgym-line-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeSvgText(title || "Line chart")}"><line x1="32" y1="20" x2="32" y2="${height - 22}" stroke="#64748b"/><line x1="32" y1="${height - 22}" x2="${width - 12}" y2="${height - 22}" stroke="#64748b"/><text x="${width / 2}" y="14" text-anchor="middle">${escapeSvgText(title)}</text>${paths}${labels}</svg>`;
}

function renderColumnChart({ categoryData, seriesData, title, width, height }: LineChartRenderInput) {
  const { min, range } = chartDomain(seriesData);
  const plotLeft = 40;
  const plotTop = 20;
  const plotBottom = height - 24;
  const plotWidth = Math.max(1, width - plotLeft - 12);
  const plotHeight = Math.max(1, plotBottom - plotTop);
  const y = (value: number) => plotTop + plotHeight * (1 - ((value - min) / range));
  const baseline = y(0);
  const categoryCount = Math.max(1, categoryData.length);
  const seriesCount = Math.max(1, seriesData.length);
  const groupWidth = plotWidth / categoryCount;
  const clusterWidth = groupWidth * 0.72;
  const barWidth = clusterWidth / seriesCount;
  const bars = seriesData.flatMap((series, seriesIndex) => numericValues(series.values).map((value, categoryIndex) => {
    const valueY = y(value);
    const x = plotLeft + categoryIndex * groupWidth + (groupWidth - clusterWidth) / 2 + seriesIndex * barWidth;
    return `<rect data-series="${escapeSvgText(series.name)}" data-category-index="${categoryIndex}" x="${x}" y="${Math.min(valueY, baseline)}" width="${Math.max(1, barWidth - 2)}" height="${Math.max(0, Math.abs(baseline - valueY))}" fill="${SERIES_COLORS[seriesIndex % SERIES_COLORS.length]}"/>`;
  })).join("");
  const labels = categoryData.map((category, index) => `<text x="${plotLeft + (index + 0.5) * groupWidth}" y="${height - 6}" text-anchor="middle">${escapeSvgText(category)}</text>`).join("");
  return `<svg class="surfgym-column-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeSvgText(title || "Column chart")}"><line x1="${plotLeft}" y1="${plotTop}" x2="${plotLeft}" y2="${plotBottom}" stroke="#64748b"/><line x1="${plotLeft}" y1="${baseline}" x2="${width - 12}" y2="${baseline}" stroke="#64748b"/><text x="${width / 2}" y="14" text-anchor="middle">${escapeSvgText(title)}</text>${bars}${labels}</svg>`;
}

function renderBarChart({ categoryData, seriesData, title, width, height }: LineChartRenderInput) {
  const { min, range } = chartDomain(seriesData);
  const plotLeft = 72;
  const plotTop = 22;
  const plotRight = width - 12;
  const plotHeight = Math.max(1, height - plotTop - 12);
  const plotWidth = Math.max(1, plotRight - plotLeft);
  const x = (value: number) => plotLeft + plotWidth * ((value - min) / range);
  const baseline = x(0);
  const categoryCount = Math.max(1, categoryData.length);
  const seriesCount = Math.max(1, seriesData.length);
  const groupHeight = plotHeight / categoryCount;
  const clusterHeight = groupHeight * 0.72;
  const barHeight = clusterHeight / seriesCount;
  const bars = seriesData.flatMap((series, seriesIndex) => numericValues(series.values).map((value, categoryIndex) => {
    const valueX = x(value);
    const y = plotTop + categoryIndex * groupHeight + (groupHeight - clusterHeight) / 2 + seriesIndex * barHeight;
    return `<rect data-series="${escapeSvgText(series.name)}" data-category-index="${categoryIndex}" x="${Math.min(valueX, baseline)}" y="${y}" width="${Math.max(0, Math.abs(baseline - valueX))}" height="${Math.max(1, barHeight - 2)}" fill="${SERIES_COLORS[seriesIndex % SERIES_COLORS.length]}"/>`;
  })).join("");
  const labels = categoryData.map((category, index) => `<text x="${plotLeft - 5}" y="${plotTop + (index + 0.5) * groupHeight + 4}" text-anchor="end">${escapeSvgText(category)}</text>`).join("");
  return `<svg class="surfgym-bar-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeSvgText(title || "Bar chart")}"><line x1="${baseline}" y1="${plotTop}" x2="${baseline}" y2="${height - 12}" stroke="#64748b"/><text x="${width / 2}" y="14" text-anchor="middle">${escapeSvgText(title)}</text>${bars}${labels}</svg>`;
}

export function renderChartSvg(input: ChartRenderInput) {
  const safeInput = { ...input, width: Math.max(80, input.width), height: Math.max(60, input.height) };
  if (input.chartType === "column") return renderColumnChart(safeInput);
  if (input.chartType === "bar") return renderBarChart(safeInput);
  return renderLineChart(safeInput);
}

export function renderLineChartSvg(input: LineChartRenderInput) {
  return renderChartSvg({ ...input, chartType: "line" });
}
