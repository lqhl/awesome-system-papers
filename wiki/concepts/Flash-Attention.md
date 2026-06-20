---
type: concept
aliases: [FlashAttention, flash-attention, Flash Attention, FlashAttention-2, FlashAttention-3, FA, FA2, FA3]
parent: "[[Attention]]"
introduced_by: "[[FlashAttention-NeurIPS22]]"
last_updated: 2026-06-20
tags: [attention, gpu-kernel, llm-training, llm-inference]
---

# Flash-Attention

> IO-aware 的 exact attention kernel：把 `softmax(QKᵀ/√d)V` 用 tiling + [[Online-Softmax|online softmax]] 融合成单个 GPU kernel，避免把 N×N attention matrix 写回 HBM。比 naive 实现 2–4× 快、内存从 O(N²) 降到 O(N)，且**数值上精确等价**——这是它与 sparse/linear attention 路线的本质区别。[[FlashAttention-2-ICLR24|FA2]]、[[FlashAttention-3-NeurIPS24|FA3]]、[[FlashAttention-4-MLSys26|FA4]] 及 ThunderKittens / HipKittens 等把同一思想推到新硬件与新变体。

## 核心思想

Baseline attention 分三步：`S = QKᵀ/√d`（写出 N×N 到 HBM）→ `P = softmax(S)`（读回、算、再写）→ `O = PV`（读回、算、写出）。N×N 矩阵 HBM 读写是瓶颈（N=8K 时中间矩阵 >100 MB，远大于 SRAM）。

FlashAttention 做法：Q/K/V 按 block 切分，block tile 装进 SRAM；外循环遍历 K/V blocks，内循环遍历 Q blocks（[[FlashAttention-2-ICLR24|FA2]] 对调为 Q 外 K 内效率更高）；用 online softmax 增量维护 `(running max, running sum, running output)`，无需一次见到完整行；全程 SRAM 内算，HBM 只读 Q/K/V 各一次、写 O 一次；反向用 recomputation 代替保存 softmax 中间值。

数学上等价 standard attention，数值误差在 FP16/BF16 舍入范围内。[[FlashAttention-3-NeurIPS24|FA3]] 在 Hopper 上用 FP8 需额外 scaling；[[FlashAttention-4-MLSys26|FA4]] 在 Blackwell 上面临 SMEM 读与 exponential 与 MMA 同级的 cycle 预算。

## 为什么重要

Attention 占 Transformer 训练/推理大头，FA 相当于给整个 LLM 栈做了一次 memory-bandwidth bound 的量级提速。这些论文共同假设：**exact dense attention 的瓶颈在 HBM 流量而非 FLOPs，IO-aware kernel 融合是比改 attention 语义更通用的加速路径**。

影响深远：训练时长 context 从「显存不够所以短」变成「算力/通信不够所以慢」；推理 prefill 长 prompt 变得可行（decode 阶段 FA 加速有限，因 batch=1 N→1）；成为事实标准——HuggingFace Transformers、[[vLLM]]、[[SGLang]] 默认路径，PyTorch `F.scaled_dot_product_attention` 内置 FA backend。与 [[KV-Cache]] / [[PagedAttention]] 正交：FA 优化 attention kernel（怎么算），KV 管理优化存储（怎么放）。

## 关键观察 / 隐含假设

- **观察 1：FA2 减少非 matmul FLOP 与 work partitioning 重设计是 A100 上 2× over FA1 的主因。** [[FlashAttention-2-ICLR24]] 沿 sequence length 增加并行度、warp 内 split-Q，attention forward 最高 230 TFLOPs/s。
- **观察 2：Hopper 上 TMA async + WGMMA-softmax overlap 是 FA3 相对 FA2 1.5–2× 的关键。** [[FlashAttention-3-NeurIPS24]] BF16 forward 最高 840 TFLOPs/s、FP8 1.3 PFLOPs/s。
- **观察 3：Blackwell 上 SMEM 读与 exponential 可与 MMA 同级甚至更高，softmax 中 `exp` 使 exponential unit 成为与 MMA 并列瓶颈。** [[FlashAttention-4-MLSys26]] roofline 在 `M=N=d=128` 时 MMA/exp 各约 1024 cycles、SMEM 768 cycles；MUFU 与 tensor core 差距约 512×。
- **观察 4：FA 与 KV 管理正交但 serving 栈常同时使用——PagedAttention block table + FA variable-length packing 是 [[Continuous-Batching]] / [[Chunked-Prefill]] 的底层支撑。** [[GhostServe-MLSys26]] 在 FA chunk 级做 KV parity checkpoint；[[ScaleSearch-MLSys26]] 将 FA 式分块与 NVFP4 attention 结合。

## 设计空间与取舍

