# tasks：任务清单（给 AI 一次一个）

> 版本 v1.0（定稿）· 规则：一次只做一个任务；先写测试再实现；覆盖的 AC 全部有测试且全量 `pytest` / `ruff` 绿，才可勾选。
> AC 记法：`CAMP-005` = `AC-CAMP-005`；`CAMP-010~014` = 010 到 014 连续。优先级见各模块 spec。
> 估时 = AI 生成 + 人工审查 + 调试 的墙钟时间。

## 任务总表

| ✓ | ID | 任务 | 覆盖 AC | 依赖 | 估时 | 里程碑 |
|---|---|---|---|---|---|---|
| ☑ | T-00 | 项目脚手架：`pyproject`、应用工厂、`core/{config,db,clock,logging,errors}`、统一错误、鉴权、请求 ID 中间件、`/healthz`、`conftest`（FakeClock / 临时库 / 网络守卫）、架构守卫测试 | SYS-001, SYS-002, SYS-003, SYS-004, SYS-005, SYS-006, SYS-013, AUD-009 | — | 1.0h（实际 ≈0.5h） | M1 |
| ☑ | T-01 | ORM 模型（12 张表）、约束 / 索引、`audit_log` 触发器、SQLite PRAGMA 与 `BEGIN IMMEDIATE` 钩子 | SYS-008, AUD-003 | T-00 | 1.0h（实际 ≈0.6h） | M1 |
| ☑ | T-02 | 手机号与脱敏工具：规范化 / E.164、加密 / 哈希 / 掩码、`mask_phone`、`redact()`、日志过滤器 | AUD-007（单元部分）, AUD-008 | T-00 | 0.5h（实际 ≈0.5h） | M1 |
| ☑ | T-03 | 审计服务：同事务写入、哈希链与校验、查询 API | AUD-001, AUD-002, AUD-004, AUD-005, AUD-011 | T-01, T-02 | 1.0h（实际 ≈0.8h） | M1 |
| ☑ | T-04 | 配置管理与种子：关键词 / 频控 / 设置注册表 CRUD、环境变量启动校验、`seed.py` | CFG-001, CFG-002, CFG-003, CFG-004, CFG-006, CFG-007, CFG-008, SCR-011 | T-01, T-03 | 1.0h（实际 ≈1.8h） | M1 |
| ☑ | T-05 | 线索导入：`LeadSource`（Mock / CsvJson / InstagramStub）、导入服务与 API、**`data/mock_leads.json` 与 `mock_blacklist.csv`（按 05 号文档）** | LEAD-001~013, LEAD-015 | T-02, T-03, T-04 | 2.0h（实际 ≈2.2h） | M1 |
| ☑ | T-06 | 评分引擎（`domain/scoring`）+ 筛选服务与 API | SCR-001~010, SCR-012, SCR-013, SCR-015 | T-04, T-05 | 1.5h（实际 ≈2.1h） | M2 |
| ☑ | T-07 | 目标池与人工审核（单条 / 批量）、池查询 | POOL-001~005 | T-06 | 1.0h（实际 ≈1.5h） | M2 |
| ☑ | T-08 | 模板服务：版本化、审核、变量白名单、渲染（`domain/render`）、预览 | TPL-001~004, TPL-006~009 | T-04 | 1.0h（实际 ≈1.8h） | M2 |
| ☑ | T-09 | 合规服务：consent、suppression、入站文本判定（服务层）、合规类闸门判定函数、静默时段；池的"可触达预估" | COMP-001, COMP-002, COMP-003, COMP-005, COMP-008~013, POOL-006 | T-05, T-07 | 1.5h（实际 ≈2.0h） | M2 |
| ☑ | T-10 | Messenger 接口与实现：`MockMessenger`（确定性矩阵 / 幂等）、`WhatsAppCloudStub`、契约测试 | CAMP-030, CAMP-031 | T-00 | 1.0h（实际 ≈1.2h） | M3 |
| ☑ | T-11 | 任务创建（目标快照、幂等键）、状态机、控制接口（start/pause/resume/cancel 的状态层）、任务 / 明细查询 | CAMP-001~004, CAMP-027, CAMP-029 | T-07, T-08, T-09 | 1.5h（实际 ≈2.0h） | M3 |
| ☑ | T-12 | 发送引擎 A：Worker、原子认领与租约、Processor、完整闸门链、全局 / 单收件人频控、`send_log` | CAMP-005, CAMP-010~014, CAMP-018, CAMP-025, COMP-004, COMP-007, TPL-005 | T-09, T-10, T-11 | 2.0h（实际 ≈2.3h） | M3 |
| ☑ | T-13 | 发送引擎 B：失败分类、退避重试、超时、暂停 / 恢复 / 取消语义、租约回收与重启恢复、自动完成、配置实时生效 | CAMP-006~009, CAMP-015~017, CAMP-019, CAMP-023, CAMP-026, CFG-005 | T-12 | 2.0h（实际 ≈2.5h） | M3 |
| ☑ | T-14 | 回执处理与 Webhook：状态回执、入站 STOP、签名校验、演示辅助端点 | CAMP-020, CAMP-021, COMP-006, SYS-009, SYS-012 | T-13 | 1.0h（实际 ≈1.6h） | M4 |
| ☑ | T-15 | 熔断与干跑预览 | CAMP-022, CAMP-024 | T-13 | 1.0h（实际 ≈1.3h） | M4 |
| ☑ | T-16 | `send_log` 查询与任务时间线 | AUD-006, AUD-010 | T-12, T-03 | 1.0h（实际 ≈0.4h） | M4 |
| ☐ | T-17 | 统计：任务统计、列表摘要、全局总览 | STAT-001~007 | T-13 | 0.5h | M4 |
| ☐ | T-18 | 管理页（★ 项优先）+ `docs/ui-checklist.md` | UI-001~011 | T-14, T-16, T-17 | 3.0h | M5 |
| ☐ | T-19 | `demo.py`、`eval_screening.py`；用评测结果微调权重 / 阈值并更新 spec | SYS-011, SCR-014 | T-14, T-06 | 1.0h | M5 |
| ☐ | T-20 | 集成与 E2E 测试补齐（E2E-1~10）、泄漏扫描、冒烟测试、优雅关闭、`ac_coverage.py` | SYS-007, SYS-010, AUD-007（泄漏扫描部分） | 全部 | 1.5h | M5 |
| ☐ | T-21 | 文档：README、数据模型与流程说明、`compliance-risk.md`、`ai-usage.md` 定稿 | —（交付物 2、3、6） | T-20 | 2.5h | M6 |
| ☐ | T-22 | 演示脚本 `docs/demo-script.md`、彩排 ×2、全新目录克隆验证、提交 | —（交付物 7） | T-21 | 2.0h | M6 |

