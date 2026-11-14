# 模块规格：campaign（批量触达任务与发送引擎）

> 版本 v1.1 · 状态 定稿（2026-11-14 修订 Q-21：新增 `RENDER_TOO_LONG` 原因码） · **这是评分权重最高的模块**
> 依赖：template、compliance、pool、audit、`engine/*`、`providers/messenger/*`、`domain/{gates,backoff,state}`

## 1. 目标

基于目标池创建批量触达任务，**可靠、可控、不重复、可追溯**地发送：闸门链 → 频控 → 发送 → 失败分类与退避重试 → 回执回写；支持创建 / 启动 / 暂停 / 恢复 / 取消，进程重启后可续跑。

## 2. 范围与非目标

- **范围**：任务创建与目标快照、状态机与控制语义、闸门链、频控、发送与重试、熔断、回执、租约与重启恢复、干跑预览、任务 / 明细查询、两个 Messenger 实现（Mock + 真实 Stub）。
- **非目标**：多 Worker / 分布式；定时调度；A/B 模板；富媒体消息。

## 3. 任务创建与快照

`POST /campaigns {name, template_id, selection}`：

- `selection`（均可选）：`min_score`、`batch_id`、`lead_ids`；默认 = 池中全部 `APPROVED` 线索；多条件取交集。
- 模板必须 `APPROVED`，否则 422 `TEMPLATE_NOT_APPROVED`；目标为空 → 422 `CAMPAIGN_EMPTY_TARGET`。
- **一个事务内**：创建任务（`DRAFT`）+ 为每个目标线索创建明细（`PENDING`），记录 `phone_hash/phone_masked` 快照与幂等键；写 `CAMPAIGN_CREATED` 审计（含 `selection` 与 `total_items`）。
- **快照语义**：此后池的变化（新增 / 移出线索）不影响已创建的任务。
- **幂等键**：`idempotency_key = sha256(f"{task_id}:{lead_id}:{template_id}")` 的 hex；全局唯一。该键同时作为 `SendRequest.idempotency_key` 传给 Messenger。

## 4. 状态机与控制语义

状态机见 `03-data-model.md` §3.2 / §3.3。控制接口语义：

| 操作 | 合法来源 | 行为 |
|---|---|---|
| `start` | `DRAFT` | 前置检查（顺序：模板 `APPROVED` → 存在非终态明细 → Provider 可用）→ `RUNNING`，记录 `started_at`，写审计。任一前置检查失败时任务状态不变；Provider 不可用（Stub）→ 501 `PROVIDER_NOT_ENABLED`（SYS-006）。对 `RUNNING` 重复调用 = **幂等 no-op**（200，不写审计，不产生新的发送） |
| `pause` | `RUNNING` | → `PAUSED`（`pause_reason=MANUAL`）。Worker 不再认领新明细；**已认领但尚未开始发送**的明细在 Processor 复检时释放租约（不消耗 attempt）；**已在 `SENDING` 的调用**允许完成并正常回写 |
| `resume` | `PAUSED` | → `RUNNING`，清零 `consecutive_failures`，`pause_reason=null` |
| `cancel` | `DRAFT/RUNNING/PAUSED` | → `CANCELLED`；所有 `PENDING/RETRY_WAIT` 明细 → `SKIPPED(TASK_CANCELLED)`；`SENDING` 的调用完成后，若结果为可重试失败，则直接 `SKIPPED(TASK_CANCELLED)` 而非 `RETRY_WAIT` |
| 其他非法组合 | — | 409 `CAMPAIGN_INVALID_STATE` |

**自动完成**：每处理完一条明细（及每个 tick）检查；不存在 `PENDING/SENDING/RETRY_WAIT` 明细时，`RUNNING → COMPLETED`，写 `finished_at` 与 `CAMPAIGN_COMPLETED` 审计。

## 5. 闸门链

