# CHANGELOG 与待决问题

> 规则（SDD 变更控制）：实现中发现 spec 歧义 / 矛盾 / 缺失 → 停 → 在「待决问题」追加 → 人类确认 → **先改 spec，再改代码** → 在「变更记录」登记。

## 待决问题（v1.0–v1.6 已全部决议，2026-11-14；Q-21 待确认）

> 以下 20 项已由人类逐条确认，全部按第三列「最终决议」执行；Q-9 ~ Q-11 已同步修订对应 AC 文本，Q-12 修订 lead.md §4.3–§4.4，Q-13/Q-14 修订 screening.md §3.5、§5，Q-15 修订 02-architecture §5、modules/audit.md §4.1、modules/system.md 与 AC-SYS-008，Q-16 修订 config-stats 的审计语义，Q-17 修订 03-data-model §2.3、§2.6、§4 与 05-mock-data §6，Q-18 修订 04-api-contract.md 与 modules/pool.md §3.2，Q-19 修订 04-api-contract.md、modules/template.md §3.1/§4 与 modules/audit.md §4.2，Q-20 修订 modules/pool.md §3.3。后续再发现歧义时继续按同一流程追加。

| 编号 | 问题 | 最终决议（人类已确认） | 影响 |
|---|---|---|---|
| Q-1 | **号码来源假设**：Instagram 公开资料无手机号，本系统约定号码只来自"企业自有授权数据 / 用户主动留资"，随线索行携带 `phone + consent_*`（A-1）。是否接受？ | 接受；答辩时主动讲清 | 数据模型、Mock 数据、合规说明 |
| Q-2 | **退订永久不可恢复**，不做再订阅流程（A-4 / D-8）。是否接受？ | 接受（更保守） | COMP-008/009 |
| Q-3 | **管理端鉴权**：静态 `X-Admin-Token` + `X-Operator` 即可（A-5）。是否足够？ | 足够 | SYS-002 |
| Q-4 | **默认模板语言**：英文问候 + 中英双语退订页脚。是否需要同时提供中文问候模板？ | 只提供英文种子模板，运营可自建中文模板 | 种子数据 |
| Q-5 | **范围体量**：全部 AC 共 142 条：P0 110 条、P1 27 条（其中管理页 11 条）、P2 5 条（不排期）。是否接受 `plan.md` §4 的裁剪顺序？ | 接受 | 排期 |
| Q-6 | **依赖**：手机号加密需 `cryptography`。是否接受？（替代：不存号码，仅存哈希 + 掩码，Mock 发送时从 `mock_leads.json` 反查——不推荐，因为那样 Mock 不再"像真的"） | 接受 `cryptography` | TC-3 |
| Q-7 | **评分初始值**（阈值 70/40、关键词权重）是否允许在 T-19 按评测结果微调？ | 允许，微调须记入本文件 | SCR、Mock |
| Q-8 | **UI 范围**：配置页（UI-008）是否可作为最先被砍的部分，用 Swagger 替代？ | 可以 | UI |
| Q-9 | **AC-SYS-003 路径清单**：要求 OpenAPI 包含 `04-api-contract.md` 全部路径，但其中 P2 端点（`/pool/export`、`/pool/stats`、`/consents/import`、`/campaigns/{id}/requeue-failed`）未排期；`/docs`、`/admin/` 等非 `/api/v1` 路径是否纳入？ | 期望清单 = 04 中全部**非 P2** 的 `/api/v1` 端点 + `/healthz`；P2 未实现则不入清单 | SYS-003 测试 |
| Q-10 | **AC-LEAD-011 重复导入计数**："第二次 imported=0 且全部计入 duplicates" 与 F 类非法行每次仍应判 invalid 有出入 | 第二次导入：`imported=0, duplicates=48, invalid=4, warnings=1`（duplicates 指 A–E 类合法行） | LEAD-011、demo 断言 |
| Q-11 | **start 的 Provider 前置检查**：SYS-006 要求 `MESSENGER_PROVIDER=whatsapp_cloud` 时 start 返回 501，但 campaign.md §4 未列该前置条件、检查顺序及失败时任务状态 | 顺序 = 模板 APPROVED → 存在非终态明细 → Provider 可用；失败时任务状态不变，Provider 不可用 → 501 `PROVIDER_NOT_ENABLED` | CAMP-004/027、SYS-006 |
| Q-12 | **合并补号码的归属与重复行授权**：lead.md §4.3 允许合并时补全「此前缺失的号码」，但可能与「一个收件人一条线索」冲突；`DUPLICATE_PHONE` 行携带的授权是否应用未写明 | 补号码前若该 `phone_hash` 已属于另一条线索 → `IMPORT_CONFLICT`、不补号码；行合法且号码有效时，`DUPLICATE_PHONE` 行仍按 §4.4 应用授权（`IMPORT_CONFLICT` 除外） | LEAD-005/009、T-05 |
| Q-13 | **`POST /leads/screen` 的 `unchanged` 含义**：screening.md §5 只列字段未定义；可能是「重算后状态未变」或「被粘性规则跳过」 | 取「本次进入重算且状态未变」的条数；`processed` 为候选数，`approved + pending_review + discarded = processed`；`APPROVED/REJECTED` 不计入任何计数 | SCR-010/012/013 |
| Q-14 | **零贡献命中是否计入 reasons / top_keyword**：weight=1 只命中 display_name / username 时贡献为 `floor(1/2)=0`，spec 未说明 | 贡献为 0 的命中不计入 `reasons`，也不参与 `top_keyword` | SCR-009/015 |
| Q-15 | **`BEGIN IMMEDIATE` 的适用范围**：`core/db.py` 的 begin 钩子对所有事务（含只读 SELECT）生效，而 spec 只要求写事务；该偏差此前未登记，且审计哈希链依赖全局写锁 | 保留全局实现（方案 A），把 02-architecture §5、modules/audit.md §4.1、modules/system.md 与 AC-SYS-008 的措辞统一为「所有数据库事务（含只读）以 `BEGIN IMMEDIATE` 开始」，并注明单进程原型接受读请求串行化；未来若出现长扫描端点再评估读写分离 | SYS-008、AUD-001/004、T-12 |
| Q-16 | **no-op 配置更新的审计语义**：关键词 / 频控 PATCH 提交与现值相同的字段时仍写 `*_UPDATED` 审计，而同类的 `PUT /settings` 会跳过无变化项；AC-CFG-004 只说「任一配置变更」 | 无变化（`before == after`）不写审计，直接返回原对象，与 settings 的语义对齐 | CFG-004、T-04 |
| Q-17 | **数据模型三处缺失约束**：`template` 无 `version >= 1`；`lead.batch_id` 无索引；`lead.phone_hash` 仅普通索引，「一个号码至多一条线索」只靠服务层 | 补 `CHECK(version >= 1)`、`Index(batch_id)`、`phone_hash` 部分唯一索引（`WHERE phone_hash IS NOT NULL`，同 suppression 款式），并在 03-data-model 新增 INV-11；原型无 Alembic，重建库即可 | 03-data-model、SYS-008、T-01/T-05 |
| Q-18 | **批量审核的请求 / 响应结构未定义**：`modules/pool.md` §3.2 只规定 ≤200 条、逐条独立处理与每条结果 `{lead_id, ok, error?}`，`04-api-contract.md` 未给示例 | 沿用 T-07 已实现的结构：请求 `{"reviews":[{lead_id, decision, note?}]}`，响应 `{"results":[{lead_id, ok, error?}]}`；每项独立提交，失败项返回 `error.code/message`（2026-11-14 人类确认） | POOL-004、T-07 测试、管理页批量审核 |
| Q-19 | **模板草稿编辑端点与审计动作缺失**：`modules/template.md` §3.1 规定 `DRAFT` 可编辑、修改 `APPROVED` 的 body → 409 `TEMPLATE_IMMUTABLE`，AC-TPL-004 也要求「尝试修改 body」；但 `04-api-contract.md` 未列模板更新端点，`modules/audit.md` §4.2 的 action 注册表也没有 `TEMPLATE_UPDATED` | 补 `PATCH /templates/{id}`（`{body?, language?}`，仅 DRAFT 可改，APPROVED / DISABLED → 409 `TEMPLATE_IMMUTABLE`），新增审计动作 `TEMPLATE_UPDATED`；T-08 已按此实现（2026-11-14 人类确认） | TPL-004、T-08 测试、管理页配置页 |
| Q-20 | **POOL-006 的 `delivery_readiness` 词表未覆盖 `INVALID_PHONE`**：发送闸门的 PHONE 闸门区分 `NO_PHONE` 与 `INVALID_PHONE`，但 `modules/pool.md` §3.3 的池值只有 `NO_PHONE` 等六种；当线索有密文但解密后不是 E.164 时如何标注未定义 | 池中把 `INVALID_PHONE` 归入 `NO_PHONE`（导入已丢弃非法号码，池词表保持六种）；发送闸门仍返回 `INVALID_PHONE`；T-09 已按此实现（2026-11-14 人类确认） | POOL-006、pool.md §3.3、T-09 测试 |
| Q-21 | **发送侧渲染失败的原因码未覆盖 `RENDER_TOO_LONG`**：`modules/campaign.md` §5 的 TEMPLATE 闸门与 §11 原因码表只列 `TEMPLATE_VARIABLE_MISSING`，但 `domain/render` 还会抛 `RENDER_TOO_LONG`（AC-TPL-007：渲染后 > 1024 字符）；此时明细的 `SKIPPED` 原因码取什么未定义 | **待确认**（T-12 暂以 `RenderError.code` 原样作为原因码，即可能出现 `SKIPPED(RENDER_TOO_LONG)`） | CAMP-010、campaign.md §11、T-12 测试 |

