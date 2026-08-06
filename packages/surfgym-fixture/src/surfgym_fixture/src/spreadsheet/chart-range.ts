export class ChartSourceRangeError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ChartSourceRangeError";
  }
}

type LogicalChartSourceRange = {
  logicalRangeA1: string;
  physicalRangeA1: string;
};

const logicalChartSourceRanges = new Map<string, LogicalChartSourceRange>();

function normalizeRangeA1(rangeA1: string) {
  return rangeA1.trim();
}

export function registerLogicalChartSourceRange(
  chartId: string,
  logicalRangeA1: string,
  physicalRangeA1: string
) {
  const logical = normalizeRangeA1(logicalRangeA1);
  const physical = normalizeRangeA1(physicalRangeA1);

  if (logical === physical) {
    logicalChartSourceRanges.delete(chartId);
    return;
  }

  logicalChartSourceRanges.set(chartId, {
    logicalRangeA1: logical,
    physicalRangeA1: physical
  });
}

export function getLogicalChartSourceRange(chartId: string, physicalRangeA1: string | null) {
  const registered = logicalChartSourceRanges.get(chartId);
  if (!registered || physicalRangeA1 === null) return null;

  if (registered.physicalRangeA1 !== normalizeRangeA1(physicalRangeA1)) {
    logicalChartSourceRanges.delete(chartId);
    return null;
  }

  return registered.logicalRangeA1;
}

export function clearLogicalChartSourceRanges() {
  logicalChartSourceRanges.clear();
}

export function splitChartSourceRanges(sourceRange: string) {
  const ranges: string[] = [];
  let segmentStart = 0;
  let inQuotedSheetName = false;
  let bracketDepth = 0;

  const pushSegment = (segmentEnd: number) => {
    const segment = sourceRange.slice(segmentStart, segmentEnd).trim();
    if (!segment) throw new ChartSourceRangeError("Chart source range contains an empty segment.");
    ranges.push(segment);
  };

  for (let index = 0; index < sourceRange.length; index += 1) {
    const character = sourceRange[index];

    if (character === "'") {
      if (inQuotedSheetName && sourceRange[index + 1] === "'") {
        index += 1;
        continue;
      }

      inQuotedSheetName = !inQuotedSheetName;
      continue;
    }

    if (inQuotedSheetName) continue;

    if (character === "[") {
      bracketDepth += 1;
      continue;
    }

    if (character === "]") {
      if (bracketDepth === 0) {
        throw new ChartSourceRangeError("Chart source range contains an unmatched ].");
      }
      bracketDepth -= 1;
      continue;
    }

    if (character === "," && bracketDepth === 0) {
      pushSegment(index);
      segmentStart = index + 1;
    }
  }

  if (inQuotedSheetName) {
    throw new ChartSourceRangeError(
      "Chart source range contains an unterminated quoted sheet name."
    );
  }
  if (bracketDepth !== 0) {
    throw new ChartSourceRangeError("Chart source range contains an unmatched [.");
  }

  pushSegment(sourceRange.length);
  return ranges;
}

type MatrixShape = {
  rows: number;
  columns: number;
};

function getMatrixShape(matrix: unknown[][], index: number): MatrixShape {
  const rows = matrix.length;
  const columns = matrix[0]?.length ?? 0;

  if (rows === 0 || columns === 0) {
    throw new ChartSourceRangeError(`Chart source range ${index + 1} is empty.`);
  }

  if (matrix.some((row) => row.length !== columns)) {
    throw new ChartSourceRangeError(`Chart source range ${index + 1} is not rectangular.`);
  }

  return { rows, columns };
}

export function mergeChartSourceMatrixInfo(matrices: unknown[][][]) {
  if (matrices.length === 0) {
    throw new ChartSourceRangeError("Chart source range is empty.");
  }

  if (matrices.length === 1) {
    const matrix = matrices[0]!.map((row) => [...row]);
    const shape = getMatrixShape(matrix, 0);

    return { isRowDirection: shape.rows >= shape.columns, matrix };
  }

  const shapes = matrices.map(getMatrixShape);
  const allSingleColumns = shapes.every(({ columns }) => columns === 1);
  const sameColumnCount = shapes.every(({ columns }) => columns === shapes[0]!.columns);
  const sameRowCount = shapes.every(({ rows }) => rows === shapes[0]!.rows);

  if (!allSingleColumns && sameColumnCount) {
    const matrix = matrices.flatMap((matrix) => matrix.map((row) => [...row]));
    getMatrixShape(matrix, 0);

    return {
      isRowDirection: false,
      matrix
    };
  }

  if (sameRowCount) {
    const matrix = Array.from({ length: shapes[0]!.rows }, (_, rowIndex) =>
      matrices.flatMap((matrix) => matrix[rowIndex] ?? [])
    );
    getMatrixShape(matrix, 0);

    return {
      isRowDirection: true,
      matrix
    };
  }

  throw new ChartSourceRangeError(
    "Chart source ranges must have matching widths or matching heights."
  );
}

export function mergeChartSourceMatrices(matrices: unknown[][][]) {
  return mergeChartSourceMatrixInfo(matrices).matrix;
}
