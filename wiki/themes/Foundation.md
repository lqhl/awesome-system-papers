---
type: theme
topic: Foundation
theme_kind: lens
member_tag: lens/foundation
paper_count: 7
first_generated: 2026-04-24
last_updated: 2026-08-18
tags: [topic-overview, foundation, milestones]
---

# Foundation 综述

> 本 topic 收录 7 篇开创性/里程碑工作，构成「定义架构 → 定义 attention kernel → 定义 LLM serving 栈 → 定义能力边界」的 milestone 链：**[[Transformer-NeurIPS17|Transformer 2017]]** 定义架构；**[[FlashAttention-NeurIPS22|FlashAttention]] / [[FlashAttention-2-ICLR24|FA2]] / [[FlashAttention-3-NeurIPS24|FA3]]** 定义 exact attention 的系统实现范式；**[[vLLM-SOSP23|vLLM]] + [[SGLang-NeurIPS24|SGLang]]** 定义通用 serving 与 structured program serving 两条路线；**[[DeepSeek-V4-arXiv26|DeepSeek-V4]]** 给出 2026 开源 frontier baseline。

## 核心论文

### 架构基石（1 篇）

- [[Transformer-NeurIPS17|Attention Is All You Need]] — 完全基于 self-attention 的 Transformer，WMT 2014 EN-DE 28.4 BLEU；Multi-Head + Scaled Dot-Product + 正余弦位置编码，现代 LLM 共同祖先

### Attention Kernel 基础设施（3 篇）

- [[FlashAttention-NeurIPS22|FlashAttention]] — IO-aware tiling + online softmax + backward recomputation，避免物化 `N×N` attention matrix；A100 attention 最高 7.6× 加速
- [[FlashAttention-2-ICLR24|FlashAttention-2]] — 沿 sequence length 并行 + warp 内 split-Q，A100 forward 最高 230 TFLOPs/s
- [[FlashAttention-3-NeurIPS24|FlashAttention-3]] — Hopper TMA/WGMMA warp specialization + GEMM-softmax overlap + FP8；H100 BF16 最高 840 TFLOPs/s

### LLM Serving 基础设施（2 篇）

- [[vLLM-SOSP23|vLLM / PagedAttention]] — [[KV-Cache]] 虚存分页：block table + on-demand 分配 + copy-on-write 前缀共享；LLM serving 事实标准 baseline
- [[SGLang-NeurIPS24|SGLang]] — LM Program DSL + **RadixAttention** 跨调用 prefix 共享 + compressed FSM；相对 vLLM v0.2.5 吞吐最高 6.4×

### 开源 Frontier 综合（1 篇）

- [[DeepSeek-V4-arXiv26|DeepSeek-V4]] — 1.6T [[MoE]]（49B 激活）、1M context；CSA+HCA 混合注意力把 1M FLOPs/KV 压到 V3.2 的 27%/10%；Muon + mHC + FP4 QAT

## 主题综述

### 一条 9 年的架构传承线

从 [[Transformer-NeurIPS17|Transformer]] 到 [[DeepSeek-V4-arXiv26|DeepSeek-V4]]，**主干仍是 stacked self-attention + FFN + residual + LayerNorm**，但每个组件被重做：FFN 从 dense 到 [[MoE]]；attention 从 $O(n^2)$ dense 到 [[FlashAttention-NeurIPS22|FA]] 系列 exact kernel 再到 CSA/HCA 压缩稀疏；位置编码从正余弦到 partial RoPE + attention sink；残差从固定 1.0 到 mHC/[[AttnRes-arXiv26|AttnRes]] 的可学习聚合。

### Attention kernel 的三代瓶颈迁移

[[FlashAttention-NeurIPS22|FA1]] 解决 HBM 物化 $N×N$ 中间态；[[FlashAttention-2-ICLR24|FA2]] 在 FA1 已 IO-efficient 后，把瓶颈推进到 thread-block/warp 分工与 sequence-parallel occupancy；[[FlashAttention-3-NeurIPS24|FA3]] 则面对 Hopper 上 **softmax/exp 与 matmul 的 256× 吞吐差**，用 producer-consumer warp 重叠与 FP8 重排算法形状。三代共同假设：**exact attention 仍值得优化**——与 [[NSA-ACL25|NSA]] 等稀疏路线形成对照。

