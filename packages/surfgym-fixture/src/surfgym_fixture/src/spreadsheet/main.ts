import { createUniver, LocaleType, mergeLocales } from '@univerjs/presets';
import {
  OpenConditionalFormattingOperator,
  UniverSheetsConditionalFormattingPreset,
} from '@univerjs/presets/preset-sheets-conditional-formatting';
import UniverPresetSheetsConditionalFormattingEnUS from '@univerjs/presets/preset-sheets-conditional-formatting/locales/en-US';
import {
  ChartTypeBits,
  UniverLicensePlugin,
  UniverSheetsChartPlugin,
  UniverSheetsChartUIPlugin,
} from '@univerjs/presets/preset-sheets-advanced';
import UniverPresetSheetsAdvancedEnUS from '@univerjs/presets/preset-sheets-advanced/locales/en-US';
import { UniverSheetsDrawingPreset } from '@univerjs/presets/preset-sheets-drawing';
import UniverPresetSheetsDrawingEnUS from '@univerjs/presets/preset-sheets-drawing/locales/en-US';
import { UniverSheetsFilterPreset } from '@univerjs/presets/preset-sheets-filter';
import UniverPresetSheetsFilterEnUS from '@univerjs/presets/preset-sheets-filter/locales/en-US';
import { UniverSheetsSortPreset } from '@univerjs/presets/preset-sheets-sort';
import UniverPresetSheetsSortEnUS from '@univerjs/presets/preset-sheets-sort/locales/en-US';
import { UniverSheetsCorePreset } from '@univerjs/preset-sheets-core';
import UniverPresetSheetsCoreEnUS from '@univerjs/preset-sheets-core/locales/en-US';

import '@univerjs/preset-sheets-core/lib/index.css';
import '@univerjs/presets/lib/styles/preset-sheets-advanced.css';
import '@univerjs/presets/lib/styles/preset-sheets-conditional-formatting.css';
import '@univerjs/presets/lib/styles/preset-sheets-drawing.css';
import '@univerjs/presets/lib/styles/preset-sheets-filter.css';
import '@univerjs/presets/lib/styles/preset-sheets-sort.css';
import './style.css';

