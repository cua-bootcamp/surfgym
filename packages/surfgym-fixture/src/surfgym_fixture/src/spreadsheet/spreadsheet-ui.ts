import { ChartTypeBits } from '@univerjs/presets/preset-sheets-advanced';
import type {
  ChartWizardConfig,
  PivotTableDataFieldConfig,
  PivotTableDataFunction,
  PivotTableFieldInfo,
  PivotTableLayoutConfig,
  PivotTableSourceInfo,
  SpreadsheetActions,
} from './spreadsheet-actions';

const fillColorCommandId = 'sheet.command.set-background-color';
const textColorCommandId = 'sheet.command.set-range-text-color';
const headerFilterMenuItemId = 'spreadsheet-header-filter-menu-item';
const startToolbarGroupId = 'spreadsheet-start-toolbar-group';
const startFilterToolbarButtonId = 'spreadsheet-start-filter-toolbar-button';
const startSortToolbarButtonId = 'spreadsheet-start-sort-toolbar-button';
const startBarChartToolbarButtonId = 'spreadsheet-start-bar-chart-toolbar-button';
const startSparklineToolbarButtonId = 'spreadsheet-start-sparkline-toolbar-button';
const startPivotTableToolbarButtonId = 'spreadsheet-start-pivot-table-toolbar-button';
const startConditionalFormattingToolbarButtonId = 'spreadsheet-start-conditional-formatting-toolbar-button';
const formattingSidebarRailId = 'spreadsheet-formatting-sidebar-rail';
const formattingSidebarButtonId = 'spreadsheet-formatting-sidebar-button';
const mockColorPaletteMenuId = 'spreadsheet-mock-color-palette-menu';
const mockNativeColorInputClassName = 'spreadsheet-mock-native-color-input';
const filterHeaderDialogId = 'spreadsheet-filter-header-dialog';
const chartWizardDialogId = 'spreadsheet-chart-wizard-dialog';
const pivotSourceDialogId = 'spreadsheet-pivot-source-dialog';
const pivotLayoutDialogId = 'spreadsheet-pivot-layout-dialog';
const pivotDataFieldDialogId = 'spreadsheet-pivot-data-field-dialog';
const sortDirectionMenuId = 'spreadsheet-sort-direction-menu';
const createConditionalFormattingRuleOperation = 1;
const openNumberFormatPanelCommandId = 'sheet.operation.open.numfmt.panel';
const openSparklineSelectorOperationId = 'sheet.operation.open-sparkline-selector';
const mergeCellsCommandId = 'sheet.command.add-worksheet-merge-all';
const unmergeCellsCommandId = 'sheet.command.remove-worksheet-merge';
const mergeCellsContextMenuItemId = 'surfgym.context-menu.merge-cells';
const unmergeCellsContextMenuItemId = 'surfgym.context-menu.unmerge-cells';
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

type MockToolbarItem = {
  label: string;
  icon: string;
  chart?: boolean;
  filter?: boolean;
  pivotTable?: boolean;
  sparkline?: boolean;
  sortAscending?: boolean;
};

type MockFormattingItem = {
  label: string;
  title: string;
  action?: 'dateFormat' | 'mergeCells' | 'numberFormat' | 'percentFormat' | 'unmergeCells';
  commandId?: string;
  colorCommandId?: string;
  icon?: string;
};

type SpreadsheetMockToolbarApi = {
  executeCommand: <P extends object = object, R = boolean>(id: string, params?: P) => Promise<R>;
};

type SpreadsheetMockToolbarOptions = {
  containerId: string;
  univerAPI?: SpreadsheetMockToolbarApi;
  actions?: Pick<
    SpreadsheetActions,
    | 'applySelectionDateFormat'
    | 'applySelectionFilter'
    | 'applySelectionChart'
    | 'applySelectionFontFamily'
    | 'applySelectionFontSize'
    | 'applySelectionHeaderlessFilter'
    | 'applySelectionInputValue'
    | 'applySelectionMerge'
    | 'applySelectionNumberFormat'
    | 'applySelectionPercentFormat'
    | 'applySelectionPivotTable'
    | 'applySelectionSort'
    | 'applySelectionUnmerge'
    | 'columnIndexToName'
    | 'getSelectionPivotSource'
    | 'getSelectionRangeTarget'
  >;
};

type FilterHeaderPreference = 'unknown' | 'use-first-line' | 'headerless';
type FilterActions = Pick<SpreadsheetActions, 'applySelectionFilter' | 'applySelectionHeaderlessFilter' | 'getSelectionRangeTarget'>;
type ChartWizardActions = Pick<SpreadsheetActions, 'applySelectionChart' | 'columnIndexToName' | 'getSelectionRangeTarget'>;
type PivotTableActions = Pick<SpreadsheetActions, 'applySelectionPivotTable' | 'getSelectionPivotSource'>;

const formatCommandIds = {
  bold: 'sheet.command.set-range-bold',
  italic: 'sheet.command.set-range-italic',
  underline: 'sheet.command.set-range-underline',
} as const;

const mockFontFamilyOptions = ['나눔고딕', 'Arial', 'Calibri', 'Times New Roman', 'Courier New', 'Verdana'] as const;
const mockFontSizeOptions = [8, 9, 10, 11, 12, 14, 16, 18, 20, 24, 28, 32, 36] as const;

const standardPaletteColors = [
  '#000000', '#1f1f1f', '#3f3f3f', '#5f5f5f', '#7f7f7f', '#9f9f9f', '#bfbfbf', '#dfdfdf', '#ffffff', '#d9e2f3', '#d9ead3', '#fff2cc',
  '#ffff00', '#ff9900', '#ff6600', '#ff0000', '#cc0000', '#99004d', '#660099', '#333399', '#006666', '#008000', '#00b050', '#92d050',
  '#ffff99', '#ffe599', '#f9cb9c', '#f4cccc', '#ead1dc', '#d9d2e9', '#c9daf8', '#cfe2f3', '#d0e0e3', '#d9ead3', '#e2f0cb', '#f4cccc',
  '#ffff66', '#ffd966', '#f6b26b', '#ea9999', '#d5a6bd', '#b4a7d6', '#a4c2f4', '#9fc5e8', '#a2c4c9', '#b6d7a8', '#d9ead3', '#d9ead3',
  '#ffff00', '#f1c232', '#e69138', '#e06666', '#c27ba0', '#8e7cc3', '#6d9eeb', '#6fa8dc', '#76a5af', '#93c47d', '#b6d7a8', '#b6d7a8',
  '#b6d7a8', '#bf9000', '#b45f06', '#cc0000', '#a64d79', '#674ea7', '#3c78d8', '#3d85c6', '#45818e', '#6aa84f', '#38761d', '#38761d',
  '#7f6000', '#783f04', '#85200c', '#990000', '#741b47', '#351c75', '#1c4587', '#073763', '#134f5c', '#274e13', '#274e13', '#274e13',
  '#4c3900', '#3d2500', '#5b0f00', '#660000', '#4c1130', '#20124d', '#0b1f3a', '#0c343d', '#0c343d', '#1b3310', '#1b3310', '#1b3310',
] as const;

type ChartWizardStep = 0 | 1 | 2 | 3;
type ChartWizardDataOrientation = NonNullable<ChartWizardConfig['dataOrientation']>;
type ChartWizardLegendPosition = NonNullable<ChartWizardConfig['legendPosition']>;
type ChartWizardIconKind =
  | 'area'
  | 'bar'
  | 'bubble'
  | 'column'
  | 'combination'
  | 'funnel'
  | 'heatmap'
  | 'line'
  | 'other'
  | 'pie'
  | 'radar'
  | 'scatter';

type ChartWizardSubtype = {
  label: string;
  chartType: ChartTypeBits;
  icon: ChartWizardIconKind;
};

type ChartWizardTypeGroup = {
  key: string;
  label: string;
  icon: ChartWizardIconKind;
  subtypes: readonly ChartWizardSubtype[];
};

const chartWizardSteps = ['Chart Type', 'Data Range', 'Data Series', 'Chart Elements'] as const;

const chartWizardTypeGroups: readonly ChartWizardTypeGroup[] = [
  {
    key: 'column',
    label: 'Column',
    icon: 'column',
    subtypes: [
      { label: 'Normal Column', chartType: ChartTypeBits.Column, icon: 'column' },
      { label: 'Stacked Column', chartType: ChartTypeBits.ColumnStacked, icon: 'column' },
      { label: 'Percent Stacked Column', chartType: ChartTypeBits.ColumnPercentStacked, icon: 'column' },
    ],
  },
  {
    key: 'bar',
    label: 'Bar',
    icon: 'bar',
    subtypes: [
      { label: 'Normal Bar', chartType: ChartTypeBits.Bar, icon: 'bar' },
      { label: 'Stacked Bar', chartType: ChartTypeBits.BarStacked, icon: 'bar' },
      { label: 'Percent Stacked Bar', chartType: ChartTypeBits.BarPercentStacked, icon: 'bar' },
    ],
  },
  {
    key: 'pie',
    label: 'Pie',
    icon: 'pie',
    subtypes: [
      { label: 'Pie', chartType: ChartTypeBits.Pie, icon: 'pie' },
      { label: 'Doughnut', chartType: ChartTypeBits.Doughnut, icon: 'pie' },
    ],
  },
  {
    key: 'area',
    label: 'Area',
    icon: 'area',
    subtypes: [
      { label: 'Area', chartType: ChartTypeBits.Area, icon: 'area' },
      { label: 'Stacked Area', chartType: ChartTypeBits.AreaStacked, icon: 'area' },
      { label: 'Percent Stacked Area', chartType: ChartTypeBits.AreaPercentStacked, icon: 'area' },
    ],
  },
  {
    key: 'line',
    label: 'Line',
    icon: 'line',
    subtypes: [
      { label: 'Line', chartType: ChartTypeBits.Line, icon: 'line' },
    ],
  },
  {
    key: 'scatter',
    label: 'XY (Scatter)',
    icon: 'scatter',
    subtypes: [
      { label: 'Scatter', chartType: ChartTypeBits.Scatter, icon: 'scatter' },
    ],
  },
  {
    key: 'bubble',
    label: 'Bubble',
    icon: 'bubble',
    subtypes: [
      { label: 'Bubble', chartType: ChartTypeBits.Bubble, icon: 'bubble' },
    ],
  },
  {
    key: 'radar',
    label: 'Net',
    icon: 'radar',
    subtypes: [
      { label: 'Radar', chartType: ChartTypeBits.Radar, icon: 'radar' },
    ],
  },
  {
    key: 'combination',
    label: 'Column and Line',
    icon: 'combination',
    subtypes: [
      { label: 'Column and Line', chartType: ChartTypeBits.Combination, icon: 'combination' },
    ],
  },
  {
    key: 'advanced',
    label: 'More',
    icon: 'other',
    subtypes: [
      { label: 'Waterfall', chartType: ChartTypeBits.Waterfall, icon: 'column' },
      { label: 'Pareto', chartType: ChartTypeBits.Pareto, icon: 'combination' },
      { label: 'Funnel', chartType: ChartTypeBits.Funnel, icon: 'funnel' },
      { label: 'Heatmap', chartType: ChartTypeBits.Heatmap, icon: 'heatmap' },
      { label: 'Boxplot', chartType: ChartTypeBits.Boxplot, icon: 'other' },
      { label: 'Word Cloud', chartType: ChartTypeBits.WordCloud, icon: 'other' },
      { label: 'Sankey', chartType: ChartTypeBits.Sankey, icon: 'other' },
      { label: 'Relation', chartType: ChartTypeBits.Relation, icon: 'other' },
    ],
  },
] as const;

let filterHeaderPreference: FilterHeaderPreference = 'unknown';

