---
type: paper
name: GhostServe
full_title: "GHOSTSERVE: A Lightweight Checkpointing System in the Shadow for Fault-Tolerant LLM Serving"
authors: [Shakya Jayakody, Youpeng Zhao, Chinmay Nehate, Jun Wang]
venue: MLSys
year: 2026
tags: [llm-inference, fault-tolerance, kv-cache, erasure-coding, serving]
source_pdf: "[[1c383cd30b7c298ab50293adfecb7b18.pdf]]"
source_md: "[[1c383cd30b7c298ab50293adfecb7b18]]"
---

# GHOSTSERVE: A Lightweight Checkpointing System in the Shadow for Fault-Tolerant LLM Serving (MLSys 2026)

> **一句话总结**：基于「[[KV-Cache]] checkpoint 的瓶颈是 PCIe I/O 与 host memory 占用、而非 parity 计算」的观察，GhostServe 在 [[Tensor-Parallelism]] 下用 8:2 [[Erasure-Coding]] 只异步存 parity shard（比全量复制省 **75%** 内存、**73%** checkpoint 延迟），配合 chunk 级 round-robin 调度与 hybrid recovery，在 [[SGLang]] 上 checkpoint 快 **2.7×**、恢复快 **2.1×**，15% 故障率下 P50 延迟改善 **1.2×**。

## 问题与动机

百万 token agent 任务（Codex、Claude Code 等）把 LLM serving 从短请求变成**长时间有状态作业**。推理引擎级故障在生产中很常见——Microsoft 对 156 起高严重度 incident 的分析显示约 **60%** 发生在 inference engine 层（[[KV-Cache]] 错误、内存泄漏、kernel crash 等）。单 GPU 软故障会丢掉随序列长度增长的 [[KV-Cache]]，系统只能从头重算 prefill；论文引用 405B 模型 1M context 在 8×H100 上可浪费约 **20 分钟**。

训练侧 checkpoint 方案（复制整份状态、写 SSD）对 serving 不适用，作者指出两条结构性矛盾：

- **延迟**：[[Tensor-Parallelism]] 下 intra-node I/O 难以与计算 overlap；64K 输入、70B 模型上 naive CPU checkpoint 可把 prefill 延迟拉高 **113%**（Figure 2）。
- **内存**：全量复制 300GB+ host memory，与 [[PagedAttention]] 式 KV offload、preempted request buffer 争抢资源，反而降低整体可靠性。

GhostServe 的 claim 是：不必复制整份 [[KV-Cache]]，只需在 shadow 里保护 erasure-coded parity，即可在故障时快速重建，且对正常 serving 路径开销极小。

## 关键观察 / 隐含假设

- **观察 1**：checkpoint 开销的主导项是 **GPU→host PCIe 传输量与 host memory 占用**，而非 parity 计算本身。Figure 6 显示 collection + erasure coding 显著低于 PCIe I/O；8:2 parity 相对全量复制，host memory 与 checkpoint 延迟各降约 **75% / 73%**。
  - **依赖假设**：parity shard 数量 K ≪ data shard 数 N（默认 8:2）；PCIe Gen4 单向约 32 GB/s 是瓶颈；parity 计算可用融合 CUDA kernel 压到可忽略。
  - **可能失效场景**：TP=2 时论文明确显示 erasure coding 收益消失（编码开销无法抵消 I/O 节省）；parity ratio 过高或 chunk 过小会把 compute 重新推回主导；跨 node 时 inter-node 带宽远低于 NVLink，parity 放置策略需重做。
  - **证据强度**：强。多模型、多序列长度、kernel microbenchmark 与 I/O breakdown 一致支撑。

