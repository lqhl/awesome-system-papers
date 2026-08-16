---
type: concept
aliases: [Zero-Redundancy-Optimizer, ZeRO-1, ZeRO-2, ZeRO-3]
last_updated: 2026-08-14
tags: [distributed-training, sharding, memory-management]
---

# ZeRO

> ZeRO（Zero Redundancy Optimizer）把数据并行进程中原本重复保存的训练状态分片。阶段越高，单卡常驻显存越少，但参数收集、梯度归并、临时缓冲、检查点和故障恢复也越复杂。

## 为什么需要它

普通 [[Data-Parallelism|数据并行]] 中，每个 rank 处理不同 mini-batch，但通常各自保存一整份模型参数、梯度和优化器状态。混合精度 Adam 还可能同时保存低精度参数、FP32 master weight、一阶动量和二阶动量。模型越大，这些副本越快耗尽显存；增加数据并行卡数会提高总显存，却不会自动降低单卡的状态副本。

ZeRO 的基本判断是：一次更新只需要所有 rank 在逻辑上看到一致的完整模型，不要求每个 rank 永久保存每一份状态。系统可以让不同 rank 负责不同分片，在需要计算某一层时临时收集参数，并在反向传播后把梯度归并到负责该分片的 rank。

## 三个阶段

| 阶段 | 常驻分片状态 | 仍在每个数据并行 rank 上复制 | 主要额外要求 |
|---|---|---|---|
| ZeRO-1 | 优化器状态 | 参数、梯度 | 更新前后协调对应参数分片 |
| ZeRO-2 | 优化器状态、梯度 | 参数 | 用 reduce-scatter 等方式让梯度归属负责 rank |
| ZeRO-3 | 优化器状态、梯度、参数 | 通常不再保留完整长期副本 | forward/backward 按执行顺序 all-gather 参数，并及时释放 |

这里的“零冗余”描述的是**常驻训练状态**，不表示运行时完全没有副本。ZeRO-3 计算某一层时仍要临时 materialize 参数；collective bucket、预取窗口、通信缓冲和尚未释放的层会形成峰值。显存是否真的降低，取决于释放时机、执行顺序和 allocator，而不只取决于选择了哪个 stage。

## 关键设计取舍

### 1. 容量与通信、调度复杂度

阶段越高，单卡可容纳的模型越大，但系统更依赖频繁 collective 和准确预取。大 bucket 能提高网络效率，却占更多临时显存；小 bucket 释放更灵活，却可能被启动延迟和拥塞主导。动态计算图、可变序列、异构 GPU 或成员频繁变化时，静态执行顺序与预取模型更容易失效。

[[CrossPipe-ATC25]] 把这个问题放进跨数据中心流水线调度：ZeRO-1 的 all-gather 必须排在每个 model chunk 第一次 forward 之前，因此不是可忽略的后台流量。论文证明通信操作需要进入依赖图和链路模型，但只覆盖其 CrossPipe 配置，不能推出某个 ZeRO stage 在所有 WAN 上都最优。

### 2. 显存与 CPU、NVMe offload

ZeRO-Offload 可以把参数或优化器状态放到 CPU，进一步扩大模型，但会消耗 PCIe、主机内存和 CPU 更新能力。[[ProTrain-MLSys26]] 指出，ZeRO、offload、activation swapping 和 gradient checkpointing 的 18 个以上旋钮会互相争用带宽；默认 DeepSpeed 配置在其测量中只利用 35.6% GPU 显存。ProTrain 用一次 profiling 和代价模型联合选择常驻 chunk、交换 buffer 与重算 block，在所测 GPT、OPT、Mistral 和 LLaMA 上相对多种基线提高 1.43–2.85 倍吞吐。证据主要来自最多 4 张 3090/A100、序列长度 1024，不代表大规模 3D 并行已有统一自动配置。

[[Obscura-ATC25]] 从流水线 activation 内存给出另一个边界：ZeRO/FSDP、重算和交换会改变哪一个 stage 最先 OOM；host-side swapping 还可能与 ZeRO-Offload、checkpoint 和 dataloader 争用 PCIe。Obscura 没有联合实测这些组合，因此这里是资源冲突警告，不是量化结论。

