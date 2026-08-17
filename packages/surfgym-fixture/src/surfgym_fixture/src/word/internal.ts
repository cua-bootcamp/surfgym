import {
  IUniverInstanceService,
  SectionType,
  UniverInstanceType
} from "@univerjs/core";
import {
  DocRenderController,
  DocSkeletonManagerService,
  IRenderManagerService
} from "@univerjs/preset-docs-core";
import type { Path, Value } from "../external";

export type AnyRecord = Record<string, any>;

type WordRuntime = {
  univer: AnyRecord;
  univerAPI: AnyRecord;
  document?: AnyRecord;
};

type TextRange = {
  start: number;
  end: number;
};

type TextTarget = Value;

type TableSpec = {
  rows: number;
  columns: number;
  cells: string[];
  tableId: string;
};

type BuiltTablesBody = {
  dataStream: string;
  paragraphs: AnyRecord[];
  sectionBreaks: AnyRecord[];
  tables: AnyRecord[];
};

export class WordRuntimeStore {
  private static _runtime: WordRuntime | null = null;

  static set runtime(runtime: WordRuntime) {
    WordRuntimeStore._runtime = runtime;
  }

  static get runtime(): WordRuntime {
    if (!WordRuntimeStore._runtime) {
      throw new Error("Word runtime is not installed.");
    }

    return WordRuntimeStore._runtime;
  }
}

const TABLE_START = "\x1A";
const TABLE_ROW_START = "\x1B";
const TABLE_CELL_START = "\x1C";
const TABLE_CELL_END = "\x1D";
const TABLE_ROW_END = "\x0E";
const TABLE_END = "\x0F";
const TABLE_TAGS = [
  TABLE_START,
  TABLE_ROW_START,
  TABLE_CELL_START,
  TABLE_CELL_END,
  TABLE_ROW_END,
  TABLE_END
];

const getDocumentModel = (): AnyRecord | null => {
  const runtime = WordRuntimeStore.runtime;
  const injector = runtime.univer.__getInjector?.();
  const instanceService = injector?.get?.(IUniverInstanceService);

  return (
    asDocumentModel(runtime.document?.doc) ??
    asDocumentModel(runtime.document) ??
    asDocumentModel(
      instanceService?.getCurrentUnitOfType?.(UniverInstanceType.UNIVER_DOC)
    ) ??
    asDocumentModel(instanceService?.getCurrentUniverDocInstance?.()) ??
    null
  );
};

const asDocumentModel = (candidate: unknown): AnyRecord | null => {
  if (!isRecordValue(candidate)) return null;
  if (typeof candidate.getSnapshot !== "function") return null;
  if (typeof candidate.reset !== "function") return null;

  return candidate;
};

const resolveBody = (): AnyRecord => getDocumentModel()?.getSnapshot?.()?.body ?? {};

const getBodyDataStream = (): string => String(resolveBody().dataStream ?? "\r\n");

export function _getBodyMeta() {
  return {
    rawText: getBodyDataStream(),
    text: getBodyText(),
    textWithPageBreak: getBodyText(true)
  };
}

export function _setBodyMeta(path: Path[], value: Value): AnyRecord {
  if (path.length !== 1 || (path[0] !== "text" && path[0] !== "textWithPageBreak")) {
    throw new Error(`Unsupported word body path: ${path.map(String).join(".")}`);
  }

  const snapshot = getMutableSnapshot();
  const text = value == null ? "" : String(value);
  const hasPageBreak = path[0] === "textWithPageBreak";
  const dataStream = textToDataStream(text, hasPageBreak);

  snapshot.body = {
    ...(isRecordValue(snapshot.body) ? snapshot.body : {}),
    dataStream,
    textRuns: [],
    customBlocks: [],
    tables: [],
    paragraphs: buildParagraphs(dataStream),
    sectionBreaks: hasPageBreak
      ? buildPageBreakSectionBreaks(dataStream)
      : buildSectionBreaks(dataStream)
  };
  snapshot.tableSource = {};

  resetDocument(snapshot);
  return _getBodyMeta();
}

export function _getTextMeta(target: TextTarget): AnyRecord {
  const targetInfo = normalizeTextTarget(target);
  const body = resolveBody();
  const dataStream = String(body.dataStream ?? "");
  const range = findTargetRange(dataStream, targetInfo);
  if (!range) return buildTextMeta({});

  const textRuns = (body.textRuns ?? []) as AnyRecord[];
  return buildTextMeta(getUniformTextStyle(dataStream, textRuns, range));
}

export function _setTextMeta(target: TextTarget, path: Path[], value: Value): AnyRecord {
  const targetInfo = normalizeTextTarget(target);
  const snapshot = getMutableSnapshot();
  const body = ensureBody(snapshot);
  const dataStream = String(body.dataStream ?? "");
  const range = findTargetRange(dataStream, targetInfo);
  if (!range) throw new Error(`Text target not found: ${targetInfo.value}`);

  const textStyle = styleForTextPath(path, value);
  mergeTextStyle(body, dataStream, range.start, range.end + 1, textStyle);

  resetDocument(snapshot);
  return _getTextMeta(target);
}

