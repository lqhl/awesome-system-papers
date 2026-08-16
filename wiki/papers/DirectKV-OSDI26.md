---
type: paper
name: DirectKV
full_title: "No Buffer, No Bottleneck: Efficient Zero-Copy KV Cache Offloading for Long-Context LLMs"
authors: [Shutian Luo, Haiying Shen]
venue: OSDI
year: 2026
tags: [llm-serving, kv-cache, zero-copy, cpu-gpu-memory, nvlink-c2c]
source_pdf: "[[osdi26-luo.pdf]]"
source_md: "[[osdi26-luo]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# DirectKV：长上下文 LLM 的零拷贝 KV Cache 卸载

> **原题**：No Buffer, No Bottleneck: Efficient Zero-Copy KV Cache Offloading for Long-Context LLMs

> **一句话总结**：DirectKV 发现 NVLink-C2C 虽让 GPU 直接读 CPU 内存成为可能，朴素 zero-copy 仍会重复拉取 KV；它用 CPU-memory-aware tiling、warp pipeline 和投影—Attention 融合去掉 HBM staging buffer，在 GH200 上把 GPU 内存降到 47 GB、比其他 offloading 系统平均少 43%。论文另报跨 context 平均提速 1.2×，但正文没有固定说明对应的 baseline，而且收益强依赖高带宽 CPU–GPU superchip。

## 问题与动机

自回归 [[LLM]] 会保存过去 token 的 [[KV-Cache]]，避免每一步重新计算 K/V。代价是 cache 随 context length 和模型维度线性增长；128K context 的大模型可能需要数百 GB，远超单卡 HBM。

现有 swap-based offloading 把 KV 放在 CPU 或 SSD，但 Attention 前仍要先搬到 GPU staging buffer。为了用复制覆盖计算，buffer 通常很大；每层还要 swap-in 和 swap-out，既占 HBM，又让同一份 KV 两次穿过 CPU–GPU interconnect。把 Attention 整体放到 CPU 可避免来回复制，却放弃 GPU 的计算能力（§2.2）。

GH200/GB200 用 NVLink-C2C 提供最高 900 GB/s 双向带宽，明显高于 PCIe Gen5 的 40–60 GB/s，使 GPU kernel 直接访问 pinned CPU memory 成为新的选择。但它仍低于 3–4 TB/s HBM。DirectKV 要解决的不是“能否 zero-copy”，而是怎样避免远端 KV 在 GPU 计算循环中被反复读取。

## 关键观察 / 隐含假设

- **观察 1：去掉 buffer 不会自动去掉瓶颈。** 在 10,240×10,240 GEMM case study 中，朴素 zero-copy 在 PCIe 上为 1,122 ms，而 HBM baseline 为 56 ms，慢 20×以上；即便换成 NVLink-C2C，仍为 106 ms 对 52 ms，约慢 2×（图 2、§2.3）。
  - **原因**：同一个 CPU-resident tile 被不同输出 tile 重复读取，CPU→GPU traffic 被放大，L2 hit rate 也从约 77% 降到 32.3%（图 3）。
- **观察 2：可以把带宽压力从慢链路转移到快 HBM。** 若把 CPU 侧 B/KV tile 留在 SMEM，遍历 GPU-resident A/Q 和中间结果，就能减少远端读取；代价是增加 HBM 对输出的读写。因为 HBM 快得多，这个交换有利（图 4–5、§2.4.1）。
- **观察 3：新生成的 K/V 被立刻使用。** 分开的 projection 与 Attention kernel 会先把 K/V 写到 CPU cache，再从 CPU 读回。融合后可在 SMEM/register 中直接消费，只把最终 KV 副本写入 CPU（图 7、§2.4.3）。
- **观察 4：长上下文访问是带宽问题多于单次 load latency。** 每个 SM 读取约 100 KB KV tile，100 多个 SM 并行会形成 MB 级传输，因此 sustained interconnect bandwidth 是主要限制（§2.2.2、§8.2）。
- **隐含假设 1：平台有 Hopper 级 kernel 能力。** 实现依赖 256 KB L1/SMEM pool、Tensor Memory Accelerator、warp-group specialization、CUTLASS 和 FlashAttention-3。论文只在 GH200/H100 上测，GB200 未测。
- **隐含假设 2：CPU memory 是便宜且不争用的 KV tier。** KV 通过 `cudaHostAlloc` 长期 pin 住，CPU 不并发修改。多 GPU、其他进程和多个请求共同争用 LPDDR/[[NUMA|NUMA]] bandwidth 时，结论可能变化。

## 核心方法

### 1. 四个组件把 kernel 选择和 KV 存放连接起来

