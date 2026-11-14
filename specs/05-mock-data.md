# 05 Mock 数据与演示场景

> 版本 v1.0 · 状态 定稿（2026-11-13 冻结） · 目标：数据"像真的"——有脏数据、重复、无授权、已退订、会失败——让演示一次讲清全部设计点，且结果**可预期、可复现**。

## 1. 文件

| 文件 | 内容 |
|---|---|
| `data/mock_leads.json` | 52 行线索（含脏数据与标注 `expected_label`，仅评测脚本使用，不入库）；授权信息随行携带（`consent_*` 字段，LEAD-009） |
| `data/mock_blacklist.csv` | 预置黑名单与退订名单（`type, phone, username, reason`） |
| `data/sample_leads.csv` | 5–8 行小样本，用于演示"CSV 上传" |

所有号码使用 `+1555555xxxx` 形式的**虚构号码**（美国 555 虚构段）。`mock_leads.json` 行格式：

```json
{"username":"glow.with.mia","display_name":"Mia","bio":"Reviewing beauty devices, LED masks & microcurrent tools | skincare nerd",
 "region":"US","language":"en","source_url":"https://www.instagram.com/glow.with.mia/",
 "phone":"+15555550101","consent_status":"GRANTED","consent_source":"web_form","consent_evidence":"form-2026-0001",
 "expected_label":"relevant"}
```

## 2. 数据构成（52 行）

| 类别 | 行数 | 说明 | 期望结果 |
|---|---|---|---|
| A 明确相关 | 20 | 简介含美容仪相关词，地区 / 语言在白名单；其中 1 条手机号格式非法（导入时丢弃号码并记 1 条 warning，线索保留） | 自动入池（APPROVED） |
| B 边缘相关 | 8 | 只提护肤 / 美妆，不提设备 | 待人工确认（PENDING_REVIEW） |
| C 无关 | 10 | 健身、美食、旅行等 | DISCARDED |
| D 负面关键词 | 6 | 含美容仪词，但同时是批发 / 代购 / 互关 / 抽奖 | DISCARDED（验证负向扣分） |
| E 重复 / 冲突 | 4 | E1 同 username 大小写不同；E2 带 `@` 前缀；E3 不同 username 同手机号；E4 同 username 不同手机号（冲突） | 计入 `duplicates`；E4 额外记 `IMPORT_CONFLICT` |
| F 非法行 | 4 | F1 缺 username；F2 username 含非法字符；F3 `source_url` 非 instagram 域名；F4 username 超过 30 字符 | 计入 `invalid`，不入库 |

> 导入报告预期：`total_rows=52, imported=44, duplicates=4, invalid=4, warnings=1`（warning 来自 A 类中号码非法的那条）。若最终实现与评测出现出入，**先改本文件与 `lead.md`，再改代码**。`04-api-contract.md` 示例中的数字以此为准。

## 3. A 类 20 条的合规与送达场景矩阵

A 类 20 条中：6 条本无号码，另有 1 条号码非法被丢弃 → **共 7 条无号码，触达时 `NO_PHONE`**。其余 13 条带号码，场景如下（号码后四位决定 Mock 行为，见 §4；"普通"指后四位不在 `9001`–`9005`）：

| # | 号码后四位 | consent | suppression | 预期 |
|---|---|---|---|---|
| 1–3 | 普通（如 `0101`–`0103`） | GRANTED | 无 | SENT → DELIVERED / READ |
| 4 | `9001` | GRANTED | 无 | 超时 ×2 后成功（演示重试 + 退避） |
| 5 | `9002` | GRANTED | 无 | 持续 503 → `FAILED(MAX_ATTEMPTS_EXCEEDED)` |
| 6 | `9003` | GRANTED | 无 | `FAILED(INVALID_NUMBER)`，**不重试** |
| 7 | `9004` | GRANTED | 无 | 429（`retry_after`）一次后成功 |
| 8 | `9005` | GRANTED | 无 | SENT 后回执 `failed` → `FAILED(DELIVERY_FAILED)` |
| 9 | 普通 | **无记录** | 无 | `SKIPPED(NO_CONSENT)` |
| 10 | 普通 | REVOKED | 无 | `SKIPPED(CONSENT_REVOKED)` |
| 11 | 普通 | GRANTED | BLACKLIST | `SKIPPED(BLACKLISTED)` |
| 12 | 普通 | GRANTED | UNSUBSCRIBE（预置） | `SKIPPED(UNSUBSCRIBED)` |
| 13 | 普通 | GRANTED | BLACKLIST（按 username） | `SKIPPED(BLACKLISTED)`（验证 suppression 优先于 consent） |

