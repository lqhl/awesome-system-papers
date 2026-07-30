---
type: paper
name: veScale-FSDP
full_title: "veScale-FSDP: Flexible and High-Performance FSDP at Scale"
authors: [Zezhou Wang, Youjie Li, Zhiqi Lin, Jiacheng Yang, Cong Xie, et al.]
venue: MLSys
year: 2026
tags: [fsdp, distributed-training, sharding, moe, quantization, zero-copy]
source_pdf: "[[642e92efb79421734881b53e1e1b18b6.pdf]]"
source_md: "[[642e92efb79421734881b53e1e1b18b6]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-30
---

# veScale-FSDP：灵活且高性能的大规模 FSDP（MLSys 2026）

> **原题**：veScale-FSDP: Flexible and High-Performance FSDP at Scale

> **一句话总结**：在「结构感知训练要求分片边界与量化块/矩阵优化器语义对齐，而现有 FSDP 的 element-wise/row-wise 分片与 FSDP2 交错 Copy 在万卡规模下同时拖垮灵活性与吞吐」这一观察下，veScale-FSDP 用 RaggedShard 任意块粒度 DTensor placement + NP-hard 通信布局启发式规划 + Distributed Buffer 零拷贝，在 1024 GPU 端到端评测中相对 DeepSpeed/FSDP1/FSDP2/Megatron-FSDP 实现 **5–66% 更高吞吐**、**16–30% 更低显存**，并原生支持 8-bit Adam 与分布式 Muon；ByteDance Seed 生产部署至 **10K+ GPU**。

## 问题与动机

[[FSDP]] / ZeRO 是 LLM 训练最基础的并行手段：按层 AllGather 参数、ReduceScatter 梯度，在几乎不改模型代码的前提下把 optimizer state / gradient / parameter 分片到多卡。但当训练栈走向 **结构感知（structure-aware）** 工作负载时，现有实现出现两类系统性短板：

1. **分片格式与计算语义不对齐**：前沿训练 increasingly 依赖 **block-wise [[Quantization]]**（如 DeepSeek-V3 的 128×128 FP8 块、8-bit Adam 的 32×32 INT8 块）和 **非 element-wise 优化器**（Shampoo、Muon 的矩阵级 Newton–Schulz 更新）。这些算子要求参数/optimizer state 的 **块边界在分片后仍完整落在单设备上**。DeepSpeed ZeRO、PyTorch FSDP1 的 element-wise 拼接分片，以及 FSDP2 / Megatron-FSDP 的 row-wise 均匀 `Shard(0)`，都会在 device 边界切断块，迫使开发者侵入式改模型/optimizer，或手写 padding、metadata 交换与额外 collective。
2. **万卡规模的吞吐与显存瓶颈**：生产集群在 **10K+ GPU、万亿参数** 量级下，GPU memory 往往比 FLOPs 更紧——`record_stream` 非确定性释放、per-parameter eager allocation、未对齐 NCCL buffer、碎片化 AllGather、FSDP2 在 collective buffer 上的 interleaved Copy-In/Out（GPT-OSS-120B 上可达 AllGather/ReduceScatter 路径时间的 **~14%**）共同抬高 peak reserved memory 并压低网络利用率。

veScale-FSDP 的定位是：**保留 PyTorch `fully_shard` API**，透明替换 FSDP2 backend，同时把灵活性与性能一起拉上去。隐含 workload 是 ByteDance Seed 的大规模 dense / [[MoE]] LLM 预训练，需与 [[Expert-Parallelism]]、[[Tensor-Parallelism]]、HSDP 组合。

## 关键观察 / 隐含假设

- **观察 1：FSDP 的性能瓶颈已从「能不能跑起来」转向「collective buffer 布局是否零拷贝、对齐、均衡」**。
  - **依赖假设**：ZeRO-3 训练 step 中 AllGather + ReduceScatter 占显著比例；MoE 稀疏计算进一步放大通信占比；NCCL 对 buffer 地址对齐敏感。
  - **可能失效场景**：极小模型或极大 per-GPU batch 使计算完全掩盖通信；自定义通信栈已解决对齐与 fusion 时，DBuffer 相对收益缩小。