DirectKV 有四个组件（图 8）：Kernel Generator 离线编译不同 dtype、head dimension、tile 和 prefill/decode 的候选 kernel；Kernel Adaptor 在线选择匹配版本；Attention Fusion Engine 运行融合 kernel；KV Cache Manager 用 pinned host memory 保存 K/V，并向 GPU 暴露 device-visible pointer。

Generator 先按 SMEM 容量筛选合法配置。SMEM 被逻辑分为 projection 和 Attention 两区，K/V 与 projection weight buffer、输出 buffer 在不同时刻复用；默认两级 pipeline 需要双缓冲，并保留约 20% L1。这样避免运行时 JIT，但每种新 dtype、head dimension 和硬件仍需预编译与调优（§4）。

### 2. CPU-memory-aware tiling 让远端 KV 保持 stationary

普通 GEMM tiling 让输出 C 留在 register/SMEM，反复读 A、B；当 B 在 CPU 时，这会把慢链路 traffic 从二次方放大到接近计算量。DirectKV 反过来让 CPU-resident B/KV tile 留在 SMEM，遍历 GPU-resident A/Q，并反复从 HBM 读写部分输出。示例中 CPU traffic 从 33.5 GB 降到 0.4 GB，而额外 HBM traffic 由其高带宽吸收，GEMM latency 从 106 ms 降到 54 ms，L2 hit rate 从 32.3% 回到 75.1%（图 4–5）。

prefill 的 Q 有多个 tokens，DirectKV 对每个 K/V tile 遍历 HBM 中的 Q，优先避免重复远端读 K/V。decode 只有一个新 query，则采用相反顺序：Q 和输出留在 register，顺序扫一次所有 CPU-resident K/V（算法 1–3、§5.1、§5.3–§5.4）。

### 3. Warp pipeline 隐藏 fetch，融合 kernel 消除回读

producer warp group 预取下一 tile，consumer 同时计算当前 tile；prefill 另有 storer 把新 K/V 写入 CPU。Hopper TMA 负责异步搬运，让 compute warp 少做地址和复制工作。GEMM 小实验中 pipeline 把 HBM throughput 从 0.3 提到 1.3 TB/s，latency 从 54 降到 48 ms（图 6）。

融合 kernel 在一次 launch 内完成 K/V projection、可选 RoPE、Attention score 和 streaming softmax。新 K/V 先留在 SMEM，既用于当前 Attention，又异步写入 CPU cache，不需要下一 kernel 再从 CPU 取回。prefill 使用 producer/consumer/storer 三组 warp；decode 只有一对新 K/V，使用 producer/consumer 两组（图 9、算法 2–3）。

### 4. KV Cache Manager 只管执行路径，不替代 serving policy

Manager 在 prefill 时把初始 K/V 写入 pinned CPU buffer，decode 时直接复用并追加新 token。DirectKV 不决定 batching、prefix reuse、eviction 或多级 cache policy；论文把它定位成 [[vLLM]]、[[SGLang]] 等 serving runtime 在“KV 已经位于 CPU”时可调用的 Attention execution path（§6、§8.1）。

因此，它可以和 [[Prefix-Caching]]、[[Continuous-Batching]]、prefill/decode [[Disaggregation]] 组合，但论文没有真正完成这些系统级集成。多服务器时，每台机器只能优化本地 CPU-resident shard，跨机 query、partial output 和远程 KV 仍由上层 runtime 处理（§8.3）。

## 设计取舍

- **HBM buffer 换 pinned CPU memory。** GPU capacity 明显增加，但 CPU DRAM 被锁页，OS 不能自由回收；论文没有报告 CPU memory footprint、pinning 上限或多租户影响。
- **远端读减少换 HBM 中间 traffic 增加。** 只有 HBM 与 C2C 带宽差足够大、HBM 仍有余量时，这种 tiling 才有利。
- **融合换 kernel 复杂度。** 省掉 launch 和 K/V 回读，却把 projection、RoPE、streaming softmax、prefill/decode、dtype 与 tile 组合进专用 CUDA 实现。
- **离线候选池换覆盖范围。** 运行时选择便宜，但新模型 shape、量化格式和 GPU 代际需要重新生成并验证 kernel。
- **容量换绝对最低延迟。** KV 全部 fit HBM 时，SGLang 仍更快；DirectKV 的价值主要在 HBM pressure 和长 context 下。
- **节点内扩容换硬件依赖。** PCIe 下仍能省显存，但吞吐收益受物理带宽限制；真正的性能 claim 主要属于 GH200/GB200 类 superchip。

## 实验设计

实现约 5,300 行 CUDA/C++，基于 CUDA 12.4、CUTLASS 3.0+ 和 [[Flash-Attention]] 3，并接入 [[PyTorch|PyTorch]]。主平台是单个 NVIDIA GH200 Grace–Hopper Superchip，96 GB HBM3 与 LPDDR5X CPU memory；PCIe 对照为相同 Hopper 架构的 H100。模型为 Llama-3.1-8B、OPT-13B、OPT-30B（§7.1–§7.2）。

