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
| T-00 | 2026-11-13 | 项目脚手架：`pyproject`、`core`（clock/config/db/errors/logging/security）、应用工厂（可注入 settings/clock/messenger）、统一错误、鉴权与请求 ID 中间件、`/healthz`、`conftest`（临时库 / 网络守卫 / FakeClock）与 8 个 AC 测试文件 | AI 自查发现并修正：未预期异常由 Starlette 最外层 `ServerErrorMiddleware` 生成 500，绕过了请求 ID 中间件 → 错误处理器改为从 `request.state` 取 id 并自行回写 `X-Request-ID`。注意：AC-SYS-003 的「全部路径」与 AC-SYS-006 的「whatsapp_cloud → 501」需随 T-10/T-11 的端点补齐，当前 T-00 只覆盖网络守卫与 `/healthz`/docs | 全部采纳 | 1.0h→≈0.5h |
| T-01 | 2026-11-14 | 12 张 ORM 表（字段、CHECK、唯一约束、索引、suppression 部分唯一索引）、`UtcDateTime`、`audit_log` 只追加触发器、`create_schema` 并接入应用创建；原生 SQL 测试覆盖 PRAGMA、外键、`BEGIN IMMEDIATE`、`task_item` 双唯一约束、审计 UPDATE/DELETE 拒绝 | ruff 的 SIM117/SIM300 提示已按建议合并 `with` 并调整断言方向；无功能改动 | 全部采纳 | 1.0h→≈0.6h |
| T-02 | 2026-11-14 | `domain/phone.normalize_phone`（E.164）、`domain/masking`（`mask_phone` / `redact` / `redact_log_text`）、`core/security.PhoneCipher`（Fernet + HMAC-SHA256）、`core/logging.RedactionFilter`（redactor 由应用工厂注入，保持 core 不依赖 domain）；5 个单元测试文件，覆盖 AUD-007 单元部分与 AUD-008，并为 LEAD-003/007/008 提供早期单元覆盖 | 人类审查发现：`redact()` 会把 ISO 时间戳误当号码掩码（如 `2026-11-14T09:00:00Z` → `2026****1-14T09:00:00Z`），会破坏 T-03 的审计快照 → 已按建议增加日期前缀跳过并补测试。ruff 仅提示一处 docstring 超长，已缩短。日志脱敏选择「domain 提供纯函数、core 过滤器接收注入」而非在 core 复制正则 | 按人类建议修正 1 处 | 0.5h→≈0.5h |
| T-03 | 2026-11-14 | AuditRepository（插入、过滤分页查询、按序读取链）、AuditService（调用方 Session 内写入、`redact` 快照、SHA-256 哈希链、verify）、`GET /api/v1/audit-logs` 与 `/verify`、X-Operator 依赖、Z 后缀时间序列化；6 个测试文件覆盖 AUD-001/002/004/005/011 | ruff B008 提示 FastAPI 默认参数调用 → 改用 `Annotated`；无功能改动。同事务/回滚在服务层验证，查询与 verify 在 API 层验证；链的并发安全依赖 T-01 的 BEGIN IMMEDIATE | 全部采纳 | 1.0h→≈0.8h |
| T-04 | 2026-11-14 | 设置注册表（26 键，类型/范围/跨字段校验）、关键词/频控/设置服务与 API、同事务审计、最后一条频控规则保护、`load_settings` 环境校验、`scripts/seed.py`（默认设置 / 25 个关键词 / 2 条频控 / greeting v1，幂等并支持 `--reset`）；9 个测试文件 | 决策：seed 作为系统初始化不写 audit（CFG-004 由 API 变更测试覆盖）；模板种子用 name=greeting、version=1 表示 greeting_v1；`SEED_DEFAULTS` 当时未实现，统一走 seed.py；blacklist CSV 导入待 T-05 提供文件；`enabled=false` 不参与评分待 T-06 验证。**审查后修正**：补 `SEED_DEFAULTS=true` 空库启动播种（含测试与 `.env.example`）；`redact_text` 不再把 32 位十六进制 / UUID 请求 ID 当号码掩码；配置 schema 改用 `StrictInt`/`StrictBool`，拒绝 `true→1`、`"30"→30`、`"false"` 等隐式转换；seed 测试改为逐条断言关键词/频控/模板正文；CFG-008 拒绝后断言规则仍启用 | 按审查意见修正 6 处 | 1.0h→≈1.8h |
| T-05 | 2026-11-14 | `domain/lead` 规范化、`providers/lead_source`（Mock / CSV-JSON / InstagramApiStub）、`lead_repo`、`LeadService`（单事务导入、去重合并、授权 upsert、批次审计）、导入与查询 API、`data/mock_leads.json`（52 行）、`mock_blacklist.csv`、`sample_leads.csv`；11 个测试文件 | 决策：黑名单 CSV 实际入库留到 T-09/T-19（本任务只提供文件）；来源选择放在 `LeadService` 静态工厂，避免 `api → providers` 违反分层；授权策略为「已有 GRANTED 不被重复 GRANTED 覆盖，REVOKED 总是生效」；自查发现 3 条 mock 简介不足 10 字符会触发短简介扣分，已加长，并用脚本按 screening §3.2 手算校验 A/B/C/D 的标签与分数区间一致；`04-api-contract.md` 示例中的错误行号 47 与数据实际行号（49–52）不同，计数一致，仅示例细节。**审查后修正**：按 Q-12 澄清并实现「合并补号码不得抢占其他线索的号码」与「`DUPLICATE_PHONE` 行仍应用合法授权」；补测引号 CSV、号码格式去重、重复 GRANTED、未知 source 与合并冲突；回滚测试按 E2E-10 留到 T-20；bio/display_name 原样返回，若其中含号码属用户内容，边界留待 T-21 的 `compliance-risk.md` 记录 | 按审查意见修正 5 处 | 2.0h→≈2.2h |
| T-06 | 2026-11-14 | `domain/scoring`（ASCII 全词 + 复数、中文子串、最长匹配占用、三字段系数、地区/语言/短简介、reasons 与 CLAMP、top_keyword、三档决策）、`ScreeningService`、`POST /leads/screen`、`LEAD_SCREENING_RUN` 审计；15 个测试文件（11 单测 + 4 集成） | 解释/决策：`unchanged` 取「本次重算后状态未变」的条数（APPROVED/REJECTED 不进入候选，也不计入 processed）；`batch_id` 与 `lead_ids` 同时给出时取交集；无启用关键词时 `warning=NO_ENABLED_KEYWORDS` 且照常运行；审计 `after` 固定含计数与阈值，仅批次筛选时附 `batch_id`；Mock 数据评分分布 20/8/16 与 05 号文档标签一致。**审查后修正**：Q-13/Q-14 澄清并固化为 `unchanged` 计数定义、零贡献命中不计入 reasons/top_keyword、batch_id 与 lead_ids 取交集；关键词准备结果按线索集缓存；短简介长度改用 `bio.strip()`；id 范围运行的审计实体改为 `selected` 并记录条数；补 batch 过滤、粘性 id、持久化 reasons/top_keyword 与批次审计测试 | 按审查意见修正 5 处 | 1.5h→≈2.1h |
| T-07 | 2026-11-14 | `PoolService`（池查询、单条 / 批量审核、§3.1 转换表）、`GET /pool`、`POST /leads/{id}/review`、`POST /leads/review-bulk`、`LEAD_REVIEWED` 审计、`LeadView` 审核字段、`lead_repo` 池查询与审核写入；5 个集成测试文件（26 个用例） | 决策：批量审核请求体 spec 未定义，采用 `{"reviews":[{lead_id,decision,note?}]}` 与 `{"results":[{lead_id,ok,error?}]}`，逐条独立提交，失败项不影响后续（Q-18 已于 2026-11-14 经人类确认，spec 已同步）；幂等重复决定仍更新审核人 / 时间并写审计，未提供备注时保留原备注；`GET /leads?status=PENDING_REVIEW` 仅在该状态下按分数降序；池的可触达预估（POOL-006）按排期留给 T-09。自查修正：POOL-005 测试把二次重算候选数算成 42，实际为 44−20 自动入池−2 手工决定=22 | 全部采纳（待人工审查） | 1.0h→≈1.5h |
| T-08 | 2026-11-14 | `domain/render`（变量提取 / 白名单、默认值、清洗与 60 码点截断、单趟替换、退订页脚、1024 上限、`RenderError`）、`TemplateService`（创建 / 草稿编辑 / 新版本 / 审核 / 停用 / 预览）、`template_repo` 扩展、模板 API；8 个测试文件（31 个用例） | 决策：AC-TPL-004 要求「修改 body」，但 04 契约未列模板更新端点、审计动作表也没有 `TEMPLATE_UPDATED` → 补 `PATCH /templates/{id}` 与 `TEMPLATE_UPDATED`（Q-19 已于 2026-11-14 经人类确认，spec 已同步）；预览响应采用 `{"rendered": "..."}`，未给 `lead_id` 时使用内置示例（Alex / alex_demo / beauty devices）；`TemplateView` 返回模板定义 body（配置管理必需），渲染后的消息正文不写日志 / 审计；重复 `disable` 按 Q-16 的 no-op 语义不写审计 | 全部采纳（待人工审查） | 1.0h→≈1.8h |
| 维护 | 2026-11-14 | 处理 T-00～T-06 统一遗留问题（甲组+乙组）：脱敏日期吞号与头值截断、日志改 Formatter 层脱敏（含 traceback）、去掉消息内 request_id、`q` 转义 LIKE 通配符、`iso_z` 收敛、AuditService 统一由 `app.state` 注入、`APP_VERSION` 改用 `importlib.metadata`、架构守卫支持相对导入与顶层白名单、网络守卫补 `connect_ex`/`getaddrinfo`/`sendto`、补 `template.version>=1`/`lead.batch_id` 索引/`lead.phone_hash` 部分唯一索引、配置 no-op 不写审计、重命名 LEAD-007 规范化测试 | 人类评审清单逐项核验；Q-15～Q-17 经确认后先改 spec 再改代码；运行时发现 `.pytest_tmp` 目录 ACL 拒绝访问，测试 basetemp 改用 `.pytest_basetemp` | 全部采纳 | — |

