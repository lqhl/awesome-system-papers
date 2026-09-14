---
type: paper
name: MAC
full_title: "MAC: Metadata Acceleration for Sustainable Performance in Big-Data Systems with CXL DRAM"
authors: [Dusol Lee, Yan Sun, Houxiang Ji, Vinit Gupta, Austin Antony Cruz, Inhyuk Choi, Nam Sung Kim, Jihong Kim]
venue: OSDI
year: 2026
tags: [cxl, memory-management, near-memory-processing, tail-latency, page-reclamation]
source_pdf: "[[osdi26-lee.pdf]]"
source_md: "[[osdi26-lee]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-09-14
---
# 面向 CXL DRAM 的内核元数据加速（OSDI 2026）

> **原题**：MAC: Metadata Acceleration for Sustainable Performance in Big-Data Systems with CXL DRAM

> **一句话总结**：CXL DRAM 扩容后，page descriptor 与 Xarray 元数据落到高延迟内存会拖慢 kswapd 并诱发前台回收；MAC 将这两类规则化遍历卸载到 CXL 侧 NMP，在数据库工作负载上把 p99.99 尾延迟最多降低 98%。

## 问题与动机

CXL DRAM 扩大容量，却把部分 Linux 内存管理元数据放到了远端、CPU-less 节点。page reclamation 反复读取 page descriptor，并沿 Xarray 删除 page-cache 项；这些访问位于回收路径上。后台回收变慢后，应用线程会在 I/O 关键路径执行 foreground reclamation。

论文测得元数据访问延迟增加约 2.4× 时，p99.99 延迟增加约 2.8×，foreground reclamation 频率增加 6.5×（图 2）。因此，单纯把元数据固定在 DDR 会与应用数据争抢容量，也不是稳妥方案。

## 关键观察 / 隐含假设

- **观察 1**：Xarray 与 page descriptor 的容量随数据集和物理内存增长；1.8 TiB 文件、120 GiB 内存的 RocksDB 实验中元数据约 5.7 GiB（§3.1）。
  - **依赖假设**：大文件、文件型 page cache 和较高 CXL:DDR 比例是主要工作负载。
  - **可能失效场景**：匿名内存占主导、元数据较小或工作集长期驻留时，收益会下降。
- **观察 2**：回收中的元数据操作主要是位检查、地址计算和 Xarray 遍历，批次至少包含 32 个页面，适合近内存并行处理（§3.2）。
  - **证据强度**：强；论文同时给出内核路径拆解和 FPGA 验证。
- **假设 1**：元数据可安全放置在 CXL DRAM，且 CXL.cache 一致性、锁持有和设备侧写入能与 Linux 回收语义兼容。该假设在原型中以延迟模型和 FPGA 替代实现验证，真实支持 BIsnp 的 CXL 设备尚未普及。

## 核心方法

MAC 将 page descriptor traversal 和 Xarray walk 卸载给 CXL DRAM 内的 NMP 加速器。主机按 CPU core 分配 MAC_buf，写入 descriptor 地址、Xarray 头指针、页索引和 shadow 值，再以普通 CXL.mem MMIO 写入 MAC_cmd 启动任务（图 5）。这样无需修改 CPU 的 CXL 协议栈。

MAC-S 使用少量加速器，MAC-P 使用 32 个加速器并行处理批次。Xarray 写入带来 cache coherence 成本，MAC 将 Xarray walk 与 BIsnp、以及主机执行的 unmap/writeback 工作重叠（§4.4–§4.5）。主机继续负责控制流复杂的 rmap、统计更新和锁管理。

## 设计取舍

- **取舍**：把元数据放入容量充足的 CXL DRAM，释放 DDR 给应用数据，但依赖设备侧计算、共享缓冲区和一致性协议。
- **边界条件**：读 descriptor 易于并行；Xarray 修改必须同步缓存。当前 FPGA 不支持设备发起的 BIsnp，论文用 host-biased coherent write 代替，CXL 3.x 的真实开销仍需硬件验证。

## 实验与结果

- RocksDB/YCSB 读负载、DDR:CXL=1:2 时，MAC-S/MAC-P 的 p99.99 比 Baseline 分别降低 97%/98%（图 11）。MAC-P 的 Xarray walk 开销降低 80%，foreground reclamation 降低 66%（图 12）。
- RocksDB 50/50 读更新负载中，MAC-P 将 update 的 p99.99 降低 52%，吞吐比 Baseline 高 10%（图 13）。
- PostgreSQL OLTP、DDR:CXL=1:2 时，MAC-P 将发生 foreground reclamation 的请求数降低 88%，p99.99 降低 92%，TPS 最多提高 5%（图 14）。
- LMDB GET 中，MAC-P 将 unmap 与 Xarray walk 重叠，使回收时间比 Baseline 降低 42%（图 17）。
- Intel Agilex 7 FPGA 原型中，Xarray walk 和 descriptor traversal 分别降低 82%/48%，端到端 kswapd 回收时间降低 30%（图 18）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| CXL 元数据回收开销会放大应用尾延迟 | p99.99 约 2.8×、foreground reclamation 约 6.5×（图 2） | RocksDB、32 cores、受控元数据延迟 | 强 |
| NMP 能加速规则化元数据操作 | FPGA 中 Xarray/descriptor 分别降低 82%/48%（图 18） | 合成结构、深度约 3 的 Xarray | 中 |
| MAC 改善真实数据库尾延迟 | PostgreSQL p99.99 降低 92%，RocksDB 最多 98%（图 11、14） | 1:1–1:4 内存比例、四类数据库 | 强 |

## 批判性分析

### 论证链条

从元数据远端化到 kswapd 变慢，再到前台回收和尾延迟，测量链条是闭合的。MAC-P 的收益同时来自 NMP、DDR 争用缓解和主机协作，单项贡献在不同工作负载中并未完全隔离。

### 假设压力测试

实验主要使用文件 I/O 密集型数据库和固定 DDR:CXL 比例。多租户、匿名页、频繁 Xarray 结构变化、CXL pooling 跨设备放置可能改变锁争用和一致性成本。论文对 CXL 3.x BIsnp 的性能采用模型，不能等同于量产设备结果。

### 实验可信度

论文覆盖 RocksDB、PostgreSQL、Neo4j、LMDB，并同时提供 NUMA 仿真和 FPGA 原型。Baseline-P 的 DDR-only 元数据策略会引入 slab 争用，比较揭示了容量与局部性之间的代价，但真实 CXL 设备上的端到端应用结果仍主要来自仿真。

### 系统性缺陷

论文未量化设备固件复杂度、故障恢复、加速器异常、跨设备迁移和运维可观测性。持有 Xarray 锁并禁止抢占也可能放大异常路径的影响。

## 局限与后续工作

- **局限 1**：FPGA 原型缺少真正的设备发起 BIsnp；一致性收益依赖未来 CXL 设备支持。
- **后续工作 1**：在真实 CXL 3.x 多设备 pooling 上测量 BIsnp、跨设备 Xarray 放置、故障恢复和多租户隔离的 p99.99 延迟。

## 相关

- **相关概念**：[[CXL]]、[[Near-Memory Processing]]、[[Page Cache]]
- **同类系统**：[[M5]]、[[Hermit]]
- **同会议**：[[OSDI-2026]]
