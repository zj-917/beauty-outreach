# 模块规格：screening（筛选与相关性评分）

> 版本 v1.1 · 状态 定稿（2026-11-14 修订 Q-13/Q-14） · 依赖：`domain/scoring`、`config`（keyword / settings）、`audit`

## 1. 目标

对线索做**可解释、可复现、离线**的相关性评分，并按阈值给出决策：自动入池 / 待人工确认 / 丢弃。这是"筛选准确性"的核心。

## 2. 范围与非目标

- **范围**：关键词匹配、加减分规则、阈值决策、重新评分、评测脚本。
- **非目标**：LLM 评分（预留扩展点：`Scorer` 协议，默认 `RuleScorer`；本期不实现）。

## 3. 评分算法（`domain/scoring.py`，纯函数）

**输入**：线索（`username, display_name, bio, region, language`）、启用的关键词列表、评分设置。
**输出**：`ScoreResult(score:int, reasons:list[Reason], top_keyword:str|None)`。

### 3.1 文本规范化
- NFKC → `casefold()` → 折叠连续空白。
- `username` 额外把 `.` `_` 替换为空格（`led_mask.daily` → `led mask daily`）。

### 3.2 关键词匹配
- **ASCII 词条**（词条全部为 ASCII 字符）：正则 `(?<![a-z0-9])<term>(?:s|es)?(?![a-z0-9])`，词条内空格匹配 `\s+`。含义：全词匹配并允许复数；`rf` 不匹配 `surf`，`led mask` 匹配 `LED masks`。
- **含非 ASCII 字符的词条（如中文）**：子串匹配。
- **最长匹配优先、不重复计分**：把所有启用关键词（正向 + 负向）按 `(len(term) 降序, term 升序)` 排序，逐个在**尚未被占用的文本片段**中匹配；匹配成功的片段被占用，更短的关键词不能再用这些字符计分。例：`beauty device` 命中后，同一处的 `beauty` 不再计分。
- 在三个字段上分别匹配：`bio`（系数 1.0）、`display_name`（0.5）、`username`（0.5）。
- **同一关键词只计一次**：取其在各字段中贡献最大者；`贡献 = weight`（bio）或 `floor(weight/2)`（display_name / username）。

### 3.3 分数构成

`raw = Σ正向贡献 − Σ负向贡献 + 地区调整 + 语言调整 + 短简介惩罚`

| 项 | 规则 | 设置项 |
|---|---|---|
| 地区 | `allowed_regions` 非空时：`region` 缺失 → 0；在名单内 → `+region_bonus`；不在 → `−region_penalty`；名单为空则不评 | `screening.allowed_regions` 等 |
| 语言 | 同上，针对 `language` | `screening.allowed_languages` 等 |
| 短简介 | `len(bio.strip()) < short_bio_min_len`（含空 / null）→ `−short_bio_penalty` | |

`score = clamp(round(raw), 0, 100)`。

### 3.4 可解释原因 `score_reasons`
每项 `{"code","detail","delta"}`：`KW_POS`（detail 如 `bio:beauty device`）、`KW_NEG`、`REGION_MATCH` / `REGION_MISMATCH`、`LANG_MATCH` / `LANG_MISMATCH`、`BIO_TOO_SHORT`；若发生截断追加 `CLAMP`（`delta = score − raw`）。**不变量：所有 `delta` 之和恒等于 `score`。**

### 3.5 `top_keyword`
贡献最大的**正向**关键词（并列取 `term` 字典序最小）；无正向命中为 `null`。供模板变量 `{{keyword}}` 使用。贡献为 0 的命中（如 `weight=1` 只命中 display_name / username）不计入 `reasons`，也不参与 `top_keyword`。

## 4. 决策规则

| 条件 | 结果（`status` / `decision_source`） |
|---|---|
| `score ≥ threshold_high` 且 `auto_approve_enabled` | `APPROVED` / `AUTO` |
| `threshold_low ≤ score`（且上一行不成立） | `PENDING_REVIEW` / `AUTO` |
| `score < threshold_low` | `DISCARDED` / `AUTO` |

默认阈值：`high=70`，`low=40`。校验：`0 ≤ low < high ≤ 100`。

## 5. 运行与重新评分

- `POST /leads/screen`（可选 `batch_id` / `lead_ids`，两者同时给出时取交集）：对 `status ∈ {NEW, PENDING_REVIEW, DISCARDED}` 的线索评分并决策。
- **人工决定具有粘性**：`APPROVED` / `REJECTED`（无论 `decision_source`）都不被重新评分改变——这是有意的取舍（自动入池后即使关键词调整也不撤回；运营可手动移出）。
- 返回 `{processed, approved, pending_review, discarded, unchanged}`。计数定义：`processed` = 本次进入重算的线索数；`approved` / `pending_review` / `discarded` = 重算后落入各状态的条数，三者之和等于 `processed`；`unchanged` = 其中状态与重算前相同的条数。`APPROVED` / `REJECTED` 不进入候选，也不计入上述任何计数。
- 每次运行写**一条** `LEAD_SCREENING_RUN` 审计（含计数与阈值快照），不逐条写。

