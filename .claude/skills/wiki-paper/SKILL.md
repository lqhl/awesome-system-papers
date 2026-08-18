---
name: wiki-paper
description: "Use this skill when the user wants to read a single paper and generate a detailed, critical wiki page for it. Triggers on /wiki-paper with a path, '为这篇论文建 wiki 页', or '生成 paper wiki'. Input can be a markdown (markdowns/*) or a PDF (papers/*)."
---

# 单篇论文 Wiki Skill

Generate a detailed but bounded, wikilink-rich research note in `wiki/papers/` for a single research paper. 命名用论文自己提的系统名或方法名，而不是 PDF 文件 stem。

目标不是复述全文，而是让半年后的自己快速恢复这篇论文的 **问题、关键观察、隐含假设、方法逻辑、实验边界、缺陷和可继续研究的位置**。系统领域论文尤其要抽取最关键的 observation / assumption，因为系统工作的贡献常常来自对 workload、瓶颈、硬件趋势或部署约束的判断。

**执行模式：无人值守 (unattended)。** 本 skill 常在批量或 loop 中运行，不要中途询问用户做选择。遇到问题（markdown 不存在、命名冲突、系统名难确定等）直接 fallback 到合理默认并继续推进，在最终输出里简短说明取舍。

## 用法

```
/wiki-paper <input-path> [--force] [--no-update] [--output <path>]
```

- `input-path`：markdown 或 PDF 路径
  - 首选：`markdowns/{dir}/{stem}/{stem}.md`
  - 退化：`papers/{dir}/{stem}.pdf`（若 markdown 不存在，先触发 mineru）
- `--force`：即使目标 wiki 页已存在也重写
- `--no-update`：只写 paper 页，不触发 `/wiki-update`，不改 entity/concept/index/log。用于大规模 rebuild worker，避免并发冲突
- `--output <path>`：强制写到指定 `wiki/papers/{filename}.md`。用于 rebuild 时保留旧文件名；若同时需要重命名，只能由主调度 agent 决定

## 执行前检查

1. **路径校验**：
   - 若路径在 `inbox/` 或仓库外 → 拒绝并提示「先把论文分类到 `papers/{conf-or-topic}/` 再跑」
   - 若传入 PDF 但对应 markdown 不存在 → 执行 `uv run scripts/run_mineru.py papers/{dir} markdowns/{dir} -j 2 -m txt`（idempotent），完成后继续
2. **幂等**：若 wiki 页已存在且未传 `--force` → 跳过并输出 `wiki 页已存在：<path>`
3. **rebuild worker 模式**：若传 `--output`，跳过 Step 2 的最终路径选择，只用 Step 2 决定 frontmatter `name` 和命名依据；实际写入路径必须等于 `--output`

## 步骤 1 — 阅读 Markdown

按 `paper-report` 风格全量阅读 markdown：

- `Read markdowns/{dir}/{stem}/{stem}.md`（默认 2000 行，必要时 `offset` 续读）
- 图片按角色读，不按文件顺序批量读取：架构图 1–2 张、主结果图/表 2–4 张、关键 ablation 1–2 张；只有正文解析不清时再读其他图片
- 碰到公式乱码 / 表格破损 / 希腊字符错位 / 可疑数字 → fallback 到 PDF 窄窗口（`Read papers/{dir}/{stem}.pdf pages=X-Y`）
- Markdown > 5000 行：跳过 References / Appendix，在输出里注明

阅读时同步抽取以下信息，不要等写作时凭印象补：

- **核心 claim**：作者到底声称解决了什么，claim 的边界是什么
- **关键观察**：measurement / workload / bottleneck / scaling behavior / deployment pain point 中哪一个发现支撑了论文
- **隐含假设**：这个方法成立需要哪些 workload、硬件、模型、规模、SLO、部署方式或工程成本前提
- **方法映射**：每个关键设计分别回应哪个 observation 或 assumption
- **实验边界**：benchmark、baseline、metric、scale、ablation 是否足以支撑 claim
- **缺陷与 future work**：论文承认的 limitation，加上读者基于证据推断出的 fragility

