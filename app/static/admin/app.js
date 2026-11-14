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

const LEAD_STATUS_LABELS = {
  NEW: ["新导入", "刚导入，还没有评分"],
  PENDING_REVIEW: ["待人工确认", "分数处在中间区间，需要人工决定是否入池"],
  APPROVED: ["已入池", "可以进入发送任务"],
  REJECTED: ["已拒绝", "人工决定不联系"],
  DISCARDED: ["已丢弃", "分数过低，不会联系"],
};

const READINESS_LABELS = {
  READY: ["可发送", "满足号码、授权和黑名单等全部条件"],
  BLACKLISTED: ["黑名单", "号码在运营黑名单中，禁止发送"],
  UNSUBSCRIBED: ["已退订", "用户回复过退订，永久不再联系"],
  NO_PHONE: ["无号码", "线索没有可用手机号"],
  NO_CONSENT: ["无授权", "没有用户同意接收的记录"],
  CONSENT_REVOKED: ["授权已撤销", "用户撤回了接收授权"],
};

const TASK_STATUS_LABELS = {
  DRAFT: ["草稿", "任务已创建，还没有开始发送"],
  RUNNING: ["运行中", "系统正在逐条检查并发送"],
  PAUSED: ["已暂停", "暂时停止处理，可以恢复"],
  COMPLETED: ["已完成", "所有线索都有了最终结果"],
  CANCELLED: ["已取消", "任务已终止，未发送的线索被跳过"],
};

const TASK_STATUS_GUIDE = {
  DRAFT: ["当前状态：草稿——还没有发送任何消息。", "下一步：点「启动」开始发送；如果不想发送，点「取消」。"],
  RUNNING: ["当前状态：运行中——系统正在逐条检查并发送，通常 20–30 秒完成。", "下一步：等待自动刷新；如需临时停止，点「暂停」。"],
  PAUSED: ["当前状态：已暂停——不会继续发送。", "下一步：点「恢复」继续；如果不再发送，点「取消」。"],
  COMPLETED: ["当前状态：已完成——全部线索都有了结果。", "下一步：在下方查看明细，或点某条明细的「日志」查看过程。"],
  CANCELLED: ["当前状态：已取消——任务已终止。", "下一步：返回任务列表新建一个任务，或到日志页查看记录。"],
};

const ITEM_STATUS_LABELS = {
  PENDING: ["待发送", "等待系统处理"],
  SENDING: ["发送中", "正在调用发送渠道"],
  RETRY_WAIT: ["等待重试", "上次失败，稍后自动重试"],
  SENT: ["已发送", "已交给渠道，等待送达回执"],
  DELIVERED: ["已送达", "对方设备已收到"],
  READ: ["已读", "对方已打开消息"],
  FAILED: ["失败", "最终失败，不再重试"],
  SKIPPED: ["已跳过", "按合规或去重规则未发送"],
};

const REASON_LABELS = {
  BLACKLISTED: ["黑名单", "号码在运营黑名单中，禁止发送"],
  UNSUBSCRIBED: ["已退订", "用户回复过退订，永久不再联系"],
  NO_PHONE: ["无号码", "线索没有可用手机号"],
  INVALID_PHONE: ["号码无效", "号码格式不正确，无法发送"],
  NO_CONSENT: ["无授权", "没有用户同意接收的记录"],
  CONSENT_REVOKED: ["授权已撤销", "用户撤回了接收授权"],
  TEMPLATE_NOT_APPROVED: ["模板未审核", "任务使用的消息模板没有通过审核"],
  TEMPLATE_VARIABLE_MISSING: ["模板缺少变量", "模板需要的变量在这条线索里不存在"],
  RENDER_TOO_LONG: ["消息超长", "渲染后的消息超过平台长度限制"],
  ALREADY_CONTACTED: ["已联系过", "同一号码已用相同模板发送过，避免重复打扰"],
  RECIPIENT_RATE_LIMITED: ["收件人频率超限", "这个号码在频控窗口内已收到足够多的消息"],
  TASK_CANCELLED: ["任务已取消", "任务被取消，这条不再发送"],
  MAX_ATTEMPTS_EXCEEDED: ["重试次数用尽", "多次尝试仍然失败，停止重试"],
  INVALID_NUMBER: ["号码无效", "发送渠道判定号码不存在或不可用"],
  NOT_WHATSAPP_USER: ["未注册渠道", "该号码没有注册当前发送渠道"],
  TEMPLATE_REJECTED: ["模板被拒绝", "发送渠道拒绝了这条消息模板"],
  AUTH_ERROR: ["凭证错误", "发送渠道凭证无效，系统已自动暂停任务"],
  DELIVERY_FAILED: ["送达失败", "渠道受理后报告发送失败"],
  RATE_LIMIT_GLOBAL: ["全局频率限制", "整体发送速度达到上限，稍后自动继续"],
  QUIET_HOURS: ["静默时段", "当前处于不打扰时段，稍后自动继续"],
  TIMEOUT: ["调用超时", "发送渠道没有及时响应"],
  NETWORK_ERROR: ["网络错误", "连接发送渠道时出错"],
  SERVER_ERROR: ["渠道服务异常", "发送渠道返回服务器错误"],
  RATE_LIMITED: ["渠道限流", "发送渠道要求稍后再发"],
};

