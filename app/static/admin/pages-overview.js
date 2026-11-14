"use strict";

/* 概览页：全局计数与状态分布。 */

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
