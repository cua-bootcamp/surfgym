import { describe, expect, it } from "vitest";
import { renderLineChartSvg } from "./surfgym-chart-renderer";
import { renderLineSparklineSvg } from "./surfgym-sparkline-renderer";

describe("independent line renderers", () => {
  it("renders a line chart from canonical series data without a chart runtime", () => {
    const svg = renderLineChartSvg({
      categoryData: ["Jan", "Feb", "Mar"],
      seriesData: [{ name: "Total", values: [12, 18, 25] }],
      title: "Monthly total",
      width: 480,
      height: 320,
    });

    expect(svg).toContain("<svg");
    expect(svg).toContain("<polyline");
    expect(svg).toContain("Monthly total");
  });

  it("renders a visible marker for a one-point Column series", () => {
    const svg = renderLineChartSvg({
      categoryData: ["Pallets"],
      seriesData: [{ name: "08:00", values: [20] }],
      title: "Dispatch volume",
      width: 480,
      height: 320,
    });

    expect(svg).toContain('data-series-marker="08:00"');
    expect(svg).toContain("<circle");
  });

  it("renders a line sparkline from its source values", () => {
    const svg = renderLineSparklineSvg([20, 30, 50]);
    expect(svg).toContain("<svg");
    expect(svg).toContain("<polyline");
  });
});