### 系统论文额外检查

若论文属于 systems / networking / storage / ML systems / infra，必须显式识别：

- workload assumption：请求分布、数据分布、模型结构、tenant 行为是否会变
- resource bottleneck assumption：CPU/GPU/内存/网络/存储/调度中哪个瓶颈被默认成主导瓶颈
- hardware/deployment assumption：硬件代际、拓扑、云环境、单机/集群设定是否限制结论
- scaling assumption：论文在小规模上看到的规律能否外推到大规模或 production trace
- correctness/SLO assumption：优化是否影响一致性、隔离、尾延迟、恢复、可观测性或运维复杂度

## 步骤 2 — 决定文件名

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

## 步骤 3 — 生成论文 wiki 页

写入 `wiki/papers/{Name}-{Conf}{Year}.md`，或写入 `--output` 指定路径。所有正文用 **中文**，但系统名、模型名、benchmark 名、API、指标名、代码标识保留英文。

### 中文写作规范

- 普通概念首次出现写成「中文解释（English）」，后续优先使用中文。例如：验证器（verifier）、脚手架（scaffold）、工作负载（workload）、基线（baseline）、消融实验（ablation）。
- 不要写成「中文连接词 + 连续英文关键词」；每段必须用中文讲清楚因果关系：为什么观察成立、设计怎样回应、证据覆盖到哪里。
- 页面 H1 使用准确、克制的中文译名，下一行写 `> **原题**：{full_title}`；frontmatter 的 `full_title` 始终保留论文英文原题。
- 定位优先写 `图 3`、`表 2`、`§5.4`；专名、变量名和代码内文本不翻译。
- 文件名、wikilink target、frontmatter key、枚举值和英文 tags 不翻译。

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
review_status: complete
evidence_level: full-text
last_reviewed: YYYY-MM-DD
---
```

字段说明：
- `name`：文件名里的 Name 部分（如 `vLLM`、`NanoFlow`、`PagedAttention`）。注意这是**命名用的短名**，不是完整标题。
- `full_title`：论文完整标题（与原论文 TeX 标题一致，去脚标和星号）
- `authors`：列表，每个元素仅姓名（去脚标、邮箱、affiliation）；> 10 人时取前 5 + `et al.`
- `venue`：会议简写
- `year`：4 位数字
- `tags`：先生成 3–6 个描述性英文小写 tag，多词用 `-` 连接（如 `llm-inference`、`kv-cache`）
- `area/`、`domain/`、`lens/`、`concern/` 是 theme membership 的保留前缀；`wiki-paper` 不凭单篇语义自行生成，只有论文进入某个 theme 的「核心论文」后才由 `wiki-lint --fix` 追加
- `source_pdf`：`"[[{pdf-stem}.pdf]]"`（**wikilink 必须用双引号 quote**，否则 YAML 解析为嵌套数组；带 .pdf 后缀）
- `source_md`：`"[[{md-stem}]]"`（同上，无后缀；`md-stem` 是 `markdowns/{dir}/{stem}/{stem}.md` 里的 stem）
- `review_status`：`complete | needs-review | abstract-only | invalid`。本 skill 正常完成全文阅读后只能写 `complete`；存在未核实信息时降级，不得伪装完成
- `evidence_level`：`full-text | abstract | metadata-only`。`complete` 必须对应 `full-text`
- `empirical_evidence: none`：仅用于原文本身明确不含数值实验的描述性工作；不得用于绕过存在但尚未核对的实验。使用时仍必须给出 2–5 条论断—证据记录，审计覆盖范围、证据缺口和代码/方法边界
- `last_reviewed`：本次实际核验日期

**Frontmatter wikilink 规则**：所有 frontmatter 字段里的 wikilink 必须用双引号包裹成字符串，例如 `parent: "[[KV-Cache]]"`、`source_pdf: "[[xxx.pdf]]"`。多个 wikilink 用 list of quoted strings：`subjects: ["[[vLLM]]", "[[SGLang]]"]`。否则 Obsidian properties 面板会显示成字面字符串而非可点击链接。

### 正文结构

```markdown
# {中文译名}（{Venue} {Year}）

