import { afterEach, describe, expect, it, vi } from "vitest";
import { renderSpreadsheetMockToolbar } from "./spreadsheet-ui";

afterEach(() => {
  document.body.innerHTML = "";
});

describe("spreadsheet list data validation UI", () => {
  it("reopens the current selection's validation list instead of blank defaults", () => {
    document.body.innerHTML = '<div id="toolbar"></div>';
    const getSelectionValidationList = vi.fn().mockReturnValue({
      values: ["Pass", "Fail", "Held"],
      allowBlank: false,
    });

    renderSpreadsheetMockToolbar({
      containerId: "toolbar",
      univerAPI: { executeCommand: async () => true },
      actions: { getSelectionValidationList },
    } as never);

    document.querySelector<HTMLButtonElement>("[data-spreadsheet-data-validation]")!.click();

    expect(getSelectionValidationList).toHaveBeenCalledTimes(1);
    expect(document.querySelector<HTMLInputElement>("[data-validation-list-values]")?.value)
      .toBe("Pass, Fail, Held");
    expect(document.querySelector<HTMLInputElement>("[data-validation-allow-blank]")?.checked)
      .toBe(false);
  });

  it("opens list validation controls and forwards Apply and Remove for the current selection", () => {
    document.body.innerHTML = '<div id="toolbar"></div>';
    const applySelectionValidationList = vi.fn().mockReturnValue({ values: ["Pass", "Fail", "Held"], allowBlank: false });
    const getSelectionValidationList = vi.fn().mockReturnValue(null);
    const removeSelectionValidationList = vi.fn().mockReturnValue(null);

    renderSpreadsheetMockToolbar({
      containerId: "toolbar",
      univerAPI: { executeCommand: async () => true },
      actions: { applySelectionValidationList, getSelectionValidationList, removeSelectionValidationList },
    } as never);

    const openButton = document.querySelector<HTMLButtonElement>("[data-spreadsheet-data-validation]");
    expect(openButton).not.toBeNull();
    openButton!.click();
    const values = document.querySelector<HTMLInputElement>("[data-validation-list-values]");
    const allowBlank = document.querySelector<HTMLInputElement>("[data-validation-allow-blank]");
    expect(values).not.toBeNull();
    expect(allowBlank).not.toBeNull();

    values!.value = " Pass, Fail, Held ";
    allowBlank!.checked = false;
    document.querySelector<HTMLButtonElement>("[data-validation-apply]")!.click();
    expect(applySelectionValidationList).toHaveBeenCalledWith({ values: ["Pass", "Fail", "Held"], allowBlank: false });

    openButton!.click();
    document.querySelector<HTMLButtonElement>("[data-validation-remove]")!.click();
    expect(removeSelectionValidationList).toHaveBeenCalledTimes(1);
  });

  it("shows a visible validation rejection when formula input cannot commit", () => {
    document.body.innerHTML = '<div id="toolbar"></div>';
    const applySelectionInputValue = vi.fn().mockReturnValue({ ok: false, message: "Choose a value from the validation list." });
    renderSpreadsheetMockToolbar({
      containerId: "toolbar",
      univerAPI: { executeCommand: async () => true },
      actions: { applySelectionInputValue },
    } as never);

    const input = document.querySelector<HTMLInputElement>("[data-spreadsheet-formula-input]")!;
    input.value = "Rejected";
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true }));
    input.dispatchEvent(new Event("blur", { bubbles: true }));

    expect(applySelectionInputValue).toHaveBeenCalledWith("Rejected");
    expect(applySelectionInputValue).toHaveBeenCalledTimes(1);
    expect(input.getAttribute("aria-invalid")).toBe("true");
    expect(document.querySelector("[data-spreadsheet-input-error]")?.textContent)
      .toContain("Choose a value from the validation list.");
  });

  it("shows a real-grid validation rejection sent by the Univer command guard", () => {
    document.body.innerHTML = '<div id="toolbar"></div>';
    renderSpreadsheetMockToolbar({
      containerId: "toolbar",
      univerAPI: { executeCommand: async () => true },
      actions: {},
    } as never);

    window.dispatchEvent(new CustomEvent("surfgym:spreadsheet-input-error", {
      detail: "Choose a value from the validation list.",
    }));

    expect(document.querySelector("[data-spreadsheet-input-error]")?.textContent)
      .toContain("Choose a value from the validation list.");
  });
});
