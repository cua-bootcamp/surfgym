// import { NamedStyleType } from '@univerjs/presets';

// type WordToolbarApi = {
//   executeCommand: <P extends object = object, R = boolean>(id: string, params?: P) => Promise<R>;
// };

// type WordToolbarAction = 'print' | 'textColor' | 'highlightColor' | 'lineSpacing' | 'table';

// type WordToolbarOptions = {
//   containerId: string;
//   getLineSpacing?: () => number;
//   setLineSpacing?: (lineSpacing: number) => void;
//   insertTable?: (rows: number, columns: number) => void;
//   univerAPI?: WordToolbarApi;
// };

// type WordToolbarItem = {
//   label: string;
//   icon: string;
//   commandId?: string;
//   params?: Record<string, unknown>;
//   action?: WordToolbarAction;
// };

// type WordFormattingItem = {
//   label: string;
//   title: string;
//   icon?: string;
//   commandId?: string;
//   params?: Record<string, unknown>;
//   action?: WordToolbarAction;
// };

// const wordCommandIds = {
//   undo: 'univer.command.undo',
//   redo: 'univer.command.redo',
//   bold: 'doc.command.set-inline-format-bold',
//   italic: 'doc.command.set-inline-format-italic',
//   underline: 'doc.command.set-inline-format-underline',
//   strikethrough: 'doc.command.set-inline-format-strikethrough',
//   subscript: 'doc.command.set-inline-format-subscript',
//   superscript: 'doc.command.set-inline-format-superscript',
//   fontFamily: 'doc.command.set-inline-format-font-family',
//   fontSize: 'doc.command.set-inline-format-fontsize',
//   textColor: 'doc.command.set-inline-format-text-color',
//   highlightColor: 'doc.command.set-inline-format-text-background-color',
//   alignLeft: 'doc.command.align-left',
//   alignCenter: 'doc.command.align-center',
//   alignRight: 'doc.command.align-right',
//   alignJustify: 'doc.command.align-justify',
//   bulletList: 'doc.command.bullet-list',
//   orderList: 'doc.command.order-list',
//   checklist: 'doc.command.check-list',
//   paragraphStyle: 'doc.command.set-paragraph-named-style',
//   table: 'doc.command.create-table',
//   horizontalLine: 'doc.command.horizontal-line',
//   headerFooter: 'doc.command.open-header-footer-panel',
//   pageSetup: 'docs.operation.open-page-setting',
//   documentFlavor: 'doc.command.switch-mode',
// } as const;

// const wordParagraphStyleOptions = [
//   { label: 'Default Paragraph Style', value: NamedStyleType.NORMAL_TEXT },
//   { label: 'Title', value: NamedStyleType.TITLE },
//   { label: 'Subtitle', value: NamedStyleType.SUBTITLE },
//   { label: 'Heading 1', value: NamedStyleType.HEADING_1 },
//   { label: 'Heading 2', value: NamedStyleType.HEADING_2 },
//   { label: 'Heading 3', value: NamedStyleType.HEADING_3 },
// ] as const;

// const wordFontFamilyOptions = ['나눔고딕', 'Arial', 'Calibri', 'Liberation Serif', 'Times New Roman', 'Courier New'] as const;
// const wordFontSizeOptions = [8, 9, 10, 11, 12, 14, 16, 18, 20, 24, 28, 32, 36, 48] as const;

// const wordPaletteColors = [
//   '#000000', '#3f3f3f', '#7f7f7f', '#bfbfbf', '#ffffff', '#1d4ed8', '#2563eb', '#38bdf8',
//   '#166534', '#22c55e', '#84cc16', '#facc15', '#f97316', '#ef4444', '#b91c1c', '#db2777',
//   '#9333ea', '#6d28d9', '#4f46e5', '#0f766e', '#0e7490', '#a16207', '#78350f', '#64748b',
// ] as const;

// const wordLineSpacingOptions = [1, 1.15, 1.5, 2] as const;
// const wordTablePickerRows = 16;
// const wordTablePickerColumns = 10;
// const wordTablePickerCellSize = 30;
// const wordTablePickerGridTop = 49;
// const wordTablePickerGridLeft = 14;
// const wordTableStyleOptions = [
//   'None',
//   'Default Table Style',
//   'Academic',
//   'Box List Blue',
//   'Box List Green',
//   'Box List Red',
//   'Box List Yellow',
//   'Elegant',
// ] as const;

