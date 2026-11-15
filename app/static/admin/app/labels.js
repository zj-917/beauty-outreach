/* 全站中文文案与释义。新增枚举时必须同时补中文名与一句话释义。 */

export const LEAD_STATUS_LABELS = {
  NEW: ["新导入", "刚导入，还没有评分"],
  PENDING_REVIEW: ["待人工确认", "分数处在中间区间，需要人工决定是否入池"],
  APPROVED: ["已入池", "可以进入发送任务"],
  REJECTED: ["已拒绝", "人工决定不联系"],
  DISCARDED: ["已丢弃", "分数过低，不会联系"],
};

export const READINESS_LABELS = {
  READY: ["可发送", "满足号码、授权和黑名单等全部条件"],
  BLACKLISTED: ["黑名单", "号码在运营黑名单中，禁止发送"],
  UNSUBSCRIBED: ["已退订", "用户回复过退订，永久不再联系"],
  NO_PHONE: ["无号码", "线索没有可用手机号"],
  NO_CONSENT: ["无授权", "没有用户同意接收的记录"],
  CONSENT_REVOKED: ["授权已撤销", "用户撤回了接收授权"],
};

export const TASK_STATUS_LABELS = {
  DRAFT: ["草稿", "任务已创建，还没有开始发送"],
  RUNNING: ["运行中", "系统正在逐条检查并发送"],
  PAUSED: ["已暂停", "暂时停止处理，可以恢复"],
  COMPLETED: ["已完成", "所有线索都有了最终结果"],
  CANCELLED: ["已取消", "任务已终止，未发送的线索被跳过"],
};

export const ITEM_STATUS_LABELS = {
  PENDING: ["待发送", "等待系统处理"],
  SENDING: ["发送中", "正在调用发送渠道"],
  RETRY_WAIT: ["等待重试", "上次失败，稍后自动重试"],
  SENT: ["已发送", "已交给渠道，等待送达回执"],
  DELIVERED: ["已送达", "对方设备已收到"],
  READ: ["已读", "对方已打开消息"],
  FAILED: ["失败", "最终失败，不再重试"],
  SKIPPED: ["已跳过", "按合规或去重规则未发送"],
};