const SCORE_REASON_LABELS = {
  KW_POS: ["正向关键词", "资料命中了正向词，加分"],
  KW_NEG: ["负向关键词", "资料命中了负向词，减分"],
  REGION_MATCH: ["地区符合", "地区在优先名单内，加分"],
  REGION_MISMATCH: ["地区不符", "地区不在优先名单内，减分"],
  LANG_MATCH: ["语言符合", "语言在优先名单内，加分"],
  LANG_MISMATCH: ["语言不符", "语言不在优先名单内，减分"],
  BIO_TOO_SHORT: ["简介过短", "资料太少，信息不足，减分"],
  CLAMP: ["分数截断", "总分超出 0 到 100，被截断到边界"],
};

const TEMPLATE_STATUS_LABELS = {
  DRAFT: ["草稿", "还不能用于任务，需要先审核通过"],
  APPROVED: ["已审核", "可以用于创建发送任务"],
  DISABLED: ["已停用", "不再用于新任务"],
};

const SUPPRESSION_TYPE_LABELS = {
  BLACKLIST: ["黑名单", "运营手动加入，可以删除"],
  UNSUBSCRIBE: ["退订", "用户主动回复，永久有效且不可删除"],
};

const CONSENT_STATUS_LABELS = {
  GRANTED: ["已授权", "用户同意接收消息"],
  REVOKED: ["已撤销", "用户撤回了接收授权"],
};

const SOURCE_LABELS = {
  web_form: ["网页表单", "用户在网页表单中主动留资并授权"],
  crm_import: ["CRM 导入", "从企业自有 CRM 数据导入"],
  csv_import: ["文件导入", "通过 CSV 或 JSON 文件导入"],
  mock: ["示例数据", "系统内置的演示数据"],
  seed: ["默认种子", "系统初始化时写入的数据"],
  IMPORT: ["文件导入", "通过 CSV 或 JSON 文件导入"],
  MANUAL: ["人工登记", "运营在管理页手动添加"],
  manual: ["人工登记", "运营在管理页手动添加"],
  INBOUND_STOP: ["用户退订", "用户回复退订指令后产生"],
  inbound_stop: ["用户退订", "用户回复退订指令后产生"],
};

const KEYWORD_KIND_LABELS = {
  POSITIVE: ["正向加分", "命中后提高线索分数"],
  NEGATIVE: ["负向减分", "命中后降低线索分数"],
};

const RATE_SCOPE_LABELS = {
  GLOBAL: ["全局", "限制整个系统的发送速度"],
  PER_RECIPIENT: ["单收件人", "限制同一号码的接收频率"],
};

const PHASE_LABELS = {
  GATE: ["发送前检查", "检查这条线索是否允许发送"],
  PROVIDER: ["调用发送渠道", "真正把消息交给发送渠道"],
  RECEIPT: ["送达回执", "渠道回报送达、已读或失败"],
};

const OUTCOME_LABELS = {
  BLOCKED: ["被拦截", "检查不通过，没有发送"],
  DEFERRED: ["推迟处理", "暂时不满足时间条件，稍后再处理"],
  ACCEPTED: ["已受理", "发送渠道接受了消息"],
  RETRYABLE_ERROR: ["可重试错误", "暂时失败，系统会再试"],
  PERMANENT_ERROR: ["永久错误", "无法修复的失败，不再重试"],
  DELIVERED: ["已送达", "对方设备已收到"],
  READ: ["已读", "对方已打开消息"],
  DELIVERY_FAILED: ["送达失败", "渠道报告发送失败"],
};

const ENTITY_TYPE_LABELS = {
  lead: ["线索", "导入的候选客户"],
  lead_batch: ["导入批次", "一次导入操作产生的批次"],
  campaign: ["发送任务", "一次批量触达任务"],
  keyword: ["关键词", "用于线索评分的词"],
  rate_rule: ["频控规则", "限制发送速度的规则"],
  template: ["消息模板", "发送消息使用的模板"],
  contact_consent: ["授权记录", "用户是否同意接收的记录"],
  suppression: ["黑名单与退订记录", "禁止联系的号码记录"],
  system_setting: ["系统设置", "运行参数"],
};

