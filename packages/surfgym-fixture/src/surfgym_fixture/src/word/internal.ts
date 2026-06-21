// import {
//   BaselineOffset,
//   BooleanNumber,
//   HorizontalAlign,
//   IUniverInstanceService,
//   NamedStyleType,
//   TableAlignmentType,
//   TableRowHeightRule,
//   TableSizeType,
//   TableTextWrapType,
//   TextDecoration,
//   UniverInstanceType
// } from "@univerjs/presets";
// import { DocSkeletonManagerService, IRenderManagerService } from "@univerjs/preset-docs-core";
// import { type Value } from "../external";
// import { WordRuntimeStore } from "./runtime";

// function resolveBody() {
//   return WordRuntimeStore.runtime.document.getSnapshot().body;
// }

// export function _getBodyMeta() {
//   const rawText = (): string => String(resolveBody()?.dataStream ?? "\r\n");

//   return {
//     rawText
//   };
// }

// export function _getTextMeta(target: string) {}

// const getTextStylePropertyValue = (target: string, property: string): string => {
//   const body = resolveBody();
//   const dataStream = String(body.dataStream ?? "");
//   const range = findTargetRange(dataStream, target);
//   if (!range) return "";

//   const textRuns = (body.textRuns ?? []) as AnyRecord[];
//   const positiveProperty = property.endsWith("Not") ? property.slice(0, -3) : property;
//   let firstValue: string | null = null;

//   for (let index = range.start; index <= range.end; index += 1) {
//     const char = dataStream[index] ?? "";
//     if (char === "\r" || char === "\n" || TABLE_TAGS.includes(char)) continue;

//     const actualValue = getTextStyleProperty(styleRunForIndex(textRuns, index), positiveProperty);
//     if (firstValue === null) {
//       firstValue = actualValue;
//     } else if (firstValue !== actualValue) {
//       return "";
//     }
//   }

//   return firstValue ?? "";
// };

// type WordAtomValue = string | number | boolean;

// type WordStateAtom = {
//   f: string;
//   property?: string[];
//   value?: WordAtomValue;
// };

// type AnyRecord = Record<string, any>;

// type WordMetaEntry = AnyRecord & {
//   address?: string;
//   f?: string;
// };

// const TABLE_START = "\x1A";
// const TABLE_ROW_START = "\x1B";
// const TABLE_CELL_START = "\x1C";
// const TABLE_CELL_END = "\x1D";
// const TABLE_ROW_END = "\x0E";
// const TABLE_END = "\x0F";
// const TABLE_TAGS = [
//   TABLE_START,
//   TABLE_ROW_START,
//   TABLE_CELL_START,
//   TABLE_CELL_END,
//   TABLE_ROW_END,
//   TABLE_END
// ];

// const truthyValues = new Set<WordAtomValue>(["true", true, 1]);

// const valueToString = (value: WordAtomValue | undefined): string =>
//   value === undefined ? "" : String(value);

// const toWordAtomValue = (value: Value): WordAtomValue => {
//   if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
//     return value;
//   }

//   throw new Error("Word state values must be a string, number, or boolean.");
// };

// const clone = <T>(value: T): T => JSON.parse(JSON.stringify(value)) as T;

// const getDocumentModel = (): AnyRecord | null => {
//   const injector = WordRuntimeStore.runtime.univer.__getInjector();
//   const instanceService = injector.get(IUniverInstanceService);
//   return instanceService.getCurrentUnitOfType(UniverInstanceType.UNIVER_DOC) as AnyRecord | null;
// };

// const localPlainText = (dataStream: string): string => {
//   const withoutFinalBreak = dataStream.endsWith("\r\n") ? dataStream.slice(0, -2) : dataStream;

//   return TABLE_TAGS.reduce((text, tag) => text.replaceAll(tag, ""), withoutFinalBreak);
// };

// const getSnapshot = (): AnyRecord | null => getDocumentModel()?.getSnapshot() ?? null;

// const makeDocumentBody = (text: string, textRuns: AnyRecord[] = []): AnyRecord => {
//   const dataStream = `${text.replaceAll("\n", "\r")}\r\n`;
//   const paragraphs: AnyRecord[] = [];

//   for (let index = 0; index < dataStream.length - 1; index += 1) {
//     if (dataStream[index] === "\r") {
//       paragraphs.push({
//         startIndex: index,
//         paragraphStyle: {
//           lineSpacing: 1
//         }
//       });
//     }
//   }

