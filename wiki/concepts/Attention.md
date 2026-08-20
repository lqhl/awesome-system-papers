---
type: concept
aliases: [attention, Self-Attention, Multi-Head-Attention, MHA]
last_updated: 2026-08-14
tags: [transformer, llm, kernel, sequence-modeling]
---

# Attention

> 注意力机制（attention）让一个 query 根据与 keys 的相关性，对对应 values 做加权汇总。self-attention 的 Q/K/V 来自同一序列，是 Transformer 的核心计算；它同时带来长序列的二次计算、线性增长的 [[KV-Cache]]，以及复杂的 GPU 数据移动和跨设备通信问题。

## 核心思想

常见的 scaled dot-product attention 先计算 `QKᵀ`，按行做 softmax，再乘 `V`。multi-head attention（MHA）把通道分成多个 heads，让不同 heads 学习不同关系；GQA/MQA 让多个 query heads 共享较少的 K/V heads，以减少 KV 容量和 decode 带宽。

训练和 prefill 通常同时处理一段序列。dense attention 对长度为 `L` 的序列计算约 `L²` 个 query-key pairs；causal mask 只隐藏未来位置，不会把数量级降成线性。decode 每步只有新的 query，但仍要读取历史 K/V，所以单步计算和读量随已有 context 线性增长，缓存总量也随序列长度增长。

系统优化主要沿四条路线展开：

- 保持 dense exact 语义，减少中间结果和 HBM I/O，例如 [[Flash-Attention]]。
- 用 [[Sparse-Attention|稀疏注意力]] 只选择部分历史 token，减少真正计算的 pairs。
- 对 KV 做分页、压缩、分层或卸载，扩大可服务 context 和并发。
- 重排 tile、通信和设备分工，让 attention 与其他算子或跨卡传输重叠。

## 为什么重要

[[Transformer-NeurIPS17]] 用 self-attention 取代循环结构，缩短了长距离依赖路径，也大幅提高训练并行性。模型规模和 context 增长后，attention 又成为系统的主要约束之一：prefill 受计算和中间 I/O 影响，decode 受历史 KV 带宽影响，长上下文训练还会受跨卡负载不均和通信影响。

OSDI 2026 的论文说明优化已经越过单个 kernel：[[Twill-OSDI26]] 求解软件流水和 warp 分工；[[DirectKV-OSDI26]] 让 kernel 直接读 CPU-resident KV；[[ECHO-OSDI26]] 把原生稀疏模型的完整 KV 放到 host；[[Syncopate-OSDI26]] 自动重叠多 GPU attention 的计算和通信；[[MPK-OSDI26]] 则把 attention tasks 放进整图 persistent mega-kernel。

## 关键观察 / 隐含假设

- **算 FLOPs 不足以预测性能。** [[FlashAttention-NeurIPS22]] 保持完全相同的 dense attention，却通过 tile 和 online softmax 不物化完整 score matrix，从而显著减少 HBM 访问。这证明数据移动和片上容量与计算量同样重要。
- **decode 的核心常是 KV 带宽和容量。** [[DirectKV-OSDI26]] 在 GH200 上改变 tile 循环，让 CPU-resident KV 尽量停留在 SMEM，并把 projection 与 attention 融合。收益依赖 NVLink-C2C；同一路径在 PCIe 上主要是容量扩展，不能当作通用低延迟方案。
- **稀疏计算不会自动删除完整历史状态。** [[ECHO-OSDI26]] 面向原生 sparse attention，仍在约 1 TB host DRAM 中保留 1.8M-token pool，再把 exact top-k 所需 KV 召回 GPU。其“无损”指预取不改变最终 top-k，不表示系统没有额外资源或延迟。
- **选择规则和存储布局必须共同设计。** [[SolidAttention-FAST26]] 用层间选择相似性预取 SSD KV，[[IceCache-arXiv26]] 按语义相关性重排 page；若 token 选择很分散，理论稀疏度会变成随机 I/O 和 metadata 开销。
- **最新硬件会改变最佳流水。** [[Twill-OSDI26]] 自动恢复 FA3/FA4 的高层策略，但实验仅覆盖固定 FP16 non-causal attention shape，且高性能 CUDA 仍由作者手工翻译。它证明约束模型能表达这类 schedule，不等于任意 attention 都能自动达到最优。
- **空间加速器需要显式放置与通信。** [[TileLoom-OSDI26]] 在 Tenstorrent 两代芯片上自动规划 tile，FlashAttention 超过 vendor TTNN；FlashDecode 却仍低于 TTNN。收益取决于算力/带宽比例和 kernel 形态，而非编译方法无条件占优。
- **多 GPU attention 是负载均衡问题，也是通信问题。** [[Syncopate-OSDI26]] 在已有通信计划上重排 chunk/tile，operator 平均加速 1.3 倍；[[DCP-SOSP25]] 用动态 context partition 处理不同序列和 mask 的工作量；[[DistCA-MLSys26]] 甚至把 core attention 调度到独立 server pool。三者的边界分别是单机 H100 operator、长上下文训练和大规模 H200 训练。
- **attention score 不一定等于可解释因果。** [[PASTA-ICLR24]] 能重加权少数 heads 来引导指定 span，但依赖外部正确标注；这证明 attention 可被操控，不证明原始权重就是模型推理过程的忠实解释。
- **模型语义变化可能比 kernel 优化更大，也更冒险。** [[NSA-ACL25]]、[[MAC-Attention-MLSys26]]、[[MSA-arXiv26]] 和 [[DeepSeek-V4-arXiv26]] 分别使用原生稀疏、摘要复用、记忆稀疏和混合压缩。它们改变被访问 token 或模型训练，不能与 exact dense kernel 只按速度直接比较。

## 设计空间与取舍