**首轮任务（全部 20 条 A 类入池后）预期汇总**：
- 发起过发送：8 条（#1–#8）——其中成功 `SENT/DELIVERED/READ` 5 条（#1–#3、#4、#7），失败 3 条（#5、#6、#8）；
- 跳过：12 条——`NO_PHONE` 7、`NO_CONSENT` 1、`CONSENT_REVOKED` 1、`BLACKLISTED` 2、`UNSUBSCRIBED` 1。

> 演示时再加一步：暂停任务 → 对 #1–#3 之一执行"模拟入站 STOP" → 恢复 → 该条变为 `SKIPPED(UNSUBSCRIBED)`，此时成功数降为 4。预期数字在 `demo.py` 中以断言固化。

## 4. MockMessenger 确定性行为（按号码后四位）

| 后四位 | 行为 |
|---|---|
| `9001` | 前 2 次调用返回 `RETRYABLE(TIMEOUT)`，第 3 次 `ACCEPTED` |
| `9002` | 每次返回 `RETRYABLE(SERVER_ERROR)` |
| `9003` | 返回 `PERMANENT(INVALID_NUMBER)` |
| `9004` | 第 1 次 `RETRYABLE(RATE_LIMITED, retry_after=3s)`，之后 `ACCEPTED` |
| `9005` | `ACCEPTED`，随后产生 `failed` 回执（`DELIVERY_FAILED`） |
| 其他 | `ACCEPTED`；回执：先 `delivered`，偶数末位再 `read` |

规则：
- 同一 `idempotency_key` 重复调用 → 返回**同一** `provider_message_id`，且不增加"已发送消息总数"（用于测试"重启后不产生第二条消息"）。"调用次数"与"唯一消息数"分别可查（`mock.calls`、`mock.unique_messages`）。
- 回执延迟由 `Clock` 驱动（默认 `delivered` +2s，`read` +5s）；`poll_receipts()` 只返回已到期回执。
- 回执队列在内存；`POST /demo/flush-receipts` 可立即产出。
- Mock 不记录完整号码到任何日志。

## 5. 频控在演示中的可见性

种子频控：`GLOBAL 5 条 / 10 秒`、`PER_RECIPIENT 1 条 / 86400 秒`。8 个可发送收件人 → 前 5 个立即发送，其余 3 个被 `DEFERRED(RATE_LIMIT_GLOBAL)`，约 10 秒后继续——`send_log` 中可见。重试退避种子：`base=2s, cap=60s, jitter=0.2, max_attempts=3`。

## 6. 筛选评测集

`expected_label ∈ {relevant, borderline, irrelevant}`：A→relevant，B→borderline，C+D→irrelevant。`scripts/eval_screening.py` 导入全部数据并按默认配置评分后输出：

- **Precision** = 被自动入池且标注为 relevant 的数 ÷ 被自动入池的总数（目标 ≥ 0.95）
- **Recall** = 被自动入池且标注为 relevant 的数 ÷ relevant 总数（目标 ≥ 0.85，即 20 条至少 17 条）
  - 标注层面共有 24 条 `relevant`（A 类 20 + E 类 4）；E 类 4 行是重复行，导入后不产生新 lead，F 类 4 行非法不入库。Precision / Recall 必须按「导入后的 lead」计算（relevant 分母为 20），E/F 行不参与。
- **边缘带准确率** = B 类落入 `PENDING_REVIEW` 的比例（目标 ≥ 0.75）
- 混淆矩阵 + 每条错判的 `score_reasons`（便于调参，对应 SCR-014）

初始权重见 `modules/screening.md` §6；权重 / 阈值允许按评测结果微调，但调整须记入 `CHANGELOG.md`。

## 6.1 评分手算示例（用于单元测试断言）

| 输入 | 命中与计分 | 结果 |
|---|---|---|
| bio=`Reviewing beauty devices, LED masks & microcurrent tools \| skincare nerd`，region=US，lang=en | microcurrent +25，led mask(s) +25，beauty device(s) +30，skincare +15，地区 +10，语言 +5 = 110 → 截断 100 | APPROVED(AUTO) |
| bio=`Skincare lover \| beauty blogger \| tips & routines`，US/en | skincare +15，beauty +10，地区 +10，语言 +5 = 40 | PENDING_REVIEW（恰在下限） |
| bio=`Wholesale beauty device supplier — DM for dropship`，无地区语言 | beauty device +30，wholesale −30，dropship −30 = −30 → 截断 0 | DISCARDED |

## 7. 演示重置

`python scripts/seed.py --reset`（或 DEMO_MODE 下 `POST /demo/reset`）：清库 → 写入默认配置（关键词、频控、设置、默认模板）→ 导入 `mock_blacklist.csv` → **不**自动导入线索（线索导入是演示步骤之一，授权随线索行入库）。
