---
type: concept
aliases: [sparse attention, Sparse Attention, sparse-attention, Attention Sparsity, attention sparsity, Block-Sparse-Attention, block sparse attention]
parent: "[[Attention]]"
last_updated: 2026-08-14
tags: [attention, long-context, efficiency, llm-inference, llm-training]
---

# 稀疏注意力（Sparse Attention）

> 稀疏注意力让每个 query 只计算或读取一部分 key/value。它可以降低长上下文的计算和 KV 带宽，但只有当“选谁、搬谁、怎样批处理”的成本也足够低时，理论稀疏率才会变成端到端加速。

## 先分清四件事

稀疏注意力常与其他优化混在一起，评价前应先区分：

1. **精确 dense attention 的高效实现**：仍计算所有有效 query–key 对，只减少中间读写，例如 [[Flash-Attention]]。它是稀疏方案必须比较的强基线，本身不是稀疏语义。
2. **原生稀疏模型**：训练时就使用压缩、窗口、top-k 或路由结构，模型学会在这个结构内工作，例如 [[NSA-ACL25]]、[[DeepSeek-V4-arXiv26]]。
3. **推理时稀疏化**：对原本 dense 的模型动态选择 token/page 或跳过低贡献 block，例如 [[BLASST-MLSys26]]、[[FlexiCache-MLSys26]]。它更容易部署，但通常是近似执行。
4. **KV 管理或重用**：可能只把一部分 KV 驻留 GPU、从 host/SSD 召回，或只重算部分 token。它能利用 attention 的访问偏斜，却不一定改变模型实际计算的 attention 集合。

这四类可以组合，但数字不能直接相乘。一个系统报告“KV 少 70%”不等于 attention kernel 快 70%；一个 kernel 报“跳过 75% block”也不等于在线吞吐提高 4 倍。

## 为什么长上下文需要它

原始 Transformer 的每层 dense self-attention 需要 (O(N^2)) 个 query–key pair。[[Transformer-NeurIPS17]] 在句子级机器翻译中接受这项成本，以换取 (O(1)) 的依赖路径和高度并行的矩阵乘；论文已把 restricted attention 列为后续方向，但没有实现稀疏模型。

生成时可以缓存历史 key/value，因此每个 decode step 的算术量近似随上下文 (N) 线性增长，整段生成仍会累积很大成本。更直接的问题是每一步都要读长 KV，decode 常受内存带宽限制。稀疏注意力试图把每步读取和计算从 (N) 降到预算 (k\ll N)，但多出 selector、索引、metadata、非连续 I/O 和不规则 kernel。

[[FlashAttention-NeurIPS22]] 说明只优化 I/O 就能在不改语义的情况下显著加速 dense attention；它的 block-sparse 扩展用固定 butterfly mask，在 LRA 上得到 2.8 倍 attention 加速且精度相近。这个结果证明“稀疏 block 能与 IO-aware kernel 结合”，但没有覆盖 learned/dynamic sparsity、在线调度和尾延迟。

## 稀疏模式从哪里来

### 固定窗口、固定 mask 与 block 稀疏

固定 local window、global token 或规则化 block mask 最容易做成连续访存和静态 kernel；代价是不能随输入内容选择远端证据。块越大，GPU 越高效，但会多算块内无关 token；块越小，选择精细，却更容易被索引和随机 I/O 吞掉。

[[db-SP-MLSys26]] 展示了稀疏 block 到多 GPU 后的新问题：视频 DiT 的不同 head 稀疏度和 dense-block 分布不均，传统 Ulysses/Ring 会产生 straggler。它用 head 级和 block 级两层 greedy 划分，再在线选择并行策略，在 8×A800 上相对所用 SOTA sequence-parallel baseline 把 attention 提高 1.40 倍、端到端提高 1.25 倍。结论面向视觉生成，且依赖跨 denoising step/layer 的 mask 相似性。

### 原生可训练的稀疏结构

