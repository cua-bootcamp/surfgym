import type { FWorkbook, FWorksheet } from "@univerjs/preset-sheets-core";
import type { Get, Set } from "../external";

type SpreadsheetRuntime = {
  workbook: FWorkbook;
  defaultWorksheet: FWorksheet;
};

export class SpreadsheetRuntimeStore {
  private static _runtime: SpreadsheetRuntime | null = null;

  static set runtime(runtime: SpreadsheetRuntime) {
    SpreadsheetRuntimeStore._runtime = runtime;
  }

  static get runtime(): SpreadsheetRuntime {
    if (!SpreadsheetRuntimeStore._runtime) {
      throw new Error("Spreadsheet get runtime is not installed.");
    }

    return SpreadsheetRuntimeStore._runtime;
  }
}

declare global {
  interface Window {
    surfgym: {
      get: Get;
      set: Set;
    };
  }
}
