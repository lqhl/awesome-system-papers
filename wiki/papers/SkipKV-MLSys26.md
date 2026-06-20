---
type: paper
name: SkipKV
full_title: "SkipKV: Selective Skipping of KV Generation and Storage for Efficient Inference with Large Reasoning Models"
authors: [Jiayi Tian, Seyedarmin Azizi, Yequan Zhao, Erfan Baghaei Potraghloo, Sean McPherson, et al.]
venue: MLSys
year: 2026
tags: [kv-cache, llm-inference, chain-of-thought, reasoning-models, eviction]
source_pdf: "[[92cc227532d17e56e07902b254dfad10.pdf]]"
source_md: "[[92cc227532d17e56e07902b254dfad10]]"
---

# SkipKV: Selective Skipping of KV Generation and Storage for Efficient Inference with Large Reasoning Models (MLSys 2026)

> **一句话总结**：观察到 [[KV-Cache]] token 级 eviction 在 [[Chain-of-Thought]] 多 batch 场景因 padding 与碎片化保留导致精度崩塌且生成长度反增，SkipKV 以**句子级**冗余评分 + 自适应 steering 抑制非执行性思考 + batch grouping 提升有效 KV budget，在 DeepSeek-R1 distill 模型上相对 R-KV 精度最高 **+26.7%**、生成长度 **1.6×** 更短、吞吐最高 **9.6×** FullKV。

## 问题与动机

Large reasoning models（[[LRM]]）在数学/代码推理中生成冗长 [[Chain-of-Thought]]，[[KV-Cache]] 随序列长度线性膨胀，常超过模型权重占用（如 R1-Llama-8B 单题 32K token、batch 10 时 KV 约为权重的 **2.5×**），decode 阶段 memory-bound。

既有 [[KV-Cache]] eviction（[[H2O]]、[[SnapKV]]、R-KV）面向长 prefill 或单 batch 设计，在 CoT 场景暴露三类问题：

1. **多 batch 精度崩塌**：固定 KV budget 下 padding 吃掉有效 budget，且扭曲 attention 重要性估计（MATH-500 bs=10 上 R-KV/H2O 明显劣于 bs=1）。
2. **压缩反而拉长生成**：eviction 丢失上下文后模型反复 re-validate，R-KV 在各 KV budget 下生成长度均高于 FullKV。
3. **token 级碎片化**：保留孤立数字/答案片段（如 `6+9i` 碎成 `6`、`9`）诱发 overthinking。

作者 claim：需要**语义连贯、句子粒度**的 eviction，并同时跳过冗余 KV **生成**与**存储**。

## 关键观察 / 隐含假设

- **观察 1：多 batch + KV eviction 时，padding 显著降低 per-sample 有效 KV budget，且扭曲 token 级重要性评分。** MATH-500 prefill 长度 batch 内差异可达 **400+** token；Fig. 3 显示 bs=10 相对 bs=1 精度在低 budget 下大幅下滑。
  - **依赖假设**：推理服务以变长 prefill batching 为主；固定全局 KV budget 而非 per-request 弹性分配。
  - **可能失效场景**：continuous batching 几乎消除 padding、或 per-request 独立 KV pool 时该观察弱化。

- **观察 2：错误 CoT 轨迹含 **1.7–2.6×** 更多高相似句子（PSS≥0.95）与非执行性思考。** AIME-24 上 R1-Qwen-7B / R1-Llama-8B 统计支持句子级冗余是主要可压缩对象。
  - **依赖假设**：句子边界可用换行/标点启发式稳定切分；last-layer hidden state 均值可近似 sentence embedding，无需在线 sentence-transformer。
  - **可能失效场景**：无标点密集数学符号流、多语言混合、或 steering 改变句子结构后切分失效。

- **观察 3：token 级 eviction 保留碎片化关键 token 会触发重复 self-validation，生成长度超过 FullKV。** Fig. 4 R-KV 案例展示 1517 token 中大量黄色 re-check 段。
  - **依赖假设**：永久 eviction（非 [[Quest]] 式 reload）是目标场景——要真省 GPU 内存而非仅稀疏 attention。
  - **可能失效场景**：后期被 evict 句子重新变重要时无法恢复（与 [[FlexiCache]] offload-promote 路线对比）。

- **假设 1：句子冗余分（PSS）量级远高于 token importance（~0.1），可主导 eviction 排序，整句删除优于碎 token 删。**
  - **证据强度**：**中**——式 (6) 设计与案例分析有力，但未单独 ablate「仅句子分 vs 仅 token 分」在各 benchmark 的分解贡献。

- **假设 2：SEAL 式 execution vs non-execution steering + 随非执行句计数自适应增强 α，可缩短生成且不依赖固定 KV budget。**
  - **证据强度**：**中**——相对 SEAL 在 AIME-24 上 **6.6×** KV 节省 + **13.3%** 精度提升；steering 用 500 MATH 样本离线构造，跨域泛化未系统验证。

## 核心方法

SkipKV 为 **training-free** 三层框架，针对 [[LRM]] decode：

**§4.1 句子级 KV storage skipping**：用 last-layer hidden state 均值算 pairwise sentence similarity（PSS）；冗余句对（τ=0.95）标记早期句可 evict。综合 eviction score 融合 SnapKV 式 token importance、R-KV 式 token redundancy 与句子相似度 λ（式 6）。维护 generation space ↔ cache space 句子 span 映射 Φ，周期性（每 ∆t 步）在固定 budget B 下按 score 升序永久 evict。