const mockToolbarIcon = {
  alignLeft: `
    <svg class="spreadsheet-mock-align-icon" viewBox="0 0 24 24" aria-hidden="true">
      <path fill="currentColor" d="M4 5h16v2H4zm0 4h11v2H4zm0 4h16v2H4zm0 4h11v2H4z" />
    </svg>
  `,
  alignCenter: `
    <svg class="spreadsheet-mock-align-icon" viewBox="0 0 24 24" aria-hidden="true">
      <path fill="currentColor" d="M4 5h16v2H4zm3 4h10v2H7zm-3 4h16v2H4zm3 4h10v2H7z" />
    </svg>
  `,
  alignRight: `
    <svg class="spreadsheet-mock-align-icon" viewBox="0 0 24 24" aria-hidden="true">
      <path fill="currentColor" d="M4 5h16v2H4zm5 4h11v2H9zm-5 4h16v2H4zm5 4h11v2H9z" />
    </svg>
  `,
  alignTop: `
    <svg class="spreadsheet-mock-vertical-align-icon" viewBox="0 0 24 24" aria-hidden="true">
      <path fill="currentColor" d="M5 4h14v2H5zm3 4h8v2H8zm0 4h8v2H8zm0 4h8v2H8z" />
    </svg>
  `,
  alignMiddle: `
    <svg class="spreadsheet-mock-vertical-align-icon" viewBox="0 0 24 24" aria-hidden="true">
      <path fill="currentColor" d="M5 4h14v2H5zm2 5h10v2H7zm0 4h10v2H7zm-2 5h14v2H5z" />
    </svg>
  `,
  alignBottom: `
    <svg class="spreadsheet-mock-vertical-align-icon" viewBox="0 0 24 24" aria-hidden="true">
      <path fill="currentColor" d="M8 6h8v2H8zm0 4h8v2H8zm0 4h8v2H8zm-3 4h14v2H5z" />
    </svg>
  `,
  mergeCells: `
    <svg class="spreadsheet-mock-merge-icon" viewBox="0 0 24 24" aria-hidden="true">
      <rect x="3.5" y="5.5" width="17" height="13" rx=".8" fill="none" stroke="currentColor" stroke-width="1.4" />
      <path d="M12 5.5v13" stroke="#8f98a3" stroke-width="1.2" stroke-dasharray="2 1.5" />
      <path d="M5.5 12H10m0 0-2-2m2 2-2 2" fill="none" stroke="#2e6eea" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
      <path d="M18.5 12H14m0 0 2-2m-2 2 2 2" fill="none" stroke="#2e6eea" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
    </svg>
  `,
  unmergeCells: `
    <svg class="spreadsheet-mock-merge-icon" viewBox="0 0 24 24" aria-hidden="true">
      <rect x="3.5" y="5.5" width="17" height="13" rx=".8" fill="none" stroke="currentColor" stroke-width="1.4" />
      <path d="M12 5.5v13" stroke="#2e6eea" stroke-width="1.4" stroke-dasharray="2 1.5" />
      <path d="M10 12H5.5m0 0 2-2m-2 2 2 2" fill="none" stroke="#2e6eea" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
      <path d="M14 12h4.5m0 0-2-2m2 2-2 2" fill="none" stroke="#2e6eea" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
    </svg>
  `,
  fillBucket: `
    <svg class="spreadsheet-mock-fill-icon" viewBox="0 0 24 24" aria-hidden="true" fill="none">
      <path d="m6.5 11.5 6-6 7 7-6 6h-7z" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" />
      <path d="M9 9 16 16" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
      <path d="M4 20h16" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
      <path d="M19 14.7c1 1.2 1.6 2.1 1.6 2.9a1.6 1.6 0 0 1-3.2 0c0-.8.6-1.7 1.6-2.9z" fill="currentColor" />
    </svg>
  `,
  date: `
    <svg class="spreadsheet-mock-date-icon" viewBox="0 0 24 24" aria-hidden="true">
      <rect x="5" y="4" width="14" height="16" rx="1.4" fill="#f8f8f8" stroke="#8f98a3" stroke-width="1.4" />
      <path d="M5 8h14" stroke="#8f98a3" stroke-width="1.4" />
      <path d="M8.5 3v3M15.5 3v3" stroke="#6f7782" stroke-width="1.5" stroke-linecap="round" />
      <text x="12" y="17" fill="#333" font-family="Arial, sans-serif" font-size="10" font-weight="700" text-anchor="middle">7</text>
    </svg>
  `,
  decimalDecrease: `
    <svg class="spreadsheet-mock-decimal-icon" viewBox="0 0 24 24" aria-hidden="true">
      <text x="3" y="10" fill="currentColor" font-family="Arial, sans-serif" font-size="8" font-weight="700">.00</text>
      <text x="3" y="19" fill="currentColor" font-family="Arial, sans-serif" font-size="8" font-weight="700">.0</text>
      <path d="M19 5v14" stroke="#2e6eea" stroke-width="2" stroke-linecap="round" />
      <path d="m15.5 8.5 3.5-3.5 3.5 3.5" fill="none" stroke="#2e6eea" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
    </svg>
  `,
  decimalIncrease: `
    <svg class="spreadsheet-mock-decimal-icon" viewBox="0 0 24 24" aria-hidden="true">
      <text x="3" y="10" fill="currentColor" font-family="Arial, sans-serif" font-size="8" font-weight="700">.0</text>
      <text x="3" y="19" fill="currentColor" font-family="Arial, sans-serif" font-size="8" font-weight="700">.00</text>
      <path d="M19 5v14" stroke="#2e6eea" stroke-width="2" stroke-linecap="round" />
      <path d="m15.5 15.5 3.5 3.5 3.5-3.5" fill="none" stroke="#2e6eea" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
    </svg>
  `,
  indentDecrease: `
    <svg class="spreadsheet-mock-indent-icon" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M11 6h10M11 11h10M11 16h10" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
      <path d="m8 8-4 4 4 4" fill="none" stroke="#2e6eea" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
    </svg>
  `,
  indentIncrease: `
    <svg class="spreadsheet-mock-indent-icon" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 6h16M11 11h9M11 16h9" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
      <path d="m5 8 4 4-4 4" fill="none" stroke="#2e6eea" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
    </svg>
  `,
  border: `
    <svg class="spreadsheet-mock-border-icon" viewBox="0 0 24 24" aria-hidden="true">
      <rect x="5" y="5" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.8" />
      <path d="M12 5v14M5 12h14" stroke="#8f98a3" stroke-width="1.3" />
      <path d="M5 5h14v14H5z" fill="none" stroke="#2e6eea" stroke-width="1.2" stroke-dasharray="2 1.5" />
    </svg>
  `,
  wrap: `
    <svg class="spreadsheet-mock-wrap-icon" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 6h16M4 10h11a4 4 0 0 1 0 8h-3" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
      <path d="m13 15-3 3 3 3" fill="none" stroke="#2e6eea" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
    </svg>
  `,
  textDirection: `
    <svg class="spreadsheet-mock-direction-icon" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M5 5h9M5 10h13M5 15h9" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
      <path d="m16 6 4 4-4 4" fill="none" stroke="#2e6eea" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
      <path d="M5 20h13" stroke="#8f98a3" stroke-width="2" stroke-linecap="round" />
    </svg>
  `,
  spreadsheet: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path fill="#eef8ef" stroke="#4b9b56" d="M5 2.5h10.5L20 7v15.5H5z" />
      <path fill="#d8efe0" d="M15 2.5V7h4.5z" />
      <path fill="#4b9b56" d="M7 10h10v8H7zm1.5 1.5v1.5h2V11.5zm3.5 0v1.5h2V11.5zm3.5 0v1.5H17V11.5zM8.5 14.5V16h2v-1.5zm3.5 0V16h2v-1.5zm3.5 0V16H17v-1.5z" />
    </svg>
  `,
  folder: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path fill="#4b9dda" d="M2.5 6.5h7l2 2h10v11H2.5z" />
      <path fill="#73b7e7" d="M2.5 8.5h19l-1.6 11H4.1z" />
    </svg>
  `,
  save: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path fill="#505b6f" d="M4 3h15l2 2v18H4z" />
      <path fill="#dce5f3" d="M7 4.5h10v6H7z" />
      <path fill="#f6f6f6" d="M7 15h11v6H7z" />
      <circle cx="18.2" cy="18.8" r="2.2" fill="#d73535" />
    </svg>
  `,
  pdf: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path fill="#f8f8f8" stroke="#9aa1aa" d="M6 2.5h9l4 4V22H6z" />
      <path fill="#e9edf5" d="M15 2.5V7h4z" />
      <path fill="#d33" d="M5 16.5c4.4-.7 7.6-2.4 10.4-6.8 1.3 3 2.6 4.7 4.6 5.8-3.4-.5-6.1-.4-10.4 1.3z" />
    </svg>
  `,
  print: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path fill="#d6d9de" d="M7 3h10v5H7z" />
      <path fill="#586170" d="M5 8h14a2 2 0 0 1 2 2v7H3v-7a2 2 0 0 1 2-2z" />
      <path fill="#f8f8f8" d="M7 14h10v7H7z" />
      <path fill="#70a7e8" d="M8 4h8v2H8z" />
    </svg>
  `,
  search: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path fill="#f8f8f8" stroke="#9aa1aa" d="M6 2.5h9l4 4V22H6z" />
      <circle cx="12" cy="12" r="4" fill="none" stroke="#2f70d8" stroke-width="2" />
      <path stroke="#2f70d8" stroke-linecap="round" stroke-width="2" d="m15 15 4 4" />
    </svg>
  `,
  cut: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="7" cy="18" r="3" fill="none" stroke="#6f7782" stroke-width="2" />
      <circle cx="17" cy="18" r="3" fill="none" stroke="#6f7782" stroke-width="2" />
      <path fill="none" stroke="#6f7782" stroke-linecap="round" stroke-width="2" d="M9 16 18 4M15 14 6 4" />
    </svg>
  `,
  copy: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path fill="#f5f5f5" stroke="#8c949f" d="M8 3h9l4 4v12H8z" />
      <path fill="#e9edf5" d="M17 3v5h4z" />
      <path fill="#fff" stroke="#8c949f" d="M4 7h10l3 3v12H4z" />
    </svg>
  `,
  paste: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path fill="#b5b7bb" d="M8 4h8l1 3H7z" />
      <path fill="#a8aaaf" d="M5 6h14v16H5z" />
      <path fill="#f4f5f7" d="M8 10h8v9H8z" />
    </svg>
  `,
  brush: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path fill="#4e6fb9" d="M15.2 3 21 8.8 10.8 19.1 5 13.2z" />
      <path fill="#f0b24b" d="m4.2 14.2 5.6 5.6c-2.4 1.3-5.4 1.7-7.5.9 1.3-1.4 1.6-3.8 1.9-6.5z" />
      <path fill="#f7d28b" d="m13.8 4.5 5.7 5.7-1.7 1.7-5.7-5.7z" />
    </svg>
  `,
  undo: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path fill="#2e6eea" d="M10 6V2L3 8l7 6V9h5a5 5 0 0 1 5 5 5.7 5.7 0 0 1-1.8 4.1l2.1 2.1A8.1 8.1 0 0 0 23 14a8 8 0 0 0-8-8z" />
    </svg>
  `,
  redo: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path fill="#b6bcc5" d="M14 6V2l7 6-7 6V9H9a5 5 0 0 0-5 5 5.7 5.7 0 0 0 1.8 4.1l-2.1 2.1A8.1 8.1 0 0 1 1 14a8 8 0 0 1 8-8z" />
    </svg>
  `,
  binoculars: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path fill="#3c454f" d="M7 5h4v11H4V8a3 3 0 0 1 3-3zm6 0h4a3 3 0 0 1 3 3v8h-7z" />
      <circle cx="7.5" cy="17" r="3.5" fill="#2f3740" />
      <circle cx="16.5" cy="17" r="3.5" fill="#2f3740" />
    </svg>
  `,
  spell: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <text x="3" y="12" fill="#222" font-family="Arial" font-size="9" font-weight="700">ABC</text>
      <path fill="none" stroke="#29a35a" stroke-linecap="round" stroke-width="2" d="m6 17 3 3 8-8" />
    </svg>
  `,
  table: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path fill="#eaf2ff" stroke="#6b8ebc" d="M3 4h18v16H3z" />
      <path stroke="#6b8ebc" d="M3 9h18M3 14h18M9 4v16M15 4v16" />
      <path fill="#51a7df" d="M3 4h18v5H3z" opacity=".85" />
    </svg>
  `,
  sort: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path fill="#2e6eea" d="M7 4h3v12h3l-4.5 5L4 16h3z" />
      <text x="13" y="11" fill="#333" font-family="Arial" font-size="9" font-weight="700">A</text>
      <text x="13" y="20" fill="#333" font-family="Arial" font-size="9" font-weight="700">Z</text>
    </svg>
  `,
  sortDescending: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path fill="#2e6eea" d="M7 4h3v12h3l-4.5 5L4 16h3z" />
      <text x="13" y="11" fill="#333" font-family="Arial" font-size="9" font-weight="700">Z</text>
      <text x="13" y="20" fill="#333" font-family="Arial" font-size="9" font-weight="700">A</text>
    </svg>
  `,
  filter: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path fill="#9ea4ad" d="M3 5h18l-7 8v5l-4 2v-7z" />
      <path fill="#f4bd3f" d="M14 13h6l-3 5z" />
    </svg>
  `,
  image: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path fill="#fbfbfb" stroke="#a4adb7" d="M4 4h17v17H4z" />
      <circle cx="16" cy="8" r="2" fill="#f4bd3f" />
      <path fill="#5fb862" d="m5 19 5.5-7 4 5 2-2.5L21 19z" />
    </svg>
  `,
  chart: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path fill="#5fb862" d="M4 11h4v10H4z" />
      <path fill="#f4bd3f" d="M10 7h4v14h-4z" />
      <path fill="#49a4df" d="M16 3h4v18h-4z" />
    </svg>
  `,
  sparkline: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path fill="#eef5ff" stroke="#9aa8bd" d="M3.5 4.5h17v15h-17z" />
      <path fill="none" stroke="#2f70d8" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="m5.5 15 3.2-4 3.1 2.5 3.2-6 3.5 3" />
    </svg>
  `,
  pivotTable: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <rect x="3.5" y="3.5" width="17" height="17" fill="#f8f8f8" stroke="#8f98a3" stroke-width="1.4" />
      <path d="M3.5 9h17M9 3.5v17M14.5 3.5v8.5" stroke="#9aa1aa" stroke-width="1.1" />
      <rect x="5.2" y="5.2" width="2.3" height="2.3" fill="#cfd4dc" />
      <rect x="10.4" y="5.2" width="2.3" height="2.3" fill="#cfd4dc" />
      <path d="M8.2 16.6c4.8 0 7.8-3 7.8-7.8V6.8" fill="none" stroke="#0b66e4" stroke-width="2.2" stroke-linecap="round" />
      <path d="m12.7 10.1 3.3-3.3 3.3 3.3" fill="none" stroke="#0b66e4" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" />
    </svg>
  `,
  omega: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <text x="4" y="19" fill="#2f70d8" font-family="Georgia" font-size="21">Ω</text>
    </svg>
  `,
  link: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path fill="none" stroke="#3b78d8" stroke-linecap="round" stroke-width="2" d="M9.5 14.5 14.5 9.5M8.5 10H7a4 4 0 0 0 0 8h4a4 4 0 0 0 3.5-2M15.5 14H17a4 4 0 0 0 0-8h-4a4 4 0 0 0-3.5 2" />
    </svg>
  `,
  comment: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path fill="#eceff3" stroke="#9aa1aa" d="M4 5h17v12H9l-5 4z" />
    </svg>
  `,
  page: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path fill="#f8f8f8" stroke="#9aa1aa" d="M6 2.5h9l4 4V22H6z" />
      <path fill="#f0c95a" d="M8 10h9v1.8H8zm0 4h9v1.8H8z" />
    </svg>
  `,
  shapes: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="9" cy="8" r="4" fill="#eef5ff" stroke="#2f70d8" />
      <path fill="#f1f5ff" stroke="#2f70d8" d="M10 12h9v9h-9z" />
    </svg>
  `,
} as const;

const mockToolbarTopGroups: readonly (readonly MockToolbarItem[])[] = [
  [
    { label: 'New Spreadsheet', icon: mockToolbarIcon.spreadsheet },
    { label: 'Open', icon: mockToolbarIcon.folder },
    { label: 'Save', icon: mockToolbarIcon.save },
  ],
  [
    { label: 'Export PDF', icon: mockToolbarIcon.pdf },
    { label: 'Print', icon: mockToolbarIcon.print },
    { label: 'Find', icon: mockToolbarIcon.search },
  ],
  [
    { label: 'Cut', icon: mockToolbarIcon.cut },
    { label: 'Copy', icon: mockToolbarIcon.copy },
    { label: 'Paste', icon: mockToolbarIcon.paste },
    { label: 'Format Paintbrush', icon: mockToolbarIcon.brush },
  ],
  [
    { label: 'Undo', icon: mockToolbarIcon.undo },
    { label: 'Redo', icon: mockToolbarIcon.redo },
    { label: 'Find All', icon: mockToolbarIcon.binoculars },
    { label: 'Spell Check', icon: mockToolbarIcon.spell },
  ],
  [
    { label: 'Insert Table', icon: mockToolbarIcon.table },
    { label: 'Sort Ascending', icon: mockToolbarIcon.sort, sortAscending: true },
    { label: 'Sort Descending', icon: mockToolbarIcon.sortDescending, sortAscending: false },
    { label: 'Auto Filter', icon: mockToolbarIcon.filter, filter: true },
    { label: 'Insert Image', icon: mockToolbarIcon.image },
    { label: 'Insert Chart', icon: mockToolbarIcon.chart, chart: true },
    // { label: 'Insert Sparkline', icon: mockToolbarIcon.sparkline, sparkline: true },
    { label: 'Pivot Table', icon: mockToolbarIcon.pivotTable, pivotTable: true },
  ],
  [
    { label: 'Special Character', icon: mockToolbarIcon.omega },
    { label: 'Hyperlink', icon: mockToolbarIcon.link },
    { label: 'Comment', icon: mockToolbarIcon.comment },
    { label: 'Page Break', icon: mockToolbarIcon.page },
    { label: 'Shapes', icon: mockToolbarIcon.shapes },
  ],
];

const mockFormattingGroups: readonly (readonly MockFormattingItem[])[] = [
  [
    { label: 'B', title: 'Bold', commandId: formatCommandIds.bold },
    { label: 'I', title: 'Italic', commandId: formatCommandIds.italic },
    { label: 'U', title: 'Underline', commandId: formatCommandIds.underline },
  ],
  [
    { label: 'A', title: 'Text Color', colorCommandId: textColorCommandId },
    { label: 'Fill', title: 'Fill Color', colorCommandId: fillColorCommandId, icon: mockToolbarIcon.fillBucket },
    { label: 'L', title: 'Align Left', icon: mockToolbarIcon.alignLeft },
    { label: 'C', title: 'Align Center', icon: mockToolbarIcon.alignCenter },
    { label: 'R', title: 'Align Right', icon: mockToolbarIcon.alignRight },
  ],
  [
    { label: 'Top', title: 'Align Top', icon: mockToolbarIcon.alignTop },
    { label: 'Mid', title: 'Align Middle', icon: mockToolbarIcon.alignMiddle },
    { label: 'Bot', title: 'Align Bottom', icon: mockToolbarIcon.alignBottom },
    { label: 'Merge', title: 'Merge Cells', action: 'mergeCells', icon: mockToolbarIcon.mergeCells },
    { label: 'Unmerge', title: 'Unmerge Cells', action: 'unmergeCells', icon: mockToolbarIcon.unmergeCells },
  ],
  [
    { label: '%', title: 'Percent Format', action: 'percentFormat' },
    { label: '0.00', title: 'Number Format', action: 'numberFormat' },
    { label: 'Date', title: 'Date Format', action: 'dateFormat', icon: mockToolbarIcon.date },
    { label: 'Dec-', title: 'Decrease Decimal', icon: mockToolbarIcon.decimalDecrease },
    { label: 'Dec+', title: 'Increase Decimal', icon: mockToolbarIcon.decimalIncrease },
  ],
  [
    { label: 'Indent-', title: 'Decrease Indent', icon: mockToolbarIcon.indentDecrease },
    { label: 'Indent+', title: 'Increase Indent', icon: mockToolbarIcon.indentIncrease },
    { label: 'Border', title: 'Borders', icon: mockToolbarIcon.border },
    { label: 'Wrap', title: 'Text Wrap', icon: mockToolbarIcon.wrap },
    { label: 'Dir', title: 'Text Direction', icon: mockToolbarIcon.textDirection },
  ],
];

function closeFilterHeaderDialog() {
  document.getElementById(filterHeaderDialogId)?.remove();
  document.removeEventListener('keydown', closeFilterHeaderDialogOnEscape, true);
}

function closeFilterHeaderDialogOnEscape(event: KeyboardEvent) {
  if (event.key !== 'Escape') return;

  closeFilterHeaderDialog();
}

function openFilterHeaderDialog({
  onHeaderless,
  onUseFirstLineAsHeader,
}: {
  onHeaderless: () => void;
  onUseFirstLineAsHeader: () => void;
}) {
  closeFilterHeaderDialog();

  const dialog = document.createElement('div');
  dialog.id = filterHeaderDialogId;
  dialog.className = 'spreadsheet-filter-header-dialog-backdrop';
  dialog.innerHTML = `
    <div class="spreadsheet-filter-header-dialog" role="dialog" aria-modal="true" aria-labelledby="spreadsheet-filter-header-dialog-title">
      <div class="spreadsheet-filter-header-dialog-title" id="spreadsheet-filter-header-dialog-title">Filter</div>
      <div class="spreadsheet-filter-header-dialog-message">
        The range does not contain column headers.<br>
        Do you want the first line to be used as column header?
      </div>
      <div class="spreadsheet-filter-header-dialog-actions">
        <button class="spreadsheet-filter-header-dialog-button" type="button" data-filter-header-yes>Yes</button>
        <button class="spreadsheet-filter-header-dialog-button" type="button" data-filter-header-no>No</button>
        <button class="spreadsheet-filter-header-dialog-button" type="button" data-filter-header-cancel>Cancel</button>
      </div>
    </div>
  `;

  dialog.addEventListener('click', (event) => {
    if (event.target === dialog) closeFilterHeaderDialog();
  });

  dialog.querySelector<HTMLButtonElement>('[data-filter-header-yes]')?.addEventListener('click', () => {
    onUseFirstLineAsHeader();
    closeFilterHeaderDialog();
  });

  dialog.querySelector<HTMLButtonElement>('[data-filter-header-no]')?.addEventListener('click', () => {
    onHeaderless();
    closeFilterHeaderDialog();
  });

  dialog.querySelector<HTMLButtonElement>('[data-filter-header-cancel]')?.addEventListener('click', () => {
    closeFilterHeaderDialog();
  });

  document.body.appendChild(dialog);
  document.addEventListener('keydown', closeFilterHeaderDialogOnEscape, true);
  dialog.querySelector<HTMLButtonElement>('[data-filter-header-yes]')?.focus();
}

function applyHeaderlessSelectionFilter(actions: FilterActions) {
  void actions.applySelectionHeaderlessFilter();
}

function requestSelectionFilter(actions: FilterActions) {
  if (!actions.getSelectionRangeTarget()) return;

  if (filterHeaderPreference === 'use-first-line') {
    void actions.applySelectionFilter();
    return;
  }

  if (filterHeaderPreference === 'headerless') {
    applyHeaderlessSelectionFilter(actions);
    return;
  }

  openFilterHeaderDialog({
    onHeaderless: () => {
      filterHeaderPreference = 'headerless';
      applyHeaderlessSelectionFilter(actions);
    },
    onUseFirstLineAsHeader: () => {
      filterHeaderPreference = 'use-first-line';
      void actions.applySelectionFilter();
    },
  });
}

function closeChartWizardDialog() {
  document.getElementById(chartWizardDialogId)?.remove();
  document.removeEventListener('keydown', closeChartWizardDialogOnEscape, true);
}

function closeChartWizardDialogOnEscape(event: KeyboardEvent) {
  if (event.key !== 'Escape') return;

  closeChartWizardDialog();
}

function escapeChartWizardAttribute(value: string) {
  return value.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function getSelectionRangeA1(actions: ChartWizardActions) {
  const selectionTarget = actions.getSelectionRangeTarget({ allowSingleRow: true });
  if (!selectionTarget) return '';

  const { range } = selectionTarget;

  return [
    actions.columnIndexToName(range.startColumn),
    range.startRow + 1,
    ':',
    actions.columnIndexToName(range.endColumn),
    range.endRow + 1,
  ].join('');
}

function createChartWizardIcon(kind: ChartWizardIconKind) {
  if (kind === 'bar') {
    return `
      <svg viewBox="0 0 42 42" aria-hidden="true">
        <path d="M8 34V9M8 34h27" stroke="#7b8491" stroke-width="1.6" stroke-linecap="round" />
        <rect x="11" y="13" width="19" height="6" fill="#ff9900" />
        <rect x="11" y="21" width="14" height="6" fill="#1a73e8" />
        <rect x="11" y="29" width="22" height="6" fill="#1db954" />
      </svg>
    `;
  }

  if (kind === 'pie') {
    return `
      <svg viewBox="0 0 42 42" aria-hidden="true">
        <path d="M21 6a15 15 0 1 1-10.6 4.4L21 21z" fill="#1a73e8" />
        <path d="M21 6a15 15 0 0 1 15 15H21z" fill="#1db954" />
        <path d="M36 21a15 15 0 0 1-15 15V21z" fill="#ff9900" />
      </svg>
    `;
  }

  if (kind === 'line') {
    return `
      <svg viewBox="0 0 42 42" aria-hidden="true">
        <path d="M8 34V8M8 34h27" stroke="#7b8491" stroke-width="1.6" stroke-linecap="round" />
        <path d="m10 28 7-8 6 5 9-12" fill="none" stroke="#1a73e8" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" />
        <path d="m10 20 7 2 6-8 9 6" fill="none" stroke="#1db954" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round" />
      </svg>
    `;
  }

  if (kind === 'area') {
    return `
      <svg viewBox="0 0 42 42" aria-hidden="true">
        <path d="M8 34V8M8 34h27" stroke="#7b8491" stroke-width="1.6" stroke-linecap="round" />
        <path d="m10 30 7-9 6 4 9-12v17z" fill="#1db954" />
        <path d="m10 33 7-5 6 2 9-7v10z" fill="#1a73e8" />
      </svg>
    `;
  }

  if (kind === 'scatter' || kind === 'bubble') {
    const radius = kind === 'bubble' ? '3.2' : '1.9';
    return `
      <svg viewBox="0 0 42 42" aria-hidden="true">
        <path d="M8 34V8M8 34h27" stroke="#7b8491" stroke-width="1.6" stroke-linecap="round" />
        <circle cx="15" cy="26" r="${radius}" fill="#1a73e8" />
        <circle cx="22" cy="18" r="${kind === 'bubble' ? '4.4' : '1.9'}" fill="#1db954" />
        <circle cx="29" cy="24" r="${kind === 'bubble' ? '3.8' : '1.9'}" fill="#ff9900" />
        <circle cx="32" cy="13" r="${radius}" fill="#1a73e8" />
      </svg>
    `;
  }

  if (kind === 'radar') {
    return `
      <svg viewBox="0 0 42 42" aria-hidden="true">
        <path d="M21 6 35 16 30 33H12L7 16z" fill="none" stroke="#7b8491" stroke-width="1.4" />
        <path d="M21 11 30 18 27 29H15l-3-11z" fill="#1db954" opacity=".75" />
        <path d="M21 6v27M7 16l23 17M35 16 12 33" stroke="#7b8491" stroke-width=".9" />
      </svg>
    `;
  }

  if (kind === 'combination') {
    return `
      <svg viewBox="0 0 42 42" aria-hidden="true">
        <path d="M8 34V8M8 34h27" stroke="#7b8491" stroke-width="1.6" stroke-linecap="round" />
        <rect x="12" y="22" width="5" height="12" fill="#1a73e8" />
        <rect x="20" y="15" width="5" height="19" fill="#1db954" />
        <rect x="28" y="19" width="5" height="15" fill="#ff9900" />
        <path d="m11 18 7 4 7-10 9 5" fill="none" stroke="#e63757" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
      </svg>
    `;
  }

  if (kind === 'funnel') {
    return `
      <svg viewBox="0 0 42 42" aria-hidden="true">
        <path d="M8 8h26l-9 11v12l-8 4V19z" fill="#9ca3af" />
        <path d="M11 11h20l-5 6H16z" fill="#1a73e8" />
        <path d="M16 20h10l-2 5h-6z" fill="#1db954" />
      </svg>
    `;
  }

  if (kind === 'heatmap') {
    return `
      <svg viewBox="0 0 42 42" aria-hidden="true">
        <rect x="9" y="9" width="8" height="8" fill="#f9c74f" />
        <rect x="18" y="9" width="8" height="8" fill="#90be6d" />
        <rect x="27" y="9" width="8" height="8" fill="#43aa8b" />
        <rect x="9" y="18" width="8" height="8" fill="#f8961e" />
        <rect x="18" y="18" width="8" height="8" fill="#f94144" />
        <rect x="27" y="18" width="8" height="8" fill="#577590" />
        <rect x="9" y="27" width="8" height="8" fill="#277da1" />
        <rect x="18" y="27" width="8" height="8" fill="#4d908e" />
        <rect x="27" y="27" width="8" height="8" fill="#f3722c" />
      </svg>
    `;
  }

  return `
    <svg viewBox="0 0 42 42" aria-hidden="true">
      <path d="M8 34V9M8 34h27" stroke="#7b8491" stroke-width="1.6" stroke-linecap="round" />
      <rect x="12" y="20" width="5" height="14" fill="#1a73e8" />
      <rect x="20" y="11" width="5" height="23" fill="#1db954" />
      <rect x="28" y="16" width="5" height="18" fill="#ff9900" />
    </svg>
  `;
}

function openChartWizardDialog(actions: ChartWizardActions) {
  closeChartWizardDialog();

  const defaultChartGroup = chartWizardTypeGroups[0]!;
  const defaultChartSubtype = defaultChartGroup.subtypes[0]!;

  let stepIndex: ChartWizardStep = 0;
  let chartGroupKey = defaultChartGroup.key;
  let chartSubtypeIndex = 0;
  let rangeA1 = getSelectionRangeA1(actions);
  let dataOrientation: ChartWizardDataOrientation = 'Column';
  let useFirstRowAsHeader = true;
  let useFirstColumnAsLabel = true;
  let title = '';
  let subtitle = '';
  let xAxisTitle = '';
  let yAxisTitle = '';
  let legendPosition: ChartWizardLegendPosition = 'right';
  let width = 560;
  let height = 360;

  const dialog = document.createElement('div');
  dialog.id = chartWizardDialogId;
  dialog.className = 'spreadsheet-chart-wizard-backdrop';
  dialog.innerHTML = `
    <div class="spreadsheet-chart-wizard-dialog" role="dialog" aria-modal="true" aria-labelledby="spreadsheet-chart-wizard-title">
      <div class="spreadsheet-chart-wizard-titlebar">
        <span class="spreadsheet-chart-wizard-window-dot spreadsheet-chart-wizard-window-dot-red" aria-hidden="true"></span>
        <span class="spreadsheet-chart-wizard-window-dot spreadsheet-chart-wizard-window-dot-yellow" aria-hidden="true"></span>
        <span class="spreadsheet-chart-wizard-window-dot spreadsheet-chart-wizard-window-dot-green" aria-hidden="true"></span>
        <strong id="spreadsheet-chart-wizard-title">Chart Wizard</strong>
        <button class="spreadsheet-chart-wizard-close" type="button" aria-label="Close">x</button>
      </div>
      <div class="spreadsheet-chart-wizard-content">
        <aside class="spreadsheet-chart-wizard-steps" data-chart-wizard-steps></aside>
        <section class="spreadsheet-chart-wizard-panel" data-chart-wizard-panel></section>
      </div>
      <div class="spreadsheet-chart-wizard-footer">
        <button class="spreadsheet-chart-wizard-button spreadsheet-chart-wizard-help" type="button" tabindex="-1" aria-disabled="true">Help</button>
        <span class="spreadsheet-chart-wizard-footer-spacer"></span>
        <button class="spreadsheet-chart-wizard-button" type="button" data-chart-wizard-back>&lt; Back</button>
        <button class="spreadsheet-chart-wizard-button" type="button" data-chart-wizard-next>Next &gt;</button>
        <button class="spreadsheet-chart-wizard-button spreadsheet-chart-wizard-button-primary" type="button" data-chart-wizard-finish>Finish</button>
        <button class="spreadsheet-chart-wizard-button" type="button" data-chart-wizard-cancel>Cancel</button>
      </div>
    </div>
  `;

  function getActiveGroup(): ChartWizardTypeGroup {
    return chartWizardTypeGroups.find((group) => group.key === chartGroupKey) ?? defaultChartGroup;
  }

  function getActiveSubtype(): ChartWizardSubtype {
    const group = getActiveGroup();

    return group.subtypes[chartSubtypeIndex] ?? group.subtypes[0] ?? defaultChartSubtype;
  }

  function syncChartWizardStateFromPanel() {
    const rangeInput = dialog.querySelector<HTMLInputElement>('[data-chart-wizard-range]');
    const orientationInput = dialog.querySelector<HTMLSelectElement>('[data-chart-wizard-orientation]');
    const firstRowInput = dialog.querySelector<HTMLInputElement>('[data-chart-wizard-first-row]');
    const firstColumnInput = dialog.querySelector<HTMLInputElement>('[data-chart-wizard-first-column]');
    const titleInput = dialog.querySelector<HTMLInputElement>('[data-chart-wizard-title-input]');
    const subtitleInput = dialog.querySelector<HTMLInputElement>('[data-chart-wizard-subtitle]');
    const xAxisInput = dialog.querySelector<HTMLInputElement>('[data-chart-wizard-x-axis]');
    const yAxisInput = dialog.querySelector<HTMLInputElement>('[data-chart-wizard-y-axis]');
    const legendInput = dialog.querySelector<HTMLSelectElement>('[data-chart-wizard-legend]');
    const widthInput = dialog.querySelector<HTMLInputElement>('[data-chart-wizard-width]');
    const heightInput = dialog.querySelector<HTMLInputElement>('[data-chart-wizard-height]');

    if (rangeInput) rangeA1 = rangeInput.value.trim();
    if (orientationInput) dataOrientation = orientationInput.value === 'Row' ? 'Row' : 'Column';
    if (firstRowInput) useFirstRowAsHeader = firstRowInput.checked;
    if (firstColumnInput) useFirstColumnAsLabel = firstColumnInput.checked;
    if (titleInput) title = titleInput.value;
    if (subtitleInput) subtitle = subtitleInput.value;
    if (xAxisInput) xAxisTitle = xAxisInput.value;
    if (yAxisInput) yAxisTitle = yAxisInput.value;
    if (legendInput) legendPosition = legendInput.value as ChartWizardLegendPosition;
    if (widthInput) width = Number(widthInput.value) || 560;
    if (heightInput) height = Number(heightInput.value) || 360;
  }

  function renderChartWizardSteps() {
    const steps = dialog.querySelector<HTMLElement>('[data-chart-wizard-steps]');
    if (!steps) return;

    steps.innerHTML = `
      <h2>Steps</h2>
      ${chartWizardSteps
        .map(
          (step, index) => `
            <button
              class="spreadsheet-chart-wizard-step ${index === stepIndex ? 'is-active' : ''}"
              type="button"
              data-chart-wizard-step="${index}"
            >
              ${index + 1}. ${step}
            </button>
          `,
        )
        .join('')}
    `;

    steps.querySelectorAll<HTMLButtonElement>('[data-chart-wizard-step]').forEach((button) => {
      button.addEventListener('click', () => {
        syncChartWizardStateFromPanel();
        stepIndex = Number(button.dataset.chartWizardStep) as ChartWizardStep;
        renderChartWizard();
      });
    });
  }

  function renderChartTypeStep(panel: HTMLElement) {
    const group = getActiveGroup();
    const subtype = getActiveSubtype();

    panel.innerHTML = `
      <h2>Choose a Chart Type</h2>
      <div class="spreadsheet-chart-wizard-type-grid">
        <div class="spreadsheet-chart-wizard-type-list">
          ${chartWizardTypeGroups
            .map(
              (chartGroup) => `
                <button
                  class="spreadsheet-chart-wizard-type ${chartGroup.key === chartGroupKey ? 'is-active' : ''}"
                  type="button"
                  data-chart-wizard-group="${chartGroup.key}"
                >
                  <span class="spreadsheet-chart-wizard-type-icon">${createChartWizardIcon(chartGroup.icon)}</span>
                  <span>${chartGroup.label}</span>
                </button>
              `,
            )
            .join('')}
        </div>
        <div class="spreadsheet-chart-wizard-subtype-area">
          <div class="spreadsheet-chart-wizard-subtype-cards">
            ${group.subtypes
              .map(
                (chartSubtype, index) => `
                  <button
                    class="spreadsheet-chart-wizard-subtype ${index === chartSubtypeIndex ? 'is-active' : ''}"
                    type="button"
                    data-chart-wizard-subtype="${index}"
                    title="${escapeChartWizardAttribute(chartSubtype.label)}"
                  >
                    ${createChartWizardIcon(chartSubtype.icon)}
                  </button>
                `,
              )
              .join('')}
          </div>
          <div class="spreadsheet-chart-wizard-subtype-name">${subtype.label}</div>
          <label class="spreadsheet-chart-wizard-disabled-check">
            <input type="checkbox" disabled>
            <span>3D Look</span>
          </label>
          <div class="spreadsheet-chart-wizard-shape-list" aria-label="Shape">
            <div class="is-active">Bar</div>
            <div>Cylinder</div>
            <div>Cone</div>
            <div>Pyramid</div>
          </div>
        </div>
      </div>
    `;

    panel.querySelectorAll<HTMLButtonElement>('[data-chart-wizard-group]').forEach((button) => {
      button.addEventListener('click', () => {
        syncChartWizardStateFromPanel();
        chartGroupKey = button.dataset.chartWizardGroup || defaultChartGroup.key;
        chartSubtypeIndex = 0;
        renderChartWizard();
      });
    });

    panel.querySelectorAll<HTMLButtonElement>('[data-chart-wizard-subtype]').forEach((button) => {
      button.addEventListener('click', () => {
        chartSubtypeIndex = Number(button.dataset.chartWizardSubtype) || 0;
        renderChartWizard();
      });
    });
  }

  function renderDataRangeStep(panel: HTMLElement) {
    panel.innerHTML = `
      <h2>Choose a Data Range</h2>
      <div class="spreadsheet-chart-wizard-form">
        <label class="spreadsheet-chart-wizard-field">
          <span>Data range</span>
          <input type="text" value="${escapeChartWizardAttribute(rangeA1)}" data-chart-wizard-range>
        </label>
        <label class="spreadsheet-chart-wizard-check">
          <input type="checkbox" data-chart-wizard-first-row ${useFirstRowAsHeader ? 'checked' : ''}>
          <span>First row as label</span>
        </label>
        <label class="spreadsheet-chart-wizard-check">
          <input type="checkbox" data-chart-wizard-first-column ${useFirstColumnAsLabel ? 'checked' : ''}>
          <span>First column as label</span>
        </label>
        <label class="spreadsheet-chart-wizard-field">
          <span>Data series in</span>
          <select data-chart-wizard-orientation>
            <option value="Column" ${dataOrientation === 'Column' ? 'selected' : ''}>Columns</option>
            <option value="Row" ${dataOrientation === 'Row' ? 'selected' : ''}>Rows</option>
          </select>
        </label>
      </div>
    `;
  }

  function renderDataSeriesStep(panel: HTMLElement) {
    panel.innerHTML = `
      <h2>Adjust Data Series</h2>
      <div class="spreadsheet-chart-wizard-form spreadsheet-chart-wizard-form-two-column">
        <label class="spreadsheet-chart-wizard-field">
          <span>Data series in</span>
          <select data-chart-wizard-orientation>
            <option value="Column" ${dataOrientation === 'Column' ? 'selected' : ''}>Columns</option>
            <option value="Row" ${dataOrientation === 'Row' ? 'selected' : ''}>Rows</option>
          </select>
        </label>
        <label class="spreadsheet-chart-wizard-field">
          <span>Range</span>
          <input type="text" value="${escapeChartWizardAttribute(rangeA1)}" data-chart-wizard-range>
        </label>
        <label class="spreadsheet-chart-wizard-check">
          <input type="checkbox" data-chart-wizard-first-row ${useFirstRowAsHeader ? 'checked' : ''}>
          <span>Use first row for series names</span>
        </label>
        <label class="spreadsheet-chart-wizard-check">
          <input type="checkbox" data-chart-wizard-first-column ${useFirstColumnAsLabel ? 'checked' : ''}>
          <span>Use first column for categories</span>
        </label>
      </div>
      <div class="spreadsheet-chart-wizard-series-preview">
        <div>Selected type</div>
        <strong>${getActiveSubtype().label}</strong>
      </div>
    `;
  }

  function renderChartElementsStep(panel: HTMLElement) {
    panel.innerHTML = `
      <h2>Set Chart Elements</h2>
      <div class="spreadsheet-chart-wizard-form spreadsheet-chart-wizard-form-two-column">
        <label class="spreadsheet-chart-wizard-field">
          <span>Title</span>
          <input type="text" value="${escapeChartWizardAttribute(title)}" placeholder="${escapeChartWizardAttribute(getActiveSubtype().label)}" data-chart-wizard-title-input>
        </label>
        <label class="spreadsheet-chart-wizard-field">
          <span>Subtitle</span>
          <input type="text" value="${escapeChartWizardAttribute(subtitle)}" data-chart-wizard-subtitle>
        </label>
        <label class="spreadsheet-chart-wizard-field">
          <span>X axis</span>
          <input type="text" value="${escapeChartWizardAttribute(xAxisTitle)}" data-chart-wizard-x-axis>
        </label>
        <label class="spreadsheet-chart-wizard-field">
          <span>Y axis</span>
          <input type="text" value="${escapeChartWizardAttribute(yAxisTitle)}" data-chart-wizard-y-axis>
        </label>
        <label class="spreadsheet-chart-wizard-field">
          <span>Legend</span>
          <select data-chart-wizard-legend>
            <option value="right" ${legendPosition === 'right' ? 'selected' : ''}>Right</option>
            <option value="bottom" ${legendPosition === 'bottom' ? 'selected' : ''}>Bottom</option>
            <option value="top" ${legendPosition === 'top' ? 'selected' : ''}>Top</option>
            <option value="left" ${legendPosition === 'left' ? 'selected' : ''}>Left</option>
            <option value="hide" ${legendPosition === 'hide' ? 'selected' : ''}>Hide</option>
          </select>
        </label>
        <div class="spreadsheet-chart-wizard-size-fields">
          <label class="spreadsheet-chart-wizard-field">
            <span>Width</span>
            <input type="number" min="240" max="1200" value="${width}" data-chart-wizard-width>
          </label>
          <label class="spreadsheet-chart-wizard-field">
            <span>Height</span>
            <input type="number" min="180" max="900" value="${height}" data-chart-wizard-height>
          </label>
        </div>
      </div>
    `;
  }

  function renderChartWizardPanel() {
    const panel = dialog.querySelector<HTMLElement>('[data-chart-wizard-panel]');
    if (!panel) return;

    if (stepIndex === 0) renderChartTypeStep(panel);
    if (stepIndex === 1) renderDataRangeStep(panel);
    if (stepIndex === 2) renderDataSeriesStep(panel);
    if (stepIndex === 3) renderChartElementsStep(panel);
  }

  function renderChartWizardFooter() {
    const backButton = dialog.querySelector<HTMLButtonElement>('[data-chart-wizard-back]');
    const nextButton = dialog.querySelector<HTMLButtonElement>('[data-chart-wizard-next]');

    if (backButton) backButton.disabled = stepIndex === 0;
    if (nextButton) nextButton.disabled = stepIndex === chartWizardSteps.length - 1;
  }

  function renderChartWizard() {
    renderChartWizardSteps();
    renderChartWizardPanel();
    renderChartWizardFooter();
  }

  dialog.addEventListener('click', (event) => {
    if (event.target === dialog) closeChartWizardDialog();
  });

  dialog.querySelector<HTMLButtonElement>('.spreadsheet-chart-wizard-close')?.addEventListener('click', closeChartWizardDialog);
  dialog.querySelector<HTMLButtonElement>('[data-chart-wizard-cancel]')?.addEventListener('click', closeChartWizardDialog);
  dialog.querySelector<HTMLButtonElement>('[data-chart-wizard-back]')?.addEventListener('click', () => {
    syncChartWizardStateFromPanel();
    stepIndex = Math.max(0, stepIndex - 1) as ChartWizardStep;
    renderChartWizard();
  });
  dialog.querySelector<HTMLButtonElement>('[data-chart-wizard-next]')?.addEventListener('click', () => {
    syncChartWizardStateFromPanel();
    stepIndex = Math.min(chartWizardSteps.length - 1, stepIndex + 1) as ChartWizardStep;
    renderChartWizard();
  });
  dialog.querySelector<HTMLButtonElement>('[data-chart-wizard-finish]')?.addEventListener('click', async () => {
    syncChartWizardStateFromPanel();

    const subtype = getActiveSubtype();
    const config: ChartWizardConfig = {
      chartType: subtype.chartType,
      chartLabel: subtype.label,
      dataOrientation,
      height,
      legendPosition,
      rangeA1,
      subtitle,
      title,
      useFirstColumnAsLabel,
      useFirstRowAsHeader,
      width,
      xAxisTitle,
      yAxisTitle,
    };
    const didInsert = await actions.applySelectionChart(config);

    if (didInsert) {
      closeChartWizardDialog();
      return;
    }

    const panel = dialog.querySelector<HTMLElement>('[data-chart-wizard-panel]');
    panel?.classList.add('has-error');
  });

  document.body.appendChild(dialog);
  document.addEventListener('keydown', closeChartWizardDialogOnEscape, true);
  renderChartWizard();
  dialog.querySelector<HTMLButtonElement>('[data-chart-wizard-finish]')?.focus();
}

type PivotTableArea = 'filter' | 'column' | 'row' | 'data';

const pivotTableDataFunctionOptions: readonly { label: string; value: PivotTableDataFunction }[] = [
  { label: 'Sum', value: 'sum' },
  { label: 'Count', value: 'count' },
  { label: 'Average', value: 'average' },
  { label: 'Median', value: 'median' },
  { label: 'Max', value: 'max' },
  { label: 'Min', value: 'min' },
  { label: 'Product', value: 'product' },
  { label: 'Count (Numbers only)', value: 'countNumbers' },
] as const;

function closePivotSourceDialog() {
  document.getElementById(pivotSourceDialogId)?.remove();
  document.removeEventListener('keydown', closePivotSourceDialogOnEscape, true);
}

function closePivotSourceDialogOnEscape(event: KeyboardEvent) {
  if (event.key !== 'Escape') return;

  closePivotSourceDialog();
}

function closePivotLayoutDialog() {
  document.getElementById(pivotLayoutDialogId)?.remove();
  closePivotDataFieldDialog();
  document.removeEventListener('keydown', closePivotLayoutDialogOnEscape, true);
}

function closePivotLayoutDialogOnEscape(event: KeyboardEvent) {
  if (event.key !== 'Escape') return;

  closePivotLayoutDialog();
}

function closePivotDataFieldDialog() {
  document.getElementById(pivotDataFieldDialogId)?.remove();
}

function getPivotTableFunctionLabel(dataFunction: PivotTableDataFunction) {
  return pivotTableDataFunctionOptions.find((option) => option.value === dataFunction)?.label ?? 'Sum';
}

function getPivotTableField(source: PivotTableSourceInfo, fieldIndex: number): PivotTableFieldInfo {
  return source.fields[fieldIndex] ?? {
    index: fieldIndex,
    isNumeric: false,
    name: `Field ${fieldIndex + 1}`,
  };
}

function getDefaultPivotDataFunction(field: PivotTableFieldInfo): PivotTableDataFunction {
  return field.isNumeric ? 'sum' : 'count';
}

function renderPivotAssignedField(source: PivotTableSourceInfo, area: PivotTableArea, fieldIndex: number, dataField?: PivotTableDataFieldConfig) {
  const field = getPivotTableField(source, fieldIndex);
  const label = dataField ? `${getPivotTableFunctionLabel(dataField.function)} - ${field.name}` : field.name;

  return `
    <button
      class="spreadsheet-pivot-layout-item"
      type="button"
      draggable="true"
      data-pivot-assigned-area="${area}"
      data-pivot-assigned-field="${fieldIndex}"
      ${dataField ? `data-pivot-data-index="${fieldIndex}"` : ''}
      title="${escapeChartWizardAttribute(label)}"
    >
      <span>${escapeChartWizardAttribute(label)}</span>
      <span class="spreadsheet-pivot-layout-remove" data-pivot-remove="true" aria-hidden="true">x</span>
    </button>
  `;
}

function openPivotDataFieldDialog({
  dataField,
  field,
  onSave,
}: {
  dataField: PivotTableDataFieldConfig;
  field: PivotTableFieldInfo;
  onSave: (dataFunction: PivotTableDataFunction) => void;
}) {
  closePivotDataFieldDialog();

  let selectedFunction = dataField.function;
  const dialog = document.createElement('div');
  dialog.id = pivotDataFieldDialogId;
  dialog.className = 'spreadsheet-pivot-data-field-backdrop';
  dialog.innerHTML = `
    <div class="spreadsheet-pivot-window spreadsheet-pivot-data-field-dialog" role="dialog" aria-modal="true" aria-labelledby="spreadsheet-pivot-data-field-title">
      <div class="spreadsheet-pivot-titlebar">
        <span class="spreadsheet-pivot-window-dot spreadsheet-pivot-window-dot-red" aria-hidden="true"></span>
        <span class="spreadsheet-pivot-window-dot spreadsheet-pivot-window-dot-yellow" aria-hidden="true"></span>
        <span class="spreadsheet-pivot-window-dot spreadsheet-pivot-window-dot-disabled" aria-hidden="true"></span>
        <strong id="spreadsheet-pivot-data-field-title">Data Field</strong>
      </div>
      <div class="spreadsheet-pivot-data-field-content">
        <strong>Function</strong>
        <div class="spreadsheet-pivot-function-list" role="listbox" aria-label="Function">
          ${pivotTableDataFunctionOptions
            .map((option) => `
              <button
                class="spreadsheet-pivot-function-item ${option.value === selectedFunction ? 'is-active' : ''}"
                type="button"
                role="option"
                aria-selected="${option.value === selectedFunction ? 'true' : 'false'}"
                data-pivot-function="${option.value}"
              >
                ${option.label}
              </button>
            `)
            .join('')}
        </div>
        <label class="spreadsheet-pivot-check spreadsheet-pivot-check-disabled">
          <input type="checkbox" disabled>
          <span>Show items without data</span>
        </label>
        <div class="spreadsheet-pivot-data-field-name">
          <span>Name:</span>
          <strong>${escapeChartWizardAttribute(field.name)}</strong>
        </div>
        <details class="spreadsheet-pivot-details">
          <summary>Displayed Value</summary>
        </details>
      </div>
      <div class="spreadsheet-pivot-footer">
        <button class="spreadsheet-pivot-button" type="button" tabindex="-1" aria-disabled="true">Help</button>
        <span class="spreadsheet-pivot-footer-spacer"></span>
        <button class="spreadsheet-pivot-button" type="button" data-pivot-data-cancel>Cancel</button>
        <button class="spreadsheet-pivot-button spreadsheet-pivot-button-primary" type="button" data-pivot-data-ok>OK</button>
      </div>
    </div>
  `;

  dialog.querySelectorAll<HTMLButtonElement>('[data-pivot-function]').forEach((button) => {
    button.addEventListener('click', () => {
      selectedFunction = (button.dataset.pivotFunction as PivotTableDataFunction | undefined) ?? 'sum';
      dialog.querySelectorAll<HTMLElement>('[data-pivot-function]').forEach((item) => item.classList.remove('is-active'));
      button.classList.add('is-active');
    });
  });

  dialog.querySelector<HTMLButtonElement>('[data-pivot-data-cancel]')?.addEventListener('click', closePivotDataFieldDialog);
  dialog.querySelector<HTMLButtonElement>('[data-pivot-data-ok]')?.addEventListener('click', () => {
    onSave(selectedFunction);
    closePivotDataFieldDialog();
  });

  document.body.appendChild(dialog);
  dialog.querySelector<HTMLButtonElement>('[data-pivot-data-ok]')?.focus();
}

function openPivotLayoutDialog(actions: PivotTableActions, source: PivotTableSourceInfo) {
  closePivotLayoutDialog();

  const config: PivotTableLayoutConfig = {
    columnFields: [],
    dataFields: [],
    destination: 'new-sheet',
    filterFields: [],
    rowFields: [],
  };
  let errorMessage = '';
  const dialog = document.createElement('div');
  dialog.id = pivotLayoutDialogId;
  dialog.className = 'spreadsheet-pivot-layout-backdrop';

  function assignedFieldsForArea(area: PivotTableArea) {
    if (area === 'filter') return config.filterFields.map((fieldIndex) => renderPivotAssignedField(source, area, fieldIndex));
    if (area === 'column') {
      const assignedFields = config.columnFields.map((fieldIndex) => renderPivotAssignedField(source, area, fieldIndex));
      return assignedFields.length > 0
        ? assignedFields
        : ['<div class="spreadsheet-pivot-layout-placeholder">Data</div>'];
    }
    if (area === 'row') return config.rowFields.map((fieldIndex) => renderPivotAssignedField(source, area, fieldIndex));

    return config.dataFields.map((dataField) => renderPivotAssignedField(source, area, dataField.fieldIndex, dataField));
  }

  function removeFieldFromArea(area: PivotTableArea, fieldIndex: number) {
    if (area === 'filter') config.filterFields = config.filterFields.filter((index) => index !== fieldIndex);
    if (area === 'column') config.columnFields = config.columnFields.filter((index) => index !== fieldIndex);
    if (area === 'row') config.rowFields = config.rowFields.filter((index) => index !== fieldIndex);
    if (area === 'data') config.dataFields = config.dataFields.filter((field) => field.fieldIndex !== fieldIndex);
  }

  function addFieldToArea(fieldIndex: number, area: PivotTableArea) {
    if (area !== 'data') {
      config.filterFields = config.filterFields.filter((index) => index !== fieldIndex);
      config.columnFields = config.columnFields.filter((index) => index !== fieldIndex);
      config.rowFields = config.rowFields.filter((index) => index !== fieldIndex);
    }

    if (area === 'filter' && !config.filterFields.includes(fieldIndex)) config.filterFields.push(fieldIndex);
    if (area === 'column' && !config.columnFields.includes(fieldIndex)) config.columnFields.push(fieldIndex);
    if (area === 'row' && !config.rowFields.includes(fieldIndex)) config.rowFields.push(fieldIndex);
    if (area === 'data' && !config.dataFields.some((field) => field.fieldIndex === fieldIndex)) {
      config.dataFields.push({
        fieldIndex,
        function: getDefaultPivotDataFunction(getPivotTableField(source, fieldIndex)),
      });
    }

    errorMessage = '';
    render();
  }

  function render() {
    dialog.innerHTML = `
      <div class="spreadsheet-pivot-window spreadsheet-pivot-layout-dialog" role="dialog" aria-modal="true" aria-labelledby="spreadsheet-pivot-layout-title">
        <div class="spreadsheet-pivot-titlebar">
          <span class="spreadsheet-pivot-window-dot spreadsheet-pivot-window-dot-red" aria-hidden="true"></span>
          <span class="spreadsheet-pivot-window-dot spreadsheet-pivot-window-dot-yellow" aria-hidden="true"></span>
          <span class="spreadsheet-pivot-window-dot spreadsheet-pivot-window-dot-green" aria-hidden="true"></span>
          <strong id="spreadsheet-pivot-layout-title">Pivot Table Layout</strong>
        </div>
        <div class="spreadsheet-pivot-layout-content">
          <div class="spreadsheet-pivot-layout-grid">
            <section>
              <strong>Filters:</strong>
              <div class="spreadsheet-pivot-drop-zone" data-pivot-drop-area="filter">${assignedFieldsForArea('filter').join('')}</div>
            </section>
            <section>
              <strong>Column Fields:</strong>
              <div class="spreadsheet-pivot-drop-zone" data-pivot-drop-area="column">${assignedFieldsForArea('column').join('')}</div>
            </section>
            <section class="spreadsheet-pivot-available-section">
              <strong>Available Fields:</strong>
              <div class="spreadsheet-pivot-available-list" role="listbox">
                ${source.fields
                  .map((field) => `
                    <button
                      class="spreadsheet-pivot-available-item"
                      type="button"
                      draggable="true"
                      data-pivot-available-field="${field.index}"
                    >
                      ${escapeChartWizardAttribute(field.name)}
                    </button>
                  `)
                  .join('')}
              </div>
            </section>
            <section>
              <strong>Row Fields:</strong>
              <div class="spreadsheet-pivot-drop-zone" data-pivot-drop-area="row">${assignedFieldsForArea('row').join('')}</div>
            </section>
            <section>
              <strong>Data Fields:</strong>
              <div class="spreadsheet-pivot-drop-zone" data-pivot-drop-area="data">${assignedFieldsForArea('data').join('')}</div>
            </section>
          </div>
          <div class="spreadsheet-pivot-layout-hint">Drag the Items into the Desired Position</div>
          <details class="spreadsheet-pivot-details">
            <summary>Options</summary>
            <label class="spreadsheet-pivot-check spreadsheet-pivot-check-disabled">
              <input type="checkbox" disabled>
              <span>Show totals and subtotals</span>
            </label>
          </details>
          <details class="spreadsheet-pivot-details">
            <summary>Source and Destination</summary>
            <div class="spreadsheet-pivot-source-destination">
              <div>Source: ${escapeChartWizardAttribute(source.rangeA1)}</div>
              <label class="spreadsheet-pivot-radio">
                <input type="radio" name="spreadsheet-pivot-destination" value="new-sheet" ${config.destination === 'new-sheet' ? 'checked' : ''}>
                <span>New sheet</span>
              </label>
              <label class="spreadsheet-pivot-radio">
                <input type="radio" name="spreadsheet-pivot-destination" value="existing-sheet" ${config.destination === 'existing-sheet' ? 'checked' : ''}>
                <span>Current sheet</span>
              </label>
            </div>
          </details>
          ${errorMessage ? `<div class="spreadsheet-pivot-error">${escapeChartWizardAttribute(errorMessage)}</div>` : ''}
        </div>
        <div class="spreadsheet-pivot-footer">
          <button class="spreadsheet-pivot-button" type="button" tabindex="-1" aria-disabled="true">Help</button>
          <span class="spreadsheet-pivot-footer-spacer"></span>
          <button class="spreadsheet-pivot-button" type="button" data-pivot-layout-cancel>Cancel</button>
          <button class="spreadsheet-pivot-button spreadsheet-pivot-button-primary" type="button" data-pivot-layout-ok>OK</button>
        </div>
      </div>
    `;

    dialog.querySelectorAll<HTMLInputElement>('input[name="spreadsheet-pivot-destination"]').forEach((input) => {
      input.addEventListener('change', () => {
        config.destination = input.value === 'existing-sheet' ? 'existing-sheet' : 'new-sheet';
      });
    });

    dialog.querySelectorAll<HTMLElement>('[data-pivot-drop-area]').forEach((zone) => {
      zone.addEventListener('dragover', (event) => {
        event.preventDefault();
        zone.classList.add('is-dragging');
      });
      zone.addEventListener('dragleave', () => {
        zone.classList.remove('is-dragging');
      });
      zone.addEventListener('drop', (event) => {
        event.preventDefault();
        zone.classList.remove('is-dragging');
        const fieldIndex = Number(event.dataTransfer?.getData('text/plain'));
        const area = zone.dataset.pivotDropArea as PivotTableArea | undefined;
        if (!Number.isInteger(fieldIndex) || !area) return;

        addFieldToArea(fieldIndex, area);
      });
    });

    dialog.querySelectorAll<HTMLButtonElement>('[data-pivot-available-field]').forEach((button) => {
      const fieldIndex = Number(button.dataset.pivotAvailableField);
      button.addEventListener('dragstart', (event) => {
        event.dataTransfer?.setData('text/plain', String(fieldIndex));
      });
      button.addEventListener('dblclick', () => {
        addFieldToArea(fieldIndex, getPivotTableField(source, fieldIndex).isNumeric ? 'data' : 'row');
      });
    });

    dialog.querySelectorAll<HTMLButtonElement>('[data-pivot-assigned-field]').forEach((button) => {
      const area = button.dataset.pivotAssignedArea as PivotTableArea | undefined;
      const fieldIndex = Number(button.dataset.pivotAssignedField);
      button.addEventListener('dragstart', (event) => {
        event.dataTransfer?.setData('text/plain', String(fieldIndex));
      });
      button.addEventListener('click', (event) => {
        if (!(event.target instanceof HTMLElement) || !event.target.closest('[data-pivot-remove]') || !area) return;

        removeFieldFromArea(area, fieldIndex);
        render();
      });
      button.addEventListener('dblclick', () => {
        if (area !== 'data') return;

        const dataField = config.dataFields.find((field) => field.fieldIndex === fieldIndex);
        if (!dataField) return;

        openPivotDataFieldDialog({
          dataField,
          field: getPivotTableField(source, fieldIndex),
          onSave: (dataFunction) => {
            dataField.function = dataFunction;
            render();
          },
        });
      });
    });

    dialog.querySelector<HTMLButtonElement>('[data-pivot-layout-cancel]')?.addEventListener('click', closePivotLayoutDialog);
    dialog.querySelector<HTMLButtonElement>('[data-pivot-layout-ok]')?.addEventListener('click', async () => {
      const result = await actions.applySelectionPivotTable(config);
      if (result.ok) {
        closePivotLayoutDialog();
        return;
      }

      errorMessage = result.message ?? 'Could not create a pivot table.';
      render();
    });
  }

  dialog.addEventListener('click', (event) => {
    if (event.target === dialog) closePivotLayoutDialog();
  });

  document.body.appendChild(dialog);
  document.addEventListener('keydown', closePivotLayoutDialogOnEscape, true);
  render();
  dialog.querySelector<HTMLButtonElement>('[data-pivot-layout-ok]')?.focus();
}

function openPivotSourceDialog(actions: PivotTableActions) {
  closePivotSourceDialog();

  const source = actions.getSelectionPivotSource();
  const dialog = document.createElement('div');
  dialog.id = pivotSourceDialogId;
  dialog.className = 'spreadsheet-pivot-source-backdrop';
  dialog.innerHTML = `
    <div class="spreadsheet-pivot-window spreadsheet-pivot-source-dialog" role="dialog" aria-modal="true" aria-labelledby="spreadsheet-pivot-source-title">
      <div class="spreadsheet-pivot-titlebar">
        <span class="spreadsheet-pivot-window-dot spreadsheet-pivot-window-dot-red" aria-hidden="true"></span>
        <span class="spreadsheet-pivot-window-dot spreadsheet-pivot-window-dot-yellow" aria-hidden="true"></span>
        <span class="spreadsheet-pivot-window-dot spreadsheet-pivot-window-dot-disabled" aria-hidden="true"></span>
        <strong id="spreadsheet-pivot-source-title">Select Source</strong>
      </div>
      <div class="spreadsheet-pivot-source-content">
        <strong>Selection</strong>
        <label class="spreadsheet-pivot-radio spreadsheet-pivot-radio-disabled">
          <input type="radio" name="spreadsheet-pivot-source" disabled>
          <span>Named range:</span>
          <select disabled aria-label="Named range"></select>
        </label>
        <label class="spreadsheet-pivot-radio">
          <input type="radio" name="spreadsheet-pivot-source" checked>
          <span>Current selection</span>
        </label>
        <label class="spreadsheet-pivot-radio spreadsheet-pivot-radio-disabled">
          <input type="radio" name="spreadsheet-pivot-source" disabled>
          <span>Data source registered in Calc</span>
        </label>
        <div class="spreadsheet-pivot-source-range">${source ? `Range: ${escapeChartWizardAttribute(source.rangeA1)}` : 'Select a range with headers first.'}</div>
      </div>
      <div class="spreadsheet-pivot-footer">
        <button class="spreadsheet-pivot-button" type="button" tabindex="-1" aria-disabled="true">Help</button>
        <span class="spreadsheet-pivot-footer-spacer"></span>
        <button class="spreadsheet-pivot-button" type="button" data-pivot-source-cancel>Cancel</button>
        <button class="spreadsheet-pivot-button spreadsheet-pivot-button-primary" type="button" data-pivot-source-ok ${source ? '' : 'disabled'}>OK</button>
      </div>
    </div>
  `;

  dialog.addEventListener('click', (event) => {
    if (event.target === dialog) closePivotSourceDialog();
  });

  dialog.querySelector<HTMLButtonElement>('[data-pivot-source-cancel]')?.addEventListener('click', closePivotSourceDialog);
  dialog.querySelector<HTMLButtonElement>('[data-pivot-source-ok]')?.addEventListener('click', () => {
    if (!source) return;

    closePivotSourceDialog();
    openPivotLayoutDialog(actions, source);
  });

  document.body.appendChild(dialog);
  document.addEventListener('keydown', closePivotSourceDialogOnEscape, true);
  dialog.querySelector<HTMLButtonElement>('[data-pivot-source-ok]')?.focus();
}

export function renderSpreadsheetMockToolbar({ containerId, univerAPI, actions }: SpreadsheetMockToolbarOptions) {
  const container = document.getElementById(containerId);
  if (!container || container.dataset.mockToolbarRendered === 'true') return;

  const disabledFontControls = actions ? '' : 'disabled aria-disabled="true"';
  const canClickMockButton = (item: MockToolbarItem) => actions && (item.chart || item.filter || item.pivotTable || item.sparkline || item.sortAscending !== undefined);
  const canClickFormattingButton = (item: MockFormattingItem) => item.action || item.commandId || item.colorCommandId;

  container.dataset.mockToolbarRendered = 'true';
  container.innerHTML = `
    <div class="spreadsheet-mock-toolbar" role="toolbar" aria-label="Spreadsheet toolbar preview">
      <div class="spreadsheet-mock-toolbar-scroll">
        <div class="spreadsheet-mock-toolbar-row spreadsheet-mock-toolbar-row-icons">
          ${mockToolbarTopGroups
            .map(
              (group) => `
                <div class="spreadsheet-mock-toolbar-group">
                  ${group
                    .map(
                      (item) => `
                        <button
                          class="spreadsheet-mock-icon-button"
                          type="button"
                          tabindex="${canClickMockButton(item) ? '0' : '-1'}"
                          aria-disabled="${canClickMockButton(item) ? 'false' : 'true'}"
                          title="${item.label}"
                          aria-label="${item.label}"
                          ${item.filter ? 'data-spreadsheet-filter="true"' : ''}
                          ${item.chart ? 'data-spreadsheet-chart="true"' : ''}
                          ${item.sparkline ? 'data-spreadsheet-sparkline="true"' : ''}
                          ${item.pivotTable ? 'data-spreadsheet-pivot-table="true"' : ''}
                          ${item.sortAscending !== undefined ? `data-spreadsheet-sort-direction="${item.sortAscending ? 'ascending' : 'descending'}"` : ''}
                        >
                          ${item.icon}
                          ${item.sortAscending === undefined ? '<span class="spreadsheet-mock-caret" aria-hidden="true"></span>' : ''}
                        </button>
                      `,
                    )
                    .join('')}
                </div>
              `,
            )
            .join('')}
        </div>
        <div class="spreadsheet-mock-toolbar-row spreadsheet-mock-toolbar-row-format">
          <div class="spreadsheet-mock-toolbar-group">
            <select class="spreadsheet-mock-select spreadsheet-mock-select-font" data-spreadsheet-font-family aria-label="Font family" ${disabledFontControls}>
              ${mockFontFamilyOptions.map((fontFamily) => `<option value="${fontFamily}">${fontFamily}</option>`).join('')}
            </select>
            <select class="spreadsheet-mock-select spreadsheet-mock-select-size" data-spreadsheet-font-size aria-label="Font size" ${disabledFontControls}>
              ${mockFontSizeOptions
                .map((fontSize) => `<option value="${fontSize}" ${fontSize === 10 ? 'selected' : ''}>${fontSize} pt</option>`)
                .join('')}
            </select>
          </div>
          ${mockFormattingGroups
            .map(
              (group) => `
                <div class="spreadsheet-mock-toolbar-group">
                  ${group
                    .map(
                      (item) => `
                        <button
                          class="spreadsheet-mock-format-button"
                          type="button"
                          tabindex="${canClickFormattingButton(item) ? '0' : '-1'}"
                          aria-disabled="${canClickFormattingButton(item) ? 'false' : 'true'}"
                          title="${item.title}"
                          aria-label="${item.title}"
                          data-format-label="${item.label}"
                          ${item.action ? `data-spreadsheet-format-action="${item.action}"` : ''}
                          ${item.commandId ? `data-spreadsheet-command="${item.commandId}"` : ''}
                          ${item.colorCommandId ? `data-spreadsheet-color-command="${item.colorCommandId}"` : ''}
                        >
                          ${item.icon ?? item.label}
                        </button>
                      `,
                    )
                    .join('')}
                </div>
              `,
            )
            .join('')}
        </div>
        <div class="spreadsheet-mock-formula-row">
          <button class="spreadsheet-mock-name-box" type="button" tabindex="-1" aria-disabled="true">
            A23:B23
            <span class="spreadsheet-mock-select-arrow" aria-hidden="true"></span>
          </button>
          <span class="spreadsheet-mock-formula-fx" aria-hidden="true">fx</span>
          <span class="spreadsheet-mock-formula-sum" aria-hidden="true">Σ</span>
          <span class="spreadsheet-mock-formula-equals" aria-hidden="true">=</span>
          <input
            class="spreadsheet-mock-formula-input"
            type="text"
            data-spreadsheet-formula-input
            aria-label="Formula input"
            autocomplete="off"
            spellcheck="false"
          />
          <span class="spreadsheet-mock-formula-drop" aria-hidden="true"></span>
        </div>
      </div>
    </div>
  `;

  const formulaInput = container.querySelector<HTMLInputElement>('[data-spreadsheet-formula-input]');
  let formulaInputDirty = false;

  function commitFormulaInputValue() {
    if (!formulaInput || !formulaInputDirty) return;

    actions?.applySelectionInputValue(formulaInput.value);
    formulaInputDirty = false;
  }

  formulaInput?.addEventListener('input', () => {
    formulaInputDirty = true;
  });

  formulaInput?.addEventListener('keydown', (event) => {
    event.stopPropagation();

    if (event.key !== 'Enter') return;

    event.preventDefault();
    commitFormulaInputValue();
    formulaInput.blur();
  });

  formulaInput?.addEventListener('blur', commitFormulaInputValue);

  if (actions) {
    container.querySelector<HTMLSelectElement>('[data-spreadsheet-font-family]')?.addEventListener('change', (event) => {
      if (!(event.currentTarget instanceof HTMLSelectElement)) return;

      actions.applySelectionFontFamily(event.currentTarget.value);
    });

    container.querySelector<HTMLSelectElement>('[data-spreadsheet-font-size]')?.addEventListener('change', (event) => {
      if (!(event.currentTarget instanceof HTMLSelectElement)) return;

      const fontSize = Number(event.currentTarget.value);
      actions.applySelectionFontSize(fontSize);
    });
  }

  container.querySelectorAll<HTMLButtonElement>('[data-spreadsheet-format-action]').forEach((button) => {
    const action = button.dataset.spreadsheetFormatAction;

    button.addEventListener('click', (event) => {
      event.preventDefault();

      if (action === 'dateFormat') actions?.applySelectionDateFormat();
      if (action === 'mergeCells') void actions?.applySelectionMerge();
      if (action === 'numberFormat') actions?.applySelectionNumberFormat();
      if (action === 'percentFormat') actions?.applySelectionPercentFormat();
      if (action === 'unmergeCells') void actions?.applySelectionUnmerge();
    });
  });

  container.querySelectorAll<HTMLButtonElement>('[data-spreadsheet-sort-direction]').forEach((button) => {
    button.addEventListener('click', (event) => {
      event.preventDefault();
      actions?.applySelectionSort(button.dataset.spreadsheetSortDirection === 'ascending');
    });
  });

  container.querySelector<HTMLButtonElement>('[data-spreadsheet-filter]')?.addEventListener('click', (event) => {
    event.preventDefault();
    if (!actions) return;

    requestSelectionFilter(actions);
  });

  container.querySelector<HTMLButtonElement>('[data-spreadsheet-chart]')?.addEventListener('click', (event) => {
    event.preventDefault();
    if (!actions) return;

    openChartWizardDialog(actions);
  });

  container.querySelector<HTMLButtonElement>('[data-spreadsheet-sparkline]')?.addEventListener('click', (event) => {
    event.preventDefault();
    if (!univerAPI) return;

    void univerAPI.executeCommand(openSparklineSelectorOperationId);
  });

  container.querySelector<HTMLButtonElement>('[data-spreadsheet-pivot-table]')?.addEventListener('click', (event) => {
    event.preventDefault();
    if (!actions) return;

    openPivotSourceDialog(actions);
  });

  if (!univerAPI) return;
  const toolbarAPI = univerAPI;

  container.querySelectorAll<HTMLButtonElement>('[data-spreadsheet-command]').forEach((button) => {
    const commandId = button.dataset.spreadsheetCommand;
    if (!commandId) return;

    button.addEventListener('click', (event) => {
      event.preventDefault();
      void toolbarAPI.executeCommand(commandId);
    });
  });

  function closeMockColorPalette() {
    document.getElementById(mockColorPaletteMenuId)?.remove();
    document.removeEventListener('pointerdown', closeMockColorPaletteOnOutsideClick, true);
    document.removeEventListener('keydown', closeMockColorPaletteOnEscape, true);
  }

  function closeMockColorPaletteOnOutsideClick(event: PointerEvent) {
    const menu = document.getElementById(mockColorPaletteMenuId);
    if (!menu || !(event.target instanceof Node) || menu.contains(event.target)) return;

    closeMockColorPalette();
  }

  function closeMockColorPaletteOnEscape(event: KeyboardEvent) {
    if (event.key !== 'Escape') return;

    closeMockColorPalette();
  }

  function applyMockColor(commandId: string, color: string) {
    void toolbarAPI.executeCommand(commandId, { value: color });
    closeMockColorPalette();
  }

  function openNativeColorPicker(commandId: string) {
    const colorInput = document.createElement('input');

    colorInput.type = 'color';
    colorInput.className = mockNativeColorInputClassName;
    colorInput.value = commandId === fillColorCommandId ? '#ffffff' : '#000000';
    colorInput.addEventListener('input', (event) => {
      if (!(event.currentTarget instanceof HTMLInputElement)) return;

      void toolbarAPI.executeCommand(commandId, { value: event.currentTarget.value });
    });
    colorInput.addEventListener('change', () => {
      colorInput.remove();
    });

    document.body.appendChild(colorInput);

    try {
      if (typeof colorInput.showPicker === 'function') {
        colorInput.showPicker();
      } else {
        colorInput.click();
      }
    } catch {
      colorInput.click();
    }

    window.setTimeout(() => {
      colorInput.remove();
    }, 60_000);
  }

  function createPaletteColorButton(commandId: string, color: string) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'spreadsheet-mock-color-palette-button';
    button.title = color;
    button.setAttribute('aria-label', color);
    button.style.backgroundColor = color;
    button.addEventListener('click', (event) => {
      event.preventDefault();
      applyMockColor(commandId, color);
    });

    return button;
  }

  function openMockColorPalette(anchor: HTMLElement, commandId: string) {
    closeMockColorPalette();

    const menu = document.createElement('div');
    const anchorRect = anchor.getBoundingClientRect();
    const menuWidth = 218;
    const left = Math.max(8, Math.min(anchorRect.left, window.innerWidth - menuWidth - 8));
    const automaticColor = commandId === fillColorCommandId ? '#ffffff' : '#000000';
    const title = commandId === fillColorCommandId ? 'Fill Color' : 'Font Color';

    menu.id = mockColorPaletteMenuId;
    menu.className = 'spreadsheet-mock-color-palette-menu';
    menu.style.left = `${left}px`;
    menu.style.top = `${anchorRect.bottom + 6}px`;
    menu.setAttribute('role', 'menu');
    menu.innerHTML = `
      <div class="spreadsheet-mock-color-palette-title">${title}</div>
      <button class="spreadsheet-mock-color-palette-auto" type="button">
        <span class="spreadsheet-mock-color-palette-auto-swatch" aria-hidden="true"></span>
        <span>Automatic</span>
      </button>
      <div class="spreadsheet-mock-color-palette-section">
        <span>Standard</span>
        <span class="spreadsheet-mock-color-palette-section-caret" aria-hidden="true"></span>
      </div>
      <div class="spreadsheet-mock-color-palette-grid"></div>
      <button class="spreadsheet-mock-color-palette-custom" type="button">
        <span class="spreadsheet-mock-color-palette-wheel" aria-hidden="true"></span>
        <span>Custom Color...</span>
      </button>
    `;

    menu.querySelector<HTMLButtonElement>('.spreadsheet-mock-color-palette-auto')?.addEventListener('click', (event) => {
      event.preventDefault();
      applyMockColor(commandId, automaticColor);
    });

    menu.querySelector<HTMLButtonElement>('.spreadsheet-mock-color-palette-custom')?.addEventListener('click', (event) => {
      event.preventDefault();
      closeMockColorPalette();
      openNativeColorPicker(commandId);
    });

    menu.querySelector<HTMLElement>('.spreadsheet-mock-color-palette-grid')?.append(
      ...standardPaletteColors.map((color) => createPaletteColorButton(commandId, color)),
    );

    document.body.appendChild(menu);
    window.setTimeout(() => {
      document.addEventListener('pointerdown', closeMockColorPaletteOnOutsideClick, true);
      document.addEventListener('keydown', closeMockColorPaletteOnEscape, true);
    }, 0);
  }

  container.querySelectorAll<HTMLButtonElement>('[data-spreadsheet-color-command]').forEach((button) => {
    const commandId = button.dataset.spreadsheetColorCommand;
    if (!commandId) return;

    button.addEventListener('click', (event) => {
      event.preventDefault();
      openMockColorPalette(button, commandId);
    });
  });
}

type SpreadsheetUiMenu = {
  appendTo: (path: string | string[]) => void;
};

type SpreadsheetUiMenuItem = {
  action: string | (() => void);
  icon?: string;
  id: string;
  order?: number;
  title: string;
  tooltip?: string;
};

type SpreadsheetUiContext = {
  univerAPI: {
    createMenu: (item: SpreadsheetUiMenuItem) => SpreadsheetUiMenu;
    executeCommand: <P extends object = object, R = boolean>(id: string, params?: P) => Promise<R>;
  };
  actions: Pick<
    SpreadsheetActions,
    | 'applySelectionChart'
    | 'applySelectionBarChart'
    | 'applySelectionFilter'
    | 'applySelectionHeaderlessFilter'
    | 'applySelectionMerge'
    | 'applySelectionPivotTable'
    | 'applySelectionSort'
    | 'applySelectionUnmerge'
    | 'columnIndexToName'
    | 'getSelectionPivotSource'
    | 'getSelectionRangeTarget'
  >;
  conditionalFormattingCommandId: string;
};

export function setupSpreadsheetUi({
  univerAPI,
  actions,
  conditionalFormattingCommandId,
}: SpreadsheetUiContext) {
  univerAPI.createMenu({
    id: mergeCellsContextMenuItemId,
    title: 'Merge Cells',
    tooltip: 'Merge Cells',
    icon: 'MergeAllIcon',
    action: mergeCellsCommandId,
    order: 4,
  }).appendTo(['contextMenu.mainArea', 'contextMenu.layout']);

  univerAPI.createMenu({
    id: unmergeCellsContextMenuItemId,
    title: 'Unmerge Cells',
    tooltip: 'Unmerge Cells',
    icon: 'CancelMergeIcon',
    action: unmergeCellsCommandId,
    order: 5,
  }).appendTo(['contextMenu.mainArea', 'contextMenu.layout']);

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
      void actions.applySelectionSort(ascending);
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
    if (!actions.getSelectionRangeTarget()) return;

    document
      .querySelectorAll<HTMLElement>('[data-u-comp="rect-popup"] .univer-min-w-52')
      .forEach((menuPanel) => {
        if (menuPanel.querySelector(`#${headerFilterMenuItemId}`)) return;

        const wrapper = document.createElement('div');
        wrapper.id = headerFilterMenuItemId;
        wrapper.className = 'univer-relative';

        wrapper.append(
          createHeaderMenuButton('Filter', () => {
            document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
            window.setTimeout(() => requestSelectionFilter(actions), 0);
          }),
          createHeaderMenuButton('Sort', (button) => {
            openSortDirectionMenu(button);
            document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
          }),
          createHeaderMenuButton('Chart Wizard', () => {
            document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
            window.setTimeout(() => openChartWizardDialog(actions), 0);
          }),
          createHeaderMenuButton('Pivot Table', () => {
            document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
            window.setTimeout(() => openPivotSourceDialog(actions), 0);
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

  function createNumberFormatSidebarIcon() {
    return `
      <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <rect x="4" y="3" width="16" height="18" rx="1.5" fill="#f6f7f8" stroke="#6b7280" stroke-width="1.4" />
        <rect x="7" y="6" width="10" height="2" rx=".5" fill="#9ca3af" />
        <rect x="7" y="10" width="4" height="8" rx=".6" fill="#e5e7eb" stroke="#9ca3af" stroke-width="1" />
        <path d="M14 11h3M14 14h3M14 17h3" stroke="#4b5563" stroke-width="1.4" stroke-linecap="round" />
      </svg>
    `;
  }

  function createPropertiesSidebarIcon() {
    return `
      <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <path d="M4 19 9.4 4h2.5l5.4 15h-2.6l-1.2-3.5H7.8L6.6 19H4zm4.5-5.5h4.3l-2.1-6.2-2.2 6.2z" fill="#2f343b" />
        <path d="m13.5 16.8 6.4-6.4 1.9 1.9-6.4 6.4z" fill="#8f98a3" />
        <path d="m15.1 18.4 5.1-5.1 1.2 1.2-5.1 5.1z" fill="#415a9d" />
        <path d="M9.5 18.6c2.1-2.3 5.1-2.7 7.8-1.2-1.1 2.5-4.8 3.6-7.8 1.2z" fill="#2e6eea" />
        <path d="M11.1 18.2c1.7-1.2 3.9-1.2 5.6-.2-1 1.2-3.4 1.6-5.6.2z" fill="#ff8a00" />
        <path d="M7.2 20.5h9.8" stroke="#f15b2a" stroke-width="1.8" stroke-linecap="round" />
      </svg>
    `;
  }

  function createGallerySidebarIcon() {
    return `
      <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <defs>
          <linearGradient id="spreadsheet-sidebar-gallery-sky" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0" stop-color="#f1c6df" />
            <stop offset=".52" stop-color="#f2b16d" />
            <stop offset="1" stop-color="#f6df9e" />
          </linearGradient>
        </defs>
        <rect x="3.5" y="4" width="17" height="15" fill="#f2f2f2" stroke="#8c8f96" stroke-width="1.2" />
        <rect x="5.8" y="6.4" width="12.4" height="9.7" fill="url(#spreadsheet-sidebar-gallery-sky)" />
        <circle cx="15.8" cy="8.7" r="1.4" fill="#f5f1ce" />
        <path d="M5.9 16.1 9 12.7l2.7 2.5 2.4-2.2 4.1 3.1z" fill="#2d3138" />
      </svg>
    `;
  }

  function createNavigatorSidebarIcon() {
    return `
      <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <circle cx="12" cy="12" r="8.8" fill="#43a0ff" stroke="#1f5fc9" stroke-width="1.4" />
        <path d="m15.9 7.9-2.2 6.1-5.6 2.1 2.2-6.1z" fill="#f04f4a" stroke="#b62831" stroke-width=".8" stroke-linejoin="round" />
        <circle cx="12" cy="12" r="1.2" fill="#ffd26a" />
      </svg>
    `;
  }

  function createFunctionSidebarIcon() {
    return `
      <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <text x="4" y="18.5" fill="#0068ff" font-family="Georgia, serif" font-size="20" font-style="italic">fx</text>
      </svg>
    `;
  }

  function createFormattingSidebarButton({
    id,
    title,
    icon,
    onClick,
  }: {
    id?: string;
    title: string;
    icon: string;
    onClick?: (event: MouseEvent) => void;
  }) {
    const button = document.createElement('button');

    if (id) button.id = id;

    button.type = 'button';
    button.className = 'spreadsheet-formatting-sidebar-button';
    button.title = title;
    button.setAttribute('aria-label', title);
    button.innerHTML = icon;

    if (onClick) {
      button.addEventListener('click', onClick);
    } else {
      button.tabIndex = -1;
      button.setAttribute('aria-disabled', 'true');
    }

    return button;
  }

  function insertFormattingSidebarRail() {
    const body = document.getElementById('spreadsheet-body');
    if (!body) return;

    const rail = document.getElementById(formattingSidebarRailId) ?? document.createElement('div');
    if (rail.querySelector(`#${formattingSidebarButtonId}`)) return;

    rail.id = formattingSidebarRailId;
    rail.className = 'spreadsheet-formatting-sidebar-rail';

    rail.append(
      createFormattingSidebarButton({
        id: formattingSidebarButtonId,
        title: 'Number Format',
        icon: createNumberFormatSidebarIcon(),
        onClick: (event) => {
          event.preventDefault();
          void univerAPI.executeCommand(openNumberFormatPanelCommandId);
        },
      }),
      createFormattingSidebarButton({
        title: 'Properties',
        icon: createPropertiesSidebarIcon(),
      }),
      createFormattingSidebarButton({
        title: 'Gallery',
        icon: createGallerySidebarIcon(),
      }),
      createFormattingSidebarButton({
        title: 'Navigator',
        icon: createNavigatorSidebarIcon(),
      }),
      createFormattingSidebarButton({
        title: 'Functions',
        icon: createFunctionSidebarIcon(),
      }),
    );
    if (!rail.parentElement) {
      body.appendChild(rail);
    }
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
          requestSelectionFilter(actions);
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
        'Chart Wizard',
        `
        <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
          <path d="M4 19h16v2H4v-2zM7 9h3v8H7V9zm5-5h3v13h-3V4zm5 8h3v5h-3v-5z" />
        </svg>
      `,
        () => {
          openChartWizardDialog(actions);
        },
      );

      const sparklineButton = createStartToolbarButton(
        startSparklineToolbarButtonId,
        'Sparkline',
        mockToolbarIcon.sparkline,
        () => {
          void univerAPI.executeCommand(openSparklineSelectorOperationId);
        },
      );

      const pivotTableButton = createStartToolbarButton(
        startPivotTableToolbarButtonId,
        'Pivot Table',
        mockToolbarIcon.pivotTable,
        (event) => {
          event.preventDefault();
          openPivotSourceDialog(actions);
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

      buttonGroup.append(filterButton, sortButton, barChartButton, sparklineButton, pivotTableButton, conditionalFormattingButton);
      toolbar.appendChild(buttonGroup);
    });
  }

  new MutationObserver(insertStartToolbarButtons).observe(document.body, {
    childList: true,
    subtree: true,
  });
  window.setTimeout(insertStartToolbarButtons, 0);
  window.setTimeout(insertFormattingSidebarRail, 0);
}
