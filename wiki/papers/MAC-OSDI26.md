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
last_reviewed: 2026-08-14
---

# MAC：用 CXL 近内存处理加速回收元数据（OSDI 2026）

> **原题**：MAC: Metadata Acceleration for Sustainable Performance in Big-Data Systems with CXL DRAM

> **一句话总结**：大容量 [[CXL]] 内存不仅让应用数据访问变慢，还让 page descriptor 与 Xarray 变大并拖慢 Linux 回收；MAC 把这两种规则、批量的元数据遍历卸载到 CXL 侧 accelerator，双 [[NUMA]] 仿真中让 [[RocksDB|RocksDB]] p99.99 最多比优化 Linux baseline 低 98%，FPGA 热路径验证的端到端 kswapd 回收时间低 30%，但完整系统仍用模型代替原生 CXL 3.x BIsnp。

## 问题与动机

CXL DRAM 用较慢、较便宜的内存扩展服务器容量。论文实测环境中 CXL 访问延迟约为 DDR DRAM 的 2.4 倍。直观做法是把热应用数据留在 DDR、冷数据放 CXL；但 Linux 为每个 4 KiB page 保存 64 B page descriptor，文件页又由每个 584 B、最多 64 个 entry 的 Xarray node 索引。容量增大时，控制这些数据的元数据也会一起增大。

在 120 GiB 物理内存、1.8 TiB RocksDB 数据库、24 GiB DDR 加 96 GiB 真实 CXL 的测量中，page descriptor 占 2 GiB，Xarray 占 3.7 GiB，合计 5.7 GiB，相当于 DDR 容量的 24%。把它们固定在 DDR 会挤走应用热数据，并在极端压力下增加 slab allocation 或 OOM 风险；让 Linux 按现有机制把 descriptor 放在设备、把 Xarray spill 到 CXL，则 kswapd 要反复跨慢链路遍历元数据。

问题最后会出现在应用关键路径上：后台 kswapd 回收不够快，free page 低于 low watermark 后，应用线程必须同步做 foreground reclaim。论文的人为延迟实验中，元数据访问慢 2.4 倍时，RocksDB p99.9/p99.99 分别放大约 2.6/2.8 倍，foreground reclaim 频率放大 6.5 倍（图 2）。MAC 的目标不是让所有 CXL 访问变快，而是加速这条“慢元数据—慢后台回收—前台停顿”的控制链。

## 关键观察 / 隐含假设

- **观察 1**：内存容量扩张会同时放大 kernel metadata；在高 CXL:DDR 比例下，把元数据留在 DDR 本身就会成为容量瓶颈（§3.1）。
  - **依赖假设**：workload 依赖大规模 file-backed page cache，Xarray 规模随活跃文件页持续增长。
  - **可能失效场景**：小 working set、主要使用匿名内存、应用自己管理 cache，或没有明显 DDR 压力时，元数据占比和迁移收益都会下降。
- **观察 2**：远端元数据延迟通过降低 kswapd 产出间接放大应用尾延迟。真实 CXL 测量中，page test 慢 2.2 倍、kswapd 回收效率下降 42%；foreground reclaim 的 page test 与 Xarray management 分别比全 DDR 慢 3.6 和 3.9 倍（§3.1、图 3）。
  - **依赖假设**：tail spike 的主因是缺少 free page，而不是 SSD、数据库锁、compaction 或 CPU oversubscription。
  - **可能失效场景**：回收压力低，或应用延迟被存储和计算完全主导时，MAC 加快回收也难以改善端到端延迟。
- **观察 3**：page descriptor 筛选主要是 bitmask，Xarray 删除主要是固定深度的 pointer walk、shift 和 shadow-value 写入；一次 reclaim 至少处理约 32 页，适合靠近数据做批量并行（§3.2）。
  - **依赖假设**：Linux direct map 允许用 `__pa()` 类算术得到物理地址，设备不需要通用 page-table walker。
  - **可能失效场景**：数据结构、reclaim policy 或地址表示改变后，固定 accelerator 可能失效；控制流复杂的 rmap unmap 仍需主机处理。
- **假设 1**：CXL 侧有可编程 controller/accelerator，并能用 CXL 3.x BIsnp 维护 device 更新与 host cache 的一致性。
  - **证据强度**：中弱。FPGA 验证了计算卸载，但当前 commodity CPU 不能让该 FPGA 发起设计所需的 BIsnp；完整仿真用延迟模型替代，原型改用 host-biased CXL.cache coherent write（§4.4、§5.1）。
