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

export type ChartSourceReference = {
  sourceSheet: string;
  sourceRanges: string[];
  sourceRange: string;
  canonicalRange: string;
};

type ParseChartSourceOptions = {
  defaultSheet?: string;
};

type ChartSourceWorksheet = {
  getRange: (rangeA1: string) => {
    getValues?: () => unknown[][];
  };
};

const A1_CELL = String.raw`\$?[A-Za-z]{1,3}\$?[1-9][0-9]*`;
const A1_COLUMN = String.raw`\$?[A-Za-z]{1,3}`;
const A1_ROW = String.raw`\$?[1-9][0-9]*`;
const A1_RANGE = new RegExp(
  `^(?:${A1_CELL}(?::${A1_CELL})?|${A1_COLUMN}:${A1_COLUMN}|${A1_ROW}:${A1_ROW})$`,
);

function parseQuotedSheet(segment: string) {
  let sourceSheet = "";

  for (let index = 1; index < segment.length; index += 1) {
    if (segment[index] !== "'") {
      sourceSheet += segment[index];
      continue;
    }

    if (segment[index + 1] === "'") {
      sourceSheet += "'";
      index += 1;
      continue;
    }

    const suffix = segment.slice(index + 1).trimStart();
    if (!suffix.startsWith("!")) {
      throw new ChartSourceRangeError("Quoted chart source sheet must be followed by !.");
    }
    return { sourceSheet, sourceRange: suffix.slice(1).trim() };
  }

  throw new ChartSourceRangeError("Chart source range contains an unterminated quoted sheet name.");
}

function parseChartSourceSegment(segment: string, defaultSheet?: string) {
  if (segment.startsWith("'")) return parseQuotedSheet(segment);

  const separator = segment.indexOf("!");
  if (separator < 0) {
    if (!defaultSheet?.trim()) {
      throw new ChartSourceRangeError("Chart source range must be sheet-qualified.");
    }
    return { sourceSheet: defaultSheet.trim(), sourceRange: segment.trim() };
  }

  return {
    sourceSheet: segment.slice(0, separator).trim(),
    sourceRange: segment.slice(separator + 1).trim(),
  };
}

export function formatChartSheetName(sourceSheet: string) {
  const sheet = sourceSheet.trim();
  if (!sheet) throw new ChartSourceRangeError("Chart source sheet must not be empty.");
  return /^[A-Za-z_][A-Za-z0-9_.]*$/.test(sheet)
    ? sheet
    : `'${sheet.replaceAll("'", "''")}'`;
}

export function formatQualifiedChartSourceRange(sourceSheet: string, sourceRange: string) {
  const formattedSheet = formatChartSheetName(sourceSheet);
  return splitChartSourceRanges(sourceRange)
    .map((range) => `${formattedSheet}!${range.trim()}`)
    .join(",");
}

export function parseChartSourceRange(
  sourceRange: string,
  { defaultSheet }: ParseChartSourceOptions = {},
): ChartSourceReference {
  if (typeof sourceRange !== "string" || !sourceRange.trim()) {
    throw new ChartSourceRangeError("Chart source range must be a non-empty A1 range.");
  }

  const parsed = splitChartSourceRanges(sourceRange).map((segment) =>
    parseChartSourceSegment(segment, defaultSheet)
  );
  const sourceSheet = parsed[0]!.sourceSheet.trim();
  if (!sourceSheet) throw new ChartSourceRangeError("Chart source sheet must not be empty.");
  if (parsed.some((part) => part.sourceSheet.trim().toLocaleLowerCase() !== sourceSheet.toLocaleLowerCase())) {
    throw new ChartSourceRangeError("A chart must use exactly one source sheet.");
  }

  const sourceRanges = parsed.map(({ sourceRange: range }) => {
    if (!A1_RANGE.test(range)) {
      throw new ChartSourceRangeError(`Invalid chart source A1 range: ${range || "(empty)"}.`);
    }
    return range;
  });
  const physicalRange = sourceRanges.join(",");

  return {
    sourceSheet,
    sourceRanges,
    sourceRange: physicalRange,
    canonicalRange: formatQualifiedChartSourceRange(sourceSheet, physicalRange),
  };
}

function readChartCellValue(value: unknown): unknown {
  if (!value || typeof value !== "object") return value;
  const cellData = value as { v?: unknown; p?: unknown; f?: unknown };
  if (cellData.v !== undefined) return cellData.v;
  if (cellData.p !== undefined) return cellData.p;
  if (cellData.f !== undefined) return cellData.f;
  return value;
}

export function readChartSourceRangeValues(worksheet: ChartSourceWorksheet, rangeA1: string) {
  const values = worksheet.getRange(rangeA1).getValues?.();
  if (!Array.isArray(values)) {
    throw new ChartSourceRangeError(`Unable to read chart source range: ${rangeA1}.`);
  }
  return values.map((row) => row.map(readChartCellValue));
}

export function resolveAndReadChartSource(
  sourceRange: string,
  getWorksheet: (sourceSheet: string) => ChartSourceWorksheet | null | undefined,
  options: ParseChartSourceOptions = {},
) {
  const reference = parseChartSourceRange(sourceRange, options);
  const worksheet = getWorksheet(reference.sourceSheet);
  if (!worksheet) {
    throw new ChartSourceRangeError(`Chart source sheet was not found: ${reference.sourceSheet}.`);
  }
  const sourceInfo = mergeChartSourceMatrixInfo(
    reference.sourceRanges.map((range) => readChartSourceRangeValues(worksheet, range)),
  );
  return { ...reference, ...sourceInfo, worksheet };
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
