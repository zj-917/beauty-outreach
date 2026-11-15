/* 配置：消息模板、关键词、频控规则、系统参数。 */

import { api, errorText } from "../api.js";
import {
  h,
  clear,
  pageHead,
  guide,
  card,
  tabs,
  button,
  badge,
  chip,
  table,
  callout,
  openModal,
  confirmDialog,
  field,
  input,
  textarea,
  checkbox,
  select,
  toast,
  toastError,
  fmtTime,
  text,
} from "../ui.js";
import {
  TEMPLATE_STATUS_LABELS,
  KEYWORD_KIND_LABELS,
  RATE_SCOPE_LABELS,
  SETTING_LABELS,
  SETTING_GROUPS,
  TEMPLATE_VARIABLES,
} from "../labels.js";
import { go } from "../router.js";

const TABS = [
  { key: "templates", label: "消息模板" },
  { key: "keywords", label: "关键词" },
  { key: "rates", label: "频控规则" },
  { key: "settings", label: "系统参数" },
];

let pageView = null;
let pageParams = null;

export async function render(view, params) {
  pageView = view;
  pageParams = params;
  const tab = params.get("tab") || "templates";
  clear(view);
  view.append(h("div", { class: "loading" }, [h("span", { class: "spinner" }), "正在读取配置…"]));
  const [templates, keywords, rules, settings] = await Promise.all([
    api("/templates"),
    api("/keywords"),
    api("/rate-rules"),
    api("/settings"),
  ]);

  clear(view);
  view.append(
    pageHead("配置", "模板、关键词、频控规则与系统参数", [
      button("刷新", { iconName: "refresh", onClick: () => refresh(tab) }),
    ]),
    guide(
      "改动会立即生效。模板要先审核通过才能用于任务；频控规则不能全部关闭；系统参数按组保存。",
      tab === "templates" ? "下一步：新建或审核一条模板，再到任务页创建任务。" : "下一步：按需调整，保存后立即生效。"
    ),
    tabs(TABS, tab, (key) => go(`#/settings?tab=${key}`))
  );

  if (tab === "templates") view.append(templatesView(templates));
  else if (tab === "keywords") view.append(keywordsView(keywords));
  else if (tab === "rates") view.append(ratesView(rules));
  else view.append(settingsView(settings));
}

function refresh(tab = "templates") {
  if (pageView) render(pageView, new URLSearchParams({ tab })).catch((error) => toastError(error));
}

/* ---------- 模板 ---------- */

function templatesView(templates) {
  const groups = new Map();
  for (const template of templates) {
    if (!groups.has(template.name)) groups.set(template.name, []);
    groups.get(template.name).push(template);
  }
  const cards = [];
  for (const [name, versions] of groups) {
    versions.sort((a, b) => b.version - a.version);
    cards.push(
      h("section", { class: "tpl-group" }, [
        h("div", { class: "tpl-group-head" }, [
          h("h3", {}, name),
          h("span", { class: "muted" }, `${versions.length} 个版本`),
        ]),
        ...versions.map((template) =>
          h("div", { class: "tpl-row" }, [
            h("div", { class: "tpl-row-head" }, [
              h("strong", {}, `v${template.version}`),
              badge(TEMPLATE_STATUS_LABELS, template.status),
              chip(template.language, "muted"),
              h("span", { class: "muted" }, fmtTime(template.created_at)),
            ]),
            h("p", { class: "tpl-body" }, template.body.length > 160 ? `${template.body.slice(0, 160)}…` : template.body),
            h("div", { class: "btn-row" }, [
              template.status === "DRAFT"
                ? button("编辑正文", { onClick: () => editTemplate(template) })
                : null,
              template.status === "DRAFT"
                ? button("审核通过", { kind: "primary", onClick: () => approveTemplate(template) })
                : null,
              template.status === "APPROVED"
                ? button("创建新版本", { onClick: () => newVersion(template) })
                : null,
              button("预览渲染", { onClick: () => previewTemplate(template) }),
              template.status !== "DISABLED"
                ? button("停用", { kind: "danger-ghost", onClick: () => disableTemplate(template) })
                : null,
            ]),
          ])
        ),
      ])
    );
  }
  return card(
    "消息模板",
    "生命周期：新建 → 草稿 → 审核通过 → 可用于任务；已审核正文不能直接改，需要创建新版本。",
    h("div", { class: "btn-row" }, [button("新建模板", { kind: "primary", iconName: "plus", onClick: newTemplate })]),
    cards.length ? h("div", { class: "tpl-list" }, cards) : callout("暂无模板。新建后会先进入草稿，审核通过后才能用于任务。", "muted")
  );
}

