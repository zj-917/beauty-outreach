"use strict";

/* 线索页：导入与筛选（批次卡片 + 人工审核）与用户池两个子页签。 */

const BATCH_TAB_PRIORITY = ["duplicates", "invalid", "warnings"];

const BATCH_TAB_LABELS = {
  imported: ["✅ 成功", "新增入库的线索"],
  duplicates: ["🔁 重复", "已存在或手机号冲突的行"],
  invalid: ["⚠️ 无效", "格式错误、被拒绝的行"],
  warnings: ["❕警告", "已保留但需要留意的行"],
};

const BATCH_ERROR_CATEGORIES = {
  duplicates: ["DUPLICATE_USERNAME", "IMPORT_CONFLICT", "DUPLICATE_PHONE"],
  invalid: ["MISSING_USERNAME", "INVALID_USERNAME", "INVALID_SOURCE_URL"],
  warnings: ["INVALID_REGION", "INVALID_LANGUAGE", "INVALID_PHONE_DROPPED", "CONSENT_INCOMPLETE"],
};

/* ---------- 子页签切换 ---------- */

function switchLeadsTab(tab) {
  $("leads-tab-import").classList.toggle("active", tab === "import");
  $("leads-tab-pool").classList.toggle("active", tab === "pool");
  $("leads-import-view").classList.toggle("hidden", tab !== "import");
  $("leads-pool-view").classList.toggle("hidden", tab !== "pool");
  if (tab === "import") loadLeads().catch(quiet);
  else loadPoolView().catch(quiet);
}

/* ---------- 人工审核（待人工确认） ---------- */

function leadRow(lead) {
  const check = make("input", {
    type: "checkbox",
    title: "勾选后可批量审核",
    dataset: { lead: String(lead.id) },
  });
  const note = make("input", {
    type: "text",
    placeholder: "备注（可选）",
    size: 8,
    title: "备注会写入操作记录",
  });
  const approve = button("通过", () => reviewLead(lead.id, "APPROVE", note.value).catch(quiet));
  const reject = button("拒绝", () => reviewLead(lead.id, "REJECT", note.value).catch(quiet));
  approve.title = "通过后加入目标池，可进入发送任务";
  reject.title = "拒绝后不会联系这条线索";
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
  const detail = make("div", { class: "expand-detail" }, [
    make("p", { text: "简介：" + (lead.bio || "—") }),
    make("p", { text: "号码：" + (lead.phone_masked || "—") }),
    make("p", { text: "主要关键词：" + (lead.top_keyword || "—") }),
  ]);
  const cells = [
    check,
    lead.username,
    lead.display_name || "—",
    make("span", { text: String(lead.score), title: "分数处在中间区间，需要人工决定是否入池" }),
    reasons,
    make("div", { class: "row" }, [note, approve, reject]),
  ];
  return expandableRow(cells, detail);
}

async function loadLeads() {
  await Promise.all([loadReviewList(), loadBatchHistory()]);
}

