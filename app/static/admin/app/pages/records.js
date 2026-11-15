/* 记录与审计：审计日志、哈希链校验、发送日志查询与详情。 */

import { api, errorText } from "../api.js";
import {
  h,
  clear,
  pageHead,
  guide,
  card,
  tabs,
  button,
  badge,
  codeChip,
  table,
  pager,
  callout,
  openDrawer,
  field,
  input,
  select,
  toastError,
  fmtTime,
} from "../ui.js";
import {
  AUDIT_ACTION_LABELS,
  ENTITY_TYPE_LABELS,
  PHASE_LABELS,
  OUTCOME_LABELS,
  REASON_LABELS,
} from "../labels.js";
import { go } from "../router.js";

const state = {
  tab: "audit",
  audit: { actor: "", action: "", entity_type: "", entity_id: "", from: "", to: "", page: 1 },
  send: { task_id: "", item_id: "", phase: "", outcome: "", reason_code: "", from: "", to: "", page: 1 },
};

let pageView = null;
let pageParams = null;

/** 枚举下拉的标签更长（中文名 + 代码），单独给更宽的上限。 */
function wideField(labelText, control) {
  const node = field(labelText, control);
  node.classList.add("field-wide");
  return node;
}

export async function render(view, params) {
  pageView = view;
  pageParams = params;
  state.tab = params.get("tab") === "send" ? "send" : "audit";
  if (params.get("task_id")) state.send.task_id = params.get("task_id");
  if (params.get("item_id")) state.send.item_id = params.get("item_id");

  clear(view);
  view.append(h("div", { class: "loading" }, [h("span", { class: "spinner" }), "正在读取日志…"]));

  const auditData = state.tab === "audit" ? await loadAudit() : null;
  const sendData = state.tab === "send" ? await loadSend() : null;

  clear(view);
  view.append(
    pageHead("记录与审计", "审计追踪与每条发送的处理过程", [
      button("刷新", { iconName: "refresh", onClick: () => render(view, params) }),
    ]),
    guide(
      "审计日志记录「人对系统做了什么」；发送日志记录「系统对每条线索做了什么」。从任务明细点「日志」会直接跳到对应的发送日志。",
      state.tab === "send" ? "下一步：查看某条明细的阶段、结果与原因，或用筛选缩小范围。" : "下一步：先查审计，再按需切到发送日志。"
    ),
    tabs(
      [
        { key: "audit", label: "审计日志" },
        { key: "send", label: "发送日志" },
      ],
      state.tab,
      (key) => {
        state.tab = key;
        go(key === "send" ? "#/records?tab=send" : "#/records");
      }
    )
  );

  if (state.tab === "audit") {
    view.append(auditView(auditData));
  } else {
    view.append(sendView(sendData));
  }
}

function auditView(data) {
  const st = state.audit;
  const actor = input({ type: "text", value: st.actor, placeholder: "例如 admin" });
  const action = select(
    Object.entries(AUDIT_ACTION_LABELS).map(([code, entry]) => ({ value: code, label: `${entry[0]}（${code}）` })),
    st.action,
    { placeholder: "全部动作" }
  );
  const entityType = select(
    Object.entries(ENTITY_TYPE_LABELS).map(([code, entry]) => ({ value: code, label: `${entry[0]}（${code}）` })),
    st.entity_type,
    { placeholder: "全部对象" }
  );
  const entityId = input({ type: "text", value: st.entity_id, placeholder: "例如 7" });
  const from = input({ type: "text", value: st.from, placeholder: "ISO 时间（可选）" });
  const to = input({ type: "text", value: st.to, placeholder: "ISO 时间（可选）" });
  const verifyHost = h("div", { class: "verify-host" });

  function apply() {
    st.actor = actor.value.trim();
    st.action = action.value;
    st.entity_type = entityType.value;
    st.entity_id = entityId.value.trim();
    st.from = from.value.trim();
    st.to = to.value.trim();
    st.page = 1;
    if (pageView) render(pageView, new URLSearchParams({ tab: "audit" }));
  }
  function clearFilters() {
    Object.assign(st, { actor: "", action: "", entity_type: "", entity_id: "", from: "", to: "", page: 1 });
    if (pageView) render(pageView, new URLSearchParams({ tab: "audit" }));
  }
  async function verify() {
    try {
      const result = await api("/audit-logs/verify");
      verifyHost.replaceChildren(
        result.ok
          ? callout(`哈希链完整：已校验 ${result.count || 0} 条记录，没有发现断裂。`, "ok")
          : callout(`哈希链校验失败：第一条断裂记录 #${result.first_broken_id}。`, "danger")
      );
    } catch (error) {
      verifyHost.replaceChildren(callout(`校验失败：${errorText(error)}`, "danger"));
    }
  }

  return card(
    "审计日志",
    "只追加、不可修改；每条记录都带操作人与请求编号。",
    h("div", { class: "filter-grid" }, [
      field("操作人", actor),
      wideField("动作", action),
      wideField("对象类型", entityType),
      field("对象编号", entityId),
      field("开始时间", from),
      field("结束时间", to),
      h("div", { class: "filter-actions" }, [
        button("查询", { kind: "primary", onClick: apply }),
        button("清空筛选", { onClick: clearFilters }),
        button("验证哈希链", { iconName: "shield", onClick: verify }),
      ]),
    ]),
    verifyHost,
    data.items.length
      ? table(
          ["时间", "操作人", "动作", "对象", "对象编号", "请求编号"],
          data.items.map((entry) => [
            fmtTime(entry.ts),
            entry.actor,
            (AUDIT_ACTION_LABELS[entry.action] || [entry.action])[0],
            (ENTITY_TYPE_LABELS[entry.entity_type] || [entry.entity_type])[0],
            entry.entity_id,
            entry.request_id ? h("span", { class: "mono muted" }, entry.request_id) : "—",
          ]),
          {
            emptyText: "没有符合条件的审计记录。可以清空筛选后重试。",
            onRowClick: (index) => openAudit(entryAt(data.items[index])),
          }
        )
      : callout("没有符合条件的审计记录。可以清空筛选后重试。", "muted"),
    data.items.length ? pager(data, (page) => { st.page = page; if (pageView) render(pageView, new URLSearchParams({ tab: "audit" })); }) : null
  );
}

