/* 合规中心：授权、黑名单 / 退订、检查链说明与演示沙盒。 */

import { api, demo, errorText } from "../api.js";
import { loadOverview, invalidateOverview } from "../store.js";
import {
  h,
  clear,
  pageHead,
  guide,
  card,
  button,
  badge,
  chip,
  table,
  callout,
  field,
  input,
  select,
  toast,
  toastError,
  confirmDialog,
  fmtTime,
  fmtDate,
} from "../ui.js";
import {
  CONSENT_STATUS_LABELS,
  SUPPRESSION_TYPE_LABELS,
  SOURCE_LABELS,
} from "../labels.js";
import { go } from "../router.js";

const GATES = [
  ["任务有效", "任务处于运行中，且没有取消。"],
  ["黑名单 / 退订", "号码或用户名在禁止联系名单中，立即跳过。"],
  ["号码可用", "必须有可用号码，且格式有效。"],
  ["授权", "必须有同意接收的记录，且未被撤销。"],
  ["模板", "模板必须已审核，变量必须能渲染。"],
  ["去重", "同一任务、同一号码、同一模板只发一次。"],
  ["单收件人频控", "同一号码在窗口内收到足够消息时推迟。"],
  ["静默时段", "处于不打扰时段时推迟到下一窗口。"],
  ["全局频控", "整体发送速度达到上限时推迟。"],
];

let pageView = null;

export async function render(view) {
  pageView = view;
  clear(view);
  view.append(h("div", { class: "loading" }, [h("span", { class: "spinner" }), "正在读取合规数据…"]));
  const [consents, suppressions, settings] = await Promise.all([
    api("/consents"),
    api("/suppressions"),
    api("/settings"),
  ]);

  clear(view);
  view.append(
    pageHead("合规中心", "授权、黑名单、退订与演示沙盒", [
      button("刷新", { iconName: "refresh", onClick: () => render(view) }),
    ]),
    guide(
      "发送前会依次经过 9 道检查；合规相关的三份名单优先于任何任务和配置。运行任务前，先确认授权与名单。",
      "下一步：运行任务前，先确认授权与名单；演示时可用下方沙盒模拟用户退订。"
    )
  );

  view.append(
    card(
      "发送前检查链",
      "固定顺序，首个不放行的检查生效；黑名单与退订永远优先。",
      h("ol", { class: "gate-chain" }, GATES.map(([title, desc], index) =>
        h("li", { class: `gate ${index === 1 || index === 3 ? "gate-compliance" : ""}` }, [
          h("span", { class: "gate-index" }, String(index + 1)),
          h("div", {}, [h("strong", {}, title), h("p", { class: "muted" }, desc)]),
        ])
      )),
      h("div", { class: "chip-row" }, [
        chip(`授权 ${consents.filter((item) => item.status === "GRANTED").length}`, "ok"),
        chip(`退订 ${suppressions.filter((item) => item.type === "UNSUBSCRIBE").length}`, "danger"),
        chip(`黑名单 ${suppressions.filter((item) => item.type === "BLACKLIST").length}`, "danger"),
        settings["sending.quiet_hours_enabled"]
          ? chip(`静默时段 ${settings["sending.quiet_hours_start"]}–${settings["sending.quiet_hours_end"]}`, "warn")
          : chip("静默时段未开启", "muted"),
      ])
    )
  );

  view.append(
    h("div", { class: "grid two" }, [
      consentsCard(consents),
      suppressionsCard(suppressions),
    ])
  );

  view.append(demoCard(true, settings));
}

