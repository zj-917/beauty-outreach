# 06 测试计划

> 版本 v1.0 · 状态 定稿（2026-11-13 冻结） · 目标：**每条 AC 有测试、测试可重复、能一键展示"AC → 测试"覆盖表**。

## 1. 测试层次

| 层 | 目录 | 对象 | 特点 |
|---|---|---|---|
| 单元 | `tests/unit/` | `domain/*` 纯函数（规范化、评分、渲染、退避、闸门、脱敏、状态表） | 无 DB、无 I/O、参数化为主 |
| 集成 | `tests/integration/` | service + repository + 真实 SQLite（临时文件）+ FastAPI `TestClient` | 每个测试独立数据库 |
| 契约 | `tests/contract/` | `Messenger` / `LeadSource` 接口 | 同一套用例跑 Mock 与 Stub |
| 端到端 | `tests/e2e/` | 完整流程（导入 → 评分 → 审核 → 任务 → 发送 → 回执 → 统计 → 审计）、重启恢复、泄漏扫描、`demo.py` | 慢，数量少而关键 |

## 2. 命名与追溯

- 函数名：`test_AC_<模块>_<编号>_<简述>`，如 `test_AC_CAMP_012_global_rate_defers_without_consuming_attempt`。
- 一个测试覆盖多条 AC 时，在 docstring 首行写 `Covers: AC-CAMP-012, AC-CFG-005`。
- 每个测试 docstring 写一行 Given/When/Then 说明。
- **`scripts/ac_coverage.py`**（T-20）：解析 `specs/modules/*.md` 的 AC 表（编号、优先级），扫描 `tests/` 中的函数名与 `Covers:` 行，输出 Markdown 对照表 `docs/ac-coverage.md`（AC、优先级、测试文件与函数名、状态）；存在**未覆盖的 P0** 时以非零码退出。这张表就是答辩里"需求 → 实现 → 验证"的证据。

## 3. 共享夹具（`tests/conftest.py`）

| 夹具 | 作用 |
|---|---|
| `clock` | `FakeClock`，初始固定时间（如 `2026-11-14T09:00:00Z`），`advance(seconds)` |
| `settings` | 测试用环境（固定密钥、`WORKER_ENABLED=false`、临时库路径） |
| `app` / `client` | 以工厂创建应用（注入 `clock`、`messenger`），`TestClient` 带鉴权头 |
| `db` | 每个测试一个新的 SQLite 临时文件，建表 + 触发器 |
| `messenger` | `SpyMessenger`：包装 `MockMessenger`，暴露 `calls`、`unique_messages`、可编程返回序列 |
| `worker` | 不启动线程，只暴露 `tick()` 供测试手动推进 |
| `seeded` | 执行种子（配置 + 模板 + 黑名单） |
| `imported` | 在 `seeded` 基础上导入 Mock 线索并完成评分 / 入池 |
| `no_network`（autouse） | 拦截对外 `socket.connect` |
| `caplog` 增强 | 供泄漏扫描收集日志 |

## 4. 确定性规则

1. **禁止 `sleep`**：一切时间推进用 `clock.advance()`；Worker 用 `worker.tick()` 手动驱动。
2. **随机可注入**：退避抖动使用注入的 RNG，测试固定种子或固定值。
3. **每个测试独立**：不共享数据库、不依赖执行顺序（可用 `pytest -p no:randomly` 与随机顺序都通过）。
4. **不访问网络**：`no_network` 夹具兜底。
5. 并发测试（认领竞争）用两个线程 + 两个会话，断言结果集合不相交，不依赖时序运气。

## 5. 必须存在的关键场景

| 编号 | 场景 | 断言要点 |
|---|---|---|
| E2E-1 | 主路径：导入 52 行 → 评分 → 自动入池 20 条 → 人工通过 N 条 → 建任务 → 跑完 | 报告计数、`05-mock-data.md` §3 全部数字、`COMPLETED` |
| E2E-2 | 暂停 → 入站 STOP → 恢复 | 该明细 `SKIPPED(UNSUBSCRIBED)`，Messenger 对其零调用 |
| E2E-3 | 崩溃恢复：构造 `SENDING + 过期租约` → `tick()` | 同键重发，唯一消息数不增，最终 `SENT` |
| E2E-4 | 重复 `start` / 并发 `start` | 唯一消息数 = 唯一收件人数 |
| E2E-5 | 泄漏扫描 | API 响应、日志、`audit_log`、`send_log`、`last_error_message`、SQLite 文件字节均无完整号码 |
| E2E-6 | 频控：窗口内超限 → 延迟 → 窗口滑过后继续 | `DEFERRED` 日志、`attempts` 不变、推进时钟后发送 |
| E2E-7 | 重试全链路：`9001` 成功于第 3 次、`9002` 最终失败、`9003` 不重试、`9004` 429 后成功 | `attempts`、`reason_code`、`send_log` 行数与退避时间 |
| E2E-8 | 回执：delivered → read；乱序；重复；`9005` 的失败回执 | 状态只前进；`applied:false`；`FAILED(DELIVERY_FAILED)` |
| E2E-9 | 配置实时生效：运行中收紧全局频控 | 下一条明细按新值执行 |
| E2E-10 | 审计一致性：服务内注入异常 | 业务与审计均未提交 |

## 6. 覆盖率与质量门槛

- 参考目标：`app/domain` 与 `app/engine` 行覆盖率 ≥ 85%（`pytest --cov=app/domain --cov=app/engine`，不作阻断）。
- 阻断条件：`pytest -q` 全绿；`ruff check .` 无告警；`ac_coverage.py` 无未覆盖 P0。
- 变异式检查（手动，答辩加分）：临时移除某个闸门或幂等约束，确认至少一个测试失败——证明测试真的在保护行为。

## 7. 运行命令

```bash
python -m pytest -q                         # 全量
python -m pytest tests/unit -q              # 只跑单元
python -m pytest -k "AC_CAMP" -q            # 按模块
python -m pytest --cov=app/domain --cov=app/engine --cov-report=term-missing
python scripts/ac_coverage.py               # 生成 docs/ac-coverage.md
python scripts/demo.py --fast               # 端到端演示脚本（同时是 e2e 测试）
```

## 8. UI 的验证
见 `modules/admin-ui.md` §6：依赖的 API 全部有测试；UI 本身用手动验收清单；`innerHTML` 静态检查一个测试。
