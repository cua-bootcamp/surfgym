import {
  _getSheetMeta,
  _getCellMeta,
  _getChartMeta,
  _setSheetMeta,
  _setCellMeta,
  _setChartMeta,
  type SheetRef,
  type ChartRef
} from "./internal";
import { getFactory, setFactory, SET, type Path, type Value } from "../external";

const external = {
  sheet
};

export const set = setFactory(external);
export const get = getFactory(external);

export function sheet(sheetRef?: SheetRef) {
  const getMeta = () => _getSheetMeta(sheetRef);

  return {
    get id() {
      return getMeta().id;
    },
    get name() {
      return getMeta().name;
    },
    get index() {
      return getMeta().index;
    },
    getMeta,
    cell: (cellRefStr: string) => cell(sheetRef, cellRefStr),
    chart: (chartRef?: ChartRef) => chart(sheetRef, chartRef),
    [SET]: (path: Path[], value: Value) => _setSheetMeta(sheetRef, path, value)
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
    get id() {
      return getMeta().id;
    },
    get sheetId() {
      return getMeta().sheetId;
    },
    get sheetName() {
      return getMeta().sheetName;
    },
    get index() {
      return getMeta().index;
    },
    get chartType() {
      return getMeta().chartType;
    },
    get sourceRange() {
      return getMeta().sourceRange;
    },
    get range() {
      return getMeta().range;
    },
    get title() {
      return getMeta().title;
    },
    get xAxisTitle() {
      return getMeta().xAxisTitle;
    },
    get yAxisTitle() {
      return getMeta().yAxisTitle;
    },
    get legendPosition() {
      return getMeta().legendPosition;
    },
    get dataOrientation() {
      return getMeta().dataOrientation;
    },
    get width() {
      return getMeta().width;
    },
    get height() {
      return getMeta().height;
    },
    get position() {
      return getMeta().position;
    },
    get context() {
      return getMeta().context;
    },
    get seriesData() {
      return getMeta().seriesData;
    },
    get categoryData() {
      return getMeta().categoryData;
    },
    getMeta,
    [SET]: (path: Path[], value: Value) => _setChartMeta(sheetRef, chartRef, path, value)
  };
}
