type External = Record<string, (...args: any[]) => unknown>;

function runQueryFactory(external: External): (query: Query[]) => unknown {
  function runQuery(query: Query[]) {
    let iter: unknown = external;

    for (const [name, param] of query) {
      if (!isRecord(iter)) throw new Error(`Cannot call ${name} on non-object query result.`);
      const next = iter[name];

      if (typeof next !== "function") throw new Error(`Unsupported surfgym query step: ${name}`);
      iter = param === null ? next() : next(param);
    }

    return iter;
  }

  return runQuery;
}

export type Set = ReturnType<typeof setFactory>;
export function setFactory(external: External): (payload: SetPayload) => void {
  const runQuery = runQueryFactory(external);

  function set(payload: SetPayload) {
    const { query, path, value } = payload;
    let iter = runQuery(query);

    if (!isSettable(iter)) throw new Error("Query result is not settable.");
    return iter[SET](path, value);
  }

  return set;
}

export type Get = ReturnType<typeof getFactory>;
export function getFactory(external: External): (payload: GetPayload) => unknown {
  const runQuery = runQueryFactory(external);

  function get(payload: GetPayload) {
    const { query, path } = payload;

    let iter = runQuery(query);
    for (const key of path) {
      if (!isRecord(iter))
        throw new Error(`Wrong path with ${String(key)} on non-object query result.`);
      iter = iter[key];
    }

    return iter;
  }

  return get;
}

// #######################################
// #                Types                #
// #######################################

export type Value = null | string | number | boolean | Value[] | { [key: string]: Value };
export type Query = [string, Value];
export type Path = PropertyKey;

type GetPayload = {
  query: Query[];
  path: Path[];
};

type SetPayload = GetPayload & {
  value: Value;
};

function isRecord(value: unknown): value is Record<PropertyKey, unknown> {
  return value !== null && typeof value === "object";
}

export const SET = Symbol("surfgym.set");
type Settable = {
  [SET]: (path: Path[], value: Value) => void;
};
function isSettable(value: unknown): value is Settable {
  return isRecord(value) && typeof value[SET] === "function";
}