// const icon = {
//   blankPage: `
//     <svg viewBox="0 0 24 24" aria-hidden="true">
//       <path fill="#fff" stroke="#9aa4b2" d="M6 3h8l4 4v14H6z" />
//       <path fill="#e9eef5" d="M14 3v5h5z" />
//       <path fill="#d12222" d="M4 13h8v8H4z" />
//       <text x="8" y="19" text-anchor="middle" font-size="7" font-weight="700" fill="#fff">Z</text>
//     </svg>
//   `,
//   copyPages: `
//     <svg viewBox="0 0 24 24" aria-hidden="true">
//       <path fill="#f7f9fc" stroke="#8f9baa" d="M7 5h11v14H7z" />
//       <path fill="#fff" stroke="#8f9baa" d="M4 8h11v13H4z" />
//     </svg>
//   `,
//   open: `
//     <svg viewBox="0 0 24 24" aria-hidden="true">
//       <path fill="#f6c85f" stroke="#9b7a20" d="M3 7h7l2 2h9v10H3z" />
//       <path fill="#ffd976" d="M4 10h16l-2 8H2z" />
//     </svg>
//   `,
//   save: `
//     <svg viewBox="0 0 24 24" aria-hidden="true">
//       <path fill="#5d7897" stroke="#34465b" d="M4 4h14l2 2v14H4z" />
//       <path fill="#fff" d="M7 5h9v5H7z" />
//       <path fill="#26394f" d="M7 15h10v5H7z" />
//       <circle cx="17" cy="18" r="3" fill="#d62828" />
//     </svg>
//   `,
//   pdf: `
//     <svg viewBox="0 0 24 24" aria-hidden="true">
//       <path fill="#fff" stroke="#a8b0bc" d="M6 3h8l4 4v14H6z" />
//       <path fill="#e74c3c" d="M5 15h14v5H5z" />
//       <text x="12" y="19" text-anchor="middle" font-size="5" font-weight="700" fill="#fff">PDF</text>
//     </svg>
//   `,
//   print: `
//     <svg viewBox="0 0 24 24" aria-hidden="true">
//       <path fill="#fff" stroke="#7c8794" d="M7 3h10v6H7z" />
//       <path fill="#dfe6ee" stroke="#7c8794" d="M4 9h16v8H4z" />
//       <path fill="#fff" stroke="#7c8794" d="M7 14h10v7H7z" />
//       <circle cx="18" cy="12" r="1" fill="#4b5563" />
//     </svg>
//   `,
//   search: `
//     <svg viewBox="0 0 24 24" aria-hidden="true">
//       <path fill="#fff" stroke="#8aa1c1" d="M6 3h9l3 3v15H6z" />
//       <circle cx="11" cy="11" r="4" fill="none" stroke="#2468c9" stroke-width="2" />
//       <path stroke="#2468c9" stroke-width="2" d="m14 14 5 5" />
//     </svg>
//   `,
//   cut: `
//     <svg viewBox="0 0 24 24" aria-hidden="true">
//       <circle cx="7" cy="7" r="3" fill="#e8ebef" stroke="#8c96a3" />
//       <circle cx="7" cy="17" r="3" fill="#e8ebef" stroke="#8c96a3" />
//       <path stroke="#8c96a3" stroke-width="2" d="m9 9 10 10M9 15 19 5" />
//     </svg>
//   `,
//   paste: `
//     <svg viewBox="0 0 24 24" aria-hidden="true">
//       <path fill="#c7ccd3" d="M8 4h8v4H8z" />
//       <path fill="#eceff3" stroke="#9aa4b2" d="M5 7h14v14H5z" />
//       <path fill="#fff" d="M8 11h8v2H8zm0 4h7v2H8z" />
//     </svg>
//   `,
//   brush: `
//     <svg viewBox="0 0 24 24" aria-hidden="true">
//       <path fill="#f28c38" stroke="#9a4b18" d="m14 4 6 3-8 9-4-4z" />
//       <path fill="#2468c9" d="M7 13c-3 1-4 4-4 7 3 0 6-1 7-4z" />
//     </svg>
//   `,
//   undo: `
//     <svg viewBox="0 0 24 24" aria-hidden="true">
//       <path fill="none" stroke="#2563eb" stroke-width="3" d="M10 7 5 12l5 5" />
//       <path fill="none" stroke="#2563eb" stroke-width="3" d="M6 12h8a5 5 0 0 1 5 5" />
//     </svg>
//   `,
//   redo: `
//     <svg viewBox="0 0 24 24" aria-hidden="true">
//       <path fill="none" stroke="#9ba3ad" stroke-width="3" d="m14 7 5 5-5 5" />
//       <path fill="none" stroke="#9ba3ad" stroke-width="3" d="M18 12h-8a5 5 0 0 0-5 5" />
//     </svg>
//   `,
//   binoculars: `
//     <svg viewBox="0 0 24 24" aria-hidden="true">
//       <path fill="#334155" d="M5 9h5v9H3v-6a3 3 0 0 1 2-3zm9 0h5a3 3 0 0 1 2 3v6h-7z" />
//       <path fill="#64748b" d="M8 5h3v5H8zm5 0h3v5h-3z" />
//       <circle cx="7" cy="18" r="3" fill="#1f2937" />
//       <circle cx="17" cy="18" r="3" fill="#1f2937" />
//     </svg>
//   `,
//   spell: `
//     <svg viewBox="0 0 24 24" aria-hidden="true">
//       <text x="4" y="11" font-size="9" font-weight="700" fill="#334155">ABC</text>
//       <path fill="none" stroke="#22a447" stroke-width="2" d="m6 16 3 3 8-8" />
//     </svg>
//   `,
//   paragraph: `
//     <svg viewBox="0 0 24 24" aria-hidden="true">
//       <path fill="#2563eb" d="M18 4v16h-2V6h-3v14h-2V6a5 5 0 0 0 0 10v2A7 7 0 1 1 11 4z" />
//     </svg>
//   `,
//   table: `
//     <svg viewBox="0 0 24 24" aria-hidden="true">
//       <path fill="#6b9ed6" stroke="#2d5d94" d="M3 5h18v15H3z" />
//       <path stroke="#fff" d="M3 10h18M3 15h18M9 5v15M15 5v15" />
//     </svg>
//   `,
//   image: `
//     <svg viewBox="0 0 24 24" aria-hidden="true">
//       <path fill="#e7f0fb" stroke="#7991ac" d="M4 5h16v14H4z" />
//       <circle cx="16" cy="9" r="2" fill="#f6c85f" />
//       <path fill="#42a85f" d="m5 18 5-6 4 4 2-3 4 5z" />
//     </svg>
//   `,
//   chart: `
//     <svg viewBox="0 0 24 24" aria-hidden="true">
//       <path fill="#42a85f" d="M5 10h3v9H5z" />
//       <path fill="#f6c85f" d="M11 6h3v13h-3z" />
//       <path fill="#4f8fe8" d="M17 3h3v16h-3z" />
//     </svg>
//   `,
//   link: `
//     <svg viewBox="0 0 24 24" aria-hidden="true">
//       <path fill="none" stroke="#697582" stroke-width="2" d="M8 12h8" />
//       <path fill="none" stroke="#697582" stroke-width="2" d="M9 8H6a4 4 0 0 0 0 8h3m6-8h3a4 4 0 0 1 0 8h-3" />
//     </svg>
//   `,
//   omega: `
//     <svg viewBox="0 0 24 24" aria-hidden="true">
//       <text x="4" y="18" font-size="20" font-weight="600" fill="#2563eb">Ω</text>
//     </svg>
//   `,
//   globe: `
//     <svg viewBox="0 0 24 24" aria-hidden="true">
//       <circle cx="12" cy="12" r="9" fill="#e8f2ff" stroke="#2563eb" />
//       <path fill="none" stroke="#2563eb" d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18" />
//     </svg>
//   `,
//   comment: `
//     <svg viewBox="0 0 24 24" aria-hidden="true">
//       <path fill="#eef1f5" stroke="#9aa4b2" d="M4 5h16v11H9l-5 4z" />
//     </svg>
//   `,
//   shapes: `
//     <svg viewBox="0 0 24 24" aria-hidden="true">
//       <path fill="none" stroke="#2563eb" stroke-width="2" d="m5 12 5-5 5 5-5 5z" />
//       <circle cx="17" cy="16" r="4" fill="none" stroke="#6aa1e8" stroke-width="2" />
//     </svg>
//   `,
//   fillBucket: `
//     <svg viewBox="0 0 24 24" aria-hidden="true">
//       <path fill="#ffe96b" stroke="#9a7b00" d="m6 12 7-7 6 6-7 7z" />
//       <path fill="#facc15" d="M4 19h16v3H4z" />
//     </svg>
//   `,
//   alignLeft: `
//     <svg viewBox="0 0 24 24" aria-hidden="true">
//       <path fill="#334155" d="M4 5h16v2H4zm0 4h11v2H4zm0 4h16v2H4zm0 4h11v2H4z" />
//     </svg>
//   `,
//   alignCenter: `
//     <svg viewBox="0 0 24 24" aria-hidden="true">
//       <path fill="#334155" d="M4 5h16v2H4zm3 4h10v2H7zm-3 4h16v2H4zm3 4h10v2H7z" />
//     </svg>
//   `,
//   alignRight: `
//     <svg viewBox="0 0 24 24" aria-hidden="true">
//       <path fill="#334155" d="M4 5h16v2H4zm5 4h11v2H9zm-5 4h16v2H4zm5 4h11v2H9z" />
//     </svg>
//   `,
//   alignJustify: `
//     <svg viewBox="0 0 24 24" aria-hidden="true">
//       <path fill="#334155" d="M4 5h16v2H4zm0 4h16v2H4zm0 4h16v2H4zm0 4h16v2H4z" />
//     </svg>
//   `,
//   bullets: `
//     <svg viewBox="0 0 24 24" aria-hidden="true">
//       <path fill="#2563eb" d="M5 7a2 2 0 1 0 0 .1zm0 5a2 2 0 1 0 0 .1zm0 5a2 2 0 1 0 0 .1z" />
//       <path stroke="#334155" stroke-width="2" d="M10 7h10M10 12h10M10 17h10" />
//     </svg>
//   `,
//   numbering: `
//     <svg viewBox="0 0 24 24" aria-hidden="true">
//       <text x="3" y="8" font-size="6" fill="#2563eb">1</text>
//       <text x="3" y="14" font-size="6" fill="#2563eb">2</text>
//       <text x="3" y="20" font-size="6" fill="#2563eb">3</text>
//       <path stroke="#334155" stroke-width="2" d="M10 7h10M10 13h10M10 19h10" />
//     </svg>
//   `,
//   indentDecrease: `
//     <svg viewBox="0 0 24 24" aria-hidden="true">
//       <path fill="#2563eb" d="m4 12 5-4v8z" />
//       <path stroke="#334155" stroke-width="2" d="M11 6h9M11 11h9M11 16h9" />
//     </svg>
//   `,
//   indentIncrease: `
//     <svg viewBox="0 0 24 24" aria-hidden="true">
//       <path fill="#2563eb" d="m10 12-5-4v8z" />
//       <path stroke="#334155" stroke-width="2" d="M12 6h8M12 11h8M12 16h8" />
//     </svg>
//   `,
//   lineSpacing: `
//     <svg viewBox="0 0 24 24" aria-hidden="true">
//       <path stroke="#334155" stroke-width="2" d="M9 6h11M9 12h11M9 18h11" />
//       <path fill="#2563eb" d="m5 4 3 3H2zm0 16 3-3H2z" />
//       <path stroke="#2563eb" stroke-width="2" d="M5 7v10" />
//     </svg>
//   `,
//   showFormatting: `
//     <svg viewBox="0 0 24 24" aria-hidden="true">
//       <path fill="#1d4ed8" d="M18 4v16h-2V6h-3v14h-2V6a5 5 0 0 0 0 10v2A7 7 0 1 1 11 4z" />
//       <path fill="#1d4ed8" d="M20 18h2v2h-2z" />
//     </svg>
//   `,
// } as const;