function entryAt(entry) {
  return entry;
}

function sendView(data) {
  const st = state.send;
  const taskId = input({ type: "text", value: st.task_id, placeholder: "例如 7" });
  const itemId = input({ type: "text", value: st.item_id, placeholder: "例如 42" });
  const phase = select(
    Object.entries(PHASE_LABELS).map(([code, entry]) => ({ value: code, label: `${entry[0]}（${code}）` })),
    st.phase,
    { placeholder: "全部阶段" }
  );
  const outcome = select(
    Object.entries(OUTCOME_LABELS).map(([code, entry]) => ({ value: code, label: `${entry[0]}（${code}）` })),
    st.outcome,
    { placeholder: "全部结果" }
  );
  const reason = select(
    Object.entries(REASON_LABELS).map(([code, entry]) => ({ value: code, label: `${entry[0]}（${code}）` })),
    st.reason_code,
    { placeholder: "全部原因" }
  );
  const from = input({ type: "text", value: st.from, placeholder: "ISO 时间（可选）" });
  const to = input({ type: "text", value: st.to, placeholder: "ISO 时间（可选）" });

  function apply() {
    st.task_id = taskId.value.trim();
    st.item_id = itemId.value.trim();
    st.phase = phase.value;
    st.outcome = outcome.value;
    st.reason_code = reason.value;
    st.from = from.value.trim();
    st.to = to.value.trim();
    st.page = 1;
    if (pageView) render(pageView, new URLSearchParams({ tab: "send" }));
  }
  function clearFilters() {
    Object.assign(st, { task_id: "", item_id: "", phase: "", outcome: "", reason_code: "", from: "", to: "", page: 1 });
    if (pageView) render(pageView, new URLSearchParams({ tab: "send" }));
  }

  return card(
    "发送日志",
    "每次发送前检查、渠道调用与回执都会留一行；号码只显示脱敏值。",
    h("div", { class: "filter-grid" }, [
      field("任务编号", taskId),
      field("明细编号", itemId),
      wideField("阶段", phase),
      wideField("结果", outcome),
      wideField("原因代码", reason),
      field("开始时间", from),
      field("结束时间", to),
      h("div", { class: "filter-actions" }, [
        button("查询", { kind: "primary", onClick: apply }),
        button("清空筛选", { onClick: clearFilters }),
      ]),
    ]),
    data.items.length
      ? table(
          ["时间", "任务", "明细", "阶段", "结果", "原因", "尝试", "耗时", "号码（脱敏）"],
          data.items.map((log) => [
            fmtTime(log.created_at),
            `#${log.task_id}`,
            `#${log.item_id}`,
            codeChip(log.phase, PHASE_LABELS),
            badge(OUTCOME_LABELS, log.outcome),
            log.reason_code ? codeChip(log.reason_code, REASON_LABELS) : "—",
            log.attempt_no === null || log.attempt_no === undefined ? "—" : String(log.attempt_no),
            log.latency_ms === null || log.latency_ms === undefined ? "—" : `${log.latency_ms} ms`,
            log.phone_masked || "—",
          ]),
          {
            emptyText: "没有符合条件的发送记录。可以从任务明细点「日志」进入，或清空筛选。",
            onRowClick: (index) => openSendLog(data.items[index]),
          }
        )
      : callout("没有符合条件的发送记录。可以从任务明细点「日志」进入，或清空筛选。", "muted"),
    data.items.length ? pager(data, (page) => { st.page = page; if (pageView) render(pageView, new URLSearchParams({ tab: "send" })); }) : null
  );
}