//   return {
//     dataStream,
//     textRuns,
//     customBlocks: [],
//     tables: [],
//     paragraphs,
//     sectionBreaks: [{ startIndex: Math.max(0, dataStream.length - 1) }]
//   };
// };

// const normalizeTargetForDataStream = (target: string): string => target.replaceAll("\n", "\r");

// const splitOccurrenceTarget = (target: string): { text: string; occurrence: number } => {
//   const match = /^(.*)#(\d+)$/.exec(target);
//   if (!match) return { text: target, occurrence: 0 };

//   return {
//     text: match[1] ?? target,
//     occurrence: Number(match[2] ?? 0)
//   };
// };

// const findTargetRange = (
//   dataStream: string,
//   targetValue: WordAtomValue | undefined
// ): { start: number; end: number } | null => {
//   const { text, occurrence } = splitOccurrenceTarget(valueToString(targetValue));
//   const needle = normalizeTargetForDataStream(text);
//   if (!needle) return null;

//   let fromIndex = 0;
//   for (let currentOccurrence = 0; currentOccurrence <= occurrence; currentOccurrence += 1) {
//     const start = dataStream.indexOf(needle, fromIndex);
//     if (start < 0) return null;
//     if (currentOccurrence === occurrence) {
//       return { start, end: start + needle.length - 1 };
//     }
//     fromIndex = start + needle.length;
//   }

//   return null;
// };

// const styleRunForIndex = (textRuns: AnyRecord[], index: number): AnyRecord => {
//   return textRuns.reduce<AnyRecord>((style, candidate) => {
//     const start = Number(candidate.st ?? -1);
//     const end = Number(candidate.ed ?? -1);
//     if (start <= index && index < end) return { ...style, ...(candidate.ts ?? {}) };

//     return style;
//   }, {});
// };

// const colorNameByValue: Record<string, string> = {
//   "#0000ff": "blue",
//   "#008000": "green",
//   "#00ff00": "green",
//   "#ffa500": "orange",
//   "rgb(0, 0, 255)": "blue",
//   "rgb(0, 128, 0)": "green",
//   "rgb(0, 255, 0)": "green",
//   "rgb(255, 165, 0)": "orange"
// };

// const colorValueByName: Record<string, string> = {
//   blue: "#0000ff",
//   green: "#008000",
//   orange: "#ffa500"
// };

// const normalizeColorValue = (value: unknown): string => {
//   if (value == null) return "normal";
//   const raw = String(value).trim();
//   if (!raw) return "normal";

//   return colorNameByValue[raw.toLowerCase()] ?? raw;
// };

// const getTextStyleProperty = (style: AnyRecord, property: string): string => {
//   if (property === "bold") return style.bl === BooleanNumber.TRUE ? "true" : "false";
//   if (property === "italic") return style.it === BooleanNumber.TRUE ? "true" : "false";
//   if (property === "underline") return style.ul?.s === BooleanNumber.TRUE ? "true" : "false";
//   if (property === "strikethrough") return style.st?.s === BooleanNumber.TRUE ? "true" : "false";
//   if (property === "fontSize") return style.fs == null ? "" : String(style.fs);
//   if (property === "fontFamily") return valueToString(style.ff);
//   if (property === "color") return normalizeColorValue(style.cl?.rgb);
//   if (property === "backgroundColor") return normalizeColorValue(style.bg?.rgb);
//   if (property === "verticalAlign") {
//     if (style.va === BaselineOffset.SUBSCRIPT) return "subscript";
//     if (style.va === BaselineOffset.SUPERSCRIPT) return "superscript";
//     return "normal";
//   }

//   return "";
// };

// const rangeEvery = (
//   dataStream: string,
//   range: { start: number; end: number },
//   predicate: (index: number) => boolean
// ): boolean => {
//   for (let index = range.start; index <= range.end; index += 1) {
//     const char = dataStream[index] ?? "";
//     if (char === "\r" || char === "\n" || TABLE_TAGS.includes(char)) continue;
//     if (!predicate(index)) return false;
//   }

//   return true;
// };

// const getTextStyleAtom = (target: string, property: string, expectedValue: string): string => {
//   const body = resolveBody();
//   const dataStream = String(body.dataStream ?? "");
//   const range = findTargetRange(dataStream, target);
//   if (!range) return "";

//   const textRuns = (body.textRuns ?? []) as AnyRecord[];
//   const positiveProperty = property.endsWith("Not") ? property.slice(0, -3) : property;