// const wordTopGroups: readonly (readonly WordToolbarItem[])[] = [
//   [
//     { label: 'New Document', icon: icon.blankPage },
//     { label: 'Open', icon: icon.open },
//     { label: 'Templates', icon: icon.copyPages },
//     { label: 'Save', icon: icon.save },
//   ],
//   [
//     { label: 'Export Directly as PDF', icon: icon.pdf },
//     { label: 'Print', icon: icon.print, action: 'print' },
//     { label: 'Find', icon: icon.search },
//   ],
//   [
//     { label: 'Cut', icon: icon.cut },
//     { label: 'Copy', icon: icon.copyPages },
//     { label: 'Paste', icon: icon.paste },
//     { label: 'Format Paintbrush', icon: icon.brush },
//   ],
//   [
//     { label: 'Undo', icon: icon.undo, commandId: wordCommandIds.undo },
//     { label: 'Redo', icon: icon.redo, commandId: wordCommandIds.redo },
//     { label: 'Find and Replace', icon: icon.binoculars },
//     { label: 'Spelling', icon: icon.spell },
//     { label: 'Formatting Marks', icon: icon.paragraph },
//   ],
//   [
//     { label: 'Insert Table', icon: icon.table, action: 'table' },
//     { label: 'Insert Image', icon: icon.image },
//     { label: 'Insert Chart', icon: icon.chart },
//     { label: 'Text Box', icon: icon.paragraph },
//     { label: 'Horizontal Line', icon: icon.shapes, commandId: wordCommandIds.horizontalLine },
//   ],
//   [
//     { label: 'Hyperlink', icon: icon.link },
//     { label: 'Special Character', icon: icon.omega },
//     { label: 'Header and Footer', icon: icon.blankPage, commandId: wordCommandIds.headerFooter },
//     { label: 'Page Settings', icon: icon.copyPages, commandId: wordCommandIds.pageSetup },
//     { label: 'Online', icon: icon.globe },
//     { label: 'Comment', icon: icon.comment },
//     { label: 'Shapes', icon: icon.shapes },
//   ],
// ];

