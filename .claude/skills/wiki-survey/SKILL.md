---
name: wiki-survey
description: "Generate or refresh conference, topic, and curated cross-directory theme surveys, preserving explicit core membership and aggregating evidence, tensions, and future directions. Triggers on /wiki-survey with a directory or --theme, '整理会议 wiki', '整理 topic wiki', '刷新 theme', '会议综述', or 'topic 综述'."
---

# Wiki 综述 Skill

支持两种输入：`papers/{dir}` 用于 conference/topic ingest；`--theme {ThemeName}` 用于刷新跨目录策展 theme。Theme 允许多重归属，`## 核心论文` 是唯一权威成员集合。

- 会议目录 → `wiki/conferences/{Conf}-{Year}.md` (`type: conference`)
- Topic 目录 → `wiki/themes/{TopicPascalCase}.md` (`type: theme`)

**执行模式：无人值守。** 不中途询问。

## 用法

```
/wiki-survey <dir> [--skip-papers] [--no-index-log] [--output <path>]
/wiki-survey --theme <ThemeName> [--no-index-log]
```

- `dir`：目录名，例如 `osdi-2025`、`mlsys-2026`、`ai-infra`、`agent-systems`、`foundation`、`finance`、`autoresearch`、`time-series`
- `--skip-papers`：跳过 Step 1,假设所有 paper wiki 页已存在,只重生成综述
- `--no-index-log`：只写 survey 页，不更新 `wiki/index.md` / `wiki/log.md`。用于大规模 rebuild worker，避免共享文件并发冲突
- `--output <path>`：强制写到指定 `wiki/conferences/*.md` 或 `wiki/themes/*.md`，用于主调度 agent 明确 worker 写入边界
- `--theme`：刷新已存在的 `wiki/themes/{ThemeName}.md`；隐含 `--skip-papers`，不得改变核心成员集合

## 步骤 0 — 判断目录类型

若传 `--theme`：

- 要求 `wiki/themes/{ThemeName}.md` 已存在且有合法 theme frontmatter 与 `## 核心论文`
- 设 `kind=curated-theme`，输出固定为该页；`--output` 若不等于该路径则拒绝
- 从核心区读取成员；读取 `member_tag` 和可选 `candidate_tags`

否则按正则匹配 `<dir>`：

- **会议**: `^(osdi|atc|nsdi|sosp|mlsys|fast)-\d{4}$` → `kind=conference`
  - 解析出 `Conf` (大写: `OSDI`/`ATC`/`NSDI`/`SOSP`/`MLSys`/`FAST`) 和 `Year` (4 位)
  - 输出路径: `wiki/conferences/{Conf}-{Year}.md`
- **否则**: `kind=topic`
  - 按下表做映射；未收录时用首字母大写 + 连字符分段，并按内容判断 kind/tag：
    | dir | Theme | theme_kind | member_tag |
    |---|---|---|---|
    | `ai-infra` | `AI-Infra` | `area` | `area/ai-infra` |
    | `foundation` | `Foundation` | `lens` | `lens/foundation` |
    | `finance` | `Finance` | `domain` | `domain/finance` |
    | `autoresearch` | `Auto-Research` | `domain` | `domain/auto-research` |
    | `time-series` | `Time-Series` | `area` | `area/time-series` |
    | `agent-systems` | `Agent-Systems` | `area` | `area/agent-systems` |
    | `ai4s` | `AI4S` | `domain` | `domain/ai4s` |
  - 输出路径: `wiki/themes/{TopicPascalCase}.md`

下面所有步骤用 `{OUT_PATH}` 指代 Step 0 决定的输出路径（若传 `--output` 则为指定路径）,`kind` 指代 `conference` 或 `topic`。

## Idempotency

若 `{OUT_PATH}` 已存在，保留 `first_generated`、`theme_kind`、`member_tag`、`candidate_tags` 和既有核心成员。只重写综合内容与分类顺序，不丢弃人工策展状态。

- 解析旧文件 frontmatter 里的 `first_generated`
- 新文件 frontmatter 写 `first_generated: {旧日期}`、`last_updated: {今天}`
- 若解析不到,写 `first_generated: {今天}`

