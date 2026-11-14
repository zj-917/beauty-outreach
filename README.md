# Beauty Outreach — 合规优先的 Instagram → WhatsApp 触达原型

一个可运行、可审计、可演示的批量触达原型：**导入线索 → 规则评分与人工审核 → 目标池 → 批量任务（闸门 + 频控 + 重试）→ 状态回写 → 审计与统计**。

> **合规前提（请先读）**
> - 本仓库**只使用 Mock / 沙箱路径**：`MESSENGER_PROVIDER` 默认 `mock`，真实 WhatsApp 实现仅为 Stub，调用即返回 `501 PROVIDER_NOT_ENABLED`；测试夹具禁止一切真实网络。
> - Instagram 公开资料不含手机号，官方接口也不提供"按关键词搜索任意公开用户"。因此本原型约定：号码只来自**企业自有授权数据 / 用户主动留资**，随线索行携带 `consent`（见 `docs/compliance-risk.md`）。
> - 完整手机号、token、密钥、消息正文不会出现在日志、审计、API 响应或 UI 中；库内只存密文、HMAC 哈希与掩码。

## 快速开始（5 条命令）

```bash
pip install -e ".[dev]"
```

```bash
cp .env.example .env            # PowerShell: Copy-Item .env.example .env
```

```bash
python scripts/seed.py
```

```bash
python -m uvicorn app.main:app --reload
```

然后打开：

- 管理页 <http://127.0.0.1:8000/admin/>（在页面右上角填入 `.env` 中的 `ADMIN_TOKEN`）
- Swagger <http://127.0.0.1:8000/docs>（点 Authorize 前需在请求头带 `X-Admin-Token`）

`seed.py` 写入默认配置（26 项设置、25 个关键词、2 条频控规则、greeting 模板）与 `data/mock_blacklist.csv` 中的黑名单。**线索数据需要额外导入**：在管理页「线索 → 导入 Mock 数据」，或调用 `POST /api/v1/lead-batches/import`（body `{"source": "mock"}`）。

更多命令：

```bash
python scripts/demo.py --fast   # 端到端演示（假时钟，几秒跑完；不带 --fast 约 1–2 分钟）
python -m pytest -q             # 全量测试（含 e2e 与泄漏扫描）
python -m ruff check .
python scripts/ac_coverage.py   # 生成 docs/ac-coverage.md（AC → 测试对照表）
python scripts/eval_screening.py  # 评分评测：混淆矩阵 + Precision/Recall + 错判原因
```

## 功能概览

| 能力 | 说明 |
|---|---|
| 线索导入 | Mock 数据集（52 行）、CSV / JSON 上传；规范化、去重合并、逐行校验报告 |
| 规则筛选 | 关键词权重（正 / 负）、地区 / 语言 / 短简介调整；三档决策（自动入池 / 人工确认 / 丢弃）；原因可解释 |
| 目标池 | 池查询、单条 / 批量人工审核、可触达性预估（六种 readiness） |
| 模板 | 版本化、变量白名单、渲染预览、审核后使用；自动追加中英双语退订页脚 |
| 批量任务 | 创建时快照目标与模板；start / pause / resume / cancel；干跑预览；自动完成 |
| 发送闸门 | 固定 9 级闸门：任务状态 → 黑名单/退订 → 号码 → 授权 → 模板 → 跨任务防重 → 单收件人频控 → 静默时段 → 全局频控 |
| 失败处理 | 永久 / 可重试 / 限流分类；指数退避 + 抖动 + `retry_after`；超时；熔断 |
| 回执 | 签名 Webhook（`X-Hub-Signature-256`）与 Mock 轮询；状态只前进；入站 STOP 即时退订 |
| 审计与日志 | 同事务写审计、SHA-256 哈希链可校验、任务时间线、`send_log` 查询；号码全程脱敏 |
| 统计 | 任务统计（8 种明细状态、成功率、原因分组、尝试直方图）与全局总览 |
| 管理页 | 原生 HTML/CSS/JS（无构建、无外部资源），token 仅存 `sessionStorage` |

## 架构

模块化单体 + 适配器隔离外部平台；依赖只向下：

```
api → services → (domain, engine, repositories) → providers
                   └────────── core（配置 / DB / Clock / 安全 / 日志）──────┘
```

- `app/domain/` 是纯函数（规范化、评分、渲染、退避、状态表、闸门判定），无 I/O、无框架依赖。
- `app/engine/` 是发送引擎：单 Worker 线程 + 数据库即队列 + 租约；`Processor` 对每条明细跑闸门链。
- 外部平台只经 `LeadSource` / `Messenger` 接口进入；Mock 之外只有 Stub。
- 全部时间经注入的 `Clock`（测试用 `FakeClock`），SQLite 以 WAL + `BEGIN IMMEDIATE` 运行。

详细设计见 `specs/02-architecture.md`；数据模型、状态机与请求流程见 [`docs/data-model.md`](docs/data-model.md)。

## 目录结构