- **观察 2：结构感知训练的核心约束是「不可分片块（non-shardable block）必须完整落在单设备 local shard」**，而非「均匀 element/row 切分」。
  - **依赖假设**：用户会为量化/矩阵优化器显式指定块粒度（如 32 row、128×128 tile）；块内可独立量化、矩阵更新无需跨设备 metadata 交换。
  - **可能失效场景**：块粒度与 FSDP group size 的 LCM 导致 padding 尖峰（GPT-OSS 融合 expert 张量在 128-row 粒度下 padding 可达 **~18%**）；块过大而 group size 不整除时有效 shard 被向上取整。

- **观察 3：Transformer 参数高度结构化——线性层权重占主导、层间 sharding block size 往往一致**——使通信布局优化的 tensor 排列启发式在实践中接近最优。
  - **依赖假设**：默认 tensor 顺序、按 block size 或 shape 排序三种顺序之一足够好；规划算法用默认顺序以简化调试。
  - **可能失效场景**：非 Transformer 架构、极度异构参数形状、用户自定义 FSDP wrap 产生数百个 diverse block size 时，默认排列可能远离最优；论文对非 Transformer 仅说「可插拔排序」但未系统评测。

- **观察 4：小规模（~64 GPU）逐层 profile 的 compute + FSDP communication 时间可外推到数千 GPU 的 weak scaling 行为**。
  - **依赖假设**：网络拓扑、collective 算法、协议与目标规模可比；workload 足够大以饱和带宽；通过 HSDP/EP 限制 collective group size 避免超大 collective 的 latency 波动。
  - **证据强度**：**中**——§6.2 weak/strong scaling 与 Lesson-1 互证，但外推条件（拓扑一致、饱和带宽）在第三方集群未必成立。

- **假设 1：在 DTensor 生态上扩展 placement 比重写并行栈更划算**——RaggedShard 作为可选 placement 即可复用 checkpointing、redistribute、与 TP/EP 组合。
  - **证据强度**：**强**——实现 7.6K LoC Python 替换 FSDP2 backend；RaggedShard 已进入 PyTorch 2026 H1 roadmap；与 `torch.distributed.checkpoint` 兼容。

## 核心方法

veScale-FSDP 由三层抽象叠加：**灵活分片 → 结构感知通信规划 → 零拷贝 buffer 原语**。

### RaggedShard：灵活 DTensor placement

受 JaggedTensor/NestedTensor 启发，RaggedShard 在 contiguous storage 上支持：

- **任意 sharding granularity**：原子不可分块可为 element、row、或自定义 shape 的 2D/高维 block（Block-wise RaggedShard）。
- **任意 per-device 分布**：不同 device 可持有不同数量的块（uneven sharding），为 Muon 的 root gather 等语义留出空间。

与现有 placement 的组合规则：

- 对 `Shard(0)`（TP/EP 常用）：引入 **StridedRaggedShard** 携带 stride/reorder 元数据，materialize 全 tensor 时做必要 reshuffle。
- 对 `Shard(dim>0)`：将 ragged granularity 设为该维 stride 与用户粒度的 **LCM**，避免切断该维。
- 约定 EP/TP 在概念上先于 FSDP，但 PyTorch placement 列表顺序相反；veScale-FSDP 在实现层 reconcile。

RaggedShard 直接复用 DTensor checkpointing 栈，支持 communication-free sharded checkpoint。

### Grouped communication：结构感知规划（Algorithm 1）

多参数 bucket 通信时，朴素拼接会导致三类低效（Figure 6a）：块被切过 device 边界、padding 落在 tensor 内部破坏连续性、per-device buffer 不均衡。

论文将布局问题形式化为：给定 RaggedShard tensor 集合，求最小 uniform per-device buffer size \(S\)，满足 **Non-Sharded Block**、**Contiguous Tensor Memory**、**Balanced Load**。该问题 **NP-hard**（可归约到 Partition problem），实践中用多项式启发式：

1. 选定 tensor 排列（默认顺序 / 按 block size / 按 shape；生产用默认顺序）。
2. DP 放置 tensor 到全局 buffer：对每 tensor 做 shard 边界 case analysis，利用 \(dp(t,i)\) 单调性压缩状态，复杂度 \(O(|T|^2 m \log E \log(|T|m))\)。
3. 在 tensor **之间**插入 padding，而非 tensor 内部；对齐 collective preferred unit size \(g_{coll}\) 与各 tensor block size 的 LCM。

