---
name: wiki-paper
description: "Use this skill when the user wants to read a single paper and generate a concise wiki page for it. Triggers on /wiki-paper <path>, '为这篇论文建 wiki 页', '生成 paper wiki'. Input can be a markdown (markdowns/*) or a PDF (papers/*)."
---

# Wiki Paper Skill

Generate a concise, wikilink-rich markdown page in `wiki/papers/` for a single research paper. 命名用论文自己提的系统名或方法名，而不是 PDF 文件 stem。

**执行模式：无人值守 (unattended)。** 本 skill 常在批量或 loop 中运行，不要中途询问用户做选择。遇到问题（markdown 不存在、命名冲突、系统名难确定等）直接 fallback 到合理默认并继续推进，在最终输出里简短说明取舍。

## Usage

```
/wiki-paper <input-path> [--force]
```

- `input-path`：markdown 或 PDF 路径
  - 首选：`markdowns/{dir}/{stem}/{stem}.md`
  - 退化：`papers/{dir}/{stem}.pdf`（若 markdown 不存在，先触发 mineru）
- `--force`：即使目标 wiki 页已存在也重写

## Pre-flight Checks

1. **路径校验**：
   - 若路径在 `inbox/` 或仓库外 → 拒绝并提示「先把论文分类到 `papers/{conf-or-topic}/` 再跑」
   - 若传入 PDF 但对应 markdown 不存在 → 执行 `uv run scripts/run_mineru.py papers/{dir} markdowns/{dir} -j 2 -m txt`（idempotent），完成后继续
2. **幂等**：若 wiki 页已存在且未传 `--force` → 跳过并输出 `wiki 页已存在：<path>`

## Step 1 — Read the markdown

按 `paper-report` 风格全量阅读 markdown：

- `Read markdowns/{dir}/{stem}/{stem}.md`（默认 2000 行，必要时 `offset` 续读）
- 图片按预算读：总数 ≤ 20 全部读；> 20 取架构图 / 主结果表 / 关键 ablation 前 ~20 张
- 碰到公式乱码 / 表格破损 / 希腊字符错位 / 可疑数字 → fallback 到 PDF 窄窗口（`Read papers/{dir}/{stem}.pdf pages=X-Y`）
- Markdown > 5000 行：跳过 References / Appendix，在输出里注明

## Step 2 — 决定文件名

按以下 fallback 顺序决定 wiki paper 页的文件名 `{Name}-{Conf}{Year}.md`：

### Fallback 规则

1. **优先：系统名/产品名**。论文里明确自命名的系统（通常在标题、Abstract 开头或 Introduction 第一句出现）：
   - `vLLM-SOSP23.md`、`NanoFlow-OSDI25.md`、`SGLang-OSDI25.md`、`FlexiCache-MLSys26.md`
   - 判断线索：论文出现 "We present X"、"We propose X, a system for..."、"X is a ..." 这类句式
2. **次选：方法名/技术名**。纯算法/机制论文，没有产品名但有标志性方法名：
   - `PagedAttention-SOSP23.md`、`FlashAttention-NeurIPS22.md`、`SpeculativeDecoding-ICML23.md`
3. **末选：作者姓-主题**。既无系统名又无方法名的纯研究：
   - `Kwon-LLMServing-SOSP23.md`、`Smith-CrashConsistency-FAST25.md`
   - 格式：`{FirstAuthorLast}-{SubjectCamelCase}-{Conf}{Year}.md`

### 会议后缀格式

`{Conf}{YY}`：`OSDI25`、`SOSP25`、`NSDI25`、`ATC25`、`FAST25`、`MLSys26`、`arXiv25` 等。两位年份。

### 命名冲突处理

`Glob wiki/papers/{Name}-{Conf}{Year}.md`：

- 不冲突 → 直接用
- 冲突 → 加 `-{FirstAuthorLastname}` 后缀，如 `vLLM-SOSP23-Kwon.md`
- 再冲突（极少） → 加 `-{SecondAuthorLastname}` 或 `-v2`

### 特殊说明

- **大小写**：PascalCase 保持原名大小写（`vLLM` 保留小写 v，`SGLang` 保留大 S 小 L 大 G）；方法名用 PascalCase（`PagedAttention` 而非 `Paged-Attention`）
- **Dash 使用**：Name 和 ConfYear 之间用 `-` 分隔；Name 内部若多词用 PascalCase 合并（`FlashAttention`）
- **不要**在文件名里用空格、特殊字符、中文

## Step 3 — 生成 wiki paper 页

Write to `wiki/papers/{Name}-{Conf}{Year}.md`。所有正文用 **中文**，技术术语保留英文。

### Frontmatter（必填）

```yaml
---
type: paper
name: {文件名里的 Name 部分}
full_title: {论文完整标题}
authors: [Author1, Author2, ...]
venue: {OSDI / SOSP / MLSys / NSDI / ATC / FAST / arXiv / ...}
year: {YYYY}
tags: [tag1, tag2, tag3]
source_pdf: "[[{pdf-stem}.pdf]]"
source_md: "[[{md-stem}]]"
---
```

