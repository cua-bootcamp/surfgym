import type { SpreadsheetActions } from './spreadsheet-actions';

const fillColorCommandId = 'sheet.command.set-background-color';
const headerFilterMenuItemId = 'spreadsheet-header-filter-menu-item';
const startToolbarGroupId = 'spreadsheet-start-toolbar-group';
const startFilterToolbarButtonId = 'spreadsheet-start-filter-toolbar-button';
const startSortToolbarButtonId = 'spreadsheet-start-sort-toolbar-button';
const startBarChartToolbarButtonId = 'spreadsheet-start-bar-chart-toolbar-button';
const startConditionalFormattingToolbarButtonId = 'spreadsheet-start-conditional-formatting-toolbar-button';
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
const fillPaletteColors = [
  { label: 'Red', color: 'rgb(255, 0, 0)' },
  { label: 'Orange', color: 'rgb(255, 90, 31)' },
  { label: 'Yellow', color: 'rgb(250, 200, 21)' },
  { label: 'Green', color: 'rgb(13, 164, 113)' },
  { label: 'Blue', color: 'rgb(63, 131, 248)' },
  { label: 'Purple', color: 'rgb(144, 97, 249)' },
] as const;

type SpreadsheetUiContext = {
  univerAPI: {
    executeCommand: <P extends object = object, R = boolean>(id: string, params?: P) => Promise<R>;
  };
  actions: Pick<
    SpreadsheetActions,
    'applySelectionBarChart' | 'applySelectionFilter' | 'applySelectionSort' | 'getSelectionRangeTarget'
  >;
  conditionalFormattingCommandId: string;
};

export function setupSpreadsheetUi({
  univerAPI,
  actions,
  conditionalFormattingCommandId,
}: SpreadsheetUiContext) {
  let shouldFilterNextColorPicker = false;

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
            void actions.applySelectionFilter();
            document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
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
          void actions.applySelectionFilter();
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