// const wordFormattingGroups: readonly (readonly WordFormattingItem[])[] = [
//   [
//     { label: 'B', title: 'Bold', commandId: wordCommandIds.bold },
//     { label: 'I', title: 'Italic', commandId: wordCommandIds.italic },
//     { label: 'U', title: 'Underline', commandId: wordCommandIds.underline },
//     { label: 'abc', title: 'Strikethrough', commandId: wordCommandIds.strikethrough },
//     { label: 'x²', title: 'Superscript', commandId: wordCommandIds.superscript },
//     { label: 'x₂', title: 'Subscript', commandId: wordCommandIds.subscript },
//   ],
//   [
//     { label: 'A', title: 'Font Color', action: 'textColor' },
//     { label: 'A', title: 'Highlight Color', action: 'highlightColor', icon: icon.fillBucket },
//   ],
//   [
//     { label: 'L', title: 'Align Left', icon: icon.alignLeft, commandId: wordCommandIds.alignLeft },
//     { label: 'C', title: 'Align Center', icon: icon.alignCenter, commandId: wordCommandIds.alignCenter },
//     { label: 'R', title: 'Align Right', icon: icon.alignRight, commandId: wordCommandIds.alignRight },
//     { label: 'J', title: 'Justify', icon: icon.alignJustify, commandId: wordCommandIds.alignJustify },
//   ],
//   [
//     { label: 'Bullets', title: 'Bulleted List', icon: icon.bullets, commandId: wordCommandIds.bulletList },
//     { label: 'Numbering', title: 'Numbered List', icon: icon.numbering, commandId: wordCommandIds.orderList },
//     { label: 'Checklist', title: 'Checklist', icon: icon.spell, commandId: wordCommandIds.checklist },
//   ],
//   [
//     { label: 'Indent-', title: 'Decrease Indent', icon: icon.indentDecrease },
//     { label: 'Indent+', title: 'Increase Indent', icon: icon.indentIncrease },
//     { label: 'Line', title: 'Line Spacing', icon: icon.lineSpacing, action: 'lineSpacing' },
//     { label: 'Marks', title: 'Show Formatting Marks', icon: icon.showFormatting },
//   ],
// ];

// const executeToolbarCommand = (
//   univerAPI: WordToolbarApi | undefined,
//   commandId: string,
//   params?: Record<string, unknown>,
// ) => {
//   if (!univerAPI) return;

//   void univerAPI.executeCommand(commandId, params).catch(() => undefined);
// };

// const closeWordColorPalette = () => {
//   document.getElementById('word-mock-color-palette-menu')?.remove();
//   document.removeEventListener('pointerdown', closeWordColorPaletteOnOutsideClick, true);
//   document.removeEventListener('keydown', closeWordColorPaletteOnEscape, true);
// };

// const closeWordLineSpacingMenu = () => {
//   document.getElementById('word-mock-line-spacing-menu')?.remove();
//   document.removeEventListener('pointerdown', closeWordLineSpacingOnOutsideClick, true);
//   document.removeEventListener('keydown', closeWordLineSpacingOnEscape, true);
// };

// const closeWordTablePickerMenu = () => {
//   document.getElementById('word-mock-table-picker-menu')?.remove();
//   document.removeEventListener('pointerdown', closeWordTablePickerOnOutsideClick, true);
//   document.removeEventListener('keydown', closeWordTablePickerOnEscape, true);
// };

// const closeWordTableOptionsDialog = () => {
//   document.getElementById('word-mock-table-options-dialog')?.remove();
//   document.removeEventListener('keydown', closeWordTableOptionsOnEscape, true);
// };

// function closeWordColorPaletteOnOutsideClick(event: PointerEvent) {
//   const menu = document.getElementById('word-mock-color-palette-menu');
//   if (!menu || !(event.target instanceof Node) || menu.contains(event.target)) return;

//   closeWordColorPalette();
// }

// function closeWordColorPaletteOnEscape(event: KeyboardEvent) {
//   if (event.key !== 'Escape') return;

//   closeWordColorPalette();
// }

// const createColorButton = (
//   univerAPI: WordToolbarApi | undefined,
//   commandId: string,
//   color: string,
// ) => {
//   const button = document.createElement('button');
//   button.type = 'button';
//   button.className = 'word-mock-color-palette-button';
//   button.title = color;
//   button.setAttribute('aria-label', color);
//   button.style.backgroundColor = color;
//   button.addEventListener('click', (event) => {
//     event.preventDefault();
//     executeToolbarCommand(univerAPI, commandId, { value: color });
//     closeWordColorPalette();
//   });

//   return button;
// };

// const openWordColorPalette = (
//   univerAPI: WordToolbarApi | undefined,
//   anchor: HTMLElement,
//   action: 'textColor' | 'highlightColor',
// ) => {
//   closeWordLineSpacingMenu();
//   closeWordTablePickerMenu();
//   closeWordColorPalette();

//   const commandId = action === 'textColor' ? wordCommandIds.textColor : wordCommandIds.highlightColor;
//   const title = action === 'textColor' ? 'Font Color' : 'Highlight Color';
//   const menu = document.createElement('div');
//   const anchorRect = anchor.getBoundingClientRect();
//   const menuWidth = 198;
//   const left = Math.max(8, Math.min(anchorRect.left, window.innerWidth - menuWidth - 8));

//   menu.id = 'word-mock-color-palette-menu';
//   menu.className = 'word-mock-color-palette-menu';
//   menu.style.left = `${left}px`;
//   menu.style.top = `${anchorRect.bottom + 6}px`;
//   menu.setAttribute('role', 'menu');
//   menu.innerHTML = `
//     <div class="word-mock-color-palette-title">${title}</div>
//     <div class="word-mock-color-palette-grid"></div>
//   `;

//   menu.querySelector<HTMLElement>('.word-mock-color-palette-grid')?.append(
//     ...wordPaletteColors.map((color) => createColorButton(univerAPI, commandId, color)),
//   );

