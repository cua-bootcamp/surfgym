window.Surfgym =
  window.Surfgym ||
  (() => {
    // #####################################
    // #        getInteractiveRects        #
    // #####################################

    let nextLabel = 10;
    const USE_CURSOR_HEURISTIC = true;
    const INTERACTIVE_SELECTOR = [
      "a[href]",
      "area[href]",
      "button",
      "input",
      "select",
      "textarea",
      "option",
      "[onclick]",
      "[contenteditable='true']",
      "[tabindex]:not([tabindex='-1'])",
      "[role='button']",
      "[role='link']",
      "[role='checkbox']",
      "[role='radio']",
      "[role='textbox']",
      "[role='searchbox']",
      "[role='combobox']",
      "[role='listbox']",
      "[role='option']",
      "[role='slider']",
      "[role='spinbutton']",
      "[role='switch']",
      "[role='tab']",
      "[role='menuitem']"
    ].join(",");

    const INTERACTIVE_ROLES = new Set([
      "button",
      "link",
      "checkbox",
      "radio",
      "textbox",
      "searchbox",
      "combobox",
      "listbox",
      "option",
      "slider",
      "spinbutton",
      "switch",
      "tab",
      "menuitem",
      "menuitemcheckbox",
      "menuitemradio"
    ]);

    const INERT_CURSORS = new Set([
      "auto",
      "default",
      "none",
      "text",
      "vertical-text",
      "not-allowed",
      "no-drop"
    ]);

    const INPUT_ROLE_BY_TYPE = {
      button: "button",
      checkbox: "checkbox",
      color: "button",
      date: "textbox",
      "datetime-local": "textbox",
      email: "textbox",
      file: "button",
      month: "textbox",
      number: "spinbutton",
      password: "textbox",
      radio: "radio",
      range: "slider",
      reset: "button",
      search: "searchbox",
      submit: "button",
      tel: "textbox",
      text: "textbox",
      time: "textbox",
      url: "textbox",
      week: "textbox"
    };

    const TAG_ROLE = {
      a: "link",
      area: "link",
      button: "button",
      select: "combobox",
      option: "option",
      textarea: "textbox",
      summary: "button"
    };

    function normalizeText(text) {
      return (text || "").replace(/\s+/g, " ").trim();
    }

    function getStyle(element) {
      return window.getComputedStyle(element);
    }

    function isDisabled(element) {
      return (
        element.disabled === true ||
        element.getAttribute("aria-disabled") === "true"
      );
    }

    function isRectInViewport(rect) {
      const viewportWidth =
        window.innerWidth || document.documentElement.clientWidth;
      const viewportHeight =
        window.innerHeight || document.documentElement.clientHeight;

      return (
        rect.width > 0 &&
        rect.height > 0 &&
        rect.right > 0 &&
        rect.bottom > 0 &&
        rect.left < viewportWidth &&
        rect.top < viewportHeight
      );
    }

    function isVisible(element) {
      if (!(element instanceof Element)) {
        return false;
      }

      const style = getStyle(element);

      if (
        style.display === "none" ||
        style.visibility === "hidden" ||
        style.pointerEvents === "none" ||
        Number(style.opacity) === 0
      ) {
        return false;
      }

      const rects = Array.from(element.getClientRects());
      return rects.some(isRectInViewport);
    }

    function queryAllDeep(selector, root = document) {
      const results = [];
      const stack = [root];

      while (stack.length > 0) {
        const currentRoot = stack.pop();

        results.push(...Array.from(currentRoot.querySelectorAll(selector)));

        const allElements = currentRoot.querySelectorAll("*");
        for (const element of allElements) {
          if (element.shadowRoot && element.shadowRoot.mode === "open") {
            stack.push(element.shadowRoot);
          }
        }
      }

      return results;
    }

    function getInteractiveRole(element) {
      const explicitRole = element.getAttribute("role");
      if (explicitRole && INTERACTIVE_ROLES.has(explicitRole)) {
        return explicitRole;
      }

      const tag = element.tagName.toLowerCase();

      if (tag === "input") {
        const type = (element.getAttribute("type") || "text").toLowerCase();
        return INPUT_ROLE_BY_TYPE[type] || "textbox";
      }

      if (tag in TAG_ROLE) {
        return TAG_ROLE[tag];
      }

      if (element.isContentEditable) {
        return "textbox";
      }

      // Non-semantic clickable element.
      // Example: <div onclick="..."> or <div style="cursor:pointer">
      return "clickable";
    }

    function getVisibleText(element) {
      const tag = element.tagName.toLowerCase();

      if (tag === "input") {
        const type = (element.getAttribute("type") || "text").toLowerCase();

        // Screen-visible value or placeholder.
        if (
          [
            "text",
            "search",
            "email",
            "tel",
            "url",
            "number",
            "date",
            "time",
            "month",
            "week",
            "datetime-local"
          ].includes(type)
        ) {
          return normalizeText(element.value || element.placeholder);
        }

        // Password value is visible only as bullets.
        if (type === "password") {
          return element.value ? "••••••" : normalizeText(element.placeholder);
        }

        // These render their value text on the control itself.
        if (["button", "submit", "reset"].includes(type)) {
          return normalizeText(element.value);
        }

        // File input often shows selected file name in the browser UI.
        // Avoid exposing raw value/fake path.
        if (type === "file") {
          if (element.files && element.files.length > 0) {
            return Array.from(element.files)
              .map((file) => file.name)
              .join(" ");
          }
          return "";
        }

        // Checkbox/radio/range/color usually do not display their value as text.
        return "";
      }

      if (tag === "textarea") {
        return normalizeText(element.value || element.placeholder);
      }

      if (tag === "select") {
        const selected = Array.from(element.selectedOptions || []);
        return normalizeText(
          selected.map((option) => option.innerText).join(" ")
        );
      }

      const text = normalizeText(element.innerText);
      if (text) return text;

      return normalizeText(
        element.getAttribute("aria-label") ||
        element.getAttribute("title") ||
        ""
      );
    }

    function isPointInViewport(x, y) {
      const viewportWidth =
        window.innerWidth || document.documentElement.clientWidth;
      const viewportHeight =
        window.innerHeight || document.documentElement.clientHeight;

      return x >= 0 && y >= 0 && x < viewportWidth && y < viewportHeight;
    }

    function isSameOrAncestor(element, hit) {
      let current = hit;

      while (current) {
        if (current === element) {
          return true;
        }

        current =
          current.parentNode ||
          (current.getRootNode && current.getRootNode().host) ||
          null;
      }

      return false;
    }

    function isTopmostAt(element, x, y) {
      if (!isPointInViewport(x, y)) {
        return false;
      }

      const hit = deepElementFromPoint(x, y);
      if (!hit) {
        return false;
      }

      return isSameOrAncestor(element, hit);
    }

    function hasTopmostPoint(element) {
      const rects = Array.from(element.getClientRects()).filter(
        isRectInViewport
      );

      for (const rect of rects) {
        const points = [
          [rect.left + rect.width / 2, rect.top + rect.height / 2],
          [
            rect.left + Math.min(5, rect.width / 2),
            rect.top + Math.min(5, rect.height / 2)
          ],
          [
            rect.right - Math.min(5, rect.width / 2),
            rect.top + Math.min(5, rect.height / 2)
          ],
          [
            rect.left + Math.min(5, rect.width / 2),
            rect.bottom - Math.min(5, rect.height / 2)
          ],
          [
            rect.right - Math.min(5, rect.width / 2),
            rect.bottom - Math.min(5, rect.height / 2)
          ]
        ];

        for (const [x, y] of points) {
          if (isTopmostAt(element, x, y)) {
            return true;
          }
        }
      }

      return false;
    }

    function deepElementFromPoint(x, y) {
      let element = document.elementFromPoint(x, y);

      while (element && element.shadowRoot) {
        const inner = element.shadowRoot.elementFromPoint(x, y);
        if (!inner || inner === element) {
          break;
        }
        element = inner;
      }

      return element;
    }

    function getCursorInteractiveElements() {
      if (!USE_CURSOR_HEURISTIC) {
        return [];
      }

      const results = [];

      for (let node of queryAllDeep("*")) {
        if (isDisabled(node) || !isVisible(node)) {
          continue;
        }

        const cursor = getStyle(node).cursor;

        if (INERT_CURSORS.has(cursor)) {
          continue;
        }

        // Move upward to the outermost element with the same interactive cursor.
        let parent = node.parentElement;
        while (parent && getStyle(parent).cursor === cursor) {
          node = parent;
          parent = node.parentElement;
        }

        results.push(node);
      }

      return results;
    }

    function getInteractiveElements() {
      const candidates = [
        ...queryAllDeep(INTERACTIVE_SELECTOR),
        ...getCursorInteractiveElements()
      ];

      const unique = Array.from(new Set(candidates));

      return unique.filter((element) => {
        if (isDisabled(element) || !isVisible(element)) {
          return false;
        }

        return hasTopmostPoint(element);
      });
    }

    function getViewportSize() {
      return {
        width: window.innerWidth || document.documentElement.clientWidth,
        height: window.innerHeight || document.documentElement.clientHeight
      };
    }

    function clipRectToViewport(rect) {
      const viewport = getViewportSize();

      const left = Math.max(0, rect.left);
      const top = Math.max(0, rect.top);
      const right = Math.min(viewport.width, rect.right);
      const bottom = Math.min(viewport.height, rect.bottom);

      const width = right - left;
      const height = bottom - top;

      if (width <= 0 || height <= 0) {
        return null;
      }

      return {
        left,
        top,
        right,
        bottom,
        width,
        height
      };
    }

    function bboxFromClippedRect(rect) {
      return [
        Math.round(rect.left),
        Math.round(rect.top),
        Math.round(rect.width),
        Math.round(rect.height)
      ];
    }

    function isTopmostInClippedRect(element, clippedRect) {
      const points = [
        [
          clippedRect.left + clippedRect.width / 2,
          clippedRect.top + clippedRect.height / 2
        ],
        [
          clippedRect.left + Math.min(5, clippedRect.width / 2),
          clippedRect.top + Math.min(5, clippedRect.height / 2)
        ],
        [
          clippedRect.right - Math.min(5, clippedRect.width / 2),
          clippedRect.top + Math.min(5, clippedRect.height / 2)
        ],
        [
          clippedRect.left + Math.min(5, clippedRect.width / 2),
          clippedRect.bottom - Math.min(5, clippedRect.height / 2)
        ],
        [
          clippedRect.right - Math.min(5, clippedRect.width / 2),
          clippedRect.bottom - Math.min(5, clippedRect.height / 2)
        ]
      ];

      for (const [x, y] of points) {
        if (isTopmostAt(element, x, y)) {
          return true;
        }
      }

      return false;
    }

    function getInteractiveRects() {
      const results = [];
      const elements = getInteractiveElements();

      for (const element of elements) {
        const rawRect = element.getBoundingClientRect();
        const clippedRect = clipRectToViewport(rawRect);

        if (!clippedRect) {
          continue;
        }

        if (!isTopmostInClippedRect(element, clippedRect)) {
          continue;
        }

        const visible_text = getVisibleText(element);

        results.push({
          role: getInteractiveRole(element),
          visible_text: visible_text || "[icon]",
          bbox: bboxFromClippedRect(clippedRect)
        });
      }

      return results;
    }

    // #####################################
    // #         getDomObservation         #
    // #####################################

    function readFromPage(rule) {
      if (rule.target === "url") return window.location.href;

      if (rule.target === "title") return document.title || "";

      if (rule.target === "text")
        return document.body ? document.body.innerText || "" : "";

      if (rule.target === "html")
        return document.documentElement
          ? document.documentElement.outerHTML || ""
          : "";

      return "";
    }

    function readAttr(element, attr) {
      if (!attr) {
        return "";
      }

      if (attr in element) {
        const value = element[attr];
        return value === undefined || value === null ? "" : String(value);
      }

      return element.getAttribute(attr) || "";
    }

    function readFromElement(rule) {
      let element = null;
      try {
        element = document.querySelector(rule.selector);
      } catch {
        return "";
      }

      if (!element) return "";
      if (rule.target === "text") {
        return element.innerText || element.textContent || "";
      }
      if (rule.target === "html") {
        return element.outerHTML || "";
      }
      if (rule.target === "attr") {
        return readAttr(element, rule.attr);
      }

      return "";
    }

    function getDomObservation(rules) {
      return rules.map((rule) =>
        rule.selector ? readFromElement(rule) : readFromPage(rule)
      );
    }

    // #####################################
    // #     getSpreadsheetObservation     #
    // #####################################

    function getSpreadsheetObservation() {
      const canvas = document.querySelector(
        "canvas[id^='univer-sheet-main-canvas']"
      );
      if (!canvas) return null;

      const rect = canvas.getBoundingClientRect();
      const ctx = canvas.getContext("2d", { willReadFrequently: true });

      const w = canvas.width;
      const h = canvas.height;
      const data = ctx.getImageData(0, 0, w, h).data;

      const scaleX = canvas.width / rect.width;
      const scaleY = canvas.height / rect.height;

      function isNonWhite(x, y) {
        const i = (y * w + x) * 4;
        const r = data[i];
        const g = data[i + 1];
        const b = data[i + 2];
        const a = data[i + 3];

        if (a < 20) return false;

        return Math.abs(255 - r) + Math.abs(255 - g) + Math.abs(255 - b) > 35;
      }

      function compact(values) {
        const out = [];
        let start = null;
        let prev = null;

        for (const v of values) {
          if (start === null) {
            start = prev = v;
          } else if (v === prev + 1) {
            prev = v;
          } else {
            out.push(Math.round((start + prev) / 2));
            start = prev = v;
          }
        }

        if (start !== null) out.push(Math.round((start + prev) / 2));
        return out;
      }

      function verticalLines() {
        const hits = [];
        const y1 = 40;
        const y2 = h - 20;
        const threshold = (y2 - y1) * 0.45;

        for (let x = 0; x < w; x++) {
          let count = 0;
          for (let y = y1; y < y2; y++) {
            if (isNonWhite(x, y)) count++;
          }
          if (count > threshold) hits.push(x);
        }

        return compact(hits);
      }

      function horizontalLines() {
        const hits = [];
        const x1 = 80;
        const x2 = w - 20;
        const threshold = (x2 - x1) * 0.45;

        for (let y = 0; y < h; y++) {
          let count = 0;
          for (let x = x1; x < x2; x++) {
            if (isNonWhite(x, y)) count++;
          }
          if (count > threshold) hits.push(y);
        }

        return compact(hits);
      }

      const xLines = verticalLines();
      const yLines = horizontalLines();

      if (xLines.length < 2 || yLines.length < 2) {
        return null;
      }

      return {
        canvas: {
          left: rect.left,
          top: rect.top
        },
        start: {
          x: xLines[0] / scaleX,
          y: yLines[0] / scaleY
        },
        size: {
          width: (xLines[1] - xLines[0]) / scaleX,
          height: (yLines[1] - yLines[0]) / scaleY
        }
      };
    }

    return {
      getInteractiveRects: getInteractiveRects,
      getDomObservation: getDomObservation,
      getSpreadsheetObservation: getSpreadsheetObservation
    };
  })();