- **dense exact、sparse exact 或 approximate**：dense 最容易保持原模型语义；sparse 需要索引和不规则读取；approximate 可进一步省计算，但要报告任务质量和失败输入。
- **MHA、GQA 或 MQA**：共享 K/V heads 能显著减小 cache；表达能力、训练方式和 kernel shape 也随之改变。
- **GPU resident、host tier 或 SSD tier**：越远容量越大、延迟和故障面也越大。prefetch 准确率、传输粒度和请求并发共同决定是否划算。
- **kernel fusion 或模块化算子**：fusion 减少中间写回和 launch，代码组合数与验证成本快速增加；模块化更容易复用、调试和选择不同后端。
- **单卡、context parallel 或 attention offload**：分片能处理更长序列，也会传 Q/KV/output。[[Weaver-ATC25]] 借冷模型 GPU 做 attention offload，利用率提高的同时要控制对 cold workload 的 head-of-line blocking。
- **静态或动态 schedule**：固定 shape 可深度优化；ragged batch、动态 sparsity 和 continuous batching 更需要 runtime 调度，固定最优 tile 未必复用。
- **只优化 attention 或联合全模型**：attention 加速后，FFN、collective、scheduler 或 KV I/O 可能成为新瓶颈。[[BatchGen-OSDI26]] 在 attention–MoE 边界重组离线 batch，就是改变全模型执行抽象而非单核加速。

## 引用本概念的论文

### 定义、dense kernel 与编译

- [[KernelEvolve-ISCA26]]：跨 NVIDIA、AMD 和 MTIA 搜索生产内核，Llama-3.1-8B vanilla attention 相对 PyTorch 加速 4.6 倍；基线不是对应平台的最强专家内核。
- [[HarnessEngineering-arXiv26]]：在 B200 的 DSA sparse attention 上用脚手架约束智能体搜索，平均延迟相对供应 FlashInfer 基线加速 29.68 倍；结果来自竞赛形状，不能外推到完整推理服务。
- [[Transformer-NeurIPS17]]：建立 self-attention Transformer 的原始模型语境。
- [[FlashAttention-NeurIPS22]]、[[FlashAttention-2-ICLR24]]、[[FlashAttention-3-NeurIPS24]]、[[FlashAttention-4-MLSys26]]：展示 exact dense attention 如何随 GPU I/O、work partition 和异步流水演进。
- [[Twill-OSDI26]]、[[TileLoom-OSDI26]]、[[Flashlight-MLSys26]]、[[WAVE-MLSys26]]：分别从约束求解、空间 dataflow、PyTorch 编译和符号 DSL 生成 attention kernel。
- [[MPK-OSDI26]]、[[KPerfIR-OSDI25]]：把 attention 放入 mega-kernel 或 compiler-centric profiling；MPK 的主要性能证据是固定离线 batch。

### 长上下文、稀疏和 KV

- [[DirectKV-OSDI26]]、[[ECHO-OSDI26]]、[[Strata-OSDI26]]：分别处理 CPU 直接访问、原生稀疏 KV offload 和分层缓存加载。
- [[NSA-ACL25]]、[[SolidAttention-FAST26]]、[[IceCache-arXiv26]]、[[MAC-Attention-MLSys26]]：选择部分历史 token 或复用摘要，并共同设计索引、page 或预取。
- [[CacheBlend-EuroSys25]]、[[SpanQueries-MLSys26]]：通过 selective recompute 或可交换 span 改变需要重新计算的 attention。
- [[MSA-arXiv26]]、[[DeepSeek-V4-arXiv26]]、[[AttnRes-arXiv26]]：从模型结构扩展 memory attention、混合长上下文或深度 residual attention，证据不能简化为 kernel 性能。

### 分布式、可靠性与邻接使用

- [[Syncopate-OSDI26]]、[[DCP-SOSP25]]、[[DistCA-MLSys26]]、[[Weaver-ATC25]]：研究多 GPU 通信重叠、context partition、core-attention 分离和跨模型 offload。
- [[AEGIS-OSDI26]]：利用 softmax 不变量与 FlashAttention 重计算检测训练 SDC；这是可靠性机制，不是 attention 加速。
- [[StriaTrace-OSDI26]]：生产案例定位到错误 FlashAttention tile build，说明 kernel 配置和可观测性会影响线上尾延迟。
- [[KAIROX-OSDI26]] 用 attention 后的信号预测下一层 FFN 神经元，[[Tessera-OSDI26]] 在异构 MoE pipeline 中安排 attention/通信，[[RobustRL-OSDI26]] 只把 FlashAttention 非确定性当作训练对齐边界；这些引用不构成新的 attention 算法证据。
- [[ADAngel-OSDI26]]、[[Prism-OSDI26]]、[[VTC-OSDI26]]、[[OpGuard-OSDI26]]、[[DCP-OSDI26]]、[[Alibaba-ASI-OSDI26]] 等页主要在系统上下文或相关概念中引用 attention，不能把它们全部归为 attention 论文。

## 已知局限 / 开放问题

- dense、sparse、量化和分层 KV 目前常各自选择不同 layout；缺少能在动态 workload 下低成本切换的统一表示。
- 新模型结构的质量证据应覆盖训练分布外、长上下文边界和 adversarial retrieval，不应只报平均 benchmark。
- kernel microbenchmark 的最优点未必给出线上最佳 TTFT/TPOT；还需纳入 scheduler、KV load、batch raggedness 和低负载能耗。
- 多 GPU 系统需要同时处理不均匀序列、通信拥塞、故障和重分片；均衡 FLOPs 不等于均衡完成时间。
- fusion、低精度和异步执行扩大数值与 SDC 验证面。应报告误差、确定性、故障检测和 fallback，而不只报告 TFLOPs。