//   if (property === "fontSizeNot" || property.endsWith("Not")) {
//     return rangeEvery(dataStream, range, (index) => {
//       const actual = getTextStyleProperty(styleRunForIndex(textRuns, index), positiveProperty);
//       return actual !== expectedValue;
//     })
//       ? expectedValue
//       : "";
//   }

//   return rangeEvery(dataStream, range, (index) => {
//     const actual = getTextStyleProperty(styleRunForIndex(textRuns, index), property);
//     return actual === expectedValue;
//   })
//     ? expectedValue
//     : "";
// };

// const horizontalAlignByValue: Record<string, number> = {
//   left: HorizontalAlign.LEFT,
//   center: HorizontalAlign.CENTER,
//   right: HorizontalAlign.RIGHT,
//   justify: HorizontalAlign.JUSTIFIED
// };

// const horizontalAlignName = (value: unknown): string => {
//   if (value === HorizontalAlign.CENTER) return "center";
//   if (value === HorizontalAlign.RIGHT) return "right";
//   if (value === HorizontalAlign.JUSTIFIED || value === HorizontalAlign.BOTH) return "justify";
//   return "left";
// };

// const namedStyleByValue: Record<string, number> = {
//   normal: NamedStyleType.NORMAL_TEXT,
//   title: NamedStyleType.TITLE,
//   subtitle: NamedStyleType.SUBTITLE,
//   heading1: NamedStyleType.HEADING_1,
//   heading2: NamedStyleType.HEADING_2,
//   heading3: NamedStyleType.HEADING_3,
//   heading4: NamedStyleType.HEADING_4,
//   heading5: NamedStyleType.HEADING_5
// };

// const namedStyleName = (value: unknown): string => {
//   const entry = Object.entries(namedStyleByValue).find(([, enumValue]) => enumValue === value);
//   return entry?.[0] ?? "";
// };

// const getParagraphProperty = (paragraph: AnyRecord | undefined, property: string): string => {
//   const style = paragraph?.paragraphStyle ?? {};
//   if (property === "horizontalAlign") return horizontalAlignName(style.horizontalAlign);
//   if (property === "lineSpacing") return style.lineSpacing == null ? "" : String(style.lineSpacing);
//   if (property === "namedStyleType") return namedStyleName(style.namedStyleType);
//   if (property === "border") {
//     return style.borderTop && style.borderBottom && style.borderLeft && style.borderRight
//       ? "box"
//       : "";
//   }

//   return "";
// };

// const getParagraphAtom = (
//   paragraphIndex: string,
//   property: string,
//   expectedValue: string
// ): string => {
//   const paragraphs = (resolveBody().paragraphs ?? []) as AnyRecord[];
//   const paragraph = paragraphs[Number(paragraphIndex)];
//   const positiveProperty = property.endsWith("Not") ? property.slice(0, -3) : property;
//   const actualValue = getParagraphProperty(paragraph, positiveProperty);

//   if (property.endsWith("Not")) {
//     return actualValue === expectedValue ? "" : expectedValue;
//   }

//   return actualValue;
// };

// const parseShape = (shape: string): { rows: number; columns: number } => {
//   const [rawRows, rawColumns] = shape.split("x").map((part) => Number(part));
//   const rows = rawRows ?? 1;
//   const columns = rawColumns ?? 1;
//   return {
//     rows: Number.isFinite(rows) && rows > 0 ? rows : 1,
//     columns: Number.isFinite(columns) && columns > 0 ? columns : 1
//   };
// };

// const getFirstTable = (): AnyRecord | null => {
//   const snapshot = getSnapshot();
//   const firstCustomTable = snapshot?.body?.tables?.[0];
//   const tableId = firstCustomTable?.tableId;
//   if (!tableId) return null;

//   return snapshot?.tableSource?.[tableId] ?? null;
// };

// const extractFirstTableCellsText = (): string => {
//   const dataStream = getBodyDataStream();
//   const tableStart = dataStream.indexOf(TABLE_START);
//   const tableEnd = dataStream.indexOf(TABLE_END, tableStart);
//   if (tableStart < 0 || tableEnd < 0) return "";

//   const cells: string[] = [];
//   let index = tableStart + 1;
//   while (index < tableEnd) {
//     if (dataStream[index] !== TABLE_CELL_START) {
//       index += 1;
//       continue;
//     }

//     const cellEnd = dataStream.indexOf(TABLE_CELL_END, index);
//     if (cellEnd < 0 || cellEnd > tableEnd) break;
//     cells.push(localPlainText(dataStream.slice(index + 1, cellEnd)).replaceAll("\r", "\n"));
//     index = cellEnd + 1;
//   }

