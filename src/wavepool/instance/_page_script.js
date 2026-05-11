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

      return normalizeText(element.innerText);
    }

    function ensureElementId(element) {
      if (!element.hasAttribute("__elementId")) {
        element.setAttribute("__elementId", String(nextLabel++));
      }
      return element.getAttribute("__elementId");
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

        let visible_text = getVisibleText(element);

        if (visible_text !== "")
          results.push({
            role: getInteractiveRole(element),
            visible_text,
            bbox: bboxFromClippedRect(clippedRect)
          });
      }

      return results;
    }

    // #####################################
    // #        getInteractiveRects        #
    // #####################################

    return {
      getInteractiveRects: getInteractiveRects
    };
  })();

// [
//    {
//     "role": "button",
//     "visible_text": "increase counter",
//     "bbox": [498, 563, 62, 44]
//    }
// ...
// ]
