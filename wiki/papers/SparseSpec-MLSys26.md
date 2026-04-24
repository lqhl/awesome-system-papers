---
type: paper
name: SparseSpec
full_title: "Accelerating Large-Scale Reasoning Model Inference: Self-Speculative Decoding with Sparse Attention"
authors: [Yilong Zhao, Jiaming Tang, Kan Zhu, Zihao Ye, Chi-Chih Chang, "et al."]
venue: MLSys
year: 2026
tags: [reasoning-models, speculative-decoding, sparse-attention, kv-cache, inference]
source_pdf: "[[6f4922f45568161a8cdf4ad2299f6d23.pdf]]"
source_md: "[[6f4922f45568161a8cdf4ad2299f6d23]]"
---

# Accelerating Large-Scale Reasoning Model Inference: Self-Speculative Decoding with Sparse Attention (MLSys 2026)

> **一句话总结**：SparseSpec 用同一模型做 draft/target（self-speculation），draft 阶段用 PillarAttn 动态 sparse attention（从 verify 阶段的 full attention score 里白嫖 top-K 识别），配合 unified batch scheduler、delayed verification、动态 KV-Cache offload，在 Qwen3 系列 RLM 上比 vLLM 快最多 2.13×。

## 问题

Reasoning LLM（o1、DeepSeek-R1、Qwen3）生成长链 CoT（AIME 上 Qwen3-14B 平均 13K+ tokens，是 Qwen2.5-32B 非推理模型的 7×）。长生成把 inference 从 compute-bound 推向 memory-bound：KV-Cache 加载量随输出长度平方增长，Qwen3-8B+H100+batch128+8K 输出下 KV-Cache 加载占 70% 端到端延迟。

[[Speculative-Decoding]] 是无损加速方案，但现有方法不适配 RLM：

1. **需要额外训练**（EAGLE、Medusa）或模型修改，部署复杂
2. **Training-free 方法 acceptance rate 低**：MagicDec 用 sliding window，N-Gram 用 rule-based，都不适应 RLM 的 context dynamics（reasoning 过程中 sparsity pattern 剧烈变化，见 attention score 可视化）
3. **系统层**：workload fluctuation（draft 和 verify 的 resource usage 不均）、CPU/GPU 显式同步（verify 在关键路径）、KV-Cache 利用率低（输出长度方差大）

## 核心方法

SparseSpec 四部分 co-design：

**1. PillarAttn（动态 sparse attention）**：
- Draft 阶段只加载 top-K critical tokens（sparsity ratio $s \approx 5\%$）
- 关键巧思：**zero memory overhead 识别 critical token**——每 $k$ 个 draft step 之后的 verify 是 full attention，天然算出所有 token 的 attention score；自定义 kernel 在 verify 时 dump logits + logsumexp，重建 attention score，取 top-K 作为接下来 $k$ 个 draft step 的 sparsity pattern（对 GQA head 组内平均）
- 动态更新 + 假设「语义 spatial locality」，stride 等于 speculative step k

**2. Unified Batch Scheduler**：
- 观察：draft 和 verify 在 self-speculation 里共享 weight，GPU 数据/控制流除了 attention 外完全一样。利用 [[PagedAttention]] page_size=1 把 sparse/full attention 统一进同一 pipeline
- Greedy bin-packing：维护 k 个 bucket，新请求塞到 least-loaded bucket，均匀混合 k draft + 1 verify，避免 $T_{GEMM}((k+1)B)$ oversaturation
- **Fused sparse+full attention kernel**：persistent-kernel style 在 on-chip 按 request 类型 dispatch 到各自最优 tile/MMA 模板（FlashInfer 的 full kernel 跑 sparse 只有 50% bandwidth；sparse kernel 跑 full 也掉到 50%）

**3. Delayed Verification**：
- CPU 需要 verify 结果（accepted/rejected tokens、更新 sparsity pattern）才能出发下一步——阻塞 > 20% 延迟
- 观察：只有 $\frac{1}{k+1}$ 的请求处于 verify 阶段。让非 verify 请求在 $(i-1)$ verify 结果出来前直接推进 metadata 准备；verify 请求 stall 一轮到 $(i+1)$ 再跑，实现 CPU/GPU 异步重叠

**4. Dynamic KV-Cache Manager**：
- 输出长度不可预测，两类方法都有坑：保守 batch → KV-Cache 用不满；激进 batch → recompute 过多
- SparseSpec：激进提高 concurrency，快 OOM 时把 KV-Cache chunk-wise async offload 到 host DRAM（FIFO 保证公平）。Qwen3-8B batch=128 每步新 KV 仅 18MB，PCIe 轻松覆盖；offloaded 请求优先 schedule 回 GPU
- 最坏 CPU DRAM 使用 = GPU capacity（8×H100 下 640GB）

**Theoretical speedup**：$\eta = T_{base}/T_{spec}$，$T_{spec}$ 里 attention 部分 reduction ratio 是 $(ks+1)/(k\alpha+1)$——$\alpha \gg s$ 时 attention 大幅缩小。$k=16, \alpha=0.75, s=0.05$ 下 attention 减少 6.78×。

## 关键结果

- 跨 Qwen3-1.7B/8B/14B 在 H100 (TP1/2/4) 上评估，AIME/OlympiadBench/LiveCodeBench 数据集
- **vs vLLM：up to 2.13× 吞吐量**
- vs 其它 training-free：vLLM-NGram 1.56×、MagicDec 1.36×、TriForce 1.76×
- Execution breakdown（Qwen3-8B）：
  - Attention：17.1 → 5.2 ms（-70%）
  - GEMM：7.2 → 8.9 ms（+24%，算力换带宽）
  - CPU：3.2 → 0.5 ms（delayed verification）
  - Total：28.7 → 16 ms（-44%）
- 代码开源 github.com/sspec-project/SparseSpec

## 相关

- **相关概念**：[[Speculative-Decoding]]、[[KV-Cache]]、[[PagedAttention]]、[[Attention]]、Sparse-Attention、[[Chunked-Prefill]]
- **同类系统**：[[vLLM]]、MagicDec、TriForce、EAGLE3、Medusa、FlashInfer
- **相关模型**：Qwen3、DeepSeek-R1、OpenAI-o1
- **同会议**：[[MLSys-2026]]
