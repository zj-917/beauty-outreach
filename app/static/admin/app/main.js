/* 入口：鉴权门、侧栏、顶栏、命令面板、演示向导入口。 */

import { api, getAuth, setAuth, clearAuth, checkHealth, ApiError } from "./api.js";
import { h, clear, icon, button, field, input, toast, toastError, openModal } from "./ui.js";
import { loadOverview, onOverviewChange, invalidateOverview } from "./store.js";
import { startRouter, navigate, setRouteListener, currentRoute, go } from "./router.js";
import { openWizard } from "./wizard.js";

const NAV = [
  { route: "#/dashboard", label: "驾驶舱", iconName: "dashboard" },
  { route: "#/leads", label: "线索", iconName: "leads" },
  { route: "#/tasks", label: "任务", iconName: "tasks" },
  { route: "#/compliance", label: "合规", iconName: "compliance" },
  { route: "#/records", label: "记录", iconName: "records" },
  { route: "#/settings", label: "配置", iconName: "settings" },
];

let gateVisible = false;
let authBusy = false;

function navButton(item) {
  const count = h("span", { class: "nav-count hidden" });
  const node = h(
    "button",
    {
      type: "button",
      class: "nav-item",
      dataset: { route: item.route },
      title: item.label,
      onclick: () => go(item.route),
    },
    [icon(item.iconName, 19), h("span", { class: "nav-label" }, item.label), count]
  );
  return node;
}

function buildNav() {
  const nav = document.getElementById("side-nav");
  clear(nav);
  for (const item of NAV) nav.append(navButton(item));
}

function setCount(route, value, tone) {
  const item = document.querySelector(`.nav-item[data-route="${route}"]`);
  if (!item) return;
  const count = item.querySelector(".nav-count");
  if (!value) {
    count.classList.add("hidden");
    count.textContent = "";
    return;
  }
  count.textContent = String(value);
  count.className = `nav-count tone-${tone}`;
}

function updateCounts(overview) {
  if (!overview) return;
  const pending = (overview.leads_by_status || {}).PENDING_REVIEW || 0;
  const running = (overview.campaigns_by_status || {}).RUNNING || 0;
  const drafts = (overview.campaigns_by_status || {}).DRAFT || 0;
  setCount("#/leads", pending, "warn");
  setCount("#/tasks", running || drafts, running ? "info" : "accent");
}

function setActive(route) {
  document.querySelectorAll(".nav-item").forEach((node) => {
    const active = node.dataset.route === route;
    node.classList.toggle("active", active);
    if (active) node.setAttribute("aria-current", "page");
    else node.removeAttribute("aria-current");
  });
}

function updateTopbar(route) {
  document.getElementById("page-title").textContent = `工作台 / ${route.title}`;
  document.getElementById("page-subtitle").textContent = "";
  document.title = `${route.title} · Beauty Outreach`;
}

function updateOperator() {
  const node = document.getElementById("operator-button");
  const { operator } = getAuth();
  clear(node);
  node.append(icon("user", 16), h("span", {}, operator || "admin"));
}

function showGate(message = "") {
  const root = document.getElementById("auth-root");
  const app = document.getElementById("app");
  if (gateVisible) {
    const error = root.querySelector(".auth-error");
    if (error && message) error.textContent = message;
    const token = root.querySelector("input[type='password']");
    if (token) token.focus();
    return;
  }
  gateVisible = true;
  app.classList.add("hidden");
  const token = input({ type: "password", placeholder: "请输入访问口令", autocomplete: "off" });
  const operator = input({ type: "text", value: getAuth().operator || "admin", placeholder: "操作人", autocomplete: "off" });
  const error = h("p", { class: "auth-error" }, message);
  const submit = h("button", { class: "primary block auth-submit", type: "button" }, "进入控制台");
  async function enter() {
    if (authBusy) return;
    authBusy = true;
    submit.disabled = true;
    submit.textContent = "验证中…";
    error.textContent = "";
    setAuth(token.value, operator.value);
    try {
      await api("/stats/overview");
      hideGate();
      updateOperator();
      invalidateOverview();
      await loadOverview(true);
      if (!location.hash) location.hash = "#/dashboard";
      await navigate();
      toast("口令验证通过，欢迎回来。", "success");
    } catch (err) {
      error.textContent =
        err instanceof ApiError && err.code === "UNAUTHORIZED"
          ? "口令不正确。请向管理员索取；本地演示口令见 README。"
          : err && err.code === "NETWORK_ERROR"
            ? "无法连接服务器，请确认服务已启动。"
            : `进入失败：${err && err.message ? err.message : String(err)}`;
      token.focus();
    } finally {
      authBusy = false;
      submit.disabled = false;
      submit.textContent = "进入控制台";
    }
  }
  submit.addEventListener("click", enter);
  token.addEventListener("keydown", (event) => {
    if (event.key === "Enter") enter();
  });
  operator.addEventListener("keydown", (event) => {
    if (event.key === "Enter") enter();
  });

  clear(root);
  root.append(
    h("div", { class: "auth-overlay" }, [
      h("div", { class: "auth-card" }, [
        h("div", { class: "auth-brand" }, [
          h("span", { class: "brand-mark" }, "BO"),
          h("div", {}, [h("strong", {}, "Beauty Outreach"), h("span", {}, "触达指挥台")]),
        ]),
        h("h1", {}, "欢迎回来"),
        h("p", { class: "auth-sub" }, "这是一个合规优先的 Mock 演示环境：不会连接 Instagram 或 WhatsApp 的真实平台。"),
        field("访问口令（Admin Token）", token, "不是账号密码，而是一枚访问口令；本地演示口令见 README。"),
        field("操作人", operator, "只用于写入审计记录，会显示在操作日志里。"),
        error,
        submit,
        h("p", { class: "auth-note muted" }, "口令只保存在当前标签页的 sessionStorage，关闭标签页即失效。"),
      ]),
    ])
  );
  window.setTimeout(() => token.focus(), 50);
}

