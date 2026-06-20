---
type: entity
kind: system
aliases: [DeepSpeed, Microsoft DeepSpeed]
status: active
last_updated: 2026-06-20
tags: [llm-training, distributed-training, zero, memory-optimization, pipeline-parallelism, checkpointing, fault-tolerance, microsoft]
---

# DeepSpeed

> Microsoft 开源的大规模深度学习训练优化库，[[ZeRO]]、pipeline parallelism、[[UCP]] 等能力的集成落点，是当前论文中最常被当作 baseline、集成宿主与生产训练栈参照的 distributed training runtime 之一。

## 是什么

DeepSpeed 是面向大规模 [[LLM-Training]] 的 PyTorch 生态训练加速库，由 Microsoft 维护并深度嵌入 BLOOM、Phi 等生产预训练路径。这些论文共同把它视为「ZeRO 分片 + 混合并行 + offload/checkpointing 旋钮」的事实标准栈：[[ProTrain-MLSys26]] 统计其暴露 **18+** 个耦合的 ZeRO/offload/checkpointing 配置项；[[UCP-ATC25]] 将 Universal Checkpointing 开源进 DeepSpeed 并用于 BLOOM 176B、Phi-3.5-MoE 42B；[[Obscura-ATC25]] 直接在 DeepSpeed 上挂自定义 pipeline scheduler 做 bubble-filling recomputation。

DeepSpeed 的边界在 inbound 论文里也很清楚。它擅长在固定并行拓扑下通过 ZeRO stage、activation checkpointing、CPU/NVMe offload 等组合压低显存峰值，但旋钮耦合使默认配置往往远离最优——[[ProTrain-MLSys26]] 报告默认设置仅利用 **35.6%** GPU 显存且比调优后慢 **1.18×**。checkpoint 文件格式与 ZeRO stage、TP/PP 切分强绑定，故障或资源弹性时需额外转换层（[[UCP-ATC25]] 的动机）；silent correctness bug 可长期潜伏而不触发异常（[[TrainCheck-OSDI25]] 的 BLOOM-176B BF16Optimizer 梯度裁剪案例）。论文反复把 DeepSpeed 与 [[FSDP]]、[[Megatron-LM]]、Colossal-AI 并列为同类系统，而非单一垄断方案。

## 关键观察 / 隐含假设

- **观察 1：ZeRO/offload/checkpointing 旋钮高度耦合，专家调参成本是真实瓶颈。** [[ProTrain-MLSys26]] 将 DeepSpeed 作为强 baseline，指出换硬件（3090→A100）后手工配置常 OOM 或利用率低；其 profiler 还揭示层间 trace 会低估 transient tensor 峰值约 **17.2%**，使基于 DeepSpeed 默认配置的内存规划不可靠。
- **观察 2：DeepSpeed checkpoint 格式与并行策略绑定，弹性重配需中间表示。** [[UCP-ATC25]] 观察到 ZeRO-3 各 rank 独立保存 P/OS 分片，与 DDP「rank 0 存全量」完全不同；UCP 选择 lazy 触发 atomic checkpoint 转换而非改写 DeepSpeed 正常 save 路径，说明这些论文共同假设生产训练仍以框架原生分片保存为主、重配是低频事件。
- **观察 3：DeepSpeed 是 pipeline/memory 优化的可改造 runtime，但深度定制意味着 fork 级集成。** [[Obscura-ATC25]] 在 DeepSpeed 上替换 scheduler、改 NCCL send/recv 为异步并加 activation swapping stream；收益依赖 1F1B 中未利用的 forward/backward bubble，与已有 zero-bubble/overlap schedule 组合时边界未充分验证。
- **观察 4：框架层 silent error 可在 DeepSpeed 优化器路径中长期潜伏。** [[TrainCheck-OSDI25]] 以 BLOOM-176B DeepSpeed BF16Optimizer 梯度裁剪 bug 为工业案例：[[Tensor-Parallelism]] rank 间 LayerNorm 权重悄悄发散 **10 天** 才被发现；TrainCheck 还在 Accelerate/DeepSpeed 生态挖出 **6** 个新 bug，且 DeepSpeed MoE 仅 **1/15** tutorial 覆盖 specialized feature。
- **观察 5：作为训练栈宿主时，DeepSpeed 的通信语义可被上层系统正交扩展。** [[Greyhound-ATC25]] 检测模块与 Megatron/DeepSpeed 框架解耦，只 hook [[NCCL]]；[[AdaCheck-FAST26]] 声明兼容 DeepSpeed/nnScaler/[[Merak]] 栈，利用并行框架已组织的 communication group 做 redundancy 探测——这些论文共同假设 DeepSpeed 最终仍走标准 collective 接口。

