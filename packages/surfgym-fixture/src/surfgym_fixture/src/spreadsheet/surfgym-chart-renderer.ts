type LineChartRenderInput = {
  categoryData: unknown[];
  seriesData: Array<{ name: string; values: unknown[] }>;
  title: string;
  width: number;
  height: number;
};

function escapeSvgText(value: unknown) {
  return String(value).replace(/[&<>\"]/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[character]!);
}

function numericValues(values: unknown[]) {
  return values.map((value) => typeof value === "number" && Number.isFinite(value) ? value : 0);
}

export function renderLineChartSvg({ categoryData, seriesData, title, width, height }: LineChartRenderInput) {
  const safeWidth = Math.max(80, width);
  const safeHeight = Math.max(60, height);
  const allValues = seriesData.flatMap((series) => numericValues(series.values));
  const max = Math.max(1, ...allValues);
  const min = Math.min(0, ...allValues);
  const verticalRange = Math.max(1, max - min);
  const x = (index: number, total: number) => 32 + (total <= 1 ? 0 : index * ((safeWidth - 44) / (total - 1)));
  const y = (value: number) => 20 + (safeHeight - 42) * (1 - ((value - min) / verticalRange));
  const paths = seriesData.map((series, seriesIndex) => {
    const values = numericValues(series.values);
    const points = values.map((value, index) => `${x(index, values.length)},${y(value)}`).join(" ");
    const color = seriesIndex % 2 ? "#dc2626" : "#2563eb";
    const marker = values.length === 1
      ? `<circle data-series-marker="${escapeSvgText(series.name)}" cx="${x(0, values.length)}" cy="${y(values[0]!)}" r="3" fill="${color}"/>`
      : "";
    return `<polyline data-series="${escapeSvgText(series.name)}" fill="none" stroke="${color}" stroke-width="2" points="${points}"/>${marker}`;
  }).join("");
  const labels = categoryData.map((category, index) => `<text x="${x(index, categoryData.length)}" y="${safeHeight - 6}" text-anchor="middle">${escapeSvgText(category)}</text>`).join("");

  return `<svg class="surfgym-line-chart" viewBox="0 0 ${safeWidth} ${safeHeight}" role="img" aria-label="${escapeSvgText(title || "Line chart")}"><line x1="32" y1="20" x2="32" y2="${safeHeight - 22}" stroke="#64748b"/><line x1="32" y1="${safeHeight - 22}" x2="${safeWidth - 12}" y2="${safeHeight - 22}" stroke="#64748b"/><text x="${safeWidth / 2}" y="14" text-anchor="middle">${escapeSvgText(title)}</text>${paths}${labels}</svg>`;
}
