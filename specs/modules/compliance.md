# 模块规格：compliance（合规闸门：授权 / 黑名单 / 退订 / 静默时段）

> 版本 v1.0 · 状态 定稿（2026-11-13 冻结） · 依赖：`domain/phone`、`domain/gates`、audit · 被 campaign 引擎与 pool 调用

## 1. 目标

保证**只对已授权的用户触达，且永不触达拒绝者**。本模块提供：授权（consent）管理、黑名单 / 退订（suppression）管理、入站 `STOP` 处理，以及发送前的**合规类闸门判定函数**。

## 2. 范围与非目标

- **范围**：consent 与 suppression 的数据与 API、入站退订处理、合规类闸门（suppression / 号码 / 授权 / 静默时段）。
- **非目标**：频控与幂等类闸门（见 campaign）；用户重新订阅流程（A-4：退订永久拦截）。

## 3. 概念与规则

### 3.1 授权（consent）
- 按 `phone_hash` 唯一，状态 `GRANTED` / `REVOKED`；**无记录 = UNKNOWN = 不可发送**。
- `PUT /consents`：`{phone, status, source, evidence_ref}`；`source` 必填；`GRANTED` 时 `evidence_ref` 必填。号码经规范化后求哈希，响应只含 `phone_masked`。
- 历史由审计保留（`CONSENT_UPSERTED`，`before/after` 只含脱敏号码与状态）。

### 3.2 suppression
- `type=BLACKLIST`（运营手动加入）、`type=UNSUBSCRIBE`（用户退订）。可按 `phone` 或 `username` 或两者登记（至少一个）。
- 匹配：线索的 `phone_hash` 命中，或线索的 `username` 命中，任一即视为在名单内。
- `BLACKLIST` 可删除（审计）；**`UNSUBSCRIBE` 不可删除**（409 `COMP_UNSUBSCRIBE_IMMUTABLE`）。
- **退订永久有效**：即使之后 consent 被设为 `GRANTED`，该号码仍被拦截为 `UNSUBSCRIBED`。

### 3.3 入站退订
`POST /webhooks/whatsapp/inbound`（HMAC 签名）：`{from, text}`。

- 文本规范化：NFKC → casefold → 去首尾空白与首尾标点；与 `compliance.stop_keywords` **整词精确相等**才算退订（默认 `stop`、`unsubscribe`、`cancel`、`end`、`quit`、`退订`、`取消订阅`）。`please don't stop` 不算。
- 命中：在**同一事务**内 `INSERT suppression(UNSUBSCRIBE, source=INBOUND_STOP)`（已存在则忽略）+ consent 置 `REVOKED`（无记录则新建，`source=inbound_stop`）+ 写 `INBOUND_STOP_PROCESSED` 审计。
- 来自**未知号码**的 `STOP` 也照常登记（宁可多拦，不可漏拦）。
- 幂等：重复 `STOP` 不产生重复记录，仍返回 `{"action":"UNSUBSCRIBED"}`。

### 3.4 合规类闸门判定（`domain/gates.py`，纯函数）

输入为已取出的数据快照（线索号码 / username、suppression 命中结果、consent 状态、当前时间与设置），输出 `Pass | Skip(reason) | Defer(until, reason)`。

| 顺序 | 闸门 | 类型 | 原因码 |
|---|---|---|---|
| 2 | `SUPPRESSION` | Skip | `BLACKLISTED` / `UNSUBSCRIBED`（同时命中时 `UNSUBSCRIBED` 优先） |
| 3 | `PHONE` | Skip | `NO_PHONE`（无号码）/ `INVALID_PHONE`（解密后不符合 E.164） |
| 4 | `CONSENT` | Skip | `NO_CONSENT`（无记录）/ `CONSENT_REVOKED` |
| 8 | `QUIET_HOURS` | Defer | `QUIET_HOURS` |

（"顺序"为全局闸门链中的位置，完整链见 `campaign.md` §4。）

### 3.5 静默时段
- 设置：`sending.quiet_hours_enabled/start/end/tz`。默认关闭。
- 窗口 `start > end`（如 `22:00–08:00`）表示跨午夜。当前时间（按 `tz` 换算）落在窗口内 → `Defer`，`until` = 窗口结束时刻（换算为 UTC）。
- 夏令时 / 无效本地时间按 `zoneinfo` 的标准行为处理；测试用 `FakeClock` 固定时间。

## 4. 内部接口

