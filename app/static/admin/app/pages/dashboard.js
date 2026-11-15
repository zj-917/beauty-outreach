/* 驾驶舱：全链路漏斗、下一步行动、合规健康与最近动态。 */

import { api, checkHealth } from "../api.js";
import { loadOverview } from "../store.js";
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
  callout,
  fmtTime,
  text,
} from "../ui.js";
import { funnel, miniBar } from "../charts.js";
import {
  AUDIT_ACTION_LABELS,
  ENTITY_TYPE_LABELS,
  TASK_STATUS_LABELS,
} from "../labels.js";
import { go } from "../router.js";
import { openWizard } from "../wizard.js";

function sum(values) {
  return Object.values(values || {}).reduce((total, value) => total + (Number(value) || 0), 0);
}

function nextAction(overview, campaigns) {
  const pending = (overview.leads_by_status || {}).PENDING_REVIEW || 0;
  const drafts = (overview.campaigns_by_status || {}).DRAFT || 0;
  const running = (overview.campaigns_by_status || {}).RUNNING || 0;
  if (!sum(overview.leads_by_status)) {
    return ["还没有任何线索。先导入示例数据，才能开始筛选。", "导入示例线索", "#/leads", "accent"];
  }
  if (pending > 0) {
    return [`有 ${pending} 条线索等待人工确认，决定它们是否进入目标池。`, "去审核", "#/leads", "warn"];
  }
  if (drafts > 0) {
    return [`有 ${drafts} 个草稿任务还没有启动，预览确认后即可发送。`, "去处理任务", "#/tasks", "info"];
  }
  if (running > 0) {
    return [`${running} 个任务正在运行，去任务详情看进度与实时动态。`, "去监控", "#/tasks", "info"];
  }
  if (!campaigns.total) {
    return ["目标池已经就绪。下一步：创建第一个触达任务。", "创建任务", "#/tasks?new=1", "accent"];
  }
  return ["主线流程已走通。可以继续导入新线索，或到记录页复盘。", "查看记录", "#/records", "muted"];
}