const AUDIT_ACTION_LABELS = {
  LEAD_BATCH_IMPORTED: ["导入线索", "把一批候选线索写入系统"],
  LEAD_SCREENING_RUN: ["运行筛选", "对线索自动打分并分档"],
  LEAD_REVIEWED: ["人工审核线索", "人工通过或拒绝线索"],
  KEYWORD_CREATED: ["新增关键词", "添加评分关键词"],
  KEYWORD_UPDATED: ["修改关键词", "调整关键词权重或启用状态"],
  KEYWORD_DELETED: ["删除关键词", "移除评分关键词"],
  SETTING_UPDATED: ["修改系统设置", "调整运行参数"],
  RATE_RULE_CREATED: ["新增频控规则", "添加发送速度限制"],
  RATE_RULE_UPDATED: ["修改频控规则", "调整发送速度限制"],
  RATE_RULE_DELETED: ["删除频控规则", "移除发送速度限制"],
  TEMPLATE_CREATED: ["新建模板", "创建一条消息模板草稿"],
  TEMPLATE_UPDATED: ["修改模板草稿", "编辑尚未审核的模板"],
  TEMPLATE_VERSIONED: ["创建模板新版本", "基于已审核模板创建新草稿"],
  TEMPLATE_APPROVED: ["审核通过模板", "模板可以用于发送任务"],
  TEMPLATE_DISABLED: ["停用模板", "模板不再用于新任务"],
  CONSENT_UPSERTED: ["登记授权", "记录用户是否同意接收"],
  SUPPRESSION_ADDED: ["加入名单", "加入黑名单或退订名单"],
  SUPPRESSION_REMOVED: ["移除名单", "移除黑名单记录"],
  INBOUND_STOP_PROCESSED: ["处理用户退订", "用户回复退订后立即生效"],
  CAMPAIGN_CREATED: ["创建任务", "生成一次发送任务"],
  CAMPAIGN_STARTED: ["启动任务", "开始逐条发送"],
  CAMPAIGN_PAUSED: ["暂停任务", "临时停止发送"],
  CAMPAIGN_RESUMED: ["恢复任务", "继续发送"],
  CAMPAIGN_CANCELLED: ["取消任务", "终止任务并跳过未发送线索"],
  CAMPAIGN_COMPLETED: ["任务完成", "所有线索都有了最终结果"],
  CAMPAIGN_CIRCUIT_OPENED: ["自动熔断暂停", "连续失败达到阈值，系统自动暂停任务"],
};

const SETTING_LABELS = {
  "screening.auto_approve_enabled": ["自动入池开关", "开启后，高分线索自动进入目标池"],
  "screening.threshold_high": ["自动入池分数线", "分数达到该值即自动入池"],
  "screening.threshold_low": ["人工确认下限", "低于该值直接丢弃，介于两档之间需人工确认"],
  "screening.allowed_regions": ["优先地区", "地区在此列表内加分"],
  "screening.allowed_languages": ["优先语言", "语言在此列表内加分"],
  "screening.region_bonus": ["地区加分值", "地区符合时增加的分数"],
  "screening.region_penalty": ["地区减分值", "地区不符时扣除的分数"],
  "screening.language_bonus": ["语言加分值", "语言符合时增加的分数"],
  "screening.language_penalty": ["语言减分值", "语言不符时扣除的分数"],
  "screening.short_bio_min_len": ["简介过短判定长度", "简介短于该长度视为信息不足"],
  "screening.short_bio_penalty": ["简介过短减分", "简介过短时扣除的分数"],
  "sending.max_attempts": ["最大尝试次数", "单条消息最多尝试发送几次"],
  "sending.backoff_base_seconds": ["重试基础等待（秒）", "第一次重试前等待的时间"],
  "sending.backoff_cap_seconds": ["重试最长等待（秒）", "重试等待时间不会超过该值"],
  "sending.backoff_jitter": ["重试随机抖动", "给重试等待加入随机量，避免同时重试"],
  "sending.claim_batch_size": ["每批处理条数", "系统每次最多取多少条明细处理"],
  "sending.lease_seconds": ["处理租约（秒）", "一条明细被占用的最长时间，超时会被回收"],
  "sending.provider_timeout_seconds": ["渠道调用超时（秒）", "等待发送渠道响应的最长时间"],
  "sending.circuit_breaker_threshold": ["连续失败熔断阈值", "连续失败达到该次数时自动暂停任务"],
  "sending.quiet_hours_enabled": ["静默时段开关", "开启后在指定时段内不发送"],
  "sending.quiet_hours_start": ["静默开始时间", "静默时段从几点开始，格式 HH:MM"],
  "sending.quiet_hours_end": ["静默结束时间", "静默时段到几点结束，格式 HH:MM"],
  "sending.quiet_hours_tz": ["静默时段时区", "计算静默时段使用的时区"],
  "message.brand": ["品牌名", "消息模板里使用的品牌名称"],
  "message.optout_text": ["退订提示文案", "自动追加到每条消息末尾的退订说明"],
  "compliance.stop_keywords": ["退订关键词", "用户回复这些词时视为退订"],
};

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

const ERROR_HINTS = {
  UNAUTHORIZED: "身份验证未通过：请在页面顶部「访问口令」中填入正确口令，然后重试。",
  VALIDATION_ERROR: "填写的内容不符合要求，请检查后重试。",
  NOT_FOUND: "找不到对应的数据，可能已被删除或编号有误。",
  CONFLICT: "这条数据已经存在，或与当前状态冲突。",
  INTERNAL_ERROR: "服务器内部错误，请稍后重试。",
  CFG_LAST_RATE_RULE: "系统至少需要保留一条全局规则和一条单收件人规则。",
  TEMPLATE_NOT_APPROVED: "模板还没有审核通过，不能用于任务。",
  TEMPLATE_IMMUTABLE: "已审核的模板正文不能直接修改，请创建新版本。",
  CAMPAIGN_EMPTY_TARGET: "没有符合条件的线索，任务没有创建。",
  COMP_UNSUBSCRIBE_IMMUTABLE: "退订记录永久有效，不能删除。",
  PROVIDER_NOT_ENABLED: "当前发送渠道未启用，无法发送。",
};

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

