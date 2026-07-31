---
type: concept
aliases: [EC, Erasure-Code]
last_updated: 2026-07-30
tags: [storage, reliability, distributed-systems, coding]
---

# Erasure Coding

> 纠删码（Erasure Coding）用少量校验块替代多副本，在给定故障模型下以编码、修复流量和恢复复杂度换取更低存储开销。

## 核心思想

一个 `(n,k)` 码把 `k` 个 data chunk 编成 `n-k` 个 parity chunk，任意满足码性质的 `k` 块可恢复原数据。Reed–Solomon 提供 MDS 可靠性但修一块常需读取大量 helper；LRC 增加局部校验降低修复成本；MSR/vector code 进一步降低修复流量，却引入 sub-packetization、系数搜索与稠密编码计算。

## 为什么重要

大规模存储的容量成本、HDD IO wall、网络修复带宽和故障恢复时间都由编码选择共同决定。[[WiseCode-OSDI26]] 说明理论最优不等于可部署：100-data-chunk 宽条带下，向量码若不能控制 sub-packetization、构造时间和编码 CPU，低修复流量并不会转化为系统收益。[[DINGO-OSDI26]] 则从调度侧说明，scrubbing、reconstruction 等编码维护 I/O 还能跨任务对齐复用。

## 关键观察 / 隐含假设

- **单块故障主导 degraded 时间，但相关多盘故障决定尾部风险。** [[WiseCode-OSDI26]] 引用生产数据，单 failure 占 98% 以上；其宽条带优化因此优先单块修复。
- **低存储开销会扩大 repair fan-in。** 条带越宽，scalar code 修复需触达更多节点；vector code 可降流量，却可能产生指数级 sub-packetization。
- **编码与修复调度是可组合而非替代关系。** WiseCode 可接入 RepairBoost；[[DINGO-OSDI26]] 可把 reconstruction 与其他维护扫描按 deadline 对齐。
- **隐含假设**：failure 近似独立、repair rate 稳定、chunk placement 能分散相关故障；rack/firmware 级相关故障会削弱平均 MTTDL 模型。

## 设计空间与取舍

- **副本、RS、LRC 与 MSR/vector code**：依次在实现简单性、容量、修复 locality 与构造复杂度间移动。
- **窄条带与宽条带**：宽条带把存储开销压近 1，却增加 fan-in、placement 与 degraded-read 成本。
- **编码计算与网络流量**：稀疏/两阶段编码减少 CPU，但可能增加 intermediate buffer 与实现复杂度。
- **repair scheduling**：centralized、cooperative 或 relay repair 能提高吞吐，却可能损害单请求 degraded-read latency。
- **维护 I/O 协同**：声明 deadline 和数据集合可复用读取，但要求任务 API、不可变 block 与集中 planner。

## 引用本概念的论文

- [[WiseCode-OSDI26]] — 以模板展开、分治系数验证和两阶段编码将向量码扩到 100-data-chunk 宽条带
- [[DINGO-OSDI26]] — 跨 reconstruction、scrubbing 等任务对齐维护读，在 100 PB 仿真中减少 28%–51% 维护 I/O
- [[McQueen-FAST26]] — 编码存储与恢复路径
- [[LESS-FAST26]] — 低开销编码存储设计
- [[DRBoost-FAST26]] — 修复优化
- [[DisCoGC-FAST26]] — 编码系统中的回收与维护
- [[TapeOBS-FAST26]] — 归档/磁带可靠性设计
- [[GhostServe-MLSys26]] — serving 场景中的冗余与容错

## 已知局限 / 开放问题

- 相关故障、维修排队和 placement drift 下的可靠性模型与平均独立故障模型差距仍大。
- 宽条带在网络提速后可能从带宽瓶颈转为 HDD 随机 I/O、CPU 或 tail degraded-read 瓶颈。
- 编码参数、repair policy 与 workload deadline 的联合优化缺少统一接口和 production trace。
- 新码从论文原型进入 Ceph/HDFS 等成熟系统时，升级、兼容和数据迁移成本常未计入。
