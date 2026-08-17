import { LocaleType, mergeLocales, Univer } from "@univerjs/core";
import { FUniver } from "@univerjs/core/facade";
import { UniverDocsCorePreset } from "@univerjs/preset-docs-core";
import UniverPresetDocsCoreEnUS from "@univerjs/preset-docs-core/locales/en-US";

type FixturePreset = {
  plugins: Array<
    | (new (...args: never[]) => unknown)
    | [new (...args: never[]) => unknown, unknown]
  >;
};

function registerPreset(univer: Univer, preset: FixturePreset) {
  for (const plugin of preset.plugins) {
    if (Array.isArray(plugin)) {
      univer.registerPlugin(plugin[0] as never, plugin[1] as never);
    } else {
      univer.registerPlugin(plugin as never);
    }
  }
}

export function createWordFixtureRuntime() {
  const univer = new Univer({
    locale: LocaleType.EN_US,
    locales: {
      [LocaleType.EN_US]: mergeLocales(UniverPresetDocsCoreEnUS),
    },
  });
  registerPreset(
    univer,
    UniverDocsCorePreset({
      container: "app",
      header: false,
      toolbar: false,
      footer: true,
      contextMenu: true,
    }) as FixturePreset,
  );

  const univerAPI = FUniver.newAPI(univer);
  const document = univerAPI.createUniverDoc({});

  return { univer, univerAPI, document };
}
