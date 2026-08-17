import type { Path, Value } from "../external";
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

const BODY_PATHS = {
  text: ["text"],
  textWithPageBreak: ["textWithPageBreak"]
} as const;

const TEXT_PATHS = {
  bold: ["bold"],
  italic: ["italic"],
  underline: ["underline"],
  strikethrough: ["strikethrough"],
  fontFamily: ["fontFamily"],
  fontSize: ["fontSize"],
  color: ["color"],
  backgroundColor: ["backgroundColor"],
  verticalAlign: ["verticalAlign"]
} as const;

const PARAGRAPH_PATHS = {
  lineSpacing: ["lineSpacing"],
  horizontalAlign: ["horizontalAlign"],
  border: ["border"],
  namedStyleType: ["namedStyleType"]
} as const;

const TABLE_PATHS = {
  shape: ["shape"],
  cellsText: ["cellsText"]
} as const;

const FOOTER_PATHS = {
  text: ["text"]
} as const;

const DOCUMENT_PATHS = {
  fontSizeOnly: ["style", "fontSizeOnly"],
  defaultFontFamily: ["defaultFontFamily"]
} as const;

type BodySpec = {
  kind: "body";
  property: keyof typeof BODY_PATHS;
};

type TextSpec = {
  kind: "text";
  text: string;
  occurrence?: number;
  property: keyof typeof TEXT_PATHS;
};

type ParagraphSpec = {
  kind: "paragraph";
  index: number;
  property: keyof typeof PARAGRAPH_PATHS;
};

type TableSpec = {
  kind: "table";
  index: number;
  property: keyof typeof TABLE_PATHS;
};

type FooterSpec = {
  kind: "footer";
  property: keyof typeof FOOTER_PATHS;
};

type DocumentSpec = {
  kind: "document";
  property: keyof typeof DOCUMENT_PATHS;
};

export type WordSpec = BodySpec | TextSpec | ParagraphSpec | TableSpec | FooterSpec | DocumentSpec;

export type WordStateAtom = {
  spec: WordSpec;
  value: Value;
};

export type Get = typeof get;
export type Set = typeof set;

export function get(spec: WordSpec): unknown {
  switch (spec.kind) {
    case "body":
      return readPath(_getBodyMeta(), resolvePath(BODY_PATHS, spec.property, spec.kind));
    case "text":
      return readPath(
        _getTextMeta(resolveTextTarget(spec)),
        resolvePath(TEXT_PATHS, spec.property, spec.kind)
      );
    case "paragraph":
      return readPath(
        _getParagraphMeta(normalizeIndex(spec.index, spec.kind)),
        resolvePath(PARAGRAPH_PATHS, spec.property, spec.kind)
      );
    case "table":
      return readPath(
        _getTableMeta(normalizeIndex(spec.index, spec.kind)),
        resolvePath(TABLE_PATHS, spec.property, spec.kind)
      );
    case "footer":
      return readPath(_getFooterMeta(), resolvePath(FOOTER_PATHS, spec.property, spec.kind));
    case "document":
      return readPath(_getDocumentMeta(), resolvePath(DOCUMENT_PATHS, spec.property, spec.kind));
  }

  throw unsupportedSpec(spec);
}

export function set(spec: WordSpec, value: Value) {
  switch (spec.kind) {
    case "body":
      return _setBodyMeta(resolvePath(BODY_PATHS, spec.property, spec.kind), value);
    case "text":
      return _setTextMeta(
        resolveTextTarget(spec),
        resolvePath(TEXT_PATHS, spec.property, spec.kind),
        value
      );
    case "paragraph":
      return _setParagraphMeta(
        normalizeIndex(spec.index, spec.kind),
        resolvePath(PARAGRAPH_PATHS, spec.property, spec.kind),
        value
      );
    case "table":
      return _setTableMeta(
        normalizeIndex(spec.index, spec.kind),
        resolvePath(TABLE_PATHS, spec.property, spec.kind),
        value
      );
    case "footer":
      return _setFooterMeta(resolvePath(FOOTER_PATHS, spec.property, spec.kind), value);
    case "document":
      return _setDocumentMeta(resolvePath(DOCUMENT_PATHS, spec.property, spec.kind), value);
  }

  throw unsupportedSpec(spec);
}

function resolveTextTarget(spec: TextSpec): Value {
  const occurrence = spec.occurrence ?? 0;
  if (!Number.isInteger(occurrence) || occurrence < 0) {
    throw new Error(`Invalid text occurrence: ${String(occurrence)}`);
  }

  return {
    value: spec.text,
    occurrence
  };
}

function normalizeIndex(index: number, label: string): number {
  if (!Number.isInteger(index) || index < 0) {
    throw new Error(`Invalid ${label} index: ${String(index)}`);
  }

  return index;
}

function resolvePath(
  paths: Readonly<Record<string, readonly string[]>>,
  property: string,
  label: string
): Path[] {
  const path = paths[property];
  if (!path) throw new Error(`Unsupported ${label} property: ${property}`);
  return [...path];
}

function readPath(value: unknown, path: Path[]): unknown {
  let current = value;

  for (const key of path) {
    if (current === null || typeof current !== "object") return undefined;
    current = (current as Record<PropertyKey, unknown>)[key];
  }

  return current;
}

function unsupportedSpec(spec: never): Error {
  const kind = (spec as { kind?: unknown }).kind;
  return new Error(`Unsupported word spec kind: ${String(kind)}`);
}
