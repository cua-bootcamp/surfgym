import { afterEach, describe, expect, it, vi } from 'vitest';
import { renderSpreadsheetMockToolbar } from './spreadsheet-ui';

afterEach(() => {
  document.body.innerHTML = '';
});

describe('pivot destination UI', () => {
  it('passes the selected sheet, A1 target, and display mode to the pivot action', async () => {
    document.body.innerHTML = '<div id="toolbar"></div>';
    const applySelectionPivotTable = vi.fn().mockResolvedValue({ ok: true, sheetName: 'Sheet2' });
    const actions = {
      applySelectionPivotTable,
      getSelectionPivotSource: () => ({
        rangeA1: 'A1:B4', rowCount: 4, columnCount: 2,
        fields: [{ index: 0, name: 'Category', isNumeric: false }, { index: 1, name: 'Amount', isNumeric: true }],
      }),
    };

    renderSpreadsheetMockToolbar({ containerId: 'toolbar', univerAPI: { executeCommand: async () => true }, actions } as never);
    document.querySelector<HTMLButtonElement>('[data-spreadsheet-pivot-table]')!.click();
    document.querySelector<HTMLButtonElement>('[data-pivot-source-ok]')!.click();
    document.querySelector<HTMLButtonElement>('[data-pivot-available-field="1"]')!.dispatchEvent(new MouseEvent('dblclick', { bubbles: true }));
    document.querySelector<HTMLInputElement>('input[value="existing-sheet"]')!.click();
    const sheet = document.querySelector<HTMLInputElement>('[data-pivot-destination-sheet]')!;
    sheet.value = 'Sheet2'; sheet.dispatchEvent(new Event('input', { bubbles: true }));
    const address = document.querySelector<HTMLInputElement>('[data-pivot-destination-a1]')!;
    address.value = 'B3'; address.dispatchEvent(new Event('input', { bubbles: true }));
    document.querySelector<HTMLButtonElement>('[data-pivot-layout-ok]')!.click();
    await Promise.resolve();

    expect(applySelectionPivotTable).toHaveBeenCalledWith(expect.objectContaining({
      destination: 'existing-sheet', destinationSheetName: 'Sheet2', destinationStartRow: 2, destinationStartColumn: 1,
      dataFields: [{ fieldIndex: 1, function: 'sum', displayAs: 'value' }],
    }));
  });

  it('shows an A1 error and does not call the action for an invalid target cell', async () => {
    document.body.innerHTML = '<div id="toolbar"></div>';
    const applySelectionPivotTable = vi.fn().mockResolvedValue({ ok: true });
    const actions = { applySelectionPivotTable, getSelectionPivotSource: () => ({ rangeA1: 'A1:B4', rowCount: 4, columnCount: 2, fields: [{ index: 0, name: 'Category', isNumeric: false }, { index: 1, name: 'Amount', isNumeric: true }] }) };
    renderSpreadsheetMockToolbar({ containerId: 'toolbar', univerAPI: { executeCommand: async () => true }, actions } as never);
    document.querySelector<HTMLButtonElement>('[data-spreadsheet-pivot-table]')!.click();
    document.querySelector<HTMLButtonElement>('[data-pivot-source-ok]')!.click();
    document.querySelector<HTMLButtonElement>('[data-pivot-available-field="1"]')!.dispatchEvent(new MouseEvent('dblclick', { bubbles: true }));
    const address = document.querySelector<HTMLInputElement>('[data-pivot-destination-a1]')!;
    address.value = 'A0'; address.dispatchEvent(new Event('input', { bubbles: true }));
    document.querySelector<HTMLButtonElement>('[data-pivot-layout-ok]')!.click();
    await Promise.resolve();

    expect(applySelectionPivotTable).not.toHaveBeenCalled();
    expect(document.querySelector('.spreadsheet-pivot-error')?.textContent).toContain('valid A1');
  });
});

describe('task-scoped line chart wizard UI', () => {
  it('shows only the supported line chart choice without unsupported 3D or shape controls', () => {
    document.body.innerHTML = '<div id="toolbar"></div>';
    renderSpreadsheetMockToolbar({
      containerId: 'toolbar',
      actions: {
        applySelectionChart: vi.fn(async () => true),
        columnIndexToName: (index: number) => String.fromCharCode(65 + index),
        getSelectionRangeTarget: () => ({
          range: { startRow: 0, endRow: 3, startColumn: 0, endColumn: 1 },
          worksheet: {},
        }),
      } as never,
    });

    document.querySelector<HTMLButtonElement>('[data-spreadsheet-chart]')!.click();

    const dialog = document.querySelector('#spreadsheet-chart-wizard-dialog')!;
    expect(dialog.textContent).toContain('Line');
    expect(dialog.textContent).not.toContain('3D Look');
    expect(dialog.textContent).not.toContain('Bar');
    expect(dialog.textContent).not.toContain('Cylinder');
    expect(dialog.textContent).not.toContain('Cone');
    expect(dialog.textContent).not.toContain('Pyramid');
    expect(dialog.querySelector('[aria-label="Shape"]')).toBeNull();
  });
});

describe('spreadsheet name box', () => {
  it('renders a dedicated value span instead of a stale hard-coded selection', () => {
    document.body.innerHTML = '<div id="toolbar"></div>';

    renderSpreadsheetMockToolbar({ containerId: 'toolbar' } as never);

    expect(document.querySelector('[data-spreadsheet-name-box-value]')?.textContent).toBe('A1');
    expect(document.querySelector('.spreadsheet-mock-select-arrow')).not.toBeNull();
  });
});