- **假设 2**：持有 page/Xarray lock 并禁止 host core 抢占直到设备返回是可接受的。
  - **证据强度**：中。正常路径的结果很好，但论文没有注入设备长尾、timeout、reset 或 link error。

## 核心方法

MAC 在容量充足的 CXL DRAM 中放置 CXL page descriptor 和所有 Xarray，让 DDR 尽量保存应用数据；然后把回收过程中的 descriptor traversal 与 Xarray walk 交给 CXL 侧 [[Near-Memory-Processing|近内存处理器]]。它只卸载重复、规则的部分，LRU 选择、锁、复杂 rmap、dirty page writeback 和统计更新仍由 host kernel 完成（图 4）。

主机与设备通过 `MAC_buf` 和 `MAC_cmd` 通信。系统启动时为每个 host CPU core 在 CXL DRAM 中预留一个 buffer，写入 descriptor address array、Xarray head、page index 和 shadow value。Host 对已注册地址发普通 CXL.mem write；device packet filter 把它解释成命令，并取得 operation type、core ID 和 batch size，不要求改 CPU 或 CXL 协议。Linux reclaim 期间本来就禁止 core preemption，因此一 core 一 buffer 可以覆盖 foreground 与 background reclaim（§4.2、图 5）。

一次回收分两段。Host 先从 LRU 隔离约 32 个候选 page，持有 page lock，把 descriptor 地址批量交给设备；accelerator 并行检查 valid、referenced、active、dirty 等 flag，返回可回收分类。随后 host 锁住相关 Xarray，提交 `(head, index)` 对；设备沿树走到 leaf，把对应 slot 改为 shadow value，host 最后释放锁并更新状态。应用线程触发的 foreground reclaim 与 kswapd 走同一卸载路径（§4.3、图 6）。

一致性是设计的难点。Host 插入或修改 Xarray 后用 `clwb` 把变化刷到设备，测得每 query 通常需要 1–3 次 flush；设备删除 page 后，设计用 CXL 3.x BIsnp 让 host cache 中的旧 line 失效。若 32 次 walk 后再串行做 32 次 500 ns invalidation，仅同步就要 16 微秒。MAC 把 walk 与 BIsnp pipeline，并用一次覆盖最多 4 条连续 cacheline 的 block invalidation；16 个 walk 并行后约为 2–3 微秒，另有约 1 微秒同步开销，相对串行 walk 再降 55%（§4.4–§4.5、图 8）。

MAC 也让 host 与 device 分工重叠。设备走 Xarray 时，host 可以 unmap `mmap` page、write back dirty page，或更新 clean page 的统计，从而隐藏一部分设备延迟（图 9）。评测实现包含 MAC-S 和 MAC-P：MAC-S 用 1 个 controller 加 4 个 accelerator，MAC-P 用 1 个 controller 加 32 个 accelerator，后者进一步利用 batch parallelism 与 modeled bulk BIsnp。

## 设计取舍

- **把元数据移出 DDR，换取设备侧计算依赖**：DDR 留给应用热数据，避免 Baseline-P 的 slab 争用；没有 NMP 的普通 CXL 设备反而会让 host 远端遍历更慢。
- **固定功能 accelerator，换取低开销**：bitmask 和 Xarray RTL 简单、可流水化；代价是紧耦合 Linux internal data structure，不是稳定 ABI。
- **批量并行，换取更长的锁定区间**：32-entry batch 摊薄通信并提高吞吐，但 host 在设备完成前持 lock 且不可抢占，设备 tail latency 会直接进入 kernel critical path。
- **Host-device 协作，换取复杂同步**：unmap/writeback 与 walk 重叠减少总时间，同时增加 page state、Xarray state 和统计更新之间的时序验证难度。
- **未来 BIsnp 换低一致性成本**：block invalidation 很适合批量删除，但当前 prototype 只能用另一条 coherent path 近似，真实链路拥塞仍未知。

## 实验与结果

