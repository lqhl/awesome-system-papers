---
type: entity
kind: tool
aliases: [Rocks-DB]
status: active
last_updated: 2026-08-14
tags: [storage, kv-store, lsm-tree, benchmark]
---

# RocksDB

> RocksDB 是一个嵌入式、持久化的 key-value engine。它用 [[LSM-Tree]] 组织写入，并把 WAL、memtable、SSTable、block cache、Bloom filter 和后台 compaction 组合成完整存储栈。

## 为什么系统论文经常使用它

RocksDB 同时有两个角色。

第一，它是可以直接改造的成熟系统。研究者可以替换 memtable、compaction、数据放置或 I/O 路径，观察一个局部机制进入真实 engine 后是否仍有收益。

第二，它是通用压力源。RocksDB 会同时使用 CPU、内存带宽、页缓存或 direct I/O、SSD 和后台线程，因此常被用来验证内核、调度器、CXL 内存、I/O completion 与 overload control。此时论文研究的不是 RocksDB 算法本身，而是下层系统能否承受一个复杂应用。

这两个角色不能混为一谈。某篇论文“在 RocksDB 上快了”不等于它改进了所有 LSM-tree，也不等于生产数据库会得到同样数字。

## 主要数据路径

- 写入通常先进入 WAL 和内存中的 memtable；memtable 满后 flush 成有序 SSTable。
- 读取依次查内存结构、block cache、Bloom filter 和若干 SSTable；命中位置与缓存状态决定实际 I/O。
- 后台 compaction 合并层或文件，删除过期版本并恢复查询效率，但会消耗 CPU、内存带宽和设备带宽，产生写放大。
- 恢复、校验、compression、direct I/O、WAL、同步写和线程数都会改变前台延迟与吞吐。

因此，RocksDB 结果至少要说明：数据量、key/value 大小、YCSB mix、cache 大小、WAL 和 sync 设置、compaction 线程、I/O 模式、预热状态、运行时长以及是否包含后台债务。

## 论文如何改造 RocksDB

### 1. 替换内存索引

[[ARCTIC-OSDI26]] 用无锁 adaptive radix tree 替换默认 lock-free skiplist。关闭 WAL 的 100M-record bulk load 中，1、2、4、8 线程吞吐分别是原版的 1.36、1.40、1.13、1.05 倍。结果支持“新索引能进入 RocksDB”，但只覆盖写密集 bulk load，且扩到 8 线程后优势已经明显缩小；非线性一致 range scan 还需要 compaction 的无 writer 阶段或上层 MVCC 提供快照语义。

[[RASK-FAST26]] 把连续 range 当成一个索引 key，用 ART 内部节点和 log-structured leaf 压缩大量连续写。论文在阿里云、腾讯、Meta 和 Google workload 上报告明显内存与吞吐收益；换掉 RocksDB memtable 后，Meta case 吞吐为原 skiplist 的 7.46 倍。这个结果依赖 65%–81.5% 写入属于连续 range 的生产观察，随机、不连续 key workload 未必受益。

### 2. 改变 LSM 数据放置与 compaction

[[DOGI-FAST26]] 在 ZenFS + RocksDB + ZNS SSD 上，用 hot filter、轻量 MLP 和动态 grouping 预测 user block 与 GC block 的寿命；相对 MiDAS 平均降低 15.5% 写放大并提高 9.2% 写吞吐。它证明了预测式 placement 可进入这一栈，但实现绑定 ZenFS 的 segment/ZoneFile 语义，不能直接外推到普通 Ext4 或云块设备。

[[HotRAP-ATC25]] 面向 fast/slow tiering，在 fast device 上维护小型热度 LSM，并在 flush 与 compaction 时提升或保留 hot record。hotspot 读写 workload 中相对次优基线最高约 1.6 倍，Twitter trace 约 1.5 倍；uniform workload 反而慢 4%，scan 不进入 promotion。收益来自细粒度热点和 point-get 局部性，不是所有 RocksDB 流量都应采用相同策略。

