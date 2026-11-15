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
  empty,
  callout,
  openDrawer,
  openModal,
  confirmDialog,
  toast,
  toastError,
  fmtTime,
  input,
  select,
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
  ERROR_HINTS,
} from "../labels.js";
import { go } from "../router.js";

const BATCH_ERROR_CATEGORIES = {
  duplicates: ["DUPLICATE_USERNAME", "IMPORT_CONFLICT", "DUPLICATE_PHONE"],
  invalid: ["MISSING_USERNAME", "INVALID_USERNAME", "INVALID_SOURCE_URL"],
  warnings: ["INVALID_REGION", "INVALID_LANGUAGE", "INVALID_PHONE_DROPPED", "CONSENT_INCOMPLETE"],
};
const BATCH_TAB_ORDER = ["duplicates", "invalid", "warnings"];
const BATCH_TAB_LABELS = { success: "成功", duplicates: "重复", invalid: "无效", warnings: "警告" };
const BOARD_STATUSES = ["NEW", "PENDING_REVIEW", "APPROVED", "REJECTED", "DISCARDED"];
const PAGE_SIZES = [10, 20, 50, 100];

let pageView = null;
let pageParams = null;
let state = {
  view: "board",
  q: "",
  poolPage: 1,
  poolSearch: "",
  board: { status: "ALL", page: 1, size: 10, selected: new Set() },
};

export async function render(view, params) {
  pageView = view;
  pageParams = params;
  state.view = params.get("view") === "pool" ? "pool" : "board";
  clear(view);
  view.append(h("div", { class: "loading" }, [h("span", { class: "spinner" }), "正在读取线索…"]));

  const [overview, batches, settings, leads, pool, distribution] = await Promise.all([
    loadOverview(true),
    api("/lead-batches", { query: { page_size: 5 } }),
    api("/settings"),
    fetchLeadsPage(),
    api("/pool", { query: { page_size: 100 } }),
    api("/leads", { query: { page_size: 100 } }),
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
      "先导入线索，再点「自动筛选」打分；分数落在中间区间的线索会进入「待人工确认」，由你决定是否入池。表格可按线索类型筛选并分页查看。",
      nextStepText(overview, batches, distribution)
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
        { key: "board", label: "线索列表" },
        { key: "pool", label: "用户池名单", count: pool.total, tone: "ok" },
      ],
      state.view,
      (key) => go(key === "pool" ? "#/leads?view=pool" : "#/leads")
    )
  );

  if (state.view === "pool") {
    view.append(renderPool(pool, overview));
  } else {
    view.append(renderBoard(overview, leads, distribution, settings));
  }
}

function nextStepText(overview, batches, distribution) {
  const items = distribution.items || [];
  const scored = items.some((lead) => lead.score !== null && lead.score !== undefined);
  const pending = (overview.leads_by_status || {}).PENDING_REVIEW || 0;
  if (!batches.total) return "下一步：点「导入示例线索」载入 52 行演示数据。";
  if (!scored) return "下一步：点「自动筛选」给线索打分并分档。";
  if (pending > 0) return `下一步：把「线索类型」选为「待人工确认」，审核这 ${pending} 条线索。`;
  if ((overview.pool_size || 0) > 0) return "下一步：到「任务」用目标池创建触达任务。";
  return "下一步：继续导入或筛选线索，形成可触达的目标池。";
}

function refresh() {
  if (pageView) render(pageView, pageParams).catch((error) => toastError(error));
}

function leadsQuery() {
  return {
    status: state.board.status === "ALL" ? null : state.board.status,
    page: state.board.page,
    page_size: state.board.size,
    q: state.q || null,
  };
}

