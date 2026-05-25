import { copyFile, mkdir, readdir, rename, rm } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig, type Plugin } from "vite";

const rootDir = dirname(fileURLToPath(import.meta.url));
const srcDir = resolve(rootDir, "src");
const distDir = resolve(rootDir, "dist");

const VITE_ENTRY_DIRECTORIES = ["spreadsheet", "word"] as const;

function createViteInputs() {
  return {
    index: resolve(rootDir, "index.html"),
    ...Object.fromEntries(
      VITE_ENTRY_DIRECTORIES.map((route) => [
        route,
        resolve(srcDir, route, "index.html"),
      ]),
    ),
  };
}

async function copyHtmlFixture(route: string) {
  const source = resolve(srcDir, route, `${route}.html`);
  const target = resolve(distDir, route, "index.html");

  await mkdir(dirname(target), { recursive: true });
  await copyFile(source, target);
}

async function moveViteEntryHtml(route: string) {
  const source = resolve(distDir, "src", route, "index.html");
  const target = resolve(distDir, route, "index.html");

  await mkdir(dirname(target), { recursive: true });
  await rename(source, target);
}

function fixtureRoutesPlugin(): Plugin {
  return {
    name: "fixture-routes",
    apply: "build",
    async closeBundle() {
      const viteEntryRoutes = new Set<string>(VITE_ENTRY_DIRECTORIES);

      const entries = await readdir(srcDir, { withFileTypes: true });
      const htmlFixtureRoutes = entries
        .filter((entry) => entry.isDirectory())
        .map((entry) => entry.name)
        .filter((route) => !viteEntryRoutes.has(route));

      await Promise.all(htmlFixtureRoutes.map(copyHtmlFixture));
      await Promise.all(VITE_ENTRY_DIRECTORIES.map(moveViteEntryHtml));

      await rm(resolve(distDir, "src"), { recursive: true, force: true });
    },
  };
}

export default defineConfig({
  appType: "mpa",
  plugins: [fixtureRoutesPlugin()],
  build: {
    emptyOutDir: true,
    rollupOptions: {
      input: createViteInputs(),
    },
  },
});