//   return cells.join("|");
// };

// const getTableAtom = (property: string): string => {
//   const table = getFirstTable();
//   if (!table) return "";

//   if (property === "shape") {
//     const rows = table.tableRows?.length ?? 0;
//     const columns = table.tableColumns?.length ?? table.tableRows?.[0]?.tableCells?.length ?? 0;
//     return `${rows}x${columns}`;
//   }

//   if (property === "cellsText") return extractFirstTableCellsText();

//   return "";
// };

// const getFooterText = (): string => {
//   const snapshot = getSnapshot();
//   const footerId =
//     snapshot?.documentStyle?.defaultFooterId || Object.keys(snapshot?.footers ?? {})[0];
//   const footer = footerId ? snapshot?.footers?.[footerId] : undefined;
//   return localPlainText(String(footer?.body?.dataStream ?? "")).replaceAll("\r", "\n");
// };

// const getDocumentFontSizeOnly = (expectedValue: string): string => {
//   const body = resolveBody();
//   const dataStream = String(body.dataStream ?? "");
//   const textRuns = (body.textRuns ?? []) as AnyRecord[];

//   for (let index = 0; index < dataStream.length; index += 1) {
//     const char = dataStream[index] ?? "";
//     if (char === "\r" || char === "\n" || char === "\f" || TABLE_TAGS.includes(char)) continue;

//     const actual = getTextStyleProperty(styleRunForIndex(textRuns, index), "fontSize");
//     if (actual !== expectedValue) return "";
//   }

//   return expectedValue;
// };

// const getDocumentUniformFontSize = (): string => {
//   const body = resolveBody();
//   const dataStream = String(body.dataStream ?? "");
//   const textRuns = (body.textRuns ?? []) as AnyRecord[];
//   let firstValue: string | null = null;

//   for (let index = 0; index < dataStream.length; index += 1) {
//     const char = dataStream[index] ?? "";
//     if (char === "\r" || char === "\n" || char === "\f" || TABLE_TAGS.includes(char)) continue;

//     const actualValue = getTextStyleProperty(styleRunForIndex(textRuns, index), "fontSize");
//     if (!actualValue) return "";

//     if (firstValue === null) {
//       firstValue = actualValue;
//     } else if (firstValue !== actualValue) {
//       return "";
//     }
//   }

//   return firstValue ?? "";
// };

// const getWordStateAtom = (atom: WordStateAtom): string => {
//   const property = atom.property ?? [];
//   const expectedValue = valueToString(atom.value);

//   if (atom.f === "word-body" && property[0] === "text") return getBodyText();
//   if (atom.f === "word-body" && property[0] === "textWithPageBreak") {
//     return getBodyTextWithPageBreak();
//   }
//   if (atom.f === "word-body" && property[0] === "notContains") {
//     return getBodyTextWithPageBreak().includes(expectedValue) ? "" : expectedValue;
//   }

//   if (atom.f === "word-text-style" && property[0] === "targets") {
//     const target = property[1];
//     const styleProperty = property[2];
//     if (target === undefined || styleProperty === undefined) return "";
//     return getTextStyleAtom(target, styleProperty, expectedValue);
//   }

//   if (atom.f === "word-paragraph" && property[0] === "paragraphs") {
//     const paragraphIndex = property[1];
//     const paragraphProperty = property[2];
//     if (paragraphIndex === undefined || paragraphProperty === undefined) return "";
//     return getParagraphAtom(paragraphIndex, paragraphProperty, expectedValue);
//   }

//   if (atom.f === "word-table" && property[0] === "tables") {
//     const tableProperty = property[2];
//     if (property[1] !== "0" || tableProperty === undefined) return "";
//     return getTableAtom(tableProperty);
//   }

//   if (atom.f === "word-footer" && property[0] === "text") return getFooterText();

//   if (atom.f === "word-document" && property[0] === "style" && property[1] === "fontSizeOnly") {
//     return getDocumentFontSizeOnly(expectedValue);
//   }

//   return "";
// };

// const getWordBodyMeta = (): AnyRecord => ({
//   text: getBodyText(),
//   textWithPageBreak: getBodyTextWithPageBreak()
// });

// const getWordTextStyleMeta = (): AnyRecord => ({
//   targets: new Proxy(
//     {},
//     {
//       get(_targetMap, target) {
//         if (typeof target !== "string" || target === "toJSON") return undefined;

//         return new Proxy(
//           {},
//           {
//             get(_styleMap, property) {
//               if (typeof property !== "string" || property === "toJSON") return undefined;

