---
type: paper
name: Rakaia
full_title: "Rakaia: Scalable In-Kernel Scheduling for TCP-Based RPCs"
authors: [Rui Yang, Konstantinos Prasopoulos, Edouard Bugnion]
venue: OSDI
year: 2026
tags: [rpc, tcp, kernel, scheduling, head-of-line-blocking]
source_pdf: "[[osdi26-yang-rui.pdf]]"
source_md: "[[osdi26-yang-rui]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# TCP RPC 的可扩展内核内调度（OSDI 2026）

> **原题**：Rakaia: Scalable In-Kernel Scheduling for TCP-Based RPCs

> **一句话总结**：Rakaia在TCP receive path最早位置解析message boundary并work-conserving分发，向userspace隐藏stream/I/O-thread/queue；throughput-under-SLO相对KCM最高5×，gRPC-Go/C++最高1.56×/2.69×。

## 问题与动机

POSIX TCP只暴露bytes，RPC framework须I/O thread重组message再交worker，既有单connection内HOL，也有connection-to-core imbalance与context-switch overhead。

## 关键观察 / 隐含假设

- kernel TCP receive已看到完整byte ordering，是最早恢复RPC boundary的位置。
- message-level scheduler能跨connections分配ready RPC而不等慢消息。
- protocol framing可安全在kernel解析，且TLS需kTLS配合。

## 核心方法

Linux module在receive path增量parse configured RPC framing，形成message descriptors并直接调度到available worker；message API替代userspace stream plumbing。支持kTLS和现有TCP stack，gRPC adapter保留application semantics。

## 实验与结果

- **设置**：多connection microbenchmarks、gRPC-Go/C++、Silo TPC-C/OpenTelemetry，对比KCM与stock gRPC，以throughput-under-SLO/tail latency为指标（§5）。
- 相对KCM最高5×，gRPC-Go 1.56×、C++ 2.69×；跨connection counts消除HOL。

## 论断—证据表

| 论断 | 证据 | 边界 | 置信度 |
|---|---|---|---|
| kernel message scheduling减少HOL | §5 | TCP RPC framing | 强 |
| real apps收益 | Silo/OTel | 所测protocols | 中 |

## 批判性分析

### 论证链条

将message semantics下沉与HOL/context switch根因一致，多个framework结果支持。

### 假设压力测试

复杂/动态 framing、encrypted userspace TLS或malicious length会增加kernel attack surface；慢handler仍会占worker。

### 实验可信度

micro到applications完整，但kernel module维护、安全审计和多协议覆盖有限。

## 局限与后续工作

- [[eBPF|eBPF]]/verified parser、QUIC与多tenant isolation。
- malformed input fuzzing与production tail。

## 相关

- **相关概念**：[[RPC]]、[[TCP]]、[[Head-of-Line-Blocking]]、[[Kernel-Bypass]]
- **相关系统**：[[gRPC]]、[[KCM]]
- **同会议**：[[OSDI-2026]]