function consentsCard(consents) {
  const phone = input({ type: "tel", placeholder: "输入号码（E.164，例如国家码开头）" });
  const status = select(
    Object.entries(CONSENT_STATUS_LABELS).map(([code, entry]) => ({ value: code, label: `${entry[0]}（${code}）` })),
    "GRANTED"
  );
  const source = input({ type: "text", placeholder: "来源，例如 web_form" });
  const evidence = input({ type: "text", placeholder: "凭证引用（可选）" });
  async function submit() {
    if (!phone.value.trim()) {
      toast("请先填写号码。", "error");
      return;
    }
    if (!source.value.trim()) {
      toast("请填写授权来源。", "error");
      return;
    }
    try {
      await api("/consents", {
        method: "PUT",
        body: {
          phone: phone.value.trim(),
          status: status.value,
          source: source.value.trim(),
          evidence_ref: evidence.value.trim() || null,
        },
      });
      invalidateOverview();
      toast("授权记录已保存，立即生效。", "success");
      if (pageView) render(pageView);
    } catch (error) {
      toastError(error, "保存授权失败");
    }
  }
  return card(
    "授权名单",
    "没有记录的号码视为未授权，不能发送。",
    h("div", { class: "form-grid" }, [
      field("号码", phone, "按号码登记；保存后只展示脱敏值。"),
      field("状态", status),
      field("来源", source, "例如网页表单、CRM 导入或人工登记。"),
      field("凭证引用", evidence, "可选：表单编号、合同号等。"),
      h("div", { class: "btn-row" }, [button("保存授权", { kind: "primary", onClick: submit })]),
    ]),
    consents.length
      ? table(
          ["号码（脱敏）", "状态", "来源", "凭证", "更新时间", "操作人"],
          consents.map((item) => [
            item.phone_masked,
            badge(CONSENT_STATUS_LABELS, item.status),
            (SOURCE_LABELS[item.source] || [item.source])[0],
            item.evidence_ref || "—",
            fmtTime(item.updated_at),
            item.updated_by,
          ])
        )
      : callout("暂无授权记录。导入示例线索时会带少量授权数据；也可以在上方手动登记。", "muted")
  );
}

function suppressionsCard(suppressions) {
  const type = select(
    Object.entries(SUPPRESSION_TYPE_LABELS).map(([code, entry]) => ({ value: code, label: `${entry[0]}（${code}）` })),
    "BLACKLIST"
  );
  const phone = input({ type: "tel", placeholder: "号码（与用户名二选一）" });
  const username = input({ type: "text", placeholder: "用户名（与号码二选一）" });
  const reason = input({ type: "text", placeholder: "加入原因，例如人工标注" });
  async function submit() {
    if (!phone.value.trim() && !username.value.trim()) {
      toast("号码和用户名至少填写一个。", "error");
      return;
    }
    if (!reason.value.trim()) {
      toast("请填写加入原因。", "error");
      return;
    }
    try {
      await api("/suppressions", {
        method: "POST",
        body: {
          type: type.value,
          phone: phone.value.trim() || null,
          username: username.value.trim() || null,
          reason: reason.value.trim(),
        },
      });
      invalidateOverview();
      toast("名单已更新，立即生效。", "success");
      if (pageView) render(pageView);
    } catch (error) {
      toastError(error, "加入名单失败");
    }
  }
  async function remove(item) {
    if (item.type === "UNSUBSCRIBE") return;
    const ok = await confirmDialog(`确定从黑名单移除 ${item.phone_masked || item.username || `#${item.id}`} 吗？`, {
      danger: true,
      confirmLabel: "移除",
    });
    if (!ok) return;
    try {
      await api(`/suppressions/${item.id}`, { method: "DELETE" });
      invalidateOverview();
      toast("已从黑名单移除。", "success");
      if (pageView) render(pageView);
    } catch (error) {
      toastError(error, "移除失败");
    }
  }
  return card(
    "黑名单与退订",
    "退订记录永久有效、不可删除；黑名单可以人工移除。",
    h("div", { class: "form-grid" }, [
      field("类型", type),
      field("号码", phone, "只展示脱敏值；与用户名二选一。"),
      field("用户名", username),
      field("原因", reason),
      h("div", { class: "btn-row" }, [button("加入名单", { kind: "primary", onClick: submit })]),
    ]),
    suppressions.length
      ? table(
          ["类型", "号码 / 用户名", "原因", "来源", "时间", "操作人", ""],
          suppressions.map((item) => [
            badge(SUPPRESSION_TYPE_LABELS, item.type),
            item.phone_masked || item.username || "—",
            item.reason,
            (SOURCE_LABELS[item.source] || [item.source])[0],
            fmtTime(item.created_at),
            item.created_by,
            item.type === "UNSUBSCRIBE"
              ? button("不可删除", { disabled: true, title: "用户主动退订永久有效，不能删除。" })
              : button("移除", { onClick: () => remove(item) }),
          ])
        )
      : callout("暂无黑名单或退订记录。可以在上方加入，或使用下方演示沙盒模拟用户退订。", "muted")
  );
}

