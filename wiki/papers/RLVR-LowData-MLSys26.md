---
type: paper
name: RLVR-LowData
full_title: "Learning from Less: Measuring the Effectiveness of RLVR in Low Data and Compute Regimes"
authors: [Justin Bauer, Thomas Walshe, Derek Pham, Harit Vishwakarma, Armin Parchami, Frederic Sala, Paroma Varma]
venue: MLSys
year: 2026
tags: [rlvr, data-scaling, procedural-data, fine-tuning, slm, grpo]
source_pdf: "[[7f1de29e6da19d22b51c68001e7e0e54.pdf]]"
source_md: "[[7f1de29e6da19d22b51c68001e7e0e54]]"
---

# Learning from Less: Measuring the Effectiveness of RLVR in Low Data and Compute Regimes (MLSys 2026)

> **一句话总结**：在固定算力下用三套 procedural benchmark + Qwen3-4B [[LoRA]] GRPO 实证：低数据 RLVR 中 **mixed-difficulty 训练比纯 easy 样本效率高最高 5×**（counting 100 mixed ≈ 500 easy），但 graph 域受 token budget 截断主导，固定 step 下增大数据反而可能降 test 精度。

## 问题与动机

[[RLVR]] 已成为 LLM 推理 post-training 主流路径（DeepSeek-R1、DeepMath-103K 等），但既有 scaling 研究多假设**充足标注数据与算力**（ScaleRL、Tan et al. 数学推理 scaling）。真实资源受限场景——小团队、新推理域、边缘 SLM——往往只有数百条可验证 QA，且训练 step / token 上限固定。

作者 claim 的不是新算法，而是**在受控低资源 regime 下刻画 data composition 如何影响 RLVR 效果**，为 future data scaling laws 提供实证起点。核心研究问题：当训练数据与算力都有限时，dataset size、difficulty mix、task complexity 如何交互并影响泛化？

与 LIMR（精选小数据集）不同，本文用 procedural generator 显式操控 size / diversity / complexity，并把 difficulty 定义为 **10 个 foundation model 的 empirical pass rate**，而非人类主观标注。深度实验矩阵见 [[7f1de29e6da19d22b51c68001e7e0e54]]。

## 关键观察 / 隐含假设

- **观察 1（难度多样性可替代数据量稳定优化）**：Counting 域下 Mixed-100 训练全程稳定，而 Easy-100 在 step 150 后 validation reward 从 0.89 崩至 0.59，伴随 gradient norm 超基线 **850×** spike；同样本数下 mixed 的跨难度覆盖似乎提供足够 reward 信号密度。
  - **依赖假设**：GRPO group-relative advantage 需要组内 reward 方差；纯 easy 数据 reward 过于同质，小 batch 下策略更新易发散。
  - **可能失效场景**：更大模型、更多 rollout 样本/组、或 dense reward 设计可能消除该不稳定；仅 counting 域出现剧烈 collapse，外推到数学/代码 RLVR 需谨慎。

- **观察 2（mixed-difficulty 带来样本效率，但受固定 step budget 制约）**：Counting test 上 Mixed-100 达 **50.0%** solve，Easy-500 仅 **40.0%**（≈**5×** sample efficiency）；Spatial 上 100 mixed 亦超过 500 easy。但 Counting mixed 从 100→500 样本 test accuracy **50.0%→40.0%** 反降，尽管 validation reward 仍在 step 300 上升。
  - **依赖假设**：固定 300/1000 step 下，更大数据集意味着**每条样本获得的优化更新更少**；mixed 的每-step 信息密度更高。
  - **可能失效场景**：按数据量比例延长训练（更多 epoch）可能逆转「大数据反而更差」；论文仅假设而未实测 prolong training。

- **观察 3（长输出域中 token budget 比 data volume 更 binding）**：Graph Reasoning 的 mixed 集平均图更大（**14.9 vs 12.6** 节点），rollout 更常超 max generation length；reward 中 **59–73%** completion 为 extraction failure，mixed validation reward 持续为负。Easy-500 为最强 test（Table 2），但 medium/hard test 仍几乎全军覆没。
  - **依赖假设**：图题需完整 JSON + 长 reasoning trace；截断输出直接吃负 reward，压制对难例的探索。
  - **可能失效场景**：提高 max tokens、length-adaptive rollout budget、或更短输出格式可能改变 mixed vs easy 的相对优劣；当前结论高度绑定输出长度约束。

- **假设 1（procedural difficulty tier 可代表真实 capability boundary）**：Easy/Medium/Hard 由 10 模型 pass rate 分桶（67–100% / 34–66% / 0–33%），且 Easy vs Mixed 对比沿**多维 complexity 共变**（图大小、filter 步数、action 数等），非单轴难度。
  - **证据强度**：**中**——校准用了 GPT/Claude/Gemini 等 frontier，但 tier 仍是相对标签；论文明确警告勿把性能差异归因于单一 complexity 因子。

