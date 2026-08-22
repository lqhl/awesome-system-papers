---
name: proposal
description: "通过证据门槛（evidence gate）筛选一个可证伪核心赌注，复用已有 probe 或执行范围化证据检查，生成面向系统研究者、背景优先的两页 research proposal，并用独立 critic 检查研究品味、证据与可读性。Triggers on /proposal with a topic, question, or --probe slug."
---

# 研究提案 Proposal Skill

把 probe 的研究版图转化为一份读者能快速理解、证据可追溯、可以被实验推翻的短提案。分析阶段保持严格；最终正文不展示候选淘汰过程或完整审计记录。

## 写作契约

生成正文、假设、品味评估或日志前，完整阅读并执行 [中文写作与术语解释契约](../_shared/chinese-writing.md)。

## 用法

```text
/proposal <topic-or-question> [--probe <slug>] [--hypotheses H1,H2,H3] [--hypotheses-only]
```

- `--probe`：显式使用 `wiki/probes/{slug}.md`，proposal 标记为 `probe-backed`。
- `--hypotheses`：把用户假设放入同一证据与品味筛选，不自动视为合格。
- `--hypotheses-only`：只在对话中返回筛选结果，不写 proposal 或日志，除非用户明确要求存档。

## 步骤 1 — 证据门槛

1. 完整读取 AGENTS.md Taste Rubric 和共享中文契约。
2. 显式传 `--probe` 时读取对应 probe；未传时先查找 topic/slug 明确匹配且不超过 30 天的 probe。匹配成功后使用 `evidence_mode: probe-backed`。
3. 没有匹配 probe 时执行范围化证据检查（scoped evidence check）：从 wiki 读取最接近的 3–5 篇工作，核对一个明确的现有假设或边界、反例、覆盖缺口和最新外部工作；使用 `evidence_mode: scoped`，不生成 probe 文件。
4. 遇到以下任一情况，范围化检查不够，停止并建议先运行 `/probe <topic>`：
   - 提案跨多条研究路线或声称 high novelty；
   - 面向完整 OSDI/SOSP 级新方向，但最近工作或社区共识不清楚；
   - 核心赌注命中覆盖缺口，或外部工作可能改变结论；
   - 最近邻无法收敛到 3–5 篇，或关键论断只有摘要证据。
5. Probe 超过 30 天时检查主题变化速度、搜索截止点和覆盖缺口；可能出现改变结论的新工作时先刷新 probe。
6. 核心主张只能由 `complete/full-text` 或直接回源全文支撑；`abstract-only` 只作线索，`needs-review` 不能单独支撑核心赌注。工业资料可以证明工作负载与需求，但不能单独证明学术空白。

## 步骤 2 — 筛选一个核心赌注

在内部生成 2–4 个候选并检查：证据来源、覆盖路线、最近反例、最小测量和 Taste 预筛。候选表不写进最终 proposal。

- 只选一个主假设；最多保留两个与主假设有因果依赖的辅助判断。
- 共同缺陷不自动成为假设，候选空白不自动成为新颖性。
- 候选必须组成“观察或测量 → 核心洞察 → 设计回应 → 结果验证”的单一链条。
- 若只剩局部工程优化或测量问题，输出归档评估，不强行生成 active proposal。

## 步骤 3 — 建立内部假设卡

每个保留假设在分析中必须具备：

- 来源与攻击对象；
- 适用的模型、工作负载、硬件和部署边界；
- 成立与不成立时的可观察结果；
- workload、baseline、metric 和最小实验；
- 有来源的决策阈值，或明确标为待先导测量；
- 反证后的含义与转向。

最终正文把这些压缩为“假设、反证条件、成功标准”，不要逐项复制内部假设卡。

## 步骤 4 — 写两页短提案

默认读者是系统研究者。GPU、NUMA、MoE、KV cache、PCIe、RDMA、P99 等常用词直接使用，不写中文名和英文全称。不要默认生成 `阅读提示`。

