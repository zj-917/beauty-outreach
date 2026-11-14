# 04 API 契约（API Contract）

> 版本 v1.1 · 状态 定稿（2026-11-14 修订 Q-18） · 字段细节以 `schemas/` 的 Pydantic 模型为准；本文件定义路径、语义、错误与 AC 对应。

## 1. 约定

- 前缀 `/api/v1`；JSON；时间 ISO-8601 带 `Z`。
- **鉴权**：请求头 `X-Admin-Token`（SYS-002）。`X-Operator` 标识操作人（默认 `admin`，`^[A-Za-z0-9_.@-]{1,40}$`）。
- **追踪**：`X-Request-ID` 透传或生成，回写到响应头（AUD-009）。
- **分页**：`page`（默认 1）、`page_size`（默认 20，最大 100）→ `{"items": [], "total": 0, "page": 1, "page_size": 20}`。
- **错误**：统一格式，见 `02-architecture.md` §8。
- **脱敏**：任何响应不含完整手机号；只返回 `phone_masked`。
- **写操作**：每个变更类接口产生审计记录（AUD-002）。

## 2. 端点清单

### 系统
| 方法 路径 | 说明 | AC |
|---|---|---|
| GET `/healthz` | 存活检查（无需鉴权）：DB、Worker 状态、版本 | SYS-004 |
| GET `/docs` | OpenAPI / Swagger | SYS-003 |
| GET `/admin/` | 管理页静态资源 | UI-001 |

### 配置
| 方法 路径 | 说明 | AC |
|---|---|---|
| GET/POST `/keywords`、PATCH/DELETE `/keywords/{id}` | 关键词 CRUD | CFG-001 |
| GET/POST `/rate-rules`、PATCH/DELETE `/rate-rules/{id}` | 频控规则 CRUD | CFG-002, CFG-008 |
| GET `/settings`、PUT `/settings` | 运行期设置（部分更新） | CFG-003 |

### 模板
| 方法 路径 | 说明 | AC |
|---|---|---|
| GET/POST `/templates`、GET `/templates/{id}` | 列表 / 创建 v1(DRAFT) / 详情 | TPL-001/002/003 |
| POST `/templates/{id}/new-version` | 基于某版本创建 `version+1`(DRAFT) | TPL-004 |
| POST `/templates/{id}/approve`、`/disable` | 审核通过 / 停用 | TPL-004/005 |
| POST `/templates/preview` | 用示例或指定 lead 渲染，无副作用 | TPL-009 |

### 线索与目标池
| 方法 路径 | 说明 | AC |
|---|---|---|
| POST `/lead-batches/import` | JSON `{"source":"mock"}`（或 `instagram_api` → 501）；或 multipart 上传 csv/json | LEAD-001/002/012 |
| GET `/lead-batches`、GET `/lead-batches/{id}` | 批次与导入报告 | LEAD-013/015 |
| GET `/leads`、GET `/leads/{id}` | 过滤：`status`、`min_score`、`batch_id`、`q`、`region`、`language` | LEAD-015, POOL-002 |
| POST `/leads/screen` | 触发评分与决策 | SCR-010/012/013 |
| POST `/leads/{id}/review` | `{"decision":"APPROVE"\|"REJECT","note":"…"}` | POOL-003/005 |
| POST `/leads/review-bulk` | 请求 `{"reviews":[{"lead_id":1,"decision":"APPROVE"\|"REJECT","note":"…"}]}`（≤200 条）；响应 `{"results":[{"lead_id":1,"ok":true}]}`，失败项附 `error:{code,message}` | POOL-004 |
| GET `/pool` | 目标池（带"可触达预估"标记） | POOL-001/006 |
| GET `/pool/export`、GET `/pool/stats` | P2 | POOL-007/008 |

### 合规
| 方法 路径 | 说明 | AC |
|---|---|---|
| GET `/consents`、PUT `/consents` | 授权查询 / upsert（按手机号） | COMP-001 |
| POST `/consents/import` | P2：CSV 批量 | COMP-014 |
| GET/POST `/suppressions`、DELETE `/suppressions/{id}` | 黑名单 / 退订名单；UNSUBSCRIBE 不可删 | COMP-008/013 |