### 3. 去冗余与故障恢复

副本既是显存浪费，也可能是现成的恢复来源。[[Hetu-v2-OSDI26]] 为了在 GPU 故障后直接从剩余数据并行副本重分片，专门禁用 ZeRO-1、保留完整冗余；Llama 32B 的正常 step time 从 6.05 秒升到 6.91 秒，约增加 15%。论文的快速重配置只覆盖仍有完整 replica 的单设备损失等配置；多个副本同时丢失或 collective 中途失败仍可能需要 checkpoint。

这说明最高 stage 不一定是生产系统的最优点。若显存有余而恢复时间昂贵，保留部分副本可能比把容量压到极限更划算。

### 4. 分片方式决定检查点还能去掉多少重复

[[AdaCheck-FAST26]] 测量不同 ZeRO、TP、PP、EP 和自动并行组合，发现训练状态冗余可在 25%–100% 之间变化。ZeRO-1 中参数仍完整复制、优化器状态已经分片；若只按单个 tensor 的重复数删除副本，可能留下优化器却丢掉对应参数。AdaCheck 因而在“参数与优化器可恢复组合”层面判断冗余，并用增量 gradient checkpoint 补足 ZeRO-3 等几乎没有离线冗余的情况。论文报告相对 CheckFreq/GEMINI 将 checkpoint 体积缩小 6–896 倍，但依赖 mixed-precision Adam、训练期间分片策略稳定和周期性完整 checkpoint。

[[AITurbo-FAST26]] 从存储侧看到同一规律：低 stage 和普通数据并行有更多重复 payload，可用 checksum 去重和 compute-fabric 广播；ZeRO-3 的分片更独特，去重收益下降。AITurbo 在 6 种 TP/PP/ZeRO 配置上报告 checkpoint write 相对存储基线最高 58.8 倍、相对 Gemini 最高 5.9 倍，但最大数字同时来自 DRAM staging、去重和 I/O plan，不能全归因于 ZeRO 感知。

### 5. 逻辑分片之后，物理碎片仍然存在

[[MoonBright-OSDI26]] 在训练中组合 ZeRO、offload、recomputation 和 virtual pipeline，发现框架 allocator 仍会因动态映射产生 external fragmentation。其 GPU 虚拟内存机制把 Qwen 的 Z+O+R 配置中 `peak allocated / peak reserved` 从 72.8% 提高到 97.8%。这个指标证明逻辑状态分片没有自动解决底层地址空间和 allocator 问题；论文没有把它等同于训练吞吐或最大模型规模。

## ZeRO 还会影响什么

### 差分隐私训练

[[DP-ZeRO-MLSys26]] 把 per-sample clipping、noise、mixed precision 与 ZeRO-1/2/3、FSDP 组合。ViT-Gigantic 中，DP 相对 standard training 的吞吐比例从 ZeRO-1 的 81%–83% 提高到 ZeRO-3 的 94%–95%；固定 26B 模型从 16 扩到 128 张 GPU 时达到 standard ZeRO 95% 以上速度，并在 256 张 A100 上运行最多 100B trainable-parameter 的效率实验。它证明的是系统可运行性和相对效率，不是 100B 私有训练的最终质量；标准 loss scaling 还可能破坏论文所测 DP mixed-precision 路径。

[[Cocoon-OSDI26]] 处理相关噪声历史的容量问题，并提出将 noise sharding 与 ZeRO/FSDP 联合规划。其主实验最大语言模型约 1.3B、4 张 GPU，没有真正验证现代大模型 optimizer sharding；因此只能列为后续集成方向。

### 作为应用训练的基础设施

[[NeuroSymbolicProof-OSDI26]] 用 DeepSpeed ZeRO-2 对 Qwen3-1.7B 和 Mistral-7B 做 full-parameter SFT。这个事实说明 ZeRO 已成为普通训练工具，但论文没有比较 stage、内存或吞吐，因此不能当作 ZeRO 性能证据。

