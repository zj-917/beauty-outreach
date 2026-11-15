"""Static usability checks for the admin UI (AC-UI-012 ~ AC-UI-014)."""

from __future__ import annotations

import re
from pathlib import Path

ADMIN_DIR = Path(__file__).resolve().parents[2] / "app" / "static" / "admin"
APP_DIR = ADMIN_DIR / "app"
INDEX_HTML = ADMIN_DIR / "index.html"
LABELS_JS = APP_DIR / "labels.js"

CJK_RE = re.compile(r"[一-鿿]")
ENTRY_RE = re.compile(
    r'^\s*"?([A-Za-z0-9_.]+)"?\s*:\s*[\["]\s*"([^"]+)"\s*,\s*"([^"]+)"'
)

LEAD_STATUSES = ["NEW", "PENDING_REVIEW", "APPROVED", "REJECTED", "DISCARDED"]
READINESS_VALUES = [
    "READY",
    "BLACKLISTED",
    "UNSUBSCRIBED",
    "NO_PHONE",
    "NO_CONSENT",
    "CONSENT_REVOKED",
]
TASK_STATUSES = ["DRAFT", "RUNNING", "PAUSED", "COMPLETED", "CANCELLED"]
ITEM_STATUSES = [
    "PENDING",
    "SENDING",
    "RETRY_WAIT",
    "SENT",
    "DELIVERED",
    "READ",
    "FAILED",
    "SKIPPED",
]
REASON_CODES = [
    "BLACKLISTED",
    "UNSUBSCRIBED",
    "NO_PHONE",
    "INVALID_PHONE",
    "NO_CONSENT",
    "CONSENT_REVOKED",
    "TEMPLATE_NOT_APPROVED",
    "TEMPLATE_VARIABLE_MISSING",
    "RENDER_TOO_LONG",
    "ALREADY_CONTACTED",
    "RECIPIENT_RATE_LIMITED",
    "TASK_CANCELLED",
    "MAX_ATTEMPTS_EXCEEDED",
    "INVALID_NUMBER",
    "NOT_WHATSAPP_USER",
    "TEMPLATE_REJECTED",
    "AUTH_ERROR",
    "DELIVERY_FAILED",
    "RATE_LIMIT_GLOBAL",
    "QUIET_HOURS",
    "TIMEOUT",
    "NETWORK_ERROR",
    "SERVER_ERROR",
    "RATE_LIMITED",
]
SCORE_REASON_CODES = [
    "KW_POS",
    "KW_NEG",
    "REGION_MATCH",
    "REGION_MISMATCH",
    "LANG_MATCH",
    "LANG_MISMATCH",
    "BIO_TOO_SHORT",
    "CLAMP",
]
TEMPLATE_STATUSES = ["DRAFT", "APPROVED", "DISABLED"]
SUPPRESSION_TYPES = ["BLACKLIST", "UNSUBSCRIBE"]
CONSENT_STATUSES = ["GRANTED", "REVOKED"]
SOURCE_VALUES = [
    "web_form",
    "crm_import",
    "csv_import",
    "mock",
    "seed",
    "IMPORT",
    "MANUAL",
    "manual",
    "INBOUND_STOP",
    "inbound_stop",
]
KEYWORD_KINDS = ["POSITIVE", "NEGATIVE"]
RATE_SCOPES = ["GLOBAL", "PER_RECIPIENT"]
LOG_PHASES = ["GATE", "PROVIDER", "RECEIPT"]
LOG_OUTCOMES = [
    "BLOCKED",
    "DEFERRED",
    "ACCEPTED",
    "RETRYABLE_ERROR",
    "PERMANENT_ERROR",
    "DELIVERED",
    "READ",
    "DELIVERY_FAILED",
]
ENTITY_TYPES = [
    "lead",
    "lead_batch",
    "campaign",
    "keyword",
    "rate_rule",
    "template",
    "contact_consent",
    "suppression",
    "system_setting",
]
AUDIT_ACTIONS = [
    "LEAD_BATCH_IMPORTED",
    "LEAD_SCREENING_RUN",
    "LEAD_REVIEWED",
    "KEYWORD_CREATED",
    "KEYWORD_UPDATED",
    "KEYWORD_DELETED",
    "SETTING_UPDATED",
    "RATE_RULE_CREATED",
    "RATE_RULE_UPDATED",
    "RATE_RULE_DELETED",
    "TEMPLATE_CREATED",
    "TEMPLATE_UPDATED",
    "TEMPLATE_VERSIONED",
    "TEMPLATE_APPROVED",
    "TEMPLATE_DISABLED",
    "CONSENT_UPSERTED",
    "SUPPRESSION_ADDED",
    "SUPPRESSION_REMOVED",
    "INBOUND_STOP_PROCESSED",
    "CAMPAIGN_CREATED",
    "CAMPAIGN_STARTED",
    "CAMPAIGN_PAUSED",
    "CAMPAIGN_RESUMED",
    "CAMPAIGN_CANCELLED",
    "CAMPAIGN_COMPLETED",
    "CAMPAIGN_CIRCUIT_OPENED",
]
SETTING_KEYS = [
    "screening.auto_approve_enabled",
    "screening.threshold_high",
    "screening.threshold_low",
    "screening.allowed_regions",
    "screening.allowed_languages",
    "screening.region_bonus",
    "screening.region_penalty",
    "screening.language_bonus",
    "screening.language_penalty",
    "screening.short_bio_min_len",
    "screening.short_bio_penalty",
    "sending.max_attempts",
    "sending.backoff_base_seconds",
    "sending.backoff_cap_seconds",
    "sending.backoff_jitter",
    "sending.claim_batch_size",
    "sending.lease_seconds",
    "sending.provider_timeout_seconds",
    "sending.circuit_breaker_threshold",
    "sending.quiet_hours_enabled",
    "sending.quiet_hours_start",
    "sending.quiet_hours_end",
    "sending.quiet_hours_tz",
    "message.brand",
    "message.optout_text",
    "compliance.stop_keywords",
]
PAGE_MODULES = [
    "dashboard.js",
    "leads.js",
    "tasks.js",
    "task-detail.js",
    "compliance.js",
    "records.js",
    "settings.js",
]