function templateEditor({ title, name = "", language = "en", body = "", submitLabel, onSubmit }) {
  const nameInput = input({ type: "text", value: name, placeholder: "例如：首轮问候" });
  const languageInput = input({ type: "text", value: language, placeholder: "例如 en / zh" });
  const bodyInput = textarea({ value: body, rows: 8, placeholder: "支持变量：{{name}}、{{username}}、{{keyword}}、{{brand}}、{{optout_text}}" });
  const count = h("span", { class: "muted" }, `${body.length} / 800`);
  bodyInput.addEventListener("input", () => {
    count.textContent = `${bodyInput.value.length} / 800`;
  });
  const variables = h("div", { class: "chip-row" }, TEMPLATE_VARIABLES.map((item) =>
    chip(item.label, "muted", `{{${item.code}}}：${item.desc}`)
  ));
  const errorHost = h("div", {});
  const modal = openModal(
    title,
    h("div", {}, [
      field("模板名称", nameInput, "同一个名称下的不同版本共用名称。"),
      field("语言", languageInput, "例如 en、zh。"),
      field("正文", bodyInput, "最多 800 字符；发送时会自动追加退订提示。"),
      count,
      variables,
      errorHost,
      h("div", { class: "btn-row end" }, [
        button("取消", { onClick: () => modal.close() }),
        button(submitLabel, { kind: "primary", onClick: async () => {
          errorHost.replaceChildren();
          try {
            await onSubmit({
              name: nameInput.value.trim(),
              language: languageInput.value.trim(),
              body: bodyInput.value,
            });
            modal.close();
            refresh("templates");
          } catch (error) {
            errorHost.replaceChildren(callout(`保存失败：${errorText(error)}`, "danger"));
          }
        } }),
      ]),
    ]),
    { width: 680 }
  );
}

function newTemplate() {
  templateEditor({
    title: "新建消息模板",
    submitLabel: "创建草稿",
    onSubmit: async (values) => {
      await api("/templates", { method: "POST", body: values });
      toast("模板已创建为草稿。审核通过后才能用于任务。", "success");
    },
  });
}

function editTemplate(template) {
  templateEditor({
    title: `编辑模板 ${template.name} v${template.version}`,
    name: template.name,
    language: template.language,
    body: template.body,
    submitLabel: "保存草稿",
    onSubmit: async (values) => {
      await api(`/templates/${template.id}`, { method: "PATCH", body: { body: values.body, language: values.language } });
      toast("模板草稿已保存。", "success");
    },
  });
}

function newVersion(template) {
  const bodyInput = textarea({ value: template.body, rows: 8 });
  const errorHost = h("div", {});
  const modal = openModal(
    `创建 ${template.name} 的新版本`,
    h("div", {}, [
      callout("已审核或已停用的模板不能直接修改正文；新版本会从草稿开始，需要重新审核。", "accent"),
      field("新版本正文", bodyInput, "最多 800 字符。"),
      errorHost,
      h("div", { class: "btn-row end" }, [
        button("取消", { onClick: () => modal.close() }),
        button("创建新版本", { kind: "primary", onClick: async () => {
          try {
            await api(`/templates/${template.id}/new-version`, { method: "POST", body: { body: bodyInput.value } });
            modal.close();
            toast("新版本已创建为草稿。", "success");
            refresh("templates");
          } catch (error) {
            errorHost.replaceChildren(callout(`创建失败：${errorText(error)}`, "danger"));
          }
        } }),
      ]),
    ]),
    { width: 620 }
  );
}

async function approveTemplate(template) {
  try {
    await api(`/templates/${template.id}/approve`, { method: "POST" });
    toast("模板已审核通过，可以用于任务。", "success");
    refresh("templates");
  } catch (error) {
    toastError(error, "审核失败");
  }
}

async function disableTemplate(template) {
  const ok = await confirmDialog("停用后，这个模板不再用于新任务；已创建的任务不受影响。", { confirmLabel: "停用" });
  if (!ok) return;
  try {
    await api(`/templates/${template.id}/disable`, { method: "POST" });
    toast("模板已停用。", "success");
    refresh("templates");
  } catch (error) {
    toastError(error, "停用失败");
  }
}

async function previewTemplate(template) {
  try {
    const result = await api("/templates/preview", { method: "POST", body: { template_id: template.id } });
    openModal(
      `预览 · ${template.name} v${template.version}`,
      h("div", {}, [
        h("p", { class: "muted" }, "使用内置示例线索渲染，不会发送。"),
        h("pre", { class: "render-preview" }, result.rendered),
      ]),
      { width: 560 }
    );
  } catch (error) {
    toastError(error, "预览失败");
  }
}

/* ---------- 关键词 ---------- */

