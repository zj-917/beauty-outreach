"use strict";

const $ = (id) => document.getElementById(id);
const quiet = () => {};

const ITEM_STATUSES = [
  "PENDING",
  "SENDING",
  "RETRY_WAIT",
  "SENT",
  "DELIVERED",
  "READ",
  "FAILED",
  "SKIPPED",
];

const state = {
  token: "",
  operator: "admin",
  leadPage: 1,
  auditPage: 1,
  sendPage: 1,
  readiness: new Map(),
  currentTask: null,
  pollTimer: null,
  pollTask: null,
  itemStatus: "",
  itemReason: "",
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
  return entries.length ? entries.map(([code, count]) => code + "×" + count).join("，") : "无";
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
    showError("401 UNAUTHORIZED：请在顶部填写正确的 Admin Token 后重试。");
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
    showError(
      detail.code + " · " + detail.message +
        (detail.request_id ? " · request_id=" + detail.request_id : "")
    );
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
  $("auth-state").textContent = state.token ? "token 已从 sessionStorage 载入" : "未填写 token";
}

function saveAuth() {
  state.token = $("token-input").value.trim();
  state.operator = $("operator-input").value.trim() || "admin";
  sessionStorage.setItem("adminToken", state.token);
  sessionStorage.setItem("adminOperator", state.operator);
  $("auth-state").textContent = "已保存到 sessionStorage";
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

/* ---------- overview ---------- */

async function loadOverview() {
  const data = await api("/api/v1/stats/overview");
  const cards = [
    ["线索总数", valuesSum(data.leads_by_status)],
    ["池内线索（APPROVED）", data.pool_size],
    ["任务总数", valuesSum(data.campaigns_by_status)],
    ["近 24h 发送", data.accepted_last_24h],
  ].map(([label, value]) => card(label, value));
  const rows = [
    ...Object.entries(data.leads_by_status).map(([key, value]) => ["线索 " + key, value]),
    ...Object.entries(data.campaigns_by_status).map(([key, value]) => ["任务 " + key, value]),
    ...Object.entries(data.suppressions_by_type).map(([key, value]) => ["suppression " + key, value]),
    ...Object.entries(data.consents_by_status).map(([key, value]) => ["consent " + key, value]),
  ];
  fill($("overview-cards"), ...cards);
  fill($("overview-detail"), make("h3", { text: "分布" }), table(["维度", "计数"], rows));
}

/* ---------- leads ---------- */

function leadRow(lead) {
  const pending = lead.status === "PENDING_REVIEW";
  const check = make("input", {
    type: "checkbox",
    disabled: !pending,
    dataset: { lead: String(lead.id) },
  });
  const note = make("input", { type: "text", placeholder: "备注", size: 8, disabled: !pending });
  const approve = button("通过", () => reviewLead(lead.id, "APPROVE", note.value).catch(quiet));
  const reject = button("拒绝", () => reviewLead(lead.id, "REJECT", note.value).catch(quiet));
  approve.disabled = !pending;
  reject.disabled = !pending;
  const actions = make("div", { class: "row" }, [note, approve, reject]);
  const reasons = (lead.score_reasons || [])
    .map((reason) => reason.code + (reason.delta >= 0 ? "+" : "") + reason.delta)
    .join(" ");
  const readiness = lead.status === "APPROVED" ? state.readiness.get(lead.id) || "—" : "—";
  return [
    check,
    lead.username,
    lead.status,
    lead.score,
    lead.top_keyword,
    reasons,
    lead.phone_masked,
    readiness,
    actions,
  ];
}

async function loadLeads() {
  const params = new URLSearchParams({ page: state.leadPage, page_size: "20" });
  const filters = {
    status: $("lead-status").value,
    min_score: $("lead-min-score").value,
    q: $("lead-q").value.trim(),
  };
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== "") params.set(key, value);
  });
  const data = await api("/api/v1/leads?" + params.toString());
  if (data.items.some((lead) => lead.status === "APPROVED")) {
    const pool = await api("/api/v1/pool?page_size=100");
    state.readiness = new Map(
      pool.items.map((lead) => [lead.id, lead.delivery_readiness])
    );
  }
  fill(
    $("lead-results"),
    data.items.length
      ? table(
          ["选", "用户名", "状态", "分数", "关键词", "命中原因", "号码", "可触达", "审核"],
          data.items.map(leadRow)
        )
      : make("p", { text: "没有符合条件的线索。" })
  );
  $("lead-page-info").textContent = "共 " + data.total + " 条 · 第 " + data.page + " 页";
  $("lead-prev").disabled = data.page <= 1;
  $("lead-next").disabled = data.page * data.page_size >= data.total;
}