规划为 **一次性初始化开销**，实测 **<0.3s**。

### Distributed Buffer (DBuffer)（分布式缓冲区（DBuffer））

DBuffer 在 N 维 device topology 上提供 **全局 buffer 语义** + **group-level 算子**：

- 通信前融合跨 tensor 的相同 CUDA kernel（add/scale/zero/copy），减少 launch 碎片与通信阻塞。
- 利用规划后的持久地址映射，实现 AllGather/ReduceScatter 前后 **zero-copy** 访问各参数 data pointer。
- **in-place** collective 与计算；batched allocation + 显式 stream 依赖管理，降低 fragmentation 与非确定性 `record_stream` 导致的 peak memory 膨胀。

整体保留 `fully_shard` API，作为 plug-and-play Python 模块接入标准 PyTorch distributed runtime。

### 结构感知训练 case study

- **8-bit Adam**：通过 `orig_param_policy` 为参数设量化粒度（如矩阵参数 32-row block）；RaggedShard 保证块边界，本地独立量化，无需 metadata collective。
- **分布式 Muon**（Algorithm 2）：`SelectRoot()` 负载均衡 → `Redistribute(u, RaggedShard(r))` 在 root 物化完整 2D 矩阵 → Newton–Schulz → redistribute 回写；非 root rank 上矩阵更新为 no-op。优化版在 256 Hopper GPU 达 **47.3% MFU**。

## 设计取舍

- **RaggedShard 灵活性 vs 规划复杂度**：任意块粒度把分片决策交给用户，但引入 NP-hard 布局问题与 padding；论文用启发式 + 离线 simulation 选 FSDP group size 缓解，仍可能在 fused-expert 布局上出现阶跃式 padding 尖峰。
- **Zero-copy DBuffer vs Megatron-FSDP 式拼接**：DBuffer 避免 FSDP2 式 Copy-Out，也不走 Megatron 为对齐 `Shard(0)` checkpoint 语义而插入的 **~33% padding**（MoE 实验）；代价是 7.6K LoC 新 backend 与对规划质量的依赖——禁用 planning 吞吐降至 **65.4%**（Table 2）。
- **Uneven sharding（Muon）vs 通信**：矩阵优化器需在 root 聚集全矩阵，引入阶段性 gather/redistribute；靠 async redistribute 与 compute 重叠缓解，但 root 计算与负载均衡策略成为新瓶颈，论文未给出 root 选择的 tail latency 分析。
- **默认 tensor 顺序 vs 最优布局**：为可调试性固定默认顺序，在高度不规则模型上可能牺牲 **~34.6%** 量级吞吐（相对禁用 planning 的 ablation 暗示布局质量关键）。
- **边界条件**：**ZeRO-3 + mixed precision（FP32 master + BF16 fwd/bwd）+ 大规模 MoE/dense LLM** 最优雅；**极小模型、无结构感知算子、第三方集群拓扑与 ByteDance 不一致** 时，相对 FSDP2 的边际收益可能仅体现在 memory 管理而非端到端吞吐。

## 实验与结果

**Setup**：§6.1/6.4/6.5 在 H800 集群（8×H800/node，979 BF16 TFLOPS，80GB HBM，400GB/s NVLink）；§6.2/6.3 在 Hopper 集群。Baselines：DeepSpeed ZeRO v0.17.6、PyTorch 2.7.1 FSDP1、PyTorch 2.7.1 FSDP2 (`fully_shard`)、Megatron-FSDP；均 ZeRO-3 + mixed precision。Workload：LLaMA-3-70B、GPT-OSS-120B、内部 MoE；默认 AdamW，GPT-OSS 部分 baseline 用 SGD 避免 OOM。

**端到端（1024 GPU，Figure 8）**：