[[DecouKV-ATC25]] 更激进地把 index 与 data 分开：DRAM IndexTable 做 CPU-bound merge，fast device 的 append-only data log 做 I/O-bound flush，并用两个队列平衡资源。PM + SATA 混合设备上，写吞吐相对 RocksDB 为 2.3–4.9 倍、P99 降低 74.3%–91.4%；代价是更多 DRAM、不同恢复路径和对混合设备瓶颈交替的依赖。

## RocksDB 作为系统压力源

### 内核与文件系统

[[DeLFS-OSDI26]] 在 F2FS 中把元数据、日志、I/O 与 GC 划成 per-core domain。RocksDB 10M records、1.28M operations 的 YCSB A/B/F/update-only，在 128 核上相对 F2FS 分别提高 1.78、1.19、1.98、2.24 倍。它验证的是日志结构文件系统扩展性；结果来自一台服务器和一块消费级 SSD，不等于替换 RocksDB 自身 compaction。

[[Xkernel-OSDI26]] 说明固定内核常量会对不同设备给出相反选择：`BLK_MAX_REQUEST_COUNT` 在 HDD FIO 上适合 128，在 32 GB NVMe RocksDB random workload 上适合 1；后者相对默认 32 提高 1.2 倍吞吐、降低 12% I/O-wait CPU。这里 RocksDB 用于证明“knob 必须按设备和 workload 调”，不是新数据库设计。

[[DPAS-FAST26]]、[[UnICom-FAST26]] 都研究 I/O completion。DPAS 在 CPU 与 I/O 干扰下，让 RocksDB/YCSB 在三类设备上随 polling、sleep 和 interrupt 动态切换；摘要结果在 3D XPoint/TLC SSD 上约提高 9%/5%。UnICom 用集中 completion thread 和调度 tag，在 direct-I/O YCSB 中相对 Ext4 单线程高 24%–28%、32 线程高 9%–18%。两者的配置、内核和完成机制不同，不能只按最高数字判断优劣。

[[MAC-OSDI26]] 研究大容量 CXL 内存中的 Linux page descriptor 与 Xarray。TiB 级 RocksDB 强内存压力下，MAC-P 将 read-only p99.99 相对优化 Linux baseline 降低 98%；50/50 read-update 中 read/update p99.99 平均降低 27%/52%，TPS 提高 10%。完整系统主要是双 NUMA 软件仿真，FPGA 只验证热路径，原生 CXL 3.x BIsnp 仍未端到端验证。

[[Espresso-OSDI26]] 用 CXL 在一组 SSD 间共享处理器与 DRAM；双 NUMA 的 RocksDB/db_bench 仿真中，相对缩减配置高 24.8%并接近全配置。该实验只有一个 borrower 和一个 lender，是功能性扩展证据，不是 12 盘真实 CXL JBOF 结果。

### 调度、过载与可抢占执行

[[SBB-OSDI26]] 把 RocksDB 移到每核网络 runtime，使用 UINTR timer 和两级迁移；其 RocksDB light/heavy-tail 在相同 tail SLO 下比对应基线高 20%–80%。不过数据库完全在内存中并关闭 logging，网络栈也没有 congestion control，因此主要验证 CPU 调度，不覆盖持久存储路径。

[[Svalinn-OSDI26]] 在真正访问内存密集路径前加入 `m_semaphore`，让局部 controller 限制打满内存带宽所需的并发。RocksDB 的 CPU/memory goodput 最高分别提高 7.62/1.26 倍，P99 最多降低 2.95/1.47 倍；代价是开发者标注路径、支持安全取消，并在 fast path 外持续读取硬件 counter。最高数字来自人工请求分类和对应基线，不能直接当作普通 RocksDB server 增益。

