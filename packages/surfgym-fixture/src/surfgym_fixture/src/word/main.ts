// // src/word/main.ts 예시
// import { LocaleType, createUniver, mergeLocales } from "@univerjs/presets";
// import { DocSelectionManagerService, UniverDocsCorePreset } from "@univerjs/preset-docs-core";
// import UniverPresetDocsCoreEnUS from "@univerjs/preset-docs-core/locales/en-US";
// import { get, set } from "./external";
// import {
//   WordRuntimeStore,
//   type AnyRecord,
//   type WordMetaEntry,
//   type WordStateAtom,
//   applyWordMeta,
//   applyWordState,
//   getBody,
//   getDocumentModel,
//   getParagraphProperty,
//   getWordMeta,
//   getWordStateAtom
// } from "./internal";
// import { renderWordMockToolbar } from "./word-ui";

// import "@univerjs/preset-docs-core/lib/index.css";
// import "./style.css";

// const { univer, univerAPI } = createUniver({
//   locale: LocaleType.EN_US,
//   locales: {
//     [LocaleType.EN_US]: mergeLocales(UniverPresetDocsCoreEnUS)
//   },
//   presets: [
//     UniverDocsCorePreset({
//       container: "app",
//       header: false,
//       toolbar: false,
//       footer: true,
//       contextMenu: true
//     })
//   ]
// });

// univerAPI.createUniverDoc({});
// WordRuntimeStore.runtime = { univer, univerAPI };

// declare global {
//   interface Window {
//     univerAPI?: unknown;
//     __getWordStateAtom?: (atom: WordStateAtom) => string;
//     __applyWordState?: (atoms: WordStateAtom[]) => void;
//     getWordMeta?: (target?: string) => AnyRecord;
//     applyWordMeta?: (entries: WordMetaEntry[]) => string[];
//   }
// }

// window.univerAPI = univerAPI;
// (window as unknown as Window & { surfgym: { get: typeof get; set: typeof set } }).surfgym = {
//   get,
//   set
// };

// const getDocSelectionManager = (): AnyRecord | null => {
//   try {
//     return univer.__getInjector().get(DocSelectionManagerService) as AnyRecord;
//   } catch {
//     return null;
//   }
// };

// const getCurrentBodyDocRanges = (): AnyRecord[] => {
//   const doc = getDocumentModel();
//   const unitId = doc?.getUnitId?.();
//   const selectionManager = getDocSelectionManager();
//   if (!selectionManager || !unitId) return [];

//   const activeTextRange = selectionManager.getActiveTextRange?.();
//   const activeRectRange = selectionManager.getActiveRectRange?.();
//   const isBodyRange = (range: AnyRecord) => !range.segmentId || range.segmentId === unitId;
//   const isUsableRange = (range: AnyRecord) =>
//     isBodyRange(range) &&
//     Number.isFinite(Number(range.startOffset)) &&
//     Number.isFinite(Number(range.endOffset));
//   const activeRange = [activeTextRange, activeRectRange].find((range): range is AnyRecord =>
//     Boolean(range && isUsableRange(range))
//   );

//   if (activeRange) {
//     return [activeRange];
//   }

//   const docRanges = selectionManager.getDocRanges?.();
//   const textRanges = selectionManager.getTextRanges?.({ unitId, subUnitId: unitId });
//   const ranges =
//     Array.isArray(textRanges) && textRanges.length
//       ? textRanges
//       : Array.isArray(docRanges) && docRanges.length
//         ? docRanges
//         : [];

//   return (ranges as AnyRecord[]).filter(isUsableRange);
// };

// const getParagraphIndexAtOffset = (paragraphs: AnyRecord[], offset: number): number | null => {
//   if (paragraphs.length === 0) return null;

//   const normalizedOffset = Math.max(0, offset);
//   const index = paragraphs.findIndex(
//     (paragraph) => Number(paragraph.startIndex) >= normalizedOffset
//   );

//   return index >= 0 ? index : paragraphs.length - 1;
// };

// const getParagraphIndexesInRange = (paragraphs: AnyRecord[], range: AnyRecord): number[] => {
//   const rawStart = Number(range.startOffset);
//   const rawEnd = Number(range.endOffset);
//   if (!Number.isFinite(rawStart) || !Number.isFinite(rawEnd)) return [];

//   const startOffset = Math.min(rawStart, rawEnd);
//   const endOffset = Math.max(rawStart, rawEnd);
//   const isCollapsed = range.collapsed === true || startOffset === endOffset;
//   const startIndex = getParagraphIndexAtOffset(paragraphs, startOffset);
//   if (startIndex === null) return [];
//   if (isCollapsed) return [startIndex];

//   const endIndex = getParagraphIndexAtOffset(paragraphs, Math.max(startOffset, endOffset - 1));
//   if (endIndex === null) return [startIndex];

//   const firstIndex = Math.min(startIndex, endIndex);
//   const lastIndex = Math.max(startIndex, endIndex);
//   return Array.from({ length: lastIndex - firstIndex + 1 }, (_unused, index) => firstIndex + index);
// };

// const getSelectedParagraphIndexes = (): number[] => {
//   const body = getBody();
//   const paragraphs = (body.paragraphs ?? []) as AnyRecord[];
//   if (paragraphs.length === 0) return [];

//   const ranges = getCurrentBodyDocRanges();
//   if (ranges.length === 0) return [];

//   return Array.from(
//     new Set(ranges.flatMap((range) => getParagraphIndexesInRange(paragraphs, range)))
//   );
// };

// const getDocumentLineSpacing = (): number => {
//   const paragraphs = (getBody().paragraphs ?? []) as AnyRecord[];
//   const paragraphIndex = getSelectedParagraphIndexes()[0] ?? 0;
//   const firstLineSpacing = Number(
//     getParagraphProperty(paragraphs[paragraphIndex], "lineSpacing") || 1
//   );

//   return Number.isFinite(firstLineSpacing) && firstLineSpacing > 0 ? firstLineSpacing : 1;
// };

// const applyDocumentLineSpacing = (lineSpacing: number): void => {
//   const normalizedLineSpacing = Number(lineSpacing);
//   if (!Number.isFinite(normalizedLineSpacing) || normalizedLineSpacing <= 0) return;

//   const targetParagraphIndexes = getSelectedParagraphIndexes();
//   if (targetParagraphIndexes.length === 0) return;

//   applyWordState(
//     targetParagraphIndexes.map((index) => ({
//       f: "word-paragraph",
//       property: ["paragraphs", String(index), "lineSpacing"],
//       value: Math.round(normalizedLineSpacing * 100) / 100
//     }))
//   );
// };

// const insertWordTableFromToolbar = (rows: number, columns: number): void => {
//   applyWordState([
//     {
//       f: "word-table",
//       property: ["tables", "0", "shape"],
//       value: `${rows}x${columns}`
//     }
//   ]);
// };

// window.__applyWordState = applyWordState;
// window.__getWordStateAtom = getWordStateAtom;
// window.getWordMeta = getWordMeta;
// window.applyWordMeta = applyWordMeta;

// renderWordMockToolbar({
//   containerId: "word-custom-toolbar",
//   getLineSpacing: getDocumentLineSpacing,
//   setLineSpacing: applyDocumentLineSpacing,
//   insertTable: insertWordTableFromToolbar,
//   univerAPI
// });