- **观察 2**：[[Tensor-Parallelism]] 下每张 GPU 只持 KV 分片；若每张卡本地持久存 peer shard 做 erasure coding，会严重挤占 HBM、限制 serving 容量。chunk 级 gather 到**单张指定 GPU** 的临时 buffer 算 parity 再异步下刷 host，可把持久 HBM 开销降到固定小块，chunk 间 idle <**5%**。
  - **依赖假设**：intra-node NVLink 足够快以支撑 `torch.dist.gather`；[[Chunked-Prefill]] 已把 prefill 切成固定 token chunk（实验默认 2K）；round-robin 指定 parity GPU 可避免单卡 hotspot。
  - **可能失效场景**：gather 是 many-to-one 同步操作，microbenchmark 显示其耗时可超过 parity reconstruct；decode 阶段 KV 增量更新时 chunk 边界与请求交错，在线 multi-request 下 stream pool 管理复杂度上升；[[Disaggregation]]（prefill/decode 分离）后 parity 应落在哪一侧论文未给出方案。
  - **证据强度**：中到强。架构图 + Algorithm 1 + TP scaling ablation 支撑；但 PD 分离与 decode-heavy workload 仅列为 future work。

- **观察 3**：生产 serving 故障多为 **GPU memory 软错误**（SDC、内存错误、kernel fault、资源泄漏），失败 GPU 可重启后重新加入，不必整 node 硬重启；因此只需恢复丢失的 KV 数据，而非 full-stack live migration。
  - **依赖假设**：NCCL 通信图与 TP 分组在 launch 时静态绑定；恢复流程包含 NCCL 重连、GPU warmup、CUDA graph capture，然后才做 KV recovery；最多容忍 K 张卡同时故障（K = parity 数）。
  - **可能失效场景**：硬故障需换卡或缩 TP group 时，静态拓扑使 inference 必须暂停直至拓扑重建——论文 Section 8 明确承认无法 runtime 剔除故障 GPU；silent corruption 若未触发 detectable fault，parity 会**无损重建错误数据**。
  - **证据强度**：中。fault model 引用生产统计，但实验用 flush memory buffer 模拟，未注入真实 SDC 或 correlated multi-GPU failure。

- **假设 1**：[[KV-Cache]] 的 FP16 张量可按 IEEE-754 重解释为 uint16，在 bit 域做 XOR/RDP/Reed-Solomon 编码**完全可逆**，恢复后浮点值 bit-exact 一致。
  - **证据强度**：中。有融合 kernel 与 PyTorch 对比；但论文未讨论 BF16/FP8 KV、量化 KV 或 MoE/MLA 等非标准 layout 的兼容性。

## 核心方法

GhostServe 把存储系统里的 [[Erasure-Coding]] 搬到 LLM serving：N 个 TP data shard 生成 K 个 parity shard，parity 异步落到 host memory；故障时用幸存 shard + parity 重建，而非复制整份 [[KV-Cache]]。

**FP16 无损编码**：标准 erasure code 在 Galois field / bit 域工作，与 FP tensor 不兼容。论文把 FP16 按 IEEE-754 重解释为整数 bit pattern，用融合 CUDA kernel 一次完成 pack → encode/reconstruct → unpack，支持 XOR（单故障）、RDP（双故障）、Reed-Solomon（更高容错）。配合 CUDA Graph 与 multi-stream reconstruct，encoding 相对 native PyTorch 显著加速。

**Chunk-level scheduler**：对齐 [[Chunked-Prefill]]，每个 token chunk 生成后，round-robin 指定 GPU k gather 全 TP 分片、算 parity、`PCIe` 异步下刷 host；k 循环递增避免 straggler。持久 HBM 只需 gather 用的小块临时 buffer，不占 peer shard 常驻空间。

**Hybrid recovery**：短序列（recompute 单元 r ≥ 已处理 chunk 数 n）全量 recompute，避免 gather/transfer 开销；长序列只 recompute 前 r 个 chunk，其余 overlap：异步把 parity 从 host 拉回失败 GPU，同时用 CUDA stream 并行 reconstruct。r 由 `get_recompute_units(s, m, N, K)` 动态决定，ablation 显示 hybrid 相对纯 reconstruct 最高快 **42.9%**。

**实现**：~4K Python + 1.5K C++/CUDA 插件，后端 [[SGLang]] 0.5.1 + FlashInfer 0.3.1；声称可移植到 [[vLLM]] / TGI。在线 [[Continuous-Batching]] 扩展为 per-request CUDA stream pool，decode 时增量更新 parity。