export const REASON_LABELS = {
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

export const SCORE_REASON_LABELS = {
  KW_POS: ["正向关键词", "资料命中了正向词，加分"],
  KW_NEG: ["负向关键词", "命中了负向词，减分"],
  REGION_MATCH: ["地区符合", "地区在优先名单内，加分"],
  REGION_MISMATCH: ["地区不符", "地区不在优先名单内，减分"],
  LANG_MATCH: ["语言符合", "语言在优先名单内，加分"],
  LANG_MISMATCH: ["语言不符", "语言不在优先名单内，减分"],
  BIO_TOO_SHORT: ["简介过短", "资料太少，信息不足，减分"],
  CLAMP: ["分数截断", "总分超出 0–100，被截断到边界"],
};

export const TEMPLATE_STATUS_LABELS = {
  DRAFT: ["草稿", "还不能用于任务，需要先审核通过"],
  APPROVED: ["已审核", "可以用于创建发送任务"],
  DISABLED: ["已停用", "不再用于新任务"],
};

export const SUPPRESSION_TYPE_LABELS = {
  BLACKLIST: ["黑名单", "运营手动加入，可以删除"],
  UNSUBSCRIBE: ["退订", "用户主动回复，永久有效且不可删除"],
};

export const CONSENT_STATUS_LABELS = {
  GRANTED: ["已授权", "用户同意接收消息"],
  REVOKED: ["已撤销", "用户撤回了接收授权"],
};

export const SOURCE_LABELS = {
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

export const KEYWORD_KIND_LABELS = {
  POSITIVE: ["正向加分", "命中后提高线索分数"],
  NEGATIVE: ["负向减分", "命中后降低线索分数"],
};

export const RATE_SCOPE_LABELS = {
  GLOBAL: ["全局", "限制整个系统的发送速度"],
  PER_RECIPIENT: ["单收件人", "限制同一号码的接收频率"],
};

export const PHASE_LABELS = {
  GATE: ["发送前检查", "检查这条线索是否允许发送"],
  PROVIDER: ["调用发送渠道", "真正把消息交给发送渠道"],
  RECEIPT: ["送达回执", "渠道回报送达、已读或失败"],
};

export const OUTCOME_LABELS = {
  BLOCKED: ["被拦截", "检查不通过，没有发送"],
  DEFERRED: ["推迟处理", "暂时不满足时间条件，稍后再处理"],
  ACCEPTED: ["已受理", "发送渠道接受了消息"],
  RETRYABLE_ERROR: ["可重试错误", "暂时失败，系统会再试"],
  PERMANENT_ERROR: ["永久错误", "无法修复的失败，不再重试"],
  DELIVERED: ["已送达", "对方设备已收到"],
  READ: ["已读", "对方已打开消息"],
  DELIVERY_FAILED: ["送达失败", "渠道报告发送失败"],
};

export const ENTITY_TYPE_LABELS = {
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

export const AUDIT_ACTION_LABELS = {
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

export const SETTING_LABELS = {
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

export const BATCH_ERROR_LABELS = {
  DUPLICATE_USERNAME: ["重复用户名", "这个用户名已经导入过，本次跳过"],
  IMPORT_CONFLICT: ["号码归属冲突", "这个手机号已经属于另一条线索，不能复制"],
  DUPLICATE_PHONE: ["重复号码", "这个手机号已被其他线索使用"],
  MISSING_USERNAME: ["缺少用户名", "这一行没有用户名，无法导入"],
  INVALID_USERNAME: ["用户名无效", "用户名只能包含字母、数字、点和下划线（1–30 位）"],
  INVALID_SOURCE_URL: ["来源链接无效", "来源必须是合规的 instagram.com 链接"],
  INVALID_REGION: ["地区无效", "地区不是两位国家 / 地区代码，已忽略该字段"],
  INVALID_LANGUAGE: ["语言无效", "语言标签格式不正确，已忽略该字段"],
  INVALID_PHONE_DROPPED: ["号码无效已丢弃", "号码不是标准的国家码格式，这条线索没有号码"],
  CONSENT_INCOMPLETE: ["授权信息不完整", "登记授权需要有效号码、授权状态、来源与凭据"],
};

export const PAUSE_REASON_LABELS = {
  MANUAL: ["手动暂停", "由操作人手动暂停"],
  CIRCUIT_OPEN: ["自动熔断", "连续失败达到阈值，系统自动暂停"],
};

export const TASK_EVENT_LABELS = {
  CREATED: ["创建任务", "生成一次发送任务"],
  STARTED: ["启动任务", "开始逐条发送"],
  PAUSED: ["暂停任务", "临时停止发送"],
  RESUMED: ["恢复任务", "继续发送"],
  CANCELLED: ["取消任务", "终止任务并跳过未发送线索"],
  COMPLETED: ["任务完成", "所有线索都有了最终结果"],
  CIRCUIT_OPENED: ["自动熔断", "连续失败达到阈值，系统自动暂停任务"],
};

export const TASK_STATUS_GUIDE = {
  DRAFT: ["当前状态：草稿——还没有发送任何消息。", "下一步：点「启动」开始发送；如果不想发送，点「取消」。"],
  RUNNING: ["当前状态：运行中——系统正在逐条检查并发送。", "下一步：等待自动刷新；如需临时停止，点「暂停」。"],
  PAUSED: ["当前状态：已暂停——不会继续发送。", "下一步：点「恢复」继续；不再发送就点「取消」。"],
  COMPLETED: ["当前状态：已完成——全部线索都有了结果。", "下一步：在下方查看明细，或点某条明细的「日志」查看过程。"],
  CANCELLED: ["当前状态：已取消——任务已终止。", "下一步：返回任务列表新建任务，或到记录页查看日志。"],
};

export const TASK_ACTIONS = {
  DRAFT: [["启动", "start"], ["取消", "cancel"]],
  RUNNING: [["暂停", "pause"], ["取消", "cancel"]],
  PAUSED: [["恢复", "resume"], ["取消", "cancel"]],
  COMPLETED: [],
  CANCELLED: [],
};

export const ACTION_DISABLED_REASON = {
  start: "只有草稿任务可以启动。",
  pause: "只有运行中的任务可以暂停。",
  resume: "只有已暂停的任务可以恢复。",
  cancel: "已完成或已取消的任务不能再取消。",
};

export const TONE = {
  NEW: "muted", PENDING_REVIEW: "warn", APPROVED: "ok", REJECTED: "danger", DISCARDED: "muted",
  READY: "ok", BLACKLISTED: "danger", UNSUBSCRIBED: "danger", NO_PHONE: "muted",
  NO_CONSENT: "muted", CONSENT_REVOKED: "danger",
  DRAFT: "muted", RUNNING: "info", PAUSED: "warn", COMPLETED: "ok", CANCELLED: "danger",
  PENDING: "muted", SENDING: "info", RETRY_WAIT: "warn", SENT: "info", DELIVERED: "ok",
  READ: "ok", FAILED: "danger", SKIPPED: "muted",
  GRANTED: "ok", REVOKED: "danger", BLACKLIST: "danger", UNSUBSCRIBE: "danger",
  POSITIVE: "ok", NEGATIVE: "danger", GLOBAL: "info", PER_RECIPIENT: "info",
  BLOCKED: "danger", DEFERRED: "warn", ACCEPTED: "ok",
  RETRYABLE_ERROR: "warn", PERMANENT_ERROR: "danger", DELIVERY_FAILED: "danger",
};

export const SETTING_GROUPS = [
  { prefix: "screening.", label: "筛选与评分", desc: "决定线索如何打分、自动入池或进入人工确认。" },
  { prefix: "sending.", label: "发送与重试", desc: "决定发送速度、重试节奏、熔断与静默时段。" },
  { prefix: "message.", label: "消息内容", desc: "模板里可用的品牌名与自动退订提示。" },
  { prefix: "compliance.", label: "合规关键词", desc: "用户回复哪些词会被视为退订。" },
];

export const TEMPLATE_VARIABLES = [
  { code: "name", label: "显示名", desc: "线索的显示名；没有显示名时使用用户名。" },
  { code: "username", label: "用户名", desc: "线索的 Instagram 用户名。" },
  { code: "keyword", label: "命中关键词", desc: "这条线索得分最高的关键词。" },
  { code: "brand", label: "品牌名", desc: "来自系统设置里的品牌名。" },
  { code: "optout_text", label: "退订提示", desc: "自动追加到消息末尾的退订说明。" },
];

export const ERROR_HINTS = {
  UNAUTHORIZED: "身份验证未通过：请在顶部重新填写访问口令。",
  VALIDATION_ERROR: "填写的内容不符合要求，请检查后重试。",
  NOT_FOUND: "找不到对应的数据，可能已被删除或编号有误。",
  CONFLICT: "这条数据已经存在，或与当前状态冲突。",
  INTERNAL_ERROR: "服务器内部错误，请稍后重试。",
  CAMPAIGN_EMPTY_TARGET: "当前筛选条件下没有可发送的线索，请调整最低分或批次。",
  TEMPLATE_NOT_APPROVED: "所选模板还没有审核通过，不能用于发送任务。",
  CAMPAIGN_INVALID_STATE: "任务当前状态不允许这个操作，请刷新后重试。",
  PROVIDER_NOT_ENABLED: "真实发送渠道未启用；本演示只使用 Mock 沙箱。",
  TEMPLATE_IMMUTABLE: "已审核或已停用的模板不能直接修改，请创建新版本。",
  RATE_RULE_REQUIRED: "必须保留至少一条启用的全局规则和一条启用的单收件人规则。",
  BATCH_FILE_UNSUPPORTED: "文件格式不支持，请上传 CSV 或 JSON。",
};

export const DEMO_STEPS = [
  { key: "import", title: "导入示例线索", desc: "把 52 行演示数据写入系统，生成导入报告。", route: "#/leads" },
  { key: "screen", title: "自动筛选", desc: "按关键词与资料给 44 条线索打分并分档。", route: "#/leads" },
  { key: "review", title: "审核 1 条", desc: "在「待人工确认」里通过一条，观察它进入目标池。", route: "#/leads" },
  { key: "create", title: "创建任务", desc: "选择已审核模板与最低分，创建一份草稿。", route: "#/tasks?new=1" },
  { key: "preview", title: "查看预览", desc: "干跑检查会发送多少、会跳过多少，不会真的发送。", route: "#/tasks" },
  { key: "start", title: "启动任务", desc: "让系统逐条检查并发送，观察进度与实时动态。", route: "#/tasks" },
  { key: "stop", title: "模拟退订", desc: "模拟用户回复 STOP，验证退订即时生效。", route: "#/compliance" },
  { key: "finish", title: "查看统计与日志", desc: "看最终漏斗、失败原因与审计记录。", route: "#/records" },
];
