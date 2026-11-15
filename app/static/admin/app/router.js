/* 哈希路由：深链接、页面清理、错误兜底。 */

import { h, clear, card, button } from "./ui.js";
import { errorText } from "./api.js";

const ROUTES = {
  "#/dashboard": {
    title: "驾驶舱",
    subtitle: "先看整体，再决定下一步做什么",
    module: () => import("./pages/dashboard.js"),
  },
  "#/leads": {
    title: "线索工作台",
    subtitle: "导入 → 自动筛选 → 人工审核 → 形成目标池",
    module: () => import("./pages/leads.js"),
  },
  "#/tasks": {
    title: "触达任务",
    subtitle: "创建任务、监控发送、查看结果",
    module: () => import("./pages/tasks.js"),
  },
  "#/compliance": {
    title: "合规中心",
    subtitle: "授权、黑名单、退订与演示沙盒",
    module: () => import("./pages/compliance.js"),
  },
  "#/records": {
    title: "记录与审计",
    subtitle: "审计追踪与每条发送的处理过程",
    module: () => import("./pages/records.js"),
  },
  "#/settings": {
    title: "配置",
    subtitle: "模板、关键词、频控规则与系统参数",
    module: () => import("./pages/settings.js"),
  },
};

const TASK_DETAIL = {
  title: "任务详情",
  subtitle: "状态、发送结果、实时动态与明细",
  module: () => import("./pages/task-detail.js"),
};

let cleanup = null;
let listener = null;

export function parseHash() {
  const raw = location.hash || "#/dashboard";
  const [path, query = ""] = raw.split("?");
  const parts = path.replace(/^#\//, "").split("/").filter(Boolean);
  const base = `#/${parts[0] || "dashboard"}`;
  const params = new URLSearchParams(query);
  if (parts[0] === "tasks" && parts[1]) params.set("id", parts[1]);
  return { base, parts, params, raw };
}

export function setRouteListener(fn) {
  listener = fn;
}

export function currentRoute() {
  const { base } = parseHash();
  return ROUTES[base] || ROUTES["#/dashboard"];
}

export function go(path) {
  if (location.hash === path) {
    navigate();
    return;
  }
  location.hash = path;
}

export async function navigate() {
  const { base, params, parts } = parseHash();
  let route = ROUTES[base] || ROUTES["#/dashboard"];
  if (parts[0] === "tasks" && parts[1]) route = TASK_DETAIL;
  if (cleanup) {
    try {
      cleanup();
    } catch (error) {
      /* 页面清理失败不阻断导航。 */
    }
    cleanup = null;
  }
  if (listener) listener(base, route, params);
  const view = document.getElementById("view");
  if (!view) return;
  clear(view);
  view.append(
    h("div", { class: "loading" }, [
      h("span", { class: "spinner" }),
      h("span", {}, "正在加载…"),
    ])
  );
  try {
    const module = await route.module();
    clear(view);
    const result = await module.render(view, params);
    if (typeof result === "function") cleanup = result;
  } catch (error) {
    clear(view);
    view.append(
      card(
        "页面加载失败",
        "这不影响其他页面；可以重试或回到驾驶舱。",
        h("p", { class: "error-text" }, errorText(error)),
        h("div", { class: "btn-row" }, [
          button("重试", { kind: "primary", onClick: () => navigate() }),
          button("回驾驶舱", { onClick: () => go("#/dashboard") }),
        ])
      )
    );
    if (!error || !error.code) console.error(error);
  }
  window.scrollTo({ top: 0, left: 0 });
}

export function startRouter() {
  window.addEventListener("hashchange", navigate);
}
