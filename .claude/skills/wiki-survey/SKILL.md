---
name: wiki-survey
description: "Generate a survey wiki page from all papers in a conference OR topic directory, aggregating categories, trends, observations, assumptions, tensions, and future directions. Triggers on /wiki-survey <dir>, '整理会议 wiki', '整理 topic wiki', '会议综述', 'topic 综述'. Works for both `osdi-2025` style conference dirs and `ai-infra`/`finance`/`foundation` style topic dirs."
---

# Wiki Survey Skill

Given a `papers/{dir}` directory — either a conference (`osdi-2025`, `mlsys-2026`, ...) or a topic (`ai-infra`, `foundation`, `finance`, `autoresearch`, `time-series`) — ensure every PDF has a wiki paper page, then aggregate into a survey page:

- 会议目录 → `wiki/conferences/{Conf}-{Year}.md` (`type: conference`)
- Topic 目录 → `wiki/themes/{TopicPascalCase}.md` (`type: theme`)

**执行模式：无人值守。** 不中途询问。

## Usage

```
/wiki-survey <dir> [--skip-papers] [--no-index-log] [--output <path>]
```

- `dir`：目录名，例如 `osdi-2025`、`mlsys-2026`、`ai-infra`、`foundation`、`finance`、`autoresearch`、`time-series`
- `--skip-papers`：跳过 Step 1,假设所有 paper wiki 页已存在,只重生成综述
- `--no-index-log`：只写 survey 页，不更新 `wiki/index.md` / `wiki/log.md`。用于大规模 rebuild worker，避免共享文件并发冲突
- `--output <path>`：强制写到指定 `wiki/conferences/*.md` 或 `wiki/themes/*.md`，用于主调度 agent 明确 worker 写入边界

## Step 0 — 判断目录类型

规则(正则匹配 `<dir>`):

- **会议**: `^(osdi|atc|nsdi|sosp|mlsys|fast)-\d{4}$` → `kind=conference`
  - 解析出 `Conf` (大写: `OSDI`/`ATC`/`NSDI`/`SOSP`/`MLSys`/`FAST`) 和 `Year` (4 位)
  - 输出路径: `wiki/conferences/{Conf}-{Year}.md`
- **否则**: `kind=topic`
  - 按下表做 `dir → TopicPascalCase` 映射,未收录时用首字母大写 + 连字符分段:
    | dir | TopicPascalCase |
    |---|---|
    | `ai-infra` | `AI-Infra` |
    | `foundation` | `Foundation` |
    | `finance` | `Finance` |
    | `autoresearch` | `Auto-Research` |
    | `time-series` | `Time-Series` |
    | `agent` | `Agent` |
    | `ai4s` | `AI4S` |
  - 输出路径: `wiki/themes/{TopicPascalCase}.md`

下面所有步骤用 `{OUT_PATH}` 指代 Step 0 决定的输出路径（若传 `--output` 则为指定路径）,`kind` 指代 `conference` 或 `topic`。

## Idempotency

若 `{OUT_PATH}` 已存在,**默认覆盖**,但保留首次生成日期:

- 解析旧文件 frontmatter 里的 `first_generated`
- 新文件 frontmatter 写 `first_generated: {旧日期}`、`last_updated: {今天}`
- 若解析不到,写 `first_generated: {今天}`

## Step 1 — 确保所有 paper wiki 页存在

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

## Step 2 — 收集本目录的 paper wiki 页

按 Step 1b 的匹配逻辑反向做一次:

1. `Glob papers/{dir}/*.pdf` 取全部 `{stem}` 集合
2. `Glob wiki/papers/*.md`,对每个文件 Read frontmatter 的 `source_pdf`,提取 wikilink 内的 stem
3. stem 命中 Step 1 的集合 → 纳入本目录的 paper 集 `P`

读取 `P` 中每篇,提取:

- `name` + `full_title` + `authors` + 一句话总结
- 主要 tags(用于分类)
- `关键观察 / 隐含假设`：该论文依赖的 workload / bottleneck / hardware / scaling / SLO 前提
- `核心方法` 与 `设计取舍`：用于分类和归纳 design space
- `Critical Analysis` 与 `局限与 Future Work`：用于提炼 tensions、open problems、适合小团队继续做的方向

## Step 3 — 生成综述页

类别由本目录实际论文内容动态推断(5-10 类,每类 3-10 篇),**每篇只归入一个类别**。

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

### {Category 1}(N 篇)

- [[{Name}-{Conf}{Year}\|{论文短标题}]] — {一句话要点}
- ...

