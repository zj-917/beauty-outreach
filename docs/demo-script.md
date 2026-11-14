# 10 分钟演示与答辩脚本

> 交付物 7。对应 `specs/plan.md` §6 的骨架；所有步骤都能在管理页完成（AC-UI-011），命令行只用于准备与备份。
> 彩排与克隆验证记录见文末；UI 逐条验收仍以 `docs/ui-checklist.md` 为准。

## 0. 演示前准备（开始前 5 分钟）

1. `.env` 确认：`MESSENGER_PROVIDER=mock`、`WORKER_ENABLED=true`、`DEMO_MODE=true`、`TICK_SECONDS=1`。
2. 启动（终端 A，保持可见）：

   ```bash
   python scripts/seed.py
   ```

   ```bash
   python -m uvicorn app.main:app --reload
   ```

3. 浏览器窗口 1：<http://127.0.0.1:8000/admin/>，右上角填 `ADMIN_TOKEN`（默认 `dev-admin-token`）与操作人，点「保存」。
4. 终端 B（备份）：`python scripts/demo.py --fast` 先跑一遍，确认输出 `DEMO OK`；页面不要滚动到关键内容之外。
5. 预置标签页：`docs/ac-coverage.md`、`docs/ai-usage.md`、`docs/compliance-risk.md`。

> 全部数据为 Mock；号码是虚构的 `+1555555xxxx`。演示中的 STOP 使用 **`+15555559004`**（Mock 数据里 `glow.micro` 的号码），原因见 3.3。

## 1. 时间轴

| 时间 | 内容 | 关键操作 | 预期 |
|---|---|---|---|
| 0:00–1:00 | 架构与合规前提 | 概览页与一张架构图 | 讲清 Mock、号码来源假设、红线 |
| 1:00–3:00 | 导入 → 筛选 → 人工审核 | 导入 Mock、运行筛选、审核 1 条 | 52/44/4/4/1；20/8/16；审核入池 |
| 3:00–6:00 | 建任务 → 干跑 → 启动 → 暂停 → STOP → 恢复 | 任务向导、预览、控制按钮、合规演示面板 | 预览 20/8/0；最终 4/3/13 |
| 6:00–8:00 | 失败、重试、回执、幂等 | 明细过滤、原因码、回执按钮 | 三类失败、重试 4 次、UNSUBSCRIBED 2 |
| 8:00–9:00 | 审计与日志 | 任务明细「日志」、审计日志查询 | 脱敏号码、request_id、动作可追溯 |
| 9:00–10:00 | 测试、覆盖表、AI 使用、风险 | 终端与文档 | 505 passed、未覆盖 P0=0 |

计时提示：3:30 左右点「启动」，让任务在讲解闸门时后台运行（约 20–30 秒完成）；6:00 前一切终态。

## 2. 逐步操作

### 2.1 开场：架构与合规前提（0:00–1:00）

- 打开 `/admin/`，停在「概览」：线索 / 池 / 任务 / 最近 24h 授权 / 名单统计。
- 一句话架构：`api → services → (domain, engine, repositories) → providers`，模块化单体，Provider 只用 Mock；真实 WhatsApp 实现是 Stub，调用即 501。
- 主动交代号码来源假设 A-1：Instagram 公开资料没有手机号，本系统只处理企业自有授权数据 / 用户留资，导入行里带 `phone + consent`。
- 红线一句话：无授权不触达、退订/黑名单绝对优先、同一收件人不重复发送、全程脱敏（`docs/compliance-risk.md`）。

### 2.2 导入 → 筛选 → 人工审核（1:00–3:00）

1. 左侧「线索」→ 点「导入 Mock 数据」。
   - 导入报告：**总数 52 / 导入 44 / 重复 4 / 无效 4 / 警告 1**。
   - 展开错误列表：第 45、46 行重复用户名，第 47 行号码被占用，第 49–52 行非法用户名 / 链接——逐行原因可见。
