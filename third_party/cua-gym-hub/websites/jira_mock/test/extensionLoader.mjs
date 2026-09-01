import { readFile } from 'node:fs/promises';
import ts from 'typescript';

const TYPESCRIPT_EXTENSIONS = ['.ts', '.tsx'];

export async function resolve(specifier, context, nextResolve) {
  try {
    return await nextResolve(specifier, context);
  } catch (error) {
    if (
      error?.code !== 'ERR_MODULE_NOT_FOUND' ||
      (!specifier.startsWith('./') && !specifier.startsWith('../')) ||
      specifier.split('/').at(-1).includes('.')
    ) {
      throw error;
    }

    for (const extension of TYPESCRIPT_EXTENSIONS) {
      try {
        return await nextResolve(`${specifier}${extension}`, context);
      } catch (candidateError) {
        if (candidateError?.code !== 'ERR_MODULE_NOT_FOUND') {
          throw candidateError;
        }
      }
    }
    throw error;
  }
}

export async function load(url, context, nextLoad) {
  if (!TYPESCRIPT_EXTENSIONS.some(extension => url.endsWith(extension))) {
    return nextLoad(url, context);
  }

  const source = await readFile(new URL(url), 'utf8');
  const transpiled = ts.transpileModule(source, {
    compilerOptions: {
      jsx: ts.JsxEmit.ReactJSX,
      module: ts.ModuleKind.ESNext,
      target: ts.ScriptTarget.ES2020,
    },
    fileName: new URL(url).pathname,
  });
  return { format: 'module', source: transpiled.outputText, shortCircuit: true };
}
