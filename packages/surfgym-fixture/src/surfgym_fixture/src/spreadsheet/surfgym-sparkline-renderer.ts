export function renderLineSparklineSvg(values: unknown[]) {
  const numbers = values.map((value) => typeof value === "number" && Number.isFinite(value) ? value : 0);
  const max = Math.max(1, ...numbers);
  const min = Math.min(0, ...numbers);
  const range = Math.max(1, max - min);
  const points = numbers.map((value, index) => {
    const x = numbers.length <= 1 ? 1 : 1 + index * (98 / (numbers.length - 1));
    const y = 19 - ((value - min) / range) * 18;
    return `${x},${y}`;
  }).join(" ");
  return `<svg class="surfgym-line-sparkline" viewBox="0 0 100 20" role="img" aria-label="Line sparkline"><polyline fill="none" stroke="#2563eb" stroke-width="1.5" points="${points}"/></svg>`;
}
