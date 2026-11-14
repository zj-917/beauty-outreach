# 模块规格：audit（审计、日志与脱敏）

> 版本 v1.0 · 状态 定稿（2026-11-13 冻结） · 横切模块：被所有写操作调用

## 1. 目标

让"谁在何时对什么做了什么、结果如何"**可追溯、不可篡改、可查询**，同时保证敏感字段**不出现**在任何输出中。

## 2. 范围与非目标

- **范围**：`audit_log`（任务 / 配置 / 合规等操作审计）、`send_log`（每次闸门决策 / Provider 调用 / 回执）、查询 API、脱敏函数与日志过滤器、请求追踪 ID、任务时间线、哈希链。
- **非目标**：外部日志系统对接；日志归档与保留策略自动化；告警。

## 3. 两类日志的分工

| | `audit_log` | `send_log` |
|---|---|---|
| 记录什么 | 人 / 系统对**实体**的操作：创建、变更、审核、启停、导入、配置 | 引擎对**单条明细**的每次闸门决策、Provider 调用、回执 |
| 量级 | 低 | 高（每条明细多行） |
| 谁写 | 各 service，与业务变更**同一事务** | Processor / receipt_service，与明细状态变更**同一事务** |
| 不可变 | 触发器禁止 UPDATE / DELETE；哈希链 | 只追加（不提供更新 / 删除接口） |

## 4. audit_log 设计

### 4.1 写入
- `AuditService.record(session, actor, action, entity_type, entity_id, before, after)`：**必须传入业务所在的同一 Session**，不自行提交——业务回滚则审计一并回滚（AUD-002）。
- 所有数据库事务（含只读）使用 `BEGIN IMMEDIATE`（`core/db.py` 钩子，Q-15），保证读取"上一条哈希"与写入之间无并发插入，哈希链不分叉。
- `before/after` 先经 `redact()`：号码 → 掩码；移除 `body`、`rendered_body`、`token`、`secret`、`password`、`key` 字段；字符串中的类号码序列 → 掩码。

### 4.2 动作注册表（`action`）
`LEAD_BATCH_IMPORTED` · `LEAD_SCREENING_RUN` · `LEAD_REVIEWED` · `KEYWORD_CREATED/UPDATED/DELETED` · `SETTING_UPDATED` · `RATE_RULE_CREATED/UPDATED/DELETED` · `TEMPLATE_CREATED/VERSIONED/APPROVED/DISABLED` · `CONSENT_UPSERTED` · `SUPPRESSION_ADDED/REMOVED` · `INBOUND_STOP_PROCESSED` · `CAMPAIGN_CREATED/STARTED/PAUSED/RESUMED/CANCELLED/COMPLETED/CIRCUIT_OPENED`

> 引擎的逐条明细事件**不**写 `audit_log`（写 `send_log`），避免审计表被淹没。

### 4.3 哈希链（P1）
- `hash = sha256(prev_hash + canonical_json({ts, actor, action, entity_type, entity_id, before, after, request_id}))`；首行 `prev_hash = "GENESIS"`；`canonical_json` = 键排序、无多余空白、UTF-8。
- `GET /audit-logs/verify`：从头校验，返回 `{ok: true, count}` 或 `{ok: false, first_broken_id}`。

### 4.4 查询
`GET /audit-logs`：过滤 `actor / action / entity_type / entity_id / from / to`；按 `ts` 降序；分页。`GET /campaigns/{id}/timeline`：该任务的 `CAMPAIGN_*` 审计，升序。

## 5. send_log 查询
`GET /send-logs`：过滤 `task_id / item_id / phase / outcome / reason_code / from / to`；分页；号码字段只含 `phone_masked`。

## 6. 脱敏

### 6.1 `mask_phone(e164) -> str`（`domain/masking.py`，纯函数）
- 保留前 4 个字符（含 `+`）与后 4 位，中间换成 `****`；总长 < 10 时只保留后 2 位，其余 `*`；非字符串 / 空 → `""`。
- 例：`+8613812345678` → `+861****5678`；`+15555550101` → `+155****0101`。