Processor 对每条被认领的明细按**固定顺序**判定，**首个非放行的闸门决定结果**。原则（D-6）：先裁决"跳过"类，再裁决"延迟"类，避免为注定被跳过的收件人占用频控额度。

| # | 闸门 | 类型 | 条件 → 结果 | 原因码 |
|---|---|---|---|---|
| 1 | `TASK_ACTIVE` | Release | 任务非 `RUNNING` → 释放租约，不改明细 | — |
| 2 | `SUPPRESSION` | Skip | 命中黑名单 / 退订 | `BLACKLISTED` / `UNSUBSCRIBED` |
| 3 | `PHONE` | Skip | 无号码 / 号码非法 | `NO_PHONE` / `INVALID_PHONE` |
| 4 | `CONSENT` | Skip | 无记录 / 已撤销 | `NO_CONSENT` / `CONSENT_REVOKED` |
| 5 | `TEMPLATE` | Skip | 模板非 `APPROVED`；渲染失败 | `TEMPLATE_NOT_APPROVED` / `TEMPLATE_VARIABLE_MISSING` / `RENDER_TOO_LONG` |
| 6 | `DUPLICATE` | Skip | 同号码 + 同**模板名**已有 `ACCEPTED`（任一任务，排除本明细）；或本明细已有 `provider_message_id` | `ALREADY_CONTACTED` |
| 7 | `RECIPIENT_FREQ` | Skip | 同号码在 `PER_RECIPIENT` 规则窗口内 `ACCEPTED` 次数 ≥ `max_count`（排除本明细） | `RECIPIENT_RATE_LIMITED` |
| 8 | `QUIET_HOURS` | Defer | 处于静默时段 | `QUIET_HOURS` |
| 9 | `GLOBAL_RATE` | Defer | 任一启用 `GLOBAL` 规则窗口内 Provider 调用数 ≥ `max_count` | `RATE_LIMIT_GLOBAL` |

处理规则：
- **Skip**：事务内 `status=SKIPPED`、`reason_code`、清租约，写 `send_log(GATE, BLOCKED, reason)`。**Messenger 零调用。**
- **Defer**：状态不变（`PENDING` / `RETRY_WAIT`）、`next_attempt_at = until`、清租约，写 `send_log(GATE, DEFERRED, reason, detail.until)`；**不增加 `attempts`**。
- 判定所需的 suppression / consent / 计数**每条实时查询**，不跨明细缓存（保证退订即时生效）。
- 闸门判定函数在 `domain/gates.py`（纯函数，输入为查询结果快照）；pool 的 `delivery_readiness` 复用其中 2–4 号闸门。

## 6. 频控设计

- 规则来自 `rate_rule`（实时读取，D-7）；所有**启用**规则必须同时满足（取最严）。
- **GLOBAL（吞吐）**：统计 `send_log` 中 `phase=PROVIDER` 且 `created_at ≥ now − window` 的行数（任何结果都算一次调用，含失败重试）。超限 → `until = 窗口内最早一条 created_at + window_seconds`；多条规则取最晚者。
- **PER_RECIPIENT（单收件人）**：统计同 `phone_hash`、`phase=PROVIDER`、`outcome=ACCEPTED`、窗口内的行数（排除本明细）。超限 → 终态 `SKIPPED(RECIPIENT_RATE_LIMITED)`，而不是延迟 24 小时。
- 种子：`GLOBAL 5/10s`、`PER_RECIPIENT 1/86400s`（`05-mock-data.md` §5）。
- 单 Worker 不变量保证"计数→发送"之间无竞争。

## 7. 发送、失败分类与重试

### 7.1 Processor 流程
见 `02-architecture.md` §5。要点：**事务外调用 Provider**；`attempts` 在开始调用前 +1 并落库；调用设超时（`sending.provider_timeout_seconds`，超时 → `RETRYABLE(TIMEOUT)`）。

### 7.2 Provider 结果与分类