async function reviewLead(leadId, decision, note) {
  await api("/api/v1/leads/" + leadId + "/review", {
    method: "POST",
    body: { decision, note: note ? note : null },
  });
  await loadLeads();
}

async function bulkReview(decision) {
  const checked = Array.from(
    document.querySelectorAll("#lead-results input[data-lead]:checked")
  );
  if (!checked.length) {
    showError("请先勾选待确认线索。");
    return;
  }
  const note = $("bulk-note").value.trim() || null;
  const data = await api("/api/v1/leads/review-bulk", {
    method: "POST",
    body: {
      reviews: checked.map((input) => ({
        lead_id: Number(input.dataset.lead),
        decision,
        note,
      })),
    },
  });
  const failed = data.results.filter((item) => !item.ok);
  if (failed.length) {
    showError(
      "批量审核完成，" + failed.length + " 条失败：" +
        failed.map((item) => item.lead_id).join("，")
    );
  }
  await loadLeads();
}

function renderImportReport(batch) {
  const nodes = [
    make("p", { text: "批次 #" + batch.id + " · " + batch.source_name }),
    table(
      ["总数", "导入", "重复", "无效", "警告"],
      [[batch.total_rows, batch.imported, batch.duplicates, batch.invalid, batch.warnings]]
    ),
  ];
  if (batch.errors && batch.errors.length) {
    nodes.push(make("p", { class: "muted", text: "错误列表：" }));
    nodes.push(
      make(
        "ul",
        {},
        batch.errors.map((error) => make("li", { class: "small", text: fmtJson(error, 300) }))
      )
    );
  }
  fill($("import-report"), ...nodes);
}

async function importMock() {
  const batch = await api("/api/v1/lead-batches/import", {
    method: "POST",
    body: { source: "mock" },
  });
  renderImportReport(batch);
  await loadLeads();
}

async function importFile() {
  const file = $("import-file").files[0];
  if (!file) {
    showError("请选择 CSV 或 JSON 文件。");
    return;
  }
  const form = new FormData();
  form.append("file", file);
  const batch = await api("/api/v1/lead-batches/import", { method: "POST", body: form });
  renderImportReport(batch);
  await loadLeads();
}

async function runScreening() {
  const report = await api("/api/v1/leads/screen", { method: "POST", body: {} });
  fill(
    $("import-report"),
    make("p", { text: "筛选完成：" }),
    table(
      ["处理", "自动通过", "待确认", "丢弃", "未变", "警告"],
      [[report.processed, report.approved, report.pending_review, report.discarded, report.unchanged, report.warning || "—"]]
    )
  );
  await loadLeads();
}

/* ---------- tasks ---------- */

async function loadTasks() {
  stopPolling();
  $("task-list-view").classList.remove("hidden");
  $("task-detail-view").classList.add("hidden");
  state.currentTask = null;
  const templates = await api("/api/v1/templates");
  const approved = templates.filter((template) => template.status === "APPROVED");
  fill(
    $("task-template"),
    ...(approved.length
      ? approved.map((template) =>
          make("option", { text: template.name + " v" + template.version, value: String(template.id) })
        )
      : [make("option", { text: "无已审核模板", value: "" })])
  );
  const data = await api("/api/v1/campaigns?page_size=50");
  if (!data.items.length) {
    fill($("task-table"), make("p", { text: "还没有任务。" }));
    return;
  }
  fill(
    $("task-table"),
    table(
      ["ID", "名称", "状态", "总数", "成功", "失败", "跳过", "进行中", ""],
      data.items.map((task) => [
        task.id,
        task.name,
        make("span", { class: "badge " + task.status, text: task.status }),
        task.counts.total,
        task.counts.success,
        task.counts.failed,
        task.counts.skipped,
        task.counts.in_progress,
        button("详情", () => showTaskDetail(task.id).catch(quiet)),
      ])
    )
  );
}

