import { LocaleType, mergeLocales, Univer } from "@univerjs/core";
import { FUniver } from "@univerjs/core/facade";
import type { ILocales } from "@univerjs/core";
import {
  OpenConditionalFormattingOperator,
  UniverSheetsConditionalFormattingPreset
} from "@univerjs/preset-sheets-conditional-formatting";
import UniverPresetSheetsConditionalFormattingEnUS from "@univerjs/preset-sheets-conditional-formatting/locales/en-US";
import { UniverSheetsDrawingPreset } from "@univerjs/preset-sheets-drawing";
import UniverPresetSheetsDrawingEnUS from "@univerjs/preset-sheets-drawing/locales/en-US";
import { UniverSheetsFilterPreset } from "@univerjs/preset-sheets-filter";
import UniverPresetSheetsFilterEnUS from "@univerjs/preset-sheets-filter/locales/en-US";
import { UniverSheetsSortPreset } from "@univerjs/preset-sheets-sort";
import UniverPresetSheetsSortEnUS from "@univerjs/preset-sheets-sort/locales/en-US";
import { UniverSheetsCorePreset, type FWorksheet } from "@univerjs/preset-sheets-core";
import UniverPresetSheetsCoreEnUS from "@univerjs/preset-sheets-core/locales/en-US";
import { createSpreadsheetActions } from "./spreadsheet-actions";
import { applyState, get, set } from "./external";
import { _getCellValidationList } from "./internal";
import { SpreadsheetRuntimeStore } from "./runtime";
import { mountTaskScopedLineVisuals } from "./surfgym-line-visuals";
import { installSpreadsheetValidationCommandGuard } from "./spreadsheet-validation-guard";
import { renderSpreadsheetMockToolbar, setupSpreadsheetUi } from "./spreadsheet-ui";

import "@univerjs/preset-sheets-core/lib/index.css";
import "@univerjs/preset-sheets-conditional-formatting/lib/index.css";
import "@univerjs/preset-sheets-drawing/lib/index.css";
import "@univerjs/preset-sheets-filter/lib/index.css";
import "@univerjs/preset-sheets-sort/lib/index.css";
import "./style.css";