> **原题**：{full_title}

> **一句话总结**：{能让半年后的自己 30 秒内 reload 论文要点的一句话。必须包含关键观察/假设 + 方法核心 + 关键结果。}

## 问题与动机

{2-4 段讲清楚论文要解决什么问题、为什么现有方案不够、问题在什么部署或 workload 下重要。区分作者 claim 和你的概括。}

## 关键观察 / 隐含假设

- **观察 1**：{论文真正依赖的 workload / system behavior / bottleneck / scaling observation。写出证据来自哪组 measurement 或实验。}
  - **依赖假设**：{这个观察成立需要什么前提。}
  - **可能失效场景**：{workload、硬件、模型、规模或部署方式改变后哪里可能不成立。}
- **假设 1**：{作者没有明说但方法必须依赖的前提。}
  - **证据强度**：{强 / 中 / 弱；一句话说明为什么。}

系统论文至少写 2 条 observation/assumption；非系统论文也要写 1-3 条。不要把普通方法步骤伪装成观察。

## 核心方法

{3-6 段介绍核心思路和关键设计决策。每个重要设计都要说明它回应了上面哪条观察或假设。**首次提到已有 wiki 概念或系统时必须加 wikilink**，如 [[KV-Cache]]、[[PagedAttention]]、[[vLLM]]。无需重复全部实现细节，深度内容回 [[source_md]] 或 [[source_pdf]] 读。}

## 设计取舍

- **取舍 1**：{为了获得什么收益，牺牲了什么：复杂度、通用性、资源、隔离性、正确性、可维护性等。}
- **边界条件**：{该设计在哪些场景下优雅，在哪些场景下会变脆。}

## 实验与结果

- {具体 metric + 数值 + baseline + workload/scale，例如「ShareGPT、A100、OPT-13B 下吞吐比 Orca 高 2.2×（Fig. 6）」}
- {2-6 条 bullet，覆盖主结果、关键 ablation、成本/开销、tail latency 或 scalability（如适用）；关键结果附 §/Fig/Table 定位}

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| {一句话总结或关键观察中的核心论断} | {§/图/表} | {硬件、模型、工作负载、规模} | {强/中/弱} |

只保留 2–5 条决定论文结论是否成立的证据，不为普通背景事实逐句建表。

## 批判性分析

### 论证链条

{作者从 observation → design → result 的逻辑是否闭合？有没有把局部结果外推成整体结论？有没有没有被实验覆盖的关键跳步？}

### 假设压力测试

{核心假设在哪些 workload、硬件、规模、模型、部署方式下可能失效？区分“论文已证明”与“你基于证据推断”。}

### 实验可信度

{benchmark 是否代表真实 workload？baseline 是否强且公平？ablation 是否支持设计分解？metric 是否覆盖吞吐、延迟、成本、正确性等关键面？}

### 系统性缺陷

{实现复杂度、尾延迟、资源隔离、故障恢复、可观测性、部署成本、兼容性、运维风险等。没有证据时明确说“论文未讨论”。}

## 局限与后续工作

- **局限 1**：{论文承认或可从实验边界推出的 limitation。}
- **后续工作 1**：{可机器/客观验证的后续问题，最好指向测量或设计空间，而不是泛泛“进一步优化”。}

## 相关