- **假设 2（Qwen3-4B + [[LoRA]] r=64 + GRPO 可代表资源受限 SLM RLVR 实践）**。
  - **证据强度**：**中偏弱**——单模型、单 seed、4×A100 固定预算；作者用 18 配置（3 域×6 数据配置）定性趋势一致性作 robustness proxy，非统计显著性检验。

## 核心方法

### Procedural datasets（可控 data development）

三套程序生成 benchmark，均带 deterministic ground truth，支撑 RLVR 无需人工标注：

1. **Counting**：整数序列上 1–7 步 conditional filter + aggregation（Count/Sum/Bitwise 等 15+ 算子）；复杂度由 range scale、filter 深度、变换数控制。
2. **Graph Reasoning**：5–25 节点无向/有向/加权图 + 图论算子（MIS、MVC、Hamiltonian path 等）；答案经 networkx 验证，输出需 GPT-4o 辅助规范化。
3. **Spatial Reasoning**（基于 Dsouza et al. 2025 框架）：20×20 网格上粒子移动/旋转，绝对/相对位置与朝向查询；仿真器给出精确浮点 ground truth。

每域生成 **1500+** 实例；10 模型单 pass 评估后分层，训练子集 **100/200/500**（纯 Easy 或 Mixed 各难度 ~33%），测试集 200（Graph 为 500），split 严格不相交。

### RLVR training stack

- **Base**：Qwen3-4B；**PEFT**：[[LoRA]] r=64、α=16，全 linear 层，可训练参数 ~**100M**。
- **Algorithm**：GRPO（group-relative advantage，batch 内多 completion 比较）。
- **Reward**（域特异，非统一）：
  - Counting：correctness + format bonus + verbosity penalty，r ∈ [−0.4, +1.1]；
  - Graph：correctness + JSON format，截断/超长惩罚；
  - Spatial：二元 exact-match r ∈ {0, 1}。
- **Compute**：4× NVIDIA A100 80GB；Counting/Graph **300 steps**，Spatial **1000 steps**；训练 5–12 小时。验证每 50 step 在 held-out 10% 上监控；测试 greedy decode（temperature 0）。

该设定直接回应低资源假设：不追求 SOTA absolute accuracy，而是在**固定 wall-clock 与 step** 下比较 data curation 策略。

## 设计取舍

- **取舍 1：Empirical difficulty calibration vs 人类/理论难度**：用 10 模型 pass rate 分桶更贴近「当前 frontier 能力边界」，但 tier 随模型代际漂移，且 multidimensional complexity 使因果解释困难；收益是可复现、可扩展的 procedural pipeline。
- **取舍 2：固定 step budget vs 固定 epoch**：所有配置共享 300/1000 step，大数据集每样本更新次数更少——这**刻意模拟**算力受限，但也使「增大数据有害」与「训练不充分」难以分离；论文将其列为与 SFT scaling law 可能背离的假设性发现。
- **取舍 3：Domain-specific reward shaping vs 统一 verifiable reward**：Counting/Graph 的 format/density reward 改善低数据探索，但引入与「纯 outcome correctness」不同的优化目标；Spatial 二元 reward 下 mixed/easy 差异更小，说明 reward 结构调制了 composition 效应强度。
- **边界条件**：Counting/Spatial（短输出）上 mixed-difficulty 与样本效率结论最清晰；Graph（长输出、高截断率）上 **token limit** 压倒 data volume；全研究绑定 4B + LoRA + 单 seed，不声称 universal scaling law。

## 实验与结果

**Counting**
- Test solve：Mixed **50.0% / 50.5% / 40.0%**（100/200/500）；Easy **21.8%→46.1%** 单调随样本增（500 例仍低于 Mixed-100）。
- Mixed-100 跨难度 profile 最均衡；Easy 需 500 例才在 easy 测试题上追平 mixed-100。
- Easy-100 训练不稳定（§4.1.1、Figure 4）；Mixed-100 同规模稳定。

**Graph Reasoning**
- Easy-500 test 最强；Mixed-100 **29.1%** 略低于 base **29.4%**。
- Easy/Medium/Hard test 上 easy-trained 略胜 mixed，但两者在 medium/hard 近乎失败。
- Mixed 训练 validation reward 长期为负；主因 extraction failure 与 incomplete rollout。

**Spatial Reasoning**
- Fine-tuning 相对 baseline 最高约 **2×** 提升（Table 2）。
- Mixed 在同规模下普遍 ≥ Easy；**100 mixed > 500 easy**。
- Easy 设置 200 例峰值后 500 例反降 **3.6%**；Mixed 在 100 例后增益平台化——固定 1000 step 下的 inverted-U。
- 四类 query（绝对/相对 × 位置/朝向）均有提升，relative orientation 在 mixed 下增益最大（Figure 6）。

**跨域设计启示（§4.2）**
1. 训练集 **composition > volume**（Counting/Spatial 5× 效率）。
2. 固定 budget 下单纯增数据可能无效甚至有害。
3. 长 rollout 域需优先解决 token budget，而非堆 easy 样本。

## Critical Analysis

### 论证链条