[[NSA-ACL25]] 用三条分支覆盖不同依赖：压缩分支保存全局摘要，top-k block selection 保留精细远端 token，滑动窗口处理局部上下文；同一 GQA group 共享 block 选择，避免多个 query heads 的 KV union 把真实读取量重新放大。它在一个 27B total/3B active MoE 模型上报告 64K context 的 forward/backward 加速 9.0/6.0 倍，并给出 11.6 倍 decode 估计。后一个数字主要来自等效 KV 读取量和 memory-bound 假设，不是完整 serving engine 的 TTFT/TPOT 实测。

[[DeepSeek-V4-arXiv26]] 进一步把压缩稀疏注意力（CSA）和分层压缩注意力混合：每 4 个 token 压成一个 KV entry，再用轻量 indexer 选择 top-k 压缩块，并以 128-token 滑窗保护近端信息。论文在 1M token 下报告单 token FLOPs 为 V3.2 的 27%、KV 为 10%，但 MRCR 1M 仍低于所列闭源强模型，说明“能运行 1M”不等于“对所有 1M 检索都无损”。selector 的 99.7% KV recall 也不是 100% 任务正确率。

[[MSA-arXiv26]] 把 retrieval 放进后半层 attention：document-wise 位置编码、chunk-wise KV 压缩和可训练选择把 64K 训练外推到 100M-token memory。论文在两块 A800 上跑通 100M token，并报告 MS MARCO 从 16K 扩到 100M 时性能只降 8.8%。这是特定 memory/RAG 架构的结果，不代表普通 dense LLM 只改 kernel 就能获得同样容量。

原生路线的优点是训练能适应稀疏语义，缺点是需要从头预训练或长期 continued training，不能透明替换既有 dense checkpoint。离散 top-k 仍会造成未选 block 梯度缺失；“可训练”不等于优化目标处处平滑。

### 推理时按内容选择或跳过

[[BLASST-MLSys26]] 不先训练 selector，也不额外计算 proxy score；它在 FlashAttention online softmax 中比较 running max 与当前 block max，满足阈值时跳过整块 exp、V 读取和 MMA，并让阈值随序列长度调整。在其测试中，prefill/decode 稀疏率为 74.7%/73.2%，对应 1.62/1.48 倍加速。它仍是阈值近似，极端 attention 分布可能掉点；生产 scheduler 和尾延迟未覆盖。

[[MAC-Attention-MLSys26]] 利用同一 decode stream 中相邻 query 的语义重复：在 pre-RoPE 空间找历史相似 query，复用其 prefix attention summary，只重算匹配边界和新 tail，再在 log domain 合并。高命中长生成中，128K 的 KV 读取最多减少 99%，attention 至少快 14.3 倍，LLaMA 端到端最高 2.6 倍；32K、小 batch、低 skip ratio 时固定成本可反超 dense baseline。其超过 99% hit 主要来自 LongGenBench/长生成类工作负载，不能外推到所有检索请求。

[[SparseSpec-MLSys26]] 让目标模型在精确验证时产生 attention score，用它指导下一轮稀疏 self-draft，再配合统一调度、延迟验证和 KV offload。相对 [[vLLM]] 的最高吞吐为 2.13 倍，相对 MagicDec/TriForce 最高为 1.36/1.76 倍。方法假设相邻轮次的 attention pattern 有局部稳定性，且主结果没有生产 trace、P99 或多租户评测。

## 稀疏 attention 与 KV 放置必须一起设计

### 原生稀疏模型：完整 KV 可以放到 host

原生 selector 必须能访问完整 key 或其索引，选中后还要把对应 KV 送给 GPU。[[ECHO-OSDI26]] 把完整 KV 备份在约 1 TB host pool，GPU 只保留当前选中的 token；上一轮阈值和 prefill query block 的 score histogram只用于**提前搬运**，最终仍做模型定义的 exact top-k，并补拉所有 miss。因此其“无损”是相对这个原生稀疏模型的 top-k 语义，不是相对 dense attention。