//   document.body.appendChild(menu);
//   window.setTimeout(() => {
//     document.addEventListener('pointerdown', closeWordColorPaletteOnOutsideClick, true);
//     document.addEventListener('keydown', closeWordColorPaletteOnEscape, true);
//   }, 0);
// };

// function closeWordLineSpacingOnOutsideClick(event: PointerEvent) {
//   const menu = document.getElementById('word-mock-line-spacing-menu');
//   if (!menu || !(event.target instanceof Node) || menu.contains(event.target)) return;

//   closeWordLineSpacingMenu();
// }

// function closeWordLineSpacingOnEscape(event: KeyboardEvent) {
//   if (event.key !== 'Escape') return;

//   closeWordLineSpacingMenu();
// }

// const formatLineSpacingValue = (value: number) => {
//   const normalized = Math.round(value * 100) / 100;
//   return Number.isInteger(normalized) ? String(normalized) : String(normalized);
// };

// const normalizeLineSpacingValue = (value: number) => {
//   if (!Number.isFinite(value) || value <= 0) return null;

//   return Math.round(value * 100) / 100;
// };

// const isPresetLineSpacing = (value: number) =>
//   wordLineSpacingOptions.some((option) => Math.abs(option - value) < 0.001);

// const createLineSpacingButton = (
//   currentValue: number,
//   setLineSpacing: (lineSpacing: number) => void,
//   value: number,
// ) => {
//   const button = document.createElement('button');
//   button.type = 'button';
//   button.className = 'word-mock-line-spacing-option';
//   button.dataset.lineSpacingValue = String(value);
//   button.setAttribute('aria-current', Math.abs(currentValue - value) < 0.001 ? 'true' : 'false');
//   button.innerHTML = `
//     ${icon.lineSpacing}
//     <span>Spacing: ${formatLineSpacingValue(value)}</span>
//   `;
//   button.addEventListener('click', (event) => {
//     event.preventDefault();
//     setLineSpacing(value);
//     closeWordLineSpacingMenu();
//   });

//   return button;
// };

// const openWordLineSpacingMenu = (
//   anchor: HTMLElement,
//   setLineSpacing: (lineSpacing: number) => void,
//   getLineSpacing?: () => number,
// ) => {
//   closeWordColorPalette();
//   closeWordTablePickerMenu();
//   closeWordLineSpacingMenu();

//   const currentValue = normalizeLineSpacingValue(getLineSpacing?.() ?? 1) ?? 1;
//   const menu = document.createElement('div');
//   const anchorRect = anchor.getBoundingClientRect();
//   const menuWidth = 302;
//   const left = Math.max(8, Math.min(anchorRect.left, window.innerWidth - menuWidth - 8));

//   menu.id = 'word-mock-line-spacing-menu';
//   menu.className = 'word-mock-line-spacing-menu';
//   menu.style.left = `${left}px`;
//   menu.style.top = `${anchorRect.bottom + 6}px`;
//   menu.setAttribute('role', 'menu');
//   menu.innerHTML = `
//     <div class="word-mock-line-spacing-options"></div>
//     <div class="word-mock-line-spacing-custom-title">Custom Value</div>
//     <label class="word-mock-line-spacing-control">
//       <span>Line Spacing:</span>
//       <select data-line-spacing-mode>
//         <option value="single">Single</option>
//         <option value="custom">Custom</option>
//       </select>
//     </label>
//     <label class="word-mock-line-spacing-control word-mock-line-spacing-value-row">
//       <span>Value:</span>
//       <input data-line-spacing-custom-value type="number" min="0.1" max="10" step="0.05" value="${formatLineSpacingValue(currentValue)}" />
//     </label>
//   `;

//   menu.querySelector<HTMLElement>('.word-mock-line-spacing-options')?.append(
//     ...wordLineSpacingOptions.map((value) => createLineSpacingButton(currentValue, setLineSpacing, value)),
//   );

//   const modeSelect = menu.querySelector<HTMLSelectElement>('[data-line-spacing-mode]');
//   const customInput = menu.querySelector<HTMLInputElement>('[data-line-spacing-custom-value]');
//   const isCustomValue = !isPresetLineSpacing(currentValue);
//   if (modeSelect) modeSelect.value = isCustomValue ? 'custom' : 'single';
//   if (customInput) customInput.disabled = !isCustomValue;

//   const applyCustomValue = () => {
//     if (!customInput) return;

//     const value = normalizeLineSpacingValue(Number(customInput.value));
//     if (value === null) return;

//     setLineSpacing(value);
//     closeWordLineSpacingMenu();
//   };

//   modeSelect?.addEventListener('change', () => {
//     if (!customInput || !modeSelect) return;

//     if (modeSelect.value === 'single') {
//       setLineSpacing(1);
//       closeWordLineSpacingMenu();
//       return;
//     }

//     customInput.disabled = false;
//     customInput.focus();
//     customInput.select();
//   });

//   customInput?.addEventListener('keydown', (event) => {
//     if (event.key !== 'Enter') return;

//     event.preventDefault();
//     applyCustomValue();
//   });
//   customInput?.addEventListener('change', applyCustomValue);

//   document.body.appendChild(menu);
//   window.setTimeout(() => {
//     document.addEventListener('pointerdown', closeWordLineSpacingOnOutsideClick, true);
//     document.addEventListener('keydown', closeWordLineSpacingOnEscape, true);
//   }, 0);
// };

// function closeWordTablePickerOnOutsideClick(event: PointerEvent) {
//   const menu = document.getElementById('word-mock-table-picker-menu');
//   if (!menu || !(event.target instanceof Node)) return;
//   if (menu.contains(event.target)) return;
//   if (event.target instanceof Element && event.target.closest('[data-word-action="table"]')) return;

//   closeWordTablePickerMenu();
// }

// function closeWordTablePickerOnEscape(event: KeyboardEvent) {
//   if (event.key !== 'Escape') return;

//   closeWordTablePickerMenu();
// }

// function closeWordTableOptionsOnEscape(event: KeyboardEvent) {
//   if (event.key !== 'Escape') return;

//   closeWordTableOptionsDialog();
// }

// const normalizeTableDimension = (value: number): number => {
//   if (!Number.isFinite(value)) return 1;

