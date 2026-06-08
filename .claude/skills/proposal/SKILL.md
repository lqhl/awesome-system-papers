---
name: proposal
description: "基于 probe 文档写迭代式的 research proposal。强制先有 probe 再做 proposal。包含 taste-rubric-driven 的自我 challenge 和 venue gradient。Triggers on /proposal <probe-slug>."
---

# Proposal Skill

把 probe 的 landscape understanding 转化为一个有 taste 的 research proposal。

**前置条件**：对应的 probe 文档必须存在于 `wiki/proposals/probes/{Slug}.md`。如果不存在或 probe 日期超过 30 天，提示用户先跑 `/probe <topic>`。

## Usage

```
/proposal <probe-slug> [--hypotheses H1,H2,H3] [--hypotheses-only]
```

- `--hypotheses`：直接用用户提供的假设，跳过自动假设生成
- `--hypotheses-only`：只生成假设部分（§1.4），用于快速迭代假设

## 执行步骤

### Step 1 — 加载 probe + taste rubric

- `Read wiki/proposals/probes/{Slug}.md`
- 从 AGENTS.md 加载 **Taste Rubric**（在 Proposals 章节下）

### Step 2 — 形成可证伪假设

若用户未传 `--hypotheses`：

- 从 probe 的 **Tensions** 和 **Candidate Blanks** 中提炼 2-4 个可证伪假设
- 每个假设必须：
  1. **攻击对象明确**：引用具体某篇论文的隐含前提（用 probe 表格的「隐含假设」列）
  2. **有可证伪预测**：what would we observe if the hypothesis is true？
  3. **有 metric**：用哪个指标验证
  4. **有预期数值**：给出一个具体的预期值（如「recall < 40% vs > 80%」）
  5. **说明了如果被验证意味着什么**：implications

### Step 3 — 写迭代 proposal

**V1 写作**：按模板输出 proposal 初稿。核心结构：

```markdown
---
type: proposal
name: {Slug}
title: "{一句话 idea 标题}"
status: draft
created: YYYY-MM-DD
last_updated: YYYY-MM-DD
target_venue: "{venue gradient}"
tags: [...]
related_papers: [...]
related_concepts: [...]
related_systems: [...]
novelty: high
feasibility: medium
effort: medium
---

# {Title}

> 一句话 idea

## 1. 为什么这是个好问题

### 1.1 问题定义
### 1.2 社区盲区
### 1.3 从 measurement 到 contribution：可证伪假设

## 2. 相关工作

### 2.1 基础设施层（站在其肩膀上）
### 2.2 策略层（共享问题但方向不同）
### 2.3 关键 tension

## 3. 核心研究问题

### RQ1: Measurement（脊梁）
### RQ2: Design
### RQ3: Implementation concern
### RQ4: Correctness concern（如适用）

## 4. 可行性

### 4.1 工程范围 + 软件栈
### 4.2 时间线（含 Go/No-Go gate）

## 5. 投稿策略

### 5.1 Venue gradient
### 5.2 为什么这个 venue 需要这篇 paper
### 5.3 论文 story arc

## 6. Pivot Plan

{如果核心假设被推翻怎么办？三条路径：MLSys 降维 / short paper / 放弃并记录教训}

*本提案基于 `wiki/proposals/probes/{Slug}.md` 的 landscape characterization + AGENTS.md Taste Rubric 的自我评估。*

```

**V1 self-challenge**：用 Taste Rubric 的 5 个维度逐条评估 V1：
- Workload 真实性
- Counterintuitive
- 10x vs 2x
- Model-proof
- Abstraction

标注每个维度是否通过。≥2 个维度不通过 → 重写 V2。≤1 个维度不通过 → 微调 V1 后输出。

**不能只在心里评估**：在 proposal 末尾显式输出评估结果和重写判断。

**V2（如需要）**：针对不通过的维度重写 proposal。保留 V1 的 section structure，替换薄弱部分。

### Step 4 — 输出 + 记录

- 写 `wiki/proposals/{Slug}.md`（PascalCase slug）
- 在 `wiki/proposals/_log.md` 追加一条：

```markdown
## [YYYY-MM-DD] {Slug}
- 基于 probe: `wiki/proposals/probes/{ProbeSlug}.md`
- {一句话说明这个 proposal 的核心赌注}
- Taste 评估：{通过的维度} / 5
```

## 命名

`wiki/proposals/{Slug}.md`，PascalCase。从 probe slug 自动转换（kebab-case → PascalCase）。

冲突时加 `-{YYYYMM}` 后缀。

## 关键约束

- **probe 是强制前置**：如果用户明确拒绝 probe，跳过但仍警告「未经 probe 的 proposal 可能忽视关键先行工作」
- **必须输出可证伪假设**：这是 proposal 的脊梁——不能只有「我们做了更好的 X」
- **必须输出 pivot plan**：如果核心假设被测量推翻怎么办
- **必须输出 venue gradient**：不同测量结果对应不同 venue，不假装只有一个目标
- **必须做 taste self-challenge**：显式标注每个维度的通过/失败 + 重写判断
- **proposal 引用 wiki 用 wikilink**，引用外部论文用 standard markdown link 到 arxiv URL
- **proposal 不写 `wiki/log.md`**，只写 `wiki/proposals/_log.md`
