# 模块规格：config & stats（配置管理与结果统计）

> 版本 v1.0 · 状态 定稿（2026-11-13 冻结） · 依赖：audit、`core/config`

## 1. 目标

- **config**：让运营在不改代码的情况下管理关键词、频控规则与运行期设置；配置变更可审计、可即时生效；保证关键合规配置不被误关。
- **stats**：给出任务与全局的**可信、一致**的结果统计。

## 2. 范围与非目标
- **范围**：关键词 / 频控规则 CRUD、设置注册表与校验、默认种子、环境变量启动校验、任务与全局统计。
- **非目标**：配置版本回滚、配置导入导出、多环境配置中心。

## 3. 设置注册表（`system_setting`）

`PUT /settings` 仅接受下表中的键，值按类型与范围校验；未知键 → 422。

| key | 类型 | 默认 | 校验 | 使用方 |
|---|---|---|---|---|
| `screening.auto_approve_enabled` | bool | `true` | | screening |
| `screening.threshold_high` | int | `70` | 1–100，且 > low | screening |
| `screening.threshold_low` | int | `40` | 0–99，且 < high | screening |
| `screening.allowed_regions` | list[str] | `["US","GB","CA","AU","SG","MY","HK","TW"]` | 大写 alpha-2；`[]` = 不评地区 | screening |
| `screening.allowed_languages` | list[str] | `["en","zh"]` | 小写 2–3 位字母；`[]` = 不评语言 | screening |
| `screening.region_bonus` / `region_penalty` | int | `10` / `20` | 0–50 | screening |
| `screening.language_bonus` / `language_penalty` | int | `5` / `10` | 0–50 | screening |
| `screening.short_bio_min_len` / `short_bio_penalty` | int | `10` / `10` | 0–200 / 0–50 | screening |
| `sending.max_attempts` | int | `3` | 1–10 | engine |
| `sending.backoff_base_seconds` | float | `2` | 0.1–3600 | engine |
| `sending.backoff_cap_seconds` | float | `60` | ≥ base，≤ 86400 | engine |
| `sending.backoff_jitter` | float | `0.2` | 0–0.5 | engine |
| `sending.claim_batch_size` | int | `10` | 1–100 | engine |
| `sending.lease_seconds` | int | `60` | 5–3600 | engine |
| `sending.provider_timeout_seconds` | float | `10` | 0.5–120 | engine |
| `sending.circuit_breaker_threshold` | int | `5` | 1–100 | engine |
| `sending.quiet_hours_enabled` | bool | `false` | | compliance |
| `sending.quiet_hours_start` / `end` | str `HH:MM` | `22:00` / `08:00` | 合法时间；start ≠ end | compliance |
| `sending.quiet_hours_tz` | str | `UTC` | 合法 IANA 时区 | compliance |
| `message.brand` | str | `GlowLab` | 1–40 字符 | template |
| `message.optout_text` | str | `Reply STOP to unsubscribe. 回复 STOP 退订。` | 1–160 字符 | template |
| `compliance.stop_keywords` | list[str] | `["stop","unsubscribe","cancel","end","quit","退订","取消订阅"]` | 非空，每项 1–20 字符 | compliance |

> 阈值联动校验：更新 `threshold_high/low` 时，用**更新后的合并值**校验 `low < high`。

## 4. 关键词（`keyword`）

- `POST /keywords {term, kind, weight, enabled}`：`term` 规范化后（NFKC、casefold、去空白）存储，`(term, kind)` 唯一（冲突 409）；`weight` 1–50；`term` 1–60 字符；启用的关键词总数 ≤ 500。
- `PATCH` 可改 `weight` / `enabled`（改 `term` 视为新建）；`DELETE` 物理删除。均写审计。

## 5. 频控规则（`rate_rule`）

- `POST /rate-rules {name, scope, window_seconds, max_count, enabled}`：`scope ∈ {GLOBAL, PER_RECIPIENT}`；`window_seconds ≥ 1`、`max_count ≥ 1`。
- 多条启用规则**同时生效，取最严**。
- **红线 R-7 / INV-10**：任何时刻必须至少有一条**启用的 GLOBAL** 与一条**启用的 PER_RECIPIENT** 规则。会使其不成立的 `DELETE` / `PATCH(enabled=false 或 scope 改变)` → 422 `CFG_LAST_RATE_RULE`。

## 6. 生效策略与种子

- **实时生效（D-7）**：引擎在每次处理明细时读取频控规则与 `sending.*` 设置（不跨 tick 缓存），因此运营在任务运行中修改限制，下一条明细即按新值执行。模板与目标仍是任务创建时的快照。
- **种子**（`scripts/seed.py`；或 `SEED_DEFAULTS=true` 且库为空时启动自动执行）：§3 默认设置；`screening.md` §6 的关键词；频控规则 `global_default`（GLOBAL 5/10s）与 `per_recipient_default`（PER_RECIPIENT 1/86400s）；模板 `greeting_v1`（APPROVED）。种子幂等（重复执行不产生重复）。
- **启动校验**：缺少 `PHONE_ENC_KEY` / `PHONE_HASH_KEY` / `ADMIN_TOKEN` / `WEBHOOK_SECRET`，或 `PHONE_ENC_KEY` 不是合法 Fernet key → 启动失败并给出明确错误（不自动生成临时密钥——否则重启后无法解密已存号码）。