async function createCampaign() {
  const name = $("task-name").value.trim();
  const templateId = Number($("task-template").value);
  if (!name) {
    showError("请填写任务名称。");
    return;
  }
  if (!templateId) {
    showError("没有可用的已审核模板，请先在配置页审核模板。");
    return;
  }
  const selection = {};
  const minScore = $("task-min-score").value;
  if (minScore !== "") selection.min_score = Number(minScore);
  const campaign = await api("/api/v1/campaigns", {
    method: "POST",
    body: { name, template_id: templateId, selection },
  });
  const preview = await api("/api/v1/campaigns/" + campaign.id + "/preview", {
    method: "POST",
  });
  await loadTasks();
  const skips = Object.entries(preview.will_skip);
  fill(
    $("task-preview"),
    make("p", { text: "已创建 DRAFT 任务 #" + campaign.id + "，干跑预览：" }),
    table(
      ["明细总数", "将尝试", "将释放（已不符合条件）"],
      [[preview.total_items, preview.will_attempt, preview.will_release]]
    ),
    make("p", {
      text:
        "将跳过：" +
        (skips.length ? skips.map(([code, count]) => code + "×" + count).join("，") : "无"),
    }),
    make("p", { class: "muted", text: preview.note }),
    button("打开任务详情", () => showTaskDetail(campaign.id).catch(quiet), "primary")
  );
}

async function showTaskDetail(taskId) {
  state.currentTask = taskId;
  $("task-list-view").classList.add("hidden");
  $("task-detail-view").classList.remove("hidden");
  await refreshTaskDetail();
}

function stopPolling() {
  if (state.pollTimer) clearInterval(state.pollTimer);
  state.pollTimer = null;
  state.pollTask = null;
  $("task-poll-note").textContent = "";
}

function startPolling(taskId) {
  if (state.pollTimer && state.pollTask === taskId) return;
  stopPolling();
  state.pollTask = taskId;
  $("task-poll-note").textContent = "运行中：每 2 秒自动刷新";
  state.pollTimer = setInterval(() => {
    refreshTaskDetail().catch(() => stopPolling());
  }, 2000);
}

async function refreshTaskDetail() {
  const taskId = state.currentTask;
  if (!taskId) return;
  const results = await Promise.all([
    api("/api/v1/campaigns/" + taskId),
    api("/api/v1/campaigns/" + taskId + "/stats"),
  ]);
  renderTaskDetail(results[0], results[1]);
  await loadTaskItems();
  if (results[0].status === "RUNNING") startPolling(taskId);
  else stopPolling();
}

function renderTaskDetail(detail, stats) {
  const active = detail.status === "RUNNING";
  const controls = [
    button("启动", () => controlCampaign("start").catch(quiet)),
    button("暂停", () => controlCampaign("pause").catch(quiet)),
    button("恢复", () => controlCampaign("resume").catch(quiet)),
    button("取消", () => controlCampaign("cancel").catch(quiet), "danger"),
  ];
  controls[0].disabled = detail.status !== "DRAFT";
  controls[1].disabled = !active;
  controls[2].disabled = detail.status !== "PAUSED";
  controls[3].disabled = !(detail.status === "DRAFT" || active || detail.status === "PAUSED");
  const cards = [
    ["成功", stats.success],
    ["失败", stats.failed],
    ["跳过", stats.skipped],
    ["进行中", stats.in_progress],
    ["成功率", stats.success_rate === null ? "—" : stats.success_rate],
    ["重试次数", stats.retry_total],
    ["耗时(s)", stats.elapsed_seconds === null ? "—" : stats.elapsed_seconds],
  ].map(([label, value]) => card(label, value));
  const nodes = [
    make("div", { class: "detail-head" }, [
      make("h2", { text: "任务 #" + detail.id + " · " + detail.name }),
      make("span", { class: "badge " + detail.status, text: detail.status }),
    ]),
  ];
  if (detail.pause_reason === "CIRCUIT_OPEN") {
    nodes.push(
      make("div", {
        class: "warning",
        text: "熔断已触发（CIRCUIT_OPEN）：连续失败达到阈值。请排查 Provider 后点“恢复”继续。",
      })
    );
  } else if (detail.pause_reason) {
    nodes.push(make("p", { class: "muted", text: "暂停原因：" + detail.pause_reason }));
  }
  nodes.push(make("div", { class: "row" }, controls));
  nodes.push(make("div", { class: "cards" }, cards));
  nodes.push(make("p", { class: "muted", text: "跳过原因：" + fmtReasons(stats.skip_reasons) }));
  nodes.push(make("p", { class: "muted", text: "失败原因：" + fmtReasons(stats.failure_reasons) }));
  fill($("task-detail"), ...nodes);
}