```python
class ComplianceService:
    def upsert_consent(self, phone: str, status: str, source: str, evidence_ref: str | None, operator: str) -> ConsentView
    def add_suppression(self, type: str, *, phone: str | None, username: str | None, reason: str, source: str, operator: str) -> SuppressionView
    def remove_suppression(self, id: int, operator: str) -> None          # UNSUBSCRIBE → COMP_UNSUBSCRIBE_IMMUTABLE
    def handle_inbound(self, from_phone: str, text: str) -> Literal["UNSUBSCRIBED","IGNORED"]
    def lookup(self, phone_hash: str | None, username: str | None) -> ComplianceSnapshot   # 供闸门使用，每次实时查询，不缓存
```

## 5. 验收标准

| AC | P | 描述（给定 / 当 / 则） |
|---|---|---|
| AC-COMP-001 | P0 | 给定 `PUT /consents`，当 `source` 缺失，或 `GRANTED` 缺 `evidence_ref`，或号码非法，则 422；合法时 upsert 成功且响应只含 `phone_masked`；每次写 `CONSENT_UPSERTED` 审计 |
| AC-COMP-002 | P0 | 给定线索号码无 consent 记录，当发送闸门判定，则 `Skip(NO_CONSENT)` |
| AC-COMP-003 | P0 | 给定 consent=`REVOKED`，当闸门判定，则 `Skip(CONSENT_REVOKED)` |
| AC-COMP-004 | P0 | 给定号码或 username 在 suppression 中，当任务发送，则明细 `SKIPPED(BLACKLISTED/UNSUBSCRIBED)` 且 `Messenger.send` 调用次数为 0 |
| AC-COMP-005 | P0 | 给定同一线索既 consent=`GRANTED` 又在黑名单，则结果为 `BLACKLISTED`；既退订又黑名单，则 `UNSUBSCRIBED`；无号码但 username 在黑名单，则 `BLACKLISTED`（suppression 先于号码与授权判定） |
| AC-COMP-006 | P0 | 给定入站文本 `STOP`、` stop. `、`退订`，当 webhook 处理，则创建 UNSUBSCRIBE、consent→REVOKED、写审计，同一事务；`please don't stop`、`stopping` 不触发；重复 `STOP` 幂等；未知号码也登记 |
| AC-COMP-007 | P0 | 给定 `RUNNING` 任务中某收件人的明细尚为 `PENDING` / `RETRY_WAIT`，当该号码发来 `STOP`，则**无需重启任务**，该明细在下一次被处理时 `SKIPPED(UNSUBSCRIBED)` |
| AC-COMP-008 | P0 | 给定 `DELETE /suppressions/{id}`，当类型为 `UNSUBSCRIBE`，则 409 `COMP_UNSUBSCRIBE_IMMUTABLE`；`BLACKLIST` 可删除并写 `SUPPRESSION_REMOVED` 审计 |
| AC-COMP-009 | P0 | 给定已退订号码，当 consent 被 `PUT` 为 `GRANTED`，则发送闸门仍判定 `UNSUBSCRIBED` |
| AC-COMP-010 | P0 | 给定线索无号码，则 `Skip(NO_PHONE)`；号码解密后不符合 E.164，则 `Skip(INVALID_PHONE)` |
| AC-COMP-011 | P1 | 给定静默时段启用，当当前时间在窗口内（含 `22:00–08:00` 跨午夜），则 `Defer`，`until` 为窗口结束时刻；窗口外 `Pass`；`FakeClock` 驱动 |
| AC-COMP-012 | P0 | 给定任意组合输入，则合规闸门判定函数是纯函数、结果确定，且判定顺序固定为 suppression → 号码 → 授权 → 静默时段（首个非 Pass 决定结果） |
| AC-COMP-013 | P0 | 给定 `POST /suppressions`，当提供 phone 或 username（至少一个），则登记成功（重复登记幂等）；两者皆空 → 422；`GET /suppressions` 支持按类型过滤，号码只显示脱敏值 |
| AC-COMP-014 | P2 | 给定 CSV，当 `POST /consents/import`，则批量 upsert，逐行报告 |

## 6. 边界与异常

- Webhook 签名无效 → 401，**不处理**（SYS-009）。
- 入站 `from` 号码格式异常 → 200 `{"action":"IGNORED"}`（避免上游重试风暴），仅记录 warning（不含号码）。
- `lookup` 每次实时查库，不做进程内缓存——保证 AC-COMP-007 的"即时生效"。

## 7. 测试要点

- 闸门判定参数化：{有 / 无号码} × {consent: 无 / GRANTED / REVOKED} × {suppression: 无 / BLACKLIST / UNSUBSCRIBE / 两者} 全组合，断言原因码优先级。
- 入站文本参数化（包括全角、标点、大小写、含多余词）。
- 用 spy `Messenger` 断言"被拦截时零调用"。
