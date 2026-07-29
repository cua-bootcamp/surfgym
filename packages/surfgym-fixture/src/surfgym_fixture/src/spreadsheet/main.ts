import { createUniver, LocaleType, mergeLocales } from "@univerjs/presets";
import {
  OpenConditionalFormattingOperator,
  UniverSheetsConditionalFormattingPreset
} from "@univerjs/presets/preset-sheets-conditional-formatting";
import UniverPresetSheetsConditionalFormattingEnUS from "@univerjs/presets/preset-sheets-conditional-formatting/locales/en-US";
import { UniverSheetsAdvancedPreset } from "@univerjs/presets/preset-sheets-advanced";
import UniverPresetSheetsAdvancedEnUS from "@univerjs/presets/preset-sheets-advanced/locales/en-US";
import { UniverSheetsDrawingPreset } from "@univerjs/presets/preset-sheets-drawing";
import UniverPresetSheetsDrawingEnUS from "@univerjs/presets/preset-sheets-drawing/locales/en-US";
import { UniverSheetsFilterPreset } from "@univerjs/presets/preset-sheets-filter";
import UniverPresetSheetsFilterEnUS from "@univerjs/presets/preset-sheets-filter/locales/en-US";
import { UniverSheetsSortPreset } from "@univerjs/presets/preset-sheets-sort";
import UniverPresetSheetsSortEnUS from "@univerjs/presets/preset-sheets-sort/locales/en-US";
import { UniverSheetsCorePreset, type FWorksheet } from "@univerjs/preset-sheets-core";
import UniverPresetSheetsCoreEnUS from "@univerjs/preset-sheets-core/locales/en-US";
import { createSpreadsheetActions } from "./spreadsheet-actions";
import { applyState, get, set } from "./external";
import { SpreadsheetRuntimeStore } from "./runtime";
import { renderSpreadsheetMockToolbar, setupSpreadsheetUi } from "./spreadsheet-ui";

import "@univerjs/preset-sheets-core/lib/index.css";
import "@univerjs/presets/lib/styles/preset-sheets-advanced.css";
import "@univerjs/presets/lib/styles/preset-sheets-conditional-formatting.css";
import "@univerjs/presets/lib/styles/preset-sheets-drawing.css";
import "@univerjs/presets/lib/styles/preset-sheets-filter.css";
import "@univerjs/presets/lib/styles/preset-sheets-sort.css";
import "./style.css";

const { univerAPI } = createUniver({
  locale: LocaleType.EN_US,
  locales: {
    [LocaleType.EN_US]: mergeLocales(
      UniverPresetSheetsCoreEnUS,
      UniverPresetSheetsAdvancedEnUS,
      UniverPresetSheetsDrawingEnUS,
      UniverPresetSheetsFilterEnUS,
      UniverPresetSheetsSortEnUS,
      UniverPresetSheetsConditionalFormattingEnUS
    )
  },
  presets: [
    UniverSheetsCorePreset({
      container: "app",
      header: true,
      toolbar: false,
      formulaBar: false,
      contextMenu: true,

      footer: {
        sheetBar: true,
        statisticBar: true,
        menus: true,
        zoomSlider: true
      }
    }),
    UniverSheetsAdvancedPreset({ license: "" }),
    UniverSheetsDrawingPreset(),
    UniverSheetsFilterPreset(),
    UniverSheetsSortPreset(),
    UniverSheetsConditionalFormattingPreset()
  ]
});

const workbook = univerAPI.createWorkbook({
  id: "workbook-01",
  name: "Spreadsheet Fixture"
});
const worksheet = workbook.getActiveSheet();

const headerStyle = {
  borderColor: "rgb(204, 204, 204)",
  backgroundColor: "rgb(230, 230, 230)"
};

function customizeSpreadsheetHeaders(targetWorksheet: FWorksheet) {
  targetWorksheet.customizeColumnHeader({ headerStyle });
  targetWorksheet.customizeRowHeader({ headerStyle });
  targetWorksheet.refreshCanvas?.();
}

function initializeWorksheet(targetWorksheet: FWorksheet) {
  targetWorksheet.setGridLinesColor("rgb(204, 204, 204)");
  targetWorksheet.setColumnWidths(0, targetWorksheet.getMaxColumns(), 136);

  if (univerAPI.getCurrentLifecycleStage() >= univerAPI.Enum.LifecycleStages.Rendered) {
    customizeSpreadsheetHeaders(targetWorksheet);
  }
}

SpreadsheetRuntimeStore.runtime = {
  workbook,
  defaultWorksheet: worksheet,
  univerAPI,
  initializeWorksheet
};

window.surfgym = { get, set, applyState };
initializeWorksheet(worksheet);

if (univerAPI.getCurrentLifecycleStage() < univerAPI.Enum.LifecycleStages.Rendered) {
  let disposable: { dispose: () => void } | null = null;

  disposable = univerAPI.addEvent(univerAPI.Event.LifeCycleChanged, ({ stage }) => {
    if (stage !== univerAPI.Enum.LifecycleStages.Rendered) return;

    customizeSpreadsheetHeaders(SpreadsheetRuntimeStore.runtime.defaultWorksheet);
    disposable?.dispose();
  });
}

const actions = createSpreadsheetActions({
  univerAPI,
  workbook: workbook as Parameters<typeof createSpreadsheetActions>[0]["workbook"],
  getDefaultWorksheet: () => SpreadsheetRuntimeStore.runtime.defaultWorksheet
});

renderSpreadsheetMockToolbar({
  containerId: "spreadsheet-custom-toolbar",
  univerAPI,
  actions
});

setupSpreadsheetUi({
  univerAPI,
  actions,
  conditionalFormattingCommandId: OpenConditionalFormattingOperator.id
});
