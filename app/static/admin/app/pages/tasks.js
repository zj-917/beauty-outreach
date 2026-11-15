/* 触达任务：任务卡片流与三步创建向导。 */

import { api, errorText } from "../api.js";
import { loadOverview, invalidateOverview } from "../store.js";
import {
  h,
  clear,
  pageHead,
  guide,
  card,
  button,
  kpi,
  badge,
  chip,
  reasonChips,
  empty,
  callout,
  openDrawer,
  toast,
  toastError,
  fmtTime,
  input,
  select,
  field,
  progressBar,
} from "../ui.js";
import { miniBar } from "../charts.js";
import {
  TASK_STATUS_LABELS,
  TEMPLATE_STATUS_LABELS,
  REASON_LABELS,
} from "../labels.js";
import { go } from "../router.js";
import { markPreviewSeen } from "../wizard.js";

let pageView = null;

export async function render(view, params) {
  pageView = view;
  clear(view);
  view.append(h("div", { class: "loading" }, [h("span", { class: "spinner" }), "正在读取任务…"]));
  const [overview, campaigns, templates, batches, pool] = await Promise.all([
    loadOverview(true),
    api("/campaigns", { query: { page_size: 50 } }),
    api("/templates"),
    api("/lead-batches", { query: { page_size: 20 } }),
    api("/pool", { query: { page_size: 1 } }),
  ]);
  const approved = templates.filter((template) => template.status === "APPROVED");
  const templateById = new Map(templates.map((template) => [template.id, template]));

  clear(view);
  view.append(
    pageHead("触达任务", "创建任务、监控发送、查看结果", [
      button("新建任务", { kind: "primary", iconName: "plus", onClick: () => openCampaignWizard({ approved, batches, pool }) }),
      button("刷新", { iconName: "refresh", onClick: () => render(view, params) }),
    ]),
    guide(
      "填写任务名称与模板 → 选择目标人群 → 创建草稿并预览；预览不会发送，确认后打开详情点「启动」。",
      campaigns.total ? "下一步：打开一个任务看详情，或新建任务。" : "下一步：点「新建任务」创建第一个触达任务。"
    )
  );

  view.append(
    h("div", { class: "kpi-row" }, [
      kpi("任务总数", campaigns.total || 0, "包含所有状态", "muted"),
      kpi("草稿", (overview.campaigns_by_status || {}).DRAFT || 0, "还没开始发送", "accent"),
      kpi("运行中", (overview.campaigns_by_status || {}).RUNNING || 0, "系统正在发送", "info"),
      kpi("已完成", (overview.campaigns_by_status || {}).COMPLETED || 0, "全部有结果", "ok"),
    ])
  );

  if (!approved.length) {
    view.append(
      callout(
        "还没有已审核的消息模板。任务只能选择已审核模板。",
        "warn",
        button("去配置页审核模板", { kind: "primary", onClick: () => go("#/settings?tab=templates") })
      )
    );
  }

  if (!campaigns.items.length) {
    view.append(
      empty(
        "还没有触达任务。先在线索工作台形成目标池，再创建任务。",
        button("新建任务", { kind: "primary", onClick: () => openCampaignWizard({ approved, batches, pool }) })
      )
    );
  } else {
    view.append(
      h(
        "div",
        { class: "task-grid" },
        campaigns.items.map((campaign) => taskCard(campaign, templateById))
      )
    );
  }

  if (params.get("new") === "1" && approved.length) {
    history.replaceState(null, "", "#/tasks");
    openCampaignWizard({ approved, batches, pool });
  }
}

