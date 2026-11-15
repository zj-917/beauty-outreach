/* 任务详情：状态横幅、发送分段、实时动态、明细与生命周期。 */

import { api, errorText } from "../api.js";
import { invalidateOverview } from "../store.js";
import {
  h,
  clear,
  pageHead,
  guide,
  card,
  button,
  badge,
  chip,
  codeChip,
  reasonChips,
  table,
  kpi,
  empty,
  callout,
  openDrawer,
  confirmDialog,
  toast,
  toastError,
  fmtTime,
  fmtPercent,
  fmtDuration,
  input,
  select,
} from "../ui.js";
import { funnel, ring } from "../charts.js";
import {
  TASK_STATUS_LABELS,
  TASK_STATUS_GUIDE,
  ITEM_STATUS_LABELS,
  REASON_LABELS,
  PHASE_LABELS,
  OUTCOME_LABELS,
  TASK_EVENT_LABELS,
  PAUSE_REASON_LABELS,
  ACTION_DISABLED_REASON,
  TONE,
} from "../labels.js";
import { go } from "../router.js";

const GROUPS = [
  { key: "all", label: "全部" },
  { key: "success", label: "成功" },
  { key: "failed", label: "失败" },
  { key: "skipped", label: "跳过" },
];

const SUCCESS_STATUSES = new Set(["SENT", "DELIVERED", "READ"]);
const ALLOWED_ACTIONS = {
  DRAFT: ["start", "cancel"],
  RUNNING: ["pause", "cancel"],
  PAUSED: ["resume", "cancel"],
  COMPLETED: [],
  CANCELLED: [],
};
const ACTION_LABELS = { start: "启动", pause: "暂停", resume: "恢复", cancel: "取消" };
const ACTION_KINDS = { start: "primary", resume: "primary", pause: "", cancel: "danger-ghost" };

let pageView = null;