### {Category 2}(N 篇)

...

## 研究趋势

{3-5 段,每段必须 wikilink 2-3 篇论文作证据。空泛断言无效。}

## 共同观察

{聚合多篇论文共享的 workload / bottleneck / scaling / deployment observation。每条说明由哪些论文支撑，以及 observation 的适用边界。不要把简单 topic overlap 写成共同观察。}

## 互相冲突的假设

{列出本会议中可能互相矛盾的 assumptions 或 evaluation boundary。例如一篇论文假设网络是主瓶颈，另一篇论文的结果暗示 GPU memory 才是主瓶颈。每条必须 wikilink 2 篇以上论文，并说明需要什么 measurement 判定谁更接近真实。}

## 值得关注的方向

{面向小团队(3-5 人、无大规模 GPU 集群)的可行方向,每条含:
- **方向名和描述**
- **为什么小团队能做**
- **哪些论文指向这个空白**(wikilink 具体论文)
- **具体的 open problems**}
```

### `kind=topic` → `wiki/themes/{TopicPascalCase}.md`

```markdown
---
type: theme
topic: {TopicPascalCase}
paper_count: {N}
first_generated: {YYYY-MM-DD}
last_updated: {YYYY-MM-DD}
tags: [topic-overview]
---

# {TopicPascalCase} 综述

> {一句话:本 topic 的核心问题和当前 state-of-the-art}

## 论文列表

按类别分组(动态推断,同会议模板规则):

### {Category 1}(N 篇)

- [[{Name}-{Conf}{Year}\|{短标题}]] — {一句话要点}
- ...

## 主题综述

{跨论文脉络分析。每段 wikilink 2-3 篇论文。允许表达个人判断,但必须有证据。不按会议/时间线走流水账;按问题/方法/趋势组织。3-5 段。}

## 共同观察

{本 topic 中反复出现的 workload / bottleneck / scaling / deployment observation。说明哪些观察已经比较稳，哪些只在特定 benchmark 或系统设定下成立。}

## 假设冲突与脆弱点

{不同路线之间的隐含假设冲突、实验边界冲突、或 production relevance 疑点。每条都要指向具体论文。}

## 值得关注的方向

{结构同会议模板。}
```

## Step 4 — 更新 `wiki/index.md`

若传 `--no-index-log`，跳过本步骤，由主调度 agent 在所有 survey 完成后统一重建 index。

### `kind=conference`

在 `## Conferences` 节下追加一行(按年份倒序、会议名字母序):

```markdown
- [[{Conf}-{Year}]] — {N} 篇 | {一句话画像}
```

若该行已存在则原地更新 `N` 和画像。

### `kind=topic`

在 `## Themes` 节下追加一行(按字母序):

```markdown
- [[{TopicPascalCase}]] — {N} 篇 | {一句话画像}
```

若该行已存在则原地更新。

## Step 5 — 追加 `wiki/log.md`

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

## Step 6 — 简短汇报

```
生成:{OUT_PATH}
已确保 {N} 篇 paper wiki 页
index.md 已更新
log.md 已记录
```

## Important Notes

- **类别动态推断**:不套固定 taxonomy,根据本目录实际论文内容决定
- **每篇论文只出现一次**:跨类别时归入最核心的那个
- **研究趋势/主题综述/共同观察/假设冲突必须 wikilink 证据**,空泛断言无效
- **优先聚合 assumptions**:新版 paper 页的 `关键观察 / 隐含假设` 和 `Critical Analysis` 是 survey 的主要原料；不要只按标题或 tags 聚类
- **区分共识和 tension**:多篇论文共享同一个 observation 才写进「共同观察」；互相 incompatible 或需要 measurement 仲裁的写进「互相冲突的假设」
- **值得关注的方向**:聚焦小团队能做的,不推荐需要大规模资源的
- 会议名大写(`OSDI`、`SOSP`、`MLSys`、`NSDI`、`ATC`、`FAST`),年份 4 位
- Topic 名用 PascalCase 连字符(`AI-Infra`、`Auto-Research`、`Time-Series`)
- 所有内部引用用 wikilink `[[{Name}-{Conf}{Year}]]`;表格内 wikilink 必须转义 `\|`
- Frontmatter 里的 wikilink 必须用双引号包裹成字符串
- 大规模 rebuild 时必须使用 `--skip-papers --no-index-log --output <path>`，只写自己的 conference/theme 页
- 无人值守:遇到类别边界模糊、论文归属不清、命名候选多选一等情况自行决定
