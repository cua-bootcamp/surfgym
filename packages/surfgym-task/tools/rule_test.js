function readText(element) {
  return element.innerText || element.textContent || "";
}

function readAttr(element, attr) {
  if (!attr) {
    return "";
  }

  console.log(attr);
  if (attr in element) {
    const value = element[attr];
    return value === undefined || value === null ? "" : String(value);
  }

  return element.getAttribute(attr) || "";
}

function readFromElement(rule) {
  if (!rule.selector) {
    return "";
  }

  let element = null;
  try {
    element = document.querySelector(rule.selector);
  } catch {
    return "";
  }

  if (!element) {
    return "";
  }

  if (rule.target === undefined) rule.target = "text";

  if (rule.target === "text") {
    return readText(element);
  }
  if (rule.target === "html") {
    return element.outerHTML || "";
  }
  if (rule.target === "attr") {
    return readAttr(element, rule.attr);
  }

  return "";
}

function readFromPage(rule) {
  if (rule.target === undefined) rule.target = "text";
  if (rule.target === "url") {
    return window.location.href;
  }
  if (rule.target === "title") {
    return document.title || "";
  }
  if (rule.target === "text") {
    return document.body ? document.body.innerText || "" : "";
  }
  if (rule.target === "html") {
    return document.documentElement
      ? document.documentElement.outerHTML || ""
      : "";
  }

  return "";
}

const inspect = (rules) => {
  return rules.map((rule) =>
    rule.selector ? readFromElement(rule) : readFromPage(rule)
  );
};

function change(rule) {
  return {
    target: rule.target,
    selector: rule.selector,
    attr: rule.attr
  };
}

function compareString(expected, actual, match = "contains") {
  const expectedText = expected == null ? "" : String(expected);
  const actualText = actual == null ? "" : String(actual);

  if (match === "contains") {
    return actualText.includes(expectedText);
  }

  if (match === "exact") {
    return actualText === expectedText;
  }

  if (match === "regex") {
    try {
      const regex = new RegExp(expectedText);
      return regex.test(actualText);
    } catch {
      return false;
    }
  }

  throw new Error(`Unsupported match type: ${match}`);
}

function allinone(rules) {
  const actuals = inspect(rules.map((r) => change(r)));

  return actuals.map((a, i) => {
    return compareString(rules[i].value, a, rules[i].match) ? 1 : 0;
  });
}
