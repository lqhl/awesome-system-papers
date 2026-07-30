---
type: paper
name: VeriMoA
full_title: "VERIMOA: A Mixture-of-Agents Framework for Spec-to-HDL Generation"
authors: [Heng Ping, Arijit Bhattacharjee, Peiyu Zhang, Shixuan Li, Wei Yang, et al.]
venue: MLSys
year: 2026
tags: [llm-agent, hdl, verilog, mixture-of-agents, code-generation, rtl]
source_pdf: "[[35f4a8d465e6e1edc05f3d8ab658c551.pdf]]"
source_md: "[[35f4a8d465e6e1edc05f3d8ab658c551]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-30
---

# VeriMoA：用于生成 Spec-to-HDL 的混合智能体框架（MLSys 2026）

> **原题**：VERIMOA: A Mixture-of-Agents Framework for Spec-to-HDL Generation

> **一句话总结**：在「标准 [[MoE|MoA]] 层间级联传播噪声、LLM 对 C++/Python 远强于 Verilog」两条观察下，VERIMOA 用全局 quality-guided cache 打破层间依赖、以 Base/C++/Python 三路径扩展解空间，在 VerilogEval 2.0 / RTLLM 2.0 上 Pass@1 提升 **15–30%**（Qwen2.5-7B **56.44%** vs Direct **22.90%**），无需 fine-tuning 即可让小模型超越更大 backbone 与 VeriMaAS。

## 问题与动机

从自然语言 spec 自动生成 Register Transfer Level（RTL）HDL 是芯片设计流水线的长期目标，但通用 LLM 在 HDL 上表现远弱于 C++/Python：预训练语料稀疏、需推理并发硬件行为与时序/综合约束。既有路线分两类：

1. **Model-centric**：prompt 工程（ParaHDL、AoT）受限于模型已有 HDL 知识；fine-tuning（RTLCoder、VeriRL）需大规模仿真验证语料与训练成本，且仍是单体生成。
2. **System-centric multi-agent**：MAGE 等线性 pipeline 易 **error propagation**；CoopetitiveV 等非结构化辩论则 **探索混乱**。二者共同缺陷是：无法过滤噪声、解空间探索受限，易过早收敛到局部最优。

论文声称 VERIMOA（Quality-guided Multi-path Mixture-of-Agents）在 **training-free** 前提下，同时解决噪声传播与推理空间受限，使小模型（7B）匹配甚至超过更大模型与 fine-tuned 专用方案。隐含 workload 是 **有 golden testbench 的 benchmark 级 RTL 模块生成**（VerilogEval 2.0 / RTLLM 2.0），而非完整 SoC 或 sign-off 级设计。

## 关键观察 / 隐含假设

- **观察 1：标准 MoA 在 HDL 任务上随层深性能退化，因每层只接收前一层输出、低质量参考污染后续层**。
  - **依赖假设**：LLM 对 HDL 的生成错误率非平凡，层间无质量过滤时 hallucination 会累积；MoA 性能近似 **t ≈ α·q + β·d + γ** 且 **α > β**（质量比多样性更主导）。
  - **可能失效场景**：若 backbone 已极强（如 GPT-4o Direct 已达 64.74% Pass@1），Q-Cache 边际收益缩小；层数/宽度不足时（1 layer × 1 agent 仅 25.5–39.8%）框架无法发挥。

- **观察 2：LLM 在 C++/Python 上的参数化知识显著强于 Verilog，两阶段 spec→高级语言→HDL 可提升最终 HDL 质量**。
  - **依赖假设**：设计 spec 可被算法化表达（控制流、数据结构）；高级语言中间表示与硬件行为存在可学习的映射；Stage 2 翻译质量随中间码与 HDL 参考质量单调提升。
  - **可能失效场景**：强依赖硬件 idiom（异步 FIFO、时钟域交叉）的模块，Python 抽象可能丢失 bit-level/时序细节；仅 Two-stage 而无 Q-Cache 时增益很小（MoA+Two-stage 对 MoA 仅 +2.60 pp @ Qwen2.5-7B）。

