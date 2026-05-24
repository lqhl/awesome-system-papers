---
type: concept
aliases: [FlashAttention, flash-attention, Flash Attention, FlashAttention-2, FlashAttention-3, FA, FA2, FA3]
parent: "[[Attention]]"
introduced_by: "[[FlashAttention-NeurIPS22]]"
last_updated: 2026-05-24
tags: [attention, gpu-kernel, llm-training, llm-inference]
---

# Flash-Attention

> IO-aware 的 exact attention kernel：把 softmax(QKᵀ/√d)V 用 tiling + [[Online-Softmax|online softmax]] 融合成单个 GPU kernel，避免把 N×N 的 attention matrix 写回 HBM。比 naive 实现 2-4× 快、内存从 O(N²) 降到 O(N)，并且**数值上精确等价**——这是它跟 sparse/linear attention 路线的本质区别。FA2、FA3、ThunderKittens / HipKittens 等后续工作把同一思想推到新硬件（H100 TMA、MI300X、Blackwell）和新变体（paged、block-sparse、quantized）。

## 核心思想

Attention 的 baseline 实现分三步：
1. `S = QKᵀ / √d` — 写出 N×N 矩阵到 HBM
2. `P = softmax(S)` — 读回、算、再写
3. `O = PV` — 读回、算、写出

N×N 矩阵的 HBM 读写是瓶颈（N=8K 时中间矩阵 >100 MB，远大于 SRAM）。

**FlashAttention 的做法**：
- 把 Q/K/V 按 block 切分，每个 block tile 装进 SRAM
- 外循环遍历 K/V blocks，内循环遍历 Q blocks（FA2 反过来，Q 外 K 内效率更高）
- 用 **online softmax** 增量维护 `(running max, running sum, running output)`，无需一次见到完整行
- 全程只在 SRAM 里算，HBM 只读 Q/K/V 各一次、写 O 一次
- 反向用 recomputation 代替保存 softmax 中间值，进一步降显存

数学上等价 standard attention，数值误差在 FP16/BF16 的舍入范围内（FA3 在 Hopper 上用 FP8 需额外处理 scaling）。

## 为什么重要

Attention 占 Transformer 训练/推理大头，这个 kernel 相当于给整个 LLM 栈做了一次 memory-bandwidth bound 的量级提速：

- **训练**：长 context 从「显存不够所以短」变成「算力不够所以慢」——把扩长度问题从显存问题转成通信/算力问题
- **推理 prefill**：长 prompt 变得可行（decode 阶段 FA 的加速有限，因为 batch=1 N→1）
- **成为事实标准**：HuggingFace Transformers、vLLM、SGLang 等默认路径；PyTorch `F.scaled_dot_product_attention` 内置 FA backend

## 版本演进

| 版本 | 硬件 | 关键改进 |
|---|---|---|
| FA1 (NeurIPS 22) | A100 | 奠定 tiling + online softmax |
| FA2 (2023) | A100 | 外循环对调 (Q 外 K 内)、减少非 matmul FLOP、2× over FA1 |
| FA3 (2024) | H100 | 利用 TMA async、FP8、warp specialization、1.5-2× over FA2 on H100 |
| FA4 ([[FlashAttention-4-MLSys26]]) | Blackwell | 针对 B200 Tensor Memory、新 tensor core 路径再做适配 |

并行工作：[[ThunderKittens]] (Stanford Hazy Research) / [[HipKittens-MLSys26|HipKittens]] (AMD 移植) / [[ParallelKittens-MLSys26|ParallelKittens]] 等是相同 tiling 哲学在新 DSL 上的再实现。

## 与 KV-Cache 的关系

FA 优化的是 attention **kernel**（怎么算），[[KV-Cache]] / [[PagedAttention]] 优化的是 KV **存储**（怎么放）。两者正交、常同时使用：PagedAttention 提供 block table，FA kernel 按 block 读取、在 SRAM 内算 online softmax。

## 引用本概念的论文

- [[FlashAttention-NeurIPS22|FlashAttention]] — 引入 IO-aware exact attention kernel：tiling + online softmax + backward recomputation，不改变 dense attention 语义但避免物化 `N x N` attention matrix
- [[FlashAttention-4-MLSys26|FlashAttention-4]] — Blackwell 世代重写
- [[HipKittens-MLSys26|HipKittens]]、[[ParallelKittens-MLSys26|ParallelKittens]]、[[Flashlight-MLSys26|Flashlight]]、[[TritorX-MLSys26|TritorX]] — 新 DSL / 新硬件上的 kernel 重实现
- [[MAC-Attention-MLSys26|MAC-Attention]]、[[BLASST-MLSys26|BLASST]]、[[SpanQueries-MLSys26|SpanQueries]]、[[IntAttention-MLSys26|IntAttention]] — FA 思想的变体（sparse、range-query、integer）
- [[FlashInfer-Bench-MLSys26|FlashInfer-Bench]]、[[PIKE-MLSys26|PIKE]]、[[DistCA-MLSys26|DistCA]] — 调度 / bench / 分布式 attention
- [[StreamDiffusionV2-MLSys26|StreamDiffusionV2]]、[[TiDAR-MLSys26|TiDAR]] — 扩散 / 生成模型里调用 FA
- [[LayeredPrefill-MLSys26|LayeredPrefill]]、[[BatchLLM-MLSys26|BatchLLM]]、[[MorphServe-MLSys26|MorphServe]]、[[BOOST-MLSys26|BOOST]]、[[PyLO-MLSys26|PyLO]]、[[AXLearn-MLSys26|AXLearn]]、[[db-SP-MLSys26|db-SP]] — serving / training 系统复用 FA backend

## 相关概念

- 上游：[[Attention]]、[[Online-Softmax]]
- 并行维度：[[Sparse-Attention]]（非精确的对照面）、[[Tree-Attention]]、[[RadixAttention]]
- 硬件 DSL：[[ThunderKittens]]
- 互补优化：[[KV-Cache]]、[[PagedAttention]]、[[Prefix-Caching]]