export async function render(view, params) {
  pageView = view;
  const id = Number(params.get("id") || 0);
  clear(view);
  if (!id) {
    view.append(
      pageHead("任务详情", "缺少任务编号"),
      callout("链接里没有任务编号。请从任务列表打开一个任务。", "warn", button("回任务列表", { kind: "primary", onClick: () => go("#/tasks") }))
    );
    return;
  }
  view.append(h("div", { class: "loading" }, [h("span", { class: "spinner" }), "正在读取任务详情…"]));

  const state = { group: "all", status: "", reason: "", q: "", items: [], campaign: null, stats: null, logs: [], timeline: [], timer: null, polling: false };
  try {
    await loadAll(id, state);
  } catch (error) {
    clear(view);
    view.append(
      pageHead("任务详情", `任务 #${id}`),
      callout(`读取失败：${errorText(error)}`, "danger", button("重试", { kind: "primary", onClick: () => render(view, params) }))
    );
    return;
  }

  clear(view);
  const headerHost = h("div", { class: "status-host" });
  const funnelHost = h("div", { class: "funnel-host" });
  const skipHost = h("div", { class: "skip-host" });
  const kpiHost = h("div", { class: "kpi-row" });
  const feedHost = h("div", { class: "feed-host" });
  const timelineHost = h("div", { class: "timeline-host" });
  const tabsHost = h("div", { class: "item-tabs" });
  const filtersHost = h("div", { class: "item-filters" });
  const itemsHost = h("div", { class: "item-table" });
  const itemsCount = h("span", { class: "muted" });

  const statusSelect = select(
    dictOptions(ITEM_STATUS_LABELS, "全部状态"),
    "",
    { onChange: () => { state.status = statusSelect.value; paintItems(); } }
  );
  const reasonSelect = select(
    dictOptions(REASON_LABELS, "全部原因"),
    "",
    { onChange: () => { state.reason = reasonSelect.value; paintItems(); } }
  );
  const search = input({ type: "search", placeholder: "搜索用户名或脱敏号码…" });
  search.addEventListener("input", () => { state.q = search.value.trim(); paintItems(); });
  filtersHost.append(statusSelect, reasonSelect, search);

  view.append(
    pageHead(state.campaign.name, `任务 #${state.campaign.id} · 模板 #${state.campaign.template_id} · 创建于 ${fmtTime(state.campaign.created_at)}`, [
      button("刷新", { iconName: "refresh", onClick: () => refreshAll(id, state, paintAll) }),
      button("回任务列表", { onClick: () => go("#/tasks") }),
    ]),
    guide(
      "本页看任务状态、发送结果分段、实时动态与每条明细；运行中会自动刷新。",
      "下一步：草稿先点「启动」；运行中等待刷新或点「暂停」；完成后查看明细与日志。"
    ),
    headerHost,
    h("div", { class: "grid two wide-left" }, [
      card("发送结果分段", "各段数量来自任务统计；点击分段可跳到对应明细。", funnelHost, skipHost, kpiHost),
      card("实时动态", "运行中每 2 秒刷新；这里显示最近的处理事件。", feedHost),
    ]),
    card(
      "任务明细",
      "按成功 / 失败 / 跳过分组；状态与原因都给出中文释义。",
      tabsHost,
      filtersHost,
      itemsCount,
      itemsHost
    ),
    card("任务生命周期", "创建、启动、暂停、恢复、完成等关键事件。", timelineHost)
  );

  function paintAll() {
    paintHeader();
    paintFunnel();
    paintKpis();
    paintTabs();
    paintItems();
    paintFeed();
    paintTimeline();
    syncPolling();
  }

  function paintHeader() {
    clear(headerHost);
    const campaign = state.campaign;
    const stats = state.stats;
    const status = campaign.status;
    const guideText = TASK_STATUS_GUIDE[status] || ["", ""];
    const processed = Math.max(0, (stats.total || 0) - (stats.in_progress || 0));
    const percent = stats.total ? (processed / stats.total) * 100 : 0;
    const actions = ["start", "pause", "resume", "cancel"].map((action) => {
      const allowed = (ALLOWED_ACTIONS[status] || []).includes(action);
      return button(ACTION_LABELS[action], {
        kind: ACTION_KINDS[action],
        disabled: !allowed,
        title: allowed ? "" : ACTION_DISABLED_REASON[action],
        onClick: () => control(id, state, action, paintAll),
      });
    });
    headerHost.append(
      h("section", { class: `status-banner tone-${TONE[status] || "muted"}` }, [
        h("div", { class: "status-main" }, [
          h("div", { class: "status-title" }, [
            h("span", { class: "dot" }),
            h("h3", {}, TASK_STATUS_LABELS[status] ? TASK_STATUS_LABELS[status][0] : status),
            h("span", { class: "mono muted" }, status),
            status === "RUNNING" ? chip("每 2 秒自动刷新", "info") : null,
          ]),
          h("p", { class: "status-desc" }, guideText[0]),
          h("p", { class: "status-next" }, guideText[1]),
          campaign.pause_reason
            ? callout(`暂停原因：${(PAUSE_REASON_LABELS[campaign.pause_reason] || [campaign.pause_reason])[0]}——${(PAUSE_REASON_LABELS[campaign.pause_reason] || ["", ""])[1]}`, campaign.pause_reason === "CIRCUIT_OPEN" ? "danger" : "warn")
            : null,
          h("div", { class: "status-actions" }, actions),
        ]),
        h("div", { class: "status-side" }, [
          ring(percent, {
            size: 118,
            stroke: 10,
            tone: status === "COMPLETED" ? "ok" : status === "PAUSED" ? "warn" : "info",
            label: `${processed}/${stats.total || 0}`,
            hint: "已处理 / 总数",
          }),
        ]),
      ])
    );
  }

  function paintFunnel() {
    clear(funnelHost);
    const by = state.stats.by_status || {};
    const delivered = (by.DELIVERED || 0) + (by.READ || 0);
    funnelHost.append(
      funnel(
        [
          { key: "all", label: "目标", value: state.stats.total || 0, tone: "muted" },
          { key: "skipped", label: "跳过", value: state.stats.skipped || 0, tone: "muted" },
          { key: "success", label: "已发送", value: state.stats.success || 0, tone: "info" },
          { key: "success", label: "送达", value: delivered, tone: "ok" },
          { key: "success", label: "已读", value: by.READ || 0, tone: "ok" },
          { key: "failed", label: "失败", value: state.stats.failed || 0, tone: "danger" },
        ],
        (step) => {
          state.group = step.key;
          state.status = "";
          state.reason = "";
          statusSelect.value = "";
          reasonSelect.value = "";
          paintTabs();
          paintItems();
          itemsHost.scrollIntoView({ behavior: "smooth", block: "center" });
        }
      )
    );
    clear(skipHost);
    const skip = state.stats.skip_reasons || {};
    const failure = state.stats.failure_reasons || {};
    if (Object.keys(skip).length || Object.keys(failure).length) {
      skipHost.append(
        h("div", { class: "reason-block" }, [
          h("h4", {}, "跳过原因分布"),
          Object.keys(skip).length ? reasonChips(skip, REASON_LABELS) : h("span", { class: "muted" }, "没有跳过"),
          h("h4", {}, "失败原因分布"),
          Object.keys(failure).length ? reasonChips(failure, REASON_LABELS) : h("span", { class: "muted" }, "没有失败"),
        ])
      );
    }
  }

  function paintKpis() {
    clear(kpiHost);
    const stats = state.stats;
    const attempts = stats.attempts_histogram || {};
    const attemptText = Object.entries(attempts)
      .map(([count, value]) => `${count} 次 ${value} 条`)
      .join(" · ");
    kpiHost.append(
      kpi("成功率", fmtPercent(stats.success_rate), "成功 ÷（成功 + 失败）", "ok"),
      kpi("重试次数", stats.retry_total || 0, "额外的重试总次数", "warn"),
      kpi("耗时", fmtDuration(stats.elapsed_seconds), "从启动到完成", "info"),
      kpi("尝试分布", attemptText || "—", "每条明细尝试了几次", "muted")
    );
  }

  function paintTabs() {
    clear(tabsHost);
    const stats = state.stats;
    const counts = { all: stats.total || 0, success: stats.success || 0, failed: stats.failed || 0, skipped: stats.skipped || 0 };
    for (const group of GROUPS) {
      tabsHost.append(
        h(
          "button",
          {
            type: "button",
            class: state.group === group.key ? "tab active" : "tab",
            onclick: () => {
              state.group = group.key;
              paintTabs();
              paintItems();
            },
          },
          [group.label, h("span", { class: "tab-count" }, String(counts[group.key] || 0))]
        )
      );
    }
  }

  function filteredItems() {
    const query = state.q.toLowerCase();
    return state.items.filter((item) => {
      if (state.group === "success" && !SUCCESS_STATUSES.has(item.status)) return false;
      if (state.group === "failed" && item.status !== "FAILED") return false;
      if (state.group === "skipped" && item.status !== "SKIPPED") return false;
      if (state.status && item.status !== state.status) return false;
      if (state.reason && item.reason_code !== state.reason) return false;
      if (query) {
        const haystack = `${item.lead_username || ""} ${item.phone_masked || ""}`.toLowerCase();
        if (!haystack.includes(query)) return false;
      }
      return true;
    });
  }

  function paintItems() {
    const rows = filteredItems();
    clear(itemsHost);
    itemsCount.textContent = `共 ${rows.length} 条明细`;
    itemsHost.append(
      table(
        ["用户名", "号码（脱敏）", "状态", "原因", "尝试", "下次重试 / 时间", "操作"],
        rows.map((item) => [
          h("span", { class: "mono" }, item.lead_username ? `@${item.lead_username}` : `#${item.lead_id}`),
          item.phone_masked || "—",
          badge(ITEM_STATUS_LABELS, item.status),
          item.reason_code ? codeChip(item.reason_code, REASON_LABELS) : "—",
          String(item.attempts || 0),
          item.next_attempt_at ? fmtTime(item.next_attempt_at) : fmtTime(item.sent_at || item.updated_at),
          button("日志", { onClick: () => go(`#/records?tab=send&task_id=${id}&item_id=${item.id}`) }),
        ]),
        {
          emptyText: "没有符合当前筛选的明细。可以切换分组或清空筛选。",
          onRowClick: (index) => openItemDrawer(id, rows[index]),
        }
      )
    );
  }

  function paintFeed() {
    clear(feedHost);
    if (!state.logs.length) {
      feedHost.append(empty("还没有发送日志。任务启动后，这里会实时出现处理事件。"));
      return;
    }
    feedHost.append(
      h("div", { class: "feed" }, state.logs.map((log) => h("div", { class: "feed-row" }, [
        h("span", { class: `feed-dot tone-${TONE[log.outcome] || "muted"}` }),
        h("div", { class: "feed-copy" }, [
          h("div", {}, [
            codeChip(log.phase, PHASE_LABELS),
            h("span", { class: "feed-outcome" }, (OUTCOME_LABELS[log.outcome] || [log.outcome])[0]),
            log.reason_code ? codeChip(log.reason_code, REASON_LABELS) : null,
          ]),
          h("div", { class: "muted" }, `明细 #${log.item_id}${log.attempt_no ? ` · 第 ${log.attempt_no} 次` : ""} · ${fmtTime(log.created_at)}${log.latency_ms !== null ? ` · ${log.latency_ms} ms` : ""}`),
        ]),
      ]))),
      h("div", { class: "btn-row" }, [
        button("查看全部发送日志", { onClick: () => go(`#/records?tab=send&task_id=${id}`) }),
      ])
    );
  }

  function paintTimeline() {
    clear(timelineHost);
    if (!state.timeline.length) {
      timelineHost.append(empty("还没有生命周期事件。"));
      return;
    }
    timelineHost.append(
      h("div", { class: "timeline" }, state.timeline.map((event) => h("div", { class: "timeline-row" }, [
        h("span", { class: "timeline-dot" }),
        h("div", { class: "timeline-copy" }, [
          h("strong", {}, (TASK_EVENT_LABELS[event.event] || [event.event])[0]),
          h("span", { class: "muted" }, ` · ${event.actor} · ${fmtTime(event.ts)}`),
          event.request_id ? h("span", { class: "muted mono" }, ` · ${event.request_id}`) : null,
        ]),
      ])))
    );
  }

  function syncPolling() {
    if (state.campaign && state.campaign.status === "RUNNING") {
      if (!state.timer) {
        state.timer = window.setInterval(async () => {
          if (document.hidden || state.polling) return;
          state.polling = true;
          try {
            await loadAll(id, state);
            paintHeader();
            paintFunnel();
            paintKpis();
            paintTabs();
            paintItems();
            paintFeed();
            paintTimeline();
          } catch (error) {
            /* 轮询失败静默重试，下一次 tick 继续。 */
          } finally {
            state.polling = false;
          }
        }, 2000);
      }
    } else if (state.timer) {
      window.clearInterval(state.timer);
      state.timer = null;
    }
  }

  paintAll();
  return () => {
    if (state.timer) window.clearInterval(state.timer);
  };
}

