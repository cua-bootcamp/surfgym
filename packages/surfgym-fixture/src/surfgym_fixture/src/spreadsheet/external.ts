import { type ChartRef, type SheetRef } from "./type";
import { _getSheetMeta, _getCellMeta, _getChartMeta, _setCellMeta } from "./internal";
import { getFactory, setFactory, SET, type Path, type Value } from "../external";

const external = {
  sheet
};

export const set = setFactory(external);
export const get = getFactory(external);

export function sheet(sheetRef?: SheetRef) {
  return {
    ..._getSheetMeta(sheetRef),
    getMeta: () => _getSheetMeta(sheetRef),
    cell: (cellRefStr: string) => cell(sheetRef, cellRefStr),
    chart: (chartRef?: ChartRef) => chart(sheetRef, chartRef)
  };
}

export function cell(sheetRef: SheetRef | undefined, cellRefStr: string) {
  return {
    ..._getCellMeta(sheetRef, cellRefStr),
    [SET]: (path: Path[], value: Value) => _setCellMeta(sheetRef, cellRefStr, path, value)
  };
}

export function chart(sheetRef?: SheetRef, chartRef?: ChartRef) {
  const getMeta = () => _getChartMeta(sheetRef, chartRef);

  return {
    ...getMeta(),
    getMeta
    // [SET]: (path: PathPart[], value: JsonValue) => _setCellMeta(sheetRef, cellRefStr, path, value)
  };
}