//               return getTextStylePropertyValue(target, property);
//             }
//           }
//         );
//       }
//     }
//   )
// });

// const getWordParagraphMeta = (): AnyRecord => {
//   const paragraphs = (resolveBody().paragraphs ?? []) as AnyRecord[];

//   return {
//     paragraphs: Object.fromEntries(
//       paragraphs.map((paragraph, index) => [
//         String(index),
//         {
//           horizontalAlign: getParagraphProperty(paragraph, "horizontalAlign"),
//           lineSpacing: getParagraphProperty(paragraph, "lineSpacing"),
//           namedStyleType: getParagraphProperty(paragraph, "namedStyleType"),
//           border: getParagraphProperty(paragraph, "border")
//         }
//       ])
//     )
//   };
// };

// const getWordTableMeta = (): AnyRecord => ({
//   tables: {
//     0: {
//       shape: getTableAtom("shape"),
//       cellsText: getTableAtom("cellsText")
//     }
//   }
// });

// const getWordFooterMeta = (): AnyRecord => ({
//   text: getFooterText()
// });

// const getWordDocumentMeta = (): AnyRecord => ({
//   style: {
//     fontSizeOnly: getDocumentUniformFontSize()
//   }
// });

// const getWordMeta = (target = ""): AnyRecord => {
//   if (target === "word-body") return getWordBodyMeta();
//   if (target === "word-text-style") return getWordTextStyleMeta();
//   if (target === "word-paragraph") return getWordParagraphMeta();
//   if (target === "word-table") return getWordTableMeta();
//   if (target === "word-footer") return getWordFooterMeta();
//   if (target === "word-document") return getWordDocumentMeta();

//   return {
//     ...getWordBodyMeta(),
//     ...getWordTextStyleMeta(),
//     ...getWordParagraphMeta(),
//     ...getWordTableMeta(),
//     footer: getWordFooterMeta(),
//     document: getWordDocumentMeta()
//   };
// };

// const makeDecoration = (): AnyRecord => ({
//   s: BooleanNumber.TRUE,
//   t: TextDecoration.SINGLE
// });

// const applyTextStyleProperty = (style: AnyRecord, property: string, value: string): void => {
//   const isEnabled = truthyValues.has(value);

//   if (property === "bold") style.bl = isEnabled ? BooleanNumber.TRUE : BooleanNumber.FALSE;
//   if (property === "italic") style.it = isEnabled ? BooleanNumber.TRUE : BooleanNumber.FALSE;
//   if (property === "underline")
//     style.ul = isEnabled ? makeDecoration() : { s: BooleanNumber.FALSE };
//   if (property === "strikethrough")
//     style.st = isEnabled ? makeDecoration() : { s: BooleanNumber.FALSE };
//   if (property === "fontSize") style.fs = Number(value);
//   if (property === "fontFamily") style.ff = value;
//   if (property === "color")
//     style.cl = value === "normal" ? null : { rgb: colorValueByName[value] ?? value };
//   if (property === "backgroundColor") {
//     style.bg = value === "normal" ? null : { rgb: colorValueByName[value] ?? value };
//   }
//   if (property === "verticalAlign") {
//     style.va =
//       value === "subscript"
//         ? BaselineOffset.SUBSCRIPT
//         : value === "superscript"
//           ? BaselineOffset.SUPERSCRIPT
//           : BaselineOffset.NORMAL;
//   }
// };

// const applyParagraphProperty = (paragraph: AnyRecord, property: string, value: string): void => {
//   const style = paragraph.paragraphStyle ?? {};
//   paragraph.paragraphStyle = style;

//   if (property === "horizontalAlign") style.horizontalAlign = horizontalAlignByValue[value];
//   if (property === "lineSpacing") style.lineSpacing = Number(value);
//   if (property === "namedStyleType") style.namedStyleType = namedStyleByValue[value];
//   if (property === "border" && value === "box") {
//     const border = { color: { rgb: "#000000" }, width: { v: 1 } };
//     style.borderTop = border;
//     style.borderBottom = border;
//     style.borderLeft = border;
//     style.borderRight = border;
//   }
// };

// const ensureParagraph = (body: AnyRecord, paragraphIndex: number): AnyRecord => {
//   const paragraphs = (body.paragraphs ?? []) as AnyRecord[];
//   body.paragraphs = paragraphs;

//   while (paragraphs.length <= paragraphIndex) {
//     paragraphs.push({ startIndex: Math.max(0, String(body.dataStream ?? "").length - 1) });
//   }