## 6. 初始关键词与权重（种子数据，可在配置页调整）

| 正向（term → weight） | |
|---|---|
| `美容仪` 30 · `beauty device` 30 · `skincare device` 30 | 核心词 |
| `导入仪` 25 · `led mask` 25 · `microcurrent` 25 | 设备类 |
| `射频` 20 · `radio frequency` 20 · `face massager` 20 · `red light therapy` 20 | 设备类 |
| `skincare` 15 · `抗衰` 12 · `anti-aging` 12 · `护肤` 12 · `beauty` 10 · `美妆` 8 | 泛护肤 |

| 负向（term → weight） | |
|---|---|
| `wholesale` 30 · `dropship` 30 · `批发` 30 · `代购` 30 · `招代理` 30 | 批发 / 代购 |
| `reseller` 25 · `giveaway` 20 · `follow4follow` 40 · `f4f` 40 | 营销 / 互关 |

> 初始值依据 `05-mock-data.md` §6.1 的手算示例；最终以 `scripts/eval_screening.py` 评测结果为准微调，微调记入 `CHANGELOG.md`。

## 7. 验收标准

| AC | P | 描述（给定 / 当 / 则） |
|---|---|---|
| AC-SCR-001 | P0 | 给定相同线索与相同配置，当多次评分，则 `score / reasons / top_keyword` 完全一致（确定性，与关键词存储顺序无关） |
| AC-SCR-002 | P0 | 给定 bio 命中正向词，当评分，则加 `weight`；仅 username / display_name 命中则加 `floor(weight/2)`；同一关键词在多个字段命中只取最大者一次 |
| AC-SCR-003 | P0 | 给定命中负向词，当评分，则扣 `weight`（规则同 AC-SCR-002）；示例：§`05-mock-data.md` 6.1 第 3 行得分 0 |
| AC-SCR-004 | P0 | 给定 `rf` 与文本 `surf & perfume`，则不匹配；给定 `led mask` 与 `LED masks`，则匹配；中文词条按子串匹配；大小写与全角半角不敏感；username 中的 `.` `_` 视为空格 |
| AC-SCR-005 | P0 | 给定 `beauty device` 与 `beauty` 同时为关键词，当文本含 `beauty device`，则只计 `beauty device`；文本另处单独出现 `beauty` 时才再计 `beauty` |
| AC-SCR-006 | P0 | 给定地区 / 语言白名单非空，当评分，则在名单内加分、不在名单内扣分、缺失为 0；白名单为空则不评该项 |
| AC-SCR-007 | P0 | 给定空 / 过短简介，当评分，则扣 `short_bio_penalty` |
| AC-SCR-008 | P0 | 给定任意输入，则 `score` 为 `[0,100]` 的整数 |
| AC-SCR-009 | P0 | 给定任意评分结果，则 `reasons` 中每项含 `code/detail/delta`，且所有 `delta` 之和等于 `score` |
| AC-SCR-010 | P0 | 给定三档分数，当按默认阈值决策，则分别为 `APPROVED(AUTO)` / `PENDING_REVIEW(AUTO)` / `DISCARDED(AUTO)`；`auto_approve_enabled=false` 时高分也进 `PENDING_REVIEW`；恰等于阈值时取较高一档 |
| AC-SCR-011 | P0 | 给定 `low ≥ high`、越界值，当更新阈值设置，则 422 `VALIDATION_ERROR` |
| AC-SCR-012 | P0 | 给定修改关键词后重新评分，则 `NEW/PENDING_REVIEW/DISCARDED` 被重算；`APPROVED/REJECTED`（含人工决定）保持不变 |
| AC-SCR-013 | P0 | 给定一次筛选运行，则写入恰好一条 `LEAD_SCREENING_RUN` 审计，含 `processed/approved/pending_review/discarded` 与阈值 |
| AC-SCR-014 | P1 | 给定 Mock 数据集与默认配置，当运行 `scripts/eval_screening.py`，则输出混淆矩阵与每条错判的 `reasons`，且 Precision ≥ 0.95、Recall ≥ 0.85、边缘带准确率 ≥ 0.75 |
| AC-SCR-015 | P0 | 给定有正向命中的线索，则 `top_keyword` 为贡献最大者（并列取字典序最小）；无正向命中为 `null` |

## 8. 边界与异常

- 没有任何启用的关键词 → 所有线索只有地区 / 语言 / 短简介项，评分多数落入 `DISCARDED`；运行不报错，但响应附 warning `NO_ENABLED_KEYWORDS`。
- 正则必须对词条做 `re.escape`，避免关键词含特殊字符导致错误或 ReDoS。
- 关键词数量上限 500（配置层校验），保证评分耗时可预期。

## 9. 测试要点

- `domain/scoring` 纯函数单测：`05-mock-data.md` §6.1 三个手算示例逐字断言；边界参数化（`rf`/`surf`、复数、全角、`@`、重叠词）。
- 属性测试风格断言：对随机输入 `Σdelta == score`、`0≤score≤100`、结果与关键词顺序无关。
- 集成：导入 Mock → 评分 → 决策分布；人工审核后重新评分不覆盖。
