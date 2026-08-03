import { LocaleType, createUniver, mergeLocales } from "@univerjs/presets";
import { UniverDocsCorePreset } from "@univerjs/preset-docs-core";
import UniverPresetDocsCoreEnUS from "@univerjs/preset-docs-core/locales/en-US";
import { get, set } from "./external";
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
  getLineSpacing: () => Number(get({ kind: "paragraph", index: 0, property: "lineSpacing" }) ?? 1),
  setLineSpacing: (lineSpacing) => {
    set({ kind: "paragraph", index: 0, property: "lineSpacing" }, lineSpacing);
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