async function controlCampaign(action) {
  if (action === "cancel" && !window.confirm("确认取消该任务？未发送的明细将标记为 SKIPPED。")) {
    return;
  }
  await api("/api/v1/campaigns/" + state.currentTask + "/" + action, { method: "POST" });
  await refreshTaskDetail();
}

async function loadTaskItems() {
  const taskId = state.currentTask;
  if (!taskId) return;
  const params = new URLSearchParams({ page_size: "100" });
  if (state.itemStatus) params.set("status", state.itemStatus);
  if (state.itemReason) params.set("reason_code", state.itemReason);
  const data = await api("/api/v1/campaigns/" + taskId + "/items?" + params.toString());
  const statusSelect = make("select", {}, [
    make("option", { text: "全部状态", value: "" }),
    ...ITEM_STATUSES.map((status) => make("option", { text: status, value: status })),
  ]);
  statusSelect.value = state.itemStatus;
  statusSelect.addEventListener("change", () => {
    state.itemStatus = statusSelect.value;
    loadTaskItems().catch(quiet);
  });
  const reasonInput = make("input", { type: "text", placeholder: "reason_code", value: state.itemReason });
  reasonInput.addEventListener("change", () => {
    state.itemReason = reasonInput.value.trim();
    loadTaskItems().catch(quiet);
  });
  const rows = data.items.map((item) => [
    item.id,
    item.lead_username,
    item.status,
    item.reason_code,
    item.attempts,
    item.next_attempt_at,
    item.last_error_code,
    item.phone_masked,
    button("日志", () => openSendLogs(taskId, item.id).catch(quiet)),
  ]);
  fill(
    $("task-items"),
    make("div", { class: "row" }, [make("h3", { text: "明细" }), statusSelect, reasonInput]),
    data.items.length
      ? table(["ID", "用户名", "状态", "原因", "尝试", "下次尝试", "最后错误", "号码", "日志"], rows)
      : make("p", { text: "没有明细。" })
  );
}

async function openSendLogs(taskId, itemId) {
  switchPage("logs");
  showLogPanel("send");
  $("send-task").value = String(taskId);
  $("send-item").value = itemId ? String(itemId) : "";
  state.sendPage = 1;
  await loadSendLogs();
}

/* ---------- compliance ---------- */

async function loadCompliance() {
  const results = await Promise.all([api("/api/v1/consents"), api("/api/v1/suppressions")]);
  fill(
    $("consent-table"),
    results[0].length
      ? table(
          ["号码", "状态", "来源", "证据", "更新时间", "更新人"],
          results[0].map((entry) => [
            entry.phone_masked,
            entry.status,
            entry.source,
            entry.evidence_ref,
            entry.updated_at,
            entry.updated_by,
          ])
        )
      : make("p", { text: "暂无授权记录。" })
  );
  const rows = results[1].map((entry) => {
    const cells = [
      entry.type,
      entry.phone_masked,
      entry.username,
      entry.reason,
      entry.source,
      entry.created_at,
    ];
    cells.push(
      entry.type === "BLACKLIST"
        ? button(
            "删除",
            () => {
              if (!window.confirm("确认删除这条黑名单记录？")) return;
              api("/api/v1/suppressions/" + entry.id, { method: "DELETE" })
                .then(loadCompliance)
                .catch(quiet);
            },
            "danger"
          )
        : "不可删除"
    );
    return cells;
  });
  fill(
    $("suppression-table"),
    rows.length
      ? table(["类型", "号码", "用户名", "原因", "来源", "时间", ""], rows)
      : make("p", { text: "暂无黑名单 / 退订记录。" })
  );
  await probeDemoMode();
}

async function addSuppression() {
  const phone = $("suppress-phone").value.trim();
  const reason = $("suppress-reason").value.trim();
  if (!phone || !reason) {
    showError("请填写号码与原因。");
    return;
  }
  await api("/api/v1/suppressions", {
    method: "POST",
    body: { type: "BLACKLIST", phone, reason },
  });
  $("suppress-phone").value = "";
  $("suppress-reason").value = "";
  await loadCompliance();
}