- **观察 3：高多样性探索若无质量过滤，Pass rate 仍低——多样性 alone 不足，需 quality-guided selection 让多样候选转化为有效改进**。
  - **依赖假设**：仿真 + HDL 领域规则（Algorithm 1）给出的 quality score 与最终 pass 率相关；top-n 选取能保留「可修复」的中间解而非纯噪声。
  - **可能失效场景**：testbench 覆盖不足时，高 quality score 仍可能漏功能 bug；语法失败时的 rule-based fallback 分可能无法预测修复潜力。

- **观察 4：并行 agent 宽度（heterogeneous mixture）比单纯加深层数更能提升 Pass@1**。
  - **依赖假设**：同层 Base / C++ / Python 三类 agent 产生结构可区分的 HDL（式 22 的 dissimilarity），且 6 宽度 × 4 层是性价比拐点。
  - **可能失效场景**：API 成本或延迟敏感部署无法承担 4×6 次生成 + 仿真评分；工业多文件工程需跨模块一致性，单模块多样性未必可组合。

- **假设 1：VerilogEval 2.0（156 题）与 RTLLM 2.0（50 题）+ Icarus Verilog 仿真足以代表 spec-to-HDL 的核心难点**。
  - **证据强度**：**中**——覆盖组合/时序与复杂真实任务，但规模小、无综合/时序 closure、无 SystemVerilog/VHDL。

## 核心方法

VERIMOA 在 [[MoE|Mixture-of-Agents]] 范式上叠加两项协同创新，架构见 Figure 1（source_md）。

### Quality-guided caching（回应观察 1、3）

- **结构**：**L=4** proposer layers + 1 aggregator layer；每层 **M=6** 并行 agent；三类 agent 见下节。
- **Global cache**：存储所有层全部中间 HDL 及 quality score **qᵢ,ⱼ = Q(Hᵢ,ⱼ, T, S)**；深层 agent 的 prompt 拼接 **top-n** 历史最优 HDL：**Pᵢ,ⱼ = D ⊕ H⁽ⁿ⁾ᵢ**（i≥2），而非仅前一层输出。
- **Quality evaluator（Algorithm 1）**：优先全仿真通过 → **q_perfect**；语法通过但功能失败 → 按严重逻辑错误、综合问题、风格问题扣分；语法失败 → 模块结构/逻辑关键字/格式 rule-based 打分。将 reset、驱动冲突、时序等 HDL 领域知识注入评分。
- **理论保证**：对 quality score 的最小值与均值 **单调不降**（式 14–15）；注意这是 **评分单调性**，非 Pass@1 单调性。
- **可选 SR**：仿真反馈驱动的 self-refinement（与 MAGE、CoopetitiveV 同类实践）。

### Multi-path generation（回应观察 2、4）

每层 6 个 agent 按位置异构配置（式 11）：

| Agent 类型 | 路径 | 特点 |
|-----------|------|------|
| **Base** | spec → HDL 直出 | 优先硬件 idiom |
| **C++** | spec → C++ → HDL | 强调 bit-level 控制 |
| **Python** | spec → Python → HDL | 高层表达力 |

- **Stage 1**：生成中间码，同样有 intermediate cache **C_L** 与 top-k 选取；语法检查后 self-refinement。
- **Stage 2**：以 refined 中间码 + top-n HDL 参考生成 Verilog。
- **中间码质量**：**q^Lᵢ,ⱼ = q(H^Lᵢ,ⱼ)**，用其产出的 HDL 仿真分代理中间码质量（task-aligned）。