async function loadAudit() {
  const st = state.audit;
  return api("/audit-logs", {
    query: {
      actor: st.actor,
      action: st.action,
      entity_type: st.entity_type,
      entity_id: st.entity_id,
      from: st.from,
      to: st.to,
      page: st.page,
      page_size: 20,
    },
  });
}

async function loadSend() {
  const st = state.send;
  return api("/send-logs", {
    query: {
      task_id: st.task_id,
      item_id: st.item_id,
      phase: st.phase,
      outcome: st.outcome,
      reason_code: st.reason_code,
      from: st.from,
      to: st.to,
      page: st.page,
      page_size: 20,
    },
  });
}

function openAudit(entry) {
  openDrawer(
    `审计记录 #${entry.id}`,
    h("div", { class: "drawer-content" }, [
      h("div", { class: "kv-list" }, [
        h("div", { class: "kv" }, [h("span", { class: "kv-label" }, "时间"), h("span", { class: "kv-value" }, fmtTime(entry.ts))]),
        h("div", { class: "kv" }, [h("span", { class: "kv-label" }, "操作人"), h("span", { class: "kv-value" }, entry.actor)]),
        h("div", { class: "kv" }, [h("span", { class: "kv-label" }, "动作"), h("span", { class: "kv-value" }, (AUDIT_ACTION_LABELS[entry.action] || [entry.action])[0])]),
        h("div", { class: "kv" }, [h("span", { class: "kv-label" }, "对象"), h("span", { class: "kv-value" }, `${(ENTITY_TYPE_LABELS[entry.entity_type] || [entry.entity_type])[0]} ${entry.entity_id}`)]),
        h("div", { class: "kv" }, [h("span", { class: "kv-label" }, "请求编号"), h("span", { class: "kv-value mono" }, entry.request_id || "—")]),
      ]),
      jsonBlock("变更前", entry.before),
      jsonBlock("变更后", entry.after),
    ]),
    { width: 620 }
  );
}

function openSendLog(log) {
  openDrawer(
    `发送日志 #${log.id}`,
    h("div", { class: "drawer-content" }, [
      h("div", { class: "kv-list" }, [
        h("div", { class: "kv" }, [h("span", { class: "kv-label" }, "时间"), h("span", { class: "kv-value" }, fmtTime(log.created_at))]),
        h("div", { class: "kv" }, [h("span", { class: "kv-label" }, "任务 / 明细"), h("span", { class: "kv-value" }, `#${log.task_id} / #${log.item_id}`)]),
        h("div", { class: "kv" }, [h("span", { class: "kv-label" }, "阶段"), h("span", { class: "kv-value" }, codeChip(log.phase, PHASE_LABELS))]),
        h("div", { class: "kv" }, [h("span", { class: "kv-label" }, "结果"), h("span", { class: "kv-value" }, badge(OUTCOME_LABELS, log.outcome))]),
        h("div", { class: "kv" }, [h("span", { class: "kv-label" }, "原因"), h("span", { class: "kv-value" }, log.reason_code ? codeChip(log.reason_code, REASON_LABELS) : "—")]),
        h("div", { class: "kv" }, [h("span", { class: "kv-label" }, "尝试"), h("span", { class: "kv-value" }, log.attempt_no === null || log.attempt_no === undefined ? "—" : String(log.attempt_no))]),
        h("div", { class: "kv" }, [h("span", { class: "kv-label" }, "渠道消息号"), h("span", { class: "kv-value mono" }, log.provider_message_id || "—")]),
        h("div", { class: "kv" }, [h("span", { class: "kv-label" }, "耗时"), h("span", { class: "kv-value" }, log.latency_ms === null || log.latency_ms === undefined ? "—" : `${log.latency_ms} ms`)]),
        h("div", { class: "kv" }, [h("span", { class: "kv-label" }, "号码（脱敏）"), h("span", { class: "kv-value" }, log.phone_masked || "—")]),
      ]),
      jsonBlock("详情", log.detail),
    ]),
    { width: 560 }
  );
}

function jsonBlock(title, value) {
  return h("section", { class: "drawer-section" }, [
    h("h4", {}, title),
    value
      ? h("pre", { class: "json-block" }, JSON.stringify(value, null, 2))
      : h("p", { class: "muted" }, "没有记录。"),
  ]);
}