- **相关概念**：[[Concept1]]、[[Concept2]]
- **同类系统**：[[System1]]、[[System2]]
- **同会议**：[[{Conf}-{Year}]]
- **对比**（如有）：[[X-vs-Y]]
```

### 写作原则

1. **详细但有边界**：目标是 5-10 分钟能读完的 research note，不是 full paper report。实现、公式推导、完整实验矩阵仍回 `[[source_md]]`。
2. **critical thinking 必须外显**：不要只复述作者 claim；必须写清楚 observation 是否支撑 design，实验是否支撑 claim，假设在哪里可能失效。
3. **不重复 PDF 内容**：不要 verbatim 抄论文段落；提炼成 claim。
4. **区分事实与判断**：作者实验直接证明的写成事实；你的质疑写成“可能”“论文未覆盖”“需要进一步测量”。
5. **wikilink 密度**：「核心方法」「关键观察 / 隐含假设」「批判性分析」「相关」尽量多 wikilink，让这篇页自然嵌入 wiki 图谱。
6. **允许留白但不逃避分析**：论文没有讨论的系统风险要写“论文未讨论”，而不是跳过。
7. **Wikilink 到未存在页**：如果提到的概念还没有 wiki 页（如 `[[KV-Cache]]` 目前不存在），照样写 wikilink，Obsidian 会显示为橘色链接，未来 `wiki-lint` 会识别为「高频缺页 watchlist」。

### 完成门槛

写文件前运行并满足 `.claude/skills/wiki-lint/lint.py` 的 paper quality 规则：

- `authors` 不得包含 `authors`、`unknown`、`anonymous`、`tbd` 等占位值
- 禁止「需读全文」「具体倍数见原文」「细节在全文」「待核对」「待补」等未完成措辞
- 实验结论必须有 metric、数值、baseline、evaluation boundary 四项中的至少三项
- `complete` 页面必须有 `论断—证据表`，且正文至少出现一个 §/图/表定位
- 无法满足时必须写 `needs-review` 或 `abstract-only`，并在最终汇报说明缺口；不得用泛化文字填满模板

共享枚举、占位模式、阈值和 watchlist 统一读取 `wiki/.quality.yml`，不得在本 skill 复制另一套值。

## 步骤 4 — 自动触发 wiki-update

写完 wiki paper 页后，除非传了 `--no-update`，立即调用 `/wiki-update wiki/papers/{Name}-{Conf}{Year}.md`：

- 扫描页里提到的所有 entity/concept 名（对比 `wiki/entities/` 和 `wiki/concepts/` 已存在的页）
- 若 paper 页里提到但没 wikilink → 补单点 wikilink
- 更新被引到的 entity/concept 页的「相关论文」或「演进时间线」节（追加一行）
- 在 `wiki/log.md` 追加条目

实现：本 skill 末尾发出 Skill 调用 `/wiki-update <paper-wiki-path>`。若不自动触发（如 skill 调用受限），在输出里显式写明「下一步请运行 /wiki-update <path>」。

`--no-update` 模式下必须明确汇报「已跳过 wiki-update」。不要改 `wiki/log.md`、`wiki/index.md`、`wiki/entities/`、`wiki/concepts/`。

## 步骤 5 — 结束输出

简短汇报：

```
生成：wiki/papers/{Name}-{Conf}{Year}.md
命名依据：{系统名 | 方法名 | 作者-主题}
wiki-update：{已触发 | --no-update 已跳过}
```

## 重要说明

- 整篇中文，技术术语保留英文
- 标题和作者按 `paper-report` 风格清洗（去脚标、邮箱、affiliation；> 10 人取前 5 + et al.）
- 一句话总结必须有关键 observation/assumption + 具体数字或 claim，不能是「提出了一种方法」这种空话
- 系统论文必须包含 `关键观察 / 隐含假设`、`设计取舍`、`批判性分析`、`局限与后续工作`
- 深度细节（完整实现、完整实验表、公式推导）不要搬进 wiki；那些是 `markdowns/` 和 PDF 的职责
- 命名冲突 fallback：加 `-{FirstAuthorLastname}` 后缀
- 无人值守：任何不确定的情况（系统名候选多选一、命名冲突、图片预算分配）自行决定并继续，不要询问用户
- 幂等：默认跳过已存在页；`--force` 才重写
- 大规模 rebuild 时必须使用 `--no-update --output <path>`，由主调度 agent 统一重建 entity/concept/index/log