const { univerAPI } = createFixtureUniver({
  locale: LocaleType.EN_US,
  locales: {
    [LocaleType.EN_US]: mergeLocales(
      UniverPresetSheetsCoreEnUS,
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
  ]
});
type FixturePreset = {
  plugins: Array<
    | (new (...args: never[]) => unknown)
    | [new (...args: never[]) => unknown, unknown]
  >;
};

function createFixtureUniver(config: {
  locale: LocaleType;
  locales: ILocales;
  presets: FixturePreset[];
}) {
  const univer = new Univer({ locale: config.locale, locales: config.locales });

  for (const preset of config.presets) {
    for (const plugin of preset.plugins) {
      if (Array.isArray(plugin)) {
        univer.registerPlugin(plugin[0] as never, plugin[1] as never);
      } else {
        univer.registerPlugin(plugin as never);
      }
    }
  }

  return { univerAPI: FUniver.newAPI(univer) };
}

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

function waitForSpreadsheetRendered(timeoutMs = 10_000) {
  const renderedStage = univerAPI.Enum.LifecycleStages.Rendered;

  if (univerAPI.getCurrentLifecycleStage() >= renderedStage) {
    return Promise.resolve();
  }

  return new Promise<void>((resolve, reject) => {
    let settled = false;
    let disposable: { dispose: () => void } | null = null;
    let timeoutId: number | null = null;

    const finish = (error?: Error) => {
      if (settled) return;

      settled = true;
      if (timeoutId !== null) window.clearTimeout(timeoutId);
      disposable?.dispose();

      if (error) reject(error);
      else resolve();
    };

    timeoutId = window.setTimeout(() => {
      finish(new Error(`Spreadsheet did not reach Rendered within ${timeoutMs}ms.`));
    }, timeoutMs);

    const registered = univerAPI.addEvent(univerAPI.Event.LifeCycleChanged, ({ stage }: { stage: number }) => {
      if (stage < renderedStage) return;

      finish();
    });

    disposable = registered;

    if (settled) {
      registered.dispose();
    } else if (univerAPI.getCurrentLifecycleStage() >= renderedStage) {
      finish();
    }
  });
}

const rendered = waitForSpreadsheetRendered();
const lineVisualLayoutEvents = new EventTarget();

SpreadsheetRuntimeStore.runtime = {
  workbook,
  defaultWorksheet: worksheet,
  univerAPI,
  rendered,
  initializeWorksheet
};

window.surfgym = { get, set, applyState };
initializeWorksheet(worksheet);

void rendered.then(
  () => {
    customizeSpreadsheetHeaders(SpreadsheetRuntimeStore.runtime.defaultWorksheet);
    const fixtureContainer = document.getElementById("app");
    const gridViewport = fixtureContainer?.querySelector<HTMLElement>("[data-range-selector='true']");
    if (!fixtureContainer || !gridViewport?.querySelector("canvas")) {
      throw new Error("Spreadsheet grid viewport is unavailable.");
    }

    let scrollX = 0;
    let scrollY = 0;
    univerAPI.addEvent(univerAPI.Event.Scroll, (event) => {
      scrollX = event.scrollX;
      scrollY = event.scrollY;
      lineVisualLayoutEvents.dispatchEvent(new Event("scroll"));
    });

    mountTaskScopedLineVisuals({
      container: fixtureContainer,
      readValues: (sheetName, sourceRange) =>
        workbook.getSheetByName(sheetName)?.getRange(sourceRange).getValues() ?? [],
      getActiveSheetName: () => workbook.getActiveSheet().getSheetName(),
      getGridGeometry: () => {
        const viewportRect = gridViewport.getBoundingClientRect();
        const containerRect = fixtureContainer.getBoundingClientRect();
        return {
          originX: viewportRect.left - containerRect.left + 45 - scrollX,
          originY: viewportRect.top - containerRect.top + 20 - scrollY,
          columnWidth: 136,
          rowHeight: 24,
        };
      },
      layoutEvents: lineVisualLayoutEvents,
      onEditChart: (chartId, update) => actions.updateTaskScopedChart(chartId, update),
      onDeleteChart: (chartId) => actions.deleteTaskScopedChart(chartId),
    });
  },
  () => undefined
);

const actions = createSpreadsheetActions({
  univerAPI,
  workbook: workbook as Parameters<typeof createSpreadsheetActions>[0]["workbook"],
  getDefaultWorksheet: () => SpreadsheetRuntimeStore.runtime.defaultWorksheet
});

installSpreadsheetValidationCommandGuard({
  commandEvents: univerAPI,
  validationForCell: (sheetId, row, column) => {
    const validation = _getCellValidationList(sheetId, `${actions.columnIndexToName(column)}${row + 1}`);
    return validation !== null && !Array.isArray(validation) ? validation : null;
  },
  onReject: (message) => {
    window.dispatchEvent(new CustomEvent("surfgym:spreadsheet-input-error", { detail: message }));
  },
});

renderSpreadsheetMockToolbar({
  containerId: "spreadsheet-custom-toolbar",
  univerAPI,
  actions
});

function refreshSpreadsheetNameBox() {
  const selection = actions.getSelectionRangeTarget({ allowSingleRow: true })?.range;
  const start = selection && `${actions.columnIndexToName(selection.startColumn)}${selection.startRow + 1}`;
  const end = selection && `${actions.columnIndexToName(selection.endColumn)}${selection.endRow + 1}`;
  const value = start ? (start === end ? start : `${start}:${end}`) : "A1";
  const valueElement = document.querySelector<HTMLElement>("[data-spreadsheet-name-box-value]");
  if (valueElement) valueElement.textContent = value;
}

refreshSpreadsheetNameBox();
univerAPI.onCommandExecuted(() => {
  refreshSpreadsheetNameBox();
  lineVisualLayoutEvents.dispatchEvent(new Event("active-sheet-change"));
});

setupSpreadsheetUi({
  univerAPI,
  actions,
  conditionalFormattingCommandId: OpenConditionalFormattingOperator.id
});
