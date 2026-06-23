import { LocaleType, createUniver, mergeLocales } from "@univerjs/presets";
import { UniverDocsCorePreset } from "@univerjs/preset-docs-core";
import UniverPresetDocsCoreEnUS from "@univerjs/preset-docs-core/locales/en-US";
import { get, set } from "./external";
import { WordRuntimeStore } from "./internal";

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
