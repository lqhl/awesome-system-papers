---
name: probe
description: "深度 landscape characterization：穷尽 wiki 内关联论文，优先利用 paper 页的关键观察/隐含假设/critical analysis，补缺、外部搜索、输出结构化 probe 文档。这是 /proposal 的强制性前置步骤。Triggers on /probe with a topic."
---

# Probe Skill

对给定 topic 做深度 landscape characterization——理解领域的 assumptions、tensions、和空白在哪，输出结构化 probe 文档。**不是 literature review 列表**，而是对领域内已有工作的定位分析 + 未解决问题识别。

## Usage

```
/probe <topic or question> [--ingest-missing]
```

- 默认：外部论文只作为 URL evidence，不修改 raw/wiki layer
- `--ingest-missing`：允许下载高相关外部论文并执行 mineru + wiki-paper；同时允许补齐 wiki 内引用但尚未 ingest 的论文

## 执行步骤

### Step 1 — 穷尽 wiki 内相关信息

从 `wiki/index.md` 出发：
- 找到相关的 **entity / concept / comparison / theme / conference** 页
- 在每个主题/概念页的「引用本概念的论文」或「相关论文」中顺 wikilink 向下读所有关联的 paper wiki 页
- 对每篇读过的 paper，提取：
  - **做了什么**：一句话核心贡献
  - **没做什么**：什么 scope 明确排除或没碰的
  - **关键观察**：论文依赖的 workload / bottleneck / scaling / deployment observation
  - **隐含假设**：what must be true for this approach to work？（例如 FlexiCache 假设 attention head stability 是 model-intrinsic、DiffKV 假设 attention score 反映持久重要性）
  - **可攻击点 / 脆弱点**：从 `Critical Analysis`、`局限与 Future Work` 提取哪些假设可能被 measurement 推翻

优先读 paper 页里的 `关键观察 / 隐含假设`、`Critical Analysis`、`局限与 Future Work`。如果旧 paper 页没有这些节，再从 `核心方法`、`关键结果` 和原始 markdown fallback 提取。

对每个相关 entity/concept/theme/conference 页也做同样的提取——它们代表了「社区共识」，隐含假设更强。

### Step 2 — 补缺

对 probe 过程中发现的：
- wiki 内引用了但缺 paper wiki 页的论文 → 默认列入 coverage gap；传 `--ingest-missing` 时才下载 PDF + 跑 mineru + 用 `/wiki-paper` 生成
- 引用的概念但没有 concept 页且达到 `wiki/.quality.yml` 的 threshold → 仅列为候选，不在 probe 内建页

确保 landscape 覆盖完整后再进入 Step 3。

### Step 3 — 外部搜索

- **WebSearch arxiv**：找最新的相关论文（特别是 2025-2026、在 wiki 覆盖范围外的）
- **WebSearch 博客/行业动态**：找如 LMCache blog、NVIDIA developer blog 等非正式但关键的信息源
- **WebSearch 工业系统**：找 closed-source 但公开讨论过的系统（如 NVIDIA KVBM、InfiniStore）
- 对找到的高相关论文：默认作为外部证据引用；只有用户显式传 `--ingest-missing` 才下载并进入 paper ingest

### Step 4 — 输出结构化 probe 文档

输出到 `wiki/proposals/probes/{Slug}.md`。

**文件命名**：Slug = topic 名称，kebab-case（如 `thinking-model-kv-cache`）。

```markdown
---
type: probe
topic: {简短 topic 描述}
created: YYYY-MM-DD
probed_papers: ["[[Page1]]", "[[Page2]]", ...]
---

# Probe: {Topic}

## Landscape

### 每个相关工作的定位
| 工作 | 做了什么 | 没做什么 | 关键观察 | 隐含假设 | 可攻击点 / 脆弱点 |
|------|----------|----------|----------|----------|--------------------|
| [[X]] | | | | | |
| [[Y]] | | | | | |

{一句话总结这个表格揭示的整体画面}

## Tensions
{这个领域里哪些假设可能互相矛盾？哪些结论在不同 workload 下可能不成立？
每个 tension 用 2-3 句描述 + 列出涉及的论文}

## Fragile Assumptions
{列出最值得被 measurement 攻击的 3-6 个假设。每个假设包括：来自哪些论文、为什么可能不稳、需要什么 workload/trace/metric 才能验证或推翻。}

## Industry Activity
{工业界在做什么但没发论文的？列出已知的 closed-source 系统、博客、tech talk}

## Candidate Blanks
{可能的空白——不是 idea，是「这里似乎没人碰过」的位置。
每个 blank 2-3 句 + 为什么现有工作没覆盖}

## Key Unknowns
{做任何 proposal 之前需要搞清楚的问题——需要什么 measurement 才能回答？
每个 unknown 附一个测量方法建议}
```

### Step 5 — 追加 wiki/proposals/_log.md

```markdown
## [YYYY-MM-DD] Probe: {Topic}
- 生成：`wiki/proposals/probes/{Slug}.md`
- 覆盖 {N} 篇论文，{M} 个 candidate blank，{K} 个 key unknown
```

---

## 关键约束

- **不做 novelty 判断**，不做 idea 生成。probe 是 neutral 的 landscape characterization
- **穷尽 wiki**：至少读完 wiki/index.md 中所有相关 page 的第一层 wikilink 链路
- **必须填「关键观察」「隐含假设」「可攻击点 / 脆弱点」列**：这是整个 probe 最有价值的部分——community wisdom 的经验基础与隐式前提
- **必须填「没做什么」列**：每篇论文的 explicit scope exclusions
- **优先利用新版 paper 页**：已有 paper 页的 `关键观察 / 隐含假设`、`Critical Analysis`、`局限与 Future Work` 是 probe 的主要原料；缺节时才回 markdown/PDF
- **证据分级**：`complete/full-text` 可作强证据；`abstract-only` 只能作线索，关键 claim 必须回源；`needs-review` 不得单独支撑 fragile assumption
- **probe 文档不引用自身到 wiki/index.md**，它是 wiki/proposals/probes/ 下的独立文件
- **probe 的 probed_papers 列表是 wikilink**（指向 wiki paper 页），外部论文用 markdown link 到 arxiv URL
- 补缺时（Step 2）的论文下载 + wiki 生成是 done in passing，不阻塞 probe 主体输出