**§4.2 自适应 KV generation skipping**：离线用 MATH 500 样本构造 steering vector V = mean(execution) − mean(non-execution)；在选定层注入 H ← H + α_t·V，α_t = α_0 + γ·N_o（非执行句计数），抑制冗余思考生成。

**§4.3 Batch grouping**：按 prefill 长度排序后组 batch，降低 ∆_pad = N_max^p − N_p，使有效 budget B′ ≈ B，缓解多 batch eviction 精度损失。

## 设计取舍

- **句子级永久 eviction vs token 级/R-KV**：赢得语义连贯与更短生成，代价是无法 recall 已删句子 KV；长链推理若后期需回看被删中间推导可能退化。

- **Hidden-state PSS vs BERT embedding**：零额外模型、低开销，但 PSS 质量依赖层选择与 delimiter 启发式；复杂代码块可能切分错误。

- **Adaptive steering vs 纯 eviction**：额外改变生成分布（非仅压缩），可能伤害需充分反思的难题；与 SEAL 相比联合压缩 KV 是核心差异。

- **Batch grouping vs 随机 batch**：提升有效 KV budget，但改变样本共批顺序，若服务层假设独立请求调度需额外重排逻辑。

- **边界条件**：单卡 A100 40GB、DeepSeek-R1 distill 7B/14B/Llama-8B、KV budget 512–比例压缩、FlashAttention-2；未集成 [[PagedAttention]]/[[vLLM]] 生产栈、多卡 [[Tensor-Parallelism|Tensor-Parallel]]、量化 [[KV-Cache]]。

## 实验与结果

- **精度**：AIME-24 上 R1-Qwen-14B 以 **6.7×** 更低 KV 内存匹配 FullKV；LiveCodeBench R1-Qwen-7B **+5.2%** 精度且 **2×** 更少 KV；相对 R-KV 最高 **+26.7%**（相似压缩 budget）。
- **生成长度**：相对 FullKV 最多缩短 **28%**；相对 R-KV 少 **32–48%** token（三模型），对应 **1.5–2×** 延迟收益。
- **吞吐**（GSM8K, R1-Qwen-7B, KV=512）：SkipKV **9.6×** FullKV、同 batch 比 R-KV 最高 **1.7×**；transition batch size 达 **28** vs FullKV **10**。
- **Ablation**（AIME-24, R1-Qwen-7B）：句子评分 + steering + batch grouping 逐步相对 R-KV 最高 **+20%** 精度、**30%** 更短输出。
- **vs SEAL**：AIME-24 上 **6.6×** KV 降低、**13.3%** 精度提升，SEAL 仅缩短 ~10% token 且不显式压 KV。

## Critical Analysis

### 论证链条

观察（padding/碎片化/句子冗余）→ 句子级 score + steering + grouping 的设计链条闭合较好；主结果覆盖数学+代码、三模型、多 KV budget。弱点在于 **永久 eviction 的正确性** 主要靠端到端 pass@1 间接验证，缺少逐步 attention 对齐或人工审计 evict 句是否含关键推导。

### 假设压力测试

- **已证明**：多 batch MATH-500 上 batch grouping 使有效 budget 接近名义值（Table 3）。
- **可能失效**：极短 CoT（GSM8K 8K cap）上句子冗余信号弱；代码生成句子边界更模糊；新 LRM 若减少 verbal redundancy，steering 向量需重标定。
- **论文未覆盖**：与 [[KV-Cache]] 量化正交组合、speculative decoding、在线 learning-to-evict。

### 实验可信度

Benchmark 代表 reasoning serving 子集；baselines（H2O、R-KV、FullKV、SEAL）合理。单卡 A100、bs=10 为主，与生产多卡集群有 gap。KV budget 定义为相对 FullKV 平均生成长度的比例，跨任务可比但依赖数据集生成长度分布。

### 系统性缺陷

实现需维护句子 span 表、周期性 eviction、steering 注入——较 R-KV 复杂。尾延迟：eviction 步额外 scoring 与 remap；论文未测 p99。多租户隔离、错误 eviction 的可观测性与回滚机制论文未讨论。

## 局限与 Future Work

- **局限 1**：永久句子 eviction 在超长 generation 中若 attention 回流被删内容，缺乏 promote/reload 机制（作者承认 token 级方法的 revalidation 问题，自身方案用 steering 缓解但未证无界安全）。
- **局限 2**：仅 A100 单卡、R1 distill 系列；与 serving framework 集成与多卡扩展未验证。
- **Future work 1**：measurement 驱动对比句子 offload（[[FlexiCache]] 式）vs 永久 evict 在长 AIME 题上的逐步精度曲线。
- **Future work 2**：与 continuous batching / per-request budget 结合，量化 padding 观察在 production trace 上是否仍主导。

## 相关

- **相关概念**：[[KV-Cache]]、[[Chain-of-Thought]]、[[Speculative-Decoding]]
- **同类系统**：[[FlexiCache]]、[[vLLM]]、[[PagedAttention]]
- **同会议**：[[MLSys-2026]]
- **对比**：[[FlexiCache-MLSys26]]（offload-promote vs 永久 evict）