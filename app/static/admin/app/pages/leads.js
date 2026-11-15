/* 线索工作台：导入与批次报告、评分看板、人工审核、用户池名单。 */

import { api, demo, errorText } from "../api.js";
import { loadOverview, invalidateOverview } from "../store.js";
import {
  h,
  clear,
  pageHead,
  guide,
  card,
  tabs,
  button,
  kpi,
  badge,
  chip,
  codeChip,
  reasonChips,
  table,
  pager,
  empty,
  callout,
  openDrawer,
  openModal,
  toast,
  toastError,
  fmtTime,
  fmtDate,
  input,
  field,
  text,
} from "../ui.js";
import { histogram, ring } from "../charts.js";
import {
  LEAD_STATUS_LABELS,
  READINESS_LABELS,
  SCORE_REASON_LABELS,
  BATCH_ERROR_LABELS,
  SOURCE_LABELS,
  TONE,
} from "../labels.js";
import { go } from "../router.js";

const BATCH_ERROR_CATEGORIES = {
  duplicates: ["DUPLICATE_USERNAME", "IMPORT_CONFLICT", "DUPLICATE_PHONE"],
  invalid: ["MISSING_USERNAME", "INVALID_USERNAME", "INVALID_SOURCE_URL"],
  warnings: ["INVALID_REGION", "INVALID_LANGUAGE", "INVALID_PHONE_DROPPED", "CONSENT_INCOMPLETE"],
};
const BATCH_TAB_ORDER = ["duplicates", "invalid", "warnings"];
const BATCH_TAB_LABELS = { success: "成功", duplicates: "重复", invalid: "无效", warnings: "警告" };

let pageView = null;
let pageParams = null;
let state = { view: "board", q: "", poolPage: 1, poolSearch: "", expanded: {} };

export async function render(view, params) {
  pageView = view;
  pageParams = params;
  state.view = params.get("view") === "pool" ? "pool" : "board";
  clear(view);
  view.append(h("div", { class: "loading" }, [h("span", { class: "spinner" }), "正在读取线索…"]));

  const [overview, batches, settings, leads, pool] = await Promise.all([
    loadOverview(true),
    api("/lead-batches", { query: { page_size: 5 } }),
    api("/settings"),
    api("/leads", { query: { page_size: 100, q: state.q || null } }),
    api("/pool", { query: { page_size: 100 } }),
  ]);

  clear(view);
  view.append(
    pageHead("线索工作台", "导入 → 自动筛选 → 人工审核 → 形成目标池", [
      button("导入示例线索", { kind: "primary", iconName: "upload", onClick: () => importMock() }),
      button("上传文件", { iconName: "upload", onClick: () => pickFile() }),
      button("批次历史", { onClick: () => openBatchHistory() }),
      button("刷新", { iconName: "refresh", onClick: () => refresh() }),
    ]),
    guide(
      "先导入线索，再点「自动筛选」打分；分数落在中间区间的线索会进入「待人工确认」，由你决定是否入池。",
      nextStepText(overview, batches, leads)
    )
  );

  const latest = batches.items[0];
  view.append(batchSummary(latest, batches));
  if (latest) {
    view.append(h("input", {
      type: "file",
      accept: ".csv,.json",
      class: "hidden",
      id: "lead-file-input",
      onchange: (event) => uploadFile(event.target.files[0]),
    }));
  } else {
    view.append(h("input", {
      type: "file",
      accept: ".csv,.json",
      class: "hidden",
      id: "lead-file-input",
      onchange: (event) => uploadFile(event.target.files[0]),
    }));
  }

  view.append(
    tabs(
      [
        { key: "board", label: "筛选看板" },
        { key: "pool", label: "用户池名单", count: pool.total, tone: "ok" },
      ],
      state.view,
      (key) => go(key === "pool" ? "#/leads?view=pool" : "#/leads")
    )
  );

  if (state.view === "pool") {
    view.append(renderPool(pool, overview));
  } else {
    view.append(renderBoard(overview, leads, settings));
  }
}

function nextStepText(overview, batches, leads) {
  const items = leads.items || [];
  const scored = items.some((lead) => lead.score !== null && lead.score !== undefined);
  const pending = (overview.leads_by_status || {}).PENDING_REVIEW || 0;
  if (!batches.total) return "下一步：点「导入示例线索」载入 52 行演示数据。";
  if (!scored) return "下一步：点「自动筛选」给线索打分并分档。";
  if (pending > 0) return `下一步：在「待人工确认」列审核这 ${pending} 条线索。`;
  if ((overview.pool_size || 0) > 0) return "下一步：到「任务」用目标池创建触达任务。";
  return "下一步：继续导入或筛选线索，形成可触达的目标池。";
}