Workload 使用 ShareGPT 和 Alpaca；因为数据集没有 timestamp，请求到达由 Poisson process 合成。主实验为 1K–32K context、最高 30 req/s，并补充更高压力。基线为 HBM-resident SGLang、NVLink staging 的 Pie、多级 4-bit offload 的 FlexGen，以及把部分 Attention 放到 CPU 的 Neo。它们接口和压缩策略不同，结果体现的是不同 capacity/performance 方案，不是单一机制的完全等价 A/B。

## 实验与结果

- **高请求率下，DirectKV 是 offloading 基线中延迟最低的。** Llama-3.1-8B 在 30 req/s 时，DirectKV per-token latency 为 0.75 s，Neo/Pie/FlexGen 为 1.55–2.95 s；SGLang 略快且不 OOM。OPT-13B 同一负载下 DirectKV 为 0.75 s，其他 offloading 系统为 1.55–3.95 s，而 SGLang OOM。OPT-30B 中 SGLang 只支持低 rate，DirectKV 可到 30 req/s（图 10、§7.3.1）。
- **容量收益在长 context 更清楚。** 不同 sequence length 下，DirectKV 使用 47 GB GPU memory；SGLang、Neo、Pie、FlexGen 分别约 92/86/88/74 GB。论文按 offloading 基线平均计算，DirectKV 少 35 GB、降 43%。在 16K tokens 时，DirectKV 比 Neo/Pie 快约 1.3×、比 FlexGen 快约 1.7×；32K 时 Neo、Pie、SGLang OOM，只有 DirectKV 与更慢的 FlexGen 继续运行。跨 context 的平均 speedup 报为 1.2×，但正文没有给这个平均值固定的单一 baseline（图 11、§7.3.2）。
- **CPU-aware tiling 是 zero-copy 能工作的首要消融。** 相对 naive zero-copy，三模型的 CPU→GPU transfer 最多减少 50%，inference latency 最多降低 70%（图 12、§7.4.1）。早期 GEMM case study 还显示 latency 106→54 ms、L2 hit 32.3%→75.1%，说明收益来自远端 traffic 与 locality，而不只是去掉 buffer（图 5）。
- **Fusion 与 warp pipeline 进一步消除局部开销。** 简化 GEMM 中 pipeline 把 latency 从 54 降到 48 ms；简化 projection+Attention fusion 从 85 降到 57 ms。完整三模型消融中，fused kernel 的 HBM throughput 最高为 separate kernel 的 3.5×，per-token latency 低 2.5–3.0×（图 6–7、13、§7.4.2）。这些是组件结果，不能直接与 1.2× 端到端 speedup 相乘。
- **4.2× 是 interconnect 对比，不是 DirectKV 对 baseline 的加速。** 图 14 在 512-token setting 下比较同一执行路径：NVLink-C2C 相对 PCIe 把 Attention latency 最多降低 4.2×。论文因此明确把 PCIe 版主要定位成 capacity extension；高性能结论依赖 C2C bandwidth（图 14、§7.4.3、§8.2）。

## 论断—证据表

| 论断 | 论文证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 高带宽 C2C 上，CPU memory 可以直接成为 KV 执行层，而不需要 HBM staging | 图 10–11：47 GB HBM、长 context 仍运行，offloading 系统中延迟最低 | 单 GH200，8B–30B，1K–32K，合成 Poisson arrival | 强 |
| CPU-aware tiling 能避免 naive zero-copy 的重复远端读取 | 图 5、12：traffic 最多少 50%，latency 最多低 70%，L2 hit 恢复到 75.1% | Hopper/CUTLASS/FP16-BF16 风格 kernel | 强 |
| Fusion 与 warp pipeline 对端到端性能有贡献 | 图 6–7、13：组件 latency 与 throughput 明显改善 | 消融多为 kernel/component metric；无法与端到端倍数直接相乘 | 中强 |
| DirectKV 普遍比 GPU-resident serving 更快 | KV fit HBM 时 SGLang 仍最低 latency | 价值来自 capacity pressure，不是所有 workload | 弱 |
| 方法可自然扩到分布式 serving 与其他 superchip | §8 给出组合方式 | 未做多 GPU、多 node 或 GB200 实验 | 弱 |

## 批判性分析

### 论证链条

论文的核心链条很清楚：naive zero-copy 因重复 remote fetch 和低 L2 hit 变慢；CPU-aware tiling 把 traffic 转到 HBM；warp pipeline 隐藏剩余延迟；fusion 去掉新 K/V 的写回再读；最终 HBM 使用和长 context latency 改善。图 2–7 的逐步 case study 与图 12–13 的模型级消融相互支持。