- 完整系统评测把 MAC 集成进 Linux 6.14：NODE0 的 64 cores 运行应用和 kswapd，NODE1 用 1 个 controller core 与最多 32 个 accelerator core 仿真 CXL NMP，并用模型加入 BIsnp delay；因此它是双 NUMA 软件仿真，不是原生 CXL 3.x 系统。工作负载包括 2.0–2.5 TiB RocksDB、2.0 TiB PostgreSQL、1 TiB Neo4j 和 1.7 TiB LMDB（§5.1–§5.2、表 1）。
- RocksDB read-only、64 GiB DDR 加 128 GiB CXL、200 threads 时，MAC-S/MAC-P 相对优化 Linux Baseline 将 p99.99 降低 97%/98%；MAC-P 将 Xarray walk 与 descriptor traversal 开销降低 80%/58%，free-page generation 提高 36%，foreground reclaim 次数降低 66%（§5.3、图 11–图 12）。
- 把 metadata 尽量钉在 DDR 的 Baseline-P 仍不是等价替代：DDR:CXL 为 1:1 时，MAC-S/MAC-P 的 p99.99 比它低 15%/22%；Baseline-P 的 slab allocation 从其他方案的 2–4 微秒上升到 10–600 微秒，DDR:CXL 为 1:4 时 TPS 比 MAC-P 低 6%（§5.3、图 11–图 12）。
- RocksDB 50/50 read-update 中，MAC-P 相对 Baseline 将 read p99.99 平均降低 27%、update p99.99 降低 52%，TPS 提高 10%；PostgreSQL 在 1:2 下的 foreground-reclaim query 数减少 88%、p99.99 降低 92%，所有容量配置的 TPS 最多提高 5%（§5.3、图 13–图 14）。Neo4j SQ6 的 p99.99 降低 82%，LMDB 的 p99.9 平均降低 62%，但计算主导的 Neo4j CQ1/CQ2 收益较小（图 15–图 17）。
- FPGA 用合成 descriptor 与代表 RocksDB/PostgreSQL 的三层 Xarray 验证热路径：相对 host 在 CXL DRAM 中遍历，Xarray walk 降低 82%、descriptor traversal 降低 48%，包含通信与同步后的 kswapd reclaim 端到端时间降低 30%。它支持“卸载计算有效”，但没有在真实数据库运行中验证 native BIsnp（§5.3、图 18）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| CXL 中的慢 kernel metadata 会通过回收控制链放大应用尾延迟 | 图 2：2.4 倍 metadata delay 对应约 2.8 倍 p99.99 和 6.5 倍 foreground reclaim；图 3 的真实 CXL characterization 显示 kswapd 效率降 42% | 1.8 TiB RocksDB/YCSB、120 GiB memory、page-cache 压力 | 强 |
| 把规则的 reclaim metadata 操作卸载到数据附近能提高 free-page 产出 | 图 12：MAC-P 的 Xarray/descriptor 开销降 80%/58%，free-page generation 增 36% | 双 NUMA 仿真与 modeled BIsnp | 强 |
| 更快的后台回收能转化为多种数据库的尾延迟收益 | 图 11–图 17：RocksDB、PostgreSQL、Neo4j、LMDB 的高分位延迟普遍下降 | TiB 级、file-backed、强内存压力 workload | 强 |
| 直接把 metadata 留在 DDR 不能避免竞争 | Baseline-P 出现 10–600 微秒 slab allocation，1:4 下 TPS 比 MAC-P 低 6% | DDR 容量紧张；临近 OOM 时 Baseline-P 仍 fallback 到 CXL | 强 |
| FPGA 结果验证了完整 MAC 的一致性与性能 | 图 18 只验证合成 metadata 热路径，端到端 reclaim 降 30%；BIsnp 仍被替代 | 无原生 BIsnp、无完整数据库执行 | 弱 |

## 批判性分析

### 论证链条

论文先量化 metadata 容量，再把慢 metadata 与 kswapd 产出、foreground reclaim 和应用 p99.99 串成因果链；MAC 随后只加速链条中最规则的两个环节。图 12 同时给出内部开销、free-page generation 和 foreground reclaim，图 11 再给端到端 tail latency，因此机制与结果之间的联系比只报告应用加速更可信。

最大的跳步是从“NUMA 模型加速有效”和“FPGA 能加速两个函数”推到“原生 CXL 3.x MAC 可获得相同系统收益”。软件仿真能跑真实数据库，却没有真实 CXL accelerator、link queue 和 coherence traffic；FPGA 有真实硬件，却只跑合成结构并用 CXL.cache coherent write 替代 BIsnp。两部分互补，但没有在一个系统中闭合。