export async function render(view) {
  clear(view);
  view.append(h("div", { class: "loading" }, [h("span", { class: "spinner" }), "正在读取总览…"]));

  const [overview, campaigns, batches, audits] = await Promise.all([
    loadOverview(true),
    api("/campaigns", { query: { page_size: 100 } }),
    api("/lead-batches", { query: { page_size: 3 } }),
    api("/audit-logs", { query: { page_size: 6 } }),
  ]);
  let health = null;
  let settings = null;
  try {
    health = await checkHealth();
  } catch (error) {
    health = null;
  }
  try {
    settings = await api("/settings");
  } catch (error) {
    settings = null;
  }

  clear(view);
  const totalLeads = sum(overview.leads_by_status);
  const screened = totalLeads - ((overview.leads_by_status || {}).NEW || 0);
  const latestCampaign = campaigns.items[0] || null;
  const taskTargets = latestCampaign ? latestCampaign.total_items || 0 : 0;
  const success = latestCampaign ? (latestCampaign.counts || {}).success || 0 : 0;
  const [actionText, actionLabel, actionRoute, actionTone] = nextAction(overview, campaigns);

  view.append(
    pageHead("驾驶舱", "先看整体，再决定下一步做什么", [
      button("继续演示流程", { kind: "primary", iconName: "wizard", onClick: () => openWizard() }),
      button("刷新", { iconName: "refresh", onClick: () => render(view) }),
    ]),
    guide(
      "看漏斗判断卡在哪一段，再用「下一步行动」推进；需要完整演示时打开「演示向导」。",
      actionText
    )
  );

  if (totalLeads === 0) {
    view.append(
      callout("这是全新的演示环境。先导入示例线索，再按漏斗逐段推进。", "accent", button("去导入", {
        kind: "primary",
        onClick: () => go("#/leads"),
      }))
    );
  }

  view.append(
    card(
      "线索 → 触达 · 全链路",
      "每一段都是当前真实数量，点击可跳到对应工作区。",
      funnel(
        [
          { key: "leads", label: "线索总数", value: totalLeads, tone: "muted" },
          { key: "screened", label: "已评分", value: screened, tone: "info" },
          { key: "pool", label: "已入池", value: overview.pool_size || 0, tone: "ok" },
          { key: "targets", label: "最近任务目标", value: taskTargets, tone: "accent", hint: latestCampaign ? latestCampaign.name : "还没有任务" },
          { key: "success", label: "最近任务成功", value: success, tone: "ok", hint: latestCampaign ? latestCampaign.name : "还没有任务" },
        ],
        (step) => {
          if (step.key === "leads" || step.key === "screened") go("#/leads");
          else if (step.key === "pool") go("#/leads?view=pool");
          else go("#/tasks");
        }
      )
    )
  );

  view.append(
    h("div", { class: "grid two" }, [
      card(
        "下一步行动",
        "按优先级排列，点击按钮直接进入对应操作。",
        h("div", { class: `todo tone-${actionTone}` }, [
          h("div", { class: "todo-copy" }, actionText),
          button(actionLabel, { kind: "primary", onClick: () => go(actionRoute) }),
        ]),
        (overview.leads_by_status || {}).PENDING_REVIEW
          ? h("div", { class: "todo" }, [
              h("div", { class: "todo-copy" }, `另有 ${overview.leads_by_status.PENDING_REVIEW} 条线索等待人工确认。`),
              button("去审核", { onClick: () => go("#/leads") }),
            ])
          : null,
        (overview.campaigns_by_status || {}).RUNNING
          ? h("div", { class: "todo" }, [
              h("div", { class: "todo-copy" }, `${overview.campaigns_by_status.RUNNING} 个任务正在运行。`),
              button("去监控", { onClick: () => go("#/tasks") }),
            ])
          : null,
        batches.total
          ? h("div", { class: "todo" }, [
              h("div", { class: "todo-copy" }, `最近一批：${batches.items[0].imported} 条成功，${batches.items[0].duplicates} 条重复，${batches.items[0].invalid} 条无效。`),
              button("看批次", { onClick: () => go("#/leads") }),
            ])
          : null
      ),
      card(
        "合规健康",
        "这些数字决定哪些人可以被触达。",
        h("div", { class: "kpi-row compact" }, [
          kpi("已授权", (overview.consents_by_status || {}).GRANTED || 0, "同意接收的人数", "ok"),
          kpi("已退订", (overview.suppressions_by_type || {}).UNSUBSCRIBE || 0, "永久不再联系", "danger"),
          kpi("黑名单", (overview.suppressions_by_type || {}).BLACKLIST || 0, "运营手动禁止", "danger"),
        ]),
        h("div", { class: "kv-list" }, [
          h("div", { class: "kv" }, [
            h("span", { class: "kv-label" }, "静默时段"),
            h("span", { class: "kv-value" }, settings && settings["sending.quiet_hours_enabled"]
              ? `${settings["sending.quiet_hours_start"]}–${settings["sending.quiet_hours_end"]}（${settings["sending.quiet_hours_tz"]}）`
              : "未开启"),
          ]),
          h("div", { class: "kv" }, [
            h("span", { class: "kv-label" }, "发送渠道"),
            h("span", { class: "kv-value" }, "Mock 沙箱（不连接真实平台）"),
          ]),
          h("div", { class: "kv" }, [
            h("span", { class: "kv-label" }, "系统状态"),
            h("span", { class: "kv-value" }, health
              ? `数据库${health.db === "ok" ? "正常" : "异常"} · Worker ${health.worker === "disabled" ? "未启用" : "运行中"} · ${health.version}`
              : "健康检查不可用"),
          ]),
        ]),
        h("div", { class: "btn-row" }, [button("去合规中心", { onClick: () => go("#/compliance") })])
      ),
    ])
  );

  const recentCampaigns = campaigns.items.slice(0, 3);
  view.append(
    h("div", { class: "grid two" }, [
      card(
        "最近任务",
        "最新创建的三个任务。",
        recentCampaigns.length
          ? h("div", { class: "task-mini-list" }, recentCampaigns.map((campaign) =>
              h("div", { class: "task-mini" }, [
                h("div", { class: "task-mini-main" }, [
                  h("strong", {}, campaign.name),
                  h("span", { class: "muted" }, `#${campaign.id} · ${fmtTime(campaign.created_at)}`),
                ]),
                badge(TASK_STATUS_LABELS, campaign.status),
                miniBar(campaign.counts || {}),
                button("打开", { onClick: () => go(`#/tasks/${campaign.id}`) }),
              ])
            ))
          : callout("还没有任务。先在线索工作台形成目标池，再创建触达任务。", "muted"),
        h("div", { class: "btn-row" }, [button("全部任务", { onClick: () => go("#/tasks") })])
      ),
      card(
        "最近动态",
        "审计记录里的最近 6 条操作。",
        audits.items.length
          ? h("div", { class: "activity-list" }, audits.items.map((entry) =>
              h("div", { class: "activity" }, [
                h("span", { class: "activity-dot" }),
                h("div", { class: "activity-copy" }, [
                  h("div", {}, [
                    h("strong", {}, (AUDIT_ACTION_LABELS[entry.action] || [entry.action])[0]),
                    h("span", { class: "muted" }, ` · ${entry.actor}`),
                  ]),
                  h("div", { class: "muted" }, `${fmtTime(entry.ts)} · ${(ENTITY_TYPE_LABELS[entry.entity_type] || [entry.entity_type])[0]} ${entry.entity_id}`),
                ]),
                entry.request_id ? chip(entry.request_id.slice(0, 8), "muted", entry.request_id) : null,
              ])
            ))
          : callout("还没有审计记录。导入或审核线索后，这里会出现操作轨迹。", "muted"),
        h("div", { class: "btn-row" }, [button("全部记录", { onClick: () => go("#/records") })])
      ),
    ])
  );
}