### 6.2 日志过滤器（`core/logging.py`）
- 对每条日志的最终消息文本：正则 `\+?\d[\d\s\-]{7,}\d` → 掩码；`X-Admin-Token`、`Authorization`、`X-Hub-Signature-256` 的值 → `***`。
- 不记录请求体；不记录消息正文。

### 6.3 泄漏扫描（兜底测试）
端到端跑完整流程后，对以下**输出面**逐一断言不含任何测试所用的完整号码：API 响应（所有端点）、日志（`caplog`）、`audit_log`、`send_log`、`task_item.last_error_message`、SQLite 文件字节（含 `-wal`）。

## 7. 请求追踪
中间件：读取或生成 `X-Request-ID`；写入响应头、日志上下文、审计 `request_id`。非法 / 过长的外部值被丢弃并重新生成。

## 8. 验收标准

| AC | P | 描述（给定 / 当 / 则） |
|---|---|---|
| AC-AUD-001 | P0 | 给定任一审计记录，则含 `ts/actor/action/entity_type/entity_id/before/after/request_id`；`actor` 取自 `X-Operator`，系统动作为 `system:worker` / `system:webhook` |
| AC-AUD-002 | P0 | 给定任一变更类 API（POST/PUT/PATCH/DELETE，含 webhook），当成功，则至少一条审计与业务变更**同一事务**；当业务失败回滚，则无审计残留 |
| AC-AUD-003 | P0 | 给定已有审计行，当尝试 `UPDATE` 或 `DELETE`，则数据库抛错（触发器）且行不变 |
| AC-AUD-004 | P1 | 给定若干审计，当 `GET /audit-logs/verify`，则 `ok=true`；人为篡改某行（绕过触发器）后 `ok=false` 并指出首个损坏 id |
| AC-AUD-005 | P0 | 给定多条审计，当按 `actor/action/entity_type/entity_id/from/to` 过滤，则结果正确、按 `ts` 降序、分页正确 |
| AC-AUD-006 | P0 | 给定多条 `send_log`，当按 `task_id/item_id/phase/outcome/reason_code/from/to` 过滤，则结果正确；号码只含脱敏值 |
| AC-AUD-007 | P0 | 给定 `mask_phone` 参数化用例（长 / 短 / 空 / 非法），则输出符合 §6.1；给定端到端完整流程，则泄漏扫描（§6.3）通过 |
| AC-AUD-008 | P0 | 给定日志中含完整号码、token、签名头，当输出，则被过滤器掩码；`last_error_message` 入库前经同一函数处理 |
| AC-AUD-009 | P1 | 给定请求，当带或不带 `X-Request-ID`，则响应头含 `X-Request-ID`，且与日志、审计的 `request_id` 一致；过长 / 非法值被替换 |
| AC-AUD-010 | P1 | 给定一个走完生命周期的任务，当 `GET /campaigns/{id}/timeline`，则按时间升序给出 `CREATED → STARTED → PAUSED → RESUMED → COMPLETED` 等事件 |
| AC-AUD-011 | P0 | 给定任意审计 `before/after`，则不含号码明文、消息正文、token、密钥；号码字段只含掩码 |

## 9. 边界与异常
- 审计写入失败 → 整个业务事务失败（宁可不做，不可做了无记录）。
- `before/after` 体积过大（> 16KB）→ 截断并标记 `"_truncated": true`。
- 哈希链校验在大表上可能较慢：原型规模可接受，文档注明。

## 10. 测试要点
- 触发器：用原生 SQL 尝试 UPDATE / DELETE。
- 事务一致性：在 service 内注入异常，断言审计与业务均未提交。
- 泄漏扫描作为独立测试文件，**每次全量测试必跑**。