### Serving 栈分叉：通用引擎 vs 程序感知 runtime

[[vLLM-SOSP23|vLLM]] 把每次 generation 当独立请求，用 [[PagedAttention]] 解决 KV 碎片与共享；[[SGLang-NeurIPS24|SGLang]] 则假设 **LM Program 产生 50-99% prefix 重叠**，用 radix tree 跨调用复用 KV，并用 compressed FSM 跳过确定性多 token 路径。分叉本质是：workload 结构是否暴露给 runtime。vLLM 后续也加入 prefix caching，但 SGLang 的 cache-aware scheduling 与 fork hint 仍是程序感知路线的代表。

### DeepSeek-V4：系统工程承载能力指数增长

[[Transformer-NeurIPS17|Transformer]] 用 8×P100 训 65M-213M 参数；[[DeepSeek-V4-arXiv26|DeepSeek-V4]] 用 33T tokens 训 1.6T 参数，Infrastructure 单独成章（EP mega-kernel、TileLang、FP4 QAT、DSec）。算法进步相对缓慢，**系统实现与硬件协同**成为 frontier 竞争主战场。

## 共同观察

**1. Attention 的瓶颈随 workload 形状在 IO、compute scheduling、memory bandwidth 间迁移。** [[FlashAttention-NeurIPS22|FA1]] 假设物化 attention matrix 是 HBM 主敌；[[FlashAttention-2-ICLR24|FA2]] 假设 FA1 之后 occupancy 与 non-matmul FLOPs 主导；[[FlashAttention-3-NeurIPS24|FA3]] 假设 Hopper 上 exponential 可占 ~50% cycle；[[DeepSeek-V4-arXiv26|DeepSeek-V4]] 假设 1M context 下 attention 同时主导 FLOPs 与 KV，需算法层压缩。**适用边界**：decode 阶段 query 极短（1-几 token）时，FA3 的 sequence-parallel 收益有限，应走 [[PagedAttention]]/split-KV 路径（FA3 Critical Analysis 已承认）。

**2. [[KV-Cache]] 管理是 serving 的核心抽象，但「谁拥有复用语义」决定系统形态。** [[vLLM-SOSP23|vLLM]] 假设 block-table 分页 + on-demand 分配即可服务绝大多数请求；[[SGLang-NeurIPS24|SGLang]] 假设跨调用 prefix 局部性足够强，值得维护 radix tree 与 cache-aware 调度。**适用边界**：短序列、KV 充裕、compute-bound 时 [[vLLM-SOSP23|vLLM]] 优势缩小；tenant 无关、长输出 chat 时 SGLang cache hit rate 接近零。

**3. Exact attention 在 2017-2026 仍是默认，稀疏/压缩是叠加而非替代。** [[Transformer-NeurIPS17|Transformer]] 的 $O(n^2)$ 在 long context 下成为主矛盾，但 [[FlashAttention-NeurIPS22|FA]] 系列选择保持 exact 语义优化实现；[[DeepSeek-V4-arXiv26|DeepSeek-V4]] 用 CSA/HCA 在算法层压缩 yet 仍保留 Transformer 骨架。**适用边界**：需要完整 attention map（可视化/蒸馏）或精确远距离单 token 访问时，压缩块内因果受限（V4 Critical Analysis 已指出）。

**4. Foundation 工作的价值在于跨时间锚定，而非技术集群归类。** 做 kernel 优化读 FA 三代；做 KV 管理读 Transformer + vLLM + SGLang；做 1M context 读 DeepSeek-V4 对 CSA/HCA 的权衡——这与 [[AI-Infra]] 等专题的「当前热点聚类」互补。

## 假设冲突与脆弱点

**1. Serving 默认：请求独立 vs 程序感知复用。** [[vLLM-SOSP23|vLLM]] 假设 continuous batching + paged KV 是通用解；[[SGLang-NeurIPS24|SGLang]] 假设 LM Program 的 fork/prefix 结构应一等公民化，且 cache 与 running request 共用 pool 时 waiting queue 大可 evict 全部 cache 换 batch。**脆弱点**：高 churn 短 prompt 下 radix tree 维护开销；公平性——最长前缀优先可能饿死冷启动请求（SGLang 明确留作 future work）。需在同一 agent/RAG trace 上对比 vLLM prefix caching vs SGLang RadixAttention 的 hit rate 与 P99。