async function fetchLeadsPage() {
  const data = await api("/leads", { query: leadsQuery() });
  const pages = Math.max(1, Math.ceil((data.total || 0) / state.board.size));
  if (state.board.page > pages) {
    state.board.page = pages;
    return api("/leads", { query: leadsQuery() });
  }
  return data;
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
        h("p", { class: "muted" }, "下一步：把「线索类型」选为「待人工确认」，逐条决定是否入池。"),
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

function renderBoard(overview, leads, distribution, settings) {
  const low = Number(settings["screening.threshold_low"] || 40);
  const high = Number(settings["screening.threshold_high"] || 70);
  const counts = overview.leads_by_status || {};
  const newCount = counts.NEW || 0;
  const allCount = Object.values(counts).reduce((sum, value) => sum + value, 0);
  const distributionItems = distribution.items || [];
  const wrap = h("div", { class: "board-wrap" });

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
    state.q ? button("清空", { onClick: () => { state.q = ""; state.board.page = 1; refresh(); } }) : null,
  ]);
  const search = searchRow.querySelector("input");
  const doSearch = () => {
    state.q = search.value.trim();
    state.board.page = 1;
    refresh();
  };
  search.addEventListener("keydown", (event) => {
    if (event.key === "Enter") doSearch();
  });
  searchRow.querySelector("button").addEventListener("click", doSearch);
  wrap.append(searchRow);

  /* 类型筛选、每页条数与翻页都交给 /leads 查询，避免只在前 100 条里过滤。 */
  const typeSelect = select(
    [
      { value: "ALL", label: `全部（${allCount}）` },
      ...BOARD_STATUSES.map((status) => ({
        value: status,
        label: `${(LEAD_STATUS_LABELS[status] || [status])[0]}（${counts[status] || 0}）`,
      })),
    ],
    state.board.status,
    {
      onChange: (event) => {
        state.board.status = event.target.value;
        state.board.page = 1;
        reload();
      },
    }
  );
  const sizeSelect = select(
    PAGE_SIZES.map((sizeOption) => ({ value: String(sizeOption), label: `每页 ${sizeOption} 条` })),
    String(state.board.size),
    {
      onChange: (event) => {
        state.board.size = Number(event.target.value);
        state.board.page = 1;
        reload();
      },
    }
  );
  const selected = state.board.selected;
  selected.clear();
  const bulkCount = h("span", { class: "bulk-count" }, "未选择线索");
  const tableHost = h("div", { class: "board-table-host" });
  wrap.append(
    h("div", { class: "search-row" }, [
      h("span", { class: "muted" }, "线索类型："),
      typeSelect,
      h("span", { class: "bulk-divider" }),
      bulkCount,
      button("批量通过", { kind: "primary", iconName: "check", onClick: () => bulkReview("APPROVE") }),
      button("批量拒绝", { kind: "danger-ghost", onClick: () => bulkReview("REJECT") }),
      h("span", { class: "spacer" }),
      sizeSelect,
    ]),
    tableHost
  );

  let requestSeq = 0;
  let currentItems = [];
  let selectAllBox = null;
  let rowChecks = new Map();

  function syncBulk() {
    rowChecks.forEach((box, id) => {
      box.checked = selected.has(id);
    });
    const pending = currentItems.filter((lead) => lead.status === "PENDING_REVIEW");
    if (selectAllBox) {
      const chosen = pending.filter((lead) => selected.has(lead.id)).length;
      selectAllBox.checked = pending.length > 0 && chosen === pending.length;
      selectAllBox.indeterminate = chosen > 0 && chosen < pending.length;
    }
    bulkCount.textContent = selected.size ? `已选 ${selected.size} 条` : "未选择线索";
  }

  function paintTable(data) {
    currentItems = data.items || [];
    rowChecks = new Map();
    const total = data.total || 0;
    const pages = Math.max(1, Math.ceil(total / state.board.size));
    const emptyText = state.q
      ? "没有匹配的线索。可以清空搜索后重试。"
      : state.board.status === "ALL"
        ? "还没有线索。点右上角「导入示例线索」开始。"
        : "这个类型下暂时没有线索。可以切换类型查看其他线索。";
    const pendingOnPage = currentItems.filter((lead) => lead.status === "PENDING_REVIEW");
    const selectAll = h("input", {
      type: "checkbox",
      class: "row-check",
      title: pendingOnPage.length ? "全选本页待审核线索" : "本页没有待审核线索",
      disabled: pendingOnPage.length === 0,
      onchange: (event) => {
        if (event.target.checked) pendingOnPage.forEach((lead) => selected.add(lead.id));
        else pendingOnPage.forEach((lead) => selected.delete(lead.id));
        syncBulk();
      },
    });
    selectAllBox = selectAll;
    clear(tableHost);
    tableHost.append(
      table(
        [h("div", { class: "lead-head" }, [selectAll, h("span", {}, "线索")]), "状态", "评分", "地区 / 语言", "号码", "操作"],
        currentItems.map((lead) => {
          const canReview = lead.status === "PENDING_REVIEW";
          let check;
          if (canReview) {
            check = h("input", {
              type: "checkbox",
              class: "row-check",
              title: `选择 @${lead.username}`,
              checked: selected.has(lead.id),
              onchange: (event) => {
                if (event.target.checked) selected.add(lead.id);
                else selected.delete(lead.id);
                syncBulk();
              },
            });
            rowChecks.set(lead.id, check);
          } else {
            check = h("span", { class: "check-spacer" });
          }
          return [
            h("div", { class: "lead-cell" }, [
              check,
              h("div", { class: "lead-main" }, [
                h("strong", {}, lead.display_name || lead.username),
                h("span", { class: "mono muted" }, `@${lead.username}`),
                lead.score_reasons && lead.score_reasons.length
                  ? reasonChips(lead.score_reasons.slice(0, 2), SCORE_REASON_LABELS)
                  : null,
              ]),
            ]),
            badge(LEAD_STATUS_LABELS, lead.status),
            lead.score === null || lead.score === undefined
              ? h("span", { class: "muted" }, "未评分")
              : chip(String(lead.score), lead.score >= high ? "ok" : lead.score >= low ? "warn" : "danger", `相关性评分 ${lead.score}`),
            [lead.region, lead.language].filter(Boolean).join(" / ") || "—",
            lead.phone_masked || h("span", { class: "muted" }, "无号码"),
            canReview
              ? h("div", { class: "btn-row" }, [
                  button("通过", { kind: "primary", onClick: () => reviewLead(lead, "APPROVE", "") }),
                  button("拒绝", { kind: "danger-ghost", onClick: () => reviewLead(lead, "REJECT", "") }),
                ])
              : button("详情", { onClick: () => openLeadDrawer(lead) }),
          ];
        }),
        {
          emptyText,
          onRowClick: (index) => openLeadDrawer(currentItems[index]),
        }
      ),
      h("div", { class: "pager" }, [
        h("span", { class: "muted" }, `共 ${total} 条 · 第 ${state.board.page} / ${pages} 页`),
        h("span", { class: "spacer" }),
        button("上一页", { disabled: state.board.page <= 1, onClick: () => { state.board.page -= 1; reload(); } }),
        button("下一页", { disabled: state.board.page >= pages, onClick: () => { state.board.page += 1; reload(); } }),
      ])
    );
    syncBulk();
  }

  async function bulkReview(decision) {
    const ids = [...selected];
    const label = decision === "APPROVE" ? "通过" : "拒绝";
    if (!ids.length) {
      toast("请先勾选至少一条待审核线索。", "info");
      return;
    }
    const confirmed = await confirmDialog(
      `确定要批量${label}选中的 ${ids.length} 条线索吗？${decision === "APPROVE" ? "通过后会进入目标池。" : "拒绝后不会再联系这些线索。"}`,
      { danger: decision === "REJECT", confirmLabel: `批量${label}` }
    );
    if (!confirmed) return;
    try {
      const response = await api("/leads/review-bulk", {
        method: "POST",
        body: { reviews: ids.map((leadId) => ({ lead_id: leadId, decision })) },
      });
      const results = response.results || [];
      const failed = results.filter((item) => !item.ok);
      invalidateOverview();
      selected.clear();
      toast(
        `批量${label}完成：成功 ${results.length - failed.length} 条，失败 ${failed.length} 条。`,
        failed.length ? "error" : "success"
      );
      if (failed.length) showBulkFailures(failed);
      refresh();
    } catch (error) {
      toastError(error, `批量${label}失败`);
    }
  }

  function showBulkFailures(failed) {
    const byId = new Map(currentItems.map((lead) => [lead.id, lead]));
    openModal(
      "部分线索未处理",
      h("div", { class: "prose" }, [
        h("p", { class: "muted" }, `有 ${failed.length} 条线索没有处理成功，其余线索已更新。`),
        table(
          ["线索", "原因"],
          failed.map((item) => {
            const lead = byId.get(item.lead_id);
            return [
              lead ? `@${lead.username}` : `#${item.lead_id}`,
              ERROR_HINTS[item.error && item.error.code] || `操作失败（错误码 ${item.error ? item.error.code : "UNKNOWN"}）`,
            ];
          })
        ),
      ]),
      { width: 520 }
    );
  }

  async function reload() {
    selected.clear();
    const seq = ++requestSeq;
    syncBulk();
    clear(tableHost);
    tableHost.append(h("div", { class: "loading" }, [h("span", { class: "spinner" }), "正在读取线索…"]));
    try {
      const data = await fetchLeadsPage();
      if (seq !== requestSeq) return;
      paintTable(data);
    } catch (error) {
      if (seq !== requestSeq) return;
      clear(tableHost);
      tableHost.append(callout(`读取线索失败：${errorText(error)}`, "danger"));
    }
  }

  paintTable(leads);

  if (distributionItems.length) {
    const buckets = Array.from({ length: 10 }, (_, index) => ({
      label: index === 9 ? "90+" : `${index * 10}`,
      count: distributionItems.filter((lead) => {
        const score = lead.score;
        return score !== null && score !== undefined && Math.floor(score / 10) === index;
      }).length,
    }));
    wrap.append(
      card(
        "评分分布",
        `共 ${distribution.total || distributionItems.length} 条；低于 ${low} 分丢弃，${low}–${high - 1} 分待确认，${high} 分及以上自动入池。`,
        histogram(buckets, [
          { value: low, tone: "warn", label: `丢弃线 ${low}` },
          { value: high, tone: "ok", label: `入池线 ${high}` },
        ])
      )
    );
    if ((distribution.total || 0) > distributionItems.length) {
      wrap.append(callout(`评分分布基于前 ${distributionItems.length} 条线索（共 ${distribution.total} 条）。`, "muted"));
    }
  }
  return wrap;
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
        callout(`本批次成功导入 ${batch.imported} 条线索。成功行可以在「线索列表」里查看与审核。`, "ok", button("去看线索", {
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