2. 点「运行筛选」。
   - 结果：**处理 44 / 自动通过 20 / 待确认 8 / 丢弃 16 / 未变 0**。
   - 讲评分：关键词权重（正/负）、地区/语言/短简介调整、最长匹配；每条线索有 `score_reasons` 与 `top_keyword`。
3. 筛选区：状态选 `PENDING_REVIEW`，「查询」。
   - 8 条，分数 40–47，均为无号码的边缘线索（可触达预估 `NO_PHONE`）。
4. 对第一行（`glow.note`，47 分）填备注「演示：人工覆盖」→ 点「通过」。
   - 再按状态 `APPROVED` + 搜索 `glow.note` 验证已入池（池 20→21）。
   - 讲：人工决定不会被重新评分覆盖，且写审计。

> 本任务在向导里用「最低分 70」建任务，仍只覆盖原 20 条主池线索；这一步只演示人工覆盖与审计。

### 2.3 建任务 → 干跑预览（3:00–3:30）

1. 左侧「任务」→ 名称填 `T-22 演示` → 模板选 `greeting v1` → 最低分填 `70` → 点「创建并干跑预览」。
2. 预览（只读、无副作用）：
   - **明细总数 20 / 将尝试 8 / 将释放 0**；
   - 将跳过：`NO_PHONE 7、NO_CONSENT 1、CONSENT_REVOKED 1、BLACKLISTED 2、UNSUBSCRIBED 1`；
   - 页面注明「频控延迟与静默时段未模拟」。
3. 讲：预览把 DRAFT 当作即将启动，按闸门 2–7 预判；真正发送时还有单收件人频控、静默时段、全局频控三道时间闸门。

### 2.4 启动 → 暂停 → 模拟 STOP → 恢复（3:30–6:00）

1. 点「打开任务详情」→ 点「启动」→ **立刻点「暂停」**（10 秒内完成，原因见下）。
2. 左侧「合规」→ 演示面板：
   - 号码填 **`+15555559004`** → 点「模拟收到 STOP」；
   - 预期提示：`已登记退订（UNSUBSCRIBE）；运行中任务的相关明细会在后续处理时被跳过。`
3. 回到「任务」→ 详情 → 点「恢复」，右上出现「运行中：每 2 秒自动刷新」。
4. 利用等待时间讲闸门链（固定 9 级，首个非放行者生效）：
   `TASK_ACTIVE → SUPPRESSION → PHONE → CONSENT → TEMPLATE → DUPLICATE → RECIPIENT_FREQ → QUIET_HOURS → GLOBAL_RATE`；
   前 5 条发送后，`GLOBAL 5/10s` 规则把其余明细推迟到下一个窗口——这正是 `glow.micro`（9004）在暂停期间还没被发送、于是被 STOP 拦截的原因。
5. 任务 `COMPLETED` 后读卡片：
   **成功 4 / 失败 3 / 跳过 13 / 成功率 0.5714 / 重试次数 4**；
   下方两行：跳过原因与失败原因（见 §3）。

### 2.5 失败、重试、回执与幂等（6:00–8:00）

在任务详情的「明细」表（可按状态 / `reason_code` 过滤）：

| 收件人（用户名 / 脱敏号码） | 状态 | 原因 / 尝试 | 讲什么 |
|---|---|---|---|
| `glow.micro` / `+155****9004` | SKIPPED | `UNSUBSCRIBED`，0 次 | 暂停期间的 STOP 即时生效，Provider 零调用 |
| `glow.led` / `+155****9002` | FAILED | `MAX_ATTEMPTS_EXCEEDED`，3 次，最后 `SERVER_ERROR` | 指数退避 + 抖动，耗尽后失败 |
| `glow.yi` / `+155****9003` | FAILED | `INVALID_NUMBER`，1 次 | 永久失败不重试 |
| `glow.glow` / `+155****9005` | FAILED | `DELIVERY_FAILED` | 受理后失败回执（Mock 2 秒后产生） |
| `glow.radio` / `+155****9001` | SENT/DELIVERED | 3 次 | 前两次超时，第三次成功；同键重发不产生第二条消息 |