function refresh() {
  if (pageView) render(pageView, pageParams).catch((error) => toastError(error));
}

async function importMock() {
  try {
    const batch = await api("/lead-batches/import", { method: "POST", body: { source: "mock" } });
    await reportBatch(batch);
    toast("示例线索已导入。", "success");
    refresh();
  } catch (error) {
    toastError(error, "导入失败");
  }
}

async function uploadFile(file) {
  if (!file) return;
  const form = new FormData();
  form.append("file", file);
  try {
    const batch = await api("/lead-batches/import", { method: "POST", form });
    await reportBatch(batch);
    toast("文件已导入。", "success");
    refresh();
  } catch (error) {
    toastError(error, "上传失败");
  }
}

function pickFile() {
  const node = document.getElementById("lead-file-input");
  if (node) node.click();
}

async function runScreening() {
  try {
    const result = await api("/leads/screen", { method: "POST", body: {} });
    invalidateOverview();
    openModal(
      "自动筛选完成",
      h("div", { class: "prose" }, [
        h("p", {}, `本次处理 ${result.processed} 条线索：自动入池 ${result.approved} 条，待人工确认 ${result.pending_review} 条，丢弃 ${result.discarded} 条，未变化 ${result.unchanged} 条。`),
        result.warning ? callout(result.warning, "warn") : null,
        h("p", { class: "muted" }, "下一步：到「待人工确认」列逐条决定是否入池。"),
      ]),
      { width: 500 }
    );
    refresh();
  } catch (error) {
    toastError(error, "筛选失败");
  }
}

function batchSummary(batch, batches) {
  if (!batch) {
    return callout("还没有导入批次。点右上角「导入示例线索」开始。", "accent");
  }
  return h("div", { class: "batch-strip" }, [
    h("div", { class: "batch-strip-main" }, [
      h("span", { class: "batch-strip-title" }, `最近批次 #${batch.id}`),
      h("span", { class: "muted" }, `${fmtTime(batch.created_at)} · ${(SOURCE_LABELS[batch.source_type] || [batch.source_type])[0]}`),
      h("div", { class: "chip-row" }, [
        chip(`总 ${batch.total_rows}`, "muted"),
        chip(`成功 ${batch.imported}`, "ok"),
        chip(`重复 ${batch.duplicates}`, "warn"),
        chip(`无效 ${batch.invalid}`, "danger"),
        chip(`警告 ${batch.warnings}`, "warn"),
      ]),
    ]),
    h("div", { class: "btn-row" }, [
      button("自动筛选", { kind: "primary", iconName: "refresh", onClick: () => runScreening() }),
      button("查看报告", { onClick: () => reportBatch(batch) }),
      button(`历史 ${batches.total}`, { onClick: () => openBatchHistory() }),
    ]),
  ]);
}

