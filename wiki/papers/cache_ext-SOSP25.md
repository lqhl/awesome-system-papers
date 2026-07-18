---
type: paper
name: cache_ext
full_title: "cache_ext: Customizing the Page Cache with eBPF"
authors: [Tal Zussman, Ioannis Zarkadas, Jeremy Carin, Andrew Cheng, Hubertus Franke, et al.]
venue: SOSP
year: 2025
tags: [page-cache, ebpf, linux, eviction-policy, memory-management]
source_pdf: "[[3731569.3764820.pdf]]"
source_md: "[[3731569.3764820]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# cache_ext: Customizing the Page Cache with eBPF (SOSP 2025)

> **一句话总结**：Linux [[page cache]] 固定 LRU 类策略对 scan/ML/DB 等异构 workload 次优，而改 kernel 代价极高；cache_ext 用 [[eBPF]] struct_ops 在 kernel 内跑可定制 eviction policy（per-[[cgroup]] 隔离），generic policy 吞吐最高 +38%，application-informed policy 最高 1.70× 吞吐且 P99 延迟降 58%。

## 问题与动机

四十年來 page cache 仍是 approximate LRU，但 workload 高度异构（大 scan、multi-core、ML training/inference）。Linux [[MGLRU]] 等 upstream 缓慢且仍 one-size-fits-all；userspace cache 难跨进程共享且需预设容量。[[P2Cache]]、PageFlex、FetchBPF 等并发工作分别限制队列形态、聚焦 swap/prefetch 或仅 prefetch，无法表达 LFU/ARC/LHD/S3-FIFO 等多队列复杂策略。

现代 SSD 百万 IOPS 要求 policy 必须在 kernel 内低开销执行——userspace event dispatch  alone 即可带来 **16–20%** 吞吐损失（论文 Table 1）。

## 关键观察 / 隐含假设

- **观察 1**：eviction policy 事件率与 I/O 率同量级，policy 必须在 kernel 执行，userspace offload 不经济。
  - **依赖假设**：eBPF verifier 允许足够表达力的 list/map 操作在预算内完成。
  - **可能失效场景**：极复杂 ML-based policy 可能触 verifier 指令上限或 latency spike。
- **观察 2**：多数先进 eviction 算法可映射为「一个或多个可变长 linked list + per-folio score」。
  - **依赖假设**：folio-level list API + iterate kfunc 足以近似 LHD/S3-FIFO 等。
  - **可能失效场景**：需全局复杂索引结构的政策可能需多次 kernel 修改扩展 API。
- **观察 3**：per-cgroup page list 已是天然多租户边界，custom policy 可按 cgroup 隔离且仍共享 physical page cache。
  - **依赖假设**：应用愿用 cgroup 绑定 policy；跨 cgroup 访问只影响 metadata 不计入 quota 的语义可接受。
  - **可能失效场景**：未放 cgroup 的 legacy 部署只能全局默认 policy。
- **假设 1**：folio reference registry 可阻止恶意/错误 policy 返回非法 eviction candidate。
  - **证据强度**：强。registry 是明确 safety 机制；但 verifier+registry 组合的正确性依赖 kernel 集成质量。

## 核心方法

cache_ext 通过 struct_ops 暴露五类 hook：policy_init、evict_folios、folio_added、folio_accessed、folio_removed。Policy 操作 **eviction lists**（eBPF kfunc：list_create/add/move/del/iterate），向 kernel 批量提交至多 32 个 eviction candidates；kernel 仍保有真实 folio 存储。

按 cgroup 加载 policy；实现 LHD、S3-FIFO、MGLRU、LFU、MRU 等，并支持 application-informed policy（如区分 point query vs scan、按 thread admission filter）。~200 行 core page cache 修改。

## 设计取舍

- **Kernel eBPF vs userspace policy**：保性能，受 verifier 表达力与 debuggability 限制。
- **List-centric API vs 任意数据结构**：易验证、易实现，部分 policy 只能近似。
- **Per-cgroup isolation vs global optimum**：避免 tenant 互相干扰，但失去全局最优替换。
- **Registry validation**：安全开销 vs 完全信任 custom policy。

## 实验与结果

- Userspace-dispatch baseline（无 policy）：YCSB/RocksDB 吞吐降 **16.6–20.6%**，ripgrep 慢 **4.7%**。
- Generic custom policies：吞吐最高 **+38%** vs default LRU/MGLRU/fadvise。
- Application-informed policies：最高 **1.70×** 吞吐、**58%** lower P99 latency。
- 实现 8 种 policies；admission filter 扩展仅 **15** 行 verifier 相关代码。

## Critical Analysis

### 论证链条

「LRU 不够 + kernel 难改 + SSD 要低开销」→ eBPF in-kernel list API → 多 workload 提升，链条闭合。未证明所有重要 workload 都能从 customization 获益——论文自己也强调 no one-size-fits-all。

### 假设压力测试

- eBPF 指令/栈限制可能阻挡更重 policy（如学习型 eviction）。
- 需 cgroup v2 等部署前提；裸机 legacy app 可能难 adopt。
- folio→list node hash 表开销随 cache 大小增长——大规模内存下 scalability 需更多数据。

### 实验可信度

- Baseline 含 MGLRU、fadvise、YCSB、ripgrep 等，较公平。
- 与 P2Cache/PageFlex 定性对比充分，但 head-to-head 数字有限（§7 related work）。
- 缺少 multi-tenant 干扰、security adversarial policy 测试。

### 系统性缺陷

- 论文未讨论 policy bug 导致性能崩溃或 livelock 的运维回滚 story。
- 与 io_uring/direct IO 旁路 page cache 的趋势未深入讨论。

## 局限与 Future Work

- **局限**：verifier 表达力；list API 对 exotic policy 的近似误差；依赖 cgroup 部署。
- **Future work**：更丰富 eBPF map 结构；自动化 policy 选择；与 MGLRU upstream 协同维护。

## 相关

- **相关概念**：[[eBPF]]、[[Page-Cache]]、[[cgroup]]、[[sched_ext]]、LRU、MGLRU
- **同类系统**：P2Cache、PageFlex、FetchBPF、[[sched_ext]]
- **同会议**：[[SOSP-2025]]
