---
type: concept
aliases: [Fully-Sharded-Data-Parallel, Fully-Sharded Data Parallel]
last_updated: 2026-07-30
tags: [distributed-training, sharding, memory-management]
---

# FSDP

> Fully Sharded Data Parallel（FSDP）把参数、梯度和优化器状态跨 data-parallel ranks 分片，在算子执行前按需 all-gather、反向后 reduce-scatter，以通信和调度复杂度换取接近按 rank 数缩小的训练状态显存。

## 核心思想

每个 rank 只常驻自己负责的参数 shard；进入某个模块前临时聚合完整参数，计算完成后释放，反向再归约梯度。它与 [[ZeRO]] Stage 3 在资源目标上接近，但具体 API、模块边界、prefetch、flattening 与 runtime 集成不同。现代 FSDP 的系统问题已从“能否省显存”转向 sharding plan、通信重叠、异构/故障重配置和数据管线协同。

## 为什么重要

FSDP 让单卡放不下的 dense model 可用普通 data parallel 编程方式训练，也是 PyTorch 生态的默认大模型分片原语之一。[[veScale-FSDP-MLSys26]] 说明 naive wrap/module policy 远未达到硬件最优；[[Hetu-v2-OSDI26]] 与 [[Cocoon-OSDI26]] 则暴露其在异构 GPU、故障恢复和超大 privacy history 下的边界。

## 关键观察 / 隐含假设

- **分片粒度决定 peak memory 与 collective 频率。** 细粒度释放更及时，但会生成更多小 collective；粗粒度通信效率高，却扩大瞬时完整参数占用。
- **overlap 依赖稳定的执行顺序和准确 profile。** [[veScale-FSDP-MLSys26]]、[[ProTrain-MLSys26]] 等工作围绕 prefetch、计划与通信隐藏优化。
- **elastic recovery 与最大分片存在张力。** [[Hetu-v2-OSDI26]] 为利用剩余设备并从 DP redundancy 恢复参数而禁用 ZeRO-1，一个配置 step time 增加约 15%；完全去冗余会让快速无 checkpoint 重配置更难。
- **训练状态不只参数/梯度。** [[Cocoon-OSDI26]] 的 correlated-noise history 可超过 200 GB，提示 FSDP/ZeRO 尚未统一管理 privacy、optimizer 和外部 history 的多层分片。

## 设计空间与取舍

- **模块级与参数级 sharding**：前者接口简单，后者内存更紧但调度复杂。
- **prefetch 深度**：提前 all-gather 可隐藏通信，却抬高峰值显存并可能预取错误分支。
- **静态与自适应计划**：静态可复现；动态适应长度、拓扑和故障，但需要 graph switching 与 state migration。
- **同构与异构设备**：传统 FSDP 假设对称 ranks；[[Hetu-v2-OSDI26]] 用 HSPMD annotation 表达非对称 shard/layout。
- **checkpoint 与冗余**：更激进分片节省容量，却增加失败后的恢复依赖和状态搬移。

## 引用本概念的论文

- [[veScale-FSDP-MLSys26]] — FSDP sharding/执行计划优化
- [[Hetu-v2-OSDI26]] — 以分层异构 SPMD 扩展对称分片，讨论故障恢复与 ZeRO 冗余张力
- [[Cocoon-OSDI26]] — 提出在 FSDP/ZeRO 式多节点训练中联合参数与 correlated-noise history 分片的开放问题
- [[Charon-MLSys26]] — 分布式训练内存与执行管理
- [[DP-ZeRO-MLSys26]] — 隐私训练与 ZeRO/FSDP 状态分片
- [[Obscura-ATC25]] — 训练状态与内存优化
- [[Optimus-ATC25]] — 分布式训练计划
- [[MPG-MLSys26]]、[[FCP-MLSys26]]、[[ProTrain-MLSys26]]、[[BOOST-MLSys26]] — 并行、通信和训练执行优化
- [[Chen-LLMDataPipelines-OSDI26]] — 数据管线与训练吞吐协同

## 已知局限 / 开放问题

- dynamic graph、MoE expert imbalance 与混合序列长度会破坏静态 prefetch/reshard 计划。
- checkpoint、optimizer、DP noise、RNG 与 dataloader state 尚缺少统一 shard/recovery 抽象。
- 多租户网络拥塞下 all-gather/reduce-scatter 的 P99 与公平性证据不足。
- 异构设备上如何在容量、算力和网络三者间自动生成可验证计划仍开放。
