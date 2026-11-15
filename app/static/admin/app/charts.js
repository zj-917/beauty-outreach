/* 手写图表：漏斗步进条、进度环、评分直方图、成功/失败/跳过迷你条。 */

import { h, svgEl, fmtCount } from "./ui.js";

export function funnel(steps, onStep = null) {
  const max = Math.max(...steps.map((step) => Number(step.value) || 0), 1);
  const base = Number(steps[0] && steps[0].value) || 0;
  return h(
    "div",
    { class: "funnel" },
    steps.map((step, index) => {
      const value = Number(step.value) || 0;
      const width = Math.max((value / max) * 100, value > 0 ? 4 : 0);
      const ratio = index > 0 && base > 0 ? Math.round((value / base) * 100) : null;
      const node = h(
        "button",
        {
          type: "button",
          class: `funnel-step tone-${step.tone || "muted"}`,
          title: step.hint || `${step.label}：${value}`,
          onclick: onStep ? () => onStep(step) : undefined,
          disabled: onStep ? null : true,
        },
        [
          h("span", { class: "funnel-value" }, fmtCount(value)),
          h("span", { class: "funnel-label" }, step.label),
          h("span", { class: "funnel-bar" }, [h("i", { style: `width:${width}%` })]),
          ratio !== null ? h("span", { class: "funnel-ratio" }, `占目标 ${ratio}%`) : null,
        ]
      );
      return node;
    })
  );
}

export function ring(percent, { size = 104, stroke = 9, tone = "ok", label = "", hint = "" } = {}) {
  const value = Math.max(0, Math.min(100, Number(percent) || 0));
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - value / 100);
  const svg = svgEl(
    "svg",
    { viewBox: `0 0 ${size} ${size}`, width: size, height: size, class: `ring tone-${tone}` },
    svgEl("circle", {
      cx: size / 2,
      cy: size / 2,
      r: radius,
      fill: "none",
      "stroke-width": stroke,
      class: "ring-bg",
    }),
    svgEl("circle", {
      cx: size / 2,
      cy: size / 2,
      r: radius,
      fill: "none",
      "stroke-width": stroke,
      "stroke-linecap": "round",
      "stroke-dasharray": String(circumference),
      "stroke-dashoffset": String(offset),
      transform: `rotate(-90 ${size / 2} ${size / 2})`,
      class: "ring-fg",
    })
  );
  return h("div", { class: "ring-wrap", style: `width:${size}px;height:${size}px` }, [
    svg,
    h("div", { class: "ring-label" }, [
      h("strong", {}, label || `${Math.round(value)}%`),
      hint ? h("span", { class: "muted" }, hint) : null,
    ]),
  ]);
}

export function histogram(buckets, thresholds = []) {
  const max = Math.max(...buckets.map((bucket) => Number(bucket.count) || 0), 1);
  const bars = h(
    "div",
    { class: "hist-bars" },
    buckets.map((bucket) => {
      const count = Number(bucket.count) || 0;
      const height = count > 0 ? Math.max((count / max) * 100, 4) : 2;
      return h("div", { class: "hist-col", title: `${bucket.label} 分：${count} 条` }, [
        h("span", { class: "hist-count" }, count > 0 ? String(count) : ""),
        h("span", { class: "hist-bar", style: `height:${height}%` }),
        h("span", { class: "hist-label" }, bucket.label),
      ]);
    })
  );
  return h("div", { class: "histogram" }, [
    h(
      "div",
      { class: "hist-plot" },
      thresholds.map((threshold) =>
        h(
          "span",
          {
            class: `hist-threshold tone-${threshold.tone || "muted"}`,
            style: `left:${Math.max(0, Math.min(100, Number(threshold.value) || 0))}%`,
            title: threshold.label,
          },
          [h("i", {}), h("em", {}, threshold.label)]
        )
      )
    ),
    bars,
  ]);
}

export function miniBar({ success = 0, failed = 0, skipped = 0, total = 0 } = {}) {
  const sum = Math.max(total || success + failed + skipped, 1);
  return h(
    "div",
    { class: "mini-bar", title: `成功 ${success} · 失败 ${failed} · 跳过 ${skipped}` },
    [
      success > 0 ? h("i", { class: "tone-ok", style: `flex-grow:${success / sum}` }) : null,
      failed > 0 ? h("i", { class: "tone-danger", style: `flex-grow:${failed / sum}` }) : null,
      skipped > 0 ? h("i", { class: "tone-muted", style: `flex-grow:${skipped / sum}` }) : null,
    ]
  );
}

export function legend(items) {
  return h(
    "div",
    { class: "legend" },
    items.map((item) => h("span", { class: "legend-item" }, [h("i", { class: `tone-${item.tone}` }), item.label]))
  );
}
