/* DOM 基础件：不使用任何 HTML 字符串注入，全部通过 createElement 构建。 */

import { TONE } from "./labels.js";

const NS = "http://www.w3.org/2000/svg";

export function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  applyAttrs(el, attrs);
  append(el, children);
  return el;
}

export function svgEl(tag, attrs = {}, ...children) {
  const el = document.createElementNS(NS, tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value === null || value === undefined || value === false) continue;
    el.setAttribute(key, String(value));
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    el.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return el;
}

function applyAttrs(el, attrs) {
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value === null || value === undefined || value === false) continue;
    if (key === "class") el.className = value;
    else if (key === "dataset") Object.assign(el.dataset, value);
    else if (key === "style") el.setAttribute("style", value);
    else if (key === "value" && "value" in el) el.value = value;
    else if (key === "checked" && "checked" in el) el.checked = Boolean(value);
    else if (key === "disabled") el.disabled = Boolean(value);
    else if (key.startsWith("on") && typeof value === "function") {
      el.addEventListener(key.slice(2).toLowerCase(), value);
    } else if (value === true) el.setAttribute(key, "");
    else el.setAttribute(key, String(value));
  }
}

export function append(el, children) {
  for (const child of children) {
    if (child === null || child === undefined || child === false) continue;
    if (Array.isArray(child)) append(el, child);
    else el.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return el;
}

export function clear(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
}

export function text(value) {
  return value === null || value === undefined || value === "" ? "—" : String(value);
}

/* ---------- 图标（内置静态 SVG，不加载任何外部资源） ---------- */

const ICONS = {
  dashboard: ["M4 13h6V4H4v9z", "M14 20h6v-9h-6v9z", "M4 20h6v-4H4v4z", "M14 8h6V4h-6v4z"],
  leads: ["M9 11a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7z", "M2.5 20c0-3.6 2.9-6 6.5-6s6.5 2.4 6.5 6", "M16 4.5a3.5 3.5 0 0 1 0 7", "M17.5 14.5c2.4.7 4 2.6 4 5.5"],
  tasks: ["M3.5 12 20 4l-4.5 16-4-6.5L3.5 12z", "M11.5 13.5 20 4"],
  compliance: ["M12 3 5 6v5c0 4.6 3 8.4 7 10 4-1.6 7-5.4 7-10V6l-7-3z", "m9 12 2 2 4-4"],
  records: ["M4 5h16", "M4 12h10", "M4 19h16", "M18.5 12a2 2 0 1 0 0-4 2 2 0 0 0 0 4z"],
  settings: ["M12 15.2a3.2 3.2 0 1 0 0-6.4 3.2 3.2 0 0 0 0 6.4z", "M12 2.8v3M12 18.2v3M2.8 12h3M18.2 12h3M5.5 5.5l2.1 2.1M16.4 16.4l2.1 2.1M18.5 5.5l-2.1 2.1M7.6 16.4l-2.1 2.1"],
  wizard: ["M12 3v3", "M12 18v3", "M3 12h3", "M18 12h3", "M6 6l2 2", "M16 16l2 2", "M18 6l-2 2", "M8 16l-2 2", "M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6z"],
  search: ["M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14z", "m20 20-4-4"],
  close: ["M6 6l12 12", "M18 6 6 18"],
  plus: ["M12 5v14", "M5 12h14"],
  refresh: ["M20 12a8 8 0 1 1-2.3-5.6", "M20 4v4h-4"],
  check: ["m5 12.5 4 4 10-10"],
  arrow: ["M5 12h14", "m13 6 6 6-6 6"],
  upload: ["M12 16V4", "m7 9 5-5 5 5", "M5 20h14"],
  play: ["m8 5 11 7-11 7V5z"],
  pause: ["M8 5v14", "M16 5v14"],
  stop: ["M6 6h12v12H6z"],
  shield: ["M12 3 5 6v5c0 4.6 3 8.4 7 10 4-1.6 7-5.4 7-10V6l-7-3z", "m9 12 2 2 4-4"],
  flask: ["M9 3h6", "M10 3v6l-5 8a2 2 0 0 0 1.7 3h10.6a2 2 0 0 0 1.7-3l-5-8V3", "M7.5 15h9"],
  clock: ["M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z", "M12 7v5l3 2"],
  user: ["M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8z", "M4 21c0-4 3.6-6.5 8-6.5s8 2.5 8 6.5"],
  alert: ["M12 3 2.5 20h19L12 3z", "M12 9v5", "M12 17.2v.1"],
  chevron: ["m9 6 6 6-6 6"],
  dot: ["M12 12h.01"],
};

export function icon(name, size = 18) {
  const paths = ICONS[name] || ICONS.dot;
  const node = svgEl("svg", {
    viewBox: "0 0 24 24",
    width: size,
    height: size,
    fill: "none",
    stroke: "currentColor",
    "stroke-width": 1.7,
    "stroke-linecap": "round",
    "stroke-linejoin": "round",
    "aria-hidden": "true",
  });
  for (const d of paths) node.append(svgEl("path", { d }));
  return h("span", { class: "icon" }, node);
}

/* ---------- 徽标、标签、键值 ---------- */

export function badge(dict, code, tone = "") {
  const entry = dict ? dict[code] : null;
  const color = tone || TONE[code] || "muted";
  return h(
    "span",
    {
      class: `badge tone-${color}`,
      title: entry ? `${entry[0]}（${code}）：${entry[1]}` : code || "—",
    },
    entry ? entry[0] : code || "—"
  );
}

export function chip(label, tone = "muted", title = "") {
  return h("span", { class: `chip tone-${tone}`, title: title || label }, label);
}

export function codeChip(code, dict, tone = "") {
  const entry = dict ? dict[code] : null;
  return chip(entry ? entry[0] : code, tone || TONE[code] || "muted", entry ? `${entry[0]}（${code}）：${entry[1]}` : code);
}

export function reasonChips(reasons, dict) {
  if (!reasons) return h("span", { class: "muted" }, "无命中");
  const list = Array.isArray(reasons) ? reasons : Object.entries(reasons).map(([code, count]) => ({ code, count }));
  if (!list.length) return h("span", { class: "muted" }, "无命中");
  return h(
    "div",
    { class: "chip-row" },
    list.map((item) => {
      const code = typeof item === "string" ? item : item.code;
      const entry = dict ? dict[code] : null;
      const delta = typeof item === "object" && item.delta !== undefined ? item.delta : null;
      const count = typeof item === "object" && item.count !== undefined ? item.count : null;
      let label = entry ? entry[0] : code;
      if (delta !== null) label += ` ${delta >= 0 ? "+" : ""}${delta}`;
      if (count !== null) label += ` ×${count}`;
      return chip(label, TONE[code] || "accent", entry ? `${entry[0]}（${code}）：${entry[1]}` : code);
    })
  );
}

export function kv(label, value, hint = "") {
  return h("div", { class: "kv" }, [
    h("span", { class: "kv-label" }, label),
    h("span", { class: "kv-value" }, text(value)),
    hint ? h("span", { class: "kv-hint muted" }, hint) : null,
  ]);
}

/* ---------- 表格、指标、空状态 ---------- */

export function table(headers, rows, { onRowClick = null, rowClass = null, emptyText = "暂无数据" } = {}) {
  if (!rows.length) return empty(emptyText);
  const body = rows.map((cells, index) => {
    const tr = h("tr", {}, cells.map((cell) => h("td", {}, cell)));
    if (rowClass) tr.className = rowClass(index);
    if (onRowClick) {
      tr.classList.add("clickable");
      tr.addEventListener("click", (event) => {
        if (event.target.closest("button, input, select, textarea, a, label")) return;
        onRowClick(index, event);
      });
    }
    return tr;
  });
  return h("div", { class: "table-host" }, [
    h("table", {}, [
      h("thead", {}, [h("tr", {}, headers.map((header) => h("th", {}, header)))]),
      h("tbody", {}, body),
    ]),
  ]);
}

export function kpi(label, value, hint = "", tone = "") {
  return h("div", { class: `kpi ${tone ? `tone-${tone}` : ""}` }, [
    h("div", { class: "kpi-label" }, label),
    h("div", { class: "kpi-value" }, String(value)),
    hint ? h("div", { class: "kpi-hint" }, hint) : null,
  ]);
}

export function empty(message, action = null) {
  return h("div", { class: "empty" }, [h("p", {}, message), action]);
}

export function skeleton(lines = 3) {
  return h(
    "div",
    { class: "skeleton" },
    Array.from({ length: lines }, (_, index) =>
      h("div", { class: "skeleton-line", style: `width:${100 - index * 12}%` })
    )
  );
}

/* ---------- Toast ---------- */

export function toast(message, kind = "info") {
  const root = document.getElementById("toast-root");
  if (!root) return;
  const node = h("div", { class: `toast toast-${kind}` }, message);
  root.append(node);
  window.setTimeout(() => node.classList.add("out"), 3600);
  window.setTimeout(() => node.remove(), 4000);
  while (root.children.length > 4) root.firstChild.remove();
}

export function toastError(error, hint = "") {
  const request = error && error.requestId ? ` · 请求编号 ${error.requestId}` : "";
  const code = error && error.code ? `（错误码 ${error.code}）` : "";
  toast(`${hint || "操作失败"}：${error && error.message ? error.message : String(error)}${code}${request}`, "error");
}

/* ---------- 抽屉与弹窗 ---------- */

function focusTrap(panel, close) {
  const previous = document.activeElement;
  const selector = "button, [href], input, select, textarea, [tabindex]:not([tabindex='-1'])";
  function onKey(event) {
    if (event.key === "Escape") {
      event.preventDefault();
      close();
      return;
    }
    if (event.key !== "Tab") return;
    const nodes = Array.from(panel.querySelectorAll(selector)).filter((node) => !node.disabled && node.offsetParent !== null);
    if (!nodes.length) return;
    const first = nodes[0];
    const last = nodes[nodes.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }
  document.addEventListener("keydown", onKey);
  window.setTimeout(() => {
    const target = panel.querySelector(selector);
    if (target) target.focus();
  }, 30);
  return () => {
    document.removeEventListener("keydown", onKey);
    if (previous && typeof previous.focus === "function") previous.focus();
  };
}

export function openDrawer(title, content, { width = 520, onClose = null } = {}) {
  const root = document.getElementById("drawer-root");
  const mask = h("div", { class: "drawer-mask" });
  const body = h("div", { class: "drawer-body" });
  const panel = h("aside", { class: "drawer", style: `width:min(${width}px, 100vw)` }, [
    h("header", { class: "drawer-head" }, [
      h("h3", {}, title),
      h("button", { class: "icon-btn", type: "button", title: "关闭", onclick: () => close() }, icon("close")),
    ]),
    body,
  ]);
  let released = null;
  let closed = false;
  function close() {
    if (closed) return;
    closed = true;
    if (released) released();
    mask.remove();
    panel.remove();
    if (onClose) onClose();
  }
  mask.addEventListener("click", close);
  released = focusTrap(panel, close);
  root.append(mask, panel);
  append(body, [content]);
  window.requestAnimationFrame(() => panel.classList.add("open"));
  return { close, body, panel };
}

export function openModal(title, content, { width = 560, onClose = null } = {}) {
  const root = document.getElementById("modal-root");
  const mask = h("div", { class: "modal-mask" });
  const body = h("div", { class: "modal-body" });
  const panel = h("div", { class: "modal", style: `max-width:${width}px` }, [
    h("header", { class: "modal-head" }, [
      h("h3", {}, title),
      h("button", { class: "icon-btn", type: "button", title: "关闭", onclick: () => close() }, icon("close")),
    ]),
    body,
  ]);
  let released = null;
  let closed = false;
  function close() {
    if (closed) return;
    closed = true;
    if (released) released();
    mask.remove();
    panel.remove();
    if (onClose) onClose();
  }
  mask.addEventListener("click", close);
  released = focusTrap(panel, close);
  root.append(mask, panel);
  append(body, [content]);
  return { close, body, panel };
}

export function confirmDialog(message, { danger = false, confirmLabel = "确认", cancelLabel = "取消" } = {}) {
  return new Promise((resolve) => {
    let settled = false;
    const modal = openModal(
      "请确认",
      h("div", {}, [
        h("p", { class: "confirm-text" }, message),
        h("div", { class: "btn-row end" }, [
          button(cancelLabel, { onClick: () => finish(false) }),
          button(confirmLabel, { kind: danger ? "danger" : "primary", onClick: () => finish(true) }),
        ]),
      ]),
      { width: 440, onClose: () => finish(false) }
    );
    function finish(value) {
      if (settled) return;
      settled = true;
      modal.close();
      resolve(value);
    }
  });
}

/* ---------- 表单件 ---------- */

export function button(label, { kind = "", onClick = null, disabled = false, title = "", type = "button", iconName = "" } = {}) {
  return h(
    "button",
    { class: kind || "", type, title: title || null, disabled: disabled || null, onclick: onClick || undefined },
    [iconName ? icon(iconName, 16) : null, label]
  );
}

export function field(labelText, control, hint = "") {
  return h("label", { class: "field" }, [
    h("span", { class: "field-label" }, labelText),
    control,
    hint ? h("span", { class: "field-hint" }, hint) : null,
  ]);
}

export function input({ type = "text", value = "", placeholder = "", name = "", min = null, max = null, step = null, onInput = null, autocomplete = "off" } = {}) {
  const node = h("input", {
    type,
    value,
    placeholder,
    name,
    autocomplete,
    min: min === null ? null : min,
    max: max === null ? null : max,
    step: step === null ? null : step,
  });
  if (onInput) node.addEventListener("input", onInput);
  return node;
}

export function textarea({ value = "", placeholder = "", rows = 4, onInput = null } = {}) {
  const node = h("textarea", { rows, placeholder }, value);
  if (onInput) node.addEventListener("input", onInput);
  return node;
}

export function select(options, value = "", { onChange = null, placeholder = "" } = {}) {
  const node = h("select", {});
  if (placeholder) node.append(h("option", { value: "" }, placeholder));
  for (const option of options) {
    node.append(h("option", { value: option.value }, option.label));
  }
  node.value = value;
  if (onChange) node.addEventListener("change", onChange);
  return node;
}

export function checkbox(labelText, checked = false, { onChange = null } = {}) {
  const box = h("input", { type: "checkbox", checked });
  if (onChange) box.addEventListener("change", onChange);
  return h("label", { class: "check" }, [box, h("span", {}, labelText)]);
}

/* ---------- 页面结构件 ---------- */

export function pageHead(title, subtitle, actions = []) {
  return h("header", { class: "page-head" }, [
    h("div", { class: "page-head-copy" }, [
      h("h2", {}, title),
      subtitle ? h("p", { class: "page-sub" }, subtitle) : null,
    ]),
    actions.length ? h("div", { class: "page-actions" }, actions) : null,
  ]);
}

export function guide(steps, nextText) {
  return h("div", { class: "guide" }, [
    h("div", { class: "guide-title" }, [icon("wizard", 16), "本页要做什么"]),
    h("p", { class: "guide-steps" }, steps),
    nextText ? h("p", { class: "guide-next" }, nextText) : null,
  ]);
}

export function card(title, subtitle = "", ...children) {
  return h("section", { class: "card" }, [
    title
      ? h("div", { class: "card-head" }, [
          h("div", {}, [
            h("h3", {}, title),
            subtitle ? h("p", { class: "card-sub" }, subtitle) : null,
          ]),
        ])
      : null,
    h("div", { class: "card-body" }, children),
  ]);
}

export function callout(message, tone = "muted", action = null) {
  return h("div", { class: `callout tone-${tone}` }, [h("span", {}, message), action]);
}

export function tabs(items, activeKey, onChange) {
  return h(
    "div",
    { class: "tabs", role: "tablist" },
    items.map((item) =>
      h(
        "button",
        {
          type: "button",
          role: "tab",
          class: item.key === activeKey ? "tab active" : "tab",
          "aria-selected": item.key === activeKey ? "true" : "false",
          onclick: () => onChange(item.key),
        },
        [
          item.label,
          item.count !== undefined && item.count !== null
            ? h("span", { class: `tab-count ${item.tone ? `tone-${item.tone}` : ""}` }, String(item.count))
            : null,
        ]
      )
    )
  );
}

export function pager(data, onPage) {
  const total = data.total || 0;
  const size = data.page_size || 20;
  const page = data.page || 1;
  const pages = Math.max(1, Math.ceil(total / size));
  return h("div", { class: "pager" }, [
    h("span", { class: "muted" }, `第 ${page} / ${pages} 页 · 共 ${total} 条`),
    h("span", { class: "spacer" }),
    button("上一页", { onClick: () => onPage(page - 1), disabled: page <= 1 }),
    button("下一页", { onClick: () => onPage(page + 1), disabled: page >= pages }),
  ]);
}

export function progressBar(value, total, tone = "ok") {
  const percent = total > 0 ? Math.max(0, Math.min(100, (value / total) * 100)) : 0;
  return h("div", { class: `progress tone-${tone}` }, [
    h("i", { style: `width:${percent}%` }),
  ]);
}

/* ---------- 时间与数字 ---------- */

export function fmtTime(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

export function fmtDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleDateString("zh-CN", { year: "numeric", month: "2-digit", day: "2-digit" });
}

export function fmtPercent(value) {
  if (value === null || value === undefined) return "—";
  return `${(Number(value) * 100).toFixed(1)}%`;
}

export function fmtDuration(seconds) {
  if (seconds === null || seconds === undefined) return "—";
  const total = Math.max(0, Math.round(Number(seconds)));
  if (total < 60) return `${total} 秒`;
  const minutes = Math.floor(total / 60);
  const rest = total % 60;
  return `${minutes} 分 ${rest} 秒`;
}

export function fmtCount(value) {
  return value === null || value === undefined ? "—" : String(value);
}