/* ---------- overview ---------- */

async function loadOverview() {
  const data = await api("/api/v1/stats/overview");
  const cards = [
    ["线索总数", valuesSum(data.leads_by_status)],
    ["已入池线索（可发送）", data.pool_size],
    ["任务总数", valuesSum(data.campaigns_by_status)],
    ["近 24 小时已受理发送", data.accepted_last_24h],
  ].map(([label, value]) => card(label, value));
  const rows = [
    ...Object.entries(data.leads_by_status).map(([key, value]) => [
      "线索 · " + zhName(LEAD_STATUS_LABELS, key),
      value,
    ]),
    ...Object.entries(data.campaigns_by_status).map(([key, value]) => [
      "任务 · " + zhName(TASK_STATUS_LABELS, key),
      value,
    ]),
    ...Object.entries(data.suppressions_by_type).map(([key, value]) => [
      "黑名单与退订 · " + zhName(SUPPRESSION_TYPE_LABELS, key),
      value,
    ]),
    ...Object.entries(data.consents_by_status).map(([key, value]) => [
      "授权 · " + zhName(CONSENT_STATUS_LABELS, key),
      value,
    ]),
  ];
  fill($("overview-cards"), ...cards);
  fill(
    $("overview-detail"),
    make("h3", { text: "按状态的分布" }),
    make("p", {
      class: "muted",
      text: "计数实时计算；状态的含义可把鼠标移到明细表或本表的状态名上查看。",
    }),
    table(["维度", "数量"], rows)
  );
}

/* ---------- leads ---------- */

function leadRow(lead) {
  const pending = lead.status === "PENDING_REVIEW";
  const check = make("input", {
    type: "checkbox",
    disabled: !pending,
    title: pending ? "勾选后可批量审核" : "只有待人工确认的线索可以审核",
    dataset: { lead: String(lead.id) },
  });
  const note = make("input", {
    type: "text",
    placeholder: "备注（可选）",
    size: 8,
    disabled: !pending,
    title: "备注会写入操作记录",
  });
  const approve = button("通过", () => reviewLead(lead.id, "APPROVE", note.value).catch(quiet));
  const reject = button("拒绝", () => reviewLead(lead.id, "REJECT", note.value).catch(quiet));
  approve.disabled = !pending;
  reject.disabled = !pending;
  approve.title = "通过后加入目标池，可进入发送任务";
  reject.title = "拒绝后不会联系这条线索";
  const actions = make("div", { class: "row" }, [note, approve, reject]);
  const reasonNodes = (lead.score_reasons || []).map((reason) =>
    make("span", {
      class: "reason-chip",
      text:
        zhName(SCORE_REASON_LABELS, reason.code) +
        " " + (reason.delta >= 0 ? "+" : "") + reason.delta,
      title: reason.code + "：" + (reason.detail || ""),
    })
  );
  const reasons = reasonNodes.length ? make("div", { class: "reason-list" }, reasonNodes) : "无";
  let readiness = "—";
  if (lead.status === "APPROVED") {
    const value = state.readiness.get(lead.id);
    readiness = value ? labelNode(READINESS_LABELS, value) : "—";
  }
  return [
    check,
    lead.username,
    labelNode(LEAD_STATUS_LABELS, lead.status),
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
          ["选择", "用户名", "状态", "分数", "主要关键词", "命中原因", "号码", "可发送性", "审核操作"],
          data.items.map(leadRow)
        )
      : make("p", {
          text: "没有符合条件的线索。可以清空筛选后重试，或先导入示例线索。",
        })
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
  setGuideText(
    "leads-next",
    "审核已保存，人工决定不会被自动评分覆盖。下一步：到左侧「任务」创建发送任务。"
  );
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
  setGuideText(
    "leads-next",
    "批量审核已保存。下一步：到左侧「任务」创建发送任务。"
  );
}

