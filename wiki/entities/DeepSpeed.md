---
type: entity
kind: system
aliases: [DeepSpeed, Microsoft DeepSpeed]
status: active
last_updated: 2026-08-14
tags: [llm-training, distributed-training, zero, memory-optimization, pipeline-parallelism, checkpointing, fault-tolerance, microsoft]
---

# DeepSpeed

> DeepSpeed 是 Microsoft 维护的大规模深度学习训练 runtime；在本 wiki 的论文中，它既是 [[ZeRO]]、pipeline parallelism 和 offload 的常用实现，也是训练调优、checkpoint、可靠性与异构并行工作反复使用的 baseline 和集成宿主。

## 是什么

DeepSpeed 集成 ZeRO-1/2/3、mixed precision、activation checkpointing、CPU/NVMe offload、pipeline parallelism 和分布式 checkpoint 等能力。用户可以在 PyTorch 模型外配置训练拓扑与状态放置，不必自行实现每个 collective 和 optimizer shard。

它的优势是能力完整、生态成熟；边界是大量旋钮彼此耦合。ZeRO stage 会改变参数、梯度和 optimizer state 的驻留与通信，offload 会争用 PCIe 和 host memory，activation checkpointing 又改变计算与显存峰值。默认配置能运行，不代表已经接近目标硬件上的最佳点。

## 关键观察 / 隐含假设

- **配置空间本身已成为系统问题。** [[ProTrain-MLSys26]] 统计 DeepSpeed 等栈有 18 个以上相关旋钮；其所测默认配置只利用 35.6% GPU 显存，并比调优配置慢 1.18 倍。该结论来自特定模型和单卡/小规模实验，不代表所有 DeepSpeed 默认值都同样差。
- **checkpoint 与并行布局强绑定。** [[UCP-ATC25]] 说明 ZeRO-3 各 rank 保存不同分片，不能像 DDP checkpoint 一样直接换 DP/TP/PP degree；UCP 的 atomic intermediate form 已进入 DeepSpeed，但转换主要服务低频重配置。
- **DeepSpeed 可以作为深度定制的 runtime。** [[Obscura-ATC25]] 替换 pipeline scheduler、异步化 NCCL send/recv，并加入 activation swapping stream；这类 fork 级修改获得灵活性，也增加升级和正确性维护成本。
- **框架优化路径可能产生 silent bug。** [[TrainCheck-OSDI25]] 记录 BLOOM-176B 的 DeepSpeed BF16Optimizer 梯度裁剪问题，LayerNorm 权重在 TP ranks 间发散十天才被发现。
- **算子级对齐能跨框架定位差异。** [[OpGuard-OSDI26]] 在 DeepSpeed、Megatron、GPT-NeoX 等不同执行栈之间寻找共同 operator boundary；它需要可构造的 reference run，不能处理两个执行共同犯同一错误的情况。
- **对称布局限制异构和故障后利用率。** [[Hetu-v2-OSDI26]] 在 H800/H20 混合配置上显著快于 DeepSpeed baseline，并在故障后保留剩余设备；收益依赖专用 planner，而且为了恢复可用性要保留更多冗余。
- **通信接口使周边工具可以保持相对独立。** [[Greyhound-ATC25]] 只 hook NCCL，[[AdaCheck-FAST26]] 复用已有 communication groups；这共同假设 DeepSpeed 最终仍走可观测的标准 collective 路径。

## 演进时间线

- **ZeRO 与混合并行基座**：DeepSpeed 把 optimizer、gradient、parameter 分片和 offload 组合进统一训练栈，成为大模型训练的常用实现。
- **2025 checkpoint 与 pipeline 扩展**：[[UCP-ATC25]] 将 Universal Checkpointing 接入 DeepSpeed；[[Obscura-ATC25]] 在其 pipeline runtime 上调度 bubble 内重算。
- **2025 正确性与诊断**：[[TrainCheck-OSDI25]] 从训练运行中推断不变量，暴露优化器等路径的 silent error；[[Greyhound-ATC25]] 从 NCCL 层检测 fail-slow。
- **2026 自动调优与状态压缩**：[[ProTrain-MLSys26]] 搜索 memory/offload policy；[[AdaCheck-FAST26]] 识别由 DeepSpeed/ZeRO 等并行策略产生的 checkpoint redundancy。
- **2026 OSDI 异构与跨栈调试**：[[Hetu-v2-OSDI26]] 挑战对称分片假设；[[OpGuard-OSDI26]] 用 operator fingerprint 对齐 DeepSpeed 与其他训练栈。

## 相关概念

- [[ZeRO]]
- [[Pipeline-Parallelism]]、[[Tensor-Parallelism]]、[[Data-Parallelism]]
- 激活检查点（activation checkpointing）、训练检查点（checkpointing）
- 容错（fault tolerance）
- [[FSDP]]
- 混合精度训练（mixed-precision training）

## 相关论文

- [[ProTrain-MLSys26]] — 把 DeepSpeed 的显存、offload 与 checkpointing 配置压缩成可搜索空间。
- [[UCP-ATC25]] — 解耦 DeepSpeed checkpoint 与并行拓扑，并用于真实大模型重配置。
- [[Obscura-ATC25]] — 在 DeepSpeed pipeline runtime 中隐藏 activation recomputation。
- [[TrainCheck-OSDI25]] — 检测 PyTorch/DeepSpeed 生态中的 silent training error。
- [[OpGuard-OSDI26]] — 在 DeepSpeed 与其他框架之间对齐 operator tensor fingerprint。
- [[Hetu-v2-OSDI26]] — 用异构 HSPMD 对照 DeepSpeed 的对称布局。
- [[AdaCheck-FAST26]] — 兼容 DeepSpeed communication groups 的冗余感知 checkpoint。
- [[DP-ZeRO-MLSys26]] — 将 differential privacy 的 clipping/noise 接入 ZeRO/FSDP 路径。
- [[Greyhound-ATC25]] — 在 NCCL 层做与 DeepSpeed 相对解耦的 fail-slow 检测。
- [[NeuroSymbolicProof-OSDI26]] — 仅把 DeepSpeed ZeRO-2 用作模型微调后端，不是对 DeepSpeed 的系统评估。
- [[2DFS-ATC25]] — 把 DeepSpeed 列为 ML 部署生态组件，关注的是 OCI artifact 而非训练 runtime。

## 已知局限 / 开放问题

- 需要把模型、硬件、网络和版本写入配置 provenance；“DeepSpeed baseline”若不说明 ZeRO/offload 等设置，结果不可复现。
- 深度定制 scheduler、optimizer 或 checkpoint path 后，要承担 upstream 升级、组合测试和 silent-error 检测成本。
- 最大化分片节省与保留恢复冗余之间没有统一默认答案，取决于故障率、checkpoint 速度和资源价格。
- 对动态 shape、MoE routing、异构 GPU 与跨地域训练，静态配置和对称 rank 假设仍会频繁失效。
