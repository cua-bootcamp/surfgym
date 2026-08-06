import fs from "node:fs/promises";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const sourcePath = new URL(
  "../../packages/surfgym-task/src/surfgym_task/data/spreadsheet/reference/calculate_campaign_net_funds/WeeklySales.xlsx",
  import.meta.url,
);
const previewPath = new URL("./existing-campaign-source.png", import.meta.url);

const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(sourcePath.pathname));

const overview = await workbook.inspect({
  kind: "workbook,sheet,table,formula,drawing",
  maxChars: 10000,
  tableMaxRows: 15,
  tableMaxCols: 10,
  options: { maxResults: 100 },
});
console.log(overview.ndjson);

const preview = await workbook.render({
  sheetName: "Sheet1",
  autoCrop: "all",
  scale: 1.5,
  format: "png",
});
await fs.writeFile(previewPath, new Uint8Array(await preview.arrayBuffer()));
console.log(`preview=${previewPath.pathname}`);