function mergeTextStyle(
  body: AnyRecord,
  dataStream: string,
  start: number,
  end: number,
  textStyle: AnyRecord
) {
  const textRuns = Array.isArray(body.textRuns)
    ? body.textRuns.filter((run): run is AnyRecord => isRecordValue(run))
    : [];
  const maxIndex = dataStream.length;
  const clampIndex = (value: unknown, fallback: number): number =>
    Math.max(0, Math.min(maxIndex, safeInteger(value, fallback)));
  const rangeStart = clampIndex(start, 0);
  const rangeEnd = clampIndex(end, rangeStart);
  if (rangeStart >= rangeEnd) return;

  const boundaries = new Set<number>([rangeStart, rangeEnd]);
  textRuns.forEach((run) => {
    const runStart = clampIndex(run.st, 0);
    const runEnd = clampIndex(run.ed, runStart);
    if (runStart >= runEnd) return;

    boundaries.add(runStart);
    boundaries.add(runEnd);
  });

  const sortedBoundaries = Array.from(boundaries).sort((left, right) => left - right);
  const mergedTextRuns: AnyRecord[] = [];

  for (let index = 0; index < sortedBoundaries.length - 1; index += 1) {
    const segmentStart = sortedBoundaries[index];
    const segmentEnd = sortedBoundaries[index + 1];
    if (segmentStart === undefined || segmentEnd === undefined || segmentStart >= segmentEnd) {
      continue;
    }

    const currentStyle = styleRunForIndex(textRuns, segmentStart);
    const segmentStyle =
      segmentStart < rangeEnd && rangeStart < segmentEnd
        ? mergeStyle(currentStyle, textStyle)
        : currentStyle;
    if (Object.keys(segmentStyle).length === 0) continue;

    const styleId = textRuns.reduce<unknown>((currentStyleId, run) => {
      const runStart = clampIndex(run.st, 0);
      const runEnd = clampIndex(run.ed, runStart);
      if (runStart <= segmentStart && segmentStart < runEnd && run.sId !== undefined) {
        return clone(run.sId);
      }

      return currentStyleId;
    }, undefined);
    const segment: AnyRecord = {
      st: segmentStart,
      ed: segmentEnd,
      ts: segmentStyle
    };
    if (styleId !== undefined) segment.sId = styleId;

    const previous = mergedTextRuns.at(-1);
    if (
      previous &&
      Number(previous.ed) === segmentStart &&
      styleValuesEqual(previous.ts, segment.ts) &&
      styleValuesEqual(previous.sId, segment.sId)
    ) {
      previous.ed = segmentEnd;
    } else {
      mergedTextRuns.push(segment);
    }
  }

  body.textRuns = mergedTextRuns;
}

export function _getParagraphMeta(index: number): AnyRecord {
  const body = resolveBody();
  const dataStream = String(body.dataStream ?? "");
  const paragraph = getParagraphAt(body, index, dataStream);
  const style = (paragraph?.paragraphStyle ?? {}) as AnyRecord;

  return {
    text: paragraph ? getParagraphText(dataStream, paragraph, index) : "",
    lineSpacing: readNumber(style.lineSpacing, 1),
    horizontalAlign: horizontalAlignToString(style.horizontalAlign),
    border: paragraphBorderToString(style),
    namedStyleType: namedStyleTypeToString(style.namedStyleType)
  };
}

export function _setParagraphMeta(index: number, path: Path[], value: Value): AnyRecord {
  const snapshot = getMutableSnapshot();
  const body = ensureBody(snapshot);
  const dataStream = String(body.dataStream ?? "\r\n");
  body.paragraphs = normalizeParagraphs(body, dataStream);

  const paragraph = body.paragraphs[index];
  if (!paragraph) throw new Error(`Paragraph index not found: ${index}`);

  const paragraphStyle = isRecordValue(paragraph.paragraphStyle)
    ? paragraph.paragraphStyle
    : {};

  if (path.length !== 1) {
    throw new Error(`Unsupported paragraph path: ${path.map(String).join(".")}`);
  }

  const [key] = path;
  if (key === "lineSpacing") {
    paragraphStyle.lineSpacing = normalizeLineSpacing(value);
  } else if (key === "horizontalAlign") {
    paragraphStyle.horizontalAlign = normalizeHorizontalAlign(value);
  } else if (key === "border") {
    applyParagraphBorder(paragraphStyle, value);
  } else if (key === "namedStyleType") {
    paragraphStyle.namedStyleType = normalizeNamedStyleType(value);
  } else {
    throw new Error(`Unsupported paragraph path: ${String(key)}`);
  }

  paragraph.paragraphStyle = paragraphStyle;
  resetDocument(snapshot);
  return _getParagraphMeta(index);
}

export function _getTableMeta(index: number): AnyRecord {
  const snapshot = getReadableSnapshot();
  const table = readTableSpecs(snapshot)[index];
  if (!table) {
    return {
      shape: "",
      cellsText: ""
    };
  }

  return {
    shape: `${table.rows}x${table.columns}`,
    cellsText: table.cells.join("|")
  };
}

export function _setTableMeta(index: number, path: Path[], value: Value): AnyRecord {
  if (path.length !== 1) {
    throw new Error(`Unsupported table path: ${path.map(String).join(".")}`);
  }

  const snapshot = getMutableSnapshot();
  const specs = readTableSpecs(snapshot);
  while (specs.length <= index) specs.push(createTableSpec(1, 1, [], tableIdForIndex(specs.length)));

  const [key] = path;
  const current = specs[index] as TableSpec;
  if (key === "shape") {
    const { rows, columns } = normalizeTableShape(value);
    specs[index] = createTableSpec(rows, columns, current.cells, current.tableId);
  } else if (key === "cellsText") {
    specs[index] = createTableSpec(
      current.rows,
      current.columns,
      normalizeTableCells(value, current.rows, current.columns),
      current.tableId
    );
  } else {
    throw new Error(`Unsupported table path: ${String(key)}`);
  }

  writeTableSpecs(snapshot, specs);
  resetDocument(snapshot);
  return _getTableMeta(index);
}

export function _getFooterMeta(): AnyRecord {
  return {
    text: getFooterText(getReadableSnapshot())
  };
}

export function _setFooterMeta(path: Path[], value: Value): AnyRecord {
  if (path.length !== 1 || path[0] !== "text") {
    throw new Error(`Unsupported footer path: ${path.map(String).join(".")}`);
  }

  const snapshot = getMutableSnapshot();
  const footerId = getDefaultFooterId(snapshot) || "surfgym-footer-default";
  const text = value == null ? "" : String(value);

  if (!isRecordValue(snapshot.footers)) snapshot.footers = {};
  if (!isRecordValue(snapshot.documentStyle)) snapshot.documentStyle = {};

  snapshot.documentStyle.defaultFooterId = footerId;
  snapshot.footers[footerId] = {
    footerId,
    body: createTextBody(text)
  };

  resetDocument(snapshot);
  return _getFooterMeta();
}

export function _getDocumentMeta(): AnyRecord {
  return {
    style: {
      fontSizeOnly: readUniformBodyFontSize()
    },
    defaultFontFamily: readDocumentDefaultFont()
  };
}

