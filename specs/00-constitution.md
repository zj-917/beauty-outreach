# 00 项目宪法（Constitution）

> 版本 v1.0 · 状态 定稿（2026-11-13 冻结） · **本文件优先级最高**：与其他 spec 冲突时以本文件为准。

## 1. 使命

构建一个**可演示、可审计、合规优先**的原型系统：
`线索导入 → 筛选评分 → 目标池 → 批量触达任务 → 发送（闸门 + 频控 + 重试）→ 状态回写 → 审计`。

原则优先级（冲突时从上到下）：
**合规 > 正确性与可靠性 > 可解释与可审计 > 可演示 > 代码整洁 > 功能数量**

## 2. 合规红线（R-xx）

| 编号 | 红线 | 在代码中的体现 |
|---|---|---|
| R-1 | 数据来源只能是 Mock、企业自有授权数据（CSV/JSON 导入）、平台官方授权接口。禁止爬虫、模拟登录、绕过风控、购买或抓取第三方号码。 | 只提供 `MockSource` / `CsvJsonSource`；`InstagramApiStub` 恒返回 501 |
| R-2 | 外部平台默认走 Mock；真实 Provider 只保留 Stub 且默认禁用；测试禁止真实网络。 | `MESSENGER_PROVIDER=mock`；socket 守卫夹具 |
| R-3 | **无授权不触达**：仅当 `consent=GRANTED` 且不在任何 suppression 名单时才可发送。 | Gate：SUPPRESSION → CONSENT |
| R-4 | **退订 / 黑名单绝对优先**：任何任务、配置、人工操作都不能绕过。 | 无 force 类参数；Gate 顺序固定 |
| R-5 | 退订必须可达且即时生效：每条消息含退订指引；入站 `STOP` 立即写入 suppression；原型中退订不可撤销。 | 模板自动追加页脚；COMP-006/007/008 |
| R-6 | 不重复发送：同一任务同一收件人只发一次；跨任务同模板同号码也不重复。 | 幂等键 + `ALREADY_CONTACTED` |
| R-7 | 频控不可关闭：始终至少存在一条启用的 GLOBAL 规则和一条启用的 PER_RECIPIENT 规则。 | CFG-008 |
| R-8 | 隐私：手机号加密存储 + HMAC 哈希 + 脱敏展示；日志 / 审计 / API / UI 不出现完整号码、token、密钥、消息正文；只采集 spec 列出的字段。 | `core/security.py`；AUD-007/008/011 |
| R-9 | 审计不可篡改：`audit_log` 只追加；与业务变更同事务提交。 | SQLite 触发器；AUD-002/003 |
| R-10 | 筛选透明：每个评分给出可解释原因；人工可覆盖；人工决定不被自动流程覆盖。 | `score_reasons`；SCR-012 |
| R-11 | 文档诚实：README / 合规说明如实写明 Mock 与真实平台的差异，以及生产化还需要什么。 | 交付物 `docs/compliance-risk.md` |

## 3. 技术约束（TC-xx）

- **TC-1** Python ≥ 3.11；FastAPI；Pydantic v2；SQLAlchemy 2.x；SQLite（WAL）。
- **TC-2** 单进程 + 进程内单 Worker 线程；**不引入** Redis / Celery / 消息队列 / ORM 之外的数据库。
- **TC-3** 依赖白名单（运行）：`fastapi`、`uvicorn[standard]`、`sqlalchemy`、`pydantic`、`pydantic-settings`、`cryptography`、`python-multipart`、`tzdata`（Windows 下 `zoneinfo` 需要）。
  （开发）：`pytest`、`httpx`、`ruff`、`pytest-cov`。新增依赖须先在 `specs/CHANGELOG.md` 记录理由。
- **TC-4** 管理页：原生 HTML + JS，**无构建步骤**，由 FastAPI `StaticFiles` 提供。
- **TC-5** 跨平台：在 Windows / macOS / Linux 上命令一致；不依赖 `make`；所有脚本用 `python scripts/xxx.py` 运行。
- **TC-6** 所有时间用 UTC 存储；业务代码通过 `Clock` 取时间（见 AGENTS.md §3）。
- **TC-7** 不做数据库迁移工具（`create_all` 即可），在 README 说明为已知限制。

## 4. 质量标准（Q-xx）

- **Q-1** 分层与依赖方向见 `02-architecture.md` §2，违反即缺陷。
- **Q-2** 每个 AC 至少一个测试，函数名带 AC 编号；P0 的 AC 必须全部通过。
- **Q-3** `domain/` 与 `engine/` 行覆盖率目标 ≥ 85%（参考值，不作为阻断条件）。
- **Q-4** 测试必须确定性：不 sleep、不依赖真实时间、不依赖网络、不依赖执行顺序。
- **Q-5** 任何输出（API 响应、日志、审计）都不得出现完整手机号——由一条全局"泄漏扫描"测试兜底（AC-AUD-007）。

## 5. SDD 流程与变更控制

1. 规格先行：先有 spec 与 AC，后有测试，最后才有实现。
2. 任务粒度：`tasks.md` 中每项 ≤ 约 3 小时，明确"覆盖哪些 AC"。
3. 变更控制：实现中发现 spec 有问题 → 停 → 记入 `specs/CHANGELOG.md`「待决问题」→ 人类确认 → 先改 spec 再改代码。
4. 优先级：**P0** 必做（演示与评分主路径）；**P1** 应做（时间允许）；**P2** 可做（默认不做）。
5. 追溯：`scripts/ac_coverage.py`（任务 T-20）输出「AC → 测试」对照表，用于答辩展示。

## 6. 完成定义（Definition of Done）

一个任务完成，当且仅当：

- [ ] 任务所列 AC 均有测试，且 `python -m pytest -q` 全绿；
- [ ] `python -m ruff check .` 无告警；
- [ ] 未引入红线违规（尤其是手机号 / token 泄漏、真实网络调用）；
- [ ] `tasks.md` 已勾选；`docs/ai-usage.md` 已追加记录；
- [ ] 若改动了行为，对应 spec 与 `CHANGELOG.md` 已同步。

## 7. 明确不做（全局非目标）

真实 Instagram 采集 · 真实 WhatsApp Business API 对接 · 多租户与权限体系 · 分布式部署 · 数据库迁移 · LLM 评分（预留接口，默认关闭，本期不实现）· 多语言界面 · 用户重新订阅流程。
