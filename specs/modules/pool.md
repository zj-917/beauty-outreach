# 模块规格：pool（目标用户池与人工确认）

> 版本 v1.1 · 状态 定稿（2026-11-14 修订 Q-18） · 依赖：lead、screening、compliance（只读，用于"可触达预估"）、audit

## 1. 目标

把评分结果变成"精确目标用户池"：高分自动入池，中间区间进入人工确认队列；运营可审核、移出或恢复。池 = **`status = APPROVED` 的线索**。

## 2. 范围与非目标

- **范围**：审核队列、单条 / 批量审核、状态转换规则、池查询（含"可触达预估"标记）。
- **非目标**：任务创建（见 campaign）；池的快照语义由任务创建时实现。

## 3. 规则

### 3.1 人工审核转换
`POST /leads/{id}/review`，`decision ∈ {APPROVE, REJECT}`：

| 当前状态 | APPROVE | REJECT |
|---|---|---|
| `PENDING_REVIEW` | → `APPROVED` | → `REJECTED` |
| `APPROVED` | （无变化，幂等） | → `REJECTED`（移出池） |
| `REJECTED` | → `APPROVED`，**备注必填** | （无变化，幂等） |
| `DISCARDED` | → `APPROVED`，**备注必填** | → `REJECTED` |
| `NEW` | ✗ 409（须先评分） | ✗ 409 |

- 结果 `decision_source=MANUAL`，记录 `reviewed_by`（取 `X-Operator`）、`reviewed_at`、`review_note`。
- 每次审核写 `LEAD_REVIEWED` 审计（`before`/`after` 含状态与备注，不含号码）。

### 3.2 批量审核
`POST /leads/review-bulk`：请求 `{"reviews":[{"lead_id":1,"decision":"APPROVE"|"REJECT","note":"…"}]}`，≤ 200 条；逐条独立处理（每条独立提交），响应 `{"results":[{"lead_id":1,"ok":true}]}`，失败项附 `error:{code, message}`；单条失败不影响其他。

### 3.3 池查询与"可触达预估"
`GET /pool` 返回 `APPROVED` 线索，每条附 `delivery_readiness`，值为 `READY` / `BLACKLISTED` / `UNSUBSCRIBED` / `NO_PHONE` / `NO_CONSENT` / `CONSENT_REVOKED`（优先级与发送闸门一致：suppression → 号码 → 授权）。**必须复用 `domain/gates` 的同一批判定函数**，避免与真实发送行为不一致。响应同时给出各类计数汇总。

> 注意：黑名单 / 退订不改变线索的 `status`（仍在池中），只在发送闸门被拦截；池列表如实标注，便于运营理解"为什么没发"。

## 4. 验收标准

| AC | P | 描述（给定 / 当 / 则） |
|---|---|---|
| AC-POOL-001 | P0 | 给定若干不同状态线索，当 `GET /pool`，则只返回 `APPROVED`，按 `score` 降序，分页正确 |
| AC-POOL-002 | P0 | 给定 `PENDING_REVIEW` 线索，当 `GET /leads?status=PENDING_REVIEW`，则按 `score` 降序返回并附 `score_reasons`，供审核参考 |
| AC-POOL-003 | P0 | 给定 §3.1 表中每个合法 / 非法转换，当审核，则合法转换成功并记录审核人 / 时间 / 备注，写入 `LEAD_REVIEWED` 审计；`NEW` 审核 → 409；`REJECTED/DISCARDED→APPROVED` 缺备注 → 422；重复同一决定幂等 |
| AC-POOL-004 | P1 | 给定 200 条以内的批量审核，当其中混有非法项，则合法项成功、非法项在结果中标明原因；超过 200 条 → 422 |
| AC-POOL-005 | P0 | 给定人工 `APPROVED` / `REJECTED` 的线索，当修改关键词并重新评分，则其状态与 `decision_source=MANUAL` 不变 |
| AC-POOL-006 | P1 | 给定池中含无号码 / 无授权 / 已撤销 / 黑名单 / 已退订的线索，当 `GET /pool`，则 `delivery_readiness` 分别标注正确，且与同一线索在发送闸门的结果一致（共享同一判定函数） |
| AC-POOL-007 | P2 | 当 `GET /pool/export`，则返回 CSV，号码列只含 `phone_masked` |
| AC-POOL-008 | P2 | 当 `GET /pool/stats`，则返回按分数段、地区、语言的分布 |

## 5. 边界与异常

- 对不存在的线索审核 → 404。
- 批量审核中同一 `lead_id` 重复出现：按出现顺序依次处理（后者可能是幂等 no-op）。
- 并发审核同一线索：以数据库事务的最后写入为准，审计保留两次记录。

## 6. 测试要点

- 转换表参数化：5 种当前状态 × 2 种决定。
- `delivery_readiness` 与发送闸门一致性测试：同一组线索分别走 `GET /pool` 与 `gates.evaluate`，结果逐条相等。
