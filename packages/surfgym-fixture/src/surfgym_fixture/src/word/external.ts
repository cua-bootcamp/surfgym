import { _getBodyMeta, _getTextMeta } from "./internal";
import { setFactory, getFactory, type Path, type Value, SET, type ChainFunc } from "../external";

const external: ChainFunc = {
  body
  // footer
};

export const set = setFactory(external);
export const get = getFactory(external);

function body() {
  return {
    ..._getBodyMeta(),
    text
    // [SET]: (path: Path[], value: Value) => {
    //   const property = firstPathPart(path);
    //   if (property !== "text" && property !== "textWithPageBreak") {
    //     throw new Error(`Unsupported word body set path: ${property}`);
    //   }
    //   setWordAtom("word-body", [property], value);
    // }
  };
}

function text(target: Value): ChainFunc {
  const targetStr = target == null ? "" : String(target);

  return _getTextMeta(targetStr);
}

function setWordAtom(f: string, property: string[], value: Value): void {
  applyWordState([{ f, property, value: toWordAtomValue(value) }]);
}

function firstPathPart(path: Path[]): string {
  const [property] = path;
  if (typeof property !== "string") throw new Error("Word meta path must start with a string key.");

  return property;
}

const paragraphProperties = ["horizontalAlign", "lineSpacing", "namedStyleType", "border"];

function paragraph(paragraphRef: Value = 0) {
  const paragraphIndex = Number(paragraphRef ?? 0);
  if (!Number.isFinite(paragraphIndex) || paragraphIndex < 0) {
    throw new Error(`Invalid paragraph index: ${String(paragraphRef)}`);
  }

  const paragraphs = (getBody().paragraphs ?? []) as AnyRecord[];
  const paragraphData = paragraphs[paragraphIndex];

  return {
    ...Object.fromEntries(
      paragraphProperties.map((property) => [
        property,
        getParagraphProperty(paragraphData, property)
      ])
    ),
    [SET]: (path: Path[], value: Value) => {
      const property = firstPathPart(path);
      setWordAtom("word-paragraph", ["paragraphs", String(paragraphIndex), property], value);
    }
  };
}

function table(tableRef: Value = 0) {
  const tableIndex = Number(tableRef ?? 0);
  if (tableIndex !== 0) {
    throw new Error("Only the first word table is supported.");
  }

  return {
    shape: getTableAtom("shape"),
    cellsText: getTableAtom("cellsText"),
    [SET]: (path: Path[], value: Value) => {
      const property = firstPathPart(path);
      if (property !== "shape" && property !== "cellsText") {
        throw new Error(`Unsupported word table set path: ${property}`);
      }

      setWordAtom("word-table", ["tables", "0", property], value);
    }
  };
}

function footer() {
  return {
    text: getFooterText(),
    [SET]: (path: Path[], value: Value) => {
      const property = firstPathPart(path);
      if (property !== "text") throw new Error(`Unsupported word footer set path: ${property}`);

      setWordAtom("word-footer", ["text"], value);
    }
  };
}

function style() {
  return {
    fontSizeOnly: getDocumentUniformFontSize(),
    [SET]: (path: Path[], value: Value) => {
      const property = firstPathPart(path);
      if (property !== "fontSizeOnly") {
        throw new Error(`Unsupported word document style set path: ${property}`);
      }

      setWordAtom("word-document", ["style", property], value);
    }
  };
}
