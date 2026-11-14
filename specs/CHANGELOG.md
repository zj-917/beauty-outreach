# CHANGELOG 与待决问题

> 规则（SDD 变更控制）：实现中发现 spec 歧义 / 矛盾 / 缺失 → 停 → 在「待决问题」追加 → 人类确认 → **先改 spec，再改代码** → 在「变更记录」登记。

## 待决问题（v1.0–v1.1 已全部决议，2026-11-14）

> 以下 12 项已由人类逐条确认，全部按第三列「最终决议」执行；Q-9 ~ Q-11 已同步修订对应 AC 文本，Q-12 于 2026-11-14 确认并修订 lead.md §4.3–§4.4。后续再发现歧义时继续按同一流程追加。

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

## 变更记录

| 版本 | 日期 | 变更 | 原因 | 影响文件 |
|---|---|---|---|---|
| v0.1 | 2026-11-13 | 初稿：宪法、概览、架构、数据模型、API 契约、Mock 数据、9 个模块规格、测试计划、排期与任务清单 | — | 全部 |
| v1.0 | 2026-11-13 | M0 定稿：Q-1~Q-11 全部确认；修订 AC-SYS-003（OpenAPI 清单排除 P2）、AC-LEAD-011（二次导入计数）、campaign §4（start 前置检查顺序含 Provider）；AGENTS.md 新增「按任务裁剪阅读」规则 | 人类评审定稿，spec 冻结 | 全部 specs 头部版本；modules/system.md、modules/lead.md、modules/campaign.md；AGENTS.md、tasks.md；docs/ai-usage.md |
| v1.1 | 2026-11-14 | Q-12 确认并修订 lead.md §4.3–§4.4：合并补号码不得抢占其他线索的号码（→ `IMPORT_CONFLICT`）；`DUPLICATE_PHONE` 行仍应用合法授权 | T-05 实现评审发现 spec 内部矛盾 | modules/lead.md；CHANGELOG.md；T-05 代码与测试 |