async function probeDemoMode() {
  try {
    const response = await fetch("/demo/inbound-stop", {
      headers: { "X-Admin-Token": state.token || "" },
    });
    $("demo-panel").classList.toggle("hidden", response.status !== 405);
  } catch (error) {
    $("demo-panel").classList.add("hidden");
  }
}

async function demoStop() {
  const phone = $("demo-phone").value.trim();
  if (!phone) {
    showError("请填写号码。");
    return;
  }
  const result = await api("/demo/inbound-stop", { method: "POST", body: { phone } });
  $("demo-result").textContent =
    result.action === "UNSUBSCRIBED"
      ? "已登记退订（UNSUBSCRIBE）；运行中任务的相关明细会在后续处理时被跳过。"
      : "未识别为 STOP，已忽略。";
}

async function demoFlush() {
  const result = await api("/demo/flush-receipts", { method: "POST" });
  $("demo-result").textContent = "已应用回执 " + result.applied + " 条。";
}

async function demoReset() {
  if (!window.confirm("重置演示数据？将清空数据库并重新播种。")) return;
  const result = await api("/demo/reset", { method: "POST" });
  $("demo-result").textContent = "已重置：" + fmtJson(result.counts);
  await loadCompliance();
}

/* ---------- config ---------- */

function configError(error) {
  const detail = error && error.detail;
  const box = $("config-error");
  box.textContent = detail ? detail.code + " · " + detail.message : "操作失败";
  box.classList.add("is-error");
}

async function loadConfig() {
  $("config-error").textContent = "";
  $("config-error").classList.remove("is-error");
  const results = await Promise.all([
    api("/api/v1/keywords"),
    api("/api/v1/rate-rules"),
    api("/api/v1/templates"),
    api("/api/v1/settings"),
  ]);
  renderKeywords(results[0]);
  renderRateRules(results[1]);
  renderTemplates(results[2]);
  renderSettings(results[3]);
}

function renderKeywords(keywords) {
  if (!keywords.length) {
    fill($("keyword-table"), make("p", { text: "暂无关键词。" }));
    return;
  }
  const rows = keywords.map((keyword) => {
    const weight = make("input", { type: "number", value: String(keyword.weight), size: 4 });
    const enabled = make("input", { type: "checkbox", checked: keyword.enabled });
    return [
      keyword.term,
      keyword.kind,
      weight,
      enabled,
      make("div", { class: "row" }, [
        configAction("保存", () =>
          api("/api/v1/keywords/" + keyword.id, { method: "PATCH", body: { weight: Number(weight.value), enabled: enabled.checked } })
        ),
        configConfirm("删除", "确认删除关键词 " + keyword.term + "？", () =>
          api("/api/v1/keywords/" + keyword.id, { method: "DELETE" })
        ),
      ]),
    ];
  });
  fill($("keyword-table"), table(["term", "类型", "权重", "启用", ""], rows));
}

async function addKeyword() {
  const term = $("kw-term").value.trim();
  if (!term) {
    showError("请填写关键词 term。");
    return;
  }
  await api("/api/v1/keywords", {
    method: "POST",
    body: {
      term,
      kind: $("kw-kind").value,
      weight: Number($("kw-weight").value),
      enabled: true,
    },
  });
  $("kw-term").value = "";
  await loadConfig();
}

function renderRateRules(rules) {
  if (!rules.length) {
    fill($("rate-table"), make("p", { text: "暂无频控规则。" }));
    return;
  }
  const rows = rules.map((rule) => [
    rule.name,
    rule.scope,
    rule.window_seconds,
    rule.max_count,
    rule.enabled ? "是" : "否",
    configConfirm("删除", "确认删除规则 " + rule.name + "？", () =>
      api("/api/v1/rate-rules/" + rule.id, { method: "DELETE" })
    ),
  ]);
  fill($("rate-table"), table(["name", "范围", "窗口(s)", "上限", "启用", ""], rows));
}

async function addRateRule() {
  await api("/api/v1/rate-rules", {
    method: "POST",
    body: {
      name: $("rr-name").value.trim(),
      scope: $("rr-scope").value,
      window_seconds: Number($("rr-window").value),
      max_count: Number($("rr-max").value),
      enabled: true,
    },
  });
  await loadConfig();
}