Active proposal 的 frontmatter 保持项目既有 schema，并增加证据来源：

```yaml
evidence_mode: probe-backed  # probe-backed | scoped
source_probe: "[[topic-slug]]"  # 仅 probe-backed 使用；scoped 模式省略
```

正文使用以下顺序：

```markdown
# {Title}

> {用一句话串起问题、核心想法和预期影响}

## 1. 背景与动机

{先说明系统与真实工作负载，再说明具体痛点、后果、为什么现在重要。用 3–5 个最接近工作解释现有方法为何仍不够。}

## 2. 问题与核心假设

{定义输入、约束、目标和不做什么。}

- **核心假设**：...
- **反证条件**：...
- **成功标准**：...

## 3. 核心方案

{解释新抽象或机制、关键数据流和最小实现，不展开所有可选组件。}

## 4. 为什么能做成

{集中说明直接证据、可复用系统、工程范围、资源条件和最大风险。不要把可行性散落到全文。}

## 5. 验证计划

| 要验证什么 | Workload / baseline | Metric 与 go/no-go |
|---|---|---|

## 6. 风险与转向

{主假设验证、部分验证和推翻时分别交付什么；在此给出按结果分级的投稿梯度。}

## 品味评估

{用一张紧凑表或一段话给出五项最终判断与最大残余风险。}

{结尾按 evidence mode 二选一：probe-backed 写“本提案基于 [[{ProbeSlug}]]”；scoped 写“本提案采用范围化证据检查，未生成独立 probe”。}
```

### 正文预算

- 正文目标为 2000–3000 个中文字，不含 frontmatter、URL 和代码块。
- 最多两张表、一个必要公式；不要附完整证据卡、候选表或 critic 长报告。
- 前 600 个中文字必须让读者理解背景、问题、重要性和现有方法缺口。
- Related work 融入“背景与动机”和“为什么能做成”，只保留最接近的 3–5 项。
- 证据等级只在影响可信度时用一句话说明；引用放在对应判断附近。
- `target_venue`、`novelty`、`feasibility`、`effort` 在证据审查和 critic 后回填。

### 归档评估

没有合格赌注时使用更短结构：

1. `原问题与背景`
2. `为什么归档`
3. `剩余未知与重启条件`
4. `品味评估`

目标为 1000–1800 个中文字。保留证据充分的终止理由，不保留历史版本、修改说明或完整旧设计。

## 步骤 5 — 独立 critic

创作稿必须交给未参与筛选和写作的独立 critic agent。只提供 probe、创作稿、Taste Rubric 和必要源证据，不提供创作者自辩。

Critic 先执行读者测试：

1. 读完第一节能否复述背景、问题、重要性和现有缺口？
2. 不读 probe 能否理解核心想法？
3. “为什么能做成”是否集中给出证据、复用基础与最小范围？
4. 正文是否符合长度、表格和常用缩写规则？

任一项失败都必须改写。随后检查五项 Taste Rubric、证据准入、覆盖缺口、阈值来源和单一因果链。至少两项 Taste 不通过时重写并复审，最多两轮；仍不通过则输出归档评估。

最终正文只保留 critic 的紧凑结论和最大残余风险，不保存 V1/V2 对比或完整评语。

## 步骤 6 — 输出与记录

- Active proposal 写入 `wiki/proposals/{PascalCaseSlug}.md`；归档页保留原身份。
- 写入前完成人工语义审计，再运行定向 `wiki-lint --language-only`。
- Probe-backed proposal 正文引用来源时写 `[[{ProbeSlug}]]`；scoped proposal 明确披露证据模式，不伪装成完整 landscape。
- 在 `wiki/proposals/_log.md` 顶部记录 evidence mode、核心赌注、证据状态、最终 Taste 和重写轮数；probe-backed 的来源写成 `基于 probe：[[{ProbeSlug}]]`。
- 不写 `wiki/log.md`。Wiki 内部引用使用 wikilink，外部论文使用标准 Markdown 链接。