function renderBoard(overview, leads, settings) {
  const low = Number(settings["screening.threshold_low"] || 40);
  const high = Number(settings["screening.threshold_high"] || 70);
  const items = leads.items || [];
  const counts = overview.leads_by_status || {};
  const newCount = counts.NEW || 0;
  const wrap = h("div", { class: "board-wrap" });
  state.histogram = null;

  if (newCount > 0) {
    wrap.append(
      callout(`还有 ${newCount} 条新导入线索没有评分。`, "warn", button("立即自动筛选", {
        kind: "primary",
        onClick: () => runScreening(),
      }))
    );
  }

  wrap.append(
    h("div", { class: "kpi-row" }, [
      kpi("新导入", newCount, "等待评分", "muted"),
      kpi("待人工确认", counts.PENDING_REVIEW || 0, "需要你决定", "warn"),
      kpi("已入池", counts.APPROVED || 0, "可进入任务", "ok"),
      kpi("已拒绝", counts.REJECTED || 0, "人工不联系", "danger"),
      kpi("已丢弃", counts.DISCARDED || 0, "分数过低", "muted"),
    ])
  );

  const searchRow = h("div", { class: "search-row" }, [
    input({ type: "search", value: state.q, placeholder: "搜索用户名、显示名或简介…" }),
    button("搜索", { kind: "primary", onClick: () => {} }),
    state.q ? button("清空", { onClick: () => { state.q = ""; refresh(); } }) : null,
  ]);
  const search = searchRow.querySelector("input");
  const doSearch = () => {
    state.q = search.value.trim();
    refresh();
  };
  search.addEventListener("keydown", (event) => {
    if (event.key === "Enter") doSearch();
  });
  searchRow.querySelector("button").addEventListener("click", doSearch);
  wrap.append(searchRow);

  if (items.length) {
    const buckets = Array.from({ length: 10 }, (_, index) => ({
      label: index === 9 ? "90+" : `${index * 10}`,
      count: items.filter((lead) => {
        const score = lead.score;
        return score !== null && score !== undefined && Math.floor(score / 10) === index;
      }).length,
    }));
    state.histogram = { buckets, low, high };  }

  const columns = [
    { status: "APPROVED", title: "自动入池", hint: "分数达到入池线，可直接用于任务", tone: "ok" },
    { status: "PENDING_REVIEW", title: "待人工确认", hint: "分数在中间区间，需要你决定", tone: "warn" },
    { status: "REJECTED", title: "已拒绝", hint: "人工决定不联系", tone: "danger" },
    { status: "DISCARDED", title: "已丢弃", hint: "分数过低，不会联系", tone: "muted" },
  ];
  const board = h("div", { class: "board" });
  for (const column of columns) {
    const columnItems = items
      .filter((lead) => lead.status === column.status)
      .sort((a, b) => (b.score || 0) - (a.score || 0));
    const cap = column.status === "PENDING_REVIEW" ? 12 : 6;
    const expanded = Boolean(state.expanded[column.status]);
    const shown = expanded ? columnItems : columnItems.slice(0, cap);
    const list = h("div", { class: "board-list" }, shown.length
      ? shown.map((lead) => leadCard(lead, low, high, column.status === "PENDING_REVIEW"))
      : empty(column.status === "PENDING_REVIEW" ? "没有待确认线索。" : "这一列暂时为空。"));
    if (columnItems.length > cap) {
      list.append(
        button(expanded ? "收起" : `显示全部 ${columnItems.length} 条`, {
          onClick: () => {
            state.expanded[column.status] = !expanded;
            refresh();
          },
        })
      );
    }
    board.append(
      h("section", { class: `board-column tone-${column.tone}` }, [
        h("div", { class: "board-head" }, [
          h("div", {}, [
            h("h3", {}, column.title),
            h("p", { class: "muted" }, column.hint),
          ]),
          h("span", { class: "board-count" }, String((counts[column.status] || 0))),
        ]),
        list,
      ])
    );
  }
  wrap.append(board);
  if (state.histogram) {
    wrap.append(
      card(
        "评分分布",
        `共 ${items.length} 条；低于 ${low} 分丢弃，${low}–${high - 1} 分待确认，${high} 分及以上自动入池。`,
        histogram(state.histogram.buckets, [
          { value: low, tone: "warn", label: `丢弃线 ${low}` },
          { value: high, tone: "ok", label: `入池线 ${high}` },
        ])
      )
    );
  }
  if (leads.total > items.length) {
    wrap.append(callout(`共有 ${leads.total} 条线索，当前展示前 ${items.length} 条；可以用搜索缩小范围。`, "muted"));
  }
  return wrap;
}

function leadCard(lead, low, high, canReview) {
  const tone = lead.score === null || lead.score === undefined ? "muted" : lead.score >= high ? "ok" : lead.score >= low ? "warn" : "danger";
  const note = canReview ? input({ type: "text", placeholder: "备注（可选）" }) : null;
  const cardNode = h("article", { class: "lead-card", onclick: (event) => {
    if (event.target.closest("button, input, textarea, select, a, label")) return;
    openLeadDrawer(lead);
  } }, [
    h("div", { class: "lead-card-head" }, [
      h("div", {}, [
        h("strong", { class: "lead-name" }, lead.display_name || lead.username),
        h("span", { class: "muted" }, `@${lead.username}`),
      ]),
      lead.score !== null && lead.score !== undefined
        ? ring(lead.score, { size: 56, stroke: 6, tone, label: String(lead.score) })
        : chip("未评分", "muted"),
    ]),
    h("div", { class: "chip-row" }, [
      badge(LEAD_STATUS_LABELS, lead.status),
      lead.phone_masked ? chip(lead.phone_masked, "muted", "号码已脱敏") : chip("无号码", "muted"),
      lead.region ? chip(lead.region, "muted") : null,
      lead.language ? chip(lead.language, "muted") : null,
    ]),
    lead.top_keyword ? h("p", { class: "lead-keyword" }, `命中关键词：${lead.top_keyword}`) : null,
    lead.score_reasons && lead.score_reasons.length ? reasonChips(lead.score_reasons.slice(0, 4), SCORE_REASON_LABELS) : null,
    h("div", { class: "lead-card-foot" }, [
      h("span", { class: "muted" }, lead.decision_source === "MANUAL" ? "人工决定" : "自动评分"),
      canReview
        ? h("div", { class: "lead-actions" }, [
            note,
            button("通过", { kind: "primary", onClick: () => reviewLead(lead, "APPROVE", note.value) }),
            button("拒绝", { kind: "danger-ghost", onClick: () => reviewLead(lead, "REJECT", note.value) }),
          ])
        : button("查看详情", { onClick: () => openLeadDrawer(lead) }),
    ]),
  ]);
  return cardNode;
}