## 步骤 1 — 确保所有论文 wiki 页存在

除非传了 `--skip-papers`。

### Step 1a — 先补 markdown(必须先于 1b 完成)

```bash
uv run scripts/run_mineru.py papers/{dir} markdowns/{dir} -j 2 -m txt
```

脚本幂等,跳过已解析 PDF。严格串行: 1b 的 `wiki-paper` 调用依赖 markdown 已就绪。

### Step 1b — 为缺 wiki 页的 PDF 生成

1. `Glob papers/{dir}/*.pdf` 获得 PDF 列表,记下每个 `{stem}`
2. 对每个 `{stem}` 检查是否已有 wiki paper 页:
   - Grep `wiki/papers/` 里匹配 `source_pdf: "\[\[{stem}\.pdf\]\]"`(转义点和方括号),命中即视为已存在
3. 对缺页的 PDF,调用 `/wiki-paper papers/{dir}/{stem}.pdf`
   - `N > 10` 时可串并行交替,每篇间不阻塞
   - `N <= 10` 直接串行

## 步骤 2 — 收集论文 wiki 页

### Conference / topic 模式

按 Step 1b 的匹配逻辑反向收集。Conference 集合等于目录论文；topic 集合等于「既有核心成员 ∪ 当前目录论文」，以保留跨目录策展成员。

1. `Glob papers/{dir}/*.pdf` 取全部 `{stem}` 集合
2. `Glob wiki/papers/*.md`,对每个文件 Read frontmatter 的 `source_pdf`,提取 wikilink 内的 stem
3. stem 命中 Step 1 的集合 → 纳入本目录的 paper 集 `P`

### Curated theme 模式

- 只从现有 `## 核心论文` 读取 `P`，不得根据 tag 自动增删
- 扫描 `member_tag` 和可选 `candidate_tags` 命中的非成员，最终仅报告 candidate
- `## 邻接资料` / `## 邻接与排除案例` 可参与综合，但不进入 `paper_count`

读取 `P` 中每篇,提取:

- `name` + `full_title` + `authors` + 一句话总结
- 主要 tags(用于分类)
- `关键观察 / 隐含假设`：该论文依赖的工作负载、瓶颈、硬件、规模扩展与 SLO 前提
- `核心方法` 与 `设计取舍`：用于分类和归纳设计空间
- `批判性分析` 与 `局限与后续工作`（兼容旧英文标题）：用于提炼矛盾、开放问题和适合小团队继续做的方向

### Step 2a — 建立页内术语表

写综述前先列出会反复出现的普通概念，为每个概念选定全页唯一的表达。默认读者具备一般技术背景，但不假设熟悉该会议或主题的专业术语。

- **有成熟中文译法**：首次写成「中文术语（English）」，随后只用中文。例如「验证器（verifier）」、「基线（baseline）」、「工作负载（workload）」。
- **英文专名、系统名、模型名、基准名、API、指标、变量和代码标识**：保留准确拼写，但在首次语义性出现时用中文解释其角色或含义；不用音译替代系统名。
- **英文缩写**：首次同时给出中文含义、英文原词和缩写，例如「样本外（out-of-sample，OOS）」；后文可只用缩写。
- **没有自然中文译法**：保留英文，首次用一句通顺中文说明它是什么、在本页中起什么作用。
- **中文术语也要解释**：对非本领域读者不自明的概念，首次不能只列中英名称，还要说明它衡量什么或解决什么问题。

如果重复专业术语超过 5 种，在第一张矩阵之前增加简短的「阅读提示」；否则在正文首次出现处直接解释。「首次」指整个页面的首次语义性出现，不在每个章节重复定义。

反例：「signal / factor / model 生成」、「paper/live deployment」、「中文连接词 + 连续英文名词」。应改为「生成信号、因子与预测模型」、「模拟盘与实盘部署」，并在首次出现时解释。

## 步骤 3 — 生成综述页

类别由本目录实际论文内容动态推断，通常为 3–10 类；小集合可更少，不为满足数量强行拆分。每篇只归入一个主类别以保持目录可读；交叉属性进入设计空间矩阵。先解释概念和组织轴，再展示矩阵。