- 合规页「立即产出回执」：立即应用队列中的 Mock 回执（送达 / 已读 / 失败），任务统计随之更新。
- 幂等：任务结束后「启动」按钮已禁用；同一任务重复 start 在 API 层是 no-op（`CAMPAIGN_STARTED` 审计只有 1 条），崩溃恢复用租约 + 同键重发（E2E-3、E2E-4 测试覆盖）。

### 2.6 审计与日志（8:00–9:00）

1. 明细行右侧「日志」→ 自动跳到「日志 → 发送日志」，带 `task_id/item_id`：
   - 每次闸门决策与 Provider 调用一行（`GATE / PROVIDER / RECEIPT`），号码列为脱敏值。
2. 「审计日志」：动作填 `CAMPAIGN_STARTED`、实体 id 填任务号 → 查询；展示 actor、时间、`request_id`。
   - 讲：审计与业务同事务、只追加、SHA-256 哈希链可校验；快照里的号码已脱敏。
3. 切到「概览」点「刷新」，总览数字与任务一致。

### 2.7 收尾：测试、覆盖表、AI 使用与风险（9:00–10:00）

- 终端 B（预先跑好截图亦可，现场只跑快的一组）：

  ```bash
  python -m pytest -q tests/e2e
  ```

  ```bash
  python scripts/ac_coverage.py
  ```

- 打开 `docs/ac-coverage.md`：**142 条 AC、已覆盖 129、未覆盖 P0 = 0**；UI P1★ 依赖人工清单。
- 打开 `docs/ai-usage.md`：如何用 AI（SDD、一次一任务、先测后码）与真实踩坑记录。
- 打开 `docs/compliance-risk.md`：Mock 与真实平台差异、生产化清单（Postgres、令牌桶、KMS、SSO、模板审核、opt-in 记录）。
- 结束语：原型把"合规闸门、幂等、审计"放在可测试的核心层；上生产只替换 Provider 与基础设施。

## 3. 预期数字（与 `05-mock-data.md` §3、`scripts/demo.py` 对齐）

### 3.1 导入与筛选

| 阶段 | 数字 |
|---|---|
| 导入 | 总数 52，导入 44，重复 4，无效 4，警告 1 |
| 筛选 | 处理 44，自动通过 20，待确认 8，丢弃 16，未变 0 |
| 预览（最低分 70） | 总数 20，将尝试 8，将释放 0；跳过 `NO_PHONE 7 / NO_CONSENT 1 / CONSENT_REVOKED 1 / BLACKLISTED 2 / UNSUBSCRIBED 1` |

### 3.2 最终统计（含一次演示 STOP）

| 指标 | 值 |
|---|---|
| 总数 | 20 |
| 成功 | 4（`0101`、`0102`、`0103`、`9001`） |
| 失败 | 3（`MAX_ATTEMPTS_EXCEEDED`、`INVALID_NUMBER`、`DELIVERY_FAILED`） |
| 跳过 | 13（`NO_PHONE 7`、`NO_CONSENT 1`、`CONSENT_REVOKED 1`、`BLACKLISTED 2`、`UNSUBSCRIBED 2`） |
| 成功率 | 0.5714（4/7） |
| 重试次数合计 | 4 |

不带 STOP 的基线是成功 5 / 跳过 12（`scripts/demo.py --fast` 不含 STOP 时同样如此）；演示脚本按 `05-mock-data.md` §3 的注记包含 STOP。

### 3.3 为什么 STOP 选 `+15555559004`

- 它是 Mock 数据中 `glow.micro` 的号码，属于自动入池的 20 条；
- 前 5 条发送会占满 `GLOBAL 5/10s` 窗口，`9004` 因此被推迟到下一个窗口，**启动后 10 秒内暂停即可保证它还没被发送**；
- 恢复后它先过 SUPPRESSION 闸门 → `SKIPPED(UNSUBSCRIBED)`，同时让最终数字与 `scripts/demo.py` 完全一致。