async function reviewLead(lead, decision, note) {
  try {
    await api(`/leads/${lead.id}/review`, {
      method: "POST",
      body: { decision, note: note || null },
    });
    invalidateOverview();
    toast(decision === "APPROVE" ? "已通过，线索进入目标池。" : "已拒绝，这条线索不会再联系。", "success");
    refresh();
  } catch (error) {
    toastError(error, "审核失败");
  }
}

function renderPool(pool, overview) {
  const items = pool.items || [];
  const counts = pool.readiness_counts || {};
  const search = input({ type: "search", value: state.poolSearch || "", placeholder: "在当前名单内搜索用户名、显示名或地区…" });
  const wrap = h("div", { class: "pool-wrap" });
  wrap.append(
    h("div", { class: "kpi-row" }, [
      kpi("池内总数", pool.total || 0, "已通过审核", "ok"),
      kpi("可发送", counts.READY || 0, "号码、授权、名单都满足", "ok"),
      kpi("无号码", counts.NO_PHONE || 0, "导入时没有可用号码", "muted"),
      kpi("无授权", counts.NO_CONSENT || 0, "没有同意接收记录", "muted"),
      kpi("黑名单", counts.BLACKLISTED || 0, "禁止联系", "danger"),
      kpi("已退订", counts.UNSUBSCRIBED || 0, "永久不再联系", "danger"),
    ])
  );
  wrap.append(
    callout(
      "「已入池」只代表筛选通过；能不能发送还要看号码、授权、黑名单与退订。",
      "accent",
      button("用这批人创建任务", { kind: "primary", onClick: () => go("#/tasks?new=1") })
    )
  );
  wrap.append(h("div", { class: "search-row" }, [search]));

  function paint() {
    const query = search.value.trim().toLowerCase();
    const filtered = items.filter((lead) =>
      !query ||
      [lead.username, lead.display_name, lead.region, lead.language]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(query))
    );
    const pageSize = 20;
    const pages = Math.max(1, Math.ceil(filtered.length / pageSize));
    state.poolPage = Math.min(Math.max(1, state.poolPage), pages);
    const start = (state.poolPage - 1) * pageSize;
    const pageItems = filtered.slice(start, start + pageSize);
    const host = wrap.querySelector(".pool-table-host");
    clear(host);
    host.append(
      table(
        ["用户名", "显示名", "状态", "评分", "地区 / 语言", "可发送性", "号码"],
        pageItems.map((lead) => [
          h("span", { class: "mono" }, `@${lead.username}`),
          text(lead.display_name),
          badge(LEAD_STATUS_LABELS, lead.status),
          lead.score === null || lead.score === undefined ? "—" : String(lead.score),
          [lead.region, lead.language].filter(Boolean).join(" / ") || "—",
          badge(READINESS_LABELS, lead.delivery_readiness),
          lead.phone_masked || "—",
        ]),
        {
          emptyText: query ? "没有匹配的线索。" : "目标池还是空的。先导入并审核线索。",
          onRowClick: (index) => openLeadDrawer(pageItems[index]),
        }
      ),
      h("div", { class: "pager" }, [
        h("span", { class: "muted" }, `第 ${state.poolPage} / ${pages} 页 · 共 ${filtered.length} 条`),
        h("span", { class: "spacer" }),
        button("上一页", { disabled: state.poolPage <= 1, onClick: () => { state.poolPage -= 1; paint(); } }),
        button("下一页", { disabled: state.poolPage >= pages, onClick: () => { state.poolPage += 1; paint(); } }),
      ])
    );
  }
  search.addEventListener("input", () => {
    state.poolSearch = search.value;
    state.poolPage = 1;
    paint();
  });
  wrap.append(h("div", { class: "pool-table-host" }));
  paint();
  if (pool.total > items.length) {
    wrap.append(callout(`池内共 ${pool.total} 条，当前加载前 ${items.length} 条。`, "muted"));
  }
  return wrap;
}

