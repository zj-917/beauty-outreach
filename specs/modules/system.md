# 模块规格：system（横切能力：错误、鉴权、启动、时钟、网络隔离、演示）

> 版本 v1.0 · 状态 定稿（2026-11-13 冻结） · 无业务逻辑，但决定整套系统是否"可信、可运行、可演示"。

## 1. 目标
统一错误与鉴权、保证确定性（时钟注入）、保证合规（测试禁网）、保证可运行（一键启动、健康检查、优雅关闭）、保证可演示（演示脚本与辅助端点）。

## 2. 规则

- **错误**：所有错误统一为 `{"error":{"code","message","request_id","details"}}`（见 `02-architecture.md` §8）；Pydantic 校验失败映射为 `422 VALIDATION_ERROR`（`details` 列出字段）；未捕获异常 → `500 INTERNAL_ERROR`，**不泄漏堆栈**，堆栈只进日志（已脱敏）。
- **鉴权**：`/api/v1/*` 需 `X-Admin-Token`，用 `hmac.compare_digest` 比较；豁免：`/healthz`、`/docs`、`/openapi.json`、`/admin/*` 静态资源、`/api/v1/webhooks/*`（改用签名）。`/demo/*` 同样需 token，且仅 `DEMO_MODE=true` 时存在。
- **Webhook 签名**：`X-Hub-Signature-256: sha256=<hex>`，HMAC-SHA256(`WEBHOOK_SECRET`, **原始请求体字节**)；缺失 / 不匹配 → `401 SIGNATURE_INVALID`，**不解析、不写库**。
- **Clock**：`core/clock.py` 提供 `Clock` 协议（`now() -> datetime(UTC)`、`monotonic()`、`sleep()`）、`SystemClock`、`FakeClock(advance(), set())`。业务代码只依赖注入的 `Clock`。
- **SQLite**：连接建立时 `PRAGMA journal_mode=WAL; foreign_keys=ON; busy_timeout=5000;`；写事务统一以 `BEGIN IMMEDIATE` 开始（SQLAlchemy 事件钩子）。
- **网络隔离**：测试夹具（autouse）拦截 `socket.connect` 到非回环地址并报错；`MESSENGER_PROVIDER=whatsapp_cloud`（Stub）时，`start` 任务返回 `501 PROVIDER_NOT_ENABLED`。
- **优雅关闭**：`lifespan` 退出时通知 Worker 停止，Worker 在当前明细处理完（或超过 5 秒）后退出；未完成的明细靠租约过期恢复。
- **健康检查**：`GET /healthz` → `{"status":"ok","db":"ok","worker":"running|disabled","version":"…"}`；数据库不可用 → 503。
- **演示脚本**：`python scripts/demo.py` 通过应用内（`TestClient`）驱动完整流程，打印可读摘要并**断言** `05-mock-data.md` §3 的预期数字；`--fast` 用 `FakeClock` 推进时间（不真实等待），默认模式使用真实时钟（现场演示，约 1–2 分钟）。
- **架构守卫**：测试扫描 `app/domain/` 的 import，不得出现 `fastapi / sqlalchemy / httpx / requests / socket`；`app/` 中除 `core/clock.py` 外不得出现 `datetime.now / datetime.utcnow / time.time / time.sleep`。

## 3. 验收标准

| AC | P | 描述（给定 / 当 / 则） |
|---|---|---|
| AC-SYS-001 | P0 | 给定任一错误场景（校验失败、404、409、业务异常、未预期异常），则响应为统一错误格式并含 `request_id`；500 响应体不含堆栈 |
| AC-SYS-002 | P0 | 给定 `/api/v1/*` 请求缺失或错误的 `X-Admin-Token`，则 401 `UNAUTHORIZED`；`/healthz`、`/docs`、webhook 豁免；token 比较为常量时间 |
| AC-SYS-003 | P0 | 给定应用启动，当访问 `/docs` 与 `/openapi.json`，则可用，且包含 `04-api-contract.md` 中全部**非 P2** 端点与 `/healthz`（测试以期望路径清单比对；P2 端点未实现则不纳入） |
| AC-SYS-004 | P0 | 给定应用运行，当 `GET /healthz`，则返回 DB / Worker 状态与版本；数据库不可用时 503 |
| AC-SYS-005 | P0 | 给定 `app/` 源码，则除 `core/clock.py` 外无直接时间 / sleep 调用（静态扫描通过）；`FakeClock` 推进后依赖时间的行为随之变化 |
| AC-SYS-006 | P0 | 给定测试运行，则网络守卫夹具生效（对外连接立即报错，有测试证明）；给定 `MESSENGER_PROVIDER=whatsapp_cloud`，当 `start` 任务，则 501 `PROVIDER_NOT_ENABLED` 且无网络调用 |
| AC-SYS-007 | P0 | 给定全新环境，当按 README 的 ≤ 5 条命令操作（安装 → 复制 `.env` → seed → 启动 → 打开 `/docs`），则应用成功启动；有冒烟测试以 `TestClient` 走一遍 lifespan |
| AC-SYS-008 | P0 | 给定任一数据库连接，则 `journal_mode=wal`、`foreign_keys=1`、`busy_timeout≥5000`；外键约束真实生效（插入悬空外键失败）；写事务以 `BEGIN IMMEDIATE` 开始 |
| AC-SYS-009 | P0 | 给定 webhook 请求，当签名缺失或错误，则 401 `SIGNATURE_INVALID`，且无任何数据库写入（含审计）；签名正确则正常处理 |
| AC-SYS-010 | P1 | 给定 Worker 正在处理，当应用关闭，则 Worker 在 5 秒内停止；处理中的明细要么完成要么保持可被租约回收的状态 |
| AC-SYS-011 | P0 | 给定种子数据，当运行 `python scripts/demo.py --fast`，则完整流程跑通、`05-mock-data.md` §3 的预期数字全部断言通过、退出码 0；该脚本同时作为 e2e 测试 |
| AC-SYS-012 | P1 | 给定 `DEMO_MODE=false`，则 `/demo/*` 返回 404；`true` 时 `inbound-stop` 由服务端代签名并走与真实 webhook 相同的处理路径，`flush-receipts` 立即产出并应用回执，`reset` 清库并重新播种 |
| AC-SYS-013 | P1 | 给定源码，当运行架构守卫测试，则 `domain/` 无禁用 import；各层依赖方向符合 `02-architecture.md` §2 |

## 4. 测试要点
- 错误格式：对每种错误构造请求，断言 JSON 形状与 `request_id`。
- 静态扫描类测试（AC-SYS-005、013）使用 `ast` 或正则遍历 `app/`，不依赖运行时。
- 网络守卫：在夹具里 `monkeypatch socket.socket.connect`；另有一个测试故意连外网并期望被拦。