def read_js() -> str:
    """Return every admin ES module concatenated in path order."""
    return "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(APP_DIR.rglob("*.js"))
    )


def read_html() -> str:
    """Return the admin page source."""
    return INDEX_HTML.read_text(encoding="utf-8")


def parse_dict(source: str, name: str) -> dict[str, tuple[str, str]]:
    """Parse a ``const NAME = { CODE: ["中文", "释义"], ... }`` block."""
    match = re.search(rf"const {name} = \{{(.*?)\n\}};", source, re.S)
    assert match is not None, f"{name} dictionary not found"
    entries: dict[str, tuple[str, str]] = {}
    for line in match.group(1).splitlines():
        item = ENTRY_RE.match(line)
        if item:
            entries[item.group(1)] = (item.group(2), item.group(3))
    assert entries, f"{name} dictionary has no parsable entries"
    return entries


def assert_labels(entries: dict[str, tuple[str, str]], codes: list[str]) -> None:
    """Every code has a Chinese name and a Chinese description."""
    missing = [code for code in codes if code not in entries]
    assert not missing, f"missing Chinese labels for: {missing}"
    for code in codes:
        name, description = entries[code]
        assert CJK_RE.search(name), f"{code} name is not Chinese: {name!r}"
        assert CJK_RE.search(description), (
            f"{code} description is not Chinese: {description!r}"
        )


def test_AC_UI_012_all_enum_values_have_chinese_labels() -> None:
    """Given the admin labels module, when scanned, then every enum has Chinese copy."""
    source = LABELS_JS.read_text(encoding="utf-8")
    expected = {
        "LEAD_STATUS_LABELS": LEAD_STATUSES,
        "READINESS_LABELS": READINESS_VALUES,
        "TASK_STATUS_LABELS": TASK_STATUSES,
        "ITEM_STATUS_LABELS": ITEM_STATUSES,
        "REASON_LABELS": REASON_CODES,
        "SCORE_REASON_LABELS": SCORE_REASON_CODES,
        "TEMPLATE_STATUS_LABELS": TEMPLATE_STATUSES,
        "SUPPRESSION_TYPE_LABELS": SUPPRESSION_TYPES,
        "CONSENT_STATUS_LABELS": CONSENT_STATUSES,
        "SOURCE_LABELS": SOURCE_VALUES,
        "KEYWORD_KIND_LABELS": KEYWORD_KINDS,
        "RATE_SCOPE_LABELS": RATE_SCOPES,
        "PHASE_LABELS": LOG_PHASES,
        "OUTCOME_LABELS": LOG_OUTCOMES,
        "ENTITY_TYPE_LABELS": ENTITY_TYPES,
        "AUDIT_ACTION_LABELS": AUDIT_ACTIONS,
        "SETTING_LABELS": SETTING_KEYS,
    }
    for name, codes in expected.items():
        assert_labels(parse_dict(source, name), codes)


def test_AC_UI_012_no_raw_english_interface_labels() -> None:
    """Given the admin sources, when scanned, then English keys are not bare labels."""
    source = read_js() + "\n" + read_html()
    for pattern in [
        ">Admin Token<",
        ">actor<",
        ">action<",
        ">entity_type<",
        ">entity_id<",
        ">task_id<",
        ">item_id<",
        ">phase<",
        ">outcome<",
        ">reason_code<",
        ">term<",
    ]:
        assert pattern not in source, f"untranslated label remains: {pattern}"
    for required in [
        "访问口令",
        "操作人",
        "任务编号",
        "明细编号",
        "阶段",
        "结果",
        "原因代码",
        "关键词",
    ]:
        assert required in source, f"missing Chinese label: {required}"


def test_AC_UI_013_every_page_has_guide_and_next_step() -> None:
    """Given the page modules, then each page offers a guide and a next step."""
    source = read_js()
    assert "本页要做什么" in source
    for module in PAGE_MODULES:
        module_source = (APP_DIR / "pages" / module).read_text(encoding="utf-8")
        assert "guide(" in module_source, f"{module} has no guide block"
        assert "下一步" in module_source, f"{module} has no next-step copy"
    for hint in [
        "下一步：点「自动筛选」",
        "下一步：到「任务」用目标池创建触达任务",
        "下一步：点「打开任务详情」",
        "下一步：回到任务详情点「恢复」",
    ]:
        assert hint in source, f"missing next-step hint: {hint}"


def test_AC_UI_014_task_status_guidance_covers_all_states() -> None:
    """Given task detail, when rendered, then each state explains what to do."""
    source = LABELS_JS.read_text(encoding="utf-8")
    guide = parse_dict(source, "TASK_STATUS_GUIDE")
    assert_labels(guide, TASK_STATUSES)
    for status in TASK_STATUSES:
        _, next_step = guide[status]
        assert "下一步" in next_step, f"{status} guidance misses next step"
    detail = (APP_DIR / "pages" / "task-detail.js").read_text(encoding="utf-8")
    assert "TASK_STATUS_GUIDE" in detail
    assert "status-actions" in detail
    assert "ACTION_DISABLED_REASON" in detail