const { univerAPI } = createUniver({
  locale: LocaleType.EN_US,
  locales: {
    [LocaleType.EN_US]: mergeLocales(
      UniverPresetSheetsCoreEnUS,
      UniverPresetSheetsAdvancedEnUS,
      UniverPresetSheetsDrawingEnUS,
      UniverPresetSheetsFilterEnUS,
      UniverPresetSheetsSortEnUS,
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
    UniverSheetsDrawingPreset(),
    UniverSheetsFilterPreset(),
    UniverSheetsSortPreset(),
    UniverSheetsConditionalFormattingPreset(),
  ],
  plugins: [
    [UniverLicensePlugin, { license: '' }],
    UniverSheetsChartPlugin,
    UniverSheetsChartUIPlugin,
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
const setZoomRatioCommandId = 'sheet.command.set-zoom-ratio';
const setFilterRangeCommandId = 'sheet.command.set-filter-range';
const removeSheetFilterCommandId = 'sheet.command.remove-sheet-filter';
const markDirtyFilterChangeMutationId = 'sheet.mutation.mark-dirty-filter-change';
const conditionalFormattingCommandId = OpenConditionalFormattingOperator.id;
const headerFilterMenuItemId = 'spreadsheet-header-filter-menu-item';
const startToolbarGroupId = 'spreadsheet-start-toolbar-group';
const startFilterToolbarButtonId = 'spreadsheet-start-filter-toolbar-button';
const startSortToolbarButtonId = 'spreadsheet-start-sort-toolbar-button';
const startBarChartToolbarButtonId = 'spreadsheet-start-bar-chart-toolbar-button';
const startConditionalFormattingToolbarButtonId = 'spreadsheet-start-conditional-formatting-toolbar-button';
const sortDirectionMenuId = 'spreadsheet-sort-direction-menu';
const createConditionalFormattingRuleOperation = 1;
const initialSpreadsheetZoomRatio = 1.8;
const maxInitialSpreadsheetZoomAttempts = 20;
const headerMenuButtonClassName = [
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

function normalizeSelectionRange(
  selectionRange: {
    startRow: number;
    endRow: number;
    startColumn: number;
    endColumn: number;
  },
  maxRow: number,
  maxColumn: number,
) {
  const selectedAllRows = selectionRange.startRow <= 0 && selectionRange.endRow >= maxRow;
  const selectedAllColumns = selectionRange.startColumn <= 0 && selectionRange.endColumn >= maxColumn;

  if (selectedAllRows && !selectedAllColumns) {
    return {
      startRow: 0,
      endRow: maxRow,
      startColumn: Math.max(0, selectionRange.startColumn),
      endColumn: Math.min(maxColumn, selectionRange.endColumn),
    };
  }

  if (selectedAllColumns) {
    const startRow = Math.min(Math.max(selectionRange.startRow, 0), maxRow - 1);

    return {
      startRow,
      endRow: maxRow,
      startColumn: 0,
      endColumn: maxColumn,
    };
  }

  const startRow = Math.min(Math.max(selectionRange.startRow, 0), maxRow);
  const endRow = Math.min(Math.max(selectionRange.endRow, startRow), maxRow);
  const startColumn = Math.min(Math.max(selectionRange.startColumn, 0), maxColumn);
  const endColumn = Math.min(Math.max(selectionRange.endColumn, startColumn), maxColumn);

  return { startRow, endRow, startColumn, endColumn };
}

function getSelectionRangeTarget() {
  const activeTarget = univerAPI.getActiveSheet();
  const targetWorksheet = activeTarget?.worksheet ?? worksheet;
  const selectionRange = targetWorksheet.getSelection()?.getActiveRange()?.getRange();
  const maxRow = targetWorksheet.getMaxRows() - 1;
  const maxColumn = targetWorksheet.getMaxColumns() - 1;

  if (!selectionRange || maxRow < 1 || maxColumn < 0) return null;

  const range = normalizeSelectionRange(selectionRange, maxRow, maxColumn);
  if (range.endRow <= range.startRow || range.endColumn < range.startColumn) return null;

  return {
    range,
    sortColumn: Math.min(Math.max(selectionRange.startColumn, range.startColumn), range.endColumn),
    workbook: activeTarget?.workbook ?? workbook,
    worksheet: targetWorksheet,
  };
}

type SelectionRangeTarget = NonNullable<ReturnType<typeof getSelectionRangeTarget>>;
type SelectionSortTarget = SelectionRangeTarget & {
  sortRange: SelectionRangeTarget['range'];
};

function columnIndexToName(columnIndex: number) {
  let columnNumber = columnIndex + 1;
  let columnName = '';

  while (columnNumber > 0) {
    const remainder = (columnNumber - 1) % 26;
    columnName = String.fromCharCode(65 + remainder) + columnName;
    columnNumber = Math.floor((columnNumber - 1) / 26);
  }

  return columnName;
}

function selectionRangeToA1(range: SelectionRangeTarget['range']) {
  return [
    columnIndexToName(range.startColumn),
    range.startRow + 1,
    ':',
    columnIndexToName(range.endColumn),
    range.endRow + 1,
  ].join('');
}

async function applySelectionFilter(filterTarget: SelectionRangeTarget | null = getSelectionRangeTarget()) {
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

function getSelectionSortTarget(): SelectionSortTarget | null {
  const filterTarget = getSelectionRangeTarget();
  if (!filterTarget) return null;

  const dataStartRow = filterTarget.range.startRow + 1;
  if (dataStartRow > filterTarget.range.endRow) return null;

  return {
    ...filterTarget,
    sortRange: {
      startRow: dataStartRow,
      endRow: filterTarget.range.endRow,
      startColumn: filterTarget.range.startColumn,
      endColumn: filterTarget.range.endColumn,
    },
  };
}

async function applySelectionSort(ascending: boolean) {
  const sortTarget = getSelectionSortTarget();
  if (!sortTarget) return;

  await applySelectionFilter(sortTarget);

  const { sortRange } = sortTarget;
  const rowCount = sortRange.endRow - sortRange.startRow + 1;
  const columnCount = sortRange.endColumn - sortRange.startColumn + 1;
  const sortColumn = sortTarget.sortColumn - sortRange.startColumn;

  sortTarget.worksheet
    .getRange(sortRange.startRow, sortRange.startColumn, rowCount, columnCount)
    .sort({ column: sortColumn, ascending });
}

async function applySelectionBarChart() {
  const chartTarget = getSelectionRangeTarget();
  if (!chartTarget || chartTarget.range.endColumn <= chartTarget.range.startColumn) return;

  const { range } = chartTarget;
  const maxColumn = chartTarget.worksheet.getMaxColumns() - 1;
  const chartColumn = range.endColumn < maxColumn ? range.endColumn + 1 : range.startColumn;
  const chartInfo = chartTarget.worksheet.newChart()
    .setChartType(ChartTypeBits.Bar)
    .addRange(selectionRangeToA1(range))
    .setPosition(range.startRow, chartColumn, 20, 20)
    .setWidth(560)
    .setHeight(360)
    .setOptions('title.content', 'Bar Chart')
    .build();

  await chartTarget.worksheet.insertChart(chartInfo);
}

function closeSortDirectionMenu() {
  document.getElementById(sortDirectionMenuId)?.remove();
  document.removeEventListener('pointerdown', closeSortDirectionMenuOnOutsideClick, true);
}

function closeSortDirectionMenuOnOutsideClick(event: PointerEvent) {
  const menu = document.getElementById(sortDirectionMenuId);
  if (!menu || !(event.target instanceof Node) || menu.contains(event.target)) return;

  closeSortDirectionMenu();
}

function createSortDirectionMenuButton(label: string, ascending: boolean) {
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'spreadsheet-sort-direction-menu-button';
  button.textContent = label;
  button.addEventListener('click', () => {
    void applySelectionSort(ascending);
    closeSortDirectionMenu();
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
  });

  return button;
}

function openSortDirectionMenu(anchor: HTMLElement) {
  closeSortDirectionMenu();

  const menu = document.createElement('div');
  const anchorRect = anchor.getBoundingClientRect();
  const menuWidth = 168;
  const left = Math.max(8, Math.min(anchorRect.left, window.innerWidth - menuWidth - 8));

  menu.id = sortDirectionMenuId;
  menu.className = 'spreadsheet-sort-direction-menu';
  menu.style.left = `${left}px`;
  menu.style.top = `${anchorRect.bottom + 6}px`;
  menu.setAttribute('role', 'menu');
  menu.append(
    createSortDirectionMenuButton('Ascending', true),
    createSortDirectionMenuButton('Descending', false),
  );

  document.body.appendChild(menu);
  window.setTimeout(() => {
    document.addEventListener('pointerdown', closeSortDirectionMenuOnOutsideClick, true);
  }, 0);
}

function createHeaderMenuButton(label: string, onClick: (button: HTMLButtonElement) => void) {
  const button = document.createElement('button');
  button.type = 'button';
  button.className = headerMenuButtonClassName;
  button.textContent = label;
  button.addEventListener('click', (event) => {
    event.preventDefault();
    event.stopPropagation();

    onClick(button);
  });

  return button;
}

function insertHeaderFilterMenuItem() {
  if (!getSelectionRangeTarget()) return;

  document
    .querySelectorAll<HTMLElement>('[data-u-comp="rect-popup"] .univer-min-w-52')
    .forEach((menuPanel) => {
      if (menuPanel.querySelector(`#${headerFilterMenuItemId}`)) return;

      const wrapper = document.createElement('div');
      wrapper.id = headerFilterMenuItemId;
      wrapper.className = 'univer-relative';

      wrapper.append(
        createHeaderMenuButton('Filter', () => {
          void applySelectionFilter();
          document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
        }),
        createHeaderMenuButton('Sort', (button) => {
          openSortDirectionMenu(button);
          document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
        }),
        createHeaderMenuButton('Bar Chart', () => {
          void applySelectionBarChart();
          document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
        }),
      );
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

function createStartToolbarButton(id: string, title: string, icon: string, onClick: (event: MouseEvent) => void) {
  const button = document.createElement('button');
  button.id = id;
  button.type = 'button';
  button.className = 'spreadsheet-start-filter-toolbar-button';
  button.title = title;
  button.setAttribute('aria-label', title);
  button.innerHTML = icon;
  button.addEventListener('click', onClick);

  return button;
}

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

    const filterButton = createStartToolbarButton(
      startFilterToolbarButtonId,
      'Filter',
      `
      <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <path d="M4 5h16l-6 7v5l-4 2v-7L4 5z" />
      </svg>
    `,
      () => {
        void applySelectionFilter();
      },
    );

    const sortButton = createStartToolbarButton(
      startSortToolbarButtonId,
      'Sort',
      `
      <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <path d="M5 7h10v2H5V7zm0 4h8v2H5v-2zm0 4h6v2H5v-2zm12-9v10h2l-3 4-3-4h2V6h2z" />
      </svg>
    `,
      (event) => {
        if (event.currentTarget instanceof HTMLElement) {
          openSortDirectionMenu(event.currentTarget);
        }
      },
    );

    const barChartButton = createStartToolbarButton(
      startBarChartToolbarButtonId,
      'Bar Chart',
      `
      <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <path d="M4 19h16v2H4v-2zM7 9h3v8H7V9zm5-5h3v13h-3V4zm5 8h3v5h-3v-5z" />
      </svg>
    `,
      () => {
        void applySelectionBarChart();
      },
    );

    const conditionalFormattingButton = createStartToolbarButton(
      startConditionalFormattingToolbarButtonId,
      'Conditional Formatting',
      `
      <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <path d="M4 5h16v14H4V5zm2 2v3h5V7H6zm7 0v3h5V7h-5zM6 12v5h5v-5H6zm7 0v5h5v-5h-5z" />
        <path d="M6 12h5v5H6v-5z" />
      </svg>
    `,
      () => {
        void univerAPI.executeCommand(conditionalFormattingCommandId, {
          value: createConditionalFormattingRuleOperation,
        });
      },
    );

    buttonGroup.append(filterButton, sortButton, barChartButton, conditionalFormattingButton);
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

type RowMeta = {
  filtered: boolean;
  visible: boolean;
  rawVisible: boolean;
  filterRange: string | null;
};

type CellMeta = {
  cell: unknown;
  style: unknown;
  row: RowMeta;
};

type SheetMeta = {
  sheet: unknown;
};

type SpreadsheetCellMetaEntry = {
  address: string;
  cell?: unknown;
  style?: unknown;
  row?: Partial<RowMeta>;
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
type FilterModelLike = {
  filteredOutRows: Set<number>;
};
type FilterLike = {
  _filterModel?: FilterModelLike;
  getRange?: () => { getA1Notation: (withSheet?: boolean) => string; getRange: () => SelectionRangeTarget['range'] };
};

function isPlainObject(value: unknown): value is PlainObject {
  return value != null && typeof value === 'object' && !Array.isArray(value);
}

function clonePlainValue<T>(value: T): T {
  if (value == null) return value;
  return JSON.parse(JSON.stringify(value)) as T;
}

function getFilterModel(filter: unknown): FilterModelLike | null {
  if (!isPlainObject(filter)) return null;

  const filterModel = filter._filterModel;
  if (!isPlainObject(filterModel) || !(filterModel.filteredOutRows instanceof Set)) return null;

  return filterModel as FilterModelLike;
}

function getFilterRangeA1(filter: FilterLike | null) {
  return filter?.getRange?.().getA1Notation(false) ?? null;
}

function createFallbackFilterRangeA1(row: number) {
  const maxColumn = Math.max(0, worksheet.getMaxColumns() - 1);
  const maxRow = Math.max(row, worksheet.getMaxRows() - 1);

  return `A1:${columnIndexToName(maxColumn)}${maxRow + 1}`;
}

function getOrCreateFilterForRowMeta(row: number, rowMeta: Partial<RowMeta>): FilterLike | null {
  const currentFilter = worksheet.getFilter();
  if (currentFilter) return currentFilter as unknown as FilterLike;

  const filterRange = typeof rowMeta.filterRange === 'string' && rowMeta.filterRange.trim()
    ? rowMeta.filterRange
    : createFallbackFilterRangeA1(row);

  return worksheet.getRange(filterRange).createFilter() as unknown as FilterLike | null;
}

function markFilterRangeDirty(filter: FilterLike | null) {
  const filterRange = filter?.getRange?.().getRange();
  if (!filterRange) return;

  void univerAPI.executeCommand(markDirtyFilterChangeMutationId, {
    unitId: workbook.getId(),
    subUnitId: worksheet.getSheetId(),
    filterRange,
  });
}

function applyFilteredRowMeta(row: number, rowMeta: Partial<RowMeta>) {
  if (typeof rowMeta.filtered !== 'boolean') return;

  const filter = getOrCreateFilterForRowMeta(row, rowMeta);
  const filterModel = getFilterModel(filter);
  if (!filterModel) return;

  const filteredOutRows = new Set(filterModel.filteredOutRows);

  if (rowMeta.filtered) {
    filteredOutRows.add(row);
  } else {
    filteredOutRows.delete(row);
  }

  filterModel.filteredOutRows = filteredOutRows;
  markFilterRangeDirty(filter);
}

function applyRowMeta(row: number, rowMeta: Partial<RowMeta>) {
  const sheet = worksheet.getSheet();
  const rowData = sheet.getRowManager().getRowOrCreate(row);

  if (typeof rowMeta.rawVisible === 'boolean') {
    rowData.hd = rowMeta.rawVisible ? 0 : 1;
  } else if (typeof rowMeta.visible === 'boolean' && typeof rowMeta.filtered !== 'boolean') {
    rowData.hd = rowMeta.visible ? 0 : 1;
  }

  applyFilteredRowMeta(row, rowMeta);
}

function getCellMeta(address: string): CellMeta {
  const { row, column } = cellNameToPosition(address);
  const range = worksheet.getRange(row, column);
  const sheet = worksheet.getSheet();
  const filter = worksheet.getFilter() as unknown as FilterLike | null;

  return {
    cell: clonePlainValue(range.getCellData()),
    style: clonePlainValue(range.getCellStyleData('cell')),
    row: {
      filtered: sheet.isRowFiltered(row),
      visible: sheet.getRowVisible(row),
      rawVisible: sheet.getRowRawVisible(row),
      filterRange: getFilterRangeA1(filter),
    },
  };
}

function applyCellMeta(entries: SpreadsheetCellMetaEntry[]): CellMeta[] {
  for (const entry of entries) {
    const { row, column } = cellNameToPosition(entry.address);
    const range = worksheet.getRange(row, column);

    if (entry.cell != null && !isPlainObject(entry.cell)) {
      throw new Error(`Invalid cell object for ${entry.address}`);
    }

    if (entry.row != null && !isPlainObject(entry.row)) {
      throw new Error(`Invalid row object for ${entry.address}`);
    }

    const hasCell = Object.prototype.hasOwnProperty.call(entry, 'cell');
    const hasStyle = Object.prototype.hasOwnProperty.call(entry, 'style');

    if (hasCell || hasStyle) {
      const nextCellData = isPlainObject(entry.cell)
        ? clonePlainValue(entry.cell)
        : hasCell
          ? {}
          : clonePlainValue(range.getCellData() ?? {});

      if (!isPlainObject(nextCellData)) {
        throw new Error(`Invalid current cell object for ${entry.address}`);
      }

      if (hasStyle) {
        if (isPlainObject(entry.style)) {
          nextCellData.s = clonePlainValue(entry.style);
        } else {
          delete nextCellData.s;
        }
      }

      range.setValueForCell(nextCellData as SpreadsheetCellValue);
    }

    if (isPlainObject(entry.row)) {
      applyRowMeta(row, entry.row as Partial<RowMeta>);
    }
  }

  return entries.map((entry) => getCellMeta(entry.address));
}

window.getCellMeta = getCellMeta;
window.applyCellMeta = applyCellMeta;