- **吞吐**：MoE 上比所有 baseline 快 **11–66%**；LLaMA-3-70B 比 DeepSpeed/FSDP1/FSDP2 快 **~5%**，略优于 Megatron-FSDP。归因：通信重叠、DBuffer 零拷贝、灵活粒度减 padding；DeepSpeed 碎片化 collective，FSDP1 通信 bubble，FSDP2 interleaved copy + 未对齐 buffer，Megatron MoE padding 膨胀。
- **显存**：peak reserved memory 降 **16–30%**；相对 DeepSpeed/FSDP1 的 `record_stream` 非确定性释放（~20% 膨胀）、FSDP2 per-parameter eager alloc（额外 ~12%）、Megatron MoE padding（~33%）与 LLaMA 上低精度 buffer 持久化（~24%）均更优。
- **GPT-OSS 应力案例**：FSDP2 在 128 GPU 可训、256 GPU OOM——128 experts 摊到 256 devices 时 AllGather buffer 因 even-split padding **有效翻倍**；veScale-FSDP 无此断崖。

**扩展性（Figure 9）**：

- **Weak scaling**：800B MoE，1K–8K GPU，固定 per-GPU 2K–16K tokens，近线性。
- **Strong scaling**：全局 batch 16M–128M tokens，120M-token batch 线性扩展到 **10K GPU**；16M-token batch 1K→8K 仍有 **3.4×** 吞吐增益；极大规模时 per-GPU token 变少、FSDP 通信主导，辅以 cross-node EP 减通信但引入 token exchange 开销。
- **Model scaling**：1K GPU 上 400B→**2.4T** 参数，MFU 随模型增大略升（计算强度增加）。

**结构感知（64 GPU，Figure 10）**：

- 8-bit Adam loss 曲线与 DDP 接近（学习率不同，曲线不直接可比）；Muon 与 DDP Muon 一致，且比 AdamW **~0.01** 更低 loss（~80B tokens 后）。

**规划质量（Figure 11）**：

- DeepSeek-V3-671B / GPT-OSS-120B，1×/16× row 粒度 padding **<3%**；128× row 时 DeepSeek 仍大多 <3%，GPT-OSS 因 **fused expert 单张量** 出现最高 **~18%** 阶跃尖峰。
- 算法运行时间 **<0.3s**。

**消融（32 GPU，GPT-OSS-style + 8-bit Adam，Table 2）**：

- 禁用 DBuffer → 吞吐 **92.8%**（Copy-In/Out 回归）。
- 禁用 planning → **65.4%**（块不再保证 contained，需 DTensor redistribution 组装 optimizer state）。
- 禁用 RaggedShard → **N/A**（需侵入式改模型或手写 collectives）。

## 批判性分析

### 论证链条

主链条闭合度较高：**结构感知算子需要 intact blocks** → **RaggedShard 表达任意粒度与分布** → **分组通信若无规划则块被切断/内存不连续/负载失衡** → **NP-hard 问题的多项式启发式 + DBuffer 零拷贝** → **端到端吞吐与显存双提升，并解锁 8-bit Adam / Muon**。

设计与观察映射明确：RaggedShard 回应 block-wise 量化与矩阵优化器；planning 回应 FSDP2 Copy-Out 与 Megatron padding；DBuffer 回应碎片化 collective 与 memory allocator 行为。

薄弱环节在于 **生产规模结论部分依赖未开源内部 MoE（800B–2.4T）**，外部复现主要集中在 LLaMA/GPT-OSS 与 64–1024 GPU 公开配置；「万卡线性扩展」的 strongest evidence 来自内部 trace + Figure 9，而非第三方集群独立验证。

### 假设压力测试

| 假设 | 论文已证明 | 可能失效条件 |
|------|-----------|-------------|
| 块完整性可避免量化 metadata 通信 | 8-bit Adam case study + planning ablation | 块粒度与 group size LCM 导致大 padding，净通信未必赢 |
| 默认 tensor 顺序足够优 | Transformer 统计 + padding <3%（多数配置） | Fused-parameter 布局（GPT-OSS experts）尖峰至 18% |
| 64 GPU profile 可外推万卡 | Weak scaling + Lesson-1 | 拓扑/算法变化、未饱和带宽的小 batch |
| Zero-copy 优于 FSDP2 copy | 7.2% 吞吐 ablation + Table 1 copy 占比 | 若未来 PyTorch 消除 interleaved buffer 设计 |
| Muon root gather 可扩展 | 47.3% MFU @ 256 GPU | 大 FSDP group 下 root 热点、Newton–Schulz 内存 |

### 实验可信度

