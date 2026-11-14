# 模块规格：template（问候模板与个性化变量）

> 版本 v1.1 · 状态 定稿（2026-11-14 修订 Q-19） · 依赖：`domain/render`、config（`message.brand` / `message.optout_text`）、audit

## 1. 目标

提供**版本化、需审核**的问候模板，支持个性化变量；渲染结果确定、安全（无注入、无超长），并**始终带退订指引**。模拟 WhatsApp"模板需预先审核"的约束。

## 2. 范围与非目标

- **范围**：模板 CRUD（版本化）、审核 / 停用、变量白名单、渲染、预览。
- **非目标**：富媒体、按钮、多语言自动翻译、真实 WhatsApp 模板提交审核。

## 3. 规则

### 3.1 模板与版本
- 创建 → `version=1`、`status=DRAFT`。`(name, version)` 唯一。
- `body` ≤ **800** 字符（给渲染后的变量与页脚留余量；渲染结果另受 1024 字符上限约束）。
- `DRAFT` 可编辑；`APPROVED` 的 `body` **不可变**（409 `TEMPLATE_IMMUTABLE`）；要修改 → `POST /templates/{id}/new-version` 创建 `version+1`（`DRAFT`）。
- 草稿编辑走 `PATCH /templates/{id}`（`body` / `language`），写 `TEMPLATE_UPDATED` 审计；无变化不写审计；非 `DRAFT` 状态返回 409 `TEMPLATE_IMMUTABLE`。
- `approve`：`DRAFT → APPROVED`，记录 `approved_by/at`，写审计。`disable`：任意状态 → `DISABLED`，不可再用于新任务。

### 3.2 变量
语法：`{{var}}` 或 `{{var|默认值}}`（空白可有可无）。正则：`\{\{\s*([a-z_]+)\s*(?:\|([^}]*))?\}\}`。

| 变量 | 来源 | 缺失时 |
|---|---|---|
| `name` | `display_name`，否则 `username` | 不会缺失 |
| `username` | 线索 username | 不会缺失 |
| `keyword` | 线索 `top_keyword` | 无默认值 → 渲染错误；有默认值则用默认值 |
| `brand` | 设置 `message.brand` | 设置有默认值，不会缺失 |
| `optout_text` | 设置 `message.optout_text` | 不会缺失 |

- 出现白名单之外的变量 → 创建 / 更新时 422 `TEMPLATE_UNKNOWN_VARIABLE`，响应列出未知变量名。

### 3.3 渲染（`domain/render.py`，纯函数）
1. 取变量值（见上表）。
2. **清洗**：去除控制字符、换行替换为空格、首尾去空白；来自线索的值（`name`/`username`/`keyword`）截断至 60 字符。
3. 值为空且无默认 → 抛 `RenderError(TEMPLATE_VARIABLE_MISSING)`。
4. 替换变量。
5. 若 `body` 不含 `{{optout_text}}` → 末尾追加 `"\n\n" + optout_text`（**始终保证退订指引存在**）。
6. 渲染后长度 > 1024 → `RenderError(RENDER_TOO_LONG)`。
7. 渲染对**同一输入得到同一输出**（无随机、无时间）。

引擎把 `RenderError` 映射为明细 `SKIPPED(TEMPLATE_VARIABLE_MISSING)`（二者均用此原因码，`detail` 区分）。

### 3.4 预览
`POST /templates/preview`：入参 `{body 或 template_id, lead_id?}`；不指定 `lead_id` 用内置示例线索。**无副作用**：不写 `send_log`、不调用 Messenger、不写审计。

### 3.5 默认种子模板
`greeting_v1`（`APPROVED`，由 seed 创建）：

```
Hi {{name|there}}, greetings from {{brand}}! We noticed you share content about {{keyword|beauty devices}} and wanted to say hello. Feel free to reply anytime. {{optout_text}}
```

## 4. 内部接口

```python
class TemplateService:
    def create(self, name: str, body: str, language: str, operator: str) -> Template
    def update(self, template_id: int, body: str | None, language: str | None, operator: str) -> Template
    def new_version(self, template_id: int, body: str, operator: str) -> Template
    def approve(self, template_id: int, operator: str) -> Template
    def disable(self, template_id: int, operator: str) -> Template
    def preview(self, body: str, lead: LeadView | None) -> str

# domain/render.py
def extract_variables(body: str) -> list[str]
def render(body: str, values: Mapping[str, str | None]) -> str     # 含页脚追加与长度检查
```

## 5. 验收标准

| AC | P | 描述（给定 / 当 / 则） |
|---|---|---|
| AC-TPL-001 | P0 | 给定合法名称与正文，当创建，则得到 `version=1`、`DRAFT`；`body > 800` → 422；`(name, version)` 重复 → 409 |
| AC-TPL-002 | P0 | 给定含未知变量（如 `{{phone}}`）的正文，当创建或新版本，则 422 `TEMPLATE_UNKNOWN_VARIABLE` 并列出变量名 |
| AC-TPL-003 | P0 | 给定 `{{name\|there}}`，当 `display_name` 缺失，则渲染时 `name` 仍取 `username`；当 `keyword` 缺失且有默认值，则使用默认值；语法允许空白（`{{ keyword \| xx }}`） |
| AC-TPL-004 | P0 | 给定 `APPROVED` 模板，当尝试修改 `body`，则 409 `TEMPLATE_IMMUTABLE`；`new-version` 产生 `version+1` 的 `DRAFT`；`approve` 写审计并记录审核人 / 时间 |
| AC-TPL-005 | P0 | 给定 `DRAFT` / `DISABLED` 模板，当创建任务，则 422 `TEMPLATE_NOT_APPROVED`；给定运行中任务的模板被停用，则其后续明细 `SKIPPED(TEMPLATE_NOT_APPROVED)` |
| AC-TPL-006 | P0 | 给定无默认值且值缺失的变量（如线索无 `top_keyword`），当渲染，则抛 `RenderError`，明细 `SKIPPED(TEMPLATE_VARIABLE_MISSING)` 且不调用 Messenger；同一输入两次渲染结果完全相同 |
| AC-TPL-007 | P0 | 给定正文不含 `{{optout_text}}`，当渲染，则末尾自动追加退订指引；已含则不重复追加；渲染后 > 1024 字符 → `RenderError` |
| AC-TPL-008 | P0 | 给定 `display_name` 含换行、控制字符或超过 60 字符，当渲染，则换行变空格、控制字符被移除、值被截断至 60 字符 |
| AC-TPL-009 | P1 | 给定 `POST /templates/preview`，则返回渲染文本，且 `send_log` / `audit_log` / Messenger 调用均无变化 |

## 6. 边界与异常

- 变量值中含 `{{x}}` 字样：不做二次渲染（单趟替换），防止模板注入。
- 页脚追加使用设置值；设置被改后，**已渲染并已发送**的明细不受影响（`rendered_body` 已落库）。
- 名字含 emoji / 多字节字符：截断按 Unicode 码点，不切断代理对。

## 7. 测试要点

- `domain/render` 纯函数参数化：变量缺失 / 默认 / 空白语法 / 注入字符串 / 长度边界（799、800、801；渲染后 1023、1024、1025）。
- 状态流：DRAFT → approve → 尝试改 body 失败 → new-version → 再 approve。