function openLeadDrawer(lead) {
  const low = 40;
  const high = 70;
  const score = lead.score;
  const tone = score === null || score === undefined ? "muted" : score >= high ? "ok" : score >= low ? "warn" : "danger";
  const drawer = openDrawer(
    lead.display_name || lead.username,
    h("div", { class: "drawer-content" }, [
      h("div", { class: "lead-detail-head" }, [
        score !== null && score !== undefined
          ? ring(score, { size: 92, stroke: 8, tone, label: String(score), hint: "相关性评分" })
          : h("div", { class: "muted" }, "尚未评分"),
        h("div", { class: "kv-list" }, [
          h("div", { class: "kv" }, [h("span", { class: "kv-label" }, "用户名"), h("span", { class: "kv-value mono" }, `@${lead.username}`)]),
          h("div", { class: "kv" }, [h("span", { class: "kv-label" }, "状态"), h("span", { class: "kv-value" }, badge(LEAD_STATUS_LABELS, lead.status))]),
          h("div", { class: "kv" }, [h("span", { class: "kv-label" }, "可发送性"), h("span", { class: "kv-value" }, lead.delivery_readiness ? badge(READINESS_LABELS, lead.delivery_readiness) : "仅入池视图显示")]),
        ]),
      ]),
      h("section", { class: "drawer-section" }, [
        h("h4", {}, "资料"),
        h("p", { class: "lead-bio" }, lead.bio || "没有简介。"),
        h("div", { class: "kv-list" }, [
          h("div", { class: "kv" }, [h("span", { class: "kv-label" }, "地区"), h("span", { class: "kv-value" }, text(lead.region))]),
          h("div", { class: "kv" }, [h("span", { class: "kv-label" }, "语言"), h("span", { class: "kv-value" }, text(lead.language))]),
          h("div", { class: "kv" }, [h("span", { class: "kv-label" }, "号码（脱敏）"), h("span", { class: "kv-value" }, lead.phone_masked || "无")]),
          h("div", { class: "kv" }, [h("span", { class: "kv-label" }, "来源"), h("span", { class: "kv-value" }, lead.source_url || "未提供")]),
          h("div", { class: "kv" }, [h("span", { class: "kv-label" }, "导入时间"), h("span", { class: "kv-value" }, fmtTime(lead.created_at))]),
        ]),
      ]),
      h("section", { class: "drawer-section" }, [
        h("h4", {}, "评分原因"),
        lead.score_reasons && lead.score_reasons.length
          ? reasonChips(lead.score_reasons, SCORE_REASON_LABELS)
          : h("p", { class: "muted" }, "还没有评分原因。"),
        lead.top_keyword ? h("p", { class: "muted" }, `命中关键词：${lead.top_keyword}`) : null,
      ]),
      h("section", { class: "drawer-section" }, [
        h("h4", {}, "审核"),
        h("div", { class: "kv-list" }, [
          h("div", { class: "kv" }, [h("span", { class: "kv-label" }, "决定来源"), h("span", { class: "kv-value" }, lead.decision_source === "MANUAL" ? "人工决定" : "自动评分")]),
          h("div", { class: "kv" }, [h("span", { class: "kv-label" }, "审核人"), h("span", { class: "kv-value" }, text(lead.reviewed_by))]),
          h("div", { class: "kv" }, [h("span", { class: "kv-label" }, "审核时间"), h("span", { class: "kv-value" }, fmtTime(lead.reviewed_at))]),
          h("div", { class: "kv" }, [h("span", { class: "kv-label" }, "备注"), h("span", { class: "kv-value" }, text(lead.review_note))]),
        ]),
      ]),
      lead.status === "PENDING_REVIEW"
        ? h("div", { class: "btn-row" }, [
            button("通过并加入目标池", { kind: "primary", onClick: async () => { await reviewLead(lead, "APPROVE", ""); drawer.close(); } }),
            button("拒绝", { kind: "danger-ghost", onClick: async () => { await reviewLead(lead, "REJECT", ""); drawer.close(); } }),
          ])
        : null,
    ]),
    { width: 560 }
  );
}