//   return paragraphs[paragraphIndex] ?? {};
// };

// const upsertTextRunStyle = (
//   body: AnyRecord,
//   range: { start: number; end: number },
//   style: AnyRecord
// ): void => {
//   const textRuns = (body.textRuns ?? []) as AnyRecord[];
//   body.textRuns = textRuns;

//   const start = range.start;
//   const end = range.end + 1;
//   const existingRun = textRuns.find((run) => Number(run.st) === start && Number(run.ed) === end);

//   if (existingRun) {
//     existingRun.ts = { ...(existingRun.ts ?? {}), ...style };
//     return;
//   }

//   textRuns.push({
//     st: start,
//     ed: end,
//     ts: style
//   });
// };

// const normalizeTextRuns = (body: AnyRecord): void => {
//   const textRuns = (body.textRuns ?? []) as AnyRecord[];
//   if (textRuns.length <= 1) return;

//   const dataLength = String(body.dataStream ?? "").length;
//   const boundaries = new Set<number>();
//   const runBounds = textRuns
//     .map((run) => ({
//       run,
//       start: Math.max(0, Math.min(dataLength, Number(run.st))),
//       end: Math.max(0, Math.min(dataLength, Number(run.ed)))
//     }))
//     .filter(({ start, end }) => Number.isFinite(start) && Number.isFinite(end) && start < end);

//   runBounds.forEach(({ start, end }) => {
//     boundaries.add(start);
//     boundaries.add(end);
//   });

//   const sortedBoundaries = Array.from(boundaries).sort((left, right) => left - right);
//   const normalizedRuns: AnyRecord[] = [];

//   for (let index = 0; index < sortedBoundaries.length - 1; index += 1) {
//     const start = sortedBoundaries[index];
//     const end = sortedBoundaries[index + 1];
//     if (start === undefined || end === undefined || start >= end) continue;

//     const style = runBounds.reduce<AnyRecord>(
//       (mergedStyle, { run, start: runStart, end: runEnd }) => {
//         if (runStart <= start && end <= runEnd) return { ...mergedStyle, ...(run.ts ?? {}) };

//         return mergedStyle;
//       },
//       {}
//     );
//     if (Object.keys(style).length === 0) continue;

//     const previousRun = normalizedRuns[normalizedRuns.length - 1];
//     if (
//       previousRun &&
//       Number(previousRun.ed) === start &&
//       JSON.stringify(previousRun.ts ?? {}) === JSON.stringify(style)
//     ) {
//       previousRun.ed = end;
//       continue;
//     }

//     normalizedRuns.push({ st: start, ed: end, ts: style });
//   }

//   body.textRuns = normalizedRuns;
// };

// const applyTextStyleAtomToBody = (body: AnyRecord, atom: WordStateAtom): void => {
//   const property = atom.property ?? [];
//   const target = property[1];
//   const styleProperty = property[2];
//   if (target === undefined || styleProperty === undefined || styleProperty.endsWith("Not")) return;

//   const dataStream = String(body.dataStream ?? "");
//   const range = findTargetRange(dataStream, target);
//   if (!range) return;

//   const style: AnyRecord = {};
//   applyTextStyleProperty(style, styleProperty, valueToString(atom.value));

//   upsertTextRunStyle(body, range, style);
// };

// const makeNumberUnit = (value: number): AnyRecord => ({ v: value });

// const makeTableSnapshot = (
//   shape: string,
//   cellsText: string | undefined
// ): Pick<AnyRecord, "body" | "tableSource"> => {
//   const { rows, columns } = parseShape(shape);
//   const cells = (cellsText ?? "").split("|");
//   const tableId = "word-table-0";
//   let cellIndex = 0;
//   let dataStream = TABLE_START;
//   const paragraphs: AnyRecord[] = [];
//   const sectionBreaks: AnyRecord[] = [];

//   for (let row = 0; row < rows; row += 1) {
//     dataStream += TABLE_ROW_START;
//     for (let column = 0; column < columns; column += 1) {
//       const cellText = cells[cellIndex] ?? "";
//       cellIndex += 1;
//       dataStream += TABLE_CELL_START + cellText.replaceAll("\n", " ") + "\r\n" + TABLE_CELL_END;
//       paragraphs.push({
//         startIndex: Math.max(0, dataStream.length - 3),
//         paragraphStyle: {
//           spaceAbove: makeNumberUnit(3),
//           lineSpacing: 2,
//           spaceBelow: makeNumberUnit(0)
//         }
//       });
//       sectionBreaks.push({ startIndex: Math.max(0, dataStream.length - 2) });
//     }
//     dataStream += TABLE_ROW_END;
//   }

