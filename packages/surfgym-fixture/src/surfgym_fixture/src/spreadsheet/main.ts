import { createUniver, LocaleType, mergeLocales } from '@univerjs/presets';
import {

  OpenConditionalFormattingOperator,
  UniverSheetsConditionalFormattingPreset,
} from '@univerjs/presets/preset-sheets-conditional-formatting';
import UniverPresetSheetsConditionalFormattingEnUS from '@univerjs/presets/preset-sheets-conditional-formatting/locales/en-US';
import { UniverSheetsFilterPreset } from '@univerjs/presets/preset-sheets-filter';
import UniverPresetSheetsFilterEnUS from '@univerjs/presets/preset-sheets-filter/locales/en-US';
import { UniverSheetsCorePreset } from '@univerjs/preset-sheets-core';
import UniverPresetSheetsCoreEnUS from '@univerjs/preset-sheets-core/locales/en-US';

import '@univerjs/preset-sheets-core/lib/index.css';
import '@univerjs/presets/lib/styles/preset-sheets-conditional-formatting.css';
import '@univerjs/presets/lib/styles/preset-sheets-filter.css';
import './style.css';

const { univerAPI } = createUniver({
  locale: LocaleType.EN_US,
  locales: {
    [LocaleType.EN_US]: mergeLocales(
      UniverPresetSheetsCoreEnUS,
      UniverPresetSheetsFilterEnUS,
      UniverPresetSheetsConditionalFormattingEnUS,
    ),
  },
  presets: [
    UniverSheetsCorePreset({
      container: 'app',
      header: true,
      toolbar: true,
      formulaBar: true,
      contextMenu: true,

      footer: {
        sheetBar: true,
        statisticBar: true,
        menus: true,
        zoomSlider: true,
      },
    }),
    UniverSheetsFilterPreset(),
    UniverSheetsConditionalFormattingPreset(),
  ],
});

const workbook = univerAPI.createWorkbook({
  id: 'workbook-01',
  name: 'Spreadsheet Fixture',
});
const worksheet = workbook.getActiveSheet();
worksheet.setRowCount(100);
worksheet.setColumnCount(26);

const fillColorCommandId = 'sheet.command.set-background-color';
const smartToggleFilterCommandId = 'sheet.command.smart-toggle-filter';
const setZoomRatioCommandId = 'sheet.command.set-zoom-ratio';
const setFilterRangeCommandId = 'sheet.command.set-filter-range';
const removeSheetFilterCommandId = 'sheet.command.remove-sheet-filter';
const conditionalFormattingCommandId = OpenConditionalFormattingOperator.id;
const headerFilterMenuItemId = 'spreadsheet-header-filter-menu-item';
const startToolbarGroupId = 'spreadsheet-start-toolbar-group';
const startFilterToolbarButtonId = 'spreadsheet-start-filter-toolbar-button';
const startConditionalFormattingToolbarButtonId = 'spreadsheet-start-conditional-formatting-toolbar-button';
const createConditionalFormattingRuleOperation = 1;
const initialSpreadsheetZoomRatio = 1.8;
const maxInitialSpreadsheetZoomAttempts = 20;
const fillPaletteColors = [
  { label: 'Red', color: 'rgb(255, 0, 0)' },
  { label: 'Orange', color: 'rgb(255, 90, 31)' },
  { label: 'Yellow', color: 'rgb(250, 200, 21)' },
  { label: 'Green', color: 'rgb(13, 164, 113)' },
  { label: 'Blue', color: 'rgb(63, 131, 248)' },
  { label: 'Purple', color: 'rgb(144, 97, 249)' },
] as const;
let shouldFilterNextColorPicker = false;

worksheet.getSheet().getConfig().zoomRatio = initialSpreadsheetZoomRatio;

async function applyInitialSpreadsheetZoom(attempt = 0) {
  const zoomApplied = await univerAPI.executeCommand(setZoomRatioCommandId, {
    unitId: workbook.getId(),
    subUnitId: worksheet.getSheetId(),
    zoomRatio: initialSpreadsheetZoomRatio,
  }).catch(() => false);

  if (!zoomApplied && attempt < maxInitialSpreadsheetZoomAttempts) {
    window.setTimeout(() => {
      void applyInitialSpreadsheetZoom(attempt + 1);
    }, 100);
  }
}

window.setTimeout(() => {
  void applyInitialSpreadsheetZoom();
}, 0);

document.addEventListener(
  'pointerdown',
  (event) => {
    if (!(event.target instanceof Element)) return;

    const commandElement = event.target.closest('[data-u-command]');
    shouldFilterNextColorPicker =
      commandElement instanceof HTMLElement &&
      commandElement.dataset.uCommand === fillColorCommandId;
  },
  true,
);