| `SendResult.kind` | `code` | 含义 | Processor 处理 |
|---|---|---|---|
| `ACCEPTED` | — | 已受理，带 `provider_message_id` | → `SENT`，`sent_at`，重置熔断计数 |
| `RETRYABLE` | `TIMEOUT` | 超时 | 重试；计入熔断 |
| `RETRYABLE` | `NETWORK_ERROR` | 网络错误 | 重试；计入熔断 |
| `RETRYABLE` | `SERVER_ERROR` | 5xx | 重试；计入熔断 |
| `RETRYABLE` | `RATE_LIMITED` | 429，可带 `retry_after_seconds` | 重试；`delay = max(退避, retry_after)`；**不计入**熔断 |
| `PERMANENT` | `INVALID_NUMBER` | 号码无效 | → `FAILED(INVALID_NUMBER)`，不重试 |
| `PERMANENT` | `NOT_WHATSAPP_USER` | 号码未注册 WhatsApp | → `FAILED(NOT_WHATSAPP_USER)` |
| `PERMANENT` | `TEMPLATE_REJECTED` | 平台拒绝模板 | → `FAILED(TEMPLATE_REJECTED)` |
| `PERMANENT` | `AUTH_ERROR` | 凭证无效 | → `FAILED(AUTH_ERROR)`，并**立即熔断**（任务 `PAUSED`，`CIRCUIT_OPEN`） |

> 非 `ACCEPTED` 时 `last_error_code / last_error_message` 落库；`message` 经清洗，不含号码（AUD-008 的脱敏函数二次处理）。

### 7.3 退避与最大尝试
- `delay = min(base × 2^(n−1), cap) × (1 + jitter × u)`，`n` = 刚失败的尝试序号，`u ∈ [−1, 1]` 由可注入的 RNG 产生。`RATE_LIMITED` 再取 `max(delay, retry_after)`。
- 默认 `max_attempts=3`（总调用次数）、`base=2s`、`cap=60s`、`jitter=0.2`。
- 可重试失败且 `attempts < max_attempts` → `RETRY_WAIT`，`next_attempt_at = now + delay`；否则 → `FAILED(MAX_ATTEMPTS_EXCEEDED)`，`last_error_code` 保留底层错误码。
- `retry_count = max(attempts − 1, 0)`（展示用）。

### 7.4 熔断（P1）
- 任务级 `consecutive_failures`：每次 `TIMEOUT/NETWORK_ERROR/SERVER_ERROR` +1，`ACCEPTED` 重置为 0；`RATE_LIMITED` 与其他 `PERMANENT` 既不增也不减。
- 达到 `sending.circuit_breaker_threshold`（默认 5）或出现 `AUTH_ERROR` → 任务自动 `PAUSED`（`pause_reason=CIRCUIT_OPEN`），写 `CAMPAIGN_CIRCUIT_OPENED` 审计。需人工 `resume`。

## 8. 回执处理（`receipt_service`）

- 入口：① 签名 Webhook `POST /webhooks/whatsapp/status`；② Worker 每 tick 调用 `messenger.poll_receipts()`（Mock）。两者共用同一 `apply_receipt()`。
- 载荷：`{provider_message_id, status: delivered|read|failed, error?{code,message}, timestamp}`。
- 规则：
  - 状态秩 `SENT(1) < DELIVERED(2) < READ(3)`：**只前进不后退**；重复 / 乱序 / 过期回执 → no-op（`{"applied": false}`，仍 200）。
  - `failed` 仅对 `SENT/DELIVERED` 生效 → `FAILED(DELIVERY_FAILED)`，**不再重试**（Provider 已受理，重发有双发风险）；对 `READ` 不生效。
  - 未知 `provider_message_id` → no-op，记 warning（不含号码）。
  - 每次生效都写 `send_log(RECEIPT, DELIVERED|READ|DELIVERY_FAILED)` 并更新 `delivered_at/read_at`。