字段说明：
- `name`：文件名里的 Name 部分（如 `vLLM`、`NanoFlow`、`PagedAttention`）。注意这是**命名用的短名**，不是完整标题。
- `full_title`：论文完整标题（与原论文 TeX 标题一致，去脚标和星号）
- `authors`：列表，每个元素仅姓名（去脚标、邮箱、affiliation）；> 10 人时取前 5 + `et al.`
- `venue`：会议简写
- `year`：4 位数字
- `tags`：3–6 个英文小写 tag，多词用 `-` 连接（如 `llm-inference`、`kv-cache`）
- `source_pdf`：`"[[{pdf-stem}.pdf]]"`（**wikilink 必须用双引号 quote**，否则 YAML 解析为嵌套数组；带 .pdf 后缀）
- `source_md`：`"[[{md-stem}]]"`（同上，无后缀；`md-stem` 是 `markdowns/{dir}/{stem}/{stem}.md` 里的 stem）

**Frontmatter wikilink 规则**：所有 frontmatter 字段里的 wikilink 必须用双引号包裹成字符串，例如 `parent: "[[KV-Cache]]"`、`source_pdf: "[[xxx.pdf]]"`。多个 wikilink 用 list of quoted strings：`subjects: ["[[vLLM]]", "[[SGLang]]"]`。否则 Obsidian properties 面板会显示成字面字符串而非可点击链接。

### 正文结构

```markdown
# {full_title} ({Venue} {Year})

> **一句话总结**：{能让半年后的自己 30 秒内 reload 论文要点的一句话。必须包含方法核心 + 关键结果。}

## 问题

{用自由长度（建议 1-3 段）讲清楚论文要解决什么问题、为什么现有方案不够。无需严格限制字数。}

## 核心方法

{用自由长度介绍论文的核心思路、关键设计决策。**首次提到已有 wiki 概念或系统时必须加 wikilink**，如 [[KV-Cache]]、[[PagedAttention]]、[[vLLM]]。无需重复描述论文全部细节，深度内容回 [[source_md]] 或 [[source_pdf]] 读。}

## 关键结果

- {具体数字 + 比较对象，如「吞吐 2.2-4.0× 比 FasterTransformer」}
- {2-5 条 bullet}

## 相关

- **相关概念**：[[Concept1]]、[[Concept2]]
- **同类系统**：[[System1]]、[[System2]]
- **同会议**：[[{Conf}-{Year}]]
- **对比**（如有）：[[X-vs-Y]]
```

### 写作原则

1. **简洁优先**：这不是 8 节深度报告；深度细节永远可以回 `[[source_md]]`。目标是「一年后回看 30 秒 reload」。
2. **wikilink 密度**：「核心方法」「相关」两节尽量多 wikilink，让这篇页自然地嵌入 wiki 图谱。
3. **不重复 PDF 内容**：不要 verbatim 抄论文段落；提炼成 claim。
4. **允许留白**：如果某节信息太少（如没有突出的 key results），写一句概述即可，不要凑字数。
5. **Wikilink 到未存在页**：如果提到的概念还没有 wiki 页（如 `[[KV-Cache]]` 目前不存在），照样写 wikilink，Obsidian 会显示为橘色链接，未来 `wiki-lint` 会识别为「高频缺页 watchlist」。

## Step 4 — 自动触发 wiki-update

写完 wiki paper 页后，立即调用 `/wiki-update wiki/papers/{Name}-{Conf}{Year}.md`：

- 扫描页里提到的所有 entity/concept 名（对比 `wiki/entities/` 和 `wiki/concepts/` 已存在的页）
- 若 paper 页里提到但没 wikilink → 补单点 wikilink
- 更新被引到的 entity/concept 页的「相关论文」或「演进时间线」节（追加一行）
- 在 `wiki/log.md` 追加条目

实现：本 skill 末尾发出 Skill 调用 `/wiki-update <paper-wiki-path>`。若不自动触发（如 skill 调用受限），在输出里显式写明「下一步请运行 /wiki-update <path>」。

## Step 5 — 结束输出

简短汇报：

```
生成：wiki/papers/{Name}-{Conf}{Year}.md
命名依据：{系统名 | 方法名 | 作者-主题}
已触发：/wiki-update
```

## Important Notes

- 整篇中文，技术术语保留英文
- 标题和作者按 `paper-report` 风格清洗（去脚标、邮箱、affiliation；> 10 人取前 5 + et al.）
- 一句话总结必须有具体数字或 claim，不能是「提出了一种方法」这种空话
- 深度细节（实现、完整实验、公式推导）不要搬进 wiki；那些是 `markdowns/` 和 PDF 的职责
- 命名冲突 fallback：加 `-{FirstAuthorLastname}` 后缀
- 无人值守：任何不确定的情况（系统名候选多选一、命名冲突、图片预算分配）自行决定并继续，不要询问用户
- 幂等：默认跳过已存在页；`--force` 才重写
