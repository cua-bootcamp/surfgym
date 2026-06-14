import type { ChartRef, SheetRef } from "./type";
import { _getCellMeta, _getChartMeta } from "./_get";

export function sheet(sheetRef: SheetRef) {
  return {
    cell: (cellRefStr: string) => cell(sheetRef, cellRefStr),
    chart
  };
}

function cell(sheetRef: SheetRef, cellRefStr: string) {
  const getMeta = () => _getCellMeta(sheetRef, cellRefStr);

  return {
    getValue: () => getMeta().cell,
    getStyle: () => getMeta().style
  };
}

function chart(sheetRef: SheetRef, chartRef?: ChartRef) {
  const getMeta = () => _getChartMeta(sheetRef, chartRef);

  return {
    getMeta,
    getType: () => getMeta().chartType,
    // getSourceRange: () => getMeta().sourceRange,
    getTitle: () => getMeta().title,
    getLegendPosition: () => getMeta().legendPosition,
    getDataOrientation: () => getMeta().dataOrientation,
    getSeriesData: () => getMeta().seriesData,
    getCategoryData: () => getMeta().categoryData
  };
}
