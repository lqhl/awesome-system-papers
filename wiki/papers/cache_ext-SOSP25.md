---
type: paper
name: cache_ext
full_title: "cache_ext: Customizing the Page Cache with eBPF"
authors: [Tal Zussman, Ioannis Zarkadas, Jeremy Carin, Andrew Cheng, Hubertus Franke, et al.]
venue: SOSP
year: 2025
tags: [ebpf, page-cache, linux-kernel, caching, memory-management]
source_pdf: "[[3731569.3764820.pdf]]"
source_md: "[[3731569.3764820]]"
---

# cache_ext: Customizing the Page Cache with eBPF (SOSP 2025)

> **一句话总结**：借鉴 sched_ext 思路，用 [[eBPF]] 让应用程序在 Linux 内核中定义自定义 page cache 淘汰策略——实现了 8 种策略（含 S3-FIFO、LHD、MGLRU、LFU 等），吞吐最多提升 1.70×、P99 降 58%。

## 问题

Linux 的 page cache 淘汰只有一个 one-size-fits-all 的 LRU 近似算法，对扫描密集型、多核、多样 ML/数据库 workload 普遍不够好。改 page cache 又难：

- kernel 代码深、与 memory management + file system 耦合
- 上游接受新策略极慢（Google MGLRU 上游花了多年，至今默认未启用）
- 现有工具不足：`fadvise()` 仅提示、`madvise()` 行为不可控；P2Cache 只支持单个 LRU/MRU 队列；PageFlex 关注 swap/prefetch 不支持 file-based eviction；FetchBPF 只改 prefetch

结果：Linux 的 key-value store、database、ML inference 都被迫要么忍受次优策略要么自建 userspace cache，两头为难。

## 核心方法

cache_ext 用 **eBPF + struct_ops + kfunc** 提供一个让用户在内核里安全跑自定义淘汰策略的框架。核心设计决策：

- **内核内运行**（非 userspace）：现代 SSD 百万 IOPS，user/kernel 同步开销致命；实测 userspace-offload 架构仅 ring buffer 通知就 -16% 到 -20% 吞吐
- **简单而灵活的接口**：用户声明一个或多个 variable-sized folio list + 一组 policy 函数（admission、eviction 等），可表达 LRU/MRU/LFU/MGLRU/LHD/S3-FIFO 等多类算法（含非 LRU、多队列）
- **cgroup 作为 isolation 边界**：每个 cgroup 一套独立策略，多租户不互相干扰
- **合法页引用注册表**：内核维护 valid folio 引用的 registry，policy 返回的 evict 候选会被校验，杜绝 use-after-free/安全漏洞
- **支持 application-informed 策略**：数据库可以让 point query 优先于 scan 的页，或按 thread id 做 admission filter

## 关键结果

- 在 RocksDB、GAP、Twitter cache trace 等多种 workload 上比 Linux 默认 LRU 和 MGLRU 显著好
- "通用"策略（S3-FIFO 等）吞吐提升 **最多 38%**
- **Application-informed** 策略吞吐提升 **最多 1.70×**、P99 尾延迟降 **58%**
- 印证"没有一种策略能包打所有 workload"——customization 本身是必要的
- 开源于 github.com/cache-ext/cache_ext

## 相关

- **相关概念**：[[eBPF]]、LRU、MGLRU、S3-FIFO、LHD
- **同类系统**：P2Cache、PageFlex、FetchBPF、sched_ext
- **同会议**：[[SOSP-2025]]
