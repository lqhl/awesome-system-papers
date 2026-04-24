---
type: paper
name: VeriMoA
full_title: "VeriMoA: A Mixture-of-Agents Framework for Spec-to-HDL Generation"
authors: [Heng Ping, Arijit Bhattacharjee, Peiyu Zhang, Shixuan Li, Wei Yang, et al.]
venue: MLSys
year: 2026
tags: [llm-agent, hdl-generation, eda, mixture-of-agents, code-generation]
source_pdf: "[[35f4a8d465e6e1edc05f3d8ab658c551.pdf]]"
source_md: "[[35f4a8d465e6e1edc05f3d8ab658c551]]"
---

# VeriMoA: A Mixture-of-Agents Framework for Spec-to-HDL Generation (MLSys 2026)

> **一句话总结**：训练免费的 Mixture-of-Agents 框架用 quality-guided global cache 打破 layer 级联依赖 + C++/Python 中间表示的多路径生成，在 VerilogEval 2.0 和 RTLLM 2.0 上跨多个 LLM backbone 把 Pass@1 提升 15–30%，让小模型追平大模型/微调模型。

## 问题

Spec-to-HDL（natural language spec → Verilog）对 LLM 很难：HDL 在 pretraining 中占比低，参数化知识稀薄；且 HDL 要建模并发硬件行为、满足时序和综合约束。现有做法：
- **Prompt engineering**（ParaHDL、AoT）：受限于 LLM 预存 HDL 知识。
- **Fine-tuning**（RTLCoder、AutoVCoder、VeriSeek、ChipSeek-R1）：需大规模 simulation-verified 数据和昂贵训练。
- **Multi-agent**（MAGE 线性 pipeline、CoopetitiveV 辩论）：噪声在层间累积；探索空间受限陷入局部最优。

标准 MoA（Mixture-of-Agents）虽然按层聚合减少错误传播，仍然受"每层仅从前一层拿输入"这个级联依赖困扰，LLM 对 HDL 的知识不足让每层都注入非平凡错误。

## 核心方法

**1. Quality-Guided Global Cache**：
- L 层结构（L-1 个 proposer 层 + 1 个 aggregator 层），每层 M 个 agent 并行。
- Global cache $\mathcal{C}$ 存所有 intermediate HDL + quality score。第 i 层 agent 的 prompt = design description ⊕ **TopN from $\mathcal{C}_{<i}$**，而非仅 layer i-1 输出。
- 数学保证（Eq. 14/15）：因为 $\mathcal{C}_{<i+1} \supset \mathcal{C}_{<i}$，top-n 的 min 质量与 avg 质量单调不降——monotonic knowledge accumulation。

**2. Quality Evaluator（Algorithm 1）**：hierarchical scoring
- 通过 syntax + function test → perfect score。
- 通过 syntax 但 func 失败 → 按 severe/moderate/minor error 扣分。
- Syntax 都不过 → module structure + logic keywords + formatting 的 rule-based fallback 评分。
- 把 HDL 特有的 reset 信号、signal driving conflict、timing 约束等领域知识编码为评分规则。

**3. Multi-Path Generation with IR**：三种 agent 类型混合
- **Base agent**：spec 直接生成 HDL。
- **C++ agent**：两阶段，spec → C++ → HDL；C++ 适合 bit-level 控制。
- **Python agent**：两阶段，spec → Python → HDL；Python 发挥 LLM 高 fluency。

Stage 1 生成 intermediate code，有自己的 cache $\mathcal{C}_\mathcal{L}$ 和 TopK 选择；生成后做 syntax 校验 + self-refine。Stage 2 用 refined IR + Top-n HDL references 生成 HDL。IR 的 quality score 用其生成的 HDL quality 标记（task-aligned）。

**4. 可选 Simulator-based Self-Refinement**：用 testbench T 和 simulator S 对初始 HDL 做反馈 refine，适用于所有 agent。

**5. 理论分析**：MoA 性能 $t = \alpha q + \beta d + \gamma$，其中 α > β（quality 权重高于 diversity）。VeriMoA 用 global cache 最大化 quality，用 multi-path 最大化 diversity，两者协同。

## 关键结果

- 两个 benchmark：VerilogEval 2.0 + RTLLM 2.0。
- 跨多个 LLM backbone（包括小模型和大模型），Pass@1 **提升 15–30%**。
- 小模型搭配 VeriMoA 可以追平大模型和 fine-tuned 专用模型，**无需训练成本**。
- Monotonic 质量提升数学有保证（top-n 集合单调扩张）。

## 相关

- **相关概念**：[[Mixture-of-Agents]]、[[LLM-Agent]]、[[Chain-of-Thought]]、[[Code-Generation]]、[[Self-Refinement]]
- **相关领域**：EDA / HDL generation、Verilog
- **同会议**：[[MLSys-2026]]
