# AI 编程助手使用说明

> 这是交付物之一，也是答辩素材。**从 SDD 阶段起就开始如实记录**，不要事后补写、不要美化。

## 1. 工具与分工

| 环节 | 工具 | 我做什么 | AI 做什么 |
|---|---|---|---|
| 需求分析与可行性评估 | Claude | 提出问题、做取舍 | 拆解需求、指出风险（如号码来源矛盾） |
| 规格（SDD）起草 | Claude | **评审、裁剪、拍板待决问题** | 起草 `specs/` 全部文件与 AC |
| 编码与测试 | Codex / Claude Code（待填） | 逐任务审查、纠错、验收 | 按 `tasks.md` 一次一个任务：先测后码 |
| 文档 | AI 辅助 | 核对事实、补充亲身理解 | 起草 README / 合规说明 |

## 2. 工作方式（SDD 循环）

`规格 → 任务 → 先写测试(带 AC 编号) → 实现 → 全量测试 + ruff → 人工审查 → 提交`

关键约束：
- 项目根的 `AGENTS.md` 规定了红线、工作流与"遇到歧义先停下提问"。
- 每个测试函数名带 AC 编号，`scripts/ac_coverage.py` 生成「AC → 测试」对照表（`docs/ac-coverage.md`）。
- 一次只给 AI 一个任务（≤ 约 3 小时），上下文 = `AGENTS.md` + 该任务相关的 spec，避免漂移。

## 3. 任务记录

| 任务 | 日期 | AI 产出 | 我审查时发现 / 纠正的问题 | 采纳程度（主观） | 耗时（估→实） |
|---|---|---|---|---|---|
| SDD v0.1→v1.0 | 2026-11-13 | 起草宪法 / 架构 / 数据模型 / 模块规格 / 测试计划 / 任务清单 | 人类评审后确认 Q-1~Q-8；AI 通读发现的 Q-9（AC-SYS-003 的 OpenAPI 路径清单）、Q-10（AC-LEAD-011 二次导入计数）、Q-11（start 的 Provider 前置检查）经人类确认并先改 spec；人类要求「执行任务时只读相关 SDD 文档、不默认通读全部 Markdown」，已写入 AGENTS.md §1 | 规格全部采纳；另按评审补充 3 条澄清与 1 条工作规则 | — |
| T-00 | 2026-11-13 | 项目脚手架：`pyproject`、`core`（clock/config/db/errors/logging/security）、应用工厂（可注入 settings/clock/messenger）、统一错误、鉴权与请求 ID 中间件、`/healthz`、`conftest`（临时库 / 网络守卫 / FakeClock）与 8 个 AC 测试文件 | （待人工审查）AI 自查发现并修正：未预期异常由 Starlette 最外层 `ServerErrorMiddleware` 生成 500，绕过了请求 ID 中间件 → 错误处理器改为从 `request.state` 取 id 并自行回写 `X-Request-ID`。注意：AC-SYS-003 的「全部路径」与 AC-SYS-006 的「whatsapp_cloud → 501」需随 T-10/T-11 的端点补齐，当前 T-00 只覆盖网络守卫与 `/healthz`/docs | 待审查 | 1.0h→≈0.5h |
| T-01 | 2026-11-14 | 12 张 ORM 表（字段、CHECK、唯一约束、索引、suppression 部分唯一索引）、`UtcDateTime`、`audit_log` 只追加触发器、`create_schema` 并接入应用创建；原生 SQL 测试覆盖 PRAGMA、外键、`BEGIN IMMEDIATE`、`task_item` 双唯一约束、审计 UPDATE/DELETE 拒绝 | （待人工审查）ruff 的 SIM117/SIM300 提示已按建议合并 `with` 并调整断言方向；无功能改动 | 待审查 | 1.0h→≈0.6h |
| T-02 | 2026-11-14 | `domain/phone.normalize_phone`（E.164）、`domain/masking`（`mask_phone` / `redact` / `redact_log_text`）、`core/security.PhoneCipher`（Fernet + HMAC-SHA256）、`core/logging.RedactionFilter`（redactor 由应用工厂注入，保持 core 不依赖 domain）；5 个单元测试文件，覆盖 AUD-007 单元部分与 AUD-008，并为 LEAD-003/007/008 提供早期单元覆盖 | 人类审查发现：`redact()` 会把 ISO 时间戳误当号码掩码（如 `2026-11-14T09:00:00Z` → `2026****1-14T09:00:00Z`），会破坏 T-03 的审计快照 → 已按建议增加日期前缀跳过并补测试。ruff 仅提示一处 docstring 超长，已缩短。日志脱敏选择「domain 提供纯函数、core 过滤器接收注入」而非在 core 复制正则 | 按人类建议修正 1 处 | 0.5h→≈0.5h |
| T-03 | 2026-11-14 | AuditRepository（插入、过滤分页查询、按序读取链）、AuditService（调用方 Session 内写入、`redact` 快照、SHA-256 哈希链、verify）、`GET /api/v1/audit-logs` 与 `/verify`、X-Operator 依赖、Z 后缀时间序列化；6 个测试文件覆盖 AUD-001/002/004/005/011 | （待人工审查）ruff B008 提示 FastAPI 默认参数调用 → 改用 `Annotated`；无功能改动。同事务/回滚在服务层验证，查询与 verify 在 API 层验证；链的并发安全依赖 T-01 的 BEGIN IMMEDIATE | 待审查 | 1.0h→≈0.8h |
| T-00 | | | | | |

## 4. AI 犯过的典型错误（持续追加）

> 例：「AI 把 `datetime.now()` 写进了业务代码，违反时钟注入 → 我要求改为 `Clock` 并加了静态扫描测试」。
> 这一节最能体现"我是在驾驭 AI，而不是被 AI 驾驭"。

-

## 5. 效率与反思（收尾时填写）

- 哪些环节 AI 提效最明显：
- 哪些环节 AI 最不可靠、需要重点审查：
- 如果重来，我会改变的做法：
