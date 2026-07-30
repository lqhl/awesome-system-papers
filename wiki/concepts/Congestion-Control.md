---
type: concept
aliases: [CC, Congestion-Control-Algorithm]
last_updated: 2026-07-18
tags: [networking, transport, latency, feedback-control]
---

# Congestion Control

> 拥塞控制根据有关丢失、延迟、传送速率或显式信号的反馈来调整发送行为，以共享网络容量，同时限制队列增长和不稳定。

## 核心思想

传输端点根据延迟和噪声观察推断可用容量。因此，控制器选择如何积极地探测、如何对拥塞信号做出反应，以及优先考虑哪个目标（吞吐量、延迟、公平性或应用程序质量）。它的行为与路径拓扑、竞争流、缓冲区和传输/运行时实现密不可分。

## 为什么重要

许多网络和实时系统声称减少了拥塞控制的选择。吞吐量的提高可能会损害排队延迟或公平性；低延迟策略可能会导致容量闲置。评估需要工作负载、RTT/丢失变化、竞争流和端点边界。

## 关键观察 / 隐含假设

- **观察**：一个控制环路可能不适合所有流量类别。 [[MARC-ATC25]] 和 [[AnchorNet-ATC25]] 将实时/应用程序约束视为目标的一部分。
- **观察**：数据中心或硬件反馈路径具有不同的信号和时间尺度。 [[Barre-ATC25]] 和 [[SwCC-ATC25]] 检查此类特定于系统的边界。
- **假设**：测试台控制器结果推广到互联网或生产流量。 [[SplitConn-ATC25]] 和 [[STORM-ATC25]] 说明了为什么路径和工作负载组成必须明确。

## 设计空间与取舍

- **丢失、延迟、速率或显式反馈**：信号在响应性和噪声敏感度方面有所不同。
- **吞吐量与尾部延迟/公平性**：更积极的探测可以改善一个流，同时损害队列或对等点。
- **终端主机与网络辅助控制**：网络反馈可以提高可观察性，但增加了部署要求。

## 引用本概念的论文

- [[AnchorNet-ATC25]] — application-aware networking path.
- [[MARC-ATC25]] — real-time adaptation context.
- [[Barre-ATC25]] — network feedback/control system boundary.
- [[SwCC-ATC25]] — congestion-control design/evaluation.
- [[SplitConn-ATC25]] — transport-path system trade-offs.