**2. Attention 优化路径：IO-aware exact kernel vs 算法层稀疏压缩。** [[FlashAttention-3-NeurIPS24|FA3]] 假设 prefill/training 仍以 dense exact attention 为主战场；[[DeepSeek-V4-arXiv26|DeepSeek-V4]] 假设 1M context 必须 CSA+HCA 压缩才有可行 FLOPs/KV。**脆弱点**：64K 以下 context、短输出 decode 时 FA 路径更优；needle-in-haystack 变体上 V4 压缩块因果受限。需在相同模型规模上测「FA-only serving」vs「V4-style CSA+HCA」的质量-延迟-内存三维权衡。

**3. PagedAttention 收益假设：memory-bound 程度决定一切。** [[vLLM-SOSP23|vLLM]] Critical Analysis 指出 OPT-175B + Alpaca 短序列上 Orca Oracle 也能批很多请求，PagedAttention 优势缩小——隐含假设是 **KV 压力足够大**。**脆弱点**：prefill-heavy、多模态、[[MoE]] 等让非 KV 瓶颈主导时，分页抽象的收益被低估；与 [[SGLang-NeurIPS24|SGLang]] 的「cache 与 batch 互斥」形成对照——两者对显存分配优先级相反。

**4. Transformer 原始假设 $n \ll d$ 在 modern LLM 中普遍失效。** [[Transformer-NeurIPS17|Transformer]] 设计时序列长度小于维度；当今 4K-1M context 使 $O(n^2)$ 成为系统主矛盾。**脆弱点**：FA 系列、chunked prefill、sparse pattern 都是对此的补丁，但 foundation 论文的 scaling law 直觉（参数量 vs 数据量）仍被 [[DeepSeek-V4-arXiv26|DeepSeek-V4]] 继承——**架构不变、工程量级指数变**。

## 值得关注的方向

### 1. 从 Transformer 2017 起跳，找 DeepSeek-V4 未做完的空白

**为什么小团队能做**：对照 foundation 论文 delta 即可定位未工程化空档。

**指向空白的论文**：[[Transformer-NeurIPS17|Transformer]] 的 local/restricted attention 与 multimodal 扩展；[[DeepSeek-V4-arXiv26|DeepSeek-V4]] 仅在 text 上做 1M context。

**具体 open problems**：restricted attention 的 $O(r·n·d)$ 如何与 CSA+HCA 细粒度组合；RoPE/ALiBi/mHC 在 1M 尺度的外推边界。

### 2. Foundation 级工作的可复现 benchmark 化

**为什么小团队能做**：读懂 foundation、复现关键结果、构建对比 benchmark 是典型学术原型工作。

**指向空白的论文**：[[DeepSeek-V4-arXiv26|DeepSeek-V4]] 完整训练不可复现，但 mHC/CSA/HCA 可用 1B-10B 压缩版验证；[[Transformer-NeurIPS17|Transformer]] Table 3 的严格 ablation 在 frontier 论文中越来越稀有。

**具体 open problems**：mHC 相对普通残差的质量增益对照；CSA vs HCA 最优混合比例；FP4 QAT 在非 DeepSeek 架构上的无损深度。

### 3. 把 foundation 方法反向投射到小模型

**为什么小团队能做**：Muon、mHC、CSA、OPD 等可单独在 1-8B 上验证。

**指向空白的论文**：[[DeepSeek-V4-arXiv26|DeepSeek-V4]] 的 Muon/OPD 规模效应未在小模型上拆解。

**具体 open problems**：Muon Newton-Schulz 系数 task-adaptive；2-3 teacher 简化版 OPD；mHC 约束在小模型上是否可放松。

### 4. FA 三代 + PagedAttention 的 inference decode 统一叙事

**为什么小团队能做**：单卡 H100/A100 即可 microbench FA kernel 与 paged KV load 的重叠。

**指向空白的论文**：[[FlashAttention-3-NeurIPS24|FA3]] 明确 decode 短 query 应走其他路径；[[vLLM-SOSP23|vLLM]] 与 [[SGLang-NeurIPS24|SGLang]] 的集成假设不同。

**具体 open problems**：prefill 用 FA3、decode 用 split-KV 的流水线分界点；radix cache 与 paged block 的统一内存池设计。