function hideGate() {
  gateVisible = false;
  document.getElementById("auth-root").replaceChildren();
  document.getElementById("app").classList.remove("hidden");
}

function showOperatorMenu() {
  const { token, operator } = getAuth();
  const operatorInput = input({ type: "text", value: operator, placeholder: "操作人" });
  const modal = openModal(
    "操作人",
    h("div", {}, [
      h("p", { class: "muted" }, "操作人只用于审计记录，不影响权限。"),
      field("操作人", operatorInput),
      h("div", { class: "btn-row end" }, [
        button("切换口令", {
          kind: "danger-ghost",
          onClick: () => {
            modal.close();
            clearAuth();
            showGate("请重新输入访问口令。");
          },
        }),
        button("取消", { onClick: () => modal.close() }),
        button("保存", {
          kind: "primary",
          onClick: () => {
            setAuth(token, operatorInput.value);
            updateOperator();
            modal.close();
            toast("操作人已更新。", "success");
          },
        }),
      ]),
    ]),
    { width: 460 }
  );
}

function showCompliance() {
  openModal(
    "演示环境说明",
    h("div", { class: "prose" }, [
      h("p", {}, "这套界面只连接本地 Mock 服务，不会访问 Instagram、WhatsApp 或 Meta 的真实接口。"),
      h("ul", {}, [
        h("li", {}, "线索来自内置示例数据或你上传的 CSV / JSON 文件；Instagram 官方接口仅保留 Stub。"),
        h("li", {}, "发送渠道是 Mock 沙箱；真实渠道实现会在调用时返回未启用。"),
        h("li", {}, "所有号码在界面与接口响应中都是脱敏值，完整号码不会出现在页面上。"),
        h("li", {}, "退订与黑名单优先级最高，任何任务都不能绕过它们。"),
      ]),
    ]),
    { width: 560 }
  );
}

function showPalette() {
  const list = h("div", { class: "palette-list" });
  const search = input({ type: "text", placeholder: "搜索页面或动作…" });
  const actions = [
    ...NAV.map((item) => ({ label: `打开「${item.label}」`, hint: "页面", run: () => go(item.route) })),
    { label: "打开演示向导", hint: "动作", run: () => openWizard() },
  ];
  function render() {
    const query = search.value.trim().toLowerCase();
    clear(list);
    for (const action of actions.filter((item) => !query || item.label.toLowerCase().includes(query))) {
      list.append(
        h(
          "button",
          {
            type: "button",
            class: "palette-item",
            onclick: () => {
              modal.close();
              action.run();
            },
          },
          [h("span", {}, action.label), h("span", { class: "muted" }, action.hint)]
        )
      );
    }
    if (!list.children.length) list.append(h("p", { class: "muted" }, "没有匹配项。"));
  }
  search.addEventListener("input", render);
  const modal = openModal("快速跳转", h("div", {}, [search, list]), { width: 520 });
  render();
  window.setTimeout(() => search.focus(), 40);
}

async function loadSystemStatus() {
  const host = document.getElementById("system-status");
  try {
    const health = await checkHealth();
    clear(host);
    host.append(
      h("span", { class: `dot tone-${health.db === "ok" ? "ok" : "danger"}` }),
      h("span", {}, `数据库${health.db === "ok" ? "正常" : "异常"}`),
      h("span", { class: "dot tone-muted" }),
      h("span", {}, `Worker ${health.worker === "disabled" ? "未启用" : "运行中"}`)
    );
  } catch (error) {
    clear(host);
    host.append(h("span", { class: "dot tone-danger" }), h("span", {}, "健康检查失败"));
  }
}

function boot() {
  buildNav();
  updateOperator();
  const chip = document.getElementById("compliance-chip");
  chip.append(icon("shield", 15), h("span", {}, "Mock 沙箱 · 号码已脱敏"));
  chip.addEventListener("click", showCompliance);
  document.getElementById("operator-button").addEventListener("click", showOperatorMenu);
  document.getElementById("palette-button").addEventListener("click", showPalette);
  document.getElementById("wizard-button").addEventListener("click", () => openWizard());

  setRouteListener((base, route) => {
    setActive(base);
    updateTopbar(route);
  });
  startRouter();
  window.addEventListener("bo:unauthorized", () => {
    if (authBusy) return;
    showGate("登录状态已失效，请重新输入口令。");
  });
  window.addEventListener("keydown", (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      if (!gateVisible) showPalette();
    }
  });
  onOverviewChange(updateCounts);

  const { token } = getAuth();
  if (!token) {
    showGate();
    return;
  }
  loadOverview(true)
    .then(async () => {
      hideGate();
      updateOperator();
      loadSystemStatus();
      if (!location.hash) location.hash = "#/dashboard";
      await navigate();
    })
    .catch((error) => {
      if (error instanceof ApiError && error.code === "UNAUTHORIZED") return;
      showGate(error && error.code === "NETWORK_ERROR" ? "无法连接服务器，请确认服务已启动。" : "");
    });
}

document.addEventListener("DOMContentLoaded", boot);
