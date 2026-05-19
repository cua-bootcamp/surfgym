import fs from "fs";

const inputPath = "./seed/prozilla/seed.jsonc";
const outputPath = "tasks.compact.json";

const data = JSON.parse(fs.readFileSync(inputPath, "utf8"));

const INDENT = 2;
const MAX_INLINE = 180;

function isPrimitive(value) {
  return (
    value === null || ["string", "number", "boolean"].includes(typeof value)
  );
}

function isInlineArray(arr) {
  return arr.every((v) => isPrimitive(v));
}

function canInlineObject(obj) {
  return (
    obj &&
    typeof obj === "object" &&
    !Array.isArray(obj) &&
    Object.values(obj).every((v) => {
      if (isPrimitive(v)) return true;
      if (Array.isArray(v)) return isInlineArray(v);
      return false;
    })
  );
}

function inlineStringify(value) {
  if (Array.isArray(value)) {
    return `[${value.map(inlineStringify).join(", ")}]`;
  }

  if (value && typeof value === "object") {
    const entries = Object.entries(value).map(
      ([key, val]) => `${JSON.stringify(key)}: ${inlineStringify(val)}`
    );
    return `{ ${entries.join(", ")} }`;
  }

  return JSON.stringify(value);
}

function formatJson(value, depth = 0) {
  const indent = " ".repeat(depth * INDENT);
  const childIndent = " ".repeat((depth + 1) * INDENT);

  if (isPrimitive(value)) {
    return JSON.stringify(value);
  }

  if (Array.isArray(value)) {
    if (value.length === 0) return "[]";

    const items = value.map(
      (item) => `${childIndent}${formatJson(item, depth + 1)}`
    );

    return `[\n${items.join(",\n")}\n${indent}]`;
  }

  if (value && typeof value === "object") {
    if (canInlineObject(value)) {
      const inline = inlineStringify(value);

      if (inline.length <= MAX_INLINE) {
        return inline;
      }
    }

    const entries = Object.entries(value).map(([key, val]) => {
      return `${childIndent}${JSON.stringify(key)}: ${formatJson(val, depth + 1)}`;
    });

    return `{\n${entries.join(",\n")}\n${indent}}`;
  }

  return JSON.stringify(value);
}

const output = formatJson(data) + "\n";
fs.writeFileSync(outputPath, output);