## 7. 统计定义（`stats_service`）

`GET /campaigns/{id}/stats` 响应形状见 `04-api-contract.md` §3。定义：

| 指标 | 定义 |
|---|---|
| `by_status` | 各状态明细数（八种状态都出现，0 也列出）；`Σ = total` |
| `success` | `SENT + DELIVERED + READ` |
| `failed` | `FAILED` |
| `skipped` | `SKIPPED` |
| `in_progress` | `PENDING + SENDING + RETRY_WAIT` |
| `success_rate` | `success / (success + failed)`；分母为 0 → `null` |
| `skip_reasons` | `SKIPPED` 明细按 `reason_code` 分组计数 |
| `failure_reasons` | `FAILED` 明细按 `reason_code` 分组计数 |
| `attempts_histogram` | 按 `attempts` 值（0、1、2、3…）统计明细数 |
| `retry_total` | `Σ max(attempts − 1, 0)` |
| `elapsed_seconds` | `finished_at`（或当前时间）− `started_at`；未启动为 `null` |

`GET /campaigns` 每项带 `total / success / failed / skipped / in_progress` 摘要（STAT-007）。`GET /stats/overview`（P1）：线索各状态数、池大小、任务各状态数、近 24 小时 `ACCEPTED` 数、suppression 按类型数、consent 按状态数。

统计一律**实时计算**（无缓存），在**同一只读事务**内读取，保证各数字之间一致（STAT-006）。

## 8. 验收标准

### config

| AC | P | 描述（给定 / 当 / 则） |
|---|---|---|
| AC-CFG-001 | P0 | 给定关键词 CRUD，当创建 / 修改 / 删除，则 `term` 被规范化；`(term, kind)` 重复 → 409；`weight` 越界、`term` 为空 → 422；`enabled=false` 的词不参与评分 |
| AC-CFG-002 | P0 | 给定频控规则 CRUD，当 `window_seconds<1`、`max_count<1`、`scope` 非法 → 422；合法时成功并写审计 |
| AC-CFG-003 | P0 | 给定 `PUT /settings`，当键不在注册表、类型错误或越界（含 `low ≥ high` 的合并校验），则 422 且无任何设置被修改（原子）；合法部分更新成功 |
| AC-CFG-004 | P0 | 给定任一配置变更（关键词 / 频控 / 设置），则写审计，`before/after` 含变更前后值 |
| AC-CFG-005 | P0 | 给定 `RUNNING` 任务，当运营收紧全局频控或修改 `max_attempts`，则**下一条被处理的明细**即按新值执行（无需重启任务） |
| AC-CFG-006 | P0 | 给定空库，当执行 seed，则得到 §6 的全部种子，重复执行不产生重复项 |
| AC-CFG-007 | P0 | 给定缺失或非法的必需环境变量，当启动应用，则启动失败并给出指明变量名的错误信息 |
| AC-CFG-008 | P0 | 给定仅剩一条启用的 GLOBAL（或 PER_RECIPIENT）规则，当删除或禁用它，则 422 `CFG_LAST_RATE_RULE`，规则保持不变 |

### stats

| AC | P | 描述（给定 / 当 / 则） |
|---|---|---|
| AC-STAT-001 | P0 | 给定任一任务任一时刻，则 `by_status` 八种状态齐全且 `Σ = total` |
| AC-STAT-002 | P0 | 给定已知分布的任务，则 `success / failed / skipped / in_progress / success_rate` 符合 §7 定义；分母为 0 时 `success_rate=null` |
| AC-STAT-003 | P0 | 给定含多种跳过与失败原因的任务，则 `skip_reasons` / `failure_reasons` 计数正确 |
| AC-STAT-004 | P0 | 给定含重试的任务，则 `attempts_histogram` 与 `retry_total` 正确 |
| AC-STAT-005 | P1 | 给定系统有数据，当 `GET /stats/overview`，则各计数与底层表一致 |
| AC-STAT-006 | P0 | 给定 Worker 正在写入，当读取统计，则同一响应内各数字自洽（单一只读事务快照） |
| AC-STAT-007 | P0 | 给定多个任务，当 `GET /campaigns`，则每项含 `total/success/failed/skipped/in_progress` 摘要，与对应 `/stats` 一致 |

## 9. 边界与异常
- 设置值为 JSON：布尔不接受字符串 `"true"`（严格类型），避免静默误配。
- 同时修改多个设置：整个请求原子（要么全成要么全败）。
- 关键词删除后已评分的线索不自动重算（需运营手动触发重新评分）。

## 10. 测试要点
- 设置注册表参数化：每个键的合法 / 非法值。
- R-7：对"最后一条规则"的删除 / 禁用 / 改 scope 三种路径逐一断言被拒。
- 统计：构造每种状态与原因的明细，断言全部指标；并发写入时的一致性用"读事务内两次查询结果自洽"验证。
