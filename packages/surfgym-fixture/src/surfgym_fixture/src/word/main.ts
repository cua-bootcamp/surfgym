import { LocaleType, createUniver, mergeLocales } from "@univerjs/presets";
import { UniverDocsCorePreset } from "@univerjs/preset-docs-core";
import UniverPresetDocsCoreEnUS from "@univerjs/preset-docs-core/locales/en-US";
import {
  body,
  document as documentQuery,
  footer,
  get,
  paragraph,
  set,
  table,
  text
} from "./external";
import { WordRuntimeStore } from "./internal";
import { renderWordMockToolbar } from "./word-ui";

import "@univerjs/preset-docs-core/lib/index.css";
import "./style.css";

const { univer, univerAPI } = createUniver({
  locale: LocaleType.EN_US,
  locales: {
    [LocaleType.EN_US]: mergeLocales(UniverPresetDocsCoreEnUS)
  },
  presets: [
    UniverDocsCorePreset({
      container: "app",
      header: false,
      toolbar: false,
      footer: true,
      contextMenu: true
    })
  ]
});

const document = univerAPI.createUniverDoc({});
WordRuntimeStore.runtime = { univer, univerAPI, document };

renderWordMockToolbar({
  containerId: "word-custom-toolbar",
  getLineSpacing: () => Number(get({ query: [["paragraph", 0]], path: ["lineSpacing"] }) ?? 1),
  setLineSpacing: (lineSpacing) => {
    set({ query: [["paragraph", 0]], path: ["lineSpacing"], value: lineSpacing });
  },
  insertTable: (rows, columns) => {
    set({ query: [["table", 0]], path: ["shape"], value: `${rows}x${columns}` });
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
    body: typeof body;
    text: typeof text;
    paragraph: typeof paragraph;
    table: typeof table;
    footer: typeof footer;
    document: typeof documentQuery;
  };
};

wordGlobal.univerAPI = univerAPI;
wordGlobal.surfgym = {
  get,
  set,
  body,
  text,
  paragraph,
  table,
  footer,
  document: documentQuery
};