## 变更记录

| 版本 | 日期 | 变更 | 原因 | 影响文件 |
|---|---|---|---|---|
| v0.1 | 2026-11-13 | 初稿：宪法、概览、架构、数据模型、API 契约、Mock 数据、9 个模块规格、测试计划、排期与任务清单 | — | 全部 |
| v1.0 | 2026-11-13 | M0 定稿：Q-1~Q-11 全部确认；修订 AC-SYS-003（OpenAPI 清单排除 P2）、AC-LEAD-011（二次导入计数）、campaign §4（start 前置检查顺序含 Provider）；AGENTS.md 新增「按任务裁剪阅读」规则 | 人类评审定稿，spec 冻结 | 全部 specs 头部版本；modules/system.md、modules/lead.md、modules/campaign.md；AGENTS.md、tasks.md；docs/ai-usage.md |
| v1.1 | 2026-11-14 | Q-12 确认并修订 lead.md §4.3–§4.4：合并补号码不得抢占其他线索的号码（→ `IMPORT_CONFLICT`）；`DUPLICATE_PHONE` 行仍应用合法授权 | T-05 实现评审发现 spec 内部矛盾 | modules/lead.md；CHANGELOG.md；T-05 代码与测试 |
| v1.2 | 2026-11-14 | Q-13/Q-14 确认并修订 screening.md §3.5、§5：定义 `processed/unchanged` 等计数；零贡献命中不计入 reasons / top_keyword；补充 `batch_id` 与 `lead_ids` 取交集 | T-06 实现评审发现字段定义缺失 | modules/screening.md；CHANGELOG.md；T-06 代码与测试 |
| v1.3 | 2026-11-14 | Q-15/Q-16/Q-17 确认：事务统一 `BEGIN IMMEDIATE`（含只读）；配置无变化不写审计；补 `template.version >= 1`、`lead.batch_id` 索引、`lead.phone_hash` 部分唯一索引（INV-11）与评测分母说明 | T-00～T-06 统一遗留问题评审 | 02-architecture.md、modules/audit.md、modules/system.md、modules/config-stats.md、03-data-model.md、05-mock-data.md、CHANGELOG.md；T-01/T-04/T-05 相关模型与测试 |
| v1.4 | 2026-11-14 | Q-18 确认：批量审核请求体固定为 `{"reviews":[{lead_id, decision, note?}]}`，响应 `{"results":[{lead_id, ok, error?}]}`，每项独立提交；同步接口契约与模块规格 | T-07 实现评审确认结构，避免管理页与后端各自猜测 | 04-api-contract.md、modules/pool.md、CHANGELOG.md |
| v1.5 | 2026-11-14 | Q-19 确认：新增 `PATCH /templates/{id}`（仅 DRAFT 可编辑）与审计动作 `TEMPLATE_UPDATED`；同步接口契约、模板规格与审计动作表 | T-08 实现评审确认草稿编辑路径与审计语义 | 04-api-contract.md、modules/template.md、modules/audit.md、CHANGELOG.md |
| v1.6 | 2026-11-14 | Q-20 确认：池的 `delivery_readiness` 将 `INVALID_PHONE` 归入 `NO_PHONE`，发送闸门仍保留 `INVALID_PHONE` | T-09 实现评审确认池词表与闸门原因码的映射 | modules/pool.md、CHANGELOG.md |