export function _setDocumentMeta(path: Path[], value: Value): AnyRecord {
  const snapshot = getMutableSnapshot();

  if (path.length === 1 && path[0] === "defaultFontFamily") {
    const fontFamily = normalizeDefaultFontFamily(value);
    const documentStyle = isRecordValue(snapshot.documentStyle) ? snapshot.documentStyle : {};
    const textStyle = isRecordValue(documentStyle.textStyle) ? documentStyle.textStyle : {};

    snapshot.documentStyle = {
      ...documentStyle,
      textStyle: {
        ...textStyle,
        ff: fontFamily
      }
    };
    resetDocument(snapshot);
    return _getDocumentMeta();
  }

  if (path.length === 2 && path[0] === "style" && path[1] === "fontSizeOnly") {
    const body = ensureBody(snapshot);
    const dataStream = String(body.dataStream ?? "\r\n");
    mergeTextStyle(body, dataStream, 0, dataStream.length, {
      fs: normalizeNumber(value, "fontSizeOnly")
    });

    resetDocument(snapshot);
    return _getDocumentMeta();
  }

  throw new Error(`Unsupported document path: ${path.map(String).join(".")}`);
}

const normalizeTargetForDataStream = (target: string): string => target.replaceAll("\n", "\r");

const splitOccurrenceTarget = (target: string): { value: string; occurrence: number } => {
  const match = /^(.*)#(\d+)$/.exec(target);
  if (!match) return { value: target, occurrence: 0 };

  return {
    value: match[1] ?? target,
    occurrence: Number(match[2] ?? 0)
  };
};

const findTargetRange = (
  dataStream: string,
  target: { value: string; occurrence: number }
): TextRange | null => {
  const { value, occurrence } = target;
  const needle = normalizeTargetForDataStream(value);
  if (!needle) return null;

  let fromIndex = 0;
  for (let currentOccurrence = 0; currentOccurrence <= occurrence; currentOccurrence += 1) {
    const start = dataStream.indexOf(needle, fromIndex);
    if (start < 0) return null;
    if (currentOccurrence === occurrence) return { start, end: start + needle.length - 1 };

    fromIndex = start + needle.length;
  }

  return null;
};

const isRecordValue = (value: unknown): value is AnyRecord =>
  value !== null && typeof value === "object" && !Array.isArray(value);

const clone = <T>(value: T): T => {
  if (value === undefined || value === null || typeof value !== "object") return value;

  return JSON.parse(JSON.stringify(value)) as T;
};

const mergeStyle = (base: AnyRecord, override: AnyRecord): AnyRecord => {
  const merged = clone(base);

  Object.entries(override).forEach(([key, value]) => {
    const previousValue = merged[key];
    merged[key] =
      isRecordValue(previousValue) && isRecordValue(value)
        ? mergeStyle(previousValue, value)
        : clone(value);
  });

  return merged;
};

const styleRunForIndex = (textRuns: AnyRecord[], index: number): AnyRecord => {
  return textRuns.reduce<AnyRecord>((style, candidate) => {
    const start = Number(candidate.st ?? -1);
    const end = Number(candidate.ed ?? -1);
    if (start <= index && index < end) return mergeStyle(style, candidate.ts ?? {});

    return style;
  }, {});
};

const shouldSkipTextStyleChar = (char: string): boolean =>
  char === "\r" || char === "\n" || char === "\f" || TABLE_TAGS.includes(char);

const styleValuesEqual = (left: unknown, right: unknown): boolean =>
  JSON.stringify(left) === JSON.stringify(right);

const intersectStyle = (left: AnyRecord, right: AnyRecord): AnyRecord => {
  const result: AnyRecord = {};

  Object.entries(left).forEach(([key, value]) => {
    const rightValue = right[key];

    if (isRecordValue(value) && isRecordValue(rightValue)) {
      const childResult = intersectStyle(value, rightValue);
      if (Object.keys(childResult).length > 0) result[key] = childResult;
      return;
    }

    if (styleValuesEqual(value, rightValue)) result[key] = clone(value);
  });

  return result;
};

const getUniformTextStyle = (
  dataStream: string,
  textRuns: AnyRecord[],
  range: TextRange
): AnyRecord => {
  let commonStyle: AnyRecord | null = null;

  for (let index = range.start; index <= range.end; index += 1) {
    const char = dataStream[index] ?? "";
    if (shouldSkipTextStyleChar(char)) continue;

    const style = styleRunForIndex(textRuns, index);
    commonStyle = commonStyle === null ? clone(style) : intersectStyle(commonStyle, style);
  }

  return commonStyle ?? {};
};

function getMutableSnapshot(): AnyRecord {
  const documentModel = getDocumentModel();
  const snapshot = documentModel?.getSnapshot?.();
  if (!isRecordValue(snapshot)) throw new Error("Word document snapshot is unavailable.");

  return clone(snapshot);
}

function getReadableSnapshot(): AnyRecord {
  const snapshot = getDocumentModel()?.getSnapshot?.();
  return isRecordValue(snapshot) ? snapshot : {};
}

function resetDocument(snapshot: AnyRecord) {
  const documentModel = getDocumentModel();
  if (typeof documentModel?.reset !== "function") {
    throw new Error("Word document reset API is unavailable.");
  }

  documentModel.reset(snapshot);
  refreshDocumentRender(documentModel);
}

function refreshDocumentRender(documentModel: AnyRecord) {
  const unitId = getDocumentUnitId(documentModel);
  if (!unitId) return;
  if (refreshDocumentRenderNow(documentModel, unitId)) return;

  queueDocumentRenderRefresh(documentModel, unitId);
}

function queueDocumentRenderRefresh(documentModel: AnyRecord, unitId: string, attempts = 5) {
  if (attempts <= 0) return;

  const browserGlobal = globalThis as AnyRecord;
  const retry = () => {
    if (!refreshDocumentRenderNow(documentModel, unitId)) {
      queueDocumentRenderRefresh(documentModel, unitId, attempts - 1);
    }
  };
  if (typeof browserGlobal.requestAnimationFrame === "function") {
    browserGlobal.requestAnimationFrame(retry);
  } else {
    browserGlobal.setTimeout?.(retry, 0);
  }
}

