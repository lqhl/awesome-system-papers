---
type: paper
name: Tigon
full_title: "Tigon: A Distributed Database for a CXL Pod"
authors: [Yibo Huang, Haowei Chen, Newton Ni, Yan Sun, Vijay Chidambaram, Dixin Tang, Emmett Witchel]
venue: OSDI
year: 2025
tags: [distributed-database, cxl, transaction, cache-coherence, memory]
source_pdf: "[[osdi25-huang-yibo.pdf]]"
source_md: "[[osdi25-huang-yibo]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-17
---

# Tigon: A Distributed Database for a CXL Pod (OSDI 2025)

> **一句话总结**：Tigon 在 CXL CAT 上协调跨主机活跃元组，并用软件协议处理大数据区；它不以原子操作“替代 2PC”。TPC-C 的 60/90 remote-transaction 设置中，最高比 DS2PL+ **2.5×**、比 Motor **15.9–18.5×**，但 0/0 remote 时 Tigon 落后 Sundial+/DS2PL+。

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

**指标、基线与边界**：transaction throughput、scaling、migration/bandwidth、latency；Tigon vs Sundial+/DS2PL+/Motor/NoSWcc；TPC-C remote ratios、YCSB 95R/5W、最多 8 hosts（§4）。

- TPC-C 60/90：vs Sundial+ 高 **75%**、vs DS2PL+ **2.5×**、vs Motor **15.9–18.5×**；0/0 时 Sundial+/DS2PL+ 比 Tigon 快 **37%/8.5%**（§4.2，Fig.4）。
- 1→8 hosts：TPC-C **5.7×**、YCSB **3.5×**；Sundial+/DS2PL+ 分别为 2.4/2.1 与1.4/1.5×（§4.2，Fig.6）。
- TPC-C HWcc=50MB 比 unlimited 慢 **5.8%**；10MB、60/90 每秒迁移 **16K** tuples、CXL bandwidth **367MB/s**（§4.3，Fig.7）。
- YCSB 100% multi-partition 中 NoSWcc 比 Tigon 慢 **4.3×**；TPC-C 60/90 慢 **19%**（§4.4，Fig.8）。

## Claim–Evidence Map

| Claim | Evidence | Metric / baseline / evaluation boundary | Locator | Confidence |
|---|---|---|---|---|
| 多分区 TPC-C 可提升但非所有 workload | 75%、2.5×、15.9–18.5×；0/0反例 | specified remote ratios；vs Sundial+/DS2PL+/Motor | §4.2，Fig.4 | high |
| 扩展性仅测至 8 hosts | TPC-C5.7×、YCSB3.5× | TPC-C60/90、YCSB95R/5W 100% multi-partition | §4.2，Fig.6 | high |
| HWcc 预算取决于 workload | 50MB -5.8%；10MB 16K tuples/367MB/s | TPC-C；YCSB满性能需100MB | §4.3，Fig.7 | high |
| SWcc 对高跨分区负载有贡献 | NoSWcc 4.3×/19% slower | YCSB/TPC-C specified configurations | §4.4，Fig.8 | high |
| epoch 是吞吐/延迟取舍 | 10ms vs50ms throughput -2.8%、p50 latency -48% | no-multi-partition TPC-C；logging comparison | §4.5，Table 1 | high |

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
