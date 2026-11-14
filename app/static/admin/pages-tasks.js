"use strict";

/* 任务页：卡片流列表 + 详情仪表盘（状态横幅、发送漏斗、明细分组标签页）。 */

const ITEM_GROUP_STATUSES = {
  all: null,
  success: ["SENT", "DELIVERED", "READ"],
  failed: ["FAILED"],
  skipped: ["SKIPPED"],
};

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
    make("div", { class: "task-grid" }, data.items.map(taskCard))
  );
}

function taskCard(task) {
  const processed = task.counts.total - task.counts.in_progress;
  const percent = task.counts.total
    ? Math.round((processed / task.counts.total) * 100)
    : 0;
  const open = button("查看详情", () => showTaskDetail(task.id).catch(quiet), "primary");
  return make("div", { class: "task-card" }, [
    make("div", { class: "task-card-head" }, [
      make("strong", { text: "#" + task.id + " " + task.name }),
      make("span", {
        class: "badge " + task.status,
        text: zhName(TASK_STATUS_LABELS, task.status),
        title: zhFull(TASK_STATUS_LABELS, task.status) + "：" + TASK_STATUS_LABELS[task.status][1],
      }),
    ]),
    make("div", { class: "progress" }, [
      make("i", { style: "width:" + percent + "%" }),
    ]),
    make("p", { class: "muted", text: "已处理 " + processed + " / " + task.counts.total + " 条" }),
    make("p", {
      class: "muted",
      text:
        "成功 " + task.counts.success + " · 失败 " + task.counts.failed +
        " · 跳过 " + task.counts.skipped,
    }),
    open,
  ]);
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
  state.itemGroup = "all";
  state.itemReason = "";
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
  state.taskStats = results[1];
  renderTaskDetail(results[0], results[1]);
  await loadTaskItems();
  if (results[0].status === "RUNNING") startPolling(taskId);
  else stopPolling();
}

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

function funnelSegment(label, count, total, group, tone) {
  const percent = total ? Math.max(Math.round((count / total) * 100), count ? 4 : 0) : 0;
  const seg = make("button", {
    type: "button",
    class: "funnel-seg" + (tone ? " tone-" + tone : ""),
    title: "点击查看对应的明细分组",
  }, [
    make("span", { class: "funnel-label", text: label }),
    make("span", { class: "funnel-count", text: String(count) }),
    make("span", { class: "funnel-bar" }, [
      make("i", { style: "width:" + percent + "%" }),
    ]),
  ]);
  seg.addEventListener("click", () => {
    state.itemGroup = group;
    loadTaskItems().catch(quiet);
    $("task-items").scrollIntoView({ behavior: "smooth", block: "nearest" });
  });
  return seg;
}

function renderTaskFunnel(stats) {
  const by = (code) => stats.by_status[code] || 0;
  const sent = by("SENT") + by("DELIVERED") + by("READ") + by("FAILED");
  const delivered = by("DELIVERED") + by("READ");
  const funnel = make("div", { class: "funnel" }, [
    funnelSegment("目标", stats.total, stats.total, "all", ""),
    funnelSegment("跳过", stats.skipped, stats.total, "skipped", "muted"),
    funnelSegment("已发送", sent, stats.total, "success", ""),
    funnelSegment("送达", delivered, stats.total, "success", ""),
    funnelSegment("已读", by("READ"), stats.total, "success", ""),
    funnelSegment("失败", stats.failed, stats.total, "failed", "danger"),
  ]);
  const skipDetail = make("details", { class: "funnel-detail" }, [
    make("summary", { text: "跳过原因分布（点击展开）" }),
    make("p", { class: "muted", text: "跳过原因：" + fmtReasons(stats.skip_reasons) }),
  ]);
  return make("div", {}, [make("h3", { text: "发送漏斗（点击任一段查看对应明细）" }), funnel, skipDetail]);
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
  controls[2].title = "只有已暂停的任务可以恢复";
  controls[3].title = "终止任务，尚未发送的线索会被跳过";
  controls[0].disabled = detail.status !== "DRAFT";
  controls[1].disabled = !active;
  controls[2].disabled = detail.status !== "PAUSED";
  controls[3].disabled = !(detail.status === "DRAFT" || active || detail.status === "PAUSED");
  const processed = stats.total - stats.in_progress;
  const percent = stats.total ? Math.round((processed / stats.total) * 100) : 0;
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
      make("span", { class: "spacer" }),
      make("div", { class: "row banner-controls" }, controls),
    ]),
    make("div", { class: "task-banner" }, [
      make("div", { class: "progress large" }, [
        make("i", { style: "width:" + percent + "%" }),
      ]),
      make("p", { class: "muted", text: "已处理 " + processed + " / " + stats.total + " 条" }),
    ]),
  ];
  nodes.push(renderTaskStatusNote(detail));
  nodes.push(renderTaskFunnel(stats));
  nodes.push(make("div", { class: "cards" }, cards));
  nodes.push(
    make("p", {
      class: "muted",
      text: "成功 = 已发送、已送达或已读；成功率 = 成功 ÷（成功 + 失败）；重试次数 = 额外重试的总次数。",
    })
  );
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