全页只选一条主要组织轴，例如问题链路、方法路线或证据强度。分类表、流程表和成熟度表若重复表达同一关系，合并为一张表。每段主要说明一个判断，分开写论文证据、综述推断和尚未验证的建议。邻接主题的材料只保留对本页主线必要的部分。

### `kind=conference` → `wiki/conferences/{Conf}-{Year}.md`

```markdown
---
type: conference
venue: {Conf}
year: {Year}
paper_count: {N}
first_generated: {YYYY-MM-DD}
last_updated: {YYYY-MM-DD}
---

# {Conf} {Year}

> {一句话画像:论文总数 + 研究热点分布}

## 概览

{3-5 段。主题分布、新出现的研究范式、社区兴趣迁移、与往年差异。每段 2-3 句。}

## 论文分类

### {类别 1}(N 篇)

- [[{Name}-{Conf}{Year}\|{论文短标题}]] — {一句话要点}
- ...

### {类别 2}(N 篇)

...

## 研究趋势

{3-5 段,每段必须 wikilink 2-3 篇论文作证据。空泛断言无效。}

## 设计空间矩阵

| 论文 | 工作负载 | 瓶颈 | 机制 | 资源 | SLO / 正确性 | 规模 |
|---|---|---|---|---|---|---|
| [[Paper]] | | | | | | |

每格只写 paper 页有证据的属性；未知写 `未报告`，不从标题猜测。表格内 wikilink 必须转义 `\|`。

## 共同观察

{聚合多篇论文共享的工作负载、瓶颈、规模扩展或部署观察。每条说明由哪些论文支撑，以及观察的适用边界。不要把简单的主题重合写成共同观察。}

## 互相冲突的假设

{列出本会议中可能互相矛盾的隐含假设或评测边界。例如一篇论文假设网络是主瓶颈，另一篇论文的结果暗示 GPU 显存才是主瓶颈。每条必须 wikilink 2 篇以上论文，并说明需要什么测量判定谁更接近真实。}

## 值得关注的方向

{面向小团队(3-5 人、无大规模 GPU 集群)的可行方向,每条含:
- **方向名和描述**
- **为什么小团队能做**
- **哪些论文指向这个空白**(wikilink 具体论文)
- **具体的待解决问题**}
```

### `kind=topic` → `wiki/themes/{TopicPascalCase}.md`

```markdown
---
type: theme
topic: {TopicPascalCase}
theme_kind: {area | domain | lens}
member_tag: {canonical facet}
paper_count: {N}
first_generated: {YYYY-MM-DD}
last_updated: {YYYY-MM-DD}
tags: [topic-overview]
---

# {TopicPascalCase} 综述

> {一句话：本主题的核心问题和当前进展}

## 核心论文

按类别分组（动态推断，同会议模板规则）：

### {类别 1}(N 篇)

- [[{Name}-{Conf}{Year}\|{短标题}]] — {一句话要点}
- ...

## 主题综述

{跨论文脉络分析。每段 wikilink 2-3 篇论文。允许表达个人判断，但必须有证据。不按会议或时间线写流水账；按问题、方法或趋势组织。3-5 段。}

## 设计空间矩阵

使用会议模板相同的「工作负载 / 瓶颈 / 机制 / 资源 / SLO 或正确性 / 规模」矩阵，表达正交关系，不重复分类列表。对小型或领域性主题，可用更符合内容的中文列名，但仍只保留一张主矩阵。

## 共同观察

{本主题中反复出现的工作负载、瓶颈、规模扩展或部署观察。说明哪些观察已经比较稳，哪些只在特定基准或系统设定下成立。}

## 假设冲突与脆弱点

{不同路线之间的隐含假设冲突、实验边界冲突或生产相关性疑点。每条都要指向具体论文。}

## 值得关注的方向

{结构同会议模板。}
```

### Step 3a — 成稿复核

写完 `{OUT_PATH}` 后，在更新 index 和 log 前完成两类检查：

