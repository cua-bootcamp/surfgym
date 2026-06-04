import type { SpreadsheetActions } from './spreadsheet-actions';

const fillColorCommandId = 'sheet.command.set-background-color';
const textColorCommandId = 'sheet.command.set-range-text-color';
const headerFilterMenuItemId = 'spreadsheet-header-filter-menu-item';
const startToolbarGroupId = 'spreadsheet-start-toolbar-group';
const startFilterToolbarButtonId = 'spreadsheet-start-filter-toolbar-button';
const startSortToolbarButtonId = 'spreadsheet-start-sort-toolbar-button';
const startBarChartToolbarButtonId = 'spreadsheet-start-bar-chart-toolbar-button';
const startConditionalFormattingToolbarButtonId = 'spreadsheet-start-conditional-formatting-toolbar-button';
const mockColorPaletteMenuId = 'spreadsheet-mock-color-palette-menu';
const mockNativeColorInputClassName = 'spreadsheet-mock-native-color-input';
const filterHeaderDialogId = 'spreadsheet-filter-header-dialog';
const sortDirectionMenuId = 'spreadsheet-sort-direction-menu';
const createConditionalFormattingRuleOperation = 1;
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
  filter?: boolean;
  sortAscending?: boolean;
};

type MockFormattingItem = {
  label: string;
  title: string;
  action?: 'dateFormat' | 'numberFormat' | 'percentFormat';
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
    | 'applySelectionFontFamily'
    | 'applySelectionFontSize'
    | 'applySelectionHeaderlessFilter'
    | 'applySelectionNumberFormat'
    | 'applySelectionPercentFormat'
    | 'applySelectionSort'
    | 'getSelectionRangeTarget'
  >;
};

type FilterHeaderPreference = 'unknown' | 'use-first-line' | 'headerless';
type FilterActions = Pick<SpreadsheetActions, 'applySelectionFilter' | 'applySelectionHeaderlessFilter' | 'getSelectionRangeTarget'>;

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
      <text x="13" y="10" fill="#333" font-family="Arial" font-size="7" font-weight="700">A</text>
      <text x="13" y="19" fill="#333" font-family="Arial" font-size="7" font-weight="700">Z</text>
    </svg>
  `,
  sortDescending: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path fill="#2e6eea" d="M7 4h3v12h3l-4.5 5L4 16h3z" />
      <text x="13" y="10" fill="#333" font-family="Arial" font-size="7" font-weight="700">Z</text>
      <text x="13" y="19" fill="#333" font-family="Arial" font-size="7" font-weight="700">A</text>
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
    { label: 'Insert Chart', icon: mockToolbarIcon.chart },
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
    // { label: 'Merge', title: 'Merge Cells' },
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

export function renderSpreadsheetMockToolbar({ containerId, univerAPI, actions }: SpreadsheetMockToolbarOptions) {
  const container = document.getElementById(containerId);
  if (!container || container.dataset.mockToolbarRendered === 'true') return;

  const disabledFontControls = actions ? '' : 'disabled aria-disabled="true"';
  const canClickMockButton = (item: MockToolbarItem) => actions && (item.filter || item.sortAscending !== undefined);
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
          <div class="spreadsheet-mock-formula-input" aria-hidden="true"></div>
          <span class="spreadsheet-mock-formula-drop" aria-hidden="true"></span>
        </div>
      </div>
    </div>
  `;

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
      if (action === 'numberFormat') actions?.applySelectionNumberFormat();
      if (action === 'percentFormat') actions?.applySelectionPercentFormat();
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

  if (!univerAPI) return;

  container.querySelectorAll<HTMLButtonElement>('[data-spreadsheet-command]').forEach((button) => {
    const commandId = button.dataset.spreadsheetCommand;
    if (!commandId) return;

    button.addEventListener('click', (event) => {
      event.preventDefault();
      void univerAPI.executeCommand(commandId);
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
    void univerAPI.executeCommand(commandId, { value: color });
    closeMockColorPalette();
  }

  function openNativeColorPicker(commandId: string) {
    const colorInput = document.createElement('input');

    colorInput.type = 'color';
    colorInput.className = mockNativeColorInputClassName;
    colorInput.value = commandId === fillColorCommandId ? '#ffffff' : '#000000';
    colorInput.addEventListener('input', (event) => {
      if (!(event.currentTarget instanceof HTMLInputElement)) return;

      void univerAPI.executeCommand(commandId, { value: event.currentTarget.value });
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

type SpreadsheetUiContext = {
  univerAPI: {
    executeCommand: <P extends object = object, R = boolean>(id: string, params?: P) => Promise<R>;
  };
  actions: Pick<
    SpreadsheetActions,
    | 'applySelectionBarChart'
    | 'applySelectionFilter'
    | 'applySelectionHeaderlessFilter'
    | 'applySelectionSort'
    | 'getSelectionRangeTarget'
  >;
  conditionalFormattingCommandId: string;
};

export function setupSpreadsheetUi({
  actions,
  conditionalFormattingCommandId,
}: SpreadsheetUiContext) {
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
          createHeaderMenuButton('Bar Chart', () => {
            void actions.applySelectionBarChart();
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
        'Bar Chart',
        `
        <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
          <path d="M4 19h16v2H4v-2zM7 9h3v8H7V9zm5-5h3v13h-3V4zm5 8h3v5h-3v-5z" />
        </svg>
      `,
        () => {
          void actions.applySelectionBarChart();
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
}