function renderImportReport(batch) {
  const nodes = [
    make("p", { text: "导入批次 #" + batch.id + " · 来源：" + batch.source_name }),
    table(
      ["总行数", "导入成功", "重复", "无效", "警告"],
      [[batch.total_rows, batch.imported, batch.duplicates, batch.invalid, batch.warnings]]
    ),
    make("p", {
      class: "muted",
      text:
        "总行数 = 文件里的行数；导入成功 = 新增的线索；重复 = 已经存在的线索；" +
        "无效 = 格式错误被忽略；警告 = 需要留意但不影响导入。",
    }),
  ];
  if (batch.errors && batch.errors.length) {
    nodes.push(make("p", { class: "muted", text: "错误明细（逐行说明）：" }));
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
  setGuideText(
    "leads-next",
    "导入完成。下一步：点击「自动筛选」，系统会给线索打分并分档。"
  );
}

async function importFile() {
  const file = $("import-file").files[0];
  if (!file) {
    showError("请先选择一个 CSV 或 JSON 文件，再点「上传并导入」。");
    return;
  }
  const form = new FormData();
  form.append("file", file);
  const batch = await api("/api/v1/lead-batches/import", { method: "POST", body: form });
  renderImportReport(batch);
  await loadLeads();
  setGuideText(
    "leads-next",
    "导入完成。下一步：点击「自动筛选」，系统会给线索打分并分档。"
  );
}

async function runScreening() {
  const report = await api("/api/v1/leads/screen", { method: "POST", body: {} });
  fill(
    $("import-report"),
    make("p", { text: "筛选完成：" }),
    table(
      ["处理", "自动通过", "待确认", "丢弃", "未变", "警告"],
      [[report.processed, report.approved, report.pending_review, report.discarded, report.unchanged, report.warning || "—"]]
    ),
    make("p", {
      class: "muted",
      text:
        "自动通过 = 分数达到自动入池线，直接进入目标池；待确认 = 分数介于两档之间，需要人工决定；" +
        "丢弃 = 分数过低，不联系；未变 = 重新评分后状态没有变化。",
    })
  );
  await loadLeads();
  setGuideText(
    "leads-next",
    "筛选完成。下一步：把「状态」选为「待人工确认」并点「查询」，逐条审核。"
  );
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
    fill(
      $("task-table"),
      make("p", { text: "还没有任务。先在上方填写信息并创建，预览确认后再启动。" })
    );
    return;
  }
  fill(
    $("task-table"),
    table(
      ["编号", "名称", "状态", "线索总数", "成功", "失败", "跳过", "处理中", "操作"],
      data.items.map((task) => [
        task.id,
        task.name,
        make("span", {
          class: "badge " + task.status,
          text: zhName(TASK_STATUS_LABELS, task.status),
          title: zhFull(TASK_STATUS_LABELS, task.status) + "：" + TASK_STATUS_LABELS[task.status][1],
        }),
        task.counts.total,
        task.counts.success,
        task.counts.failed,
        task.counts.skipped,
        task.counts.in_progress,
        button("查看详情", () => showTaskDetail(task.id).catch(quiet)),
      ])
    )
  );
}