function refreshDocumentRenderNow(documentModel: AnyRecord, unitId: string): boolean {
  const runtime = WordRuntimeStore.runtime;
  const injector = runtime.univer.__getInjector?.();
  const renderManagerService = injector?.get?.(IRenderManagerService) as AnyRecord | undefined;
  const render = renderManagerService?.getRenderById?.(unitId);
  if (!isRecordValue(render)) return false;

  const skeletonManager = render.with?.(DocSkeletonManagerService) as AnyRecord | undefined;
  const viewModel = skeletonManager?.getViewModel?.();
  if (typeof viewModel?.reset !== "function") return false;
  viewModel.reset(documentModel);

  const renderController = render.with?.(DocRenderController) as AnyRecord | undefined;
  if (typeof renderController?.reRender !== "function") return false;
  renderController.reRender(unitId);

  return true;
}

function getDocumentUnitId(documentModel: AnyRecord): string | null {
  const unitId = documentModel.getUnitId?.() ?? documentModel.getId?.();
  return typeof unitId === "string" && unitId.length > 0 ? unitId : null;
}

function ensureBody(snapshot: AnyRecord): AnyRecord {
  if (!isRecordValue(snapshot.body)) snapshot.body = {};

  const body = snapshot.body as AnyRecord;
  if (typeof body.dataStream !== "string") body.dataStream = "\r\n";
  if (!Array.isArray(body.textRuns)) body.textRuns = [];
  body.paragraphs = normalizeParagraphs(body, body.dataStream);

  return body;
}

function createTextBody(text: string): AnyRecord {
  const dataStream = textToDataStream(text);
  return {
    dataStream,
    textRuns: [],
    customBlocks: [],
    tables: [],
    paragraphs: buildParagraphs(dataStream),
    sectionBreaks: buildSectionBreaks(dataStream)
  };
}

function textToDataStream(text: string, convertPageBreaks = false): string {
  let normalized = text.replaceAll("\r\n", "\n").replaceAll("\r", "\n").replaceAll("\n", "\r");
  if (convertPageBreaks) normalized = normalized.replaceAll("\f", "\n");

  return `${normalized}\r\n`;
}

function getBodyText(includePageBreaks = false): string {
  const stripped = stripTableContent(getBodyDataStream());
  let dataStream = stripped.dataStream;
  while (dataStream.endsWith("\r\n")) dataStream = dataStream.slice(0, -2);
  if (stripped.removedTable && dataStream.endsWith("\r")) {
    dataStream = dataStream.slice(0, -1);
  }

  return Array.from(dataStream, (char) => {
    if (char === "\r") return "\n";
    if (char === "\n") return includePageBreaks ? "\f" : "\n";
    return char;
  }).join("");
}

function stripTableContent(dataStream: string): { dataStream: string; removedTable: boolean } {
  let tableDepth = 0;
  let removedTable = false;
  let text = "";

  for (let index = 0; index < dataStream.length; index += 1) {
    const char = dataStream[index] ?? "";
    if (char === TABLE_START) {
      tableDepth += 1;
      removedTable = true;
      continue;
    }

    if (char === TABLE_END && tableDepth > 0) {
      tableDepth -= 1;
      if (tableDepth === 0 && dataStream[index + 1] === "\r") {
        index += 1;
        if (dataStream[index + 1] === "\n") index += 1;
      }
      continue;
    }

    if (tableDepth === 0) text += char;
  }

  return { dataStream: text, removedTable };
}

function buildParagraphs(dataStream: string): AnyRecord[] {
  const paragraphs: AnyRecord[] = [];
  for (let index = 0; index < dataStream.length; index += 1) {
    if (dataStream[index] === "\r") paragraphs.push({ startIndex: index });
  }

  return paragraphs;
}

function buildSectionBreaks(dataStream: string): AnyRecord[] {
  const sectionBreaks: AnyRecord[] = [];
  for (let index = 0; index < dataStream.length; index += 1) {
    if (dataStream[index] === "\n") sectionBreaks.push({ startIndex: index });
  }

  return sectionBreaks;
}

function buildPageBreakSectionBreaks(dataStream: string): AnyRecord[] {
  return buildSectionBreaks(dataStream).map((sectionBreak, index) =>
    index === 0
      ? sectionBreak
      : { ...sectionBreak, sectionType: SectionType.NEXT_PAGE }
  );
}

function getFooterText(snapshot: AnyRecord): string {
  const footerId = getDefaultFooterId(snapshot);
  const footers = isRecordValue(snapshot.footers) ? snapshot.footers : {};
  const footer = footerId && isRecordValue(footers[footerId]) ? footers[footerId] : firstRecordValue(footers);
  const body = isRecordValue(footer?.body) ? footer.body : {};
  return bodyDataStreamToText(String(body.dataStream ?? "\r\n"));
}

function getDefaultFooterId(snapshot: AnyRecord): string {
  const documentStyle = isRecordValue(snapshot.documentStyle) ? snapshot.documentStyle : {};
  return typeof documentStyle.defaultFooterId === "string" ? documentStyle.defaultFooterId : "";
}

function firstRecordValue(record: AnyRecord): AnyRecord | null {
  for (const value of Object.values(record)) {
    if (isRecordValue(value)) return value;
  }

  return null;
}

function bodyDataStreamToText(dataStreamValue: string): string {
  let dataStream = dataStreamValue;
  if (dataStream.endsWith("\r\n")) dataStream = dataStream.slice(0, -2);

  return dataStream.replaceAll("\r", "\n");
}

