---
type: paper
name: Tigon
full_title: "Tigon: A Distributed Database for a CXL Pod"
authors: [Yibo Huang, Haowei Chen, Newton Ni, Yan Sun, Vijay Chidambaram, et al.]
venue: OSDI
year: 2025
tags: [distributed-database, cxl, transaction, cache-coherence, memory]
source_pdf: "[[osdi25-huang-yibo.pdf]]"
source_md: "[[osdi25-huang-yibo]]"
---

# Tigon: A Distributed Database for a CXL Pod (OSDI 2025)

> **一句话总结**：Tigon 把跨主机活跃元组 CAT 放进 CXL 内存，用 HWcc 区放 latch/index、SWcc 协议扩展大数据区，原子操作替代 2PC，TPC-C/YCSB 吞吐比 CXL-transport shared-nothing **2.5×**、比 RDMA 数据库 **18.5×**。

## 问题与动机

分布式事务传统靠网络消息+**2PC**，multi-partition 代价高。RDMA disaggregated memory 延迟仍比本地 DRAM 高 1–2 数量级。CXL pod（8–16 机共享 CXL）可用 load/store + 有限 **HWcc** 做跨机同步，但 CXL 延迟/带宽差于 DRAM，且 HWcc 仅 dozens–hundreds MB。

## 关键观察 / 隐含假设

- **观察 1**：数据库很大，但任意时刻 **CAT**（跨主机并发读写的 tuple 集）很小——TPC-C 平均 39 tuple/txn，千核并发约 39K tuple ≈ 7MB。
  - **依赖假设**：txn 触碰 tuple 数有界；in-memory DB 并发度≈核数。
  - **可能失效场景**：大范围扫描/全表锁导致 CAT 膨胀，CXL 带宽成瓶颈。
- **观察 2**：索引与 latch 需要频繁原子同步 → 放 HWcc；tuple 体可放 SWcc 并用 DB 自身 latch 协议做软件一致性。
  - **依赖假设**：HWcc 容量可装下热索引/metadata；其余靠显式迁移。
  - **证据强度**：强——敏感性实验变 HWcc 大小。
- **假设 1**：单 host 执行 txn 并本地日志即可 durable，索引其他 host 可在恢复时重建，从而避免 2PC。
  - **依赖假设**：fail-stop + 本地 SSD log；恢复逻辑正确实现。

## 核心方法

**Pasha 式分区 + 动态提升**：owner 在 DRAM；跨主机访问时 owner 把 tuple 迁入 CXL CAT。

**Shortcut pointer**：owner 缓存 CXL 中 tuple 位置，减 index 查找。

**增强 2PL + next-key locking + scalable logging**：无 2PC commit。

**SWcc 协议**：与 tuple latch 协同，减少 HWcc↔DRAM 来回。

## 设计取舍

- **取舍 1**：绑定 CXL pod 规模（~16 机），非全球分布式。
- **取舍 2**：显式数据迁移逻辑复杂，换网络消息风暴消除。
- **边界条件**：CAT 过大时 CXL 带宽/延迟劣势显现。

## 实验与结果

- TPC-C & YCSB variant：vs optimized shared-nothing（CXL 作 transport）**2.5×**；vs RDMA DB **18.5×**。
- HWcc 容量敏感性实验验证设计（见 source_md §4）。
- 开源：https://github.com/ut-datasys/tigon

## Critical Analysis

### 论证链条

CXL 低延迟共享内存 → CAT 小 → 原子同步替代 2PC → SWcc 扩展可用容量 → 吞吐大幅提升。链条在 benchmark 闭合；真实 OLTP skew 下 CAT 大小需监控。

### 假设压力测试

- 热点跨分区事务使 CAT 增长，性能可能非线性下降。
- NUMA 测试床代理 CXL 的调参结论迁移到 Niagara 2.0 等真硬件需再验证。
- 索引重建恢复时间在大库上可能成为 RTO 风险。

### 实验可信度

强 baseline（CXL transport SN、RDMA DB）；开源。缺长期 fault-injection 生产故事。

### 系统性缺陷

论文未讨论：CXL 设备故障域、多 pod 扩展、与 [[Disaggregation]] 存储层一致性。

## 局限与 Future Work

- **局限 1**：scale 限于 pod；HWcc 容量硬限制。
- **局限 2**：CAT 膨胀时性能未保证。
- **Future work 1**：无 HWcc 设备的纯 SWcc 路径优化。
- **Future work 2**：自动 CAT 大小监控与降级到 2PC 的混合模式。

## 相关

- **相关概念**：[[Disaggregation]]、Cache Coherence、Two-Phase Commit
- **同类系统**：Calvin、FaRM、HydraRPC、RDMA OLTP
- **同会议**：[[OSDI-2025]]