设计映射：观察 1 → 只存 K 个 parity 降 I/O；观察 2 → chunk gather + round-robin；观察 3 → 聚焦 intra-node 软故障 KV 恢复。深度实现见 [[1c383cd30b7c298ab50293adfecb7b18]] / [[1c383cd30b7c298ab50293adfecb7b18.pdf]]。

## 设计取舍

- **Parity 换复制**：8:2 比全量复制省 75% 内存，但容错上限绑死为 K 路并发故障；超过 K 仍需 pure recompute。RS 比 XOR/RDP 更强容错，但 latency/storage 更高——论文提供三 scheme 让用户按 SLO 选。
- **Gather 中心化换 HBM 容量**：避免每卡存 peer shard，但引入 NCCL gather 同步与单卡 parity 计算 hotspot；round-robin 缓解但未消除 gather 本身开销。
- **Hybrid recovery 换实现复杂度**：短序列走 recompute、长序列走 reconstruct，需动态选 r；错误估计 r 会在「多余 recompute」与「多余 PCIe」之间摆动。
- **Intra-node 专注换通用性**：不处理 NCCL 拓扑动态重组、跨 node 带宽分层、node 级硬故障；与 TorchFT 等 full-stack 框架互补而非替代。
- **边界条件**：TP≥3 且长输入 prefill-heavy 时最优雅；TP=2、极短序列、decode-dominated reasoning、PD 分离部署时收益变薄或需重新设计。

## 实验与结果

- **平台**：8×H200 NVLink Gen4 + 2×48-core Intel + 1024GB DDR5；Medha 合成 trace（4K–1M 序列、batch 4–64、Poisson 到达）；故障率 5%–15% 随机注入（flush 故障 GPU buffer）。
- **Batched inference**：相对 SGLang-CPU（DejàVu 风格全量复制），checkpoint 平均 **2.7×** 快、恢复 **2.1×** 快；I/O 开销降 **13×**（vs CPU）、**132×**（vs SSD/PCCheck 风格）；decode 开销 <**10%**。
- **恢复延迟**：LLaMA-3-70B、64K 输入恢复 <**5s**，SSD 基线近 **2 分钟**；GPT-OSS-120B / 70B 上仍最低。
- **在线 serving**：15% 故障率下 LLaMA-70B P50/P99 分别 **1.2× / 1.1×** 优于 naive recompute；EITR >**90%**；failure-free 下 mean/tail latency 最多降 **11%**。
- **百万 token**：相对无 checkpoint 基线 overhead <**6%**；相对 DejàVu checkpoint 从 **2.6 分钟** 降到 **9 秒**。
- **Sensitivity**：parity ratio 升高仅边际增加开销；batch 放大时优势保持；hybrid recovery ablation 最高 **42.9%** 增益；TP=2 时 erasure coding 无优势。

## Critical Analysis

### 论证链条

「KV checkpoint 贵在 I/O 与内存，不贵在 parity 计算」→「只存 K 个 parity + chunk gather」→「2.7× checkpoint、2.1× recovery、1M context <6% overhead」链条在 **intra-node TP + 长 prefill** 设定下闭合较好。作者没有把结果外推成 cross-node 或 full-stack HA，Section 8 主动收窄 scope，与实验一致。

薄弱跳步在于：**gather 同步成本是否会在更大 TP、更短 chunk 或更高 batch 下反超 parity 节省？** microbenchmark 显示 reconstruct 可快于 gather，但 end-to-end 仍以整体 win 呈现；TP=2 失效边界说明论证对 N/K 敏感，论文未给出「收益为正」的解析不等式。

### 假设压力测试

