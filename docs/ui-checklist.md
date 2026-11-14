# 管理页手动验收清单（AC-UI-001 ~ 011）

> UI 自动化成本高，原型采用「后端 API 测试 + 手动清单」组合（`specs/modules/admin-ui.md` §6）。
> 每完成一次 UI 改动或彩排，按本清单逐条勾选；未勾选项不得在答辩中声称已支持。

## 0. 启动环境

```bash
python scripts/seed.py
python -m uvicorn app.main:app --reload
```

- 打开 `http://127.0.0.1:8000/admin/`。
- 浏览器控制台无报错；Network 面板中除 `localhost` 外无外部请求。
- 顶部填入 `ADMIN_TOKEN` 与操作人，点「保存」。

（自动化部分：`python -m pytest -q tests/integration/test_AC_UI_001_admin_static.py tests/unit/test_AC_UI_010_ui_static_checks.py`）

## 1. 逐条验收

- [ ] **AC-UI-001**：访问 `/admin/` 返回页面；`app.js`、`style.css` 均 200；页面不加载任何外部资源（无 CDN / 外链字体）。无构建步骤，直接由应用提供。
- [ ] **AC-UI-002**：清空 token 后点任意操作 → 全局错误条显示 `401 UNAUTHORIZED` 且焦点跳到 token 输入框；填写并保存后请求成功。DevTools → Application → Session Storage 可见 `adminToken`，Local Storage 中**没有** token。
- [ ] **AC-UI-003**：线索页「导入 Mock 数据」后，按状态 `PENDING_REVIEW` 与最低分过滤，列表只剩匹配项；可见分数、命中原因、脱敏号码、可触达预估；对单条填写备注后点「通过 / 拒绝」，列表即时刷新；勾选多条后「批量通过 / 批量拒绝」生效。
- [ ] **AC-UI-004**：点「导入 Mock 数据」→ 显示批次报告（总数 / 导入 / 重复 / 无效 / 警告）；上传 `data/sample_leads.csv` 同样显示报告；若文件含错误行，错误列表以纯文本展示。
- [ ] **AC-UI-005**：任务页选择已审核模板与最低分 → 点「创建并干跑预览」→ 显示 `将尝试 / 将释放 / 将跳过`；点「打开任务详情」进入详情。
- [ ] **AC-UI-006**：任务详情按钮随状态启用：`DRAFT` 仅「启动」「取消」；`RUNNING` 仅「暂停」「取消」；`PAUSED` 仅「恢复」「取消」；`COMPLETED/CANCELLED` 全部禁用。`RUNNING` 时右上显示「每 2 秒自动刷新」，切走标签页后停止（Network 中不再轮询）。明细按 `status` / `reason_code` 过滤生效。熔断后 `pause_reason=CIRCUIT_OPEN` 显示醒目红色提示。
- [ ] **AC-UI-007**：合规页可见 consent 与 suppression 列表；填号码 + 原因「加入黑名单」成功；`DEMO_MODE=true` 时显示演示面板 → 填运行中任务某号码「模拟收到 STOP」→ 该任务明细后续处理变为 `SKIPPED`（原因 `UNSUBSCRIBED`）。「立即产出回执」后对应明细变为 `DELIVERED/READ`；「重置演示数据」清库并重新播种。
- [ ] **AC-UI-008**：配置页可新增 / 改权重 / 启停 / 删除关键词；新增 / 删除频控规则（删除最后一条必需规则时页面就地显示后端错误码）；模板可新建、审核通过、停用、新版本、预览；设置表单可修改并保存，非法值就地显示错误且不改动其它设置。
- [ ] **AC-UI-009**：日志页可查询审计日志（actor / action / entity_type / entity_id）与发送日志（task_id / item_id / phase / outcome / reason_code），均可翻页；所有号码列均为脱敏值；任务详情的「日志」按钮能带 `task_id/item_id` 跳到发送日志。
- [ ] **AC-UI-010**：导入一条 `display_name` 含 `<img onerror=alert(1)>`、`bio` 含 `<script>alert(1)</script>` 的线索后，页面以纯文本显示，弹窗不出现；`app.js` 无 `innerHTML` 赋值（自动测试覆盖）。
- [ ] **AC-UI-011**：按 `docs/demo-script.md`（T-22 产出）从重置开始逐步操作：导入 → 筛选 → 审核 → 建任务 → 干跑 → 启动 → 暂停 / 恢复 → 统计与明细 → 日志 → 模拟 STOP / 回执，全部可在 UI 完成，无需 Swagger 或命令行。

## 2. 已知限制（如实记录）

- UI 只做演示与运维遥控，不含登录 / 权限体系；token 存于 `sessionStorage`。
- 配置页模板「新版本」使用浏览器 `prompt` 输入正文；预览使用内置示例线索。
- 线索页「可触达预估」只对 `APPROVED` 行展示，来源是 `/pool` 的第一页（最多 100 条）。
- `demo.js` 面板通过 `GET /demo/inbound-stop` 返回 405 判断演示模式是否开启（不新增探测端点）。
