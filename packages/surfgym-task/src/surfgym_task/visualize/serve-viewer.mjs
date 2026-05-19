#!/usr/bin/env node

import http from "node:http";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const port = readPort(process.argv.slice(2));

const mimeTypes = new Map([
  [".html", "text/html; charset=utf-8"],
  [".css", "text/css; charset=utf-8"],
  [".js", "text/javascript; charset=utf-8"],
  [".json", "application/json; charset=utf-8"],
  [".png", "image/png"],
  [".jpg", "image/jpeg"],
  [".jpeg", "image/jpeg"],
  [".svg", "image/svg+xml"]
]);

const server = http.createServer(async (request, response) => {
  try {
    const requestUrl = new URL(request.url ?? "/", `http://${request.headers.host}`);
    const pathname = requestUrl.pathname === "/" ? "/viewer/" : requestUrl.pathname;
    const requestedPath = pathname.endsWith("/") ? path.join(pathname, "index.html") : pathname;
    const absolutePath = path.resolve(__dirname, `.${decodeURIComponent(requestedPath)}`);

    if (!absolutePath.startsWith(__dirname)) {
      response.writeHead(403);
      response.end("Forbidden");
      return;
    }

    const body = await fs.readFile(absolutePath);
    const contentType = mimeTypes.get(path.extname(absolutePath)) ?? "application/octet-stream";
    response.writeHead(200, { "Content-Type": contentType, "Cache-Control": "no-store" });
    response.end(body);
  } catch (error) {
    response.writeHead(error.code === "ENOENT" ? 404 : 500, { "Content-Type": "text/plain; charset=utf-8" });
    response.end(error.code === "ENOENT" ? "Not found" : String(error));
  }
});

server.listen(port, "127.0.0.1", () => {
  console.log(`Viewer: http://127.0.0.1:${port}/viewer/`);
});

function readPort(argv) {
  for (let i = 0; i < argv.length; i += 1) {
    if (argv[i] === "--port") return Number(argv[i + 1]);
    if (argv[i].startsWith("--port=")) return Number(argv[i].slice("--port=".length));
  }
  return Number(process.env.PORT ?? 4173);
}
