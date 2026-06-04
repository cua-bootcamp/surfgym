import { copyFile, mkdir, readFile, readdir, rename, rm } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import type { Plugin as EsbuildPlugin } from "esbuild";
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

function getCleanModuleId(id: string) {
  return (id.split("?")[0] ?? id).replaceAll("\\", "/");
}

function isUniverFilterUiIndex(id: string) {
  const cleanId = getCleanModuleId(id);

  return cleanId.includes("@univerjs/sheets-filter-ui") && cleanId.endsWith("/lib/es/index.js");
}

function isUniverFilterCoreIndex(id: string) {
  const cleanId = getCleanModuleId(id);

  return cleanId.includes("@univerjs/sheets-filter/lib/es/index.js");
}

function patchHeaderlessUniverFilterCode(code: string, id: string) {
  if (isUniverFilterUiIndex(id)) {
    return code.replaceAll(
      "startRow: range.startRow + 1,",
      "startRow: range.__surfgymHeaderless ? range.startRow : range.startRow + 1,",
    );
  }

  if (isUniverFilterCoreIndex(id)) {
    return code.replace(
      "startRow: this._range.startRow + 1,",
      "startRow: this._range.__surfgymHeaderless ? this._range.startRow : this._range.startRow + 1,",
    );
  }

  return code;
}

function headerlessUniverFilterEsbuildPlugin(): EsbuildPlugin {
  return {
    name: "headerless-univer-filter-esbuild",
    setup(build) {
      build.onLoad(
        { filter: /@univerjs[\\/]sheets-filter(?:-ui)?[\\/]lib[\\/]es[\\/]index\.js$/ },
        async (args) => {
          const code = await readFile(args.path, "utf8");
          const patchedCode = patchHeaderlessUniverFilterCode(code, args.path);

          return patchedCode === code ? undefined : { contents: patchedCode, loader: "js" };
        },
      );
    },
  };
}

function headerlessUniverFilterPlugin(): Plugin {
  return {
    name: "headerless-univer-filter",
    enforce: "pre",
    transform(code, id) {
      const patchedCode = patchHeaderlessUniverFilterCode(code, id);

      return patchedCode === code ? null : { code: patchedCode, map: null };
    },
  };
}

export default defineConfig({
  appType: "mpa",
  plugins: [headerlessUniverFilterPlugin(), fixtureRoutesPlugin()],
  optimizeDeps: {
    esbuildOptions: {
      plugins: [headerlessUniverFilterEsbuildPlugin()],
    },
  },
  build: {
    emptyOutDir: true,
    rollupOptions: {
      input: createViteInputs(),
    },
  },
});