## 4. AI 犯过的典型错误（持续追加）

> 例：「AI 把 `datetime.now()` 写进了业务代码，违反时钟注入 → 我要求改为 `Clock` 并加了静态扫描测试」。
> 这一节最能体现"我是在驾驭 AI，而不是被 AI 驾驭"。

- AI 用正则做号码掩码时两次误伤正常文本：T-02 把 ISO 时间戳（`2026-11-14T09:00:00Z`）当成号码，T-04 审查又发现 32 位十六进制请求 ID 会被掩码（实测约 13% 的随机 ID 受影响，日志与响应头对不上）。两次都是人类审查发现 → 改为跳过日期前缀，并识别、保留 hex/UUID 令牌，各补一条回归测试。
- AI 默认接受 Pydantic 的宽松转换，`weight: true` 变成 `1`、`"30"` 变成 `30`、`enabled: "false"` 变成 `False`，与"类型错误应 422"的意图不符 → 审查后配置 schema 改用 `StrictInt`/`StrictBool`。
- AI 在 T-04 把"库为空时自动播种"写成已知缺口而不是先记入 `CHANGELOG` 待决 → 审查后按 spec 原文补上 `SEED_DEFAULTS=true` 的启动播种与测试。
- AI 的日期豁免按"token 起点像日期"整段放行，`2026-11-14 555-555-0101` 中的完整号码实测漏网；异常堆栈也绕过了当时的消息级过滤器。两处都直到统一遗留问题评审才被发现 → 日期改为独立分支并前置，脱敏下沉到 Formatter 层，补日期+号码、traceback 两组回归测试。
- T-07 写 POOL-005 测试时把二次重算的候选数算错：忘记首次评分已自动入池的 20 条不会再次进入候选，断言 42 而实际是 22；测试先失败后修正。说明写断言前要显式列出集合的组成。

## 5. 效率与反思（收尾时填写）

- 哪些环节 AI 提效最明显：
- 哪些环节 AI 最不可靠、需要重点审查：
- 如果重来，我会改变的做法：