//   return Math.max(1, Math.min(99, Math.floor(value)));
// };

// const executeCreateTableCommand = (
//   options: Pick<WordToolbarOptions, 'insertTable' | 'univerAPI'>,
//   rows: number,
//   columns: number,
// ) => {
//   const normalizedRows = normalizeTableDimension(rows);
//   const normalizedColumns = normalizeTableDimension(columns);

//   if (options.insertTable) {
//     options.insertTable(normalizedRows, normalizedColumns);
//     return;
//   }

//   executeToolbarCommand(options.univerAPI, wordCommandIds.table, {
//     rowCount: normalizedRows,
//     colCount: normalizedColumns,
//   });
// };

// const updateWordTablePickerSelection = (
//   menu: HTMLElement,
//   rows: number,
//   columns: number,
// ) => {
//   const normalizedRows = normalizeTableDimension(rows);
//   const normalizedColumns = normalizeTableDimension(columns);
//   const sizeLabel = menu.querySelector<HTMLElement>('[data-word-table-picker-size]');
//   const labelLeft = Math.max(
//     55,
//     Math.min(270, wordTablePickerGridLeft + (normalizedColumns * wordTablePickerCellSize) / 2),
//   );
//   const labelTop = Math.max(
//     70,
//     Math.min(505, wordTablePickerGridTop + (normalizedRows * wordTablePickerCellSize) / 2),
//   );

//   if (sizeLabel) {
//     sizeLabel.hidden = false;
//     sizeLabel.textContent = `${normalizedColumns} x ${normalizedRows}`;
//     sizeLabel.style.left = `${labelLeft}px`;
//     sizeLabel.style.top = `${labelTop}px`;
//   }

//   menu.querySelectorAll<HTMLButtonElement>('[data-word-table-picker-cell]').forEach((cell) => {
//     const cellRow = Number(cell.dataset.tableRows);
//     const cellColumn = Number(cell.dataset.tableColumns);
//     const isSelected = cellRow <= normalizedRows && cellColumn <= normalizedColumns;
//     cell.classList.toggle('is-selected', isSelected);
//     cell.setAttribute('aria-pressed', isSelected ? 'true' : 'false');
//   });
// };

// const clearWordTablePickerSelection = (menu: HTMLElement) => {
//   const sizeLabel = menu.querySelector<HTMLElement>('[data-word-table-picker-size]');
//   if (sizeLabel) sizeLabel.hidden = true;

//   menu.querySelectorAll<HTMLButtonElement>('[data-word-table-picker-cell]').forEach((cell) => {
//     cell.classList.remove('is-selected');
//     cell.setAttribute('aria-pressed', 'false');
//   });
// };

// const createTablePickerCell = (
//   menu: HTMLElement,
//   tableOptions: Pick<WordToolbarOptions, 'insertTable' | 'univerAPI'>,
//   rows: number,
//   columns: number,
// ) => {
//   const button = document.createElement('button');
//   button.type = 'button';
//   button.className = 'word-mock-table-picker-cell';
//   button.dataset.wordTablePickerCell = 'true';
//   button.dataset.tableRows = String(rows);
//   button.dataset.tableColumns = String(columns);
//   button.setAttribute('aria-label', `Insert ${columns} x ${rows} table`);
//   button.setAttribute('aria-pressed', 'false');
//   button.addEventListener('mouseenter', () => {
//     updateWordTablePickerSelection(menu, rows, columns);
//   });
//   button.addEventListener('focus', () => {
//     updateWordTablePickerSelection(menu, rows, columns);
//   });
//   button.addEventListener('click', (event) => {
//     event.preventDefault();
//     executeCreateTableCommand(tableOptions, rows, columns);
//     closeWordTablePickerMenu();
//   });

//   return button;
// };

// const openWordTableOptionsDialog = (
//   tableOptions: Pick<WordToolbarOptions, 'insertTable' | 'univerAPI'>,
// ) => {
//   closeWordColorPalette();
//   closeWordLineSpacingMenu();
//   closeWordTablePickerMenu();
//   closeWordTableOptionsDialog();

//   const dialog = document.createElement('div');
//   dialog.id = 'word-mock-table-options-dialog';
//   dialog.className = 'word-mock-table-options-backdrop';
//   dialog.innerHTML = `
//     <div class="word-mock-table-options-window" role="dialog" aria-modal="true" aria-labelledby="word-mock-table-options-title">
//       <div class="word-mock-table-options-titlebar">
//         <span class="word-mock-table-options-traffic" aria-hidden="true"></span>
//         <span class="word-mock-table-options-traffic" aria-hidden="true"></span>
//         <span class="word-mock-table-options-traffic" aria-hidden="true"></span>
//         <div class="word-mock-table-options-window-title" id="word-mock-table-options-title">Insert Table</div>
//       </div>
//       <div class="word-mock-table-options-body">
//         <section class="word-mock-table-options-section">
//           <h2>General</h2>
//           <label class="word-mock-table-options-field word-mock-table-options-name">
//             <span>Name:</span>
//             <input type="text" value="Table1" aria-label="Table name" />
//           </label>
//           <div class="word-mock-table-options-dimensions">
//             <label class="word-mock-table-options-field">
//               <span>Columns:</span>
//               <input data-word-table-options-columns type="number" min="1" max="99" step="1" value="2" />
//             </label>
//             <label class="word-mock-table-options-field">
//               <span>Rows:</span>
//               <input data-word-table-options-rows type="number" min="1" max="99" step="1" value="2" />
//             </label>
//           </div>
//         </section>
//         <section class="word-mock-table-options-section">
//           <h2>Options</h2>
//           <label class="word-mock-table-options-check">
//             <input type="checkbox" disabled />
//             <span>Heading</span>
//           </label>
//           <label class="word-mock-table-options-check word-mock-table-options-subcheck is-disabled">
//             <input type="checkbox" checked disabled />
//             <span>Repeat heading rows on new pages</span>
//           </label>
//           <label class="word-mock-table-options-field word-mock-table-options-heading-rows is-disabled">
//             <span>Heading rows:</span>
//             <input type="number" value="1" disabled />
//           </label>
//           <label class="word-mock-table-options-check">
//             <input type="checkbox" disabled />
//             <span>Don't split table over pages</span>
//           </label>
//         </section>
//         <section class="word-mock-table-options-section">
//           <h2>Styles</h2>
//           <div class="word-mock-table-options-styles-row">
//             <select class="word-mock-table-options-styles" size="8" aria-label="Table style">
//               ${wordTableStyleOptions
//                 .map((styleName, index) => `<option ${index === 0 ? 'selected' : ''}>${styleName}</option>`)
//                 .join('')}
//             </select>
//             <div class="word-mock-table-options-preview" aria-hidden="true">
//               <div></div><div>Jan</div><div>Feb</div><div>Mar</div><div>Sum</div>
//               <div>North</div><div>6</div><div>7</div><div>8</div><div>21</div>
//               <div>Mid</div><div>11</div><div>12</div><div>13</div><div>36</div>
//               <div>South</div><div>16</div><div>17</div><div>18</div><div>51</div>
//               <div>Sum</div><div>33</div><div>36</div><div>39</div><div>108</div>
//             </div>
//           </div>
//         </section>
//       </div>
//       <div class="word-mock-table-options-actions">
//         <button class="word-mock-table-options-button" type="button" data-word-table-options-help>Help</button>
//         <span></span>
//         <button class="word-mock-table-options-button" type="button" data-word-table-options-cancel>Cancel</button>
//         <button class="word-mock-table-options-button" type="button" data-word-table-options-insert>Insert</button>
//       </div>
//     </div>
//   `;

