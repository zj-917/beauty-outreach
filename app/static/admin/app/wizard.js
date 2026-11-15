/* 演示向导：把 10 分钟脚本变成可勾选的真实数据路线。 */

import { api, errorText } from "./api.js";
import { DEMO_STEPS } from "./labels.js";
import {
  h,
  clear,
  icon,
  badge,
  button,
  openDrawer,
  skeleton,
  empty,
  callout,
} from "./ui.js";
import { go } from "./router.js";
import { loadOverview } from "./store.js";

const PREVIEW_KEY = "bo.previewSeen";

export function markPreviewSeen() {
  sessionStorage.setItem(PREVIEW_KEY, "1");
}

function statusChip(done, current) {
  if (done) return h("span", { class: "step-state done" }, [icon("check", 14), "已完成"]);
  if (current) return h("span", { class: "step-state current" }, "当前步骤");
  return h("span", { class: "step-state todo" }, "待办");
}

function stepRoute(step, campaigns) {
  const latest = campaigns && campaigns.items && campaigns.items[0];
  if (step.key === "create" || step.key === "preview") return "#/tasks?new=1";
  if ((step.key === "start" || step.key === "finish") && latest) return `#/tasks/${latest.id}`;
  return step.route;
}

export async function openWizard() {
  const body = h("div", { class: "wizard-body" }, skeleton(5));
  const drawer = openDrawer("演示向导", body, { width: 460 });
  await render(body, drawer);
}

async function render(body, drawer) {
  clear(body);
  body.append(skeleton(5));
  let data;
  try {
    const [overview, batches, campaigns, suppressions, leads] = await Promise.all([
      loadOverview(true),
      api("/lead-batches", { query: { page_size: 5 } }),
      api("/campaigns", { query: { page_size: 20 } }),
      api("/suppressions"),
      api("/leads", { query: { page_size: 100 } }),
    ]);
    data = { overview, batches, campaigns, suppressions, leads };
  } catch (error) {
    clear(body);
    body.append(
      callout(`读取演示状态失败：${errorText(error)}`, "danger"),
      h("div", { class: "btn-row" }, [
        button("重试", { kind: "primary", onClick: () => render(body, drawer) }),
      ])
    );
    return;
  }

  const done = {
    import: (data.batches.total || 0) > 0,
    screen: (data.leads.items || []).some((lead) => lead.score !== null && lead.score !== undefined),
    review: (data.leads.items || []).some((lead) => lead.decision_source === "MANUAL"),
    create: (data.campaigns.total || 0) > 0,
    preview: sessionStorage.getItem(PREVIEW_KEY) === "1",
    start: (data.campaigns.items || []).some((campaign) => campaign.started_at),
    stop: (data.suppressions || []).some((item) => item.type === "UNSUBSCRIBE"),
    finish: (data.campaigns.items || []).some((campaign) => campaign.status === "COMPLETED"),
  };
  const doneCount = Object.values(done).filter(Boolean).length;
  let currentKey = null;
  for (const step of DEMO_STEPS) {
    if (!done[step.key]) {
      currentKey = step.key;
      break;
    }
  }

  clear(body);
  body.append(
    h("div", { class: "wizard-head" }, [
      h("p", { class: "wizard-intro" }, "按顺序走完这 8 步，就能完整演示线索、筛选、触达、合规与审计。"),
      h("div", { class: "wizard-progress" }, [
        h("div", { class: "wizard-progress-bar" }, [
          h("i", { style: `width:${(doneCount / DEMO_STEPS.length) * 100}%` }),
        ]),
        h("span", {}, `${doneCount} / ${DEMO_STEPS.length} 已完成`),
      ]),
    ])
  );
  const list = h("ol", { class: "wizard-steps" });
  DEMO_STEPS.forEach((step, index) => {
    const isDone = done[step.key];
    const isCurrent = step.key === currentKey;
    list.append(
      h("li", { class: `wizard-step ${isDone ? "done" : ""} ${isCurrent ? "current" : ""}` }, [
        h("span", { class: "step-index" }, String(index + 1)),
        h("div", { class: "step-copy" }, [
          h("div", { class: "step-title" }, [
            h("strong", {}, step.title),
            statusChip(isDone, isCurrent),
          ]),
          h("p", { class: "step-desc" }, step.desc),
          h("button", {
            type: "button",
            class: "link-button",
            onclick: () => {
              drawer.close();
              go(stepRoute(step, data.campaigns));
            },
          }, ["去操作", icon("arrow", 14)]),
        ]),
      ])
    );
  });
  body.append(list);
  body.append(
    h("div", { class: "wizard-foot" }, [
      button("刷新状态", { onClick: () => render(body, drawer), iconName: "refresh" }),
      h("span", { class: "muted" }, "步骤状态来自真实数据，不会自动替你操作。"),
    ])
  );
}