const RESET_LABELS = {
  settings: "设置项",
  keywords: "关键词",
  rate_rules: "频控规则",
  templates: "模板",
  suppressions: "名单",
  consents: "授权记录",
  leads: "线索",
  lead_batches: "导入批次",
  campaigns: "任务",
  campaign_items: "任务明细",
  audit_logs: "审计记录",
  send_logs: "发送日志",
};

function formatResetCounts(counts) {
  const entries = Object.entries(counts || {});
  if (!entries.length) return "数据已恢复初始状态。";
  return entries.map(([key, value]) => `${RESET_LABELS[key] || key} ${value}`).join(" · ");
}

function demoCard(available, settings) {
  if (!available) {
    return callout("演示沙盒未启用（服务端 DEMO_MODE=false）。这不影响正常的合规操作。", "muted");
  }
  const phone = input({ type: "tel", placeholder: "输入要模拟退订的号码（E.164）" });
  const text = input({ type: "text", value: "STOP" });
  const result = h("div", { class: "demo-result" });

  async function inboundStop() {
    if (!phone.value.trim()) {
      toast("请先填写号码。", "error");
      return;
    }
    try {
      const response = await demo("/inbound-stop", {
        method: "POST",
        body: { phone: phone.value.trim(), text: text.value.trim() || "STOP" },
      });
      result.replaceChildren(
        callout(`处理结果：${response.action === "UNSUBSCRIBED" ? "已登记退订，后续处理会跳过这个号码。下一步：回到任务详情点「恢复」，观察这个号码被跳过。" : "文本未命中退订关键词，已忽略。"}`, response.action === "UNSUBSCRIBED" ? "warn" : "muted")
      );
      invalidateOverview();
      toast("模拟退订已处理。", "success");
    } catch (error) {
      toastError(error, "模拟退订失败");
    }
  }

  async function flush() {
    try {
      const response = await demo("/flush-receipts", { method: "POST" });
      result.replaceChildren(callout(`已生成并应用 ${response.applied} 条 Mock 回执。`, "success"));
      toast("回执已生成。", "success");
    } catch (error) {
      toastError(error, "生成回执失败");
    }
  }

  async function reset() {
    const ok = await confirmDialog("将清空当前数据库并恢复初始演示数据。这个操作不可撤销。", {
      danger: true,
      confirmLabel: "重置演示数据",
    });
    if (!ok) return;
    try {
      const response = await demo("/reset", { method: "POST" });
      invalidateOverview();
      toast("演示数据已恢复初始状态。", "success");
      result.replaceChildren(callout(`重置完成：${formatResetCounts(response.counts)}`, "ok"));
    } catch (error) {
      toastError(error, "重置失败");
    }
  }

  return card(
    "演示沙盒",
    "这些按钮只在演示模式可用，不会影响真实平台。",
    h("div", { class: "form-grid" }, [
      field("演示号码", phone, "演示脚本里会给出具体号码；页面不回显完整号码。"),
      field("退订文本", text, "默认 STOP；服务端会按真实入站路径处理。"),
      h("div", { class: "btn-row" }, [
        button("模拟用户退订", { kind: "primary", onClick: inboundStop }),
        button("立即生成送达回执", { onClick: flush }),
        button("重置演示数据", { kind: "danger-ghost", onClick: reset }),
      ]),
    ]),
    result,
    h("p", { class: "muted" }, `退订关键词：${(settings["compliance.stop_keywords"] || []).join("、")}。`)
  );
}