function dictOptions(dict, allLabel) {
  return [
    { value: "", label: allLabel },
    ...Object.entries(dict).map(([code, entry]) => ({ value: code, label: `${entry[0]}（${code}）` })),
  ];
}

async function loadAll(id, state) {
  const [campaign, stats, items, logs, timeline] = await Promise.all([
    api(`/campaigns/${id}`),
    api(`/campaigns/${id}/stats`),
    api(`/campaigns/${id}/items`, { query: { page_size: 100 } }),
    api("/send-logs", { query: { task_id: id, page_size: 8 } }),
    api(`/campaigns/${id}/timeline`),
  ]);
  state.campaign = campaign;
  state.stats = stats;
  state.items = items.items || [];
  state.logs = logs.items || [];
  state.timeline = timeline.events || [];
}

async function refreshAll(id, state, paintAll) {
  try {
    await loadAll(id, state);
    paintAll();
    toast("已刷新。", "success");
  } catch (error) {
    toastError(error, "刷新失败");
  }
}

async function control(id, state, action, paintAll) {
  if (action === "cancel") {
    const ok = await confirmDialog("取消后，尚未发送的线索会被跳过。确定取消这个任务吗？", {
      danger: true,
      confirmLabel: "确定取消",
    });
    if (!ok) return;
  }
  try {
    await api(`/campaigns/${id}/${action}`, { method: "POST" });
    invalidateOverview();
    toast(`已${ACTION_LABELS[action]}任务。`, "success");
    await loadAll(id, state);
    paintAll();
  } catch (error) {
    toastError(error, "操作失败");
    try {
      await loadAll(id, state);
      paintAll();
    } catch (inner) {
      /* 保持当前界面。 */
    }
  }
}