new MutationObserver(() => {
  if (!shouldFilterNextColorPicker) return;

  let customized = false;

  document.querySelectorAll<HTMLElement>('[data-u-comp="color-picker"]').forEach((picker) => {
    if (picker.dataset.fillPaletteFiltered === 'true') return;

    const presets = picker.querySelector<HTMLElement>('[data-u-comp="color-picker-presets"]');
    if (!presets) return;

    picker.dataset.fillPaletteFiltered = 'true';
    presets.classList.add('spreadsheet-fill-color-palette');
    presets.replaceChildren(
      ...fillPaletteColors.map(({ label, color }) => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'spreadsheet-fill-color-palette-button';
        button.title = label;
        button.setAttribute('aria-label', label);
        button.style.backgroundColor = color;
        button.addEventListener(
          'click',
          (event) => {
            event.preventDefault();
            event.stopImmediatePropagation();

            void univerAPI.executeCommand(fillColorCommandId, { value: color });
            document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
          },
          true,
        );

        return button;
      }),
    );

    Array.from(picker.children).forEach((child) => {
      if (child !== presets && child instanceof HTMLElement) {
        child.style.display = 'none';
      }
    });

    customized = true;
  });

  if (customized) shouldFilterNextColorPicker = false;
}).observe(document.body, { childList: true, subtree: true });

function getHeaderFilterRange() {
  const activeTarget = univerAPI.getActiveSheet();
  const targetWorksheet = activeTarget?.worksheet ?? worksheet;
  const selectionRange = targetWorksheet.getSelection()?.getActiveRange()?.getRange();
  const maxRow = targetWorksheet.getMaxRows() - 1;
  const maxColumn = targetWorksheet.getMaxColumns() - 1;

  if (!selectionRange || maxRow < 1 || maxColumn < 0) return null;

  const selectedAllRows = selectionRange.startRow <= 0 && selectionRange.endRow >= maxRow;
  const selectedAllColumns = selectionRange.startColumn <= 0 && selectionRange.endColumn >= maxColumn;

  if (selectedAllRows && !selectedAllColumns) {
    return {
      range: {
        startRow: 0,
        endRow: maxRow,
        startColumn: selectionRange.startColumn,
        endColumn: selectionRange.endColumn,
      },
      workbook: activeTarget?.workbook ?? workbook,
      worksheet: targetWorksheet,
    };
  }

  if (selectedAllColumns) {
    const startRow = Math.min(selectionRange.startRow, maxRow - 1);

    return {
      range: {
        startRow,
        endRow: maxRow,
        startColumn: 0,
        endColumn: maxColumn,
      },
      workbook: activeTarget?.workbook ?? workbook,
      worksheet: targetWorksheet,
    };
  }

  return null;
}

async function applyHeaderFilter() {
  const filterTarget = getHeaderFilterRange();
  if (!filterTarget) return;

  const commandParams = {
    unitId: filterTarget.workbook.getId(),
    subUnitId: filterTarget.worksheet.getSheetId(),
  };

  await univerAPI.executeCommand(removeSheetFilterCommandId, commandParams).catch(() => false);
  await univerAPI.executeCommand(setFilterRangeCommandId, {
    ...commandParams,
    range: filterTarget.range,
  });
}

function insertHeaderFilterMenuItem() {
  if (!getHeaderFilterRange()) return;

  document
    .querySelectorAll<HTMLElement>('[data-u-comp="rect-popup"] .univer-min-w-52')
    .forEach((menuPanel) => {
      if (menuPanel.querySelector(`#${headerFilterMenuItemId}`)) return;

      const wrapper = document.createElement('div');
      wrapper.id = headerFilterMenuItemId;
      wrapper.className = 'univer-relative';

      const button = document.createElement('button');
      button.type = 'button';
      button.className = [
        'univer-relative',
        'univer-flex',
        'univer-min-h-8',
        'univer-w-full',
        'univer-items-center',
        'univer-justify-between',
        'univer-gap-3',
        'univer-rounded-md',
        'univer-border-none',
        'univer-bg-transparent',
        'univer-px-2',
        'univer-text-left',
        'univer-text-sm',
        'univer-cursor-pointer',
        'hover:univer-bg-gray-50',
        'dark:hover:!univer-bg-gray-600',
      ].join(' ');
      button.textContent = 'Filter';
      button.addEventListener('click', (event) => {
        event.preventDefault();
        event.stopPropagation();

        void applyHeaderFilter();
        document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
      });

      wrapper.appendChild(button);
      menuPanel.appendChild(wrapper);
    });
}

document.addEventListener(
  'contextmenu',
  () => {
    window.setTimeout(insertHeaderFilterMenuItem, 0);
    window.setTimeout(insertHeaderFilterMenuItem, 50);
  },
  true,
);

new MutationObserver(insertHeaderFilterMenuItem).observe(document.body, {
  childList: true,
  subtree: true,
});