async function createCampaign() {
  const name = $("task-name").value.trim();
  const templateId = Number($("task-template").value);
  if (!name) {
    showError("请先填写任务名称。");
    return;
  }
  if (!templateId) {
    showError("当前没有已审核的模板。请先到左侧「配置」新建模板并点「审核通过」。");
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
    make("p", { text: "已创建任务 #" + campaign.id + "（草稿）。下面是预览结果：" }),
    make("p", {
      class: "muted",
      text: "预览只检查发送条件，不会真的发送；真正启动时还会再检查一次。",
    }),
    table(
      ["线索总数", "符合条件将发送", "已不符合条件（会跳过）"],
      [[preview.total_items, preview.will_attempt, preview.will_release]]
    ),
    make("p", {
      text:
        "将跳过的线索及原因：" +
        (skips.length
          ? skips.map(([code, count]) => zhName(REASON_LABELS, code) + "×" + count).join("，")
          : "无"),
    }),
    make("p", {
      class: "muted",
      text: "预览不模拟发送频率延迟和静默时段；这些只会在真正发送时生效。",
    }),
    button(
      "打开任务详情，确认并启动",
      () => showTaskDetail(campaign.id).catch(quiet),
      "primary"
    )
  );
  setGuideText(
    "tasks-next",
    "任务已创建（草稿）。下一步：点「打开任务详情」，确认后点「启动」。"
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

const PAUSE_REASON_LABELS = {
  MANUAL: ["手动暂停", "由操作人手动暂停"],
  CIRCUIT_OPEN: ["自动熔断", "连续失败达到阈值，系统自动暂停"],
};

function renderTaskStatusNote(detail) {
  const guide = TASK_STATUS_GUIDE[detail.status] || ["", ""];
  const allowed = {
    DRAFT: "可用操作：启动、取消。",
    RUNNING: "可用操作：暂停、取消。",
    PAUSED: "可用操作：恢复、取消。",
    COMPLETED: "可用操作：无（任务已结束），可以查看明细与日志。",
    CANCELLED: "可用操作：无（任务已终止），可以返回列表新建任务。",
  }[detail.status] || "";
  const nodes = [
    make("p", { class: "state-note-title", text: guide[0] }),
    make("p", { class: "state-note-next", text: guide[1] }),
    make("p", { class: "muted", text: allowed }),
  ];
  if (detail.pause_reason === "CIRCUIT_OPEN") {
    nodes.push(
      make("div", {
        class: "warning",
        text:
          "连续发送失败达到阈值，系统已自动暂停任务，避免继续出错。" +
          "请先检查发送渠道，再点「恢复」继续。",
      })
    );
  } else if (detail.pause_reason) {
    nodes.push(
      make("p", {
        class: "muted",
        text: "暂停原因：" + zhFull(PAUSE_REASON_LABELS, detail.pause_reason),
      })
    );
  }
  return make("div", { class: "state-note" }, nodes);
}

function renderTaskDetail(detail, stats) {
  const active = detail.status === "RUNNING";
  const controls = [
    button("启动", () => controlCampaign("start").catch(quiet)),
    button("暂停", () => controlCampaign("pause").catch(quiet)),
    button("恢复", () => controlCampaign("resume").catch(quiet)),
    button("取消", () => controlCampaign("cancel").catch(quiet), "danger"),
  ];
  controls[0].title = "开始发送；只有草稿任务可以启动";
  controls[1].title = "临时停止发送，之后可以恢复；只有运行中的任务可以暂停";
  controls[2].title = "继续发送；只有已暂停的任务可以恢复";
  controls[3].title = "终止任务，尚未发送的线索会被跳过";
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
    ["耗时（秒）", stats.elapsed_seconds === null ? "—" : stats.elapsed_seconds],
  ].map(([label, value]) => card(label, value));
  const nodes = [
    make("div", { class: "detail-head" }, [
      make("h2", { text: "任务 #" + detail.id + " · " + detail.name }),
      make("span", {
        class: "badge " + detail.status,
        text: zhName(TASK_STATUS_LABELS, detail.status),
        title: zhFull(TASK_STATUS_LABELS, detail.status) + "：" + TASK_STATUS_LABELS[detail.status][1],
      }),
    ]),
  ];
  nodes.push(renderTaskStatusNote(detail));
  nodes.push(make("div", { class: "row" }, controls));
  nodes.push(make("div", { class: "cards" }, cards));
  nodes.push(
    make("p", {
      class: "muted",
      text: "成功 = 已发送、已送达或已读；成功率 = 成功 ÷（成功 + 失败）；重试次数 = 额外重试的总次数。",
    })
  );
  nodes.push(make("p", { class: "muted", text: "跳过原因：" + fmtReasons(stats.skip_reasons) }));
  nodes.push(make("p", { class: "muted", text: "失败原因：" + fmtReasons(stats.failure_reasons) }));
  fill($("task-detail"), ...nodes);
}

async function controlCampaign(action) {
  if (action === "cancel" && !window.confirm("确认取消该任务？尚未发送的线索会被跳过。")) {
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
    ...ITEM_STATUSES.map((status) => optionNode(ITEM_STATUS_LABELS, status)),
  ]);
  statusSelect.title = "按明细状态筛选";
  statusSelect.value = state.itemStatus;
  statusSelect.addEventListener("change", () => {
    state.itemStatus = statusSelect.value;
    loadTaskItems().catch(quiet);
  });
  const reasonInput = make("input", {
    type: "text",
    placeholder: "原因代码，如 UNSUBSCRIBED",
    value: state.itemReason,
    title: "可填中文名对应的代码，如 UNSUBSCRIBED、NO_PHONE",
  });
  reasonInput.addEventListener("change", () => {
    state.itemReason = reasonInput.value.trim();
    loadTaskItems().catch(quiet);
  });
  const rows = data.items.map((item) => [
    item.id,
    item.lead_username,
    labelNode(ITEM_STATUS_LABELS, item.status),
    item.reason_code ? labelNode(REASON_LABELS, item.reason_code) : "—",
    item.attempts,
    item.next_attempt_at,
    item.last_error_code ? labelNode(REASON_LABELS, item.last_error_code) : "—",
    item.phone_masked,
    button("日志", () => openSendLogs(taskId, item.id).catch(quiet)),
  ]);
  rows.forEach((row) => {
    row[row.length - 1].title = "查看这条线索的发送过程";
  });
  fill(
    $("task-items"),
    make("div", { class: "row" }, [
      make("h3", { text: "明细（每条线索的处理结果）" }),
      statusSelect,
      reasonInput,
    ]),
    data.items.length
      ? table(
          ["编号", "用户名", "状态", "原因", "尝试次数", "下次尝试", "最后错误", "号码", "操作"],
          rows
        )
      : make("p", {
          text: "没有符合条件的明细。可以清空状态或原因筛选后重试。",
        })
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
          ["号码", "授权状态", "来源", "凭据", "更新时间", "更新人"],
          results[0].map((entry) => [
            entry.phone_masked,
            labelNode(CONSENT_STATUS_LABELS, entry.status),
            labelNode(SOURCE_LABELS, entry.source),
            entry.evidence_ref,
            entry.updated_at,
            entry.updated_by,
          ])
        )
      : make("p", { text: "暂无授权记录。导入示例线索后会带少量授权数据。" })
  );
  const rows = results[1].map((entry) => {
    const cells = [
      labelNode(SUPPRESSION_TYPE_LABELS, entry.type),
      entry.phone_masked,
      entry.username,
      entry.reason,
      labelNode(SOURCE_LABELS, entry.source),
      entry.created_at,
    ];
    cells.push(
      entry.type === "BLACKLIST"
        ? button(
            "删除",
            () => {
              if (!window.confirm("确认删除这条黑名单记录？退订记录不能删除。")) return;
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
      ? table(["类型", "号码", "用户名", "原因", "来源", "时间", "操作"], rows)
      : make("p", {
          text: "暂无黑名单或退订记录。可以在上方手动加入，或在演示区模拟用户退订。",
        })
  );
  await probeDemoMode();
}

async function addSuppression() {
  const phone = $("suppress-phone").value.trim();
  const reason = $("suppress-reason").value.trim();
  if (!phone || !reason) {
    showError("请填写号码和原因。");
    return;
  }
  await api("/api/v1/suppressions", {
    method: "POST",
    body: { type: "BLACKLIST", phone, reason },
  });
  $("suppress-phone").value = "";
  $("suppress-reason").value = "";
  await loadCompliance();
  setGuideText("compliance-next", "已加入黑名单。该号码在后续任务中会被跳过。");
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
    showError("请先填写要模拟退订的号码。");
    return;
  }
  const result = await api("/demo/inbound-stop", { method: "POST", body: { phone } });
  if (result.action === "UNSUBSCRIBED") {
    $("demo-result").textContent =
      "已登记退订（UNSUBSCRIBE）；运行中任务的相关明细会在后续处理时被跳过。";
    setGuideText(
      "compliance-next",
      "已登记退订。下一步：回到任务详情点「恢复」，观察这条线索被跳过。"
    );
  } else {
    $("demo-result").textContent = "没有识别为退订指令，已忽略。";
  }
}

async function demoFlush() {
  const result = await api("/demo/flush-receipts", { method: "POST" });
  $("demo-result").textContent = "已生成送达回执 " + result.applied + " 条，任务统计会自动更新。";
}

async function demoReset() {
  if (!window.confirm("重置演示数据？将清空当前数据并恢复初始演示数据。")) return;
  const result = await api("/demo/reset", { method: "POST" });
  $("demo-result").textContent = "已重置：" + fmtJson(result.counts);
  setGuideText("compliance-next", "演示数据已恢复初始状态。请从左侧「线索」重新开始。");
  await loadCompliance();
}

/* ---------- config ---------- */

function configError(error) {
  const detail = error && error.detail;
  const box = $("config-error");
  box.textContent = detail ? errorText(detail) : "操作失败，请稍后重试。";
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
    fill(
      $("keyword-table"),
      make("p", { text: "暂无关键词。可以新增一个，或重置演示数据恢复默认配置。" })
    );
    return;
  }
  const rows = keywords.map((keyword) => {
    const weight = make("input", {
      type: "number",
      value: String(keyword.weight),
      size: 4,
      title: "权重 1 到 50，越大影响越强",
    });
    const enabled = make("input", {
      type: "checkbox",
      checked: keyword.enabled,
      title: "取消勾选后这个词不参与评分",
    });
    return [
      keyword.term,
      labelNode(KEYWORD_KIND_LABELS, keyword.kind),
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
  fill($("keyword-table"), table(["关键词", "类型", "权重", "启用", "操作"], rows));
}

async function addKeyword() {
  const term = $("kw-term").value.trim();
  if (!term) {
    showError("请先填写关键词。");
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
  setGuideText("config-next", "关键词已新增，下一次筛选时生效。");
}

function renderRateRules(rules) {
  if (!rules.length) {
    fill(
      $("rate-table"),
      make("p", { text: "暂无频控规则。系统要求至少保留一条全局规则和一条单收件人规则。" })
    );
    return;
  }
  const rows = rules.map((rule) => [
    rule.name,
    labelNode(RATE_SCOPE_LABELS, rule.scope),
    rule.window_seconds,
    rule.max_count,
    rule.enabled ? "是" : "否",
    configConfirm("删除", "确认删除规则 " + rule.name + "？系统至少需要保留一条全局规则和一条单收件人规则。", () =>
      api("/api/v1/rate-rules/" + rule.id, { method: "DELETE" })
    ),
  ]);
  fill($("rate-table"), table(["名称", "范围", "窗口（秒）", "上限（次）", "启用", "操作"], rows));
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
  setGuideText("config-next", "频控规则已新增，下一条被处理的明细即按新值执行。");
}

function renderTemplates(templates) {
  if (!templates.length) {
    fill(
      $("template-table"),
      make("p", { text: "暂无模板。新建后会先进入草稿，审核通过后才能用于任务。" })
    );
    return;
  }
  const rows = templates.map((template) => {
    const actions = make("div", { class: "row" });
    if (template.status === "DRAFT") {
      const approve = configAction("审核通过", () =>
        api("/api/v1/templates/" + template.id + "/approve", { method: "POST" })
      );
      approve.title = "审核通过后，这个模板才能用于发送任务";
      actions.appendChild(approve);
    }
    if (template.status === "APPROVED") {
      actions.appendChild(
        configConfirm("停用", "确认停用该模板？停用后不能用于新任务。", () =>
          api("/api/v1/templates/" + template.id + "/disable", { method: "POST" })
        )
      );
    }
    const version = button("创建新版本", () => {
      const body = window.prompt("新版本正文（已审核模板的正文不能直接修改）", template.body);
      if (body) {
        configRun(() =>
          api("/api/v1/templates/" + template.id + "/new-version", {
            method: "POST",
            body: { body },
          })
        );
      }
    });
    version.title = "基于当前模板创建一个新的草稿版本，需要重新审核";
    actions.appendChild(version);
    const preview = button("预览", () =>
      api("/api/v1/templates/preview", { method: "POST", body: { template_id: template.id } })
        .then((result) => {
          $("template-preview").textContent = "渲染效果：\n" + result.rendered;
        })
        .catch(configError)
    );
    preview.title = "用内置示例线索渲染这条模板，查看实际消息";
    actions.appendChild(preview);
    return [
      template.name,
      template.version,
      labelNode(TEMPLATE_STATUS_LABELS, template.status),
      template.language,
      actions,
    ];
  });
  fill($("template-table"), table(["名称", "版本", "状态", "语言", "操作"], rows));
}

async function addTemplate() {
  const name = $("tpl-name").value.trim();
  const body = $("tpl-body").value;
  if (!name || !body.trim()) {
    showError("请填写模板名称和正文。");
    return;
  }
  await api("/api/v1/templates", {
    method: "POST",
    body: {
      name,
      language: $("tpl-language").value.trim() || "en",
      body,
    },
  });
  $("tpl-name").value = "";
  $("tpl-body").value = "";
  await loadConfig();
  setGuideText("config-next", "模板已创建（草稿）。下一步：点行内「审核通过」，之后才能用于任务。");
}

function renderSettings(settings) {
  state.settings = settings;
  fill(
    $("settings-form"),
    ...Object.keys(settings)
      .sort()
      .map((key) => {
        const entry = dictEntry(SETTING_LABELS, key);
        const name = entry ? entry[0] : key;
        const description = entry ? entry[1] : "运行参数";
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
        input.title = description;
        return make("div", { class: "row setting-item" }, [
          make("label", { class: "muted", text: name, title: description }),
          input,
          make("span", {
            class: "setting-desc muted",
            text: description + "（字段名 " + key + "）",
          }),
        ]);
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
    $("config-error").textContent = "没有修改。改完再点「保存设置」。";
    return;
  }
  try {
    const updated = await api("/api/v1/settings", { method: "PUT", body: payload });
    renderSettings(updated);
    $("config-error").classList.remove("is-error");
    $("config-error").textContent = "设置已保存，立即生效。";
    setGuideText("config-next", "设置已保存，立即生效。");
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
          ["时间", "操作人", "动作", "对象", "变更前", "变更后", "请求编号"],
          data.items.map((entry) => [
            entry.ts,
            entry.actor,
            labelNode(AUDIT_ACTION_LABELS, entry.action),
            make("span", {
              text: zhName(ENTITY_TYPE_LABELS, entry.entity_type) + " #" + entry.entity_id,
              title: entry.entity_type + ":" + entry.entity_id,
            }),
            fmtJson(entry.before),
            fmtJson(entry.after),
            entry.request_id,
          ])
        )
      : make("p", { text: "没有符合条件的操作记录。可以清空筛选后重试。" })
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
          ["时间", "阶段", "结果", "原因", "尝试次数", "延迟（毫秒）", "号码", "渠道消息编号", "详情"],
          data.items.map((entry) => [
            entry.created_at,
            labelNode(PHASE_LABELS, entry.phase),
            labelNode(OUTCOME_LABELS, entry.outcome),
            entry.reason_code ? labelNode(REASON_LABELS, entry.reason_code) : "—",
            entry.attempt_no,
            entry.latency_ms,
            entry.phone_masked,
            entry.provider_message_id,
            fmtJson(entry.detail),
          ])
        )
      : make("p", {
          text: "没有符合条件的发送记录。可以先在任务详情里点击某条明细的「日志」。",
        })
  );
  $("send-page-info").textContent = "共 " + data.total + " 条 · 第 " + data.page + " 页";
  $("send-prev").disabled = data.page <= 1;
  $("send-next").disabled = data.page * data.page_size >= data.total;
}

/* ---------- wiring ---------- */

function populateChoices(id, dict, allLabel) {
  const select = $(id);
  if (!select) return;
  const previous = select.value;
  clear(select);
  if (allLabel) select.appendChild(make("option", { text: allLabel, value: "" }));
  Object.keys(dict).forEach((code) => select.appendChild(optionNode(dict, code)));
  if (previous && Object.prototype.hasOwnProperty.call(dict, previous)) {
    select.value = previous;
  } else if (!allLabel) {
    select.value = Object.keys(dict)[0] || "";
  }
}

function populateFilterChoices() {
  populateChoices("lead-status", LEAD_STATUS_LABELS, "全部");
  populateChoices("send-phase", PHASE_LABELS, "全部");
  populateChoices("send-outcome", OUTCOME_LABELS, "全部");
  populateChoices("kw-kind", KEYWORD_KIND_LABELS, null);
  populateChoices("rr-scope", RATE_SCOPE_LABELS, null);
}

function bindEvents() {
  $("save-auth").addEventListener("click", saveAuth);
  $("error-close").addEventListener("click", hideError);
  $("go-leads").addEventListener("click", () => switchPage("leads"));
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
  populateFilterChoices();
  loadAuth();
  bindEvents();
  switchPage("overview");
}

document.addEventListener("DOMContentLoaded", init);