## 9. 租约与重启恢复

见 `02-architecture.md` §6。要点：
- 认领 = `BEGIN IMMEDIATE` 内给明细加租约（`locked_by/locked_at`）；`lease_seconds` 默认 60。
- 每个 tick 先回收：`status=SENDING` 且租约过期 → `RETRY_WAIT`（`next_attempt_at=now`）。
- 重启后 `RUNNING` 任务自动继续；以**同一幂等键**重发；Mock 对同键幂等 → 唯一消息数不增加。
- `PAUSED` / `DRAFT` / 终态任务在重启后保持原状态。

## 10. 干跑预览（P1）

`POST /campaigns/{id}/preview`：对所有非终态明细**只读**评估闸门 1–7（不含时间相关的 8–9），返回 `{will_attempt, will_skip: {reason: n}, readiness_by_lead?}`。**无副作用**：不写 `send_log`、不调用 Messenger、不改明细。注明"频控延迟与静默时段未模拟"。

## 11. 原因码注册表

| 类别 | 原因码 |
|---|---|
| `SKIPPED` | `BLACKLISTED` `UNSUBSCRIBED` `NO_PHONE` `INVALID_PHONE` `NO_CONSENT` `CONSENT_REVOKED` `TEMPLATE_NOT_APPROVED` `TEMPLATE_VARIABLE_MISSING` `RENDER_TOO_LONG` `ALREADY_CONTACTED` `RECIPIENT_RATE_LIMITED` `TASK_CANCELLED` |
| `FAILED` | `MAX_ATTEMPTS_EXCEEDED` `INVALID_NUMBER` `NOT_WHATSAPP_USER` `TEMPLATE_REJECTED` `AUTH_ERROR` `DELIVERY_FAILED` |
| `DEFERRED`（仅 `send_log`） | `RATE_LIMIT_GLOBAL` `QUIET_HOURS` |
| Provider `code` | `TIMEOUT` `NETWORK_ERROR` `SERVER_ERROR` `RATE_LIMITED` `INVALID_NUMBER` `NOT_WHATSAPP_USER` `TEMPLATE_REJECTED` `AUTH_ERROR` |

## 12. Messenger 实现

- **`MockMessenger`**：行为矩阵见 `05-mock-data.md` §4；对同一 `idempotency_key` 返回同一 `provider_message_id`；暴露 `calls`（总调用数）、`unique_messages`（唯一消息数）、`poll_receipts()`；时钟由 `Clock` 注入；不记录完整号码。
- **`WhatsAppCloudStub`**：实现同一协议；`enabled=false`（默认）时 `send()` 抛 `ProviderNotEnabled`（→ 501 语义），**不发起任何网络调用**；文档注明真实对接所需：企业认证、Access Token、已审核模板、Webhook 验证。

## 13. 验收标准