- **Workload 变化**：实验以 long-input-short-output 与 Medha 合成为主；decode-heavy reasoning（不可预测生成长度）论文承认 encoding 协议复杂化，未验证。Mooncake 类超长上下文 + 多级 KV 存储时，parity 与已有 CPU/SSD tier 如何协同未讨论。
- **硬件变化**：H200 + NVLink Gen4 集群；普通 PCIe 拓扑或无 NVLink 时 gather/parity 平衡可能翻转。故障模型假设 failed GPU 可重启归队，真实 datacenter 换卡/降配场景需新 TP group，GhostServe 只能暂停等待。
- **模型变化**：FP16、标准 MHA；GQA/MLA/MoE、FP8/BF16 KV、压缩 KV 是否仍 bit-exact 可编码，论文未覆盖。
- **正确性**：erasure coding 保证**比特级可逆**，不保证语义正确；若 SDC 污染 KV 而未触发 detectable fault，recovery 会忠实还原错误状态——与 SAVE 类 bit-level 检测正交。

### 实验可信度

- **Baseline 公平性**：SGLang-CPU 为作者实现的 DejàVu 风格异步复制（非原 PP 设定 DejàVu）；SGLang-SSD 基于 PCCheck 思路复现。对比合理但可能低估原系统在其他并行策略下的表现。SGLang-Base（pure recompute）是在线 serving 的关键对照，结果可信。
- **Benchmark 代表性**：Medha + Poisson 到达比纯 synthetic uniform 更接近异构 serving，但仍非公开 production trace；15% 故障率为上限压力测试，与 Microsoft incident 统计方向一致。
- **Fault injection**：flush memory + hang peers 测恢复路径，不覆盖 gradual leak、partial corruption、multi-GPU correlated failure；EITR/MTTR 对 injection 时点敏感。
- **Ablation**：kernel fusion、CUDA graph、hybrid recovery、parity ratio、TP scale 均有；**缺少** round-robin vs static parity GPU、chunk size 对在线 tail latency 的分解。

### 系统性缺陷

- **Full-stack HA**：NCCL 图静态，故障 GPU 不能热剔除；与 RaidServe 等「不规则 GPU 数继续服务」形成对比，GhostServe 定位更窄。
- **尾延迟与隔离**：在线实验报 P50/P99 与 EITR，未细拆 recovery 期间对其他 request 的 head-of-line blocking；multi-tenant parity host memory 隔离未讨论。
- **可观测性 / 运维**：shadow checkpoint 失败、parity 损坏、host OOM 时的降级策略论文未讨论。
- **跨 node / PD 分离**：Section 8 列为主要 future work；当前方案难直接用于 Mooncake / DistServe 类架构。
- **专利**：作者声明 pending patent（dynamic erasure-coded KV + live migration），与开源 demo 的授权边界未说明。

## 局限与 Future Work

- **局限 1**：仅覆盖 intra-node TP 软故障 KV 恢复，不实现 runtime TP 重组、跨 node parity 放置或 node 级硬故障。
- **局限 2**：静态 NCCL 拓扑下 failed GPU 必须恢复后才能继续，无法像 overprovisioning + live migration 那样无缝降配服务。
- **局限 3**：decode-heavy、PD 分离、不可预测生成长度场景缺乏端到端评估；与 [[Disaggregation]] 结合的 fault model 仍开放。
- **Future work 1**：topology-aware 跨 node parity 调度，平衡 NVLink vs InfiniBand/NIC 带宽差距，并引入 durable remote storage 应对 node 失效。
- **Future work 2**：与 TorchFT 等 full-stack fault tolerance 集成，把 KV-level erasure recovery 接到权重恢复、通信图重建与 live service migration。
- **Future work 3**：在真实 production fault trace（非 flush 模拟）上测量 SDC 场景下的检测缺口，并量化 parity host memory 与 [[PagedAttention]] offload 共存时的容量规划曲线。

## 相关

- **相关概念**：[[KV-Cache]]、[[Chunked-Prefill]]、[[Tensor-Parallelism]]、[[Continuous-Batching]]、[[Disaggregation]]、[[PagedAttention]]、[[Erasure-Coding]]
- **同类系统**：[[SGLang]]、[[vLLM]]、Mooncake、DejàVu（Strati et al. 2024）、PCCheck、RaidServe
- **同会议**：[[MLSys-2026]]
- **对比**：相对 DejàVu/CPU 全量复制，GhostServe 用 parity 降 I/O；相对 SSD checkpoint，避免持久化尾延迟；相对 RaidServe，聚焦 KV parity 而非 irregular-TP 继续服务