function renderTemplates(templates) {
  if (!templates.length) {
    fill($("template-table"), make("p", { text: "暂无模板。" }));
    return;
  }
  const rows = templates.map((template) => {
    const actions = make("div", { class: "row" });
    if (template.status === "DRAFT") {
      actions.appendChild(
        configAction("审核通过", () => api("/api/v1/templates/" + template.id + "/approve", { method: "POST" }))
      );
    }
    if (template.status === "APPROVED") {
      actions.appendChild(
        configConfirm("停用", "确认停用该模板？", () =>
          api("/api/v1/templates/" + template.id + "/disable", { method: "POST" })
        )
      );
    }
    actions.appendChild(
      button("新版本", () => {
        const body = window.prompt("新版本正文", template.body);
        if (body) configRun(() => api("/api/v1/templates/" + template.id + "/new-version", { method: "POST", body: { body } }));
      })
    );
    actions.appendChild(
      button("预览", () =>
        api("/api/v1/templates/preview", { method: "POST", body: { template_id: template.id } })
          .then((result) => {
            $("template-preview").textContent = result.rendered;
          })
          .catch(configError)
      )
    );
    return [template.name, template.version, template.status, template.language, actions];
  });
  fill($("template-table"), table(["name", "版本", "状态", "语言", ""], rows));
}

async function addTemplate() {
  await api("/api/v1/templates", {
    method: "POST",
    body: {
      name: $("tpl-name").value.trim(),
      language: $("tpl-language").value.trim() || "en",
      body: $("tpl-body").value,
    },
  });
  $("tpl-name").value = "";
  $("tpl-body").value = "";
  await loadConfig();
}

function renderSettings(settings) {
  state.settings = settings;
  fill(
    $("settings-form"),
    ...Object.keys(settings)
      .sort()
      .map((key) => {
        const value = settings[key];
        let input;
        if (typeof value === "boolean") {
          input = make("input", { type: "checkbox", checked: value });
        } else if (typeof value === "number") {
          input = make("input", { type: "number", value: String(value) });
        } else {
          input = make("input", {
            type: "text",
            value: value === null || value === undefined ? "" : String(value),
            size: 30,
          });
        }
        input.id = "setting-" + key;
        return make("div", { class: "row" }, [make("label", { class: "muted", text: key }), input]);
      })
  );
}

async function saveSettings() {
  const payload = {};
  Object.keys(state.settings).forEach((key) => {
    const input = $("setting-" + key);
    if (!input) return;
    let value;
    if (input.type === "checkbox") value = input.checked;
    else if (input.type === "number") value = Number(input.value);
    else value = input.value;
    if (JSON.stringify(value) !== JSON.stringify(state.settings[key])) payload[key] = value;
  });
  if (!Object.keys(payload).length) {
    $("config-error").classList.remove("is-error");
    $("config-error").textContent = "没有修改。";
    return;
  }
  try {
    const updated = await api("/api/v1/settings", { method: "PUT", body: payload });
    renderSettings(updated);
    $("config-error").classList.remove("is-error");
    $("config-error").textContent = "已保存。";
  } catch (error) {
    configError(error);
  }
}

/* ---------- logs ---------- */

function showLogPanel(which) {
  $("logs-audit").classList.toggle("hidden", which !== "audit");
  $("logs-send").classList.toggle("hidden", which !== "send");
  $("logs-audit-btn").classList.toggle("active", which === "audit");
  $("logs-send-btn").classList.toggle("active", which === "send");
}

async function loadLogs() {
  showLogPanel("audit");
  await loadAuditLogs();
}

async function loadAuditLogs() {
  const params = new URLSearchParams({ page: state.auditPage, page_size: "20" });
  const filters = [
    ["actor", $("audit-actor").value.trim()],
    ["action", $("audit-action").value.trim()],
    ["entity_type", $("audit-entity-type").value.trim()],
    ["entity_id", $("audit-entity-id").value.trim()],
  ];
  filters.forEach(([key, value]) => {
    if (value) params.set(key, value);
  });
  const data = await api("/api/v1/audit-logs?" + params.toString());
  fill(
    $("audit-table"),
    data.items.length
      ? table(
          ["时间", "actor", "action", "实体", "变更前", "变更后", "request_id"],
          data.items.map((entry) => [
            entry.ts,
            entry.actor,
            entry.action,
            entry.entity_type + ":" + entry.entity_id,
            fmtJson(entry.before),
            fmtJson(entry.after),
            entry.request_id,
          ])
        )
      : make("p", { text: "没有符合条件的审计记录。" })
  );
  $("audit-page-info").textContent = "共 " + data.total + " 条 · 第 " + data.page + " 页";
  $("audit-prev").disabled = data.page <= 1;
  $("audit-next").disabled = data.page * data.page_size >= data.total;
}