1. **语义与可读性**：逐个审查 frontmatter、wikilink、代码、公式和外部 URL 之外的拉丁字母词。每个保留词必须属于专名、指标、API 或无自然译法的术语，且首次已有中文解释。消除英文串词、英文普通概念表头和重复定义。
2. **确定性规则**：运行 `uv run python .claude/skills/wiki-lint/lint.py --language-only {OUT_PATH}`，并复查表格内 wikilink 的 `\|`、frontmatter 和核心成员计数。语言 lint 是保守检查；`language_warnings=0` 不能替代上一步的语义复核。

index 中的一句话画像与 log 中的普通叙述也遵守同一写作规则。

## 步骤 4 — 更新 `wiki/index.md`

若传 `--no-index-log`，跳过本步骤，由主调度 agent 在所有 survey 完成后统一重建 index。

### `kind=conference`

在 `## Conferences` 节下追加一行(按年份倒序、会议名字母序):

```markdown
- [[{Conf}-{Year}]] — {N} 篇 | {一句话画像}
```

若该行已存在则原地更新 `N` 和画像。

### `kind=topic | curated-theme`

在 `## 主题` 下按 `theme_kind` 更新对应小节：`area` →「系统领域」，`domain` →「应用与研究目标」，`lens` →「横切与策展视角」。小节内按字母序：

```markdown
- [[{TopicPascalCase}]] — {N} 篇 | {一句话画像}
```

若该行已存在则原地更新。

## 步骤 5 — 追加 `wiki/log.md`

若传 `--no-index-log`，跳过本步骤，由主调度 agent 统一追加 rebuild log。

在文件顶部插入(倒序 = 最新在前):

```markdown
## [{YYYY-MM-DD}] {显示名} 综述生成
- 生成：[[{显示名}]]
- 聚合 {N} 篇 paper wiki 页
- 分类 {M} 个
```

`显示名`: conference 用 `{Conf}-{Year}`; topic 用 `{TopicPascalCase}`(也是输出页文件名 stem)。

**禁止** `[[{显示名}]]({OUT_PATH})` 或 `[[{显示名}]]({OUT_PATH})` 这种 wikilink + paren 混合写法——`[[X]]` 已是有效 Obsidian 链接,后面的路径会被解析成字面文本。需要强调路径时另起一行用 backtick 包裹: ``生成路径: `{OUT_PATH}` ``。

## 步骤 6 — 简短汇报

```
生成:{OUT_PATH}
已确保 {N} 篇 paper wiki 页
index.md 已更新
log.md 已记录
```

## 重要说明

- **类别动态推断**:不套固定 taxonomy,根据本目录实际论文内容决定
- **成员权威来源**：只认 `## 核心论文`；每篇核心论文只在其中一个主分类出现一次，跨类别属性写入 design-space matrix
- **多重 theme 合法**：同一 paper 可出现在多个 theme；`member_tag` 表达该归属
- **candidate 不自动晋升**：tag 只负责发现；策展判断后才可写入核心区
- **研究趋势/主题综述/共同观察/假设冲突必须 wikilink 证据**,空泛断言无效
- **优先聚合假设**：新版论文页的 `关键观察 / 隐含假设` 和 `批判性分析` 是综述的主要原料；不要只按标题或 tags 聚类
- **中文优先**：综述正文、分类名、表头和普通概念使用中文；系统名、模型名、benchmark、API、指标和代码标识保留英文。普通概念首次出现时补英文原词。
- **区分共识和 tension**:多篇论文共享同一个 observation 才写进「共同观察」；互相 incompatible 或需要 measurement 仲裁的写进「互相冲突的假设」
- **值得关注的方向**:聚焦小团队能做的,不推荐需要大规模资源的
- 会议名大写(`OSDI`、`SOSP`、`MLSys`、`NSDI`、`ATC`、`FAST`),年份 4 位
- Topic 名用 PascalCase 连字符(`AI-Infra`、`Auto-Research`、`Time-Series`)
- 所有内部引用用 wikilink `[[{Name}-{Conf}{Year}]]`;表格内 wikilink 必须转义 `\|`
- Frontmatter 里的 wikilink 必须用双引号包裹成字符串
- 大规模 rebuild 时必须使用 `--skip-papers --no-index-log --output <path>`，只写自己的 conference/theme 页
- 无人值守:遇到类别边界模糊、论文归属不清、命名候选多选一等情况自行决定