//   dialog.addEventListener('click', (event) => {
//     if (event.target === dialog) closeWordTableOptionsDialog();
//   });

//   dialog.querySelector<HTMLButtonElement>('[data-word-table-options-cancel]')?.addEventListener('click', closeWordTableOptionsDialog);
//   dialog.querySelector<HTMLButtonElement>('[data-word-table-options-insert]')?.addEventListener('click', () => {
//     const rowsInput = dialog.querySelector<HTMLInputElement>('[data-word-table-options-rows]');
//     const columnsInput = dialog.querySelector<HTMLInputElement>('[data-word-table-options-columns]');
//     executeCreateTableCommand(
//       tableOptions,
//       normalizeTableDimension(Number(rowsInput?.value ?? 2)),
//       normalizeTableDimension(Number(columnsInput?.value ?? 2)),
//     );
//     closeWordTableOptionsDialog();
//   });

//   document.body.appendChild(dialog);
//   document.addEventListener('keydown', closeWordTableOptionsOnEscape, true);
//   dialog.querySelector<HTMLInputElement>('[data-word-table-options-columns]')?.focus();
// };

// const openWordTablePickerMenu = (
//   tableOptions: Pick<WordToolbarOptions, 'insertTable' | 'univerAPI'>,
//   anchor: HTMLElement,
// ) => {
//   if (document.getElementById('word-mock-table-picker-menu')) {
//     closeWordTablePickerMenu();
//     return;
//   }

//   closeWordColorPalette();
//   closeWordLineSpacingMenu();
//   closeWordTableOptionsDialog();

//   const menu = document.createElement('div');
//   const anchorRect = anchor.getBoundingClientRect();
//   const menuWidth = 330;
//   const left = Math.max(6, Math.min(anchorRect.left, window.innerWidth - menuWidth - 6));

//   menu.id = 'word-mock-table-picker-menu';
//   menu.className = 'word-mock-table-picker-menu';
//   menu.style.left = `${left}px`;
//   menu.style.top = `${anchorRect.bottom + 6}px`;
//   menu.setAttribute('role', 'menu');
//   menu.innerHTML = `
//     <div class="word-mock-table-picker-title">Table</div>
//     <div class="word-mock-table-picker-grid" role="grid" aria-label="Table size"></div>
//     <div class="word-mock-table-picker-size" data-word-table-picker-size hidden>1 x 1</div>
//     <button class="word-mock-table-picker-more" type="button">More Options...</button>
//   `;

//   const grid = menu.querySelector<HTMLElement>('.word-mock-table-picker-grid');
//   if (grid) {
//     grid.addEventListener('mouseleave', () => {
//       clearWordTablePickerSelection(menu);
//     });

//     for (let row = 1; row <= wordTablePickerRows; row += 1) {
//       for (let column = 1; column <= wordTablePickerColumns; column += 1) {
//         grid.appendChild(createTablePickerCell(menu, tableOptions, row, column));
//       }
//     }
//   }

//   menu.querySelector<HTMLButtonElement>('.word-mock-table-picker-more')?.addEventListener('click', (event) => {
//     event.preventDefault();
//     openWordTableOptionsDialog(tableOptions);
//   });

//   document.body.appendChild(menu);
//   clearWordTablePickerSelection(menu);

//   window.setTimeout(() => {
//     document.addEventListener('pointerdown', closeWordTablePickerOnOutsideClick, true);
//     document.addEventListener('keydown', closeWordTablePickerOnEscape, true);
//   }, 0);
// };

// export function renderWordMockToolbar({
//   containerId,
//   getLineSpacing,
//   setLineSpacing,
//   insertTable,
//   univerAPI,
// }: WordToolbarOptions) {
//   const container = document.getElementById(containerId);
//   if (!container || container.dataset.mockToolbarRendered === 'true') return;

//   const canClickAction = (action: WordToolbarAction | undefined) =>
//     Boolean(action && (action !== 'lineSpacing' || setLineSpacing));
//   const canClickTopItem = (item: WordToolbarItem) => Boolean(item.commandId || canClickAction(item.action));
//   const canClickFormatItem = (item: WordFormattingItem) => Boolean(item.commandId || canClickAction(item.action));