function itemGroupCounts(stats) {
  const by = (code) => (stats.by_status[code] || 0);
  return {
    all: stats.total,
    success: by("SENT") + by("DELIVERED") + by("READ"),
    failed: by("FAILED"),
    skipped: by("SKIPPED"),
  };
}

async function loadTaskItems() {
  const taskId = state.currentTask;
  if (!taskId) return;
  const reasonParams = state.itemReason
    ? "&reason_code=" + encodeURIComponent(state.itemReason)
    : "";
  const statuses = ITEM_GROUP_STATUSES[state.itemGroup];
  let items;
  if (statuses) {
    const results = await Promise.all(
      statuses.map((status) =>
        api("/api/v1/campaigns/" + taskId + "/items?status=" + status + "&page_size=50" + reasonParams)
      )
    );
    items = results
      .flatMap((data) => data.items)
      .sort((a, b) => a.id - b.id);
  } else {
    const data = await api(
      "/api/v1/campaigns/" + taskId + "/items?page_size=50" + reasonParams
    );
    items = data.items;
  }

  const counts = state.taskStats ? itemGroupCounts(state.taskStats) : null;
  const tabBar = make("div", { class: "tabbar" });
  [
    ["all", "全部"],
    ["success", "成功"],
    ["failed", "失败"],
    ["skipped", "跳过"],
  ].forEach(([group, label]) => {
    const tabButton = button(
      label + (counts ? " (" + counts[group] + ")" : ""),
      () => {
        state.itemGroup = group;
        loadTaskItems().catch(quiet);
      }
    );
    tabButton.dataset.group = group;
    if (state.itemGroup === group) tabButton.classList.add("active");
    tabBar.appendChild(tabButton);
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

  const rows = items.map((item) => {
    const logButton = button("日志", () => openSendLogs(taskId, item.id).catch(quiet));
    logButton.title = "查看这条线索的发送过程";
    const detail = make("div", { class: "expand-detail" }, [
      make("p", { text: "下次尝试：" + (item.next_attempt_at || "—") }),
      make("p", {}, [
        "最后错误：",
        item.last_error_code ? labelNode(REASON_LABELS, item.last_error_code) : "—",
      ]),
      make("p", { text: "号码：" + (item.phone_masked || "—") }),
    ]);
    return expandableRow(
      [
        item.id,
        item.lead_username,
        labelNode(ITEM_STATUS_LABELS, item.status),
        item.reason_code ? labelNode(REASON_LABELS, item.reason_code) : "—",
        item.attempts,
        logButton,
      ],
      detail
    );
  });
  const rowsFlattened = [];
  rows.forEach(([row, detail]) => {
    rowsFlattened.push(row, detail);
  });
  const tableNode = make("table", {}, [
    make("tr", {}, ["编号", "用户名", "状态", "原因", "尝试次数", "操作"].map((header) =>
      make("th", { text: header })
    )),
    ...rowsFlattened,
  ]);
  fill(
    $("task-items"),
    make("div", { class: "row" }, [
      make("h3", { text: "明细（每条线索的处理结果，点击行展开详情）" }),
      reasonInput,
    ]),
    tabBar,
    items.length
      ? tableNode
      : make("p", {
          text: "没有符合条件的明细。可以切换分组或清空原因筛选后重试。",
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