需要克制解释端到端数字。摘要称“up to 1.2×”，§7.3.2 又称“1.2× average”，正文没有明确这个平均值始终相对哪一个 baseline。图 10 的高负载收益远大于 1.2×，但包含 OOM 与不同 offloading 策略；当 KV fit 时 SGLang 更快。最稳妥的结论是“DirectKV 改善 GH200 上的 capacity–latency tradeoff”，不是“所有 LLM serving 都加速 1.2×”。

### 假设压力测试

CPU-aware tiling 假设远端 KV 值得长期驻留 SMEM，增加的 HBM 输出 traffic 仍能被吸收。若同一 GPU 还运行 bandwidth-heavy FFN、多个 model replica 或更多并发 kernel，HBM 可能不再有余量。若 C2C bandwidth 被其他 GPU/CPU workload 共享，remote tile 也会重新成为瓶颈。

实现还假设常见 head dimension、FP16/BF16、GQA/MHA 与 Hopper execution model。[[Quantization|FP8]]/INT4 KV、稀疏 Attention、context parallelism、动态 KV layout 和下一代 kernel API 可能需要新 fusion。KV 只由 GPU append、CPU 不修改，使 pinned memory 不需要 coherence；CPU 侧压缩、重排或跨节点迁移会破坏这个简单模型。

### 实验可信度

SGLang、Pie、FlexGen、Neo 覆盖 HBM、swap、多级 offload 和 CPU compute 四类方案；三种模型、rate/context sweep、memory、transfer、L2、HBM throughput 和两种 interconnect 也较完整。作者明确报告 SGLang 在 fit 时更快、PCIe 主要省容量，这是重要边界。

但主系统实验只有一台 GH200，模型最大 30B、context 最大 32K，远小于动机中的 128K 与数百 GB KV。ShareGPT/Alpaca 没有真实 arrival time，Poisson 合成请求不能覆盖 burst、prefix sharing 和多轮会话。Baseline 各自使用不同压缩、CPU compute 和 buffer policy，公平性很难只用 per-token latency 概括。图 14 的 C2C/PCIe 对比还是 512-token setting，不足以代表所有长 context。

论文声称保持完整 Attention accuracy，但评测没有列数值误差、模型 quality 或不同 fusion 次序的 validation。Kernel correctness 主要靠实现与结果默认成立，缺少专门测试。

### 系统性缺陷

DirectKV 把 serving 的一部分通用 memory management 问题变成硬件专用 fused kernel。约 5,300 行 CUDA/C++ 要覆盖 prefill/decode、RoPE、dtype、head dimension、tile、SMEM partition 和 pipeline；未来接入量化、[[MoE|MoE]]、[[Speculative-Decoding|speculative decoding]] 或新 Attention variant 的维护成本可能很高。

KV Cache Manager 使用大量 page-locked host memory，但论文只报告 GPU memory，没有 CPU capacity、memory bandwidth、NUMA locality、pinning 失败、OS pressure 和多租户 isolation。单机上某个 workload 占满 C2C/LPDDR 后，会影响同 superchip 的所有请求；系统没有 admission control 或 bandwidth QoS。

最后，论文把 integration 与 distributed serving 留在讨论。没有真正接入 vLLM/SGLang 的 scheduler、prefix cache、eviction 与 CUDA Graph，也没有 multi-GPU tensor/pipeline parallel test。因而“自然兼容”目前是接口论证，不是部署证据。

## 局限与后续工作

- 在 GB200、多个 GH200、PCIe H100 和不同 CPU memory 配置上画出 zero-copy 相对 swap 的 bandwidth crossover。
- 用 128K/256K context、70B 以上模型、真实 burst trace 和 prefix-sharing workload 测 throughput、P99 与 HBM/CPU memory。
- 多 GPU 同时访问 Grace memory 时，报告 C2C、LPDDR、HBM、NUMA contention 和每租户 tail latency。
- 报告 pinned memory 大小、CPU memory cost、OS 回收影响，并加入 bandwidth-aware admission/control。
- 将 DirectKV 真正接入 vLLM 或 SGLang，测 continuous batching、CUDA Graph、prefix caching、eviction 和 PD disaggregation。
- 对 FP16/BF16/FP8、不同 head dimension 和 context 做逐元素误差及端到端模型质量验证。

## 相关

- **相关概念**：[[LLM-Inference]]、[[KV-Cache]]、zero-copy、KV offloading、[[Attention]]、[[Flash-Attention]]、[[PCIe]]、[[Disaggregation]]
- **相关系统**：[[SGLang]]、[[vLLM]]、Pie、FlexGen、Neo
- **同会议**：[[OSDI-2026]]