//   container.dataset.mockToolbarRendered = 'true';
//   container.innerHTML = `
//     <div class="word-mock-toolbar" role="toolbar" aria-label="LibreOffice Writer toolbar preview">
//       <div class="word-mock-toolbar-scroll">
//         <div class="word-mock-toolbar-row word-mock-toolbar-row-icons">
//           ${wordTopGroups
//             .map(
//               (group) => `
//                 <div class="word-mock-toolbar-group">
//                   ${group
//                     .map(
//                       (item) => `
//                         <button
//                           class="word-mock-icon-button"
//                           type="button"
//                           tabindex="${canClickTopItem(item) ? '0' : '-1'}"
//                           aria-disabled="${canClickTopItem(item) ? 'false' : 'true'}"
//                           title="${item.label}"
//                           aria-label="${item.label}"
//                           ${item.commandId ? `data-word-command="${item.commandId}"` : ''}
//                           ${item.params ? `data-word-command-params="${encodeURIComponent(JSON.stringify(item.params))}"` : ''}
//                           ${item.action ? `data-word-action="${item.action}"` : ''}
//                         >
//                           ${item.icon}
//                           <span class="word-mock-caret" aria-hidden="true"></span>
//                         </button>
//                       `,
//                     )
//                     .join('')}
//                 </div>
//               `,
//             )
//             .join('')}
//         </div>
//         <div class="word-mock-toolbar-row word-mock-toolbar-row-format">
//           <div class="word-mock-toolbar-group">
//             <select class="word-mock-select word-mock-select-style" data-word-paragraph-style aria-label="Paragraph style">
//               ${wordParagraphStyleOptions
//                 .map((option) => `<option value="${option.value}">${option.label}</option>`)
//                 .join('')}
//             </select>
//             <button class="word-mock-icon-button word-mock-style-button" type="button" tabindex="-1" aria-disabled="true" title="Clear Direct Formatting" aria-label="Clear Direct Formatting">
//               <span class="word-mock-style-icon">A</span>
//             </button>
//             <button class="word-mock-icon-button word-mock-style-button" type="button" tabindex="-1" aria-disabled="true" title="New Style from Selection" aria-label="New Style from Selection">
//               <span class="word-mock-style-icon word-mock-style-plus">A+</span>
//             </button>
//           </div>
//           <div class="word-mock-toolbar-group">
//             <select class="word-mock-select word-mock-select-font" data-word-font-family aria-label="Font family">
//               ${wordFontFamilyOptions.map((fontFamily) => `<option value="${fontFamily}">${fontFamily}</option>`).join('')}
//             </select>
//             <select class="word-mock-select word-mock-select-size" data-word-font-size aria-label="Font size">
//               ${wordFontSizeOptions
//                 .map((fontSize) => `<option value="${fontSize}" ${fontSize === 10 ? 'selected' : ''}>${fontSize} pt</option>`)
//                 .join('')}
//             </select>
//           </div>
//           ${wordFormattingGroups
//             .map(
//               (group) => `
//                 <div class="word-mock-toolbar-group">
//                   ${group
//                     .map(
//                       (item) => `
//                         <button
//                           class="word-mock-format-button"
//                           type="button"
//                           tabindex="${canClickFormatItem(item) ? '0' : '-1'}"
//                           aria-disabled="${canClickFormatItem(item) ? 'false' : 'true'}"
//                           title="${item.title}"
//                           aria-label="${item.title}"
//                           data-format-label="${item.label}"
//                           ${item.commandId ? `data-word-command="${item.commandId}"` : ''}
//                           ${item.params ? `data-word-command-params="${encodeURIComponent(JSON.stringify(item.params))}"` : ''}
//                           ${item.action ? `data-word-action="${item.action}"` : ''}
//                         >
//                           ${item.icon ?? item.label}
//                         </button>
//                       `,
//                     )
//                     .join('')}
//                 </div>
//               `,
//             )
//             .join('')}
//           <div class="word-mock-toolbar-group">
//             <button class="word-mock-format-button" type="button" data-word-command="${wordCommandIds.documentFlavor}" title="Toggle Document Mode" aria-label="Toggle Document Mode">
//               ${icon.showFormatting}
//             </button>
//           </div>
//         </div>
//       </div>
//     </div>
//   `;

//   container.querySelector<HTMLSelectElement>('[data-word-paragraph-style]')?.addEventListener('change', (event) => {
//     if (!(event.currentTarget instanceof HTMLSelectElement)) return;

//     executeToolbarCommand(univerAPI, wordCommandIds.paragraphStyle, {
//       value: Number(event.currentTarget.value),
//     });
//   });

//   container.querySelector<HTMLSelectElement>('[data-word-font-family]')?.addEventListener('change', (event) => {
//     if (!(event.currentTarget instanceof HTMLSelectElement)) return;

//     executeToolbarCommand(univerAPI, wordCommandIds.fontFamily, {
//       value: event.currentTarget.value,
//     });
//   });

//   container.querySelector<HTMLSelectElement>('[data-word-font-size]')?.addEventListener('change', (event) => {
//     if (!(event.currentTarget instanceof HTMLSelectElement)) return;

//     executeToolbarCommand(univerAPI, wordCommandIds.fontSize, {
//       value: Number(event.currentTarget.value),
//     });
//   });

//   container.querySelectorAll<HTMLButtonElement>('[data-word-command]').forEach((button) => {
//     const commandId = button.dataset.wordCommand;
//     if (!commandId) return;

//     button.addEventListener('click', (event) => {
//       event.preventDefault();

//       const encodedParams = button.dataset.wordCommandParams;
//       const params = encodedParams ? JSON.parse(decodeURIComponent(encodedParams)) as Record<string, unknown> : undefined;
//       executeToolbarCommand(univerAPI, commandId, params);
//     });
//   });

//   container.querySelectorAll<HTMLButtonElement>('[data-word-action]').forEach((button) => {
//     const action = button.dataset.wordAction;
//     if (!action) return;

//     button.addEventListener('click', (event) => {
//       event.preventDefault();

//       if (action === 'print') window.print();
//       if (action === 'textColor' || action === 'highlightColor') {
//         openWordColorPalette(univerAPI, button, action);
//       }
//       if (action === 'lineSpacing' && setLineSpacing) {
//         openWordLineSpacingMenu(button, setLineSpacing, getLineSpacing);
//       }
//       if (action === 'table') {
//         const tableOptions: Pick<WordToolbarOptions, 'insertTable' | 'univerAPI'> = {};
//         if (insertTable) tableOptions.insertTable = insertTable;
//         if (univerAPI) tableOptions.univerAPI = univerAPI;
//         openWordTablePickerMenu(tableOptions, button);
//       }
//     });
//   });
// }
