---
type: paper
name: Atropos
full_title: "Mitigating Application Resource Overload with Targeted Task Cancellation"
authors: [Yigong Hu, Zeyin Zhang, Yicheng Liu, Yile Gu, Shuangyu Lei, et al.]
venue: SOSP
year: 2025
tags: [overload-control, resource-contention, task-cancellation, slo, tail-latency]
source_pdf: "[[3731569.3764835.pdf]]"
source_md: "[[3731569.3764835]]"
---

# Mitigating Application Resource Overload with Targeted Task Cancellation (SOSP 2025)

> **一句话总结**:当应用级资源(buffer pool、table lock 等)过载时,主动找出**监占资源的元凶请求**并触发应用自带的 cancel 机制(而非丢弃受害请求),在 16 个真实 overload 场景下维持 96% 基线吞吐、P99 仅 1.16×、drop rate <0.01%。

## 问题

现代系统跑满带宽时一波流量尖峰就会引爆 SLO 违约。传统 overload control 看全局信号(队列长度、排队延迟,如 Breakwater、Protego)并做 admission control/drop,但 application-level 资源过载由**少数重量请求**引发——比如 MySQL 里 0.01% 的 dump 查询能把 QPS 从 25K 打到 12K;一个 backup 查询撞上长 scan 就让 table lock 被长时间占着。global signal 不知道是哪个请求在作怪,只能盲丢一堆受害请求。性能隔离(pBox)又不能中断正在执行的请求。

## 核心方法

Atropos 换一个思路:**允许请求先跑,观察实际行为,估算资源影响,选择性取消元凶**。

1. **抽象**:所有工作(用户请求 + 后台任务)都注册为 **cancellable task**。开发者用 `createCancel`/`freeCancel` 定义范围、`setCancelInitiator` 注册应用自带的安全取消函数指针。
2. **应用资源抽象**:统一封装 buffer pool、table lock 等资源,对外暴露两个指标——**contention level**(资源争用程度)和 **resource gain**(取消某请求可释放多少负载)。
3. **运行时**:Runtime Manager 持续按 cancellable task 归因资源占用;当 overload 探测器发现 SLO 即将违反,Estimator 基于历史占用预测每个任务的 resource gain;Policy Engine 在多资源间平衡选出"取消收益最大"的任务;然后调用它注册的 cancellation initiator 让应用走自己的 safe cancel 路径。
4. **可用性**:作者调研 151 个主流应用发现 **76% 已有自定义 cancel 逻辑**(Go Context、Java `interrupt()`、C# CancellationToken、C++20 `stop_token`、pthread_cancel 等),95% 带 initiator 入口。Atropos 直接复用这些入口,避免自己重造危险的中断机制。

在 C/C++、Java、Go 上都实现了,接入了 MySQL、Apache、PostgreSQL、Elasticsearch、Solr、etcd 六个大型系统。

## 关键结果

- 16 个真实 overload 场景,**96%** 基线吞吐维持,P99 tail latency 仅 **1.16×**,request drop <**0.01%**。
- 显著优于 Protego(state-of-the-art overload control)、pBox(性能隔离)、DARC(请求感知调度)。
- 151 应用调研:76% 有 cancel 支持,95% 有 built-in initiator。

## 相关

- **相关概念**:[[Overload-Control]]、[[Tail-Latency]]、[[SLO]]、[[Task-Cancellation]]、[[Resource-Contention]]
- **对比系统**:Breakwater、Protego、pBox、DARC
- **同会议**:[[SOSP-2025]]
