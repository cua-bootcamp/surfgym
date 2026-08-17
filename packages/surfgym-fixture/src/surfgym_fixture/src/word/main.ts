import { get, set } from "./external";
import { WordRuntimeStore } from "./internal";
import { createWordFixtureRuntime } from "./word-bootstrap";
import { createParagraphSelectionTracker, setSelectedParagraphLineSpacing } from "./word-selection";
import { renderWordMockToolbar } from "./word-ui";

import "@univerjs/preset-docs-core/lib/index.css";
import "./style.css";

const { univer, univerAPI, document } = createWordFixtureRuntime();
WordRuntimeStore.runtime = { univer, univerAPI, document };
const paragraphSelectionTracker = createParagraphSelectionTracker(
  univerAPI as unknown as Parameters<typeof createParagraphSelectionTracker>[0],
);

renderWordMockToolbar({
  containerId: "word-custom-toolbar",
  getLineSpacing: () => {
    const index = paragraphSelectionTracker.getSelectedParagraphIndexes(document.getSnapshot())[0] ?? 0;
    return Number(get({ kind: "paragraph", index, property: "lineSpacing" }) ?? 1);
  },
  setLineSpacing: (lineSpacing) => {
    setSelectedParagraphLineSpacing(
      paragraphSelectionTracker,
      document.getSnapshot(),
      lineSpacing,
      set,
    );
  },
  getDocumentDefaultFont: () => {
    const fontFamily = get({ kind: "document", property: "defaultFontFamily" });
    return typeof fontFamily === "string" ? fontFamily : undefined;
  },
  setDocumentDefaultFont: (fontFamily) => {
    set({ kind: "document", property: "defaultFontFamily" }, fontFamily);
  },
  insertTable: (rows, columns) => {
    set({ kind: "table", index: 0, property: "shape" }, `${rows}x${columns}`);
  },
  univerAPI: univerAPI as unknown as NonNullable<
    Parameters<typeof renderWordMockToolbar>[0]["univerAPI"]
  >
});

const wordGlobal = window as unknown as {
  univerAPI?: unknown;
  surfgym: {
    get: typeof get;
    set: typeof set;
  };
};

wordGlobal.univerAPI = univerAPI;
wordGlobal.surfgym = {
  get,
  set
};