//   const tableDataStreamLength = dataStream.length + 1;
//   dataStream += TABLE_END + "\r\n";
//   paragraphs.push({ startIndex: Math.max(0, dataStream.length - 2) });
//   sectionBreaks.push({ startIndex: Math.max(0, dataStream.length - 1) });

//   const cellSize = {
//     type: TableSizeType.SPECIFIED,
//     width: makeNumberUnit(120)
//   };
//   const tableRows = Array.from({ length: rows }, (_unused, rowIndex) => ({
//     tableCells: Array.from({ length: columns }, () => ({ size: cellSize })),
//     trHeight: {
//       val: makeNumberUnit(30),
//       hRule: TableRowHeightRule.AUTO
//     },
//     isFirstRow: rowIndex === 0 ? BooleanNumber.TRUE : BooleanNumber.FALSE
//   }));

//   return {
//     body: {
//       dataStream,
//       textRuns: [],
//       customBlocks: [],
//       tables: [{ startIndex: 0, endIndex: tableDataStreamLength, tableId }],
//       paragraphs,
//       sectionBreaks
//     },
//     tableSource: {
//       [tableId]: {
//         tableId,
//         tableRows,
//         tableColumns: Array.from({ length: columns }, () => ({ size: cellSize })),
//         align: TableAlignmentType.START,
//         indent: makeNumberUnit(0),
//         textWrap: TableTextWrapType.NONE,
//         position: {},
//         dist: {},
//         size: {
//           type: TableSizeType.SPECIFIED,
//           width: makeNumberUnit(columns * 120)
//         }
//       }
//     }
//   };
// };

// const buildSnapshotFromAtoms = (atoms: WordStateAtom[]): AnyRecord => {
//   const currentSnapshot = clone(getSnapshot() ?? {});
//   const baseTextAtom = atoms.find(
//     (atom) =>
//       atom.f === "word-body" &&
//       (atom.property?.[0] === "text" || atom.property?.[0] === "textWithPageBreak")
//   );
//   const tableShapeAtom = atoms.find(
//     (atom) =>
//       atom.f === "word-table" &&
//       atom.property?.[0] === "tables" &&
//       atom.property?.[1] === "0" &&
//       atom.property?.[2] === "shape"
//   );
//   const tableCellsTextAtom = atoms.find(
//     (atom) =>
//       atom.f === "word-table" &&
//       atom.property?.[0] === "tables" &&
//       atom.property?.[1] === "0" &&
//       atom.property?.[2] === "cellsText"
//   );

//   let body = baseTextAtom
//     ? makeDocumentBody(valueToString(baseTextAtom.value))
//     : clone(currentSnapshot.body ?? makeDocumentBody(getBodyTextWithPageBreak()));

//   if (tableShapeAtom) {
//     const tableSnapshot = makeTableSnapshot(
//       valueToString(tableShapeAtom.value),
//       tableCellsTextAtom ? valueToString(tableCellsTextAtom.value) : undefined
//     );
//     body = tableSnapshot.body;
//     currentSnapshot.tableSource = tableSnapshot.tableSource;
//   } else if (tableCellsTextAtom && !baseTextAtom) {
//     const currentShape = getTableAtom("shape");
//     if (currentShape) {
//       const tableSnapshot = makeTableSnapshot(
//         currentShape,
//         valueToString(tableCellsTextAtom.value)
//       );
//       body = tableSnapshot.body;
//       currentSnapshot.tableSource = tableSnapshot.tableSource;
//     }
//   } else if (baseTextAtom) {
//     currentSnapshot.tableSource = {};
//   }

//   for (const atom of atoms) {
//     const property = atom.property ?? [];

//     if (atom.f === "word-text-style") applyTextStyleAtomToBody(body, atom);

//     if (atom.f === "word-paragraph" && property[0] === "paragraphs") {
//       const paragraphIndex = Number(property[1] ?? 0);
//       const paragraphProperty = property[2];
//       if (paragraphProperty === undefined || paragraphProperty.endsWith("Not")) continue;

//       applyParagraphProperty(
//         ensureParagraph(body, paragraphIndex),
//         paragraphProperty,
//         valueToString(atom.value)
//       );
//     }

//     if (atom.f === "word-document" && property[0] === "style" && property[1] === "fontSizeOnly") {
//       const textLength = String(body.dataStream ?? "").replace(/\r\n$/, "").length;
//       if (textLength > 0) {
//         upsertTextRunStyle(
//           body,
//           { start: 0, end: textLength - 1 },
//           { fs: Number(valueToString(atom.value)) }
//         );
//       }
//     }
//   }

