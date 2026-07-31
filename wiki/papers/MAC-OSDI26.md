---
type: paper
name: MAC
full_title: "MAC: Metadata Acceleration for Sustainable Performance in Big-Data Systems with CXL DRAM"
authors: [Dusol Lee, Yan Sun, Houxiang Ji, Vinit Gupta, Austin Antony Cruz, Inhyuk Choi, Nam Sung Kim, Jihong Kim]
venue: OSDI
year: 2026
tags: [cxl, memory-management, near-memory-processing, tail-latency, kernel]
source_pdf: "[[osdi26-lee.pdf]]"
source_md: "[[osdi26-lee]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 面向 CXL 大数据系统的元数据加速

> **原题**：MAC: Metadata Acceleration for Sustainable Performance in Big-Data Systems with CXL DRAM

## 一句话总结

MAC 将 Linux 回收路径中的 page descriptor 检查与 Xarray walk 批量卸载到 CXL DRAM 侧的近内存处理器，在不把庞大内核元数据挤回稀缺 DDR DRAM 的前提下，提高后台回收速率并将应用 p99.99 延迟最多降低 98%。

## 问题与动机

CXL DRAM 以较低成本扩展容量，但访问延迟约为 DDR DRAM 的 2.4 倍。更隐蔽的问题是，物理内存越大，page descriptor 与文件页缓存的 Xarray 也越大：作者的 120 GiB 内存、1.8 TiB [[RocksDB|RocksDB]] 数据库中，两者合计约 5.7 GiB；当 DDR:CXL 为 1:4 时已相当于 DDR 容量的 24%，1:8 时可接近 40%。

把元数据固定在 DDR 会与应用数据争抢低延迟容量，极端压力下还会放大 slab 分配或 OOM 风险；让元数据自然溢出 CXL，则 kswapd 每次回收都要远程遍历它们。作者观察到元数据延迟增至 2.4 倍时，前台回收事件增加 6.5 倍，RocksDB p99.99 延迟增至约 2.8 倍。关键因果链不是“应用直接访问慢内存”，而是“后台回收变慢 → 空闲页不足 → 应用线程同步回收”。

## 关键观察 / 隐含假设

### 关键观察

- page descriptor 筛选主要是 flag bitmask，Xarray 删除主要是指针追踪、移位和写入 shadow value；它们计算简单、访问重复，适合在数据附近并行执行。
- 两类元数据位于内核 direct map，虚拟地址可用简单算术转换为物理地址，因此设备侧无需维护通用页表或复杂地址转换器。
- 一次回收至少处理约 32 页，批处理足以摊薄命令、通信和一致性成本。
- Xarray walk 与主机侧 rmap unmap、脏页 writeback 可并行，而 CXL 3.x 的 back-invalidation 也可与 walk 重叠。

### 隐含假设

- CXL 设备具备可编程计算资源、足够并行度以及 CXL.cache/未来 BIsnp 一致性能力。
- Linux page cache 回收结构与操作仍保持规则、批量化，卸载边界不会被频繁内核演化破坏。
- 元数据主要驻留在同一 CXL 设备；跨设备 Xarray 的放置和迁移尚未成为常态。
- 应用处于明显内存压力下，且 tail latency 的主要干扰源确实是前台回收，而非存储、锁竞争或数据库内部停顿。

## 核心方法

### 元数据放置与命令接口

MAC 主动把 page descriptor 和 Xarray 分配在容量充裕的 CXL DRAM。每个 CPU core 在 CXL 地址区拥有一个共享工作缓冲区 `MAC_buf`，内含 descriptor 地址数组、Xarray head、文件页索引和 shadow value。主机向预注册地址写普通 CXL.mem 请求作为 `MAC_cmd`；设备 packet filter 识别地址、解析操作类型、core ID 与批大小，无需改 CPU 或 CXL 协议。

### 两阶段回收卸载

一次回收先由主机从 LRU 隔离候选页并加锁，将约 32 个 descriptor 地址交给设备。设备并行检查 valid、referenced、active、dirty 等 flag，返回可回收分类。主机随后锁定目标 Xarray，批量提交 head/index 对；设备遍历树并把叶槽替换为 shadow value。前台与后台回收共用同一路径，每 core 一份缓冲区依赖 Linux 回收期间禁止抢占来避免并发覆盖。

### 一致性与协作并行

主机插入页并修改 Xarray 后用 `clwb` 刷回 cacheline；设备删除页后需用 CXL 3.x BIsnp 使主机 cacheline 失效。MAC 把多个 Xarray walk 并行执行，并将 BIsnp 与后续 walk 流水化；block invalidation 还可一条消息覆盖最多四条连续 cacheline。与此同时，主机在持锁等待设备时处理 mapped 页的 unmap、dirty 页 writeback 和统计更新，以隐藏设备计算与同步延迟。

## 实现

作者在 Linux 6.14 上实现双 [[NUMA|NUMA]] 软件仿真：NODE0 的 64 cores 运行应用和 kswapd，NODE1 用 1 个 controller core 加 32 个 accelerator cores 模拟 CXL NMP，并显式模拟 BIsnp 延迟。另在 Intel Agilex 7 I-series FPGA 上综合 Xarray walk 与 descriptor traversal；因现有 CPU 缺少设备发起的快速 BIsnp，原型以 coherent CXL.cache write 代替。

系统比较包括：允许 Xarray 在 DDR 不足时溢出 CXL 的优化 Linux Baseline；强制元数据优先驻留 DDR 的 Baseline-P；串行卸载 MAC-S；以及并行、流水化的 MAC-P。

## 实验与结果

