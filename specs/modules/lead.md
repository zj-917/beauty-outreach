# 模块规格：lead（线索采集与清洗）

> 版本 v1.1 · 状态 定稿（2026-11-14 修订 Q-12） · 依赖：`core/security`、`domain/normalize`、`domain/phone`、`audit`

## 1. 目标

把外部来源的"公开用户线索"安全地导入系统：标准化、校验、去重、记录来源与导入报告；手机号与授权信息按合规方式入库。

## 2. 范围与非目标

- **范围**：`LeadSource` 接口；`MockSource`、`CsvJsonSource`、`InstagramApiStub`；导入服务（逐行标准化 → 校验 → 去重 → 入库）；批次与导入报告；线索列表 / 详情 API。
- **非目标**：真实 Instagram 采集；评分与决策（见 screening）；授权的独立管理（见 compliance）。

## 3. 输入格式

JSON 数组或 CSV（UTF-8，可含 BOM；CRLF / LF 均可）。必需列只有 `username`；多余列忽略。

| 字段 | 必填 | 说明 |
|---|---|---|
| `username` | ✅ | Instagram 用户名 |
| `display_name`, `bio` | | `bio` 超过 2000 字符截断 |
| `region` | | ISO-3166 alpha-2 |
| `language` | | BCP-47，取主语言子标签 |
| `source_url` | | 若提供，必须是 `https://(www.)instagram.com/...` |
| `phone` | | 企业自有授权数据中的号码，E.164 |
| `consent_status` | | `GRANTED` \| `REVOKED`；仅当同时有 `phone` 时生效 |
| `consent_source` / `consent_evidence` | | `GRANTED` 时两者必填，否则授权被忽略并计一条 warning |

## 4. 处理规则

**4.1 规范化**（`domain/normalize.py`，纯函数）

| 字段 | 规则 |
|---|---|
| username | NFKC → 去首尾空白 → 去开头 `@` → 转小写 |
| display_name / bio | NFKC → 去首尾空白；空串视为 `null` |
| region | 去空白 → 转大写；非 2 位字母 → `null` + warning `INVALID_REGION` |
| language | 去空白 → 转小写 → 取 `-`/`_` 前的主标签；非 2–3 位字母 → `null` + warning `INVALID_LANGUAGE` |
| phone | 去空格 / 连字符 / 括号；必须匹配 `^\+[1-9]\d{7,14}$`，否则丢弃号码 + warning `INVALID_PHONE_DROPPED`（线索保留） |

**4.2 校验（不合格的行整行拒绝，计入 `invalid`）**

- `MISSING_USERNAME`：规范化后为空。
- `INVALID_USERNAME`：不匹配 `^[a-z0-9._]{1,30}$`。
- `INVALID_SOURCE_URL`：提供了但不是 `https` 的 instagram.com / www.instagram.com 链接。

**4.3 去重（先 username，后 phone_hash）**

1. 规范化 username 已存在（批内或历史）→ 重复，**不新建**，计入 `duplicates`。
   - 若新行带的号码与已存的号码不同，或已存线索没有号码、而该号码已属于**另一条线索** → 错误记录码 `IMPORT_CONFLICT`（保留原号码 / 不补号码，不覆盖）；否则 `DUPLICATE_USERNAME`。
   - 合并策略：**先写者优先**，仅把已存线索中**为空**的字段用新行补全（含此前缺失的、且未被其他线索占用的号码与授权）。
2. 否则若 `phone_hash` 已被**另一条线索**使用 → `DUPLICATE_PHONE`，计入 `duplicates`，不新建（一个收件人一条线索）。该行携带的完整授权仍按 §4.4 应用（授权按 `phone_hash` 归属，不因未新建线索而丢失）。

**4.4 手机号与授权入库**

- `phone_enc`（Fernet）、`phone_hash`（HMAC-SHA256）、`phone_masked`；`DB` 中不得出现明文。
- 行内 `consent_status`：`GRANTED`（含 source + evidence）→ upsert `contact_consent`；`REVOKED` → upsert REVOKED；其余情况忽略授权并计 warning `CONSENT_INCOMPLETE`。无授权字段 = 不写记录（即 UNKNOWN，不可发送）。
- 授权按 `phone_hash` 归属，与是否新建线索无关：行合法且号码有效时，即使该行因 username 重复（`IMPORT_CONFLICT` 除外）或 `DUPLICATE_PHONE` 未新建线索，也按上一条规则 upsert。`IMPORT_CONFLICT` 行保留的是原号码，其新号码与本线索不一致，不应用授权。
- 授权按 `phone_hash` 唯一；已存在记录的号码不被导入覆盖，除非新行是 `REVOKED`（撤销总是生效）。

**4.5 原子性**：整个批次在**一个事务**内处理；行级错误不中断（记入报告），异常则整批回滚；成功后写一条 `LEAD_BATCH_IMPORTED` 审计。

**4.6 导入报告（`lead_batch.errors`）**：`[{"row": 12, "code": "INVALID_USERNAME", "detail": "…"}]`；`row` 从 1 起。`detail` 不含号码。