//   normalizeTextRuns(body);

//   const documentStyle = currentSnapshot.documentStyle ?? {};
//   const footerAtom = atoms.find(
//     (atom) => atom.f === "word-footer" && atom.property?.[0] === "text"
//   );
//   if (footerAtom) {
//     const footerId = documentStyle.defaultFooterId || "word-footer-0";
//     documentStyle.defaultFooterId = footerId;
//     currentSnapshot.footers = {
//       ...(currentSnapshot.footers ?? {}),
//       [footerId]: {
//         footerId,
//         body: makeDocumentBody(valueToString(footerAtom.value))
//       }
//     };
//   }

//   return {
//     ...currentSnapshot,
//     body,
//     documentStyle
//   };
// };

// const refreshWordDocumentView = (doc: AnyRecord): boolean => {
//   const unitId = doc.getUnitId?.();
//   if (!unitId) return false;

//   const injector = WordRuntimeStore.runtime.univer.__getInjector();
//   const renderManagerService = injector.get(IRenderManagerService);
//   const renderUnit = renderManagerService.getRenderById(unitId);
//   const skeletonManager = renderUnit?.with(DocSkeletonManagerService) as AnyRecord | undefined;
//   const viewModel = skeletonManager?.getViewModel?.();
//   const skeleton = skeletonManager?.getSkeleton?.();
//   if (!skeletonManager || !viewModel || !skeleton) return false;

//   viewModel.reset(doc);
//   skeleton.makeDirty?.(true);
//   skeleton.calculate();
//   skeletonManager._currentSkeletonBefore$.next?.(skeleton);
//   skeletonManager._currentSkeleton$.next?.(skeleton);
//   skeletonManager._currentViewModel$.next?.(viewModel);
//   const mainComponent = renderUnit?.mainComponent as AnyRecord | undefined;
//   mainComponent?.changeSkeleton?.(skeleton);
//   mainComponent?.makeDirty?.(true);
//   renderUnit?.components?.forEach?.((component: AnyRecord) => {
//     component.changeSkeleton?.(skeleton);
//     component.makeDirty?.(true);
//   });
//   renderUnit?.scene?.makeDirty?.(true);

//   return true;
// };

// const refreshWordDocumentViewSoon = (doc: AnyRecord): void => {
//   if (refreshWordDocumentView(doc)) return;

//   requestAnimationFrame(() => {
//     refreshWordDocumentView(doc);
//   });
// };

// const applyWordState = (atoms: WordStateAtom[]): void => {
//   const doc = getDocumentModel();
//   if (!doc) return;

//   const nextSnapshot = buildSnapshotFromAtoms(atoms);
//   doc.reset(nextSnapshot);
//   refreshWordDocumentViewSoon(doc);
// };

// const isWordAtomValue = (value: unknown): value is WordAtomValue =>
//   typeof value === "string" || typeof value === "number" || typeof value === "boolean";

// const collectWordMetaAtoms = (
//   f: string,
//   property: string[],
//   value: unknown,
//   atoms: WordStateAtom[]
// ): void => {
//   if (isWordAtomValue(value)) {
//     atoms.push({ f, property, value });
//     return;
//   }

//   if (value && typeof value === "object" && !Array.isArray(value)) {
//     Object.entries(value as AnyRecord).forEach(([key, childValue]) => {
//       collectWordMetaAtoms(f, [...property, key], childValue, atoms);
//     });
//   }
// };

// const wordMetaEntryToAtoms = (entry: WordMetaEntry): WordStateAtom[] => {
//   const f =
//     typeof entry.address === "string" ? entry.address : typeof entry.f === "string" ? entry.f : "";

//   if (!f) {
//     throw new Error("Each word meta entry must include an address or f field.");
//   }

//   const atoms: WordStateAtom[] = [];
//   Object.entries(entry).forEach(([key, value]) => {
//     if (key === "address" || key === "f") return;

//     collectWordMetaAtoms(f, [key], value, atoms);
//   });

//   return atoms;
// };

// const applyWordMeta = (entries: WordMetaEntry[]): string[] => {
//   if (!Array.isArray(entries)) {
//     throw new Error("Word meta entries must be an array.");
//   }

//   const atoms = entries.flatMap(wordMetaEntryToAtoms);
//   applyWordState(atoms);

//   return atoms.map((atom) => getWordStateAtom(atom));
// };