function keywordsView(keywords) {
  const term = input({ type: "text", placeholder: "例如 skincare" });
  const kind = select(
    Object.entries(KEYWORD_KIND_LABELS).map(([code, entry]) => ({ value: code, label: `${entry[0]}（${code}）` })),
    "POSITIVE"
  );
  const weight = input({ type: "number", value: "10", min: 0, max: 100 });
  const enabled = checkbox("立即启用", true);
  async function add() {
    if (!term.value.trim()) {
      toast("请填写关键词。", "error");
      return;
    }
    try {
      await api("/keywords", {
        method: "POST",
        body: {
          term: term.value.trim(),
          kind: kind.value,
          weight: Number(weight.value || 0),
          enabled: enabled.querySelector("input").checked,
        },
      });
      toast("关键词已添加。", "success");
      refresh("keywords");
    } catch (error) {
      toastError(error, "添加失败");
    }
  }
  async function update(item, patch) {
    try {
      await api(`/keywords/${item.id}`, { method: "PATCH", body: patch });
      toast("关键词已更新。", "success");
      refresh("keywords");
    } catch (error) {
      toastError(error, "更新失败");
    }
  }
  async function remove(item) {
    const ok = await confirmDialog(`确定删除关键词「${item.term}」吗？`, { danger: true, confirmLabel: "删除" });
    if (!ok) return;
    try {
      await api(`/keywords/${item.id}`, { method: "DELETE" });
      toast("关键词已删除。", "success");
      refresh("keywords");
    } catch (error) {
      toastError(error, "删除失败");
    }
  }
  return card(
    "关键词",
    "正向词加分，负向词减分；关键词本身修改后不能改名，需要删除后重新添加。",
    h("div", { class: "form-grid" }, [
      field("关键词", term, "英文或中文词，例如 skincare。"),
      field("类型", kind),
      field("权重", weight, "命中后加减的分数。"),
      enabled,
      h("div", { class: "btn-row" }, [button("添加关键词", { kind: "primary", onClick: add })]),
    ]),
    keywords.length
      ? table(
          ["关键词", "类型", "权重", "状态", "更新时间", "操作"],
          keywords.map((item) => [
            h("strong", {}, item.term),
            badge(KEYWORD_KIND_LABELS, item.kind),
            weightCell(item, update),
            enabledCell(item, update),
            fmtTime(item.updated_at),
            button("删除", { kind: "danger-ghost", onClick: () => remove(item) }),
          ])
        )
      : callout("暂无关键词。可以新增一个，或重置演示数据恢复默认配置。", "muted")
  );
}

function weightCell(item, update) {
  const node = input({ type: "number", value: String(item.weight), min: 0, max: 100 });
  node.classList.add("inline-number");
  return h("div", { class: "inline-edit" }, [
    node,
    button("保存", { onClick: () => update(item, { weight: Number(node.value || 0) }) }),
  ]);
}

function enabledCell(item, update) {
  const box = h("input", { type: "checkbox", checked: item.enabled });
  box.addEventListener("change", () => update(item, { enabled: box.checked }));
  return h("label", { class: "check" }, [box, h("span", {}, item.enabled ? "启用" : "停用")]);
}

/* ---------- 频控规则 ---------- */

