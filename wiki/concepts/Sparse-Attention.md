---
type: concept
aliases: [sparse attention, Sparse Attention, sparse-attention, sparsity, Attention Sparsity, attention sparsity, Block-Sparse-Attention, block sparse attention]
parent: "[[Attention]]"
last_updated: 2026-06-20
tags: [attention, long-context, efficiency, llm-inference, llm-training]
---

# Sparse-Attention

> 放弃 exact dense attention 中的 O(N²) 全对全计算，只让每个 query token 看到全序列的一个子集。子集的选择策略是这个领域的核心设计空间：按位置选（fixed pattern）、按内容选（content-dependent）、按分数选（score-aware）、或学习选（learned/trainable）。

## 核心思想

Dense attention 计算 `softmax(QKᵀ/√d)V`，每对 token 交互，复杂度 O(N²)。Sparse attention 的赌注是：**大部分 token pair 对输出贡献极小**——若能识别并跳过，可在几乎不损失质量的前提下大幅降计算与 KV 读取。

设计空间可按三个维度展开：

| 维度 | 选项 | 代表 |
|------|------|------|
| **稀疏模式** | 固定位置 / 内容依赖 / 分数感知 / 端到端可微 | Longformer、NSA、BLASST、MSA |
| **稀疏粒度** | token / block / document / 层头自适应 | NSA selection、BLASST 128-token block、Twilight |
| **应用阶段** | 仅推理 / 预训练原生 / 从 dense 微调 | BLASST、NSA、SubQ SSA |

关键转折来自 [[NSA-ACL25|NSA]]：在大规模实验（27B MoE, 270B tokens）上，**原生可训练的稀疏注意力可匹配甚至超越 full attention**（7/9 benchmark 反超），稀疏化被重新定位为可能的设计选择而非不得已妥协。但 NSA 也强调：**仅降 FLOPs 不够，kernel 必须少搬 KV、与 GQA/MQA 共享访问对齐**——否则 wall-clock 收益无法兑现。

## 为什么重要

长上下文下 attention 瓶颈随阶段变化：prefill 偏 compute-bound，decode 每步读取整段 [[KV-Cache]] 偏 memory-bandwidth-bound。[[NSA-ACL25|NSA]] 报告 64K context 解码时 attention 可占延迟 **70–80%**；[[BLASST-MLSys26|BLASST]] 在 FA online softmax 中跳过整块可达 **74.7%** 稀疏且 prefill **1.62×**。

这些论文共同假设：**长上下文的解法不能只靠 KV 分页或 offload，必须改信息聚合方式**——但实现路线分裂为：

- **改 attention 计算**（NSA、BLASST、MAC-Attention）
- **改 KV 管理但保留 recall**（[[OPKV-MLSys26|OPKV]]、[[FlexiCache-MLSys26|FlexiCache]]）
- **改检索架构**（[[MSA-arXiv26|MSA]] 用 sparse routing 替代 [[RAG]] retrieve-then-read）

与 [[Flash-Attention]] 正交：FA 保留 exact dense，通过 IO tiling 减 HBM 访问；sparse attention 改变计算本身，二者可叠加（BLASST 在 FA kernel 上 block skipping）。

## 关键观察 / 隐含假设

- **观察 1：稀疏必须覆盖 training + prefill + decode 全生命周期，否则端到端仍接近 dense。** [[NSA-ACL25|NSA]] 批评 H2O（偏 decode）、MInference（偏 prefill）的单阶段优化；inference-only pruning 可能损伤 retrieval head。
- **观察 2：GQA/MQA 下 per-head 独立选 KV 会被 union 读取抵消。** [[NSA-ACL25|NSA]] 要求同 GQA group 共享 block selection；否则稀疏选择不转化为真实带宽节省。
- **观察 3：attention score 呈 blockwise clustering，block 级选择硬件友好。** [[NSA-ACL25|NSA]] 用 64-token selection block；[[BLASST-MLSys26|BLASST]] 用 block max 与 running max 差 **< ln(λ)** 跳过整块，零 proxy score 开销。
- **观察 4：recallable sparsity 优于永久丢弃，但 token-page 粒度错配放大 I/O。** [[OPKV-MLSys26|OPKV]] 测得按页召回可使 I/O 放大 **4×**；critical token 空间离散、时间局部（相邻 iteration 高重叠）是系统优化支点。
- **观察 5：KV head 的 top-K 时序稳定性分化，可分层管理。** [[FlexiCache-MLSys26|FlexiCache]] 发现 stable head（75%）可每 16 步 rerank + offload 非 top-K 到 host；unstable head 需每步全 GPU 驻留。
- **观察 6：稀疏可从劣化变为正则化，但因果分解仍不充分。** [[NSA-ACL25|NSA]] 在 LongBench、AIME 上超 full attention，作者归因于噪声过滤；三分支 gate 的归纳偏置与 MoE backbone 交互未完全拆开。