- **优势**：对比 **四个** SOTA 开源 FSDP 栈；覆盖 dense + MoE + 内部超大模型；显存与吞吐同图；含 scalability、规划质量、组件 ablation；披露 GPT-OSS/FSDP2 OOM 应力案例。
- **局限**：内部 MoE 与 2.4T 实验 **不可复现**；GPT-OSS baseline 部分改用 SGD；loss 曲线（8-bit Adam）明确 **不可直接对比**；Figure/table 经 MinerU 可能有 OCR 噪声，精确曲线应以 PDF 核对。
- **缺失**：未系统报告 **端到端 step time 的 P99**、故障恢复、多 tenant 集群下的 memory 隔离；Muon 仅报 MFU 未报相对 AdamW 的 wall-clock 开销分解。

### 系统性缺陷

- **Padding 与 FSDP group 选择耦合**：有效 shard size 随 group size 阶跃；论文建议 HSDP 限 group size + 离线 simulation，但 **无自动调参工具** 交付给普通用户。
- **Fused parameter 布局敏感**：GPT-OSS 将所有 expert fuse 为单 tensor，削弱 per-expert padding 自由度——这是 **模型定义与系统优化未解耦** 的反例（与 Lesson-3 主张形成张力）。
- **Root-based Muon**：矩阵优化器在 root 集中计算，存在 **straggler root** 与内存峰值风险；论文未讨论 root 失败或弹性重选。
- **运维与可观测性**：DBuffer + 规划布局使参数在全局 buffer 中的位置间接映射，debug numerics、对比 checkpoint 与 per-parameter inspect 成本上升；**论文未讨论**。
- **兼容性边界**：绑定 PyTorch `fully_shard` / DTensor 生态；对 DeepSpeed 用户需迁移；非 CUDA / 非 NCCL 栈未验证。

## 局限与后续工作

- **局限 1**（实验边界）：最强 scaling 与 2.4T model scaling 依赖 **内部 MoE**，公开基准主要集中在 70B–120B 量级与 1024 GPU 以下对比。
- **局限 2**（布局敏感）：fused expert 等大张量布局下，128× row 粒度 padding 可飙升至 **~18%**；需模型侧 per-expert 物化或更小 FSDP group / HSDP 折中。
- **局限 3**（优化器路径）：Muon/Shampoo 等需阶段性 full-matrix 语义，引入 gather 与 root 计算；论文展示可行性但未给出与纯 AdamW 在大规模下的 **总训练时间** 权衡曲线。
- **局限 4**（规划启发式）：默认 tensor 顺序对非 Transformer 或极度异构 wrap 的最优性 **未充分评测**。
- **Future work 1**：在 **公开 MoE 模型** 上复现 8K–10K GPU weak/strong scaling，并报告 padding ratio、Copy 开销、MFU 的联合 sensitivity，验证 Lesson-1 外推条件。
- **Future work 2**：对 **fused vs per-expert parameter layout** 做系统测量：固定总参数量与 FSDP size，比较 padding 尖峰、AllGather 体积与 checkpoint 复杂度的 Pareto 前沿。
- **Future work 3**：将 FSDP group size / RaggedShard 粒度选择形式化为 **可离线求解的 co-design 问题**（与 hidden size 因子分解、HSDP/EP 拓扑联合），给出可复现的 simulation 工具而非经验法则。

## 相关

- **相关概念**：[[FSDP]]、[[Expert-Parallelism]]、[[Tensor-Parallelism]]、[[MoE]]、[[Quantization]]、ZeRO、DTensor、HSDP
- **同类系统**：PyTorch FSDP2 (`fully_shard`)、DeepSpeed ZeRO、Megatron-FSDP、[[veScale]]（同团队 eager-mode SPMD /tensor 编程栈）
- **同会议**：[[MLSys-2026]]
- **对比**：veScale-FSDP vs FSDP2（RaggedShard 块对齐 + 零拷贝 DBuffer，避免 ~14% interleaved copy 与 even-split OOM）；vs Megatron-FSDP（避免 ~33% MoE padding 同时保留 DTensor checkpoint 语义）；与 [[DP-ZeRO-MLSys26|DP-ZeRO]] 正交——后者解决 **差分隐私** 下的 ZeRO 兼容，veScale-FSDP 解决 **结构感知训练 + 万卡性能**
