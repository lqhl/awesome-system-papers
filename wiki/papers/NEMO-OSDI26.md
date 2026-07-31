---
type: paper
name: NEMO
full_title: "Finding NEMO: Nimble and Expressive Memory Observability"
authors: [Shihang Li, Matthew Giordano, Tushar Garg, Rohan Kadekodi, Daniel S. Berger, et al.]
venue: OSDI
year: 2026
tags: [memory-management, cxl, hardware-telemetry, memory-tiering, noisy-neighbor]
source_pdf: "[[osdi26-li-shihang.pdf]]"
source_md: "[[osdi26-li-shihang]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 灵活可编程的内存可观测性（OSDI 2026）

> **原题**：Finding NEMO: Nimble and Expressive Memory Observability

> **一句话总结**：NEMO 在memory controller数据路径加入可编程filter→counter mapping→state update规则，使OS按policy直接获得page/tenant级telemetry；FPGA CXL prototype让HeMem hot-set反应快5×、MEMTIS THP split快10.4×、noisy-neighbor检测overhead低350×，应用最高1.7× throughput。

## 问题与动机

CXL与multi-tier memory要求OS持续判断hot pages、huge-page内部稀疏访问和tenant bandwidth。PTE accessed-bit扫描coverage高但CPU/latency昂贵，PMU sampling轻量但不精确，固定memory-controller counter只能给channel/bank aggregate。不同policy需要不同granularity/filter/state，固定hotness tracker难随datacenter需求演化。

## 关键观察 / 隐含假设

- memory controller看见所有memory operations，是低overhead、完整coverage的天然观察点。
- 多数management telemetry可表达为匹配address/request attributes、映射到region counter、执行简单update；无需通用processor。
- OS只需policy-specific compressed state/notification，而非逐access event流，能避免CPU polling与bandwidth。
- 规则与translation必须跟上page migration/remap；physical-address attribution由kernel/hypervisor可信维护。

## 核心方法

NEMO rule声明过滤哪些read/write/tenant/address access，如何将其映射到有限counter region，以及对per-counter state执行increment/max/bitmap等简单更新。OS driver动态安装rule/translation、读取counter或订阅threshold notification。match-update pipeline以固定硬件成本处理memory requests，不阻塞普通access。

作者在FPGA-based CXL-attached memory expander实现prototype，并把NEMO接入三个现有policy：HeMem hot/cold tiering、MEMTIS的THP内部hotness/split，以及Linux per-tenant bandwidth/noisy-neighbor control。

## 实验与结果

- HeMem对hot-set change反应快5×，减少错误tier placement并使KV/database throughput最高1.7×。
- MEMTIS huge-page split触发快10.4×，应用latency最高降低23%。
- noisy-neighbor attribution相对Linux MBM polling以350×更低CPU overhead检测；高频MBM polling可占超过30% CPU，而NEMO notification避免持续扫描。
- 三类use case覆盖hotness、[[Sparse-Attention|sparsity]]与bandwidth attribution，证明rule abstraction不局限单一fixed function。

## 论断—证据表

| 论断 | 证据 | 边界 | 置信度 |
|---|---|---|---|
| controller-side programmable telemetry更及时 | HeMem/MEMTIS experiments | FPGA CXL prototype | 强 |
| 显著降低OS观测CPU开销 | noisy-neighbor/MBM | 指定tenant setup | 强 |
| telemetry质量改善应用性能 | KV/database results | 三个policy | 强 |
| rule abstraction足够通用 | 三类case study | 非任意复杂telemetry | 中 |

> **证据定位**：端到端结果与组件消融见 §6。

## 批判性分析

### 论证链条

NEMO不是又一个tiering policy，而是让多个policy共享可编程观测substrate；三个性质不同的case很好地支持abstraction价值，且最终应用指标证明更快telemetry确实能影响control quality。

### 假设压力测试

有限SRAM counter在TB级内存/4KB granularity下无法全覆盖，仍需region sweep或sampling；uniform coverage的reaction time受DRAM:SRAM ratio约束。FPGA pipeline与real CPU memory controller timing/area/power并不等价。physical-to-tenant translation频繁变化会增加control overhead与stale attribution。

### 实验可信度

实验数据支持主要设计论断，但平台与工作负载范围仍限制其普遍性。

### 系统性缺陷

需要修改memory controller/CXL device，短期部署依赖vendor adoption。可编程rule也形成共享硬件资源，multi-tenant policy之间需隔离、配额和安全验证。论文主要评价性能，缺少area/power、counter overflow与malicious rule分析。

## 局限与后续工作

- ASIC综合并报告area/power/critical-path，对比真实CXL controller。
- 设计多tenant rule isolation、counter quota与verifier，防止泄漏access pattern。
- 研究counter有限时的adaptive region allocation与telemetry error bound。

## 相关

- **相关概念**：[[CXL]]、[[Memory-Tiering]]、[[Hardware-Telemetry]]、[[Huge-Pages]]、[[Noisy-Neighbor]]
- **相关系统**：[[HeMem]]、[[MEMTIS]]、[[Intel-MBM]]
- **同会议**：[[OSDI-2026]]