工作负载覆盖 2.0–2.5 TiB RocksDB/YCSB、2.0 TiB PostgreSQL/pgbench、1 TiB Neo4j/LDBC SNB 与 1.7 TiB LMDB/ioarena，并改变 DDR:CXL 从 1:1 到 1:4，讨论还扩展到 1:8。

- RocksDB read-only、DDR:CXL=1:2 时，相比 Baseline，MAC-S/MAC-P 将 p99.99 分别降低 97%/98%；MAC-P 将 Xarray walk 降低 80%、descriptor traversal 降低 58%，空闲页生成增加 36%，前台回收减少 66%。
- 相比把元数据留在 DDR 的 Baseline-P，MAC-P 在同一配置仍将 p99.99 降低 22%，并在 1:4 下提高 TPS 6%；Baseline-P 的 slab 分配延迟会从常见的 2–4 μs 放大到 10–600 μs。
- RocksDB 50/50 read-update 中，MAC-P 相对 Baseline 将读 p99.99 平均降低 27%、更新 p99.99 降低 52%，吞吐提高 10%。
- PostgreSQL 在 1:2 下，MAC-P 将遭遇前台回收的 query 数减少 88%，p99.99 降低 92%，TPS 最多提高 5%。
- Neo4j SQ6 相比 Baseline 的 p99.99 降低 82%；混合 IS/IC 总运行时间相对 Baseline-P 缩短 11%，但计算密集长查询收益较小。
- LMDB 中 MAC-S/MAC-P 相比 Baseline 的 p99.9 平均降低 62%，MAC-P 将回收时间降低 42%，说明主机 unmap 与设备 walk 的协作有效。
- FPGA 原型将 Xarray walk、descriptor traversal 分别降低 82% 和 48%，端到端 kswapd 回收缩短 30%，与仿真趋势一致。

## 论断—证据表

| 论断 | 证据 | 边界 | 置信度 |
|---|---|---|---|
| CXL 中的内核元数据会间接放大应用尾延迟 | 图 2：2.4 倍元数据访问延迟对应 6.5 倍前台回收和约 2.8 倍 p99.99 | 人工延迟实验聚焦 RocksDB 与 page-cache 压力 | 强 |
| NMP 能比普通 Linux 更快回收 | 图 12：MAC-P 的 Xarray/descriptor 开销分别下降 80%/58%，空闲页率升 36% | NUMA 仿真不能完全复现真实 CXL controller 争用 | 强 |
| 提速最终转化为数据库 tail-latency 收益 | 图 11、14、15、17：多种数据库的高分位延迟普遍下降 | 对计算密集 Neo4j 查询收益有限 | 强 |
| 硬件卸载收益并非纯仿真假象 | 图 18：FPGA 端到端回收缩短 30% | 原型以 CXL.cache coherent write 代替尚不可用的 BIsnp | 强 |
| 把元数据强留 DDR 不是等价替代 | Baseline-P 出现 10–600 μs slab allocation，并牺牲 TPS | 结论依赖 DDR 容量紧张和超大数据集 | 强 |
## 批判性分析

### 论证链条

最有价值的贡献是重新定位瓶颈：CXL 的性能风险不仅是应用数据远端访问，内核元数据也会通过回收控制环间接破坏 tail latency。MAC 的卸载粒度较克制，只挑选规则、可批处理的两个热路径，并用 direct map 避免引入设备页表。评估同时包含多类数据库、容量比例、软件仿真和 FPGA 原型，因果链证据相对完整。

### 假设压力测试

- 完整设计依赖 CXL 3.x BIsnp，而实机原型并未验证该路径；未来 CPU/设备上的真实一致性延迟、拥塞和错误处理可能改变收益。
- 为每次回收持有 Xarray locks 且禁止抢占直到设备完成，设备尾延迟或故障可能扩大内核关键区风险。
- 软件仿真把 accelerator 映射为通用 CPU cores，不能精确覆盖设备内带宽、packet filter、cache-coherence 队列和多租户干扰。
- 研究聚焦 file-backed page cache；匿名页、swap、huge page、内存压缩及容器级 reclaim 的可卸载性尚不明确。
- 内核内部数据结构不是稳定 ABI，Xarray、LRU/reclaim 策略变更会增加硬件逻辑维护成本。

### 可推广启示

### 实验可信度

评估同时覆盖 software emulation、真实数据库与 FPGA prototype，证据链较完整；但 BIsnp 仍由模型代替，真实 CXL 3.x coherence congestion 尚未验证。

MAC 揭示了一类更一般的设计模式：在异构内存中，容量扩展也会扩展控制元数据；若控制面仍由远端 CPU 串行遍历，系统可能先撞上“元数据速度墙”。适合卸载的不是任意 kernel code，而是具有 direct addressing、规则遍历、批量操作和清晰一致性边界的元数据热路径。

## 局限与后续工作

- **局限**：完整收益依赖尚未普及的 CXL 3.x back-invalidation 与稳定的 kernel internal ABI。
- **后续工作**：应在原生 BIsnp、多设备和多租户环境中验证 tail behavior、故障 fallback 与匿名页回收。

后续应在原生 CXL 3.x BIsnp 硬件上复现实验，测量多设备共享链路和多租户时的 tail behavior；给设备超时、故障、取消与 CPU fallback 定义可验证语义；扩展到匿名页和 memcg reclaim；并研究把可变内核遍历描述成设备可解释程序或稳定卸载接口，以降低 Linux 版本耦合。

## 相关概念

- [[CXL]]
- [[Near-Memory-Processing]]
- [[Memory-Reclamation]]
- [[Tail-Latency]]
- [[Page-Cache]]
