---
type: paper
name: BLASST
full_title: "BLASST: DYNAMIC BLOCKED ATTENTION SPARSITY VIA SOFTMAX THRESHOLDING"
authors: [Jiayi Yuan, Cameron Shinn, Kai Xu, Jingze Cui, George Klimiashvili, Guangxuan Xiao, Perkz Zheng, Bo Li, Yuxin Zhou, Zhouhai Ye, et al.]
venue: MLSys
year: 2026
tags: [sparse-attention, flashattention, long-context, llm-inference]
source_pdf: "[[d82c8d1619ad8176d665453cfb2e55f0.pdf]]"
source_md: "[[d82c8d1619ad8176d665453cfb2e55f0]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# BLASST：通过 SOFTMAX 阈值动态阻止注意力稀疏度（MLSys 2026）

> **原题**：BLASST: DYNAMIC BLOCKED ATTENTION SPARSITY VIA SOFTMAX THRESHOLDING

> **一句话总结**：长 context [[LLM]] 需要无预计算、无 proxy score 的稀疏 attention；BLASST 在 [[Flash-Attention|FlashAttention]] online softmax 中用 running max 与 block max 差 **< ln(λ)** 跳过整块 exp / V 加载 / MMA，prefill **1.62×**（74.7% 稀疏）、decode **1.48×**（73.2% 稀疏），且 **λ∝1/L** 自动标定。

## 问题与动机

[[Attention]] **O(n²)** 主导长上下文推理；[[Flash-Attention|FlashAttention]] 优化带宽但仍算满矩阵。[[MInference]]/[[XAttention]] 等需预计算或 proxy scores，开销可抵消收益；静态 pattern 不适配多样分布。多数方法只优化 prefill 或 decode 一端。

BLASST（BLocked Attention Sparsity via Softmax Thresholding）在 block-wise online softmax 中复用已有统计动态剪枝，统一 prefill+decode，支持 [[GQA]]/[[MLA]]/sliding window。

## 关键观察 / 隐含假设

- **观察 1**：若 block 局部 max `m̃` 比 running row max `m` 小超过 `ln(λ)`，则 exp 后整块对输出贡献可忽略，无需另算 importance。
  - **依赖假设**：block-level 决策用 block max 代理 token-level 足够准。
  - **可能失效场景**：极尖锐分布或数值边界使少量远 token 仍重要时被误剪。

- **观察 2**：对给定 target sparsity，用 calibration data 拟合的阈值 `λ=a/L` 与 context length 近似成反比；这不是无需校准的通用常数。
  - **依赖假设**：不同任务/长度共享同一标定规律。
  - **可能失效场景**：多模态/检索增强导致 attention 模式突变需重标定。

- **观察 3：prefill 省 CUDA core+Tensor Core；decode 额外省 HBM V 加载，针对 memory-bound。**
  - **依赖假设**：跳过逻辑开销相对 block 计算可忽略（与 FA 融合）。
  - **可能失效场景**：极低稀疏或极小 batch 时 branch 开销显性。

- **假设 1**：sparsity-aware training 可进一步推 accuracy–sparsity 前沿（可选扩展）。**
  - **证据强度**：**中**——training-free 主路径已测；训练扩展为加分项。

## 核心方法

Algorithm 1 修改 FA forward：每 block 更新 running max；若 **m̃−m < ln(λ)** 跳过 exp、V load、P·V MMA。

**CUDA kernels**：prefill/decode 特化；与 FA2/FA3 类实现融合。

**Calibration**：自动搜 **λ** 达目标稀疏；发现 **λ=a/L** 规律。

**Sparsity-aware training**（扩展）：让模型适应稀疏模式。

## 设计取舍

- **Training-free drop-in vs 架构改动**：易部署，上限受固定阈值启发式约束。
- **Block skip vs token skip**：SIMD 友好，可能多剪一点。
- **vs SpargeAttention**：BLASST 覆盖 decode 且零 proxy 开销；Sparge 仅 prefill 且有 prediction step。
- **边界条件**：H200/B200 评测；与多种 attention variant。

## 实验与结果

- Prefill：**1.62×** @ **74.7%** sparsity；Decode：**1.48×** @ **73.2%** vs FA baseline。
- 精度：高稀疏下 minimal degradation（多 benchmark）。
- **λ=a/L** 标定跨长度鲁棒。
- Sparsity-aware training 可进一步提高可承受稀疏率。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| BLASST 以 online-softmax block comparison 跳过 exp、V load 与 MMA | §1, §3.1, §4, Fig. 1 | kernel-design claim；非端到端 serving result | strong |
| 相对 FlashAttention-3 BF16，最高 prefill/decode 为 1.62×/1.48× | §5.3, Table 4, Fig. 5 | H200/B200；kernel benchmark；非全部 workload | strong |
| B200 约 50%/70% sparsity 时 prefill/decode 有明确 speedups | §5.3, Table 4 | batch 148；32K seq；head dim 128；不同 Q/KV heads | strong |
| BLASST 在 Llama-3.1-8B prefill accuracy 上优于 MInference/FlexPrefill | §5.2, Table 2 | RULER 4K–64K、LongBench；不外推 decode | strong |
| `λ=a/L` 的 calibration 将 50% target 偏离降至平均 1.2% | §3.2, §5.4, Table 5 | Llama-3.1-8B；a 按 target sparsity calibration 拟合 | strong |

## 批判性分析

### 论证链条

Online softmax 已有 m → 可证 negligible block → 跳过三块昂贵操作 → 实测加速，逻辑紧。Block max 代理是主要近似跳步。

### 假设压力测试

128K–1M context 外推依赖 **λ∝1/L** 是否仍成立需更多点。与 [[KV-Cache]] 驱逐类方法正交但联合效果未知。batch>1 serving 行为论文偏 kernel 级。

### 实验可信度

强 FA baseline；prefill+decode 双评。缺：与 [[EAGLE]]/[[Speculative-Decoding]] 端到端 serving、多租户 tail latency。

### 系统性缺陷

论文未讨论误剪对安全对齐/长链推理的累积误差。动态 λ 在线切换的一致性未谈。

## 局限与后续工作

- **局限 1**：block-level 近似在极端 attention 可能掉点。
- **局限 2**：production scheduler 集成为主。
- **Future work 1**：per-layer adaptive λ 的 accuracy–speed 曲线。
- **Future work 2**：与 [[FlexiCache]]/[[PagedAttention]] serving 栈端到端测 TPOT。

## 相关

- **相关概念**：[[Flash-Attention|FlashAttention]]、[[Sparse-Attention]]、[[Long-Context]]、[[GQA]]
- **同类方法**：MInference、XAttention、SpargeAttention、[[NSA]]
- **同会议**：[[MLSys-2026]]
