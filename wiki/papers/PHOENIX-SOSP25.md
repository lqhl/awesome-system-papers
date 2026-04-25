---
type: paper
name: PHOENIX
full_title: "Optimistic Recovery for High-Availability Software via Partial Process State Preservation"
authors: [Yuzhuo Jing, Yuqi Mai, Angting Cai, Yi Chen, Wanning He, et al.]
venue: SOSP
year: 2025
tags: [high-availability, recovery, fault-tolerance, os, static-analysis]
source_pdf: "[[3731569.3764858.pdf]]"
source_md: "[[3731569.3764858]]"
---

# Optimistic Recovery for High-Availability Software via Partial Process State Preservation (SOSP 2025)

> **一句话总结**:在"完全重启(慢但对)"与"checkpoint 恢复(快但带 bug)"之间开辟中间地带——选择性保留大而稳的长期状态、丢弃短命 transient 状态并重置执行,把 Redis 等服务的恢复+warmup 从半小时缩到亚秒级,85.6% 注入故障可走 fast path 且无额外损坏。

## 问题

高可用要求"快 + 对"。完全 process restart 正确但要重建所有状态(Redis 从 6 GB RDB 恢复 53.5s,warmup 361.7s);CRIU 之类的 checkpoint 快但若 bug 已写入快照则带回问题;journaling 重放缓慢;microreboot/Orleans 要重构应用。

## 核心方法

**两个核心 insight**:
1. 大多数生产故障(研究 64 个真实 bug,87.5%)只污染 transient 状态(局部变量/短命堆对象),不碰稳定的大块 global 数据。
2. Bug 与字节分布不对称——bug 集中在少量复杂代码,字节集中在简单良测过的大数据结构。

**PHOENIX-mode restart 设计**:
- 新增 fast path 与原有默认恢复(如 log replay)并存。开发者通过简单 API annotate 要保留的 state。
- 重启时:保留被注解的 long-lived state(跨进程迁移),丢弃其余 transient,从 `main` 重新初始化未保留部分。
- **Unsafe region detection**:静态识别正在修改 preservable state 的代码段,若故障发生在此则 fallback 到 default recovery(避免带着不一致状态起飞)。
- **Cross-check validation**:主进程快速起来服务请求的同时,后台跑 default recovery,对比状态;不一致则切过去。保证最多一小段"潜在错误输出"窗口。
- 实现:Linux kernel 改动 + runtime library + 修改版 glibc + 基于 LLVM 的 compiler tool。

## 关键结果

- 移植到 6 个大服务(Redis、MySQL、Hadoop、MongoDB、Ceph、ElasticSearch),小代码量改动。
- 17 个真实 bug 场景:恢复+warmup 从几十分钟到亚秒级,几乎 100% 恢复性能。
- 随机故障注入:85.6% 走 PHOENIX fast path,其余自动 fallback,无引入额外数据损坏。
- 开源 github.com/OrderLab/phoenix。

## 相关

- **相关概念**:Crash Recovery、Checkpointing、CRIU、Microreboot、Fault Injection
- **同类系统**:CRIU、Orleans、Microreboot、FSCQ
- **同会议**:[[SOSP-2025]]
