---
type: concept
aliases: [CXL, Compute Express Link, CXL.mem, CXL.io, CXL.cache, CXL-SSD]
last_updated: 2026-07-30
tags: [memory, disaggregation, interconnect, tiered-memory, datacenter]
---

# CXL

> Compute Express Link（CXL）基于 [[PCIe]] 物理层提供 cache/memory coherent device access，使 memory expansion、pooling 与 near-memory computation 进入统一 load/store fabric。

## 核心思想

CXL.mem 将 Type-3 memory 暴露为较慢的大容量 tier，CXL.cache 允许 device cache host memory，CXL.io 处理 device discovery/control。系统仍需决定 page/object placement、coherence metadata、migration 与 fabric routing；“可寻址”并不意味着与 local DRAM 同性能。

## 为什么重要

OSDI 2026 从容量、带宽与 device pooling 三面推进。[[RamRyder-OSDI26]] 把 CXL capacity 与 local memory-channel bandwidth 分离；[[Megalon-OSDI26]] 面对只有数百 MB hardware-coherent region 的 TB 级 memory，只把小且频繁更新的 coherence record 放入该区；[[Espresso-OSDI26]] 让 SSD 间经 CXL 共享 FTL compute/memory，利用 burst 的统计复用。

[[Soul-OSDI26]] 与 [[Duhu-OSDI26]] 进一步说明：coherence 不应无差别覆盖数据与 metadata，immutable/large object 和 mutable/small record 适合不同机制。

## 关键观察 / 隐含假设

- **观察：coherent-region capacity 可能远小于 pooled memory。** [[Megalon-OSDI26]] 用 replicated index + compact record 解耦两者。
- **观察：capacity 与 bandwidth 是不同资源。** [[RamRyder-OSDI26]] 通过 page-to-channel mapping 分别供给。
- **假设：remote tier 的 latency 可由 cache、batch 或迁移隐藏。** random fine-grained workload 可能使该假设失效。

## 设计空间与取舍

- **Page / object / record granularity**：粗粒度部署简单，细粒度提高利用率但增加 metadata。
- **Hardware coherence / ownership/message passing**：前者透明，后者扩展好却要求软件参与。
- **Static tiering / dynamic migration**：动态策略适应 phase，但会占用 fabric bandwidth。

## 引用本概念的论文

- [[RamRyder-OSDI26]] — CXL capacity 与 memory-channel bandwidth 控制。
- [[Megalon-OSDI26]] — limited coherent region 下的 object coherence。
- [[Espresso-OSDI26]] — CXL-connected SSD resource pooling。
- [[Soul-OSDI26]] — coherence 与 synchronization 的统一。
- [[Demeter-SOSP25]] — guest-delegated tiered memory management。

## 已知局限 / 开放问题

- fabric congestion、failure domain、security 与多租户 QoS 尚缺统一模型。
- 真机规模有限，模拟器结果与 CXL 3.x rack-scale hardware 的差距需持续校准。