## 演进时间线

- **ZeRO 时代（生态基座）**：ZeRO-1/2/3 分片 optimizer state、gradient、parameters，成为 [[ProTrain-MLSys26]]、[[DP-ZeRO-MLSys26]]、[[AdaCheck-FAST26]] 讨论内存与 checkpoint redundancy 的共同前提；[[DP-ZeRO-MLSys26]] 将 per-sample clip+noise 嵌入 ZeRO 各 stage，宣称达到与 DeepSpeed/[[FSDP]] 同级的十亿参数 DP 训练能力。
- **2025 生产栈深化**：[[UCP-ATC25]] 在 DeepSpeed 开源 Universal Checkpointing，BLOOM 176B 真实事件（48 node→24 node）与 Phi-3.5-MoE 42B 端到端训练验证；[[Obscura-ATC25]] 基于 DeepSpeed runtime 做 pipeline bubble-filling recomputation，18B–28B 相对 full recomputation 约 **22%–33%** 加速。
- **2025–2026 可靠性与周边栈**：[[TrainCheck-OSDI25]] 主动在 PyTorch/DeepSpeed 栈推断训练不变量；[[AdaCheck-FAST26]] 将 adaptive redundancy-aware checkpoint 接入 DeepSpeed 兼容 API；[[Greyhound-ATC25]] 将 fail-slow 缓解限于 Megatron plugin，DeepSpeed 生产栈迁移仍待验证。
- **2026 对照与竞争**：[[ProTrain-MLSys26]] 在 GPT-2/OPT/Mistral/LLaMA 上相对 DeepSpeed 吞吐 **1.43–2.71×**、最大可训练模型达 DeepSpeed **2.47×**；DeepSpeed 从「默认选型」转为「需精细调参或替代的强 baseline」。

## 相关概念

- [[ZeRO]]（DeepSpeed 核心内存分片机制）
- [[Pipeline-Parallelism]]、[[Tensor-Parallelism]]、[[Data-Parallelism]]
- [[Gradient-Checkpointing]]、[[Activation-Checkpointing]]
- [[Checkpointing]]、[[Fault-Tolerance]]
- [[FSDP]]（PyTorch 原生对等方案）
- [[Mixed-Precision-Training]]

## 相关论文

- [[UCP-ATC25]] — Universal Checkpointing 开源进 DeepSpeed，解耦 ZeRO/3D/MoE checkpoint 与并行重配
- [[Obscura-ATC25]] — 在 DeepSpeed 上实现 bubble-filling pipeline transformation 隐藏 recomputation
- [[ProTrain-MLSys26]] — 将 DeepSpeed 18+ 旋钮抽象为 chunk/block 参数并自动搜索，吞吐与可训练规模显著超越默认 DeepSpeed
- [[TrainCheck-OSDI25]] — 在 PyTorch/DeepSpeed 生态自动推断不变量，检出 BLOOM BF16Optimizer 等 silent bug
- [[AdaCheck-FAST26]] — 兼容 DeepSpeed 栈的 adaptive redundancy-aware minimal checkpoint
- [[DP-ZeRO-MLSys26]] — 宣称一行接入 DeepSpeed/FSDP，首次 DP 训练 GPT-100B 级可训参数
- [[Greyhound-ATC25]] — fail-slow 检测与 Megatron/DeepSpeed 框架解耦，缓解端尚未 plug 到 DeepSpeed
- [[2DFS-ATC25]] — 分布式 ML 部署 artifact 语境下的同类系统参照（与 DeepSpeed 训练栈正交）