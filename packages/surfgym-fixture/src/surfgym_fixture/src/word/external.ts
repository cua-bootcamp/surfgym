import { _getBodyMeta, _getTextMeta } from "./internal";
import { setFactory, getFactory, type Value, type ChainFunc } from "../external";

const external: ChainFunc = {
  body
};

export const set = setFactory(external);
export const get = getFactory(external);

export function body() {
  return {
    ..._getBodyMeta(),
    text
  };
}

function text(target: Value): ChainFunc {
  const targetStr = target == null ? "" : String(target);

  return _getTextMeta(targetStr);
}
