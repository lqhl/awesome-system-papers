---
type: concept
aliases: [Congestion-Control-Algorithm]
last_updated: 2026-08-14
tags: [networking, transport, latency, feedback-control]
---

# Congestion Control

> 拥塞控制（congestion control）根据丢包、排队、RTT、ECN/CNP 或显式网络遥测调节发送速率和在途数据量，目标是在共享链路上同时维持吞吐、低延迟和基本公平性。

## 核心思想

发送端看不到“真实可用带宽”，只能从反馈推断网络状态。控制器通常反复执行三步：探测容量、识别拥塞、减小或恢复发送量。不同算法的差别不只在公式，还在反馈从哪里来、多久到达一次、状态放在 host、NIC 还是 switch，以及控制粒度是 packet、flow、chunk 还是 application frame。

一个算法不能脱离路径讨论。RTT、buffer、PFC、流量突发、incast 规模、多路径和竞争算法都会改变闭环行为。论文中的高带宽利用率若没有同时报告队列、P99 流完成时间和对其他流的影响，不能直接解释为“更好的拥塞控制”。

## 为什么重要

AI 集群的 AllReduce、AllGather 和 AlltoAll 具有完全不同的 fan-in、消息大小与持续时间。[[Barre-ATC25]] 指出 MoE 训练中的 AlltoAll 已成为重要流量来源，而传统 DCQCN 在 400 Gbps 网络上的反馈与增窗节奏可能过慢。[[UCCL-Tran-OSDI26]] 则说明，大块 ML 通信允许把控制逻辑从 NIC 固件移到 host software，但这会消耗 CPU，并把 host 抖动带入传输路径。

拥塞控制还会和其他层相互作用。[[FLB-ATC25]] 表明，在 PFC 网络中把一个拥塞流扩散到更多路径，可能扩大 head-of-line blocking；[[MARC-ATC25]] 和 [[AnchorNet-ATC25]] 说明，应用码率与连接切换若忽略控制器状态，也会制造发送队列和重新慢启动。控制器不是独立模块，而是整个端到端反馈链的一部分。

## 关键观察 / 隐含假设

- **反馈越细，不代表一定越好。** [[SwCC-ATC25]] 支持 per-packet 可编程控制，但需要很短的事件处理路径和专门的 QP 状态访问；[[UCCL-Tran-OSDI26]] 每 32 KB 才做一次决定，用较低控制开销换取可能的反应损失。
- **CNP、RTT 和 inflight 各自只看到一部分状态。** [[Barre-ATC25]] 用 CNP 触发减速、用 RTT 决定增窗节奏，再补充 inflight 约束；这个组合依赖 ECN/CNP 配置和 PCC 能力，不能直接外推到任意 RNIC。
- **多路径既能绕开冲突，也能扩大拥塞影响面。** [[UCCL-Tran-OSDI26]] 通过 RTT 感知选路避开 flow collision；[[FLB-ATC25]] 在 PFC 网络中反而要把真正拥塞的 flow 限制到更小路径集合。
- **同名算法的实现和版本也会改变行为。** [[SplitConn-ATC25]] 发现 BBR v1、v2、v3 及不同 TCP/QUIC 实现的 loss response 差异很大；“使用 BBR”不是足够精确的实验描述。
- **应用语义可以改善控制，但不是免费信息。** [[STORM-ATC25]] 需要 deadline、priority、reliability 和无线信号；[[MARC-ATC25]] 需要识别 motion phase。错误或过期的标注会让调度决策反而更差。
- **编码器与拥塞控制构成闭环。** [[Reparo-MLSys26]] 的恒定 token 码率可能让控制更稳定，但论文没有在完整 WebRTC/GCC 闭环中验证，视频质量结果不能替代网络公平性证据。

## 设计空间与取舍

- **反馈信号**：loss 简单但反应晚；RTT 能看到排队却受路径基线影响；ECN/CNP 需要网络配置；INT 信息丰富但部署成本高。
- **控制位置**：NIC 延迟稳定但程序受限；host 易升级但占 CPU；switch 可见全局局部状态，却带来硬件和运维依赖。
- **控制粒度**：per-packet 反应快、状态访问重；chunk/RTT 级更省资源，但可能错过 microburst。
- **rate 与 window/inflight**：rate limiter 适合稳定节奏，但反馈到达前仍可能注入过多数据；inflight 上限更直接，却需要准确 BDP 和 ACK 状态。
- **单路径与多路径**：多路径提高容错和利用率；reordering、路径不对称和 PFC 扩散会增加复杂性。
- **网络目标与应用目标**：最大吞吐、低 P99、公平性、视频 QoE 和训练完成时间常不一致，必须明确优先级。

## 引用本概念的论文

- [[SwCC-ATC25]] — 在 FPGA RDMA engine 中提供可编程 per-packet 拥塞控制核心。
- [[Barre-ATC25]] — 在生产 400 Gbps RoCE 集群中组合 CNP、RTT 与 inflight 控制。
- [[UCCL-Tran-OSDI26]] — 将 ML transport 的控制面移到 host software，并保留 NIC 数据搬运。
- [[FLB-ATC25]] — 研究拥塞控制、负载均衡和 PFC head-of-line blocking 的耦合。
- [[SplitConn-ATC25]] — 说明 path splitting 的收益依赖具体算法、版本和实现。
- [[STORM-ATC25]] — 用无线信号和应用可靠性语义调度多路径移动流量。
- [[MARC-ATC25]] — 在拥塞控制给出的 pacing rate 之上做 motion-aware 应用码率控制。
- [[AnchorNet-ATC25]] — 通过统一 publishing path 避免模式切换时重建独立拥塞控制状态。
- [[Reparo-MLSys26]] — 用恒定码率 neural codec 改变拥塞控制所看到的输入流量。

## 已知局限 / 开放问题

- 需要在真实多租户 trace 上联合报告 P50/P99/P99.9、吞吐、公平性、PFC 和 CPU/NIC 开销。
- 800 Gbps、更大 EP degree 和 P/D KV 传输混跑后，现有参数和反馈周期需要重新标定。
- 可编程 NIC/host controller 需要程序验证、资源配额、回滚和可观测性，不能只比较算法 LoC。
- 多路径系统需要解释拥塞归因、reordering、路径故障和错误隔离如何影响控制稳定性。