| AC | P | 描述（给定 / 当 / 则） |
|---|---|---|
| AC-CAMP-001 | P0 | 给定 `APPROVED` 模板与池中线索，当创建任务，则一个事务内生成 `DRAFT` 任务与每个目标的 `PENDING` 明细（含号码快照与幂等键），写 `CAMPAIGN_CREATED` 审计；目标为空 → 422 `CAMPAIGN_EMPTY_TARGET`；`selection` 条件取交集 |
| AC-CAMP-002 | P0 | 给定已创建的任务，当之后池中新增或移出线索，则该任务的明细集合不变 |
| AC-CAMP-003 | P0 | 给定任务与线索，则 `idempotency_key = sha256("{task_id}:{lead_id}:{template_id}")`，全局唯一；试图插入重复键时被数据库拒绝且被正确处理 |
| AC-CAMP-004 | P0 | 给定 §4 表，当执行每种合法 / 非法的状态操作，则合法转换成功、非法返回 409 `CAMPAIGN_INVALID_STATE`（参数化覆盖全部 5×4 组合） |
| AC-CAMP-005 | P0 | 给定 `RUNNING` 任务，当再次 `start`（含并发两次），则 200 幂等，Messenger 的**唯一消息数**等于唯一收件人数，且不产生额外审计 |
| AC-CAMP-006 | P0 | 给定 `RUNNING` 任务，当 `pause`，则 Worker 不再认领新明细；已认领未发送的明细租约被释放且 `attempts` 不变；已在发送的调用正常回写 |
| AC-CAMP-007 | P0 | 给定 `PAUSED` 任务，当 `resume`，则继续处理剩余明细，已终态的明细不被重复处理，`consecutive_failures` 清零 |
| AC-CAMP-008 | P0 | 给定任务，当 `cancel`，则 `PENDING/RETRY_WAIT` 明细全部 `SKIPPED(TASK_CANCELLED)`；之后 `start/resume` → 409；发送中遇可重试失败不再进入 `RETRY_WAIT` |
| AC-CAMP-009 | P0 | 给定模拟崩溃（明细停在 `SENDING` 且租约过期，Provider 已受理该幂等键），当 Worker 重启 tick，则该明细被回收并以同键重发，Mock 的**唯一消息数不增加**，明细最终 `SENT` |
| AC-CAMP-010 | P0 | 给定同时触发多个闸门的明细，则按 §5 固定顺序判定、首个非放行者决定结果；每次拦截 / 延迟写一条 `send_log(GATE)`，含原因码 |
| AC-CAMP-011 | P0 | 给定命中闸门 2–7 任一的明细，则 `Messenger.send` 调用次数为 0（spy 断言） |
| AC-CAMP-012 | P0 | 给定 `GLOBAL N/窗口` 规则，当窗口内调用数已达上限，则后续明细 `DEFERRED(RATE_LIMIT_GLOBAL)`：状态不变、`attempts` 不变、`next_attempt_at` 正确；窗口滑过后继续发送（`FakeClock` 推进） |
| AC-CAMP-013 | P0 | 给定同号码在窗口内已有 `ACCEPTED`，当另一任务含该号码，则 `SKIPPED(RECIPIENT_RATE_LIMITED)` |
| AC-CAMP-014 | P0 | 给定同号码 + 同模板名已发送成功（任一任务），当新任务含该号码，则 `SKIPPED(ALREADY_CONTACTED)` |
| AC-CAMP-015 | P0 | 给定 Provider 各类 `SendResult`，则按 §7.2 分类：可重试 → `RETRY_WAIT`；永久 → `FAILED`；`AUTH_ERROR` 另触发熔断 |
| AC-CAMP-016 | P0 | 给定连续失败，则 `delay = min(base·2^(n−1), cap)·(1±jitter)`（注入固定 RNG 断言）；`RATE_LIMITED` 的 `delay ≥ retry_after` |
| AC-CAMP-017 | P0 | 给定 `max_attempts=3`，当第 3 次仍可重试失败，则 `FAILED(MAX_ATTEMPTS_EXCEEDED)`，`last_error_code` 保留底层码；永久失败首次即 `FAILED`，`attempts=1` |
| AC-CAMP-018 | P0 | 给定任一 Provider 调用，则写一条 `send_log(PROVIDER)`，含 `attempt_no`、`outcome`、`reason_code`、`latency_ms`、`provider_message_id`（如有） |
| AC-CAMP-019 | P0 | 给定发送过程，则明细的 `attempts / next_attempt_at / last_error_code / last_error_message / provider_message_id / sent_at` 正确回写；`last_error_message` 不含号码 |
| AC-CAMP-020 | P0 | 给定 `SENT` 明细，当收到 `delivered` 再 `read`，则状态依次前进；乱序（先 `read` 后 `delivered`）、重复回执均不后退、返回 `applied:false`；`SENT→READ` 跳级允许；每次生效写 `send_log(RECEIPT)` |
| AC-CAMP-021 | P0 | 给定 `SENT/DELIVERED` 明细，当收到 `failed` 回执，则 `FAILED(DELIVERY_FAILED)` 且不再重试；对 `READ` 明细的 `failed` 回执被忽略 |
| AC-CAMP-022 | P1 | 给定连续 5 次 `TIMEOUT/NETWORK_ERROR/SERVER_ERROR`，则任务自动 `PAUSED(CIRCUIT_OPEN)` 并写审计；`ACCEPTED` 重置计数；`RATE_LIMITED` 不计数；`AUTH_ERROR` 立即熔断；`resume` 后继续 |
| AC-CAMP-023 | P0 | 给定所有明细均达终态，则任务自动 `COMPLETED`，写 `finished_at` 与 `CAMPAIGN_COMPLETED` 审计，且只写一次 |
| AC-CAMP-024 | P1 | 给定 `POST /campaigns/{id}/preview`，则返回闸门 1–7 的结果分布，且 `send_log`、明细、Messenger 调用均无变化 |
| AC-CAMP-025 | P0 | 给定两个并发认领者（两个会话 / 线程），当同时认领，则不会认领到同一条明细；租约未过期的明细不被再次认领 |
| AC-CAMP-026 | P0 | 给定 Provider 调用超过 `provider_timeout_seconds`，则按 `RETRYABLE(TIMEOUT)` 处理 |
| AC-CAMP-027 | P0 | 给定 `start`，当模板已非 `APPROVED` 或无非终态明细，则 422（`TEMPLATE_NOT_APPROVED` / `CAMPAIGN_EMPTY_TARGET`），任务状态不变 |
| AC-CAMP-028 | P2 | 给定 `FAILED` 明细，当 `POST /campaigns/{id}/requeue-failed`，则可重试类失败被重新入队（`attempts` 重置，仍经全部闸门），永久失败不入队 |
| AC-CAMP-029 | P0 | 给定任务，当 `GET /campaigns`、`/campaigns/{id}`、`/campaigns/{id}/items`，则列表含汇总计数；明细支持 `status / reason_code / q` 过滤与分页；仅含 `phone_masked` |
| AC-CAMP-030 | P0 | 给定 `MockMessenger`，则同一 `idempotency_key` 多次调用返回同一 `provider_message_id` 且不增加唯一消息数；§`05-mock-data.md` 4 的号码行为矩阵全部符合预期 |
| AC-CAMP-031 | P1 | 给定 `WhatsAppCloudStub` 默认配置，当 `send()`，则抛 `ProviderNotEnabled` 且无任何网络连接；与 `MockMessenger` 通过同一套契约测试（接口形状） |

## 14. 边界与异常

- Provider 抛未预期异常 → 视为 `RETRYABLE(NETWORK_ERROR)`，并记录（不含号码）；Worker 线程永不因单条明细异常退出。
- 数据库写失败（`SQLITE_BUSY` 等）→ 本 tick 放弃该明细（租约自然过期后重试），记录错误日志。
- `next_attempt_at` 在过去的明细立即可认领；在未来的不被认领。
- 熔断与暂停并存：`PAUSED` 的 `pause_reason` 决定 UI 展示的提示文案。
- 已知限制：全局频控触发时，每条被延迟的明细各写一条 `DEFERRED` 日志，量大时有写放大（原型规模可接受）。

## 15. 测试要点

- **FakeClock + 手动 `worker.tick()`**：整个引擎测试无 sleep、完全确定。
- 用 spy 包装 `MockMessenger` 断言调用次数 / 唯一消息数。
- 闸门链：对全部 9 个闸门各自构造"仅它触发"与"多个同时触发"的用例。
- 并发认领：两个线程各自 `claim()`，断言交集为空。
- 崩溃恢复：手动构造 `SENDING + 过期租约` 状态，调用 `tick()` 验证。
- 端到端：`05-mock-data.md` §3 的汇总数字逐一断言。