## 4. 应急预案

| 情况 | 处理 |
|---|---|
| UI 卡住 / 数据混乱 | 「合规 → 重置演示数据」清库并重新播种，从 2.2 重来（约 40 秒） |
| 后台 Worker 未及时推进 | 切终端 B：`python scripts/demo.py --fast`（约 2 秒）展示同一组数字，回到 UI 讲审计与日志 |
| 浏览器不可用（远程 / 录屏） | 播放 `python scripts/demo.py` 真实时钟录屏（约 22 秒输出七步与断言） |
| 时间不够 | 跳过 2.5 的逐行讲解与 2.6 的审计查询，保留：导入 → 筛选 → 预览 → STOP → 最终统计 → 覆盖表 |
| 被问真实接口 | 明确：未实现、也不允许；Stub 调用即 501，测试禁网，生产化清单见 `docs/compliance-risk.md` §6 |

## 5. 高概率提问与一句话答案

- **为什么用 Mock？** 官方接口不提供任意用户搜索、且题目禁止爬虫；发送需要企业认证与模板审核，原型只做 Mock + Stub。
- **号码哪来的？** A-1：企业自有授权数据 / 用户留资，导入行带 `phone + consent`；原型无法验证真实性，这是 CR-1。
- **如何保证不重复发送？** 幂等键（task:lead:template）+ 全局唯一约束 + 同键重发 + 跨任务同模板防重。
- **退订即时生效吗？** 每条实时查库、不缓存；STOP 同事务写 suppression 并撤销授权。
- **崩溃会不会双发？** 租约过期回收 + 同幂等键重发；Mock 对同键返回同一消息 id。真实 Provider 无幂等键是生产风险 CR-6。
- **怎么上生产？** `docs/compliance-risk.md` §6：真实 API 接入、Postgres + 多 Worker、Redis 令牌桶、KMS、SSO、保留期与 DSAR。

## 6. 彩排记录

### 彩排 1（2026-11-14，UI 等价流程）

用 `TestClient` 按本脚本的接口序列重放（重置 → 导入 → 筛选 → 审核 → 建任务最低分 70 → 预览 → 启动/暂停 → STOP `+15555559004` → 恢复 → Worker 跑完）：

- 首次发现：DRAFT 任务的干跑预览被闸门 1 全部判为「将释放」，UI 向导看不到任何有效信息 → 已修正为 DRAFT 按"即将启动"评估（`specs/CHANGELOG.md` v1.9，2026-11-14 经人类确认保留）。
- 修正后：预览 20 / 8 / 0；最终 **成功 4、失败 3、跳过 13**；原因分布与本脚本 §3 完全一致。

### 彩排 2（2026-11-14，真实时钟脚本）

- `python scripts/demo.py`：21 个 tick，**22.3 秒**，输出 `DEMO OK — COMPLETED，success=4，failed=3，skipped=13`。
- `python scripts/demo.py --fast`：**1.9 秒**，数字相同。

### 全新目录克隆验证（2026-11-14）

在系统临时目录 `git clone` 本仓库 → 新建 venv → `pip install -e ".[dev]"` → 复制 `.env.example` → `python scripts/seed.py` →

- `python -m pytest -q`：**505 passed**；
- `python -m ruff check .`：无告警；
- `python scripts/ac_coverage.py`：142 条，已覆盖 129，未覆盖 P0 = 0；
- `python scripts/demo.py --fast`：`DEMO OK`；
- `python -m uvicorn app.main:app`：`/healthz` 返回 `{"status":"ok",...}`，`/admin/` 200。

### 未完成项（如实记录）

- 本环境没有可用的浏览器预览，UI 未逐条点击走查；彩排以"接口等价序列 + demo.py + 克隆验证"完成。
- `docs/ui-checklist.md` 的勾选仍需在答辩前用真实浏览器按本脚本走一遍（预计 15 分钟）。