function readTableSpecs(snapshot: AnyRecord): TableSpec[] {
  const body = isRecordValue(snapshot.body) ? snapshot.body : {};
  const dataStream = String(body.dataStream ?? "");
  const tables = Array.isArray(body.tables)
    ? body.tables.filter((table): table is AnyRecord => isRecordValue(table))
    : [];
  const tableSource = isRecordValue(snapshot.tableSource) ? snapshot.tableSource : {};

  if (tables.length === 0) return readLooseTableSpecs(dataStream);

  return tables
    .slice()
    .sort((left, right) => Number(left.startIndex ?? 0) - Number(right.startIndex ?? 0))
    .map((table, index) => {
      const tableId = typeof table.tableId === "string" ? table.tableId : tableIdForIndex(index);
      const source = isRecordValue(tableSource[tableId]) ? tableSource[tableId] : {};
      const startIndex = safeInteger(table.startIndex, 0);
      const endIndex = safeInteger(table.endIndex, dataStream.length);
      const parsed = parseTableDataStream(dataStream.slice(startIndex, endIndex));
      const rows = readTableSourceRows(source) || parsed.rows || 1;
      const columns = readTableSourceColumns(source) || parsed.columns || 1;

      return createTableSpec(rows, columns, parsed.cells, tableId);
    });
}

function readLooseTableSpecs(dataStream: string): TableSpec[] {
  const specs: TableSpec[] = [];
  let searchIndex = 0;

  while (searchIndex < dataStream.length) {
    const startIndex = dataStream.indexOf(TABLE_START, searchIndex);
    if (startIndex < 0) break;

    const endIndex = dataStream.indexOf(TABLE_END, startIndex + 1);
    if (endIndex < 0) break;

    const parsed = parseTableDataStream(dataStream.slice(startIndex, endIndex + 1));
    specs.push(
      createTableSpec(parsed.rows || 1, parsed.columns || 1, parsed.cells, tableIdForIndex(specs.length))
    );
    searchIndex = endIndex + 1;
  }

  return specs;
}

function writeTableSpecs(snapshot: AnyRecord, specs: TableSpec[]) {
  const builtBody = buildTablesBody(specs);
  const previousBody = isRecordValue(snapshot.body) ? snapshot.body : {};
  const prefix = preserveBodyPrefix(previousBody);
  const tableOffset = prefix.dataStream.length;
  const dataStream = `${prefix.dataStream}${builtBody.dataStream}`;
  const builtSectionBreaks = offsetStartIndices(builtBody.sectionBreaks, tableOffset);
  const builtTables = offsetStartIndices(builtBody.tables, tableOffset);
  const lastBuiltSectionBreak = builtSectionBreaks.at(-1);

  if (lastBuiltSectionBreak && prefix.trailingSectionBreak) {
    const { startIndex: _previousStartIndex, ...trailingConfig } = prefix.trailingSectionBreak;
    Object.assign(lastBuiltSectionBreak, clone(trailingConfig));
  }

  snapshot.body = {
    ...previousBody,
    dataStream,
    textRuns: [
      ...prefix.textRuns,
      ...builtTables.map((table, index) => ({
        st: safeInteger(table.startIndex, tableOffset),
        ed: safeInteger(table.endIndex, tableOffset),
        ts: { fs: (specs[index]?.columns ?? 1) <= 5 ? 13.5 : 9 }
      }))
    ],
    customBlocks: prefix.customBlocks,
    tables: builtTables,
    paragraphs: [
      ...prefix.paragraphs,
      ...offsetStartIndices(builtBody.paragraphs, tableOffset)
    ],
    sectionBreaks: [
      ...prefix.sectionBreaks,
      ...builtSectionBreaks
    ]
  };
  snapshot.tableSource = specs.reduce<AnyRecord>((tableSource, spec) => {
    tableSource[spec.tableId] = buildTableSource(spec, getPageContentWidth(snapshot));
    return tableSource;
  }, {});
}

function preserveBodyPrefix(body: AnyRecord): {
  dataStream: string;
  textRuns: AnyRecord[];
  customBlocks: AnyRecord[];
  paragraphs: AnyRecord[];
  sectionBreaks: AnyRecord[];
  trailingSectionBreak: AnyRecord | null;
} {
  const dataStream = String(body.dataStream ?? "\r\n");
  const allSectionBreaks = Array.isArray(body.sectionBreaks)
    ? body.sectionBreaks.filter((record): record is AnyRecord => isRecordValue(record))
    : [];
  const trailingSectionBreak = allSectionBreaks.find(
    (record) => safeInteger(record.startIndex, -1) === dataStream.length - 1
  );
  const tables = Array.isArray(body.tables)
    ? body.tables.filter((table): table is AnyRecord => isRecordValue(table))
    : [];
  const firstTableStart = tables.reduce(
    (start, table) => Math.min(start, safeInteger(table.startIndex, dataStream.length)),
    dataStream.length
  );

  let prefix = dataStream.slice(0, firstTableStart);
  if (tables.length === 0 && prefix === "\r\n") prefix = "";
  else if (tables.length === 0 && prefix.endsWith("\r\n")) prefix = prefix.slice(0, -1);

  const prefixLength = prefix.length;
  const recordsBeforePrefixEnd = (value: unknown): AnyRecord[] =>
    Array.isArray(value)
      ? value
          .filter((record): record is AnyRecord => isRecordValue(record))
          .filter((record) => safeInteger(record.startIndex, prefixLength) < prefixLength)
          .map((record) => clone(record))
      : [];
  const textRuns = Array.isArray(body.textRuns)
    ? body.textRuns
        .filter((run): run is AnyRecord => isRecordValue(run))
        .map((run) => {
          const start = Math.max(0, safeInteger(run.st, 0));
          const end = Math.min(prefixLength, safeInteger(run.ed, start));
          return { ...clone(run), st: start, ed: end };
        })
        .filter((run) => run.st < run.ed)
    : [];

  return {
    dataStream: prefix,
    textRuns,
    customBlocks: recordsBeforePrefixEnd(body.customBlocks),
    paragraphs: recordsBeforePrefixEnd(body.paragraphs),
    sectionBreaks: recordsBeforePrefixEnd(body.sectionBreaks),
    trailingSectionBreak: trailingSectionBreak ? clone(trailingSectionBreak) : null
  };
}

function buildTablesBody(specs: TableSpec[]): BuiltTablesBody {
  if (specs.length === 0) {
    return {
      dataStream: "\r\n",
      paragraphs: buildParagraphs("\r\n"),
      sectionBreaks: [{ startIndex: 1 }],
      tables: []
    };
  }

  let dataStream = "";
  const paragraphs: AnyRecord[] = [];
  const sectionBreaks: AnyRecord[] = [];
  const tables: AnyRecord[] = [];

  specs.forEach((spec, specIndex) => {
    const tableStartIndex = dataStream.length;
    const tableBody = buildSingleTableBody(spec);

    dataStream += tableBody.dataStream;
    paragraphs.push(...offsetStartIndices(tableBody.paragraphs, tableStartIndex));
    sectionBreaks.push(...offsetStartIndices(tableBody.sectionBreaks, tableStartIndex));
    tables.push({
      startIndex: tableStartIndex,
      endIndex: dataStream.length,
      tableId: spec.tableId
    });

    const isLastTable = specIndex === specs.length - 1;
    dataStream += isLastTable ? "\r\n" : "\r";
    paragraphs.push({ startIndex: dataStream.length - (isLastTable ? 2 : 1) });
    if (isLastTable) sectionBreaks.push({ startIndex: dataStream.length - 1 });
  });

  return {
    dataStream,
    paragraphs,
    sectionBreaks,
    tables
  };
}

function buildSingleTableBody(spec: TableSpec): Pick<BuiltTablesBody, "dataStream" | "paragraphs" | "sectionBreaks"> {
  let dataStream = TABLE_START;
  const paragraphs: AnyRecord[] = [];
  const sectionBreaks: AnyRecord[] = [];

  for (let rowIndex = 0; rowIndex < spec.rows; rowIndex += 1) {
    dataStream += TABLE_ROW_START;
    for (let columnIndex = 0; columnIndex < spec.columns; columnIndex += 1) {
      const cellIndex = rowIndex * spec.columns + columnIndex;
      const cellText = normalizeCellTextForDataStream(spec.cells[cellIndex] ?? "");
      dataStream += `${TABLE_CELL_START}${cellText}\r\n${TABLE_CELL_END}`;
      paragraphs.push({
        startIndex: dataStream.length - 3,
        paragraphStyle: {
          spaceAbove: { v: 0 },
          lineSpacing: 1,
          spaceBelow: { v: 0 }
        }
      });
      sectionBreaks.push({ startIndex: dataStream.length - 2 });
    }
    dataStream += TABLE_ROW_END;
  }

  dataStream += TABLE_END;
  return {
    dataStream,
    paragraphs,
    sectionBreaks
  };
}

function buildTableSource(spec: TableSpec, pageContentWidth: number): AnyRecord {
  const columnWidth = pageContentWidth / spec.columns;
  const tableCell = {
    margin: tableCellMargin(),
    size: tableSize(1, columnWidth)
  };
  const tableRow = {
    tableCells: Array.from({ length: spec.columns }, () => clone(tableCell)),
    trHeight: {
      val: { v: spec.columns <= 5 ? 30 : 22 },
      hRule: 0
    }
  };

  return {
    tableRows: Array.from({ length: spec.rows }, () => clone(tableRow)),
    tableColumns: Array.from({ length: spec.columns }, () => ({
      size: tableSize(1, columnWidth)
    })),
    tableId: spec.tableId,
    align: 0,
    indent: { v: 0 },
    textWrap: 0,
    position: {
      positionH: {
        relativeFrom: 0,
        posOffset: 0
      },
      positionV: {
        relativeFrom: 0,
        posOffset: 0
      }
    },
    dist: {
      distB: 0,
      distL: 0,
      distR: 0,
      distT: 0
    },
    cellMargin: tableCellMargin(),
    size: tableSize(0, pageContentWidth)
  };
}

function parseTableDataStream(tableStream: string): { rows: number; columns: number; cells: string[] } {
  const rows: string[][] = [];
  let currentRow: string[] | null = null;
  let currentCell: string | null = null;

  for (const char of tableStream) {
    if (char === TABLE_ROW_START) {
      currentRow = [];
      continue;
    }

    if (char === TABLE_CELL_START) {
      currentCell = "";
      continue;
    }

    if (char === TABLE_CELL_END) {
      if (currentRow && currentCell !== null) currentRow.push(readCellTextFromDataStream(currentCell));
      currentCell = null;
      continue;
    }

    if (char === TABLE_ROW_END) {
      if (currentRow) rows.push(currentRow);
      currentRow = null;
      continue;
    }

    if (currentCell !== null) currentCell += char;
  }

  if (currentRow && currentRow.length > 0) rows.push(currentRow);

  const rowCount = rows.length;
  const columnCount = rows.reduce((maxColumnCount, row) => Math.max(maxColumnCount, row.length), 0);
  const cells: string[] = [];
  for (let rowIndex = 0; rowIndex < rowCount; rowIndex += 1) {
    for (let columnIndex = 0; columnIndex < columnCount; columnIndex += 1) {
      cells.push(rows[rowIndex]?.[columnIndex] ?? "");
    }
  }

  return {
    rows: rowCount,
    columns: columnCount,
    cells
  };
}

function createTableSpec(rows: number, columns: number, cells: string[], tableId: string): TableSpec {
  const safeRows = positiveInteger(rows, "table rows");
  const safeColumns = positiveInteger(columns, "table columns");
  const cellCount = safeRows * safeColumns;

  return {
    rows: safeRows,
    columns: safeColumns,
    tableId,
    cells: Array.from({ length: cellCount }, (_, index) => cells[index] ?? "")
  };
}

function normalizeTableShape(value: Value): { rows: number; columns: number } {
  if (Array.isArray(value) && value.length >= 2) {
    return {
      rows: positiveInteger(Number(value[0]), "table rows"),
      columns: positiveInteger(Number(value[1]), "table columns")
    };
  }

  if (isRecordValue(value)) {
    const shapeValue = value as Record<string, Value>;
    return {
      rows: positiveInteger(Number(shapeValue.rows), "table rows"),
      columns: positiveInteger(Number(shapeValue.columns), "table columns")
    };
  }

  const match = /^(\d+)\s*x\s*(\d+)$/i.exec(String(value ?? "").trim().replace("×", "x"));
  if (!match) throw new Error(`Invalid table shape: ${String(value)}`);

  return {
    rows: positiveInteger(Number(match[1]), "table rows"),
    columns: positiveInteger(Number(match[2]), "table columns")
  };
}