### 任务
| 方法 路径 | 说明 | AC |
|---|---|---|
| POST `/campaigns` | 创建（DRAFT）并快照目标 | CAMP-001/002/003 |
| GET `/campaigns`、GET `/campaigns/{id}` | 列表（含汇总计数）/ 详情 | CAMP-029, STAT-007 |
| GET `/campaigns/{id}/items` | 明细，过滤 `status`、`reason_code`、`q` | CAMP-029 |
| GET `/campaigns/{id}/stats` | 结果统计 | STAT-001 ~ 006 |
| GET `/campaigns/{id}/timeline` | 任务级事件时间线 | AUD-010 |
| POST `/campaigns/{id}/preview` | 干跑：各闸门结果分布，无副作用 | CAMP-024 |
| POST `/campaigns/{id}/start` \| `pause` \| `resume` \| `cancel` | 状态控制 | CAMP-004 ~ 008, 027 |
| POST `/campaigns/{id}/requeue-failed` | P2 | CAMP-028 |

### Webhook（签名鉴权，不用 Admin Token）
| 方法 路径 | 说明 | AC |
|---|---|---|
| POST `/webhooks/whatsapp/status` | 送达 / 已读 / 失败回执 | CAMP-020/021, SYS-009 |
| POST `/webhooks/whatsapp/inbound` | 入站消息（识别 STOP） | COMP-006, SYS-009 |

### 日志与统计
| 方法 路径 | 说明 | AC |
|---|---|---|
| GET `/audit-logs` | 过滤：`actor`、`action`、`entity_type`、`entity_id`、`from`、`to` | AUD-005 |
| GET `/audit-logs/verify` | 哈希链校验（P1） | AUD-004 |
| GET `/send-logs` | 过滤：`task_id`、`item_id`、`phase`、`outcome`、`reason_code`、`from`、`to` | AUD-006 |
| GET `/stats/overview` | 全局概览（P1） | STAT-005 |

### 演示辅助（仅 `DEMO_MODE=true`，否则 404）
| 方法 路径 | 说明 | AC |
|---|---|---|
| POST `/demo/inbound-stop` | 服务端代签名模拟某号码发来 `STOP` | SYS-012 |
| POST `/demo/flush-receipts` | 立即产出并应用 Mock 回执 | SYS-012 |
| POST `/demo/reset` | 清库并重新播种 | SYS-012 |

## 3. 关键请求 / 响应示例

**创建任务**
```http
POST /api/v1/campaigns
{"name":"首轮问候","template_id":3,"selection":{"min_score":70,"batch_id":null,"lead_ids":null}}
→ 201 {"id":7,"status":"DRAFT","total_items":20,"template_id":3,"created_at":"…Z"}
```
空目标 → `422 CAMPAIGN_EMPTY_TARGET`；模板未审核 → `422 TEMPLATE_NOT_APPROVED`。

**启动 / 幂等**
```http
POST /api/v1/campaigns/7/start → 200 {"id":7,"status":"RUNNING"}
POST /api/v1/campaigns/7/start → 200 {"id":7,"status":"RUNNING"}   # 重复调用：无副作用
POST /api/v1/campaigns/7/resume (RUNNING) → 409 CAMPAIGN_INVALID_STATE
```

**统计**
```json
{
  "task_id": 7, "status": "RUNNING", "total": 20,
  "by_status": {"PENDING":3,"SENDING":0,"RETRY_WAIT":1,"SENT":2,"DELIVERED":4,"READ":2,"FAILED":2,"SKIPPED":6},
  "success": 8, "failed": 2, "skipped": 6, "in_progress": 4,
  "success_rate": 0.8,
  "skip_reasons": {"BLACKLISTED":2,"NO_PHONE":3,"UNSUBSCRIBED":1},
  "failure_reasons": {"INVALID_NUMBER":1,"MAX_ATTEMPTS_EXCEEDED":1},
  "attempts_histogram": {"0":9,"1":6,"2":3,"3":2},
  "retry_total": 5,
  "started_at": "…Z", "finished_at": null, "elapsed_seconds": 41.2
}
```

**状态回执 Webhook**
```http
POST /api/v1/webhooks/whatsapp/status
X-Hub-Signature-256: sha256=<hmac-hex of raw body>
{"provider_message_id":"mock-msg-abc","status":"delivered","timestamp":"…Z"}
{"provider_message_id":"mock-msg-def","status":"failed","error":{"code":"131026","message":"…"}}
→ 200 {"applied": true}        # 重复 / 乱序 / 未知消息：200 {"applied": false}
```

**入站消息 Webhook**
```http
POST /api/v1/webhooks/whatsapp/inbound
{"from":"+15555550123","text":"stop","timestamp":"…Z"}
→ 200 {"action":"UNSUBSCRIBED"}   # 其他文本：{"action":"IGNORED"}
```

**导入线索（Mock）**
```http
POST /api/v1/lead-batches/import   {"source":"mock"}
→ 201 {"id":1,"total_rows":52,"imported":44,"duplicates":4,"invalid":4,"warnings":1,"errors":[{"row":47,"code":"INVALID_USERNAME","detail":"…"}]}
```