合计约 **31.5 小时**。未排期的 P2：`LEAD-014`、`POOL-007`、`POOL-008`、`COMP-014`、`CAMP-028`。

## 通用约定（每个任务都适用）

- 开始前：AI 复述任务编号、覆盖的 AC、将新增 / 修改的文件（≤ 5 行）；**只按 AGENTS.md §1 读取本任务相关的 spec 小节，不默认通读全部文档**。
- 完成时：测试全绿；`tasks.md` 勾选并写实际耗时；`docs/ai-usage.md` 追加记录；按 `plan.md` §3 做人工审查；提交 `T-xx: …`。
- 发现 spec 问题：停；写入 `CHANGELOG.md` 待决问题；确认后先改 spec。

## 任务补充说明（仅列需要提醒的点）

- **T-00**：`Clock` 协议与 `FakeClock` 在此建立，后续一切时间依赖都注入；`create_app(clock=..., messenger=..., settings=...)` 工厂必须支持注入，否则后面测试无法确定性。
- **T-01**：`audit_log` 触发器与 `task_item` 唯一约束的测试要用原生 SQL 直接冲击。
- **T-02**：号码处理的唯一入口——其他模块一律调用这里的函数，不得自行拼接号码处理逻辑。
- **T-03**：`record()` 必须接收调用方的 Session，不得自行 `commit`。
- **T-05**：Mock 数据的构成与预期必须逐条对齐 `05-mock-data.md` §2–§3（52 行；报告 `44/4/4/1`）；评分权重可在 T-19 微调。
- **T-09**：闸门判定函数放在 `domain/gates.py`，供引擎与池预估共用（AC-POOL-006 的一致性测试）。
- **T-12**：认领用 `BEGIN IMMEDIATE`；Provider 调用**不得**在写事务内；闸门判定每条实时查库。
- **T-13**：崩溃恢复测试用"手工构造 `SENDING` + 过期租约"，不要真的杀进程。
- **T-18**：禁止 `innerHTML` 赋值；先做 ★ 页，配置页最后做。
- **T-10**：AC-SYS-003 的期望路径清单 = `04-api-contract.md` 中全部非 P2 的 `/api/v1` 端点 + `/healthz`；`WhatsAppCloudStub` 只返回 `501 PROVIDER_NOT_ENABLED`，不建立任何网络路径。
- **T-11**：AC-SYS-006 的 `MESSENGER_PROVIDER=whatsapp_cloud` 前置检查在 `POST /campaigns/{id}/start` 返回 `501 PROVIDER_NOT_ENABLED`；检查顺序按 Q-11（模板 APPROVED → 非终态明细 → Provider 可用），失败时任务状态不变。
- **T-19**：权重调整后须同步更新 `screening.md` §6 与 `05-mock-data.md` §6.1，并记入 `CHANGELOG.md`；`mock_leads.json` 有 24 条 `expected_label=relevant`（A 类 20 + E 类 4），E 类 4 行是重复行、导入后不产生 lead，Precision/Recall 必须按「导入后的 lead」计算（relevant 分母 20），E/F 行跳过。另：`05-mock-data.md` §6 要求的 `mock_blacklist.csv` 黑名单导入至今未实现（seed 与 `/demo/reset` 都未导入），需在本任务补上并加测试。
