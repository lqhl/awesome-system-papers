---
type: paper
name: MoonBright
full_title: "MoonBright: A GPU Memory Allocator with Device-Side Page Table Materialization and Deferred TLB Coherence"
authors: [Yangyu Zhang, Lei Chen, Chunwei Xia, Shuaijiang Li, Shuoming Zhang, et al.]
venue: OSDI
year: 2026
tags: [gpu, memory-management, tlb]
source_pdf: "[[osdi26-zhang-yangyu.pdf]]"
source_md: "[[osdi26-zhang-yangyu]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 设备侧页表物化与延迟 TLB 一致性的 GPU 分配器
> **原题**：MoonBright: A GPU Memory Allocator with Device-Side Page Table Materialization and Deferred TLB Coherence

## 问题与动机

现代 GPU kernel 已缩短到微秒级，但动态 allocation、page-table construction 与 TLB shootdown 仍沿 CPU/driver 串行路径执行，VMM mapping 可达毫秒级；pool allocator 虽快，却积累 external fragmentation。

## 关键观察 / 隐含假设

- 页表批量构造适合 GPU 数据并行，validation 与 metadata authority 仍可留在 host。
- 新映射使用 fresh virtual address，就不存在同地址 stale TLB entry。
- 假设虚拟地址空间足够宽裕，地址回收不在常见路径。

## 核心方法

[[MoonBright]] 将 bulk page-table materialization 搬到 device side；Always-Fresh allocation protocol 延迟 TLB coherence，只在地址真正复用时处理 shootdown。方案无需 GPU hardware modification，支持 NVIDIA 与 AMD commodity GPU。

## 实验与结果

MoonBright 将 mapping latency 最高降低 3 个数量级，并在 [[LLM|LLM]] inference 中把 TTFT 最高改善 8.2×（§7，图 14）；同时缓解长寿命、混合大小 allocation 的 external fragmentation。边界是可采用 low-level VMM 的 workload。

## 论断—证据表

| 论断 | 证据 | 边界 | 置信度 |
|---|---|---|---|
| CPU control path 主导动态映射成本 | page-table 与 permission 占总延迟 80–99% | §2 | 强 |
| device materialization 改善端到端服务 | mapping 最高 1000×、TTFT 8.2× | §7 | 强 |

## 批判性分析

### 论证链条
设计分别消除页表构造串行性和常见路径 shootdown，直接对应 profile 中的两个成本源。

### 假设压力测试
虚拟地址耗尽、频繁地址复用、共享映射及多进程隔离会迫使 deferred coherence 提前兑现成本。

### 实验可信度
跨 NVIDIA/AMD 与端到端 LLM 结果增强普适性，但 driver integration 和长期地址空间压力仍需生产验证。

## 局限与后续工作

- 可研究地址回收策略、multi-GPU coherence、security isolation，以及与 framework caching allocator 的联合策略。

## 相关

- [[OSDI-2026]]
- [[GPU-Memory]]
- [[TLB]]