function ratesView(rules) {
  const name = input({ type: "text", placeholder: "例如：全局 5 次 / 10 秒" });
  const scope = select(
    Object.entries(RATE_SCOPE_LABELS).map(([code, entry]) => ({ value: code, label: `${entry[0]}（${code}）` })),
    "GLOBAL"
  );
  const windowSeconds = input({ type: "number", value: "10", min: 1 });
  const maxCount = input({ type: "number", value: "5", min: 1 });
  const enabled = checkbox("立即启用", true);
  async function add() {
    if (!name.value.trim()) {
      toast("请填写规则名称。", "error");
      return;
    }
    try {
      await api("/rate-rules", {
        method: "POST",
        body: {
          name: name.value.trim(),
          scope: scope.value,
          window_seconds: Number(windowSeconds.value || 1),
          max_count: Number(maxCount.value || 1),
          enabled: enabled.querySelector("input").checked,
        },
      });
      toast("频控规则已添加。", "success");
      refresh("rates");
    } catch (error) {
      toastError(error, "添加失败");
    }
  }
  async function toggle(item) {
    try {
      await api(`/rate-rules/${item.id}`, { method: "PATCH", body: { enabled: !item.enabled } });
      toast(item.enabled ? "规则已停用。" : "规则已启用。", "success");
      refresh("rates");
    } catch (error) {
      toastError(error, "更新失败");
    }
  }
  async function remove(item) {
    const ok = await confirmDialog(`确定删除频控规则「${item.name}」吗？`, { danger: true, confirmLabel: "删除" });
    if (!ok) return;
    try {
      await api(`/rate-rules/${item.id}`, { method: "DELETE" });
      toast("频控规则已删除。", "success");
      refresh("rates");
    } catch (error) {
      toastError(error, "删除失败");
    }
  }
  return card(
    "频控规则",
    "所有启用规则同时生效，取最严限制；必须至少保留一条启用的全局规则和一条启用的单收件人规则。",
    h("div", { class: "form-grid" }, [
      field("规则名称", name),
      field("范围", scope),
      field("窗口（秒）", windowSeconds),
      field("窗口内最多条数", maxCount),
      enabled,
      h("div", { class: "btn-row" }, [button("添加规则", { kind: "primary", onClick: add })]),
    ]),
    rules.length
      ? h("div", { class: "rate-list" }, rules.map((item) =>
          h("div", { class: "rate-card" }, [
            h("div", {}, [
              h("strong", {}, item.name),
              h("p", { class: "muted" }, `${(RATE_SCOPE_LABELS[item.scope] || [item.scope])[0]} · 每 ${item.window_seconds} 秒最多 ${item.max_count} 条`),
            ]),
            chip(item.enabled ? "启用" : "停用", item.enabled ? "ok" : "muted"),
            h("div", { class: "btn-row" }, [
              button(item.enabled ? "停用" : "启用", { onClick: () => toggle(item) }),
              button("删除", { kind: "danger-ghost", onClick: () => remove(item) }),
            ]),
          ])
        ))
      : callout("暂无频控规则。系统要求至少保留一条全局规则和一条单收件人规则。", "warn")
  );
}

/* ---------- 系统参数 ---------- */

function settingsView(settings) {
  return h("div", { class: "settings-groups" }, SETTING_GROUPS.map((group) => {
    const keys = Object.keys(SETTING_LABELS).filter((key) => key.startsWith(group.prefix));
    const controls = {};
    const rows = keys.map((key) => {
      const current = settings[key];
      const label = SETTING_LABELS[key] || [key, ""];
      let control;
      if (typeof current === "boolean") {
        control = h("input", { type: "checkbox", checked: current });
      } else if (typeof current === "number") {
        control = input({ type: "number", value: String(current), step: Number.isInteger(current) ? "1" : "0.1" });
      } else if (Array.isArray(current)) {
        control = input({ type: "text", value: current.join(", ") });
      } else {
        control = input({ type: "text", value: current === null || current === undefined ? "" : String(current) });
      }
      controls[key] = control;
      return h("div", { class: "setting-row" }, [
        h("div", { class: "setting-copy" }, [
          h("strong", {}, label[0]),
          h("p", { class: "muted" }, label[1]),
          h("span", { class: "setting-key mono" }, key),
        ]),
        h("div", { class: "setting-control" }, [control]),
      ]);
    });
    const errorHost = h("div", {});
    async function save() {
      errorHost.replaceChildren();
      const patch = {};
      for (const key of keys) {
        const current = settings[key];
        const control = controls[key];
        if (typeof current === "boolean") patch[key] = control.checked;
        else if (typeof current === "number") patch[key] = Number(control.value);
        else if (Array.isArray(current)) patch[key] = splitList(control.value, key);
        else patch[key] = control.value;
      }
      try {
        await api("/settings", { method: "PUT", body: patch });
        toast(`${group.label}已保存，立即生效。`, "success");
        refresh("settings");
      } catch (error) {
        const details = error.details && error.details.errors ? error.details.errors : null;
        errorHost.replaceChildren(
          callout(`保存失败：${errorText(error)}`, "danger"),
          details
            ? h("ul", { class: "error-list" }, Object.entries(details).map(([key, message]) =>
                h("li", {}, `${key === "cross_field" ? "跨字段校验" : (SETTING_LABELS[key] || [key])[0]}：${message}`)
              ))
            : null
        );
      }
    }
    return h("section", { class: "card settings-card" }, [
      h("div", { class: "card-head" }, [
        h("div", {}, [h("h3", {}, group.label), h("p", { class: "card-sub" }, group.desc)]),
      ]),
      h("div", { class: "card-body" }, [
        ...rows,
        errorHost,
        h("div", { class: "btn-row" }, [button("保存本组", { kind: "primary", onClick: save })]),
      ]),
    ]);
  }));
}

function splitList(value, key) {
  const parts = String(value || "")
    .split(/[,，\s]+/)
    .map((item) => item.trim())
    .filter(Boolean);
  if (key === "screening.allowed_regions") return parts.map((item) => item.toUpperCase());
  if (key === "screening.allowed_languages") return parts.map((item) => item.toLowerCase());
  return parts;
}