ECHO 在单台 8×H20、1.8M-token host pool 的固定输出实验中，吞吐最高达到 [[SGLang]] 的 2.15 倍、[[vLLM]] 的 4.1 倍。主要收益来自 host 容量允许更高并发；intra-query prefetch 对端到端最多贡献 4%，inter-query 只给了最高 1.1 倍 microbenchmark。低负载、短 context 或 host/NUMA 带宽被共享时，15.9%–19.2% 端到端管理开销可能不值得。

### Dense 模型：保留全量 KV，动态决定驻留

[[FlexiCache-MLSys26]] 先按 head 的 top-k page 集合稳定性分类。稳定 head 只在 GPU 留 top-k，其余放 host，每 16 步重排并只拉 promoted 差集；不稳定 head 的全量 KV 留 GPU。它在 [[vLLM]] 上最高省 70% GPU KV，离线吞吐提高 1.38–1.55 倍，在线 mean TPOT 降到原来的 1/1.6–1/2.1，并在 LongBench/L-Eval 保留约 99% dense 分数。稳定 head 的全局 75% 比例、16 步周期和固定 token budget 都是经验设置；论文没有 P99 TPOT 和 attention 突变时的质量守卫。

[[IceCache-arXiv26]] 认为顺序 page 会把相关 token 打散，于是按 key embedding 的近邻关系建 per-head DCI tree，把语义相关 token 放在同一 page，再用 ANN 找 top-k page。36K context 下总 TPOT 约 0.11 秒，其中 DCI query 约 0.05 秒，已经超过 PCIe loading 的约 0.015 秒；这清楚表明 selector 会成为新瓶颈。256-token budget 在其 LongBench 设置中约保留 99% Full KV 结果，但 ANN 漏掉关键 page 时没有在线检测或 dense fallback。

[[OPKV-MLSys26]] 不发明新的稀疏算法，而是给 token-granularity 的 recallable sparsity 做 page/cache substrate：OP Block 聚合零散 token、hot page 复用、Sub Block Manager 降低内部浪费。在单卡、batch 2–10 的 [[vLLM]] 实验中，它让 InfiniGen/OmniKV 的 decode 吞吐提高 1.3–1.8 倍。Python page retrieval 和 GIL 在高 batch 仍是线性瓶颈，质量主要继承上层稀疏算法，论文没有系统量化额外召回对质量的影响。

### SSD：访问粒度比稀疏率更重要

[[SolidAttention-FAST26]] 面向 8–16 GB DRAM、6–8 GB VRAM、batch 1 的 PC。它把 KV 按 32-token block 选择，并交错 K/V 形成适合 SSD 的大传输块；利用相邻层选择约 81% 相似做 speculative prefetch，再用 DAG microtask 重叠 I/O 与计算。128K context 下相对其基线最高快 3.1 倍，KV 内存降到 2%，评测质量接近全内存 baseline。结果依赖 LongBench 上的层间稳定性、单请求和固定 1K token budget；SSD 有 4 GB/s 背景读取时吞吐会降 58%。

## 相邻机制，不应混成同一种稀疏

- [[CacheBlend-EuroSys25]] 和 [[CacheSlide-FAST26]] 只重算高 KV 偏差 token，用于修复非前缀 cache reuse 的 cross-attention。它们稀疏的是**重计算集合**，不是普通 decode 中每个 query 的 attention mask；2.2–3.3 倍或 3.11–4.3 倍延迟收益不能写成稀疏 attention kernel 加速。
- [[SpanQueries-MLSys26]] 用声明式 span IR 表达输入块是否可交换，并利用 map-reduce 式 attention locality。其 10–20 倍 TTFT 降低主要来自 KV 复用和输入语义，不是通用 top-k attention。
- [[MoE-nD-arXiv26]] 对现有 dense 模型逐层选择 KV eviction 与 K/V bit-width。14 倍 cache 压缩来自 eviction+quantization 路由，论文没有端到端 TTFT/TPOT；它应与稀疏注意力对比，而非视为同一架构。
- [[Jenga-ATC25]] 稀疏的是长上下文微调中的 token activation，目标是降低反向激活；把这种 pattern 蒸馏到 inference sparse attention 只是后续方向。
- [[ASI-ARCH-arXiv25]] 在 linear attention 等架构空间做自动研究，未给 discovered models 的推理 kernel 或服务效率；其 1,773 次实验不能作为稀疏 attention 运行时证据。