function taskCard(campaign, templateById) {
  const counts = campaign.counts || {};
  const processed = Math.max(0, (counts.total || 0) - (counts.in_progress || 0));
  const template = templateById.get(campaign.template_id);
  return h("article", { class: "task-card", onclick: (event) => {
    if (event.target.closest("button, a")) return;
    go(`#/tasks/${campaign.id}`);
  } }, [
    h("div", { class: "task-card-head" }, [
      h("div", {}, [
        h("h3", {}, campaign.name),
        h("p", { class: "muted" }, `#${campaign.id} · ${fmtTime(campaign.created_at)}`),
      ]),
      badge(TASK_STATUS_LABELS, campaign.status),
    ]),
    template ? h("p", { class: "muted" }, `模板：${template.name} v${template.version}`) : null,
    h("div", { class: "task-progress" }, [
      progressBar(processed, counts.total || 0, campaign.status === "RUNNING" ? "info" : campaign.status === "COMPLETED" ? "ok" : "muted"),
      h("span", { class: "muted" }, `已处理 ${processed} / ${counts.total || 0}`),
    ]),
    miniBar(counts),
    h("div", { class: "chip-row" }, [
      chip(`成功 ${counts.success || 0}`, "ok"),
      chip(`失败 ${counts.failed || 0}`, "danger"),
      chip(`跳过 ${counts.skipped || 0}`, "muted"),
      campaign.pause_reason ? chip("已暂停", "warn") : null,
    ]),
    h("div", { class: "btn-row end" }, [
      button("打开任务详情", { kind: "primary", onClick: () => go(`#/tasks/${campaign.id}`) }),
    ]),
  ]);
}