function insertStartToolbarButtons() {
  document.querySelectorAll<HTMLElement>('[data-u-comp="ribbon-toolbar"]').forEach((toolbar) => {
    const existingButtonGroup = toolbar.querySelector(`#${startToolbarGroupId}`);

    if (toolbar.getAttribute('aria-label') !== 'Start') {
      existingButtonGroup?.remove();
      return;
    }

    if (existingButtonGroup) return;

    const buttonGroup = document.createElement('div');
    buttonGroup.id = startToolbarGroupId;
    buttonGroup.className = 'spreadsheet-start-filter-toolbar-group';

    const filterButton = document.createElement('button');
    filterButton.id = startFilterToolbarButtonId;
    filterButton.type = 'button';
    filterButton.className = 'spreadsheet-start-filter-toolbar-button';
    filterButton.title = 'Toggle Filter';
    filterButton.setAttribute('aria-label', 'Toggle Filter');
    filterButton.innerHTML = `
      <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <path d="M4 5h16l-6 7v5l-4 2v-7L4 5z" />
      </svg>
    `;
    filterButton.addEventListener('click', () => {
      void univerAPI.executeCommand(smartToggleFilterCommandId);
    });

    const conditionalFormattingButton = document.createElement('button');
    conditionalFormattingButton.id = startConditionalFormattingToolbarButtonId;
    conditionalFormattingButton.type = 'button';
    conditionalFormattingButton.className = 'spreadsheet-start-filter-toolbar-button';
    conditionalFormattingButton.title = 'Conditional Formatting';
    conditionalFormattingButton.setAttribute('aria-label', 'Conditional Formatting');
    conditionalFormattingButton.innerHTML = `
      <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <path d="M4 5h16v14H4V5zm2 2v3h5V7H6zm7 0v3h5V7h-5zM6 12v5h5v-5H6zm7 0v5h5v-5h-5z" />
        <path d="M6 12h5v5H6v-5z" />
      </svg>
    `;
    conditionalFormattingButton.addEventListener('click', () => {
      void univerAPI.executeCommand(conditionalFormattingCommandId, {
        value: createConditionalFormattingRuleOperation,
      });
    });

    buttonGroup.append(filterButton, conditionalFormattingButton);
    toolbar.appendChild(buttonGroup);
  });
}

new MutationObserver(insertStartToolbarButtons).observe(document.body, {
  childList: true,
  subtree: true,
});
window.setTimeout(insertStartToolbarButtons, 0);

// ##################################
// #      Helper for evalution      #
// ##################################

type CellMeta = {
  cell: unknown;
  style: unknown;
};

type SheetMeta = {
  sheet: unknown;
};

type SpreadsheetCellMetaEntry = CellMeta & {
  address: string;
};

declare global {
  interface Window {
    getCellMeta: (address: string) => CellMeta;
    getSheetMeta: () => SheetMeta;
    applyCellMeta: (entries: SpreadsheetCellMetaEntry[]) => CellMeta[];
  }
}

function columnNameToIndex(columnName: string) {
  return columnName
    .toUpperCase()
    .split('')
    .reduce((sum, char) => sum * 26 + char.charCodeAt(0) - 64, 0) - 1;
}

function cellNameToPosition(address: string) {
  const match = address.trim().match(/^\$?([A-Z]+)\$?(\d+)$/i);
  if (!match) {
    throw new Error(`Invalid cell address: ${address}`);
  }

  const [, columnName, rowName] = match;

  if (!columnName || !rowName) {
    throw new Error(`Invalid cell address: ${address}`);
  }

  const column = columnNameToIndex(columnName);
  const row = Number(rowName) - 1;

  return { row, column };
}

type PlainObject = Record<string, unknown>;
type SpreadsheetRange = ReturnType<typeof worksheet.getRange>;
type SpreadsheetCellValue = Parameters<SpreadsheetRange['setValueForCell']>[0];

function isPlainObject(value: unknown): value is PlainObject {
  return value != null && typeof value === 'object' && !Array.isArray(value);
}

function clonePlainValue<T>(value: T): T {
  if (value == null) return value;
  return JSON.parse(JSON.stringify(value)) as T;
}

function getCellMeta(address: string): CellMeta {
  const { row, column } = cellNameToPosition(address);
  const range = worksheet.getRange(row, column);

  return {
    cell: clonePlainValue(range.getCellData()),
    style: clonePlainValue(range.getCellStyleData('cell')),
  };
}


function applyCellMeta(entries: SpreadsheetCellMetaEntry[]): CellMeta[] {
  for (const entry of entries) {
    const { row, column } = cellNameToPosition(entry.address);
    const range = worksheet.getRange(row, column);

    if (entry.cell != null && !isPlainObject(entry.cell)) {
      throw new Error(`Invalid cell object for ${entry.address}`);
    }

    const nextCellData = isPlainObject(entry.cell)
      ? clonePlainValue(entry.cell)
      : {};

    if (isPlainObject(entry.style)) {
      nextCellData.s = clonePlainValue(entry.style);
    } else {
      delete nextCellData.s;
    }

    range.setValueForCell(nextCellData as SpreadsheetCellValue);
  }

  return entries.map((entry) => getCellMeta(entry.address));
}

window.getCellMeta = getCellMeta;
window.applyCellMeta = applyCellMeta;