## 正确性词汇要精确

| 说法 | 实际含义 | 不能推出什么 |
|---|---|---|
| exact dense | 计算 dense 模型定义的全部有效 pair | 不代表实现最快 |
| native sparse | 模型从训练起就按稀疏结构定义输出 | 不等于 dense checkpoint 的输出 |
| exact top-k recall | 没漏掉稀疏模型 selector 最终选中的 KV | 不等于 dense attention 无损 |
| quality retained | 指定 benchmark 分数接近 baseline | 不等于逐 token 或分布等价 |
| prefetch lossless | 预测错只增加等待/流量，最终会补拉 | 不表示 selector 自身没有近似误差 |

## 设计空间

| 选择 | 优点 | 主要代价 | 代表论文 |
|---|---|---|---|
| 固定 block/window | 规则、易并行、I/O 连续 | 难适应内容相关远端依赖 | [[FlashAttention-NeurIPS22]] |
| 原生压缩+选择+窗口 | 训练和服务语义一致 | 需要重训，selector 有离散边界 | [[NSA-ACL25]]、[[DeepSeek-V4-arXiv26]] |
| 在线阈值跳块 | 无额外 proxy 模型 | 近似质量与动态分支 | [[BLASST-MLSys26]] |
| query summary 复用 | 高命中时几乎不读旧 KV | 依赖时间局部性，miss 有固定开销 | [[MAC-Attention-MLSys26]] |
| host 保全量、GPU 留选中集 | 容量大，可召回 | CPU/PCIe/NUMA 和 metadata | [[ECHO-OSDI26]]、[[FlexiCache-MLSys26]] |
| 语义 page+ANN | page 纯度高、query-aware | 索引可能成为主导且有 silent miss | [[IceCache-arXiv26]] |
| SSD block co-design | 适合内存很小的单用户 PC | 粗粒度、多毫秒 I/O、争用敏感 | [[SolidAttention-FAST26]] |
| 稀疏序列并行 | 扩到多 GPU/视觉生成 | mask 不均造成双层负载失衡 | [[db-SP-MLSys26]] |

## 评价稀疏注意力论文时应看什么

1. 先写清是原生稀疏模型、dense 模型的推理近似、KV 放置，还是只做 selective recompute。
2. 同时报告实际 selected token/page 比例、selector/index 时间、KV 字节、kernel 时间和端到端 TTFT/TPOT/吞吐。
3. 与同硬件上的最新 exact IO-aware dense kernel 比较，并把 prefill、decode、batch 和序列长度分开。
4. 质量评测不能只用 needle retrieval；还需代码、数学、长生成、多文档、位置变化和分布外输入，并给出失败样例。
5. GQA/MQA 要按共享 KV group 计算真实 union 读取量；多 GPU 要报告稀疏 mask 引起的负载不均和通信。
6. Offload 方案要报告 CPU/DRAM/PCIe/SSD 争用、P95/P99、page hit、misprefetch、故障和 fallback。
7. “无损”必须注明相对 dense 模型、原生 sparse top-k，还是仅指 prefetch 不改变上层选择。

## 仍未解决的问题

- 用在线风险估计动态扩大预算或回退 dense，并能检测“输出流畅但漏掉关键证据”的 silent failure。
- 把 selector、page layout、prefetch、kernel 和 continuous batching放进同一个优化器，而不是各自选固定超参。
- 在多租户、NUMA、跨节点和存储争用下稳定控制尾延迟，并提供每请求质量/成本配额。
- 让原生稀疏模型的训练 pattern 与 serving block/page abstraction 对齐，避免训练 FLOPs 降了、真实 I/O 没降。
- 建立统一 benchmark，区分 attention 算法、KV 管理、缓存重用和硬件并行各自贡献。