async function loadReviewList() {
  const params = new URLSearchParams({
    page: state.leadPage,
    page_size: "20",
    status: "PENDING_REVIEW",
  });
  if ($("lead-min-score").value !== "") params.set("min_score", $("lead-min-score").value);
  if ($("lead-q").value.trim() !== "") params.set("q", $("lead-q").value.trim());
  const data = await api("/api/v1/leads?" + params.toString());
  fill(
    $("lead-results"),
    data.items.length
      ? table(
          ["选择", "用户名", "显示名", "分数", "命中原因", "审核操作"],
          data.items.map(leadRow)
        )
      : make("p", {
          text: "没有待人工确认的线索。导入并自动筛选后，中间分数段的线索会出现在这里。",
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

/* ---------- 批次结果卡片 ---------- */

function batchErrorsByCategory(batch) {
  const grouped = { duplicates: [], invalid: [], warnings: [] };
  (batch.errors || []).forEach((error) => {
    for (const category of BATCH_TAB_PRIORITY) {
      if (BATCH_ERROR_CATEGORIES[category].includes(error.code)) {
        grouped[category].push(error);
        return;
      }
    }
  });
  return grouped;
}

function pickBatchTab(batch) {
  const grouped = batchErrorsByCategory(batch);
  const counts = {
    imported: batch.imported,
    duplicates: batch.duplicates,
    invalid: batch.invalid,
    warnings: batch.warnings,
  };
  for (const category of BATCH_TAB_PRIORITY) {
    if (counts[category] > 0) return { tab: category, grouped, counts };
  }
  return { tab: "imported", grouped, counts };
}

function batchTabContent(batch, tab, grouped) {
  if (tab === "imported") {
    return make("div", { class: "batch-tab-body" }, [
      make("p", {
        class: "muted",
        text: "本批次新增入库的线索（通过「用户池 / 线索」可查看完整资料）：",
      }),
      make("div", { class: "batch-imported", dataset: { batch: String(batch.id) } }, [
        make("p", { class: "muted", text: "加载中…" }),
      ]),
    ]);
  }
  const rows = grouped[tab].map((error) => [
    "第 " + error.row + " 行",
    labelNode(BATCH_ERROR_LABELS, error.code),
    error.detail,
  ]);
  return make("div", { class: "batch-tab-body" }, [
    rows.length
      ? table(["行号", "原因", "说明"], rows)
      : make("p", { class: "muted", text: "本批次没有这一类别的行。" }),
  ]);
}

async function fillBatchImportedRows(container, batchId) {
  const data = await api("/api/v1/leads?batch_id=" + batchId + "&page_size=20");
  clear(container);
  container.appendChild(
    data.items.length
      ? table(
          ["用户名", "显示名", "状态", "地区"],
          data.items.map((lead) => [
            lead.username,
            lead.display_name || "—",
            labelNode(LEAD_STATUS_LABELS, lead.status),
            lead.region || "—",
          ])
        )
      : make("p", { class: "muted", text: "没有查到本批次新增的线索。" })
  );
}

function renderBatchCard(batch) {
  const { tab: defaultTab, grouped, counts } = pickBatchTab(batch);
  const tabBar = make("div", { class: "tabbar" });
  const body = make("div", { class: "batch-tab-body" });
  const cardEl = make("div", { class: "batch-card" });

  function activate(tab) {
    tabBar.querySelectorAll("button").forEach((item) => {
      item.classList.toggle("active", item.dataset.tab === tab);
    });
    fill(body, batchTabContent(batch, tab, grouped));
    if (tab === "imported") {
      fillBatchImportedRows(body.querySelector(".batch-imported"), batch.id).catch(quiet);
    }
  }

  Object.keys(BATCH_TAB_LABELS).forEach((key) => {
    const label = BATCH_TAB_LABELS[key][0];
    const hint = BATCH_TAB_LABELS[key][1];
    const tabButton = button(
      label + " (" + (counts[key] || 0) + ")",
      () => activate(key)
    );
    tabButton.dataset.tab = key;
    tabButton.title = hint;
    tabBar.appendChild(tabButton);
  });

  const toggle = button("收起", () => {
    const hidden = body.classList.toggle("hidden");
    toggle.textContent = hidden ? "展开" : "收起";
  });
  toggle.title = "收起后仍保留计数摘要";

  cardEl.appendChild(
    make("div", { class: "batch-card-head" }, [
      make("div", {}, [
        make("strong", { text: "导入批次 #" + batch.id }),
        make("span", {
          class: "muted",
          text: " · 来源 " + batch.source_name + " · " + (batch.created_at || ""),
        }),
        make("span", {
          class: "muted batch-counts",
          text:
            "　总 " + batch.total_rows + " · 成功 " + batch.imported +
            " · 重复 " + batch.duplicates + " · 无效 " + batch.invalid +
            " · 警告 " + batch.warnings,
        }),
      ]),
      toggle,
    ])
  );
  cardEl.appendChild(tabBar);
  cardEl.appendChild(body);
  cardEl.appendChild(
    make("p", {
      class: "muted",
      text:
        "成功 = 新增入库；重复 = 已存在或手机号冲突；无效 = 格式错误被忽略；" +
        "警告 = 需要留意但不影响导入。",
    })
  );
  activate(defaultTab);
  return cardEl;
}

function renderImportReport(batch) {
  fill($("import-report"), renderBatchCard(batch));
}

async function loadBatchHistory() {
  const data = await api("/api/v1/lead-batches?page_size=10");
  fill(
    $("batch-history"),
    data.items.length
      ? make("div", {}, [
          make("h3", { text: "批次历史" }),
          table(
            ["批次", "来源", "时间", "总行数", "成功", "重复", "无效", "警告", "操作"],
            data.items.map((batch) => [
              "#" + batch.id,
              batch.source_name,
              batch.created_at || "—",
              batch.total_rows,
              batch.imported,
              batch.duplicates,
              batch.invalid,
              batch.warnings,
              button("展开结果", () => {
                renderImportReport(batch);
                $("import-report").scrollIntoView({ behavior: "smooth", block: "nearest" });
              }),
            ])
          ),
        ])
      : make("p", { class: "muted", text: "还没有导入记录。" })
  );
}

async function importMock() {
  const batch = await api("/api/v1/lead-batches/import", {
    method: "POST",
    body: { source: "mock" },
  });
  renderImportReport(batch);
  await loadBatchHistory();
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
  await loadBatchHistory();
  setGuideText(
    "leads-next",
    "导入完成。下一步：点击「自动筛选」，系统会给线索打分并分档。"
  );
}

/* ---------- 自动筛选：三卡片 ---------- */

function screeningCard(label, value, hint) {
  return make("div", { class: "card" }, [
    make("div", { class: "label", text: label }),
    make("div", { class: "value", text: String(value) }),
    make("div", { class: "muted", text: hint }),
  ]);
}

async function runScreening() {
  const report = await api("/api/v1/leads/screen", { method: "POST", body: {} });
  fill(
    $("screening-cards"),
    screeningCard("自动入池", report.approved, "分数达到自动入池线，直接进入目标池"),
    screeningCard("待人工确认", report.pending_review, "分数介于两档之间，在下方人工决定"),
    screeningCard("已丢弃", report.discarded, "分数过低，不会联系")
  );
  fill(
    $("screening-summary"),
    make("p", {
      class: "muted",
      text:
        "本次处理 " + report.processed + " 条 · 状态未变 " + report.unchanged +
        " 条" + (report.warning ? " · 警告：" + report.warning : ""),
    })
  );
  await loadReviewList();
  setGuideText(
    "leads-next",
    "筛选完成。下一步：在「待人工确认」计数下方逐条审核；已入池名单可到「用户池」子页签查看。"
  );
}

/* ---------- 用户池子页签 ---------- */

function poolRow(lead) {
  const status = labelNode(LEAD_STATUS_LABELS, lead.status);
  let readiness = "—";
  const ready = lead.delivery_readiness || state.readiness.get(lead.id);
  if (lead.status === "APPROVED" && ready) readiness = labelNode(READINESS_LABELS, ready);
  const reasonNodes = (lead.score_reasons || []).map((reason) =>
    make("span", {
      class: "reason-chip",
      text:
        zhName(SCORE_REASON_LABELS, reason.code) +
        " " + (reason.delta >= 0 ? "+" : "") + reason.delta,
      title: reason.code + "：" + (reason.detail || ""),
    })
  );
  const detail = make("div", { class: "expand-detail" }, [
    make("p", { text: "简介：" + (lead.bio || "—") }),
    make("p", { text: "号码：" + (lead.phone_masked || "—") }),
    make("p", { text: "主要关键词：" + (lead.top_keyword || "—") }),
    make("p", {}, [
      "可发送性：",
      readiness,
      "　命中原因：",
      reasonNodes.length ? make("span", { class: "reason-list" }, reasonNodes) : "无",
    ]),
  ]);
  return expandableRow(
    [
      lead.username,
      lead.display_name || "—",
      status,
      lead.score === null ? "—" : lead.score,
      lead.region || "—",
    ],
    detail
  );
}

async function loadPoolView() {
  const results = await Promise.all([
    api("/api/v1/pool?page_size=100"),
    api("/api/v1/stats/overview"),
  ]);
  const poolPageData = results[0];
  const overview = results[1];
  state.readiness = new Map(
    poolPageData.items.map((lead) => [lead.id, lead.delivery_readiness])
  );

  const readiness = poolPageData.readiness_counts || {};
  fill(
    $("pool-kpi"),
    card("池内用户总数（已入池）", poolPageData.total),
    card("可触达（有号码且已授权）", readiness.READY || 0),
    card("待人工确认", overview.leads_by_status.PENDING_REVIEW || 0),
    card("线索总数", valuesSum(overview.leads_by_status))
  );

  const regions = {};
  const languages = {};
  poolPageData.items.forEach((lead) => {
    if (lead.region) regions[lead.region] = (regions[lead.region] || 0) + 1;
    if (lead.language) languages[lead.language] = (languages[lead.language] || 0) + 1;
  });
  const regionText = Object.entries(regions)
    .sort((a, b) => b[1] - a[1])
    .map(([code, count]) => code + " " + count)
    .join(" · ") || "—";
  const languageText = Object.entries(languages)
    .sort((a, b) => b[1] - a[1])
    .map(([code, count]) => code + " " + count)
    .join(" · ") || "—";
  const readinessText = Object.entries(readiness)
    .map(([code, count]) => zhName(READINESS_LABELS, code) + " " + count)
    .join(" · ") || "—";
  fill(
    $("pool-dist-note"),
    make("p", {
      class: "muted",
      text:
        "可发送性分布（全池）：" + readinessText +
        "；地区分布（当前页 " + poolPageData.items.length + " 条）：" + regionText +
        "；语言分布：" + languageText,
    })
  );

  let data;
  if (state.poolView === "pool") {
    data = await api("/api/v1/pool?page=" + state.poolPage + "&page_size=20");
  } else {
    const params = new URLSearchParams({ page: state.poolPage, page_size: "20" });
    if (state.poolView === "pending") params.set("status", "PENDING_REVIEW");
    if (state.poolQ) params.set("q", state.poolQ);
    data = await api("/api/v1/leads?" + params.toString());
  }
  fill(
    $("pool-table"),
    data.items.length
      ? table(
          ["用户名", "显示名", "状态", "评分", "地区"],
          data.items.map(poolRow)
        )
      : make("p", { text: "没有符合条件的线索。可以切换视图或清空搜索后重试。" })
  );
  $("pool-page-info").textContent = "共 " + data.total + " 条 · 第 " + data.page + " 页";
  $("pool-prev").disabled = data.page <= 1;
  $("pool-next").disabled = data.page * data.page_size >= data.total;
}