async function loadSendLogs() {
  const params = new URLSearchParams({ page: state.sendPage, page_size: "20" });
  const filters = [
    ["task_id", $("send-task").value],
    ["item_id", $("send-item").value],
    ["phase", $("send-phase").value],
    ["outcome", $("send-outcome").value],
    ["reason_code", $("send-reason").value.trim()],
  ];
  filters.forEach(([key, value]) => {
    if (value) params.set(key, value);
  });
  const data = await api("/api/v1/send-logs?" + params.toString());
  fill(
    $("send-table"),
    data.items.length
      ? table(
          ["时间", "phase", "outcome", "原因", "尝试", "延迟(ms)", "号码", "provider_message_id", "detail"],
          data.items.map((entry) => [
            entry.created_at,
            entry.phase,
            entry.outcome,
            entry.reason_code,
            entry.attempt_no,
            entry.latency_ms,
            entry.phone_masked,
            entry.provider_message_id,
            fmtJson(entry.detail),
          ])
        )
      : make("p", { text: "没有符合条件的发送日志。" })
  );
  $("send-page-info").textContent = "共 " + data.total + " 条 · 第 " + data.page + " 页";
  $("send-prev").disabled = data.page <= 1;
  $("send-next").disabled = data.page * data.page_size >= data.total;
}

/* ---------- wiring ---------- */

function bindEvents() {
  $("save-auth").addEventListener("click", saveAuth);
  $("error-close").addEventListener("click", hideError);
  document.querySelectorAll("#tabs button").forEach((item) =>
    item.addEventListener("click", () => switchPage(item.dataset.page))
  );
  const actions = {
    "overview-refresh": loadOverview,
    "import-mock": importMock,
    "import-file-btn": importFile,
    "run-screening": runScreening,
    "bulk-approve": () => bulkReview("APPROVE"),
    "bulk-reject": () => bulkReview("REJECT"),
    "task-create": createCampaign,
    "task-refresh": loadTasks,
    "task-back": loadTasks,
    "task-detail-refresh": refreshTaskDetail,
    "consent-refresh": loadCompliance,
    "suppress-add": addSuppression,
    "demo-stop": demoStop,
    "demo-flush": demoFlush,
    "demo-reset": demoReset,
    "kw-add": () => addKeyword().catch(configError),
    "rr-add": () => addRateRule().catch(configError),
    "tpl-create": () => addTemplate().catch(configError),
    "settings-save": () => saveSettings().catch(configError),
    "logs-audit-btn": () => {
      showLogPanel("audit");
      return loadAuditLogs();
    },
    "logs-send-btn": () => {
      showLogPanel("send");
      return loadSendLogs();
    },
    "audit-search": () => {
      state.auditPage = 1;
      return loadAuditLogs();
    },
    "audit-prev": () => {
      state.auditPage = Math.max(1, state.auditPage - 1);
      return loadAuditLogs();
    },
    "audit-next": () => {
      state.auditPage += 1;
      return loadAuditLogs();
    },
    "send-search": () => {
      state.sendPage = 1;
      return loadSendLogs();
    },
    "send-prev": () => {
      state.sendPage = Math.max(1, state.sendPage - 1);
      return loadSendLogs();
    },
    "send-next": () => {
      state.sendPage += 1;
      return loadSendLogs();
    },
  };
  Object.entries(actions).forEach(([id, action]) => bind(id, action));
  bind("lead-search", () => {
    state.leadPage = 1;
    return loadLeads();
  });
  bind("lead-prev", () => {
    state.leadPage = Math.max(1, state.leadPage - 1);
    return loadLeads();
  });
  bind("lead-next", () => {
    state.leadPage += 1;
    return loadLeads();
  });
}

function init() {
  loadAuth();
  bindEvents();
  switchPage("overview");
}

document.addEventListener("DOMContentLoaded", init);