```
app/           应用代码（api / services / domain / engine / repositories / models / providers / core / static）
specs/         SDD 规格：宪法、架构、数据模型、API 契约、Mock 数据、模块规格、测试计划、任务清单
docs/          README 之外的交付文档：数据模型说明、合规与风险、AI 使用说明、UI 验收清单、AC 覆盖表
data/          mock_leads.json、mock_blacklist.csv、sample_leads.csv
scripts/       seed.py、demo.py、eval_screening.py、ac_coverage.py
tests/         unit / integration / contract / e2e
```

## 配置

复制 `.env.example` 后按需修改（完整说明见 `specs/02-architecture.md` §9）：

| 变量 | 默认 | 说明 |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./data/app.db` | SQLite 文件 |
| `ADMIN_TOKEN` | `dev-admin-token` | 管理 API / `/demo/*` 的 `X-Admin-Token` |
| `PHONE_ENC_KEY` | 开发用 Fernet key | 手机号加密；缺失或非法则启动失败 |
| `PHONE_HASH_KEY` | 开发用字符串 | HMAC-SHA256 去重 / 关联 |
| `WEBHOOK_SECRET` | `dev-webhook-secret` | Webhook 与 `/demo/inbound-stop` 签名 |
| `MESSENGER_PROVIDER` | `mock` | 仅 `mock` 可用；`whatsapp_cloud` 为 Stub |
| `WORKER_ENABLED` | `true` | 是否启动进程内 Worker |
| `TICK_SECONDS` | `1` | Worker 轮询间隔 |
| `DEMO_MODE` | `true` | 是否注册 `/demo/*` 辅助端点 |
| `SEED_DEFAULTS` | `false` | 启动时若库为空则自动播种 |
| `LOG_LEVEL` | `INFO` | |

运行期参数（阈值、频控、重试、静默时段、品牌与退订文案等）存在 `system_setting` / `rate_rule` 表，可通过 API 或管理页实时调整。

## API 摘要

全部端点见 `/docs` 与 `specs/04-api-contract.md`。主要分组：

- 线索：`POST /api/v1/lead-batches/import`、`GET /leads`、`POST /leads/screen`、`POST /leads/{id}/review`
- 池：`GET /pool`、`POST /leads/review-bulk`
- 模板：`GET|POST /templates`、`PATCH /templates/{id}`、`POST /templates/{id}/approve`
- 任务：`POST|GET /campaigns`、`/{id}/preview`、`/{id}/(start|pause|resume|cancel)`、`/{id}/items|stats|timeline`
- 合规：`GET|PUT /consents`、`GET|POST|DELETE /suppressions`
- 配置：`/keywords`、`/rate-rules`、`/settings`
- 审计 / 日志 / 统计：`/audit-logs`（含 `/verify`）、`/send-logs`、`/stats/overview`
- 回调：`POST /api/v1/webhooks/whatsapp/status`、`POST /api/v1/webhooks/whatsapp/inbound`（HMAC 签名，豁免 token）
- 演示（`DEMO_MODE=true`）：`POST /demo/inbound-stop`、`POST /demo/flush-receipts`、`POST /demo/reset`
- 健康检查：`GET /healthz`

## 测试与质量

- 全量 `python -m pytest -q`：单元、集成、契约与 e2e（含 E2E-1~10 主流程、崩溃恢复、泄漏扫描、优雅关闭）。
- `docs/ac-coverage.md` 由 `scripts/ac_coverage.py` 生成：目标为**未覆盖 P0 = 0**。
- 测试确定性：`FakeClock`、手动 `worker.tick()`、socket 守卫禁止真实网络；每个测试独立临时库。
- 泄漏扫描覆盖 API 响应、日志、`audit_log`、`send_log`、`last_error_message` 与 SQLite 文件字节。

## 已知限制与生产化

原型刻意保留的边界（详见 [`docs/compliance-risk.md`](docs/compliance-risk.md)）：

- 只有 Mock Provider；真实 WhatsApp / Instagram 接入需要平台审核与授权，不在本仓库范围内。
- 单进程 + SQLite + 单 Worker：生产需 Postgres、多 Worker、令牌桶式频控（Redis）与独立队列。
- 管理端单一静态 token、无账号体系；密钥来自环境变量。
- 无数据库迁移工具；`create_all` 建表。
- Mock 回执队列在内存中，重启即丢；真实路径以签名 Webhook 为准。
- 退订永久拦截，不提供重新订阅流程（更保守）。

## 文档索引

| 文档 | 内容 |
|---|---|
| `docs/data-model.md` | 12 张表、状态机、数据不变量与核心流程时序 |
| `docs/compliance-risk.md` | Mock 与真实平台的差异、合规设计、风险清单与生产化路径 |
| `docs/ai-usage.md` | AI 编程助手的使用方式、任务记录与真实踩坑（答辩素材） |
| `docs/demo-script.md` | 10 分钟演示与答辩脚本（含彩排与克隆验证记录） |
| `docs/ac-coverage.md` | AC → 测试对照表（自动生成） |
| `docs/ui-checklist.md` | 管理页手动验收清单 |
| `specs/` | SDD 规格（唯一事实来源，入口 `specs/00-constitution.md`） |
