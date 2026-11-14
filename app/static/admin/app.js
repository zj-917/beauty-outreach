"use strict";

/* 接线层：下拉选项填充、事件绑定与初始化。 */

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
  $("leads-tab-import").addEventListener("click", () => switchLeadsTab("import"));
  $("leads-tab-pool").addEventListener("click", () => switchLeadsTab("pool"));
  $("pool-view").addEventListener("change", () => {
    state.poolView = $("pool-view").value;
    state.poolPage = 1;
    loadPoolView().catch(quiet);
  });
  $("pool-search").addEventListener("click", () => {
    state.poolQ = $("pool-q").value.trim();
    state.poolPage = 1;
    loadPoolView().catch(quiet);
  });
  $("pool-prev").addEventListener("click", () => {
    state.poolPage = Math.max(1, state.poolPage - 1);
    loadPoolView().catch(quiet);
  });
  $("pool-next").addEventListener("click", () => {
    state.poolPage += 1;
    loadPoolView().catch(quiet);
  });
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
    return loadReviewList();
  });
  bind("lead-prev", () => {
    state.leadPage = Math.max(1, state.leadPage - 1);
    return loadReviewList();
  });
  bind("lead-next", () => {
    state.leadPage += 1;
    return loadReviewList();
  });
}

function init() {
  populateFilterChoices();
  loadAuth();
  bindEvents();
  switchPage("overview");
}

document.addEventListener("DOMContentLoaded", init);
