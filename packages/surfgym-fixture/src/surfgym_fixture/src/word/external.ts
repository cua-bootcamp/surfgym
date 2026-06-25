import {
  _getBodyMeta,
  _getDocumentMeta,
  _getFooterMeta,
  _getParagraphMeta,
  _getTableMeta,
  _getTextMeta,
  _setBodyMeta,
  _setDocumentMeta,
  _setFooterMeta,
  _setParagraphMeta,
  _setTableMeta,
  _setTextMeta
} from "./internal";
import { setFactory, getFactory, SET, type Path, type Value, type ChainFunc } from "../external";

const external: ChainFunc = {
  body,
  text,
  paragraph,
  table,
  footer,
  document
};

export const set = setFactory(external);
export const get = getFactory(external);

export function body() {
  return {
    ..._getBodyMeta(),
    [SET]: (path: Path[], value: Value) => _setBodyMeta(path, value)
  };
}

export function text(target: Value): ChainFunc {
  return {
    ..._getTextMeta(target),
    [SET]: (path: Path[], value: Value) => _setTextMeta(target, path, value)
  };
}

export function paragraph(index: Value): ChainFunc {
  const paragraphIndex = normalizeParagraphIndex(index);

  return {
    ..._getParagraphMeta(paragraphIndex),
    [SET]: (path: Path[], value: Value) => _setParagraphMeta(paragraphIndex, path, value)
  };
}

export function table(index: Value): ChainFunc {
  const tableIndex = normalizeIndex(index, "table");

  return {
    ..._getTableMeta(tableIndex),
    [SET]: (path: Path[], value: Value) => _setTableMeta(tableIndex, path, value)
  };
}

export function footer(): ChainFunc {
  return {
    ..._getFooterMeta(),
    [SET]: (path: Path[], value: Value) => _setFooterMeta(path, value)
  };
}

export function document(): ChainFunc {
  return {
    ..._getDocumentMeta(),
    [SET]: (path: Path[], value: Value) => _setDocumentMeta(path, value)
  };
}

function normalizeParagraphIndex(index: Value): number {
  return normalizeIndex(index, "paragraph");
}

function normalizeIndex(index: Value, label: string): number {
  const normalizedIndex = typeof index === "number" ? index : Number(index);
  if (!Number.isInteger(normalizedIndex) || normalizedIndex < 0) {
    throw new Error(`Invalid ${label} index: ${String(index)}`);
  }

  return normalizedIndex;
}
