---
type: paper
name: Nixie
full_title: "Nixie: Efficient, Transparent Temporal Multiplexing for Consumer GPUs"
authors: [Yechen Xu, Yifei Wang, Nathanael Ren, Yiran Chen, Danyang Zhuo]
venue: OSDI
year: 2026
tags: [gpu, memory-management, multiplexing]
source_pdf: "[[osdi26-xu-yechen.pdf]]"
source_md: "[[osdi26-xu-yechen]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 消费级 GPU 的透明时间复用
> **原题**：Nixie: Efficient, Transparent Temporal Multiplexing for Consumer GPUs

## 问题与动机

消费级设备同时运行多个几乎占满显存的 ML 应用时，UVM 会抖动，完全 pin 到 CPU memory 又缺乏隔离和优先级。用户需要前台交互应用抢占后台长任务，但不能要求修改应用或驱动。

## 关键观察 / 隐含假设

- 应用工作集可以按时间切换，而非同时常驻 GPU。
- [[PCIe|PCIe]] 双向带宽和 pinned memory 可由全局服务统一利用。
- 假设 kernel launch 可被透明协调，且交互任务可被分类。

## 核心方法

Nixie 作为系统服务统一协调显存分配、迁移与 kernel launch；采用双向交换和受控 pinned memory 降低切换代价，并以 MLFQ 让短交互作业优先于长后台作业。

## 实验与结果

代码补全与长运行 [[LLM|LLM]] 共置时，交互延迟最高改善 3.8×；相同延迟下 CPU pinned memory 最高减少 66.8%，多应用组合获得 1.3–1.6× speedup（§6，图 10）。边界是单机消费级 GPU 和可时间复用的应用。

## 论断—证据表

| 论断 | 证据 | 边界 | 置信度 |
|---|---|---|---|
| 协调切换优于 UVM 无序换页 | 多应用 speedup 为 1.3–1.6× | §6 | 强 |
| 交互优先级不必靠大量 host pinning | 延迟改善 3.8×、pinned memory 减少 66.8% | 图 10 | 强 |

## 批判性分析

### 论证链条
论文将容量冲突转化为时间调度问题，并把迁移与 kernel admission 放在同一控制面。

### 假设压力测试
频繁细粒度共享、强并发 kernel 或无法安全暂停的应用会破坏时间隔离假设。

### 实验可信度
涵盖多种应用组合并同时报告延迟和内存，但消费 GPU 型号及 PCIe 代际可能显著影响结论。

## 局限与后续工作

- 后续可研究多 GPU、统一 QoS 接口、显存数据安全清理与不可抢占 kernel 的最坏延迟。

## 相关

- [[OSDI-2026]]
- [[GPU-Memory]]
- [[Resource-Multiplexing]]
