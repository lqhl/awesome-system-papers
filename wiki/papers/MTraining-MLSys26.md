---
type: paper
name: MTraining
full_title: "MTraining: Distributed Dynamic Sparse Attention for Efficient Ultra-Long Context Training"
authors: [Wenxuan Li, Chengruidong Zhang, Huiqiang Jiang, Yucheng Li, Yuqing Yang, "et al."]
venue: MLSys
year: 2026
tags: [long-context, sparse-attention, ring-attention, context-parallelism, training]
source_pdf: "[[e2c420d928d4bf8ce0ff2ec19b371514.pdf]]"
source_md: "[[e2c420d928d4bf8ce0ff2ec19b371514]]"
---

# MTraining: Distributed Dynamic Sparse Attention for Efficient Ultra-Long Context Training (MLSys 2026)

> **一句话总结**：MTraining 在 Context Parallelism 中解决动态稀疏注意力的 worker-/step-level 不均问题，用 Striped 布局 + Hierarchical Ring，把 Qwen2.5-3B 的上下文从 32K 扩到 512K（32× A100），吞吐相对 dense 6×、相对 naive 分布式 DSA 2.6×。

## 问题

LLM 扩展上下文到 512K-1M 级别时，attention 占训练成本 90%+。动态稀疏注意力（MInference、xAttention、NSA、MoBA）能省计算，但分布式 Context Parallelism（Ring Attention）下出现两级不均：

- **Worker-level imbalance**：不同 CP worker 持有不同序列块，稀疏 mask 导致 FLOPs 严重不均（xAttention 95% 稀疏 + 32-way CP 的 imbalance degree 3.17）。
- **Step-level imbalance**：同一 worker 在 Ring 各 step 的计算负载随 K/V chunk 差异起伏，高稀疏时 compute 短于 communication 失去 overlap。

此外 ZigZag / Striped 两种 Ring Attention 布局下动态稀疏的空时模式完全不对齐。

## 核心方法

算法 + 系统 co-design 三件套：

1. **Dynamic Sparse Training Pattern**：理论证明 RoPE 下 attention 期望权重仅依赖相对位置 n-m，呈 **Vertical-Slash** 局部性（反向梯度亦然）。在线用 `last_q` 估算 vertical 和 slash 的 budget（top-p），kernel-aware granularity（vertical token-level，slash 64×64 block-level）。

2. **Balanced Sparse Ring Attention (Striped)**：由于 slash 在 block-wise GPU 计算中占主导，用 **Striped**（对角线分布）而非 ZigZag（反对角），64-token stripe 粒度保护 kernel 一致性。细粒度条带（128 worker + 512K 序列时每 worker 拿 64 条 block stripe）自然均摊 step-level 负载。

3. **Hierarchical Balanced Sparse Ring Attention**：inter-node (IB HDR 25 GB/s) 与 intra-node (NVLink 3.0 300 GB/s) 带宽差 3-12×。拆成 inner-ring（节点内 $G_{node}$ 卡循环 KV）和 outer-ring（节点间 $N_{node}$ 节点聚合 KV），post outer P2P 与 inner-ring compute 并行；稀疏 + 对角线布局下计算 pattern 仍保持 Vertical-Slash。

## 关键结果

- Qwen2.5-3B：32K → 512K 扩展，32× A100-40GB，吞吐 6× over dense、2.6× over naive 分布式 DSA。
- 精度与 dense baseline 相当或更优，覆盖 RULER / PG-19 / InfiniteBench / Needle-in-Haystack。
- Llama-3.1-8B-Instruct 更大规模复现。

## 相关

- **相关概念**：Long-context LLM、Dynamic Sparse Attention、Context Parallelism、Ring Attention、RoPE、Vertical-Slash Pattern
- **同类系统**：MInference、xAttention、FlexPrefill、NSA、MoBA、Striped Attention、ZigZag Ring Attention
- **同会议**：[[MLSys-2026]]