function normalizeTableCells(value: Value, rows: number, columns: number): string[] {
  const rawCells = Array.isArray(value)
    ? value.map((cell) => (cell == null ? "" : String(cell)))
    : String(value ?? "").split("|");
  return createTableSpec(rows, columns, rawCells, "unused").cells;
}

function readTableSourceRows(source: AnyRecord): number {
  return Array.isArray(source.tableRows) ? source.tableRows.length : 0;
}

function readTableSourceColumns(source: AnyRecord): number {
  return Array.isArray(source.tableColumns) ? source.tableColumns.length : 0;
}

function offsetStartIndices(records: AnyRecord[], offset: number): AnyRecord[] {
  return records.map((record) => {
    const shifted: AnyRecord = {
      ...clone(record),
      startIndex: Number(record.startIndex ?? 0) + offset
    };

    if (record.endIndex !== undefined) {
      shifted.endIndex = Number(record.endIndex ?? 0) + offset;
    }

    return shifted;
  });
}

function normalizeCellTextForDataStream(text: string): string {
  return text.replaceAll("\r\n", "\n").replaceAll("\r", "\n").replaceAll("\n", "\r");
}

function readCellTextFromDataStream(text: string): string {
  let normalized = text;
  if (normalized.endsWith("\r\n")) normalized = normalized.slice(0, -2);
  else if (normalized.endsWith("\r")) normalized = normalized.slice(0, -1);

  return normalized.replaceAll("\r", "\n");
}

function tableCellMargin(): AnyRecord {
  return {
    start: { v: 10 },
    end: { v: 10 },
    top: { v: 5 },
    bottom: { v: 5 }
  };
}

function tableSize(type: number, width: number): AnyRecord {
  return {
    type,
    width: { v: width }
  };
}

function getPageContentWidth(snapshot: AnyRecord): number {
  const documentStyle = isRecordValue(snapshot.documentStyle) ? snapshot.documentStyle : {};
  const pageSize = isRecordValue(documentStyle.pageSize) ? documentStyle.pageSize : {};
  const pageWidth = readNumber(pageSize.width, 595 / 0.75);
  const marginLeft = readNumber(documentStyle.marginLeft, 50);
  const marginRight = readNumber(documentStyle.marginRight, 50);

  return Math.max(120, pageWidth - marginLeft - marginRight);
}

function tableIdForIndex(index: number): string {
  return `surfgym-table-${index}`;
}

function safeInteger(value: unknown, fallback: number): number {
  const numberValue = Number(value);
  return Number.isInteger(numberValue) ? numberValue : fallback;
}

function positiveInteger(value: number, label: string): number {
  if (!Number.isInteger(value) || value <= 0) throw new Error(`Invalid ${label}: ${String(value)}`);

  return value;
}

function paragraphBorderToString(style: AnyRecord): string | null {
  return hasParagraphBoxBorder(style) ? "box" : null;
}

function hasParagraphBoxBorder(style: AnyRecord): boolean {
  return (
    isRecordValue(style.borderTop) &&
    isRecordValue(style.borderBottom) &&
    isRecordValue(style.borderLeft) &&
    isRecordValue(style.borderRight)
  );
}

function applyParagraphBorder(paragraphStyle: AnyRecord, value: Value) {
  if (value === null || value === false || value === "" || value === "none") {
    delete paragraphStyle.borderTop;
    delete paragraphStyle.borderBottom;
    delete paragraphStyle.borderLeft;
    delete paragraphStyle.borderRight;
    return;
  }

  if (String(value).toLowerCase() !== "box") {
    throw new Error(`Unsupported paragraph border: ${String(value)}`);
  }

  const border = {
    color: { rgb: "#000000" },
    width: 1,
    dashStyle: 1,
    padding: 2
  };
  paragraphStyle.borderTop = clone(border);
  paragraphStyle.borderBottom = clone(border);
  paragraphStyle.borderLeft = clone(border);
  paragraphStyle.borderRight = clone(border);
}

function normalizeNamedStyleType(value: Value): number {
  if (typeof value === "number") return value;

  switch (String(value).toLowerCase().replaceAll(/[\s_-]/g, "")) {
    case "normal":
    case "normaltext":
      return 1;
    case "title":
      return 2;
    case "subtitle":
      return 3;
    case "heading1":
      return 4;
    case "heading2":
      return 5;
    case "heading3":
      return 6;
    case "heading4":
      return 7;
    case "heading5":
      return 8;
    default:
      throw new Error(`Unsupported namedStyleType: ${String(value)}`);
  }
}

function namedStyleTypeToString(value: unknown): string | null {
  switch (value) {
    case 1:
      return "normalText";
    case 2:
      return "title";
    case 3:
      return "subtitle";
    case 4:
      return "heading1";
    case 5:
      return "heading2";
    case 6:
      return "heading3";
    case 7:
      return "heading4";
    case 8:
      return "heading5";
    default:
      return null;
  }
}

function readUniformBodyFontSize(): number | null {
  const body = resolveBody();
  const dataStream = String(body.dataStream ?? "");
  const textRuns = Array.isArray(body.textRuns) ? (body.textRuns as AnyRecord[]) : [];
  let fontSize: number | null = null;

  for (let index = 0; index < dataStream.length; index += 1) {
    const char = dataStream[index] ?? "";
    if (shouldSkipTextStyleChar(char)) continue;

    const style = styleRunForIndex(textRuns, index);
    if (typeof style.fs !== "number" || !Number.isFinite(style.fs)) return null;
    if (fontSize === null) fontSize = style.fs;
    else if (fontSize !== style.fs) return null;
  }

  return fontSize;
}

function normalizeParagraphs(body: AnyRecord, dataStream: string): AnyRecord[] {
  if (!Array.isArray(body.paragraphs) || body.paragraphs.length === 0) {
    return buildParagraphs(dataStream);
  }

  return body.paragraphs
    .filter((paragraph): paragraph is AnyRecord => isRecordValue(paragraph))
    .sort((left, right) => Number(left.startIndex ?? 0) - Number(right.startIndex ?? 0));
}