**4.7 错误码**：`MISSING_USERNAME` `INVALID_USERNAME` `INVALID_SOURCE_URL`（→ invalid）· `DUPLICATE_USERNAME` `DUPLICATE_PHONE` `IMPORT_CONFLICT`（→ duplicates）· `INVALID_PHONE_DROPPED` `INVALID_REGION` `INVALID_LANGUAGE` `CONSENT_INCOMPLETE`（→ warnings）。

## 5. 内部接口

```python
class LeadService:
    def import_batch(self, source: LeadSource, *, source_type: str, source_name: str, operator: str) -> LeadBatch
    def list_leads(self, filters, page) -> Page[LeadView]
    def get_lead(self, id: int) -> LeadView
```

`LeadView` 只含 `phone_masked`，不含 `phone_enc` / `phone_hash`。

## 6. API

见 `04-api-contract.md`：`POST /lead-batches/import`、`GET /lead-batches[/{id}]`、`GET /leads[/{id}]`。
`source: "instagram_api"` → `501 PROVIDER_NOT_ENABLED`。空文件 / 缺 `username` 列 / 非 csv/json → `422 VALIDATION_ERROR`。

## 7. 验收标准

| AC | P | 描述（给定 / 当 / 则） |
|---|---|---|
| AC-LEAD-001 | P0 | 给定 Mock 数据集，当 `POST /lead-batches/import {"source":"mock"}`，则创建一个批次，合法行入库为 `NEW`，响应含 `total_rows/imported/duplicates/invalid/warnings`，且数字与 `05-mock-data.md` §2 一致 |
| AC-LEAD-002 | P0 | 给定合法 CSV 与 JSON 文件，当 multipart 上传，则解析入库；BOM、CRLF、多余列均可处理；非 csv/json 或空文件 → 422 |
| AC-LEAD-003 | P0 | 给定 `@Glow.Mia `、`us`、`en-US`，当导入，则 username=`glow.mia`、region=`US`、language=`en` |
| AC-LEAD-004 | P0 | 给定缺 username / 非法字符 / 超 30 字符的行，当导入，则这些行不入库、记入 `errors` 且计入 `invalid`，其余行正常入库，整批不中断 |
| AC-LEAD-005 | P0 | 给定批内或历史中已存在的 username（含大小写 / `@` 差异）或已被他人使用的号码，当导入，则不新建线索、计入 `duplicates`；已存线索的**空字段**被补全，非空字段不被覆盖 |
| AC-LEAD-006 | P1 | 给定同 username 但号码不同，当导入，则保留原号码，记录 `IMPORT_CONFLICT` |
| AC-LEAD-007 | P0 | 给定非 E.164 号码，当导入，则线索保留、号码置空、记 warning `INVALID_PHONE_DROPPED` |
| AC-LEAD-008 | P0 | 给定带号码的线索，当入库，则 `phone_enc` 可解密还原、`phone_hash` 稳定、`phone_masked` 符合规则；数据库文件（含 WAL）中搜不到明文号码；任何 API 响应不含 `phone_enc` / `phone_hash` / 明文号码 |
| AC-LEAD-009 | P0 | 给定行内 `consent_status=GRANTED` 且含 source+evidence，当导入，则写入 `contact_consent`；缺 evidence → 不写授权并记 `CONSENT_INCOMPLETE`；`REVOKED` 总是生效 |
| AC-LEAD-010 | P0 | 给定 `source_url` 非 instagram.com / 非 https，当导入，则该行 `INVALID_SOURCE_URL` 被拒；缺省（null）允许 |
| AC-LEAD-011 | P0 | 给定同一文件，当连续导入两次，则第二次 `imported=0`，A–E 类合法行全部计入 `duplicates`（48），F 类 4 行仍计入 `invalid`（`warnings=1`），线索总数不变 |
| AC-LEAD-012 | P0 | 给定 `source=instagram_api`，当调用，则返回 501 `PROVIDER_NOT_ENABLED`，且测试证明未发起任何网络连接 |
| AC-LEAD-013 | P0 | 给定任一成功导入，则批次记录 `source_type/source_name/created_by/created_at`，并写入一条 `LEAD_BATCH_IMPORTED` 审计（含计数，不含号码） |
| AC-LEAD-014 | P2 | 给定超过 5000 行或 5MB 的文件，当上传，则 413 `LEAD_IMPORT_TOO_LARGE` |
| AC-LEAD-015 | P0 | 给定已导入数据，当 `GET /leads`，则支持 `status/min_score/batch_id/q/region/language` 过滤与分页；`GET /lead-batches/{id}` 返回完整导入报告；响应中号码仅 `phone_masked` |

## 8. 边界与异常

- 导入过程中发生未预期异常 → 整批回滚，不留半个批次；返回 500 `INTERNAL_ERROR`（不泄漏堆栈）。
- CSV 引号 / 逗号 / 换行内嵌：按标准 CSV 解析。
- 超长字段：`bio` 截断到 2000；`display_name` 截断到 100。
- 号码相同但格式不同（`+1 555-555-0101` vs `+15555550101`）：规范化后视为同一号码。

## 9. 测试要点

- `domain/normalize` 参数化单测（大量边界输入）。
- 用 `05-mock-data.md` 的 52 行跑集成测试，断言报告计数与 E1–E4、F1–F4 的归类。
- 泄漏扫描：导入后检查 SQLite 文件字节、API 响应、日志（caplog）。
- `InstagramApiStub`：socket 守卫夹具下调用不触发任何连接。