[[PeeR-OSDI26]] 测得 RocksDB XRP eBPF invocation 的 P50/P99 为 4/882 微秒，用它说明“verifier 通过”不代表程序运行时间短。PeeR 在安全 helper boundary 抢占长 eBPF execution；RocksDB 在这里是 tail-heavy 内核程序案例，不是 KV engine benchmark。

## RocksDB 作为系统组件或对照

有些入链只说明论文系统使用了 RocksDB，不提供 RocksDB 的性能结论：

- [[Ambulance-OSDI26]] 用 RocksDB 持久化 BFT payload，但没有拆分 compaction、durability 或 corruption 对协议恢复的影响。
- [[LogDrive-OSDI26]] 的 Conflux replica 用本地 RocksDB 保存 materialized metadata state；论文没有量化大状态 replay、snapshot 与 compaction 成本。
- [[McQueen-FAST26]] 的 ClassVI metadata service 以 RocksDB 为本地 engine，并用跨 region Raft 保证 row-level 强一致；核心贡献是两层纠删码对象存储，不是 RocksDB。
- [[MlsDisk-FAST26]] 把 RocksDB 当作已是 log-structured 的上层应用。其安全磁盘对 RocksDB 收益有限，反而说明两层日志结构叠加不一定继续加速。
- [[HATS-FAST26]] 研究 Cassandra replica selection 与 compaction 协同。它与 RocksDB 共享 LSM/compaction 问题，但主实验不是 RocksDB，不能直接搬用 Cassandra 数字。

## 跨论文得到的结论

1. **解除一个瓶颈会暴露下一层。** 更快 memtable 可能把瓶颈推到 WAL、compaction 或 SSD；更快 I/O completion 可能把瓶颈推到 CPU、锁或内存带宽。
2. **后台工作必须进入评测。** 关闭 WAL、纯内存、短时间或预热后运行，可以隔离机制，但不能代表长期持久化服务。
3. **设备改变最优策略。** PM、ZNS、NVMe、SATA、CXL 与纯 DRAM 对 queue depth、compaction、placement 和 polling 的选择不同。
4. **吞吐与尾延迟可能方向相反。** 更积极 compaction、promotion 或 admission 能提高平均吞吐，也可能制造 P99 spike。
5. **“RocksDB 集成”是必要但不充分证据。** 它能证明 API 和工程路径可接入；要证明生产价值，还需 crash recovery、长时间 compaction debt、真实 trace 和资源成本。

## 阅读 RocksDB 结果时的检查表

- WAL、sync write、compression、checksum 和 direct I/O 是否开启？
- block cache、操作系统 page cache 与数据集大小是什么关系？
- 是否包含 fill、warm-up、steady state、compaction debt 和 recovery？
- YCSB A–F 的 key/value size、Zipf 参数、线程数和客户端限速是什么？
- 报告的是 ops/s、goodput、平均延迟还是 P99/P99.99？
- 基线是否使用相同 RocksDB 版本、配置、设备和可用 CPU 核？
- 额外 DRAM、polling core、accelerator、CXL 或 fast tier 的成本是否计入？

## 相关论文

- **索引与数据布局**：[[ARCTIC-OSDI26]]、[[RASK-FAST26]]、[[DOGI-FAST26]]、[[HotRAP-ATC25]]、[[DecouKV-ATC25]]。
- **内核、内存与 I/O**：[[DeLFS-OSDI26]]、[[DPAS-FAST26]]、[[UnICom-FAST26]]、[[MAC-OSDI26]]、[[Espresso-OSDI26]]、[[Xkernel-OSDI26]]。
- **调度与控制**：[[SBB-OSDI26]]、[[Svalinn-OSDI26]]、[[PeeR-OSDI26]]。
- **组件或对照**：[[Ambulance-OSDI26]]、[[LogDrive-OSDI26]]、[[McQueen-FAST26]]、[[MlsDisk-FAST26]]、[[HATS-FAST26]]。

## 相关概念

- [[LSM-Tree]]、[[Garbage-Collection]]、[[NVMe]]、[[CXL]]、compaction、write amplification、key-value store