function getParagraphAt(body: AnyRecord, index: number, dataStream: string): AnyRecord | null {
  const paragraphs = normalizeParagraphs(body, dataStream);
  return paragraphs[index] ?? null;
}

function getParagraphText(dataStream: string, paragraph: AnyRecord, index: number): string {
  const paragraphs = normalizeParagraphs({ paragraphs: resolveBody().paragraphs }, dataStream);
  const previousEnd = index > 0 ? Number(paragraphs[index - 1]?.startIndex ?? -1) : -1;
  const start = previousEnd + 1;
  const end = Number(paragraph.startIndex ?? start);

  return dataStream.slice(start, end).replaceAll("\r", "\n");
}

function normalizeTextTarget(target: TextTarget): { value: string; occurrence: number } {
  if (isRecordValue(target)) {
    const targetRecord = target as AnyRecord;
    const value = targetRecord.value == null ? "" : String(targetRecord.value);
    const occurrence =
      typeof targetRecord.occurrence === "number" && Number.isInteger(targetRecord.occurrence)
        ? targetRecord.occurrence
        : 0;

    return { value, occurrence: Math.max(0, occurrence) };
  }

  return splitOccurrenceTarget(String(target ?? ""));
}

function buildTextMeta(style: AnyRecord): AnyRecord {
  return {
    bold: style.bl === 1,
    italic: style.it === 1,
    underline: isRecordValue(style.ul) ? style.ul.s === 1 : false,
    strikethrough: isRecordValue(style.st) ? style.st.s === 1 : false,
    fontFamily: typeof style.ff === "string" ? style.ff : readDocumentDefaultFont(),
    fontSize: readNumber(style.fs, null),
    color: readColor(style.cl),
    backgroundColor: readBackgroundColor(style.bg),
    verticalAlign: verticalAlignToString(style.va)
  };
}

function readDocumentDefaultFont(): string | undefined {
  const snapshot = getReadableSnapshot();
  const documentStyle = isRecordValue(snapshot.documentStyle) ? snapshot.documentStyle : {};
  const textStyle = isRecordValue(documentStyle.textStyle) ? documentStyle.textStyle : {};
  const fontFamily = textStyle.ff;

  return typeof fontFamily === "string" && fontFamily.trim() !== "" ? fontFamily : undefined;
}

function normalizeDefaultFontFamily(value: Value): string {
  if (typeof value !== "string" || value.trim() === "") {
    throw new Error(`Invalid defaultFontFamily: ${String(value)}`);
  }

  return value.trim();
}

function styleForTextPath(path: Path[], value: Value): AnyRecord {
  if (path.length !== 1) {
    throw new Error(`Unsupported text style path: ${path.map(String).join(".")}`);
  }

  const [key] = path;
  if (key === "bold") return { bl: booleanNumber(value) };
  if (key === "italic") return { it: booleanNumber(value) };
  if (key === "underline") return { ul: { s: booleanNumber(value) } };
  if (key === "strikethrough") return { st: { s: booleanNumber(value) } };
  if (key === "fontFamily") return { ff: value == null ? null : String(value) };
  if (key === "fontSize") return { fs: normalizeNumber(value, "fontSize") };
  if (key === "color") return { cl: colorValue(value) };
  if (key === "backgroundColor") return { bg: backgroundColorValue(value) };
  if (key === "verticalAlign") return { va: normalizeVerticalAlign(value) };

  throw new Error(`Unsupported text style path: ${String(key)}`);
}

function booleanNumber(value: Value): 0 | 1 {
  if (value === true || value === 1 || value === "true") return 1;
  if (value === false || value === 0 || value === "false") return 0;

  throw new Error(`Expected boolean style value, got: ${String(value)}`);
}

function normalizeNumber(value: Value, label: string): number {
  const numberValue = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(numberValue)) throw new Error(`Invalid ${label}: ${String(value)}`);

  return numberValue;
}

function normalizeLineSpacing(value: Value): number {
  return normalizeNumber(value, "lineSpacing");
}

function colorValue(value: Value): { rgb: string } | null {
  if (value === null) return null;
  if (typeof value !== "string" || value.trim() === "") {
    throw new Error(`Expected color string, got: ${String(value)}`);
  }

  return { rgb: value };
}

function backgroundColorValue(value: Value): { rgb: string } | null {
  if (typeof value === "string" && value.trim().toLowerCase() === "none") return null;

  return colorValue(value);
}

function readColor(value: unknown): string | null {
  return isRecordValue(value) && typeof value.rgb === "string" ? value.rgb : null;
}

function readBackgroundColor(value: unknown): string {
  return readColor(value) ?? "none";
}

function readNumber(value: unknown, fallback: number): number;
function readNumber(value: unknown, fallback: null): number | null;
function readNumber(value: unknown, fallback: number | null): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function normalizeHorizontalAlign(value: Value): number {
  if (typeof value === "number") return value;

  switch (String(value).toLowerCase()) {
    case "left":
      return 1;
    case "center":
      return 2;
    case "right":
      return 3;
    case "justify":
    case "justified":
      return 4;
    case "both":
      return 5;
    case "distributed":
      return 6;
    default:
      throw new Error(`Unsupported horizontalAlign: ${String(value)}`);
  }
}

function horizontalAlignToString(value: unknown): string {
  switch (value) {
    case 2:
      return "center";
    case 3:
      return "right";
    case 4:
    case 5:
      return "justify";
    case 6:
      return "distributed";
    case 1:
    default:
      return "left";
  }
}

function normalizeVerticalAlign(value: Value): number {
  if (typeof value === "number") return value;

  switch (String(value).toLowerCase()) {
    case "normal":
      return 1;
    case "subscript":
      return 2;
    case "superscript":
      return 3;
    default:
      throw new Error(`Unsupported verticalAlign: ${String(value)}`);
  }
}

function verticalAlignToString(value: unknown): string {
  switch (value) {
    case 2:
      return "subscript";
    case 3:
      return "superscript";
    case 1:
      return "normal";
    default:
      return "normal";
  }
}
