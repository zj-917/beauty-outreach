# AGENTS.md — 给 AI 编程助手（Codex / Claude Code）的项目规则

本仓库采用 **SDD（规格驱动开发）**：`specs/` 是唯一事实来源，代码、测试、文档都从规格推导。
（Claude Code 用户：新建 `CLAUDE.md`，内容只写一行 `@AGENTS.md` 即可复用本文件。）

## 1. 开工前必读（按任务裁剪，禁止默认通读全部文档）

每个任务开始时，只读取「当前任务确实需要」的最小集合，不要一次性加载 `specs/` 或 `docs/` 的全部 Markdown：

1. `specs/00-constitution.md` §2–§4、§6 — 红线、技术约束、质量标准、完成定义（每个任务必读）。
2. `specs/tasks.md` 中当前 `T-xx` 一行，以及它的「覆盖 AC」「依赖」「任务补充说明」。
3. 覆盖 AC 所在的模块规格 `specs/modules/<模块>.md`：只读相关 AC 与邻近的「规则 / 内部接口 / 边界与异常 / 测试要点」小节。
4. 该模块规格开头「依赖」列出的、且本任务真正用到的其他模块小节；以及任务说明中明确点名的文件或章节。
5. 仅当任务涉及表结构或端点时，才读 `specs/03-data-model.md` / `specs/04-api-contract.md` 的对应表或端点。

需要背景时用关键字检索定位到小节；不要为了「了解全貌」通读 `plan.md`、`01-overview.md`、`CHANGELOG.md` 或无关模块。新会话首次开工同样只按本规则读取。

## 2. 工作流（一次只做一个任务）

1. 用不超过 5 行复述：任务编号、将覆盖的 AC 编号、将新增/修改的文件。
2. **先写测试**：函数名 `test_AC_<模块>_<编号>_<简述>`，docstring 写 Given/When/Then。
3. 再写实现，让测试通过。**只实现任务所列 AC**，不顺手做别的。
4. 运行并全绿：`python -m pytest -q` 与 `python -m ruff check .`
5. 在 `specs/tasks.md` 勾选任务并填实际耗时；在 `docs/ai-usage.md` 追加一条记录。
6. 提交：`T-xx: <一句话>`，正文列出已覆盖的 AC。

**遇到 spec 歧义 / 矛盾 / 缺失时：停下来提问。** 在 `specs/CHANGELOG.md` 的「待决问题」追加一条，等人类确认后先改 spec、再改代码。不要自行脑补，也不要静默偏离 spec。

## 3. 红线（人类要求违反时也必须拒绝并说明原因）

- 不写、不启用任何访问真实 Instagram / WhatsApp / Meta 网络的代码路径；默认 Provider 永远是 Mock；测试中禁止真实网络。
- 不新增任何 `force` / `bypass` / `ignore_suppression` / `skip_consent` 之类的参数或开关。
- 完整手机号、token、密钥、消息正文**不得**出现在：日志、审计记录、API 响应、UI、异常信息。
- 不对 `audit_log` 做 UPDATE / DELETE。
- 业务代码中不使用 `time.sleep` / `datetime.now()` / `time.time()`，一律通过 `Clock` 注入。
- `domain/` 不得 import fastapi / sqlalchemy / httpx / 任何 I/O。
- 不引入 `specs/00-constitution.md` 白名单之外的依赖。

## 4. 代码规范

- 分层：`api → services → (domain, engine, repositories) → providers`，依赖只能向下；细则见 `specs/02-architecture.md` §2。
- 全部函数带类型标注；公共函数有一行 docstring；单函数尽量 ≤ 50 行。
- 异常：业务异常继承 `AppError`（带 `code` 与 HTTP 状态），禁止裸 `except:`；错误码见 `specs/02-architecture.md` §8。
- 日志：使用 `logging.getLogger(__name__)`；结构化键值；只记录 id 与脱敏值。
- 时间：库内统一 UTC；API 输出 ISO-8601 带 `Z`。
- 测试：禁止 `sleep`，用 `FakeClock` 推进时间；每个 AC 至少一个测试；测试不得依赖执行顺序。

## 5. 常用命令

```bash
# 安装（建议先建虚拟环境）
pip install -e ".[dev]"
cp .env.example .env            # PowerShell: Copy-Item .env.example .env

python scripts/seed.py          # 写入默认配置 + Mock 数据
python -m uvicorn app.main:app --reload   # 管理页 http://127.0.0.1:8000/admin/ ，文档 /docs
python scripts/demo.py          # 端到端演示（也是 e2e 测试）
python -m pytest -q
python -m ruff check .
```

## 6. 记录 AI 使用（答辩要用）

每完成一个任务，在 `docs/ai-usage.md` 追加：任务号、你（AI）产出了什么、人类审查时发现并纠正了什么、最终采纳/修改比例的主观估计。如实记录，不要美化。