## 设计空间与取舍

- **Inference-only vs natively trainable**：BLASST、OPKV 可 plug-in 部署，上限受固定启发式约束；NSA 需从预训练采用新 attention layer，迁移成本高但质量天花板更高。
- **永久丢弃 vs offload vs recall**：StreamingLLM/SnapKV 省内存但有长 generation 精度风险；[[FlexiCache-MLSys26|FlexiCache]] offload 全量 KV 到 host 可 promote，需大 host DRAM + PCIe；[[OPKV-MLSys26|OPKV]] 用 OP Block 聚合降 recall I/O。
- **Block skip vs token skip**：SIMD/Tensor Core 友好，但可能误剪离散关键 token（代码符号、表格单元）。
- **Training-free threshold vs learned routing**：BLASST 的 **λ∝1/L** 自动标定简洁；DSA indexer 等 content-dependent 方法的 O(N²) 额外开销可能在某 context length 吞噬节省的 FLOPs。
- **与系统栈集成**：[[PagedAttention]] block 粒度、[[Continuous-Batching]] iteration 级 metadata、[[Prefix-Caching]]、speculative decoding 的交互在多数论文中仍未端到端验证。
- **与相邻概念**：vs [[Linear-Attention]]（去 softmax）；vs [[KV-Cache-Compression]]（压内存不必然减 attention FLOPs）；vs [[Flash-Attention]]（IO-aware dense kernel）。

## 引用本概念的论文

- [[NSA-ACL25|NSA]] — 硬件对齐 + 原生可训练三分支稀疏，64K decode 等效 KV 读取 **11.6×** 减少，LongBench 超 full attention。
- [[BLASST-MLSys26|BLASST]] — FA online softmax 中 block threshold 动态稀疏，prefill **1.62×**、decode **1.48×**，λ∝1/L 自动标定。
- [[OPKV-MLSys26|OPKV]] — recallable sparsity 的 plugin 框架，OP Block 聚合 + hot page 复用，InfiniGen/OmniKV 吞吐 **1.3–1.8×**。
- [[FlexiCache-MLSys26|FlexiCache]] — per-head 时序稳定性分层 sparse decode + KV offload，GPU 内存降 **70%**、TPOT **1.6–2.1×**。
- [[MAC-Attention-MLSys26|MAC-Attention]] — query 复用减少 KV 访问（见 paper 页）。
- [[SparseSpec-MLSys26|SparseSpec]] — 自投机解码中的动态 sparse attention。
- [[db-SP-MLSys26|db-SP]] — block-sparse attention 与序列并行的 head/block 双级负载不均。
- [[FlashAttention-NeurIPS22|FlashAttention]] — block-sparse FA 变体，证明 sparse 也需 IO-aware kernel 才兑现 speedup。
- [[MSA-arXiv26|MSA]] — 可微 document-wise routing，从架构侧挑战 [[RAG]] + dense attention 组合。
- [[DeepSeek-V4-arXiv26|DeepSeek-V4]] — CSA+HCA 混合 sparse + compressed dense 路线（见 paper 页）。
- [[MoE-nD-arXiv26|MoE-nD]] — 推理时 KV 压缩与 [[Sparse-Attention]] 类方法对照：不改 attention 架构，改每层保留 token（见 paper 页）。

## 已知局限 / 开放问题

- 不同稀疏策略在 100B+ / 2T+ tokens 规模下的相对质量排序未知；NSA 仅覆盖一个 27B MoE 主设置。
- 完全无 dense fallback（SSA 路线）vs 保留少量 dense（HCA 路线）的头对头对比缺失。
- Content-dependent selection 的 indexer 开销在多大 context 下吞噬 attention 节省，缺少统一 crossover 模型。
- 稀疏注意力在 thinking/reasoning 模型长 CoT trace 上的行为未系统研究；[[OPKV-MLSys26|OPKV]] 指出 temporal locality 可能衰减。
- production serving stack 下的 P99 TPOT、multi-tenant fairness、与 [[Prefix-Caching]]/PD 分离的组合评测普遍缺失（NSA、BLASST、FlexiCache 均指出）。
- blockwise locality 对代码、表格、形式化证明等离散 attention 模式是否成立，需 missed-critical-token rate 诊断（[[NSA-ACL25|NSA]] future work）。