import {
  type ChartRef,
  type SheetRef,
  type SurfgymGetPayload,
  type SurfgymSetPayload,
  type QueryStep,
  type PathPart,
  type JsonValue,
  SET,
  isSettable
} from "./type";
import { isRecord } from "./type";
import { _getCellMeta, _getChartMeta, _setCellMeta } from "./internal";

function runQuery(query: QueryStep[]) {
  let current: unknown = {
    sheet
  };

  for (const [name, param] of query) {
    if (!isRecord(current)) throw new Error(`Cannot call ${name} on non-object query result.`);
    const next = current[name];

    if (typeof next !== "function") throw new Error(`Unsupported surfgym query step: ${name}`);
    current = param === null ? next() : next(param);
  }

  return current;
}

export function set(payload: SurfgymSetPayload) {
  const { query, path, value } = payload;
  let current = runQuery(query);

  if (!isSettable(current)) throw new Error("Query result is not settable.");

  return current[SET](path, value);
}

export function get(payload: SurfgymGetPayload) {
  const { query, path } = payload;

  let current = runQuery(query);
  for (const key of path) {
    if (!isRecord(current)) throw new Error(`Wrong path with ${key} on non-object query result.`);
    current = current[key];
  }

  return current;
}

function sheet(sheetRef: SheetRef) {
  return {
    cell: (cellRefStr: string) => cell(sheetRef, cellRefStr),
    chart: (chartRef?: ChartRef) => chart(sheetRef, chartRef)
  };
}

function cell(sheetRef: SheetRef, cellRefStr: string) {
  return {
    ..._getCellMeta(sheetRef, cellRefStr),
    [SET]: (path: PathPart[], value: JsonValue) => _setCellMeta(sheetRef, cellRefStr, path, value)
  };
}

function chart(sheetRef: SheetRef, chartRef?: ChartRef) {
  const getMeta = () => _getChartMeta(sheetRef, chartRef);

  return {
    getMeta
    // getType: () => getMeta().chartType,
    // // getSourceRange: () => getMeta().sourceRange,
    // getTitle: () => getMeta().title,
    // getLegendPosition: () => getMeta().legendPosition,
    // getDataOrientation: () => getMeta().dataOrientation,
    // getSeriesData: () => getMeta().seriesData,
    // getCategoryData: () => getMeta().categoryData
  };
}
