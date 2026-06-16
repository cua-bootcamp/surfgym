import { createUniver, LocaleType, mergeLocales } from "@univerjs/presets";
import {
  OpenConditionalFormattingOperator,
  UniverSheetsConditionalFormattingPreset
} from "@univerjs/presets/preset-sheets-conditional-formatting";
import UniverPresetSheetsConditionalFormattingEnUS from "@univerjs/presets/preset-sheets-conditional-formatting/locales/en-US";
import {
  UniverLicensePlugin,
  UniverSheetsChartPlugin,
  UniverSheetsChartUIPlugin
} from "@univerjs/presets/preset-sheets-advanced";
import UniverPresetSheetsAdvancedEnUS from "@univerjs/presets/preset-sheets-advanced/locales/en-US";
import { UniverSheetsDrawingPreset } from "@univerjs/presets/preset-sheets-drawing";
import UniverPresetSheetsDrawingEnUS from "@univerjs/presets/preset-sheets-drawing/locales/en-US";
import { UniverSheetsFilterPreset } from "@univerjs/presets/preset-sheets-filter";
import UniverPresetSheetsFilterEnUS from "@univerjs/presets/preset-sheets-filter/locales/en-US";
import { UniverSheetsSortPreset } from "@univerjs/presets/preset-sheets-sort";
import UniverPresetSheetsSortEnUS from "@univerjs/presets/preset-sheets-sort/locales/en-US";
import { UniverSheetsCorePreset } from "@univerjs/preset-sheets-core";
import UniverPresetSheetsCoreEnUS from "@univerjs/preset-sheets-core/locales/en-US";
import { createSpreadsheetActions } from "./spreadsheet-actions";
import { get, set } from "./external";
import { SpreadsheetRuntimeStore } from "./internal";
import type { SpreadsheetRuntime } from "./type";
// import { installSpreadsheetEvaluationHelpers } from "./spreadsheet-evaluation";
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
    UniverSheetsDrawingPreset(),
    UniverSheetsFilterPreset(),
    UniverSheetsSortPreset(),
    UniverSheetsConditionalFormattingPreset()
  ],
  plugins: [
    [UniverLicensePlugin, { license: "" }],
    UniverSheetsChartPlugin,
    UniverSheetsChartUIPlugin
  ]
});

const workbook = univerAPI.createWorkbook({
  id: "workbook-01",
  name: "Spreadsheet Fixture"
});
const worksheet = workbook.getActiveSheet();

SpreadsheetRuntimeStore.runtime = {
  workbook,
  defaultWorksheet: worksheet
} as SpreadsheetRuntime;

window.surfgym = {
  get,
  set
};

worksheet.setGridLinesColor("rgb(204, 204, 204)");
worksheet.setColumnWidths(0, worksheet.getMaxColumns(), 136); // 전체 컬럼 폭: 136px
worksheet.setRowHeights(0, worksheet.getMaxRows(), 24); // 전체 행 높이: 32px

const headerStyle = {
  borderColor: "rgb(204, 204, 204)",
  backgroundColor: "rgb(230, 230, 230)"
};

function customizeSpreadsheetHeaders() {
  worksheet.customizeColumnHeader({ headerStyle });
  worksheet.customizeRowHeader({ headerStyle });
  worksheet.refreshCanvas?.();
}

if (univerAPI.getCurrentLifecycleStage() >= univerAPI.Enum.LifecycleStages.Rendered) {
  customizeSpreadsheetHeaders();
} else {
  let disposable: { dispose: () => void } | null = null;

  disposable = univerAPI.addEvent(univerAPI.Event.LifeCycleChanged, ({ stage }) => {
    if (stage !== univerAPI.Enum.LifecycleStages.Rendered) return;

    customizeSpreadsheetHeaders();
    disposable?.dispose();
  });
}

const actions = createSpreadsheetActions({
  univerAPI,
  workbook: workbook as Parameters<typeof createSpreadsheetActions>[0]["workbook"],
  worksheet
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

// installSpreadsheetEvaluationHelpers({
//   univerAPI,
//   workbook: workbook as Parameters<typeof installSpreadsheetEvaluationHelpers>[0]["workbook"],
//   worksheet,
//   actions
// });