function openItemDrawer(taskId, item) {
  const drawer = openDrawer(
    `明细 #${item.id}`,
    h("div", { class: "drawer-content" }, [
      h("div", { class: "kv-list" }, [
        h("div", { class: "kv" }, [h("span", { class: "kv-label" }, "用户名"), h("span", { class: "kv-value mono" }, item.lead_username ? `@${item.lead_username}` : `#${item.lead_id}`)]),
        h("div", { class: "kv" }, [h("span", { class: "kv-label" }, "号码（脱敏）"), h("span", { class: "kv-value" }, item.phone_masked || "—")]),
        h("div", { class: "kv" }, [h("span", { class: "kv-label" }, "状态"), h("span", { class: "kv-value" }, badge(ITEM_STATUS_LABELS, item.status))]),
        h("div", { class: "kv" }, [h("span", { class: "kv-label" }, "原因"), h("span", { class: "kv-value" }, item.reason_code ? codeChip(item.reason_code, REASON_LABELS) : "—")]),
        h("div", { class: "kv" }, [h("span", { class: "kv-label" }, "尝试次数"), h("span", { class: "kv-value" }, String(item.attempts || 0))]),
        h("div", { class: "kv" }, [h("span", { class: "kv-label" }, "下次重试"), h("span", { class: "kv-value" }, fmtTime(item.next_attempt_at))]),
        h("div", { class: "kv" }, [h("span", { class: "kv-label" }, "最近错误"), h("span", { class: "kv-value" }, item.last_error_code || "—")]),
        h("div", { class: "kv" }, [h("span", { class: "kv-label" }, "渠道消息号"), h("span", { class: "kv-value mono" }, item.provider_message_id || "—")]),
        h("div", { class: "kv" }, [h("span", { class: "kv-label" }, "发送时间"), h("span", { class: "kv-value" }, fmtTime(item.sent_at))]),
        h("div", { class: "kv" }, [h("span", { class: "kv-label" }, "送达时间"), h("span", { class: "kv-value" }, fmtTime(item.delivered_at))]),
        h("div", { class: "kv" }, [h("span", { class: "kv-label" }, "已读时间"), h("span", { class: "kv-value" }, fmtTime(item.read_at))]),
      ]),
      h("div", { class: "btn-row" }, [
        button("查看这条的发送日志", {
          kind: "primary",
          onClick: () => {
            drawer.close();
            go(`#/records?tab=send&task_id=${taskId}&item_id=${item.id}`);
          },
        }),
      ]),
    ]),
    { width: 520 }
  );
}