observation（低资源 RLVR 中 reward 稀疏、更新不均、截断频发）→ design（procedural tier + easy/mixed 对照 + 固定 step）→ result（mixed 样本效率、graph 受 token 绑死、spatial inverted-U）在**描述性层面**闭合。论文诚实标注 multidimensional complexity 与 18 配置趋势一致性，避免过度因果宣称。

薄弱环节：「5× sample efficiency」主要来自 **Counting 单域单指标**（test solve rate），Spatial 支持方向一致但未给出相同倍数；Graph 反例说明 composition 优势**非普适**。把「easy 训练可泛化到更难测试题」推广为一般规律时，graph 域在 medium/hard 上的失败构成反证——泛化边界比 abstract 表述更窄。

### 假设压力测试

- **模型规模**：仅 Qwen3-4B；Tan et al. 表明更大模型 sample efficiency 更高，mixed 优势是否在 7B/32B 上缩小或放大，论文未测。
- **训练预算**：若 mixed-500 训练到 validation 收敛（>300 step），Counting 的「大数据降 test」可能被推翻；当前结论绑定 **under-training of larger sets**。
- **Reward / algorithm**：GRPO + 手工 reward；换 PPO、纯 binary reward、或 outcome-only reward 可能改变 easy-100 collapse 与 mixed 稳定性叙事。
- **难度定义**：10 模型校准快照于 2025 frontier；换 weaker base 或更强 teacher 会重划 tier，procedural 结论是否稳健需时间外推验证。
- **真实数据**：procedural 任务无自然语言噪声、无领域先验；LIMR 在数学上 1.4K curated > 8.5K raw，本文未对比「同等预算下 procedural mixed vs 真实 curated math」。

### 实验可信度

**强项**：三域 18 配置矩阵、训练曲线 + per-difficulty breakdown、reward component 分解（Figure 5）、gradient norm 与 collapse 对齐、严格 disjoint split、多 frontier 模型校准 difficulty。

**不足**：
- **无 multi-seed**；作者以跨配置趋势替代，统计置信区间缺失。
- **单 base model**；LoRA rank、GRPO 超参未做 sensitivity。
- **Graph 评估依赖 GPT-4o 规范化**，引入额外模型依赖与成本，且可能掩盖格式错误。
- **Test metric 不统一**（counting 用 mean reward + solve rate，spatial 用 accuracy，graph 用 mean reward）；跨域比较需谨慎。
- **未报告训练成本细分**（rollout tokens、截断率分布、每 step wall-clock），系统部署者难以直接映射预算。

### 系统性缺陷

- **尾延迟 / 截断**：Graph 域 incomplete rollout 是系统性失败模式，论文识别但未提供 production 级 mitigation（dynamic max tokens、speculative shortening）。
- **可复现性**：procedural generator + 10 模型 calibration 管线复杂，开源状态文中未强调；复现需重现同等 difficulty tier。
- **运维**：面向 practitioner 的决策规则（何时选 mixed、多少 step/样本比）仅为定性启发，无自动 curation policy 或 budget-aware scheduler。
- **多租户 / 持续学习**：未讨论 mixed 数据分布漂移或 replay easy 样本是否必要。
- **与 SFT 对比**：全程 RLVR，未在同一 data budget 下对照 SFT，难以分离「RL 探索」与「难度 mix」各自贡献。

## 局限与 Future Work

- **局限 1**（论文承认）：4B + LoRA、固定低算力、无 multi-seed；定量增益（如 5×）未必迁移更大模型或 full fine-tuning。
- **局限 2**：Procedural 任务不覆盖自然语言推理复杂度；无 MATH/GSM8K 等 transfer 实验。
- **局限 3**：Easy vs Mixed 对比沿多维 complexity 共变，因果归因受限；graph 反例显示 domain-specific constraint（token limit）可压倒 composition 收益。
- **局限 4**：固定 step 使 data scaling 与 optimization budget 纠缠，结论应解读为 **joint budget** 现象而非纯 data law。
- **Future work 1**（论文提出）：建立 dataset properties → post-RLVR performance 的扩展 scaling laws；在更大模型与算力下验证 mixed-difficulty 趋势是否保持。
- **Future work 2**：length-adaptive optimization / token budget 与 difficulty mix 联合调度，尤其在 verbose reasoning 域复测 graph 结论。
- **Future work 3**（可验证延伸）：对 mixed-N 配置按 N 比例延长 training steps，分离「每样本更新不足」与「难度 mix 本身」对 test 的影响；报告 multi-seed 置信区间。
- **Future work 4**：同等低预算下对比 RLVR vs SFT + curated vs procedural mixed，量化 exploration 与 composition 的边际贡献。

## 相关

- **相关概念**：[[LoRA]]、RLVR、GRPO、Data-Scaling-Laws、Procedural-Benchmarks、SLM-Fine-Tuning
- **同类工作**：DeepSeek-R1、DeepMath-103K、ScaleRL、LIMR、Tan et al. RL post-training scaling、Dang & Ngo SLM RL 研究
- **同会议**：[[MLSys-2026]]
- **对比**：大数据 RLVR scaling（ScaleRL）vs 低数据 composition 效应（本文）vs 精选小数据（LIMR）