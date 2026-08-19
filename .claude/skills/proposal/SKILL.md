---
name: proposal
description: "基于 probe 文档写迭代式的 research proposal，优先从 fragile assumptions / tensions / candidate blanks 中形成可证伪假设。强制先有 probe 再做 proposal。包含 taste-rubric-driven 的自我 challenge 和 venue gradient。Triggers on /proposal {probe-slug}."
---

# 研究提案 Proposal Skill

把 probe 的 landscape understanding 转化为一个有 taste 的 research proposal。

## 共享中文写作契约

在生成 proposal 正文、假设、品味评估或 proposal log 前，必须完整阅读并执行 [中文写作与术语解释契约](../_shared/chinese-writing.md)。只能继承 probe 的证据，不能继承其中英混写方式。

**前置条件**：对应的 probe 文档必须存在于 `wiki/proposals/probes/{Slug}.md`。如果不存在或 probe 日期超过 30 天，提示用户先跑 `/probe <topic>`。

## 用法

```
/proposal <probe-slug> [--hypotheses H1,H2,H3] [--hypotheses-only]
```

- `--hypotheses`：直接用用户提供的假设，跳过自动假设生成
- `--hypotheses-only`：只生成假设部分（§1.4），用于快速迭代假设

## 执行步骤

### 步骤 1 — 加载 probe 与品味量表

- `Read wiki/proposals/probes/{Slug}.md`
- 从 AGENTS.md 加载 **Taste Rubric**（在 Proposals 章节下）
- 若 probe 含 `脆弱假设` 或研究版图表里的 `可攻击点 / 脆弱点`，把它们作为假设生成的首要输入；兼容旧英文栏目
- 从 probe 提取重复术语并重建 proposal 自己的页内术语表；不得直接复制英文名词串或未解释缩写

### 步骤 2 — 形成可证伪假设

若用户未传 `--hypotheses`：

- 从 probe 的 **脆弱假设**、**矛盾与张力** 和 **候选空白** 中提炼 2-4 个可证伪假设
- 每个假设必须：
  1. **攻击对象明确**：引用具体某篇论文的关键观察、隐含前提或可攻击点（用 probe 表格的「关键观察」「隐含假设」「可攻击点 / 脆弱点」列）
  2. **有可证伪预测**：what would we observe if the hypothesis is true？
  3. **有 metric**：用哪个指标验证
  4. **有预期数值**：给出一个具体的预期值（如「recall < 40% vs > 80%」）
  5. **说明了如果被验证意味着什么**：implications
  6. **不是单纯优化假设**：必须能改变或挑战一个 community assumption；否则最多算 engineering task，不够 proposal 主线

### 步骤 3 — 迭代撰写 proposal

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

> 一句话核心想法

## 阅读提示

{若全文有超过 5 种反复专业术语，简要解释核心概念、缩写和统一表达。}

## 1. 为什么这是个好问题

### 1.1 问题定义
### 1.2 社区盲区
### 1.3 被挑战的关键观察 / 隐含假设
### 1.4 从测量到贡献：可证伪假设

## 2. 相关工作

### 2.1 基础设施层（站在其肩膀上）
### 2.2 策略层（共享问题但方向不同）
### 2.3 关键张力
### 2.4 现有证据的脆弱点

## 3. 核心研究问题

### 研究问题 1：测量（脊梁）
### 研究问题 2：设计
### 研究问题 3：实现约束
### 研究问题 4：正确性约束（如适用）

## 4. 可行性

### 4.1 工程范围与软件栈
### 4.2 时间线（含继续/终止门槛）

## 5. 投稿策略

### 5.1 投稿梯度
### 5.2 为什么目标会议需要这篇论文
### 5.3 论文叙事主线

## 6. 转向方案

{如果核心假设被推翻怎么办？三条路径：缩小为 MLSys 可接受的问题、改投短文或放弃并记录教训。}

*本提案基于 `wiki/proposals/probes/{Slug}.md` 的研究版图分析与 AGENTS.md 品味量表自评。*

```

**V1 自我挑战**：用品味量表的 5 个维度逐条评估 V1：
- 工作负载真实性
- 反直觉性
- 10 倍突破还是 2 倍优化
- 不依赖模型代际
- 抽象贡献

标注每个维度是否通过。≥2 个维度不通过 → 重写 V2。≤1 个维度不通过 → 微调 V1 后输出。

**不能只在心里评估**：在 proposal 末尾显式输出评估结果和重写判断。

**V2（如需要）**：针对不通过的维度重写 proposal。保留 V1 的 section structure，替换薄弱部分。

### 步骤 4 — 输出与记录

- 写文件前按共享契约审查正文、表格、假设、品味评估和投稿策略中保留的英文词；消除未解释术语后再运行定向 `wiki-lint --language-only`
- 写 `wiki/proposals/{Slug}.md`（PascalCase slug）
- 在 `wiki/proposals/_log.md` 追加一条：

```markdown
## [YYYY-MM-DD] {Slug}
- 基于 probe: `wiki/proposals/probes/{ProbeSlug}.md`
- {一句话说明这个提案的核心赌注}
- 品味评估：{通过的维度} / 5
```

## 命名

`wiki/proposals/{Slug}.md`，PascalCase。从 probe slug 自动转换（kebab-case → PascalCase）。

冲突时加 `-{YYYYMM}` 后缀。

## 关键约束

- **probe 是强制前置**：如果用户明确拒绝 probe，跳过但仍警告「未经调研的提案可能忽视关键先行工作」
- **必须输出可证伪假设**：这是提案的脊梁——不能只有「我们做了更好的 X」
- **必须攻击具体假设**：提案的核心赌注应来自 probe 的脆弱假设或关键张力，而不是泛泛补功能或做优化
- **必须输出转向方案**：说明核心假设被测量推翻后怎么办
- **必须输出投稿梯度**：不同测量结果对应不同会议，不假装只有一个目标
- **必须做品味自我挑战**：显式标注每个维度的通过/失败与重写判断
- **proposal 引用 wiki 用 wikilink**，引用外部论文用 standard markdown link 到 arxiv URL
- **proposal 不写 `wiki/log.md`**，只写 `wiki/proposals/_log.md`
- Proposal 的中文叙述、术语解释和可读性必须通过共享写作契约；论文、系统、模型、指标和 venue 原名按契约保留并首次解释。
