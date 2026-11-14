"use strict";

/* 合规、配置与日志页。 */

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