[[FlexPipe-ATC25]] 的变长流水线工作把与 ZeRO、TP、EP 的系统组合明确列为未覆盖范围。它提醒我们，单项优化在 3D 并行栈中可能改变通信组、显存瓶颈和迁移成本；不能把“分别有效”直接理解为“叠加后仍有效”。

## 批判性分析

ZeRO 的核心抽象很清楚：把“所有 rank 永久保存完整训练状态”改成“每个 rank 长期负责一部分，需要时临时重建完整视图”。它把可训练模型上限从单卡显存约束推向集群总显存与网络约束，是大模型训练最重要的内存机制之一。

但“stage 越高越好”是危险的简化。更高 stage 可能减少 checkpoint 去重机会、增加参数 materialization、放大网络尾延迟，并拿走故障后原本可利用的副本。真实选择至少要同时考虑：模型是否能装下、collective 拓扑、临时峰值、checkpoint 带宽、故障率、恢复目标和 host offload 冲突。

现有论文多在各自系统中选一个 ZeRO 配置，再展示局部收益。AdaCheck、AITurbo、Hetu-v2 和 MoonBright 的共同价值，是分别暴露了检查点、恢复、存储去重和 allocator 四个“ZeRO 之外”的状态问题；它们还没有形成一个能自动联合优化训练速度、容量和可靠性的统一控制面。

## 使用时应检查

- 每个 stage 下，参数、梯度、优化器、activation 与临时 bucket 的**实测峰值**是多少？
- all-gather 与 reduce-scatter 是否和计算重叠，P99 collective 延迟是否稳定？
- checkpoint 保存的是全局状态还是 rank-local shard，换并行度后能否恢复？
- 故障后是否还有完整副本；若没有，重新加载和 reshard 要多久？
- CPU/NVMe offload 是否与 dataloader、activation swap 和 checkpoint 抢同一条 PCIe/内存带宽？
- 模型、序列长度或成员变化后，prefetch、bucket 和释放策略是否需要重新 profile？

## 开放问题

- 在给定故障率和显存预算下，应该保留多少冗余，才能最小化长期 lost work？
- 动态 membership 中，参数、优化器、RNG、dataloader、privacy history 和 checkpoint 怎样做原子 reshard？
- 如何把 stage、offload、activation 重算、pipeline schedule 与 checkpoint 策略放进同一代价模型？
- MoE、低精度 optimizer、异构 GPU、CXL 与 NVMe tier 会不会让固定三阶段描述不够用？
- 如何提供 shard、collective、prefetch、临时峰值和恢复路径的统一可观测性？

## 相关论文

- [[AdaCheck-FAST26]]：自动识别不同并行组合中的可恢复冗余。
- [[AITurbo-FAST26]]：从云存储侧利用 ZeRO 配置留下的重复 checkpoint 数据。
- [[Hetu-v2-OSDI26]]：展示去冗余与无 checkpoint 快速恢复的直接冲突。
- [[MoonBright-OSDI26]]：说明逻辑分片后仍有 GPU allocator fragmentation。
- [[DP-ZeRO-MLSys26]]：把差分隐私训练接入 ZeRO 各阶段。
- [[ProTrain-MLSys26]]：联合搜索 ZeRO-3、offload、swapping 和重算配置。
- [[CrossPipe-ATC25]]：把 ZeRO-1 all-gather 纳入跨地域流水线依赖图。
- [[FlexPipe-ATC25]]：指出变长流水线与 ZeRO 等 3D 并行组合尚未实测。
- [[Obscura-ATC25]]：暴露 activation swapping 与 ZeRO-Offload 的潜在 host 资源冲突。
- [[Cocoon-OSDI26]]：提出 privacy noise history 与 ZeRO/FSDP 的联合分片方向。
- [[NeuroSymbolicProof-OSDI26]]：把 ZeRO-2 用作 proof model 微调基础设施，不提供 ZeRO 消融。

## 相关概念

- [[Data-Parallelism]]、[[FSDP]]、[[DeepSpeed]]、[[Tensor-Parallelism]]、[[Pipeline-Parallelism]]、[[Checkpoint]]
