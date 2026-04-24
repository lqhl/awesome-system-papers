---
name: wiki-conference
description: "Generate a conference survey wiki page from all papers in a given conference directory. Triggers on /wiki-conference <conf>-<year>, '整理会议 wiki', '会议综述'. Replaces the old papers-digest for conference directories."
---

# Wiki Conference Skill

Given a conference directory (e.g. `osdi-2025`、`mlsys-2026`、`ai-infra`），确保该目录所有论文都有对应 wiki paper 页，然后聚合生成 `wiki/conferences/{Conf}-{Year}.md`（或 `wiki/themes/{Topic}.md` 若是 topic 目录）。

**执行模式：无人值守。** 不中途询问。

## Usage

```
/wiki-conference <dir> [--skip-papers]
```

- `dir`：会议或 topic 目录名（如 `osdi-2025`、`mlsys-2026`、`ai-infra`、`foundation`、`finance`、`autoresearch`、`time-series`）
- `--skip-papers`：跳过 Step 1，假设所有 paper wiki 页已存在，只重生成会议综述

## Idempotency

若 `wiki/conferences/{Conf}-{Year}.md` 或 `wiki/themes/{Topic}.md` 已存在，**默认覆盖**，但保留首次生成日期：

- 解析旧文件 frontmatter 里的 `first_generated`
- 新文件 frontmatter 写 `first_generated: {旧日期}`、`last_updated: {今天}`
- 若解析不到，写 `first_generated: {今天}`

## Step 1 — 确保所有 paper wiki 页存在

除非传了 `--skip-papers`：

### Step 1a — 先补 markdown（必须先于 1b 完成）

```bash
uv run scripts/run_mineru.py papers/{dir} markdowns/{dir} -j 2 -m txt
```

脚本幂等，跳过已解析 PDF。严格串行：1b 的并行 `wiki-paper` 调用依赖 markdown 已就绪。

### Step 1b — 为缺 wiki 页的 PDF 生成

1. `Glob papers/{dir}/*.pdf` 获得 PDF 列表
2. 对每个 PDF 检查：是否存在对应 `wiki/papers/*.md`？
   - 匹配方式：Read `wiki/papers/*.md` frontmatter 的 `source_pdf`，匹配 `[[{pdf-stem}.pdf]]`
   - 或者 Grep `wiki/papers/` 内容里是否出现 `{pdf-stem}.pdf`
3. 对缺页的 PDF，串行或批量调用 `/wiki-paper papers/{dir}/{stem}.pdf`
   - 会议目录（N > 10 篇）可复用 `scripts/batch_paper_reports.sh` 模式，但要改调 `wiki-paper` 而非 `paper-report`（若批处理脚本未升级，先串行，每篇间不阻塞）
   - Topic 目录（通常 < 20 篇）直接串行调用

## Step 2 — 读取所有 paper wiki 页

`Glob wiki/papers/*.md`，筛选出本 `{dir}` 的页：

- 从 frontmatter `source_pdf` 或 `source_md` 反推所属目录
- 或者简单地按 frontmatter `venue` + `year` 筛（对会议目录准确；topic 目录需补充判断）

读取所有筛出的页，提取：

- `name` + `full_title` + `authors` + 一句话总结
- 主要 tags（用于分类）
- 正文「核心方法」节的核心 insight

## Step 3 — 生成综述页

### 会议目录 → `wiki/conferences/{Conf}-{Year}.md`

`Conf` 用大写（`OSDI`、`SOSP`、`MLSys`、`NSDI`、`ATC`、`FAST`），`Year` 用 4 位。

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

> {一句话：本届会议的整体画像，如「53 篇论文，LLM 系统占比 ~25%，memory/storage 次之」}

## 概览

{3-5 段。主题分布、新出现的研究范式、社区的兴趣迁移、与往年相比的差异。每段 2-3 句。}

## 论文分类

类别动态推断（5-10 类，每类 3-10 篇），**每篇论文只出现在一个类别里**。格式：

### {Category 1}（N 篇）

- [[{Name}-{Conf}{Year}|{论文名或短标题}]] — {一句话要点}
- [[{Name2}-{Conf}{Year}|...]] — ...

### {Category 2}（N 篇）

...

## 研究趋势

{3-5 段。每段必须 wikilink 2-3 篇具体论文作证据。空泛断言无效。

示例段落：

> KV cache 管理仍是 LLM 推理系统的核心议题。[[NanoFlow-OSDI25]] 从单节点吞吐入手，[[FlexiCache-MLSys26]] 则利用 attention head 的时域稳定性，[[...|...]] 进一步 ...}

## 值得关注的方向

{面向小团队（3-5 人、无大规模 GPU 集群）的可行研究方向。

每个方向包括：
- **方向名称和描述**
- **为什么小团队能做**
- **哪些论文指向了这个空白**（wikilink 具体论文）
- **具体的 open problems**}
```

### Topic 目录 → `wiki/themes/{Topic}.md`（如 `AI-Infra.md`、`Finance.md`、`Auto-Research.md`）

但注意 `wiki/themes/` 的语义是「个人观点 + 趋势」，和纯 topic 综述略有差异。建议：

- **对 `ai-infra`、`autoresearch`、`finance`、`time-series` 这种 topic 目录**：生成到 `wiki/themes/{TopicPascalCase}.md`，frontmatter `type: theme`
- **模板**：
```markdown
---
type: theme
topic: {TopicPascalCase}
paper_count: {N}
first_generated: {YYYY-MM-DD}
last_updated: {YYYY-MM-DD}
tags: [topic-overview]
---

# {Topic Display Name}

> {一句话：本 topic 的核心问题和当前 state-of-the-art}

## 论文列表

- [[{Name}-{Conf}{Year}|{短标题}]] — {一句话要点}
- ...

## 主题综述

{跨论文的脉络分析，每段 wikilink 2-3 篇论文。允许表达个人观察和判断，但必须有证据。}

## 值得关注的方向

（结构同会议模板）
```

## Step 4 — 更新全局 index

写完综述页后，更新 `wiki/index.md`：

### 会议

在 `## Conferences` 节下追加一行（按年份倒序、会议名字母序）：

```markdown
- [[{Conf}-{Year}]] — {N} 篇 | {一句话画像}
```

### Topic

在 `## Themes` 节下追加一行：

```markdown
- [[{TopicPascalCase}]] — {N} 篇 | {一句话画像}
```

## Step 5 — 追加 log.md

在 `wiki/log.md` 顶部插入（倒序 = 最新在前）：

```markdown
## [{YYYY-MM-DD}] {Conf}-{Year} 综述生成
- 生成：wiki/conferences/{Conf}-{Year}.md
- 聚合 {N} 篇 paper wiki 页
- 分类 {M} 个
```

## Step 6 — 简短汇报

```
生成：wiki/conferences/{Conf}-{Year}.md
已确保 {N} 篇 paper wiki 页
index.md 已更新
log.md 已记录
```

## Important Notes

- **类别动态推断**：不要套固定 taxonomy，根据本目录实际论文内容决定分类
- **每篇论文只出现一次**：跨类别时归入最核心的那个
- **研究趋势分析段落必须 wikilink 证据**，空泛断言无效
- **值得关注的方向**：聚焦小团队能做的，不要推荐需要大规模资源的方向
- 会议名大写（`OSDI`、`SOSP`），年份 4 位
- Topic 名用 PascalCase（`AI-Infra`、`Auto-Research`、`Time-Series`、`Finance`）
- 所有内部引用用 wikilink `[[{Name}-{Conf}{Year}]]`
- 表格内 wikilink 必须转义 `\|`（见 CLAUDE.md 链接格式章节）
- 无人值守：遇到类别边界模糊、论文归属不清、命名候选多选一等情况自行决定