Aggregator 层综合各层 top 候选为最终输出。实现：Icarus Verilog 仿真；采样 temperature=0.8、top_p=0.95；代码 [GitHub](https://github.com/hping666/HDL_Generation)。

## 设计取舍

- **Global cache + top-n vs 标准 MoA 层间传递**：打破级联依赖、实现单调知识累积；代价是 prompt 随层深变长（拼接 n 份 HDL 参考）、每候选都需仿真评分，**LLM 调用与仿真次数显著高于 Direct/CoT**。
- **Training-free vs 推理成本**：无需 HDL 语料 fine-tuning，但 4 层 × 6 agent ×（部分两阶段）≈ 数十次生成/题；论文 **未报告** wall-clock、token 成本或 Pass@1 per dollar。
- **仿真驱动 quality score vs 纯 LLM judge**：功能正确性可验证、与 benchmark 对齐；但绑定 golden testbench，无法泛化到无 TB 的早期架构探索；语法失败时的启发式分可能与「接近正确」程度弱相关。
- **C++/Python 双路径 vs 单路径**：扩展解空间、利用高资源语言先验；增加 Stage 1 失败传播风险，且 Q-Cache 是 Two-stage 生效的前提（ablation 证明）。
- **边界条件**：**有 testbench 的单模块 Verilog 生成**最优雅；**多模块 SoC、综合约束、形式验证、VHDL/SystemVerilog** 论文未覆盖。

## 实验与结果

**Setup**：VerilogEval 2.0（156）、RTLLM 2.0（50）；pass@k（n=10）；非训练 baseline：Direct、CoT、HDLCoRe、VeriMaAS；fine-tuned：RTLCoder、OriGen、HaVen、VeriRL 等。

**主结果（RQ1，Table 1）**——VERIMOA 在所有列出的 backbone 上均为最强非训练方法：

- **Qwen2.5-7B**：VerilogEval Pass@1 **56.44%**（Direct 22.90%，**+33.54 pp**；VeriMaAS 32.81%，**+23.63 pp**）；超越 VeriMaAS + **Qwen2.5-32B**（53.57%）
- **Qwen2.5-Coder-7B**：**60.96%** vs VeriMaAS + Coder-32B **56.67%**
- **Qwen2.5-Coder-32B**：**73.31%** vs VeriMaAS **56.67%**（**+16.64 pp**）
- **GPT-4o-mini**：**72.43%** vs VeriMaAS **56.24%**；**GPT-4o**：**84.97%** vs **71.34%**
- **RTLLM 2.0**：相对 VeriMaAS 稳定 **+7–12 pp** Pass@1，小模型增益更大

**vs Fine-tuned（Table 2）**：

- Coder-7B **60.96%** 接近 VeriRL-DeepSeek-Coder **64.57%**
- Coder-14B **66.86%** 匹配 VeriRL-CodeQwen2.5 **66.28%**
- Coder-32B **73.31%** 超越全部 fine-tuned（**+7.03 pp** over VeriRL-CodeQwen2.5）

**Ablation（RQ2，Figure 2）**：

- **Q-Cache >> Two-stage alone**：7B 上 MoA→MoA+Q-Cache **+11.93 pp** vs MoA+Two-stage **+2.60 pp**
- **Q-Cache 是 Two-stage 前提**：MoA+Q-Cache+Two-stage **52.06%**；完整 +SR **56.44%**

**参数敏感性（RQ3）**：需 **≥3 层且 ≥4 宽** 才达 47.6–56.4%；等 agent 总数下 **加宽优于加深**（2×6 > 3×4 > 4×3）。

**Case study LIFObuffer（RQ4）**：MoA+Q-Cache 质量 0.50→0.82（50% pass）；+Two-stage 0.54→0.93（**80% pass**）。高多样性无 Q-Cache 时 pass 率仍低。

## 批判性分析

### 论证链条

主链条：**测量到标准 MoA 在 HDL 上级联噪声 + LLM 高资源语言更强** → **global cache 打破依赖 + 三路径异构探索** → **Pass@1 大幅提升且小模型可越级**。

设计与观察映射清晰：Q-Cache 直接回应观察 1；Two-stage 回应观察 2；异构 mixture 回应观察 4；case study 支撑观察 3（多样性需质量过滤）。

薄弱环节：理论保证针对 **quality score** 单调性，外推到 **Pass@1 随层深单调提升** 需额外假设（评分与 pass 强相关）。Abstract「15–30%」是相对表述，部分 backbone 相对 Direct 增益达 **33 pp**，口径随 baseline 选择变化。

### 假设压力测试

| 假设 | 论文已证明 | 可能失效条件 |
|------|-----------|-------------|
| Q-Cache 打破级联误差 | Ablation + LIFObuffer 质量曲线 | 极强 backbone、极浅层配置 |
| C++/Python 中间表示有效 | +Two-stage 在 Q-Cache 上 +11.27 pp | 硬件特有 idiom、无算法化 spec |
| 仿真 quality score 代表改进方向 | 与 pass rate 正相关 case study | TB 覆盖不足、工业 sign-off 约束 |
| 4×6 配置可部署 | 参数敏感性 | 生产环境 latency/成本预算 |
| Benchmark 结论可外推 | 两基准 SOTA 对比 | 多文件、IP 集成、非 Verilog |

### 实验可信度

- **优势**：多 backbone（开源 7B–32B + GPT-4o 系列）、强 baseline（VeriMaAS、HDLCoRe、多种 fine-tuned）、系统 ablation 与 case study、理论分析与 MoA 实证（Li et al. 2025）对齐。
- **局限**：**仅 pass@k、n=10**；**单一仿真器**（Icarus）；**无推理成本/延迟**对比；fine-tuned 对比随 backbone 变化（7B 未全面超越）；Table 1/2 为 MinerU 图片，精确数值以 source_pdf 为准。
- **缺失**：无 **工业 trace**、无综合后面积/时序、无 cross-problem 泛化到训练集外 secret holdout 的独立报告。

### 系统性缺陷

- **成本与尾延迟**：每层每 agent 仿真评分，最坏情况 **O(L×M×仿真)** per problem；论文未讨论 batch 仿真、early stopping 或预算约束下的 **anytime** 行为。
- **可观测性**：多层 cache 与多路径使调试链变长；哪条路径贡献最终 pass 的 attribution 未工具化。
- **正确性边界**：依赖 testbench 完整性；对 **X-propagation、metastability、CDC** 等难测性质无额外保障。
- **兼容性**：绑定 Verilog + Icarus flow；与商业 EDA（VCS、DC）集成、[[RocketPPA-MLSys26|RocketPPA]] 类 PPA 闭环未讨论。
- **运维**：API 多 agent 并发的 rate limit、失败重试、确定性复现（temperature=0.8）对 CI 集成的影响论文未涉及。

## 局限与后续工作

- **局限 1**（实验边界）：基准题为 **孤立模块**，规模 156+50，不覆盖系统级 RTL 与验证环境搭建。
- **局限 2**（成本）：training-free 但 **推理/仿真开销** 未量化，难以与 fine-tuning 的一次性成本做公平 TCO 比较。
- **局限 3**（评估）：quality score 在语法错误时的 rule-based 分与最终可修复性的相关性未系统验证。
- **局限 4**（泛化）：仅 Verilog；C++/Python 路径对 SystemVerilog assertion、VHDL 的适用性未知。
- **Future work 1**：在固定 **$/正确模块** 或 **wall-clock** 预算下，对比 VERIMOA vs RTLCoder/VeriRL vs Direct+SR，画出 **quality–cost Pareto**。
- **Future work 2**：**自适应深度/宽度**：当 global cache top-n 质量达阈值时提前终止层迭代，测量 Pass@1 损失 vs 成本节省。
- **Future work 3**：将 Q-Cache 与 **工业 partial testbench / formal property** 结合，在 RTLLM 外加入多模块、带 CDC 的 open benchmark，检验「高资源语言脚手架」是否仍成立。

## 相关

- **相关概念**：[[MoE]]（MoA 层间聚合范式）、multi-agent LLM、spec-to-code、RTL 自动化
- **同类系统**：MAGE、CoopetitiveV、VeriMaAS、HDLCoRe、RTLCoder、[[AccelOpt-MLSys26|AccelOpt]]、[[PIKE-MLSys26|PIKE]]
- **同会议**：[[MLSys-2026]]
- **对比**：vs VeriMaAS——VERIMOA 用 **global Q-Cache** 替代层间盲传递，用 **C++/Python 三路径** 替代单一 agent 拓扑；vs fine-tuned VeriRL——32B 上 **+7 pp** 且无需域内 RL 训练
