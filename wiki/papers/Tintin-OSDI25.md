---
type: paper
name: Tintin
full_title: "Tintin: A Unified Hardware Performance Profiling Infrastructure to Uncover and Manage Uncertainty"
authors: [Ao Li, Marion Sudvarg, Zihan Li, Sanjoy Baruah, Chris Gill, Ning Zhang]
venue: OSDI
year: 2025
tags: [profiling, hardware-counters, operating-systems, linux-kernel, real-time-scheduling]
source_pdf: "[[osdi25-li.pdf]]"
source_md: "[[osdi25-li]]"
---

# Tintin: A Unified Hardware Performance Profiling Infrastructure to Uncover and Manage Uncertainty (OSDI 2025)

> **一句话总结**：Tintin 把硬件计数器(HPC)多路复用引入的误差**量化为 uncertainty 并在线反馈给应用**,再用弹性实时调度在 HPC 上分时,比 Linux `perf_event` 的插值精度提升 3.09×,overhead ≤2.4%。

## 问题

现代 CPU 提供大量可编程 HPC 事件(Intel Haswell-X 1623 种),但每核只有 2–6 个物理计数器。当感兴趣事件多于物理计数器,`perf_event` 采用时间片轮转的 multiplexing,然后通过插值估计总计数——这种估计有可观的误差,且误差大小完全不透明,下游工具拿到的是「看起来精确的数字」。

第二个问题是 attribution:HPC 只是独立的计数器,需要 OS 把它与程序执行对齐。`perf_event` 只提供 per-task / per-core 两种绑定,但应用真正想要的 scope 各异——特定代码区域、VM、跨多任务——没有统一的抽象。两个 scope 重叠时(进程和它运行的 core 都要 profile),后到的事件可能完全得不到调度,造成 starvation。

DMon、Pond 这类用 HPC 做在线决策的应用因此普遍存在误测和误归因。

## 核心方法

Tintin 由三个内核组件构成:

1. **Tintin-Monitor**:在测量事件计数的同时估计 uncertainty。ground truth 运行时不可得,所以用 incremental variance 做代理,低开销追踪每个事件的波动。uncertainty 通过 user-space 接口返回给应用——据作者说这是第一个把不确定性反馈给上层的 profiling 工具。
2. **Tintin-Scheduler**:把多路复用问题形式化为**多 HPC 的弹性实时调度**,目标是最小化总体 uncertainty。证明了最优性,并给出拟线性时间的构造算法;除此之外还支持简单的 Uncertainty-First 优先级调度。
3. **Tintin-Manager**:提出 **Event Profiling Context (ePX)** 作为一等 OS primitive,把「profiling scope」从 task/core 绑定中解放出来——ePX 可以是代码区域、VM、多任务集合等任意粒度。多个 ePX 重叠时由 Manager 统一调度,避免 starvation。对代码区域 ePX 通过 syscall 插桩触发 switch,对执行实例 ePX 通过监听 CPU 调度事件触发 switch。

接口上扩展了 Linux `perf_event` API,向后兼容现有工具链。

## 关键结果

- Pond(云资源 latency-sensitivity 预测):accuracy 比用 Intel EMON 的 baseline **提高 64%**(平均 0.51)。
- Diamorphine rootkit 分类(入侵检测):AUC 提升 **22.8%**。
- DMon(数据局部性诊断):借助灵活 ePX 可「一键」完成,不再需要手动调 top-down 层级的时间窗。
- SPEC 2017 / PARSEC:多路复用事件插值精度 **3.09×** 于 state of the art;runtime overhead 约 **2–4%**,scope 冲突场景下仍 <2.4%。

## 相关

- **相关概念**:performance counter、elastic real-time scheduling、`perf_event`、Top-Down methodology
- **同类工作**:Linux `perf_event`、Intel EMON / VTune、PAPI、DMon、Pond
- **同会议**:[[OSDI-2025]]