- **路线 1：FA1/2/3/4 代际演进（exact dense）**：数值等价、生态成熟；牺牲是每代硬件需重写 kernel（A100→H100→B200），cuDNN 合入后开源/闭源差距缩小（[[FlashAttention-4-MLSys26]] 局限 2）。
- **路线 2：DSL 重实现（[[ThunderKittens]]、[[HipKittens-MLSys26]]、[[ParallelKittens-MLSys26]]、[[Flashlight-MLSys26]]）**：可组合 primitive、新硬件快速适配；牺牲是开发门槛与性能调优周期。
- **路线 3：Sparse / range-query 变体（[[MAC-Attention-MLSys26]]、[[BLASST-MLSys26]]、[[SpanQueries-MLSys26]]、[[IntAttention-MLSys26]]）**：保留 FA tiling 哲学但放宽 exact 语义或改数值格式；牺牲是精度/泛化需 per-workload 验证。
- **路线 4：量化 attention（[[FlashAttention-3-NeurIPS24]] FP8、[[ScaleSearch-MLSys26]] NVFP4、[[Kitty-MLSys26]]）**：利用低精度 tensor core；牺牲是 scaling 策略与 conditional rescaling 的训练语义影响未充分评估（[[FlashAttention-4-MLSys26]]）。
- **路线 5：分布式 attention（[[DistCA-MLSys26]]、[[PIKE-MLSys26]]、[[Collective-NoC-MLSys26]]）**：长 context 跨卡 FA + ring/sequence parallel；牺牲是通信与 kernel 协同复杂度。
- **路线 6：放弃 exact dense（[[Sparse-Attention]]、[[Linear-Attention]]）**：从根本上降 O(N²)；牺牲是模型质量与算法通用性，与 FA 路线正交。

## 引用本概念的论文

- [[FlashAttention-NeurIPS22|FlashAttention]] — IO-aware exact attention：tiling + online softmax + backward recomputation
- [[FlashAttention-2-ICLR24|FlashAttention-2]] — work partitioning 重设计，A100 attention forward 最高 230 TFLOPs/s
- [[FlashAttention-3-NeurIPS24|FlashAttention-3]] — Hopper TMA/WGMMA warp specialization、GEMM-softmax overlap、FP8，BF16 840 TFLOPs/s
- [[FlashAttention-4-MLSys26|FlashAttention-4]] — Blackwell B200 Tensor Memory 适配，SMEM/exp 与 MMA 同级瓶颈分析
- [[HipKittens-MLSys26|HipKittens]]、[[ParallelKittens-MLSys26|ParallelKittens]]、[[Flashlight-MLSys26|Flashlight]]、[[TritorX-MLSys26|TritorX]] — 新 DSL / 新硬件 kernel 重实现
- [[MAC-Attention-MLSys26|MAC-Attention]]、[[BLASST-MLSys26|BLASST]]、[[SpanQueries-MLSys26|SpanQueries]]、[[IntAttention-MLSys26|IntAttention]] — FA 思想变体（sparse、range-query、integer）
- [[ScaleSearch-MLSys26|ScaleSearchAttention]] — QKᵀ/PV 在 NVFP4 Tensor Core 上无 dequant 执行
- [[DistCA-MLSys26|DistCA]]、[[PIKE-MLSys26|PIKE]]、[[FlashInfer-Bench-MLSys26|FlashInfer-Bench]] — 分布式 attention / bench / 调度
- [[LayeredPrefill-MLSys26|LayeredPrefill]]、[[BatchLLM-MLSys26|BatchLLM]]、[[MorphServe-MLSys26|MorphServe]] — serving 系统复用 FA backend
- [[PipelinedSharding-MLSys26|PipelinedSharding]] — VLMOpt vision encoder 启用 FA + Q-chunking 控 VRAM
- [[StreamDiffusionV2-MLSys26|StreamDiffusionV2]]、[[TiDAR-MLSys26|TiDAR]] — 扩散 / 生成模型调用 FA
- [[GhostServe-MLSys26|GhostServe]] — 对齐 [[Chunked-Prefill]] chunk 级 FA KV parity
- [[FlexiCache-MLSys26|FlexiCache]]、[[OPKV-MLSys26|OPKV]]、[[SkipKV-MLSys26|SkipKV]] — FA 输出端挂载 KV 管理 / importance / eviction
- [[SolidAttention-FAST26|SolidAttention]]、[[NSA-ACL25|NSA]]、[[WAVE-MLSys26|WAVE]] — attention kernel 新变体与 AMD 路径

## 已知局限 / 开放问题

- [[FlashAttention-4-MLSys26]] 主文聚焦 Blackwell training/prefill；decode、[[PagedAttention]]、split-KV inference 路径未同等展开
- FA4 conditional rescaling 与 partial exp emulation 的训练语义影响（FP32 master weight、混合精度 policy）未评估
- cuDNN 合入 FA4 后闭源库与开源实现性能差距缩小，持久 TFLOPs 垄断不再是主要优势（[[FlashAttention-4-MLSys26]] 局限 2）
- 量化 FA（NVFP4/FP8）的 simulator-to-hardware gap 与 LM serving 端到端延迟未报告（[[ScaleSearch-MLSys26]]）
- B300/GB300（MUFU 翻倍）上 exp emulation 比例是否仍最优待重跑 roofline（[[FlashAttention-4-MLSys26]] future work）