function errorCategory(code) {
  for (const category of BATCH_TAB_ORDER) {
    if (BATCH_ERROR_CATEGORIES[category].includes(code)) return category;
  }
  return "warnings";
}

async function reportBatch(batch) {
  const body = h("div", { class: "batch-report" });
  const drawer = openDrawer(`导入报告 · 批次 #${batch.id}`, body, { width: 640 });
  renderBatchCard(batch, body);
}

function renderBatchCard(batch, host) {
  clear(host);
  const categories = {
    success: batch.imported || 0,
    duplicates: batch.duplicates || 0,
    invalid: batch.invalid || 0,
    warnings: batch.warnings || 0,
  };
  let active = "success";
  for (const key of BATCH_TAB_ORDER) {
    if (categories[key] > 0) {
      active = key;
      break;
    }
  }
  const body = h("div", { class: "batch-report-body" });
  function paint() {
    clear(body);
    if (active === "success") {
      body.append(
        callout(`本批次成功导入 ${batch.imported} 条线索。成功行可以在「筛选看板」里查看与审核。`, "ok", button("去看线索", {
          onClick: () => { go("#/leads"); },
        }))
      );
      return;
    }
    const rows = (batch.errors || []).filter((entry) => errorCategory(entry.code) === active);
    body.append(
      table(
        ["行号", "原因", "说明"],
        rows.map((entry) => {
          const label = BATCH_ERROR_LABELS[entry.code] || [entry.code, ""];
          return [String(entry.row), codeChip(entry.code, BATCH_ERROR_LABELS), label[1] || entry.detail];
        }),
        { emptyText: "这一类没有记录。" }
      )
    );
  }
  host.append(
    h("div", { class: "chip-row batch-report-counts" }, [
      chip(`总数 ${batch.total_rows}`, "muted"),
      chip(`成功 ${batch.imported}`, "ok"),
      chip(`重复 ${batch.duplicates}`, "warn"),
      chip(`无效 ${batch.invalid}`, "danger"),
      chip(`警告 ${batch.warnings}`, "warn"),
    ]),
    h("p", { class: "muted" }, `${fmtTime(batch.created_at)} · 来源 ${(SOURCE_LABELS[batch.source_type] || [batch.source_type])[0]} · 操作人 ${batch.created_by}`),
    tabs(
      Object.keys(BATCH_TAB_LABELS).map((key) => ({
        key,
        label: BATCH_TAB_LABELS[key],
        count: categories[key],
        tone: key === "success" ? "ok" : key === "invalid" ? "danger" : "warn",
      })),
      active,
      (key) => { active = key; paint(); }
    ),
    body
  );
  paint();
}

async function loadBatchHistory() {
  return api("/lead-batches", { query: { page_size: 20 } });
}

async function openBatchHistory() {
  const body = h("div", {}, h("div", { class: "loading" }, [h("span", { class: "spinner" }), "正在读取批次…"]));
  const drawer = openDrawer("批次历史", body, { width: 680 });

  function showReport(batch) {
    clear(body);
    body.append(
      h("div", { class: "btn-row" }, [button("← 返回批次历史", { onClick: () => paintHistory() })]),
      h("div", { class: "batch-report" })
    );
    renderBatchCard(batch, body.querySelector(".batch-report"));
  }

  async function paintHistory() {
    clear(body);
    body.append(h("div", { class: "loading" }, [h("span", { class: "spinner" }), "正在读取批次…"]));
    try {
      const data = await loadBatchHistory();
      clear(body);
      if (!data.items.length) {
        body.append(empty("还没有导入批次。", button("导入示例线索", { kind: "primary", onClick: () => { drawer.close(); importMock(); } })));
        return;
      }
      body.append(
        table(
          ["批次", "时间", "来源", "总数", "成功", "重复", "无效", "警告", ""],
          data.items.map((batch) => [
            `#${batch.id}`,
            fmtTime(batch.created_at),
            (SOURCE_LABELS[batch.source_type] || [batch.source_type])[0],
            String(batch.total_rows),
            String(batch.imported),
            String(batch.duplicates),
            String(batch.invalid),
            String(batch.warnings),
            button("展开结果", { onClick: () => showReport(batch) }),
          ])
        )
      );
    } catch (error) {
      clear(body);
      body.append(callout(`读取失败：${errorText(error)}`, "danger"));
    }
  }

  await paintHistory();
}
