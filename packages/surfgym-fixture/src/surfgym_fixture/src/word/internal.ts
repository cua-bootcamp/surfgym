import { IUniverInstanceService, UniverInstanceType } from "@univerjs/presets";

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
  if (runtime.document) return runtime.document;

  const injector = runtime.univer.__getInjector?.();
  const instanceService = injector?.get?.(IUniverInstanceService);

  return instanceService?.getCurrentUnitOfType?.(UniverInstanceType.UNIVER_DOC) ?? null;
};

const resolveBody = (): AnyRecord => getDocumentModel()?.getSnapshot?.()?.body ?? {};

const getBodyDataStream = (): string => String(resolveBody().dataStream ?? "\r\n");

export function _getBodyMeta() {
  return {
    rawText: getBodyDataStream
  };
}

export function _getTextMeta(target: string): AnyRecord {
  const body = resolveBody();
  const dataStream = String(body.dataStream ?? "");
  const range = findTargetRange(dataStream, target);
  if (!range) return {};

  const textRuns = (body.textRuns ?? []) as AnyRecord[];
  return getUniformTextStyle(dataStream, textRuns, range);
}

const normalizeTargetForDataStream = (target: string): string => target.replaceAll("\n", "\r");

const splitOccurrenceTarget = (target: string): { text: string; occurrence: number } => {
  const match = /^(.*)#(\d+)$/.exec(target);
  if (!match) return { text: target, occurrence: 0 };

  return {
    text: match[1] ?? target,
    occurrence: Number(match[2] ?? 0)
  };
};

const findTargetRange = (dataStream: string, target: string): TextRange | null => {
  const { text, occurrence } = splitOccurrenceTarget(target);
  const needle = normalizeTargetForDataStream(text);
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