export function openCampaignWizard({ approved, batches, pool } = {}) {
  const body = h("div", { class: "wizard-form" });
  const drawer = openDrawer("新建触达任务", body, { width: 620 });
  const state = { step: 1, campaign: null, preview: null };
  const name = input({ type: "text", value: `演示任务 ${new Date().toLocaleDateString("zh-CN")}`, placeholder: "例如：首轮问候" });
  const template = select(
    (approved || []).map((item) => ({
      value: String(item.id),
      label: `${item.name} v${item.version}（#${item.id}）`,
    })),
    approved && approved.length ? String(approved[0].id) : ""
  );
  const templatePreview = h("p", { class: "tpl-preview muted" }, approved && approved.length ? approved[0].body : "没有可用模板。");
  template.addEventListener("change", () => {
    const picked = (approved || []).find((item) => String(item.id) === template.value);
    templatePreview.textContent = picked ? picked.body : "";
  });
  const minScore = input({ type: "number", value: "70", min: 0, max: 100 });
  const batch = select(
    [{ value: "", label: "全部批次" }, ...(batches ? batches.items : []).map((item) => ({
      value: String(item.id),
      label: `批次 #${item.id} · ${fmtTime(item.created_at)}`,
    }))],
    ""
  );
  const errorHost = h("div", { class: "wizard-error" });

  function paint() {
    clear(body);
    body.append(stepHeader(state));
    errorHost.replaceChildren();
    if (state.step === 1) {
      body.append(
        field("任务名称", name, "只用于识别这次发送，不影响内容。"),
        field("消息模板", template, "只能选择已审核模板；模板正文里的变量会在发送时替换。"),
        h("div", { class: "tpl-preview-box" }, [
          h("h4", {}, "模板预览"),
          templatePreview,
        ]),
        errorHost,
        h("div", { class: "btn-row end" }, [
          button("取消", { onClick: () => drawer.close() }),
          button("下一步：选择人群", { kind: "primary", onClick: () => {
            if (!name.value.trim()) {
              errorHost.replaceChildren(callout("请先填写任务名称。", "danger"));
              return;
            }
            if (!template.value) {
              errorHost.replaceChildren(callout("请先在配置页审核一条消息模板。", "danger"));
              return;
            }
            state.step = 2;
            paint();
          } }),
        ])
      );
    } else if (state.step === 2) {
      const readiness = (pool && pool.readiness_counts) || {};
      body.append(
        field("最低分", minScore, "只把评分达到该值的已入池线索放进任务；分数越低，目标越多。"),
        field("限定批次", batch, "只在某一次导入的线索里选人；不选则覆盖全部已入池线索。"),
        h("div", { class: "readiness-summary" }, [
          h("div", { class: "kv" }, [h("span", { class: "kv-label" }, "目标池总数"), h("span", { class: "kv-value" }, String(pool ? pool.total : 0))]),
          h("div", { class: "kv" }, [h("span", { class: "kv-label" }, "其中可发送"), h("span", { class: "kv-value" }, String(readiness.READY || 0))]),
          h("div", { class: "kv" }, [h("span", { class: "kv-label" }, "无号码 / 无授权 / 名单拦截"), h("span", { class: "kv-value" }, `${(readiness.NO_PHONE || 0)} / ${(readiness.NO_CONSENT || 0) + (readiness.CONSENT_REVOKED || 0)} / ${(readiness.BLACKLISTED || 0) + (readiness.UNSUBSCRIBED || 0)}`)]),
        ]),
        callout("创建后会先得到一份草稿，下一步的预览会把发送前检查全部跑一遍，但不会真的发送。", "accent"),
        errorHost,
        h("div", { class: "btn-row end" }, [
          button("上一步", { onClick: () => { state.step = 1; paint(); } }),
          button("创建草稿并预览", { kind: "primary", onClick: () => createAndPreview() }),
        ])
      );
    } else {
      const preview = state.preview;
      body.append(
        callout("预览不会发送消息，也不会改变明细状态；它只模拟发送前检查。", "accent"),
        preview
          ? h("div", { class: "preview-grid" }, [
              kpi("任务明细", preview.total_items, "创建时快照的目标数量", "muted"),
              kpi("将尝试", preview.will_attempt, "通过发送前检查", "ok"),
              kpi("将释放", preview.will_release, "暂不发送，稍后释放", "warn"),
              kpi("将跳过", Object.values(preview.will_skip || {}).reduce((a, b) => a + b, 0), "被合规或去重规则拦截", "danger"),
            ])
          : null,
        preview && Object.keys(preview.will_skip || {}).length
          ? h("div", { class: "preview-skip" }, [
              h("h4", {}, "将跳过的原因"),
              reasonChips(preview.will_skip, REASON_LABELS),
            ])
          : null,
        h("p", { class: "muted" }, "频控延迟与静默时段没有在预览里模拟；真正发送时还会经过时间类检查。"),
        h("p", { class: "guide-next" }, "下一步：点「打开任务详情」确认后启动；或直接启动。"),
        errorHost,
        h("div", { class: "btn-row end" }, [
          button("上一步", { onClick: () => { state.step = 2; paint(); } }),
          button("打开任务详情", { onClick: () => { drawer.close(); go(`#/tasks/${state.campaign.id}`); } }),
          button("直接启动", {
            kind: "primary",
            disabled: !preview || preview.will_attempt === 0,
            title: preview && preview.will_attempt === 0 ? "没有可尝试的明细，先调整最低分或批次。" : "创建后立即启动发送",
            onClick: () => startNow(),
          }),
        ])
      );
    }
  }

  async function createAndPreview() {
    errorHost.replaceChildren();
    try {
      const campaign = await api("/campaigns", {
        method: "POST",
        body: {
          name: name.value.trim(),
          template_id: Number(template.value),
          selection: {
            min_score: Number(minScore.value || 0),
            batch_id: batch.value ? Number(batch.value) : null,
          },
        },
      });
      state.campaign = campaign;
      const preview = await api(`/campaigns/${campaign.id}/preview`, { method: "POST" });
      state.preview = preview;
      markPreviewSeen();
      invalidateOverview();
      toast(`任务已创建为草稿（#${campaign.id}）。`, "success");
      state.step = 3;
      paint();
    } catch (error) {
      errorHost.replaceChildren(
        callout(`创建失败：${error.message}（错误码 ${error.code}）${error.requestId ? ` · 请求编号 ${error.requestId}` : ""}`, "danger"),
        error.code === "CAMPAIGN_EMPTY_TARGET"
          ? h("p", { class: "muted" }, "可以降低最低分、切换批次，或先到线索工作台审核更多线索。")
          : null
      );
    }
  }

  async function startNow() {
    if (!state.campaign) return;
    try {
      await api(`/campaigns/${state.campaign.id}/start`, { method: "POST" });
      invalidateOverview();
      toast("任务已启动，正在逐条发送。", "success");
      drawer.close();
      go(`#/tasks/${state.campaign.id}`);
    } catch (error) {
      errorHost.replaceChildren(callout(`启动失败：${errorText(error)}`, "danger"));
    }
  }

  paint();
  return drawer;
}

function stepHeader(state) {
  const steps = ["基本信息", "目标人群", "预览确认"];
  return h("div", { class: "stepper" }, steps.map((label, index) => {
    const number = index + 1;
    const cls = number === state.step ? "step active" : number < state.step ? "step done" : "step";
    return h("div", { class: cls }, [
      h("span", { class: "step-dot" }, number < state.step ? "✓" : String(number)),
      h("span", {}, label),
    ]);
  }));
}