### 假设压力测试

MAC 对大 file-backed working set 最有价值。匿名页、swap、transparent huge page、zswap、memory compaction、memcg reclaim 和容器级 pressure 的主导元数据与控制流可能不同；论文没有证明同样的两种 accelerator 能覆盖它们。数据库规模较小或 DRAM 足够时，元数据不挤压 DDR，额外通信与锁持有可能不值得。

硬件方面，真实 CXL fabric 上多个 device、host 与 tenant 会共享带宽和 coherence queue。论文的 500 ns BIsnp 和 bulk invalidation 假定可能在拥塞下失效。一个 Xarray 若跨设备放置，walk、锁与迁移也不再局部；§7 只提出“尽量放在同一设备”，没有实现。

### 实验可信度

优点是 workload 很大，并覆盖 RocksDB、PostgreSQL、Neo4j、LMDB 四种数据库；Baseline 是带现代 reclaim 优化的 Linux 6.14，Baseline-P 还检验了“把 metadata 固定在 DDR”这一直接替代。RocksDB 从 read-only 延伸到 compaction-heavy update，Neo4j 和 LMDB 又覆盖 graph query 与 `mmap`，证据不是单一 benchmark。

但软件环境用 33 个通用 CPU core 模拟 controller/accelerator，并人为限制 LLC，再用模型加 coherence delay；它不能复现 FPGA 资源限制、CXL link contention、packet filter queue 或 device power。各容量配置会调 thread count 到最高吞吐，虽然同一配置内比较公平，却使跨比例 latency 曲线不只反映内存比例。论文也没有系统报告 trial 数、置信区间或 p99.99 的样本稳定性；FPGA 图 18 使用合成 metadata，而非真实应用产生的完整时序。

### 系统性缺陷

Device 在 host 持有 page/Xarray lock 且禁止抢占时工作。如果 accelerator 卡住、CXL link reset 或 command completion 丢失，kernel 需要 timeout、取消、回滚和 CPU fallback；论文没有定义这些语义。Host 与 device 并行修改相关 page 状态，也扩大 race 与 deadlock 的验证空间。

把 Xarray walk 与 descriptor logic 固化进 RTL 还产生版本维护成本。Linux 的 folio、multi-gen LRU、Xarray 和 reclaim 路径持续变化；论文没有稳定 offload ABI、capability negotiation 或版本降级方案。每 core `MAC_buf`、多 kswapd、多 socket、多 CXL device 和多租户之间的资源隔离与 backpressure 也没有评测。

## 局限与后续工作

- **局限 1**：完整系统结果来自 NUMA 仿真，FPGA 只验证热路径；原生 CXL 3.x BIsnp、fabric congestion 和真实 database execution 尚未合并验证。
- **局限 2**：结论集中在 TiB 级 file-backed database 和强 page-cache pressure，匿名页、memcg、huge page 与混合 workload 没有覆盖。
- **局限 3**：设备故障、timeout、kernel upgrade、多 device 与多租户隔离没有协议或实验。
- **后续工作 1**：在支持 device-initiated BIsnp 的平台上复现图 11–图 18，并同时记录 CXL bandwidth、BIsnp queue latency、lock hold time、p99.99 与 accelerator utilization。
- **后续工作 2**：对 accelerator hang、command loss、link reset 和 host reboot 做 fault injection，要求每个 batch 能在有限时间内安全回退 CPU，且 Xarray/page state 通过 kernel consistency check。
- **后续工作 3**：加入 anonymous、memcg、THP、zswap 与 mixed file/anonymous pressure，逐项测可卸载比例、通信成本和 tail-latency break-even point。
- **后续工作 4**：定义带 version 与 capability 的 kernel-to-device bytecode/descriptor，而不是固定 Linux 函数 RTL；跨至少三个 kernel release 验证兼容与降级路径。

## 相关

- **相关概念**：[[CXL]]、[[Near-Memory-Processing]]、[[Memory-Reclamation]]、[[Tail-Latency]]、[[Page-Cache]]、[[NUMA]]
- **同类系统**：[[Radiant]]、[[Hermit]]
- **同会议**：[[OSDI-2026]]
