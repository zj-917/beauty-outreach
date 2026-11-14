"use strict";

/* 基础工具、API 封装、鉴权与页面切换。 */

const $ = (id) => document.getElementById(id);
const quiet = () => {};

const state = {
  token: "",
  operator: "admin",
  leadPage: 1,
  auditPage: 1,
  sendPage: 1,
  poolPage: 1,
  poolView: "pool",
  poolQ: "",
  itemGroup: "all",
  itemReason: "",
  taskStats: null,
  readiness: new Map(),
  currentTask: null,
  pollTimer: null,
  pollTask: null,
  settings: {},
};

function make(tag, props = {}, children = []) {
  const node = document.createElement(tag);
  Object.entries(props).forEach(([key, value]) => {
    if (key === "text") node.textContent = String(value);
    else if (key === "class") node.className = value;
    else if (key === "dataset") Object.assign(node.dataset, value);
    else node[key] = value;
  });
  children.forEach((child) => {
    node.appendChild(
      child instanceof Node ? child : document.createTextNode(String(child))
    );
  });
  return node;
}

function button(label, onClick, className) {
  return make("button", { type: "button", text: label, class: className || "", onclick: onClick });
}

function card(label, value) {
  return make("div", { class: "card" }, [
    make("div", { class: "label", text: label }),
    make("div", { class: "value", text: value }),
  ]);
}

function configAction(label, request) {
  return button(label, () => configRun(request));
}

function configRun(request) {
  request().then(loadConfig).catch(configError);
}

function configConfirm(label, message, request) {
  return button(
    label,
    () => {
      if (!window.confirm(message)) return;
      request().then(loadConfig).catch(configError);
    },
    "danger"
  );
}

function clear(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
}

function fill(container, ...nodes) {
  clear(container);
  nodes.forEach((node) => container.appendChild(node));
}

function table(headers, rows) {
  return make("table", {}, [
    make("tr", {}, headers.map((header) => make("th", { text: header }))),
    ...rows.map((cells) =>
      make(
        "tr",
        {},
        cells.map((cell) =>
          make("td", {}, [cell instanceof Node ? cell : cell === null || cell === undefined || cell === "" ? "—" : cell])
        )
      )
    ),
  ]);
}

function valuesSum(object) {
  return Object.values(object).reduce((total, value) => total + value, 0);
}

function fmtJson(value, limit = 120) {
  if (value === null || value === undefined) return "—";
  const text = JSON.stringify(value);
  return text.length > limit ? text.slice(0, limit) + "…" : text;
}

function fmtReasons(reasons) {
  const entries = Object.entries(reasons || {});
  return entries.length
    ? entries.map(([code, count]) => zhName(REASON_LABELS, code) + "×" + count).join("，")
    : "无";
}

function dictEntry(dict, code) {
  return Object.prototype.hasOwnProperty.call(dict, code) ? dict[code] : null;
}

function zhName(dict, code) {
  const entry = dictEntry(dict, code);
  return entry ? entry[0] : code || "—";
}

function zhFull(dict, code) {
  const entry = dictEntry(dict, code);
  return entry ? entry[0] + "（" + code + "）" : code || "—";
}

function labelNode(dict, code) {
  const entry = dictEntry(dict, code);
  return make("span", {
    text: entry ? entry[0] + "（" + code + "）" : code || "—",
    title: entry ? entry[1] : "",
  });
}

function optionNode(dict, code) {
  return make("option", { text: zhFull(dict, code), value: code });
}

function setGuideText(id, text) {
  const node = $(id);
  if (node) node.textContent = text;
}

function errorText(detail) {
  const friendly = ERROR_HINTS[detail.code];
  const message = friendly || detail.message || "请稍后重试。";
  const request = detail.request_id ? " · 请求编号 " + detail.request_id : "";
  return "操作失败：" + message + "（错误码 " + detail.code + "）" + request;
}

function showError(message) {
  $("error-text").textContent = message;
  $("error-bar").classList.remove("hidden");
}

function hideError() {
  $("error-bar").classList.add("hidden");
}

async function api(path, options = {}) {
  const headers = {
    "X-Admin-Token": state.token || "",
    "X-Operator": state.operator || "admin",
  };
  let body = options.body;
  if (body !== undefined && !(body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(body);
  }
  const response = await fetch(path, { method: options.method || "GET", headers, body });
  if (response.status === 401) {
    showError(ERROR_HINTS.UNAUTHORIZED);
    $("token-input").focus();
    throw new Error("unauthorized");
  }
  if (!response.ok) {
    let detail = { code: response.status, message: response.statusText, request_id: null };
    try {
      const payload = await response.json();
      if (payload && payload.error) detail = payload.error;
    } catch (error) {
      detail.message = response.statusText;
    }
    showError(errorText(detail));
    const failure = new Error(detail.code);
    failure.detail = detail;
    throw failure;
  }
  if (response.status === 204) return null;
  return response.json();
}

function bind(id, action) {
  $(id).addEventListener("click", () => action().catch(quiet));
}

function loadAuth() {
  state.token = sessionStorage.getItem("adminToken") || "";
  state.operator = sessionStorage.getItem("adminOperator") || "admin";
  $("token-input").value = state.token;
  $("operator-input").value = state.operator;
  $("auth-state").textContent = state.token ? "口令已从当前标签页载入" : "未填写口令";
}

function saveAuth() {
  state.token = $("token-input").value.trim();
  state.operator = $("operator-input").value.trim() || "admin";
  sessionStorage.setItem("adminToken", state.token);
  sessionStorage.setItem("adminOperator", state.operator);
  $("auth-state").textContent = state.token ? "口令已临时保存在当前标签页" : "未填写口令";
  hideError();
}

function switchPage(name) {
  stopPolling();
  document.querySelectorAll("#tabs button").forEach((item) => {
    const active = item.dataset.page === name;
    item.classList.toggle("active", active);
    if (active) item.setAttribute("aria-current", "page");
    else item.removeAttribute("aria-current");
  });
  ["overview", "leads", "tasks", "compliance", "config", "logs"].forEach((page) => {
    $("page-" + page).classList.toggle("hidden", page !== name);
  });
  const loaders = {
    overview: loadOverview,
    leads: loadLeads,
    tasks: loadTasks,
    compliance: loadCompliance,
    config: loadConfig,
    logs: loadLogs,
  };
  loaders[name]().catch(quiet);
}

/* 可展开明细行：点击数据行切换展开区（忽略行内控件自身的点击）。 */
function expandableRow(cells, detailNode) {
  const row = make("tr", {}, cells);
  const detail = make("tr", { class: "expand-row hidden" }, [
    make("td", { colspan: String(cells.length) }, [detailNode]),
  ]);
  row.addEventListener("click", (event) => {
    if (event.target.closest("input, button, select, label, a")) return;
    detail.classList.toggle("hidden");
  });
  return [row, detail];
}
