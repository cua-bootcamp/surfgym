import type { FWorkbook, FWorksheet } from "@univerjs/preset-sheets-core";
import type { ApplyState, Get, Set } from "./external";

type SpreadsheetUniverAPI = {
  executeCommand: <P extends object = object, R = boolean>(id: string, params?: P) => Promise<R>;
};

type SpreadsheetRuntime = {
  workbook: FWorkbook;
  defaultWorksheet: FWorksheet;
  univerAPI: SpreadsheetUniverAPI;
  rendered: Promise<void>;
  initializeWorksheet: (worksheet: FWorksheet) => void;
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
      applyState: ApplyState;
    };
  }
}
