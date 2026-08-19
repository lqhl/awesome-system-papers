---
name: probe
description: "深度 landscape characterization：穷尽 wiki 内关联论文，优先利用 paper 页的关键观察/隐含假设/critical analysis，补缺、外部搜索、输出结构化 probe 文档。这是 /proposal 的强制性前置步骤。Triggers on /probe with a topic."
---

# 深度调研 Probe Skill

对给定 topic 做深度 landscape characterization——理解领域的 assumptions、tensions、和空白在哪，输出结构化 probe 文档。**不是 literature review 列表**，而是对领域内已有工作的定位分析 + 未解决问题识别。

## 共享中文写作契约

在生成 probe 正文、表格单元格或 proposal log 前，必须完整阅读并执行 [中文写作与术语解释契约](../_shared/chinese-writing.md)。来源论文页或外部资料里的中英混写不得直接复制到 probe。

## 用法

```
/probe <topic or question> [--ingest-missing]
```

- 默认：外部论文只作为 URL evidence，不修改 raw/wiki layer
- `--ingest-missing`：允许下载高相关外部论文并执行 mineru + wiki-paper；同时允许补齐 wiki 内引用但尚未 ingest 的论文

## 执行步骤

### 步骤 1 — 穷尽 wiki 内相关信息

从 `wiki/index.md` 出发：
- 找到相关的 **entity / concept / comparison / theme / conference** 页
- 在每个主题/概念页的「引用本概念的论文」或「相关论文」中顺 wikilink 向下读所有关联的 paper wiki 页
- 对每篇读过的 paper，提取：
  - **做了什么**：一句话核心贡献
  - **没做什么**：什么 scope 明确排除或没碰的
  - **关键观察**：论文依赖的 workload / bottleneck / scaling / deployment observation
  - **隐含假设**：what must be true for this approach to work？（例如 FlexiCache 假设 attention head stability 是 model-intrinsic、DiffKV 假设 attention score 反映持久重要性）
  - **可攻击点 / 脆弱点**：从 `批判性分析`、`局限与后续工作` 提取哪些假设可能被测量推翻

优先读论文页里的 `关键观察 / 隐含假设`、`批判性分析`、`局限与后续工作`。兼容旧页英文栏目；如果旧论文页没有这些节，再从 `核心方法`、`关键结果` 和原始 Markdown 提取。

对每个相关 entity/concept/theme/conference 页也做同样的提取——它们代表了「社区共识」，隐含假设更强。

### 步骤 2 — 补缺

对 probe 过程中发现的：
- wiki 内引用了但缺 paper wiki 页的论文 → 默认列入 coverage gap；传 `--ingest-missing` 时才下载 PDF + 跑 mineru + 用 `/wiki-paper` 生成
- 引用的概念但没有 concept 页且达到 `wiki/.quality.yml` 的 threshold → 仅列为候选，不在 probe 内建页

确保 landscape 覆盖完整后再进入 Step 3。

### 步骤 3 — 外部搜索

- **WebSearch arxiv**：找最新的相关论文（特别是 2025-2026、在 wiki 覆盖范围外的）
- **WebSearch 博客/行业动态**：找如 LMCache blog、NVIDIA developer blog 等非正式但关键的信息源
- **WebSearch 工业系统**：找 closed-source 但公开讨论过的系统（如 NVIDIA KVBM、InfiniStore）
- 对找到的高相关论文：默认作为外部证据引用；只有用户显式传 `--ingest-missing` 才下载并进入 paper ingest

### 步骤 4 — 输出结构化 probe 文档

输出到 `wiki/proposals/probes/{Slug}.md`。

写作前先建立页内术语表，对跨系统、研究方法和领域的重复概念选定统一中文表达。Probe 的研究版图表格属于正文；「做了什么」、「隐含假设」和「可攻击点」等单元格不豁免术语解释。

**文件命名**：Slug = topic 名称，kebab-case（如 `thinking-model-kv-cache`）。

```markdown
---
type: probe
topic: {简短 topic 描述}
created: YYYY-MM-DD
probed_papers: ["[[Page1]]", "[[Page2]]", ...]
---

# 深度调研（Probe）：{Topic}

## 阅读提示

{若全文有超过 5 种反复专业术语，用简短中文解释核心术语、缩写和本 probe 采用的统一表达。}

## 研究版图

### 每个相关工作的定位
| 工作 | 做了什么 | 没做什么 | 关键观察 | 隐含假设 | 可攻击点 / 脆弱点 |
|------|----------|----------|----------|----------|--------------------|
| [[X]] | | | | | |
| [[Y]] | | | | | |

{一句话总结这个表格揭示的整体画面}

## 矛盾与张力
{这个领域里哪些假设可能互相矛盾？哪些结论在不同工作负载下可能不成立？
每个张力用 2-3 句描述并列出涉及的论文。}

## 脆弱假设
{列出最值得用测量攻击的 3-6 个假设。每个假设包括：来自哪些论文、为什么可能不稳、需要什么工作负载、轨迹和指标才能验证或推翻。}

## 产业动态
{工业界在做什么但没发论文的？列出已知的闭源系统、博客和技术演讲。}

## 候选空白
{可能的空白——不是研究点子，是「这里似乎没人碰过」的位置。
每个空白用 2-3 句说明，并解释现有工作为什么没有覆盖。}

## 关键未知
{做任何提案之前需要搞清楚的问题——需要什么测量才能回答？
每个未知问题附一个测量方法建议。}
```

### 步骤 4a — 成稿语义审计

在追加 log 前，按共享契约审查全文保留的拉丁字母词，重点检查表格单元格、研究版图总结、矛盾、脆弱假设和测量建议。消除英文名词串和未解释缩写，再运行定向 `wiki-lint --language-only`；`language_warnings=0` 不能替代语义审计。

### 步骤 5 — 追加 wiki/proposals/_log.md

```markdown
## [YYYY-MM-DD] Probe: {Topic}
- 生成：`wiki/proposals/probes/{Slug}.md`
- 覆盖 {N} 篇论文，{M} 个候选空白，{K} 个关键未知问题
```

---

## 关键约束

- **不做新颖性判断**，不生成研究点子。probe 是中立的研究版图分析
- **穷尽 wiki**：至少读完 wiki/index.md 中所有相关 page 的第一层 wikilink 链路
- **必须填「关键观察」「隐含假设」「可攻击点 / 脆弱点」列**：这是整个 probe 最有价值的部分——社区共识的经验基础与隐式前提
- **必须填「没做什么」列**：记录每篇论文明确排除的范围
- **优先利用新版论文页**：已有论文页的 `关键观察 / 隐含假设`、`批判性分析`、`局限与后续工作` 是 probe 的主要原料；缺节时才回 Markdown/PDF
- Probe 的中文叙述、术语解释和可读性必须通过共享写作契约；论文、系统、模型和指标原名按契约保留并首次解释。
- **证据分级**：`complete/full-text` 可作强证据；`abstract-only` 只能作线索，关键论断必须回源；`needs-review` 不得单独支撑脆弱假设
- **probe 文档不引用自身到 wiki/index.md**，它是 wiki/proposals/probes/ 下的独立文件
- **probe 的 probed_papers 列表是 wikilink**（指向 wiki paper 页），外部论文用 markdown link 到 arxiv URL
- 补缺时（Step 2）顺带完成论文下载与 wiki 生成，不阻塞 probe 主体输出
