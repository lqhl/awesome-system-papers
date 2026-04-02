# Cuckoo for Clients: Disaggregated Cuckoo Hashing

**作者**：Stewart Grant, Alex C. Snoeren (UC San Diego)
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/grant
**源文件**：[[atc2025-grant.pdf]]

---

## 一、背景

内存解耦（memory disaggregation）架构通过将网络附加的内存资源池化来提升可扩展性和利用率，减少每台机器的内存碎片和搁浅。随着 DRAM 密度增长放缓，远程内存池化变得愈发重要。然而，高性能的通用远程内存系统仍然难以实现——即使最快的机架级网络（如 RDMA，延迟约 1μs）也比本地 DRAM（约 50ns）慢一个数量级。

在解耦架构中，Key/Value Store（KVS）是共享访问远程内存池的最有前景的接口。然而，现有的高性能 KVS 系统多数依赖 two-sided RDMA 操作，需要内存侧 CPU 管理锁和执行临界区，这削弱了解耦架构的资源节省优势。完全解耦的 KVS（仅使用 one-sided RDMA）面临一致性维护的核心挑战：有序键系统使用锁，无序键系统则偏好 lock-free 乐观方法——后者在写密集场景下性能较差。

---

## 二、要解决的问题

1. **Lock-free 方案的写性能瓶颈**：现有完全解耦的 KVS（如 FUSEE）采用 lock-free 乐观方案，将索引条目限制为 8 字节 CAS 操作，无法内联存储小值，所有读取都需要两次 round trip（索引 + extent），在写密集工作负载下性能下降明显。

2. **RDMA 原子操作的硬件瓶颈**：RDMA atomic 操作在主机内存上有严重的吞吐量上限（约 50 MOPS），竞争场景下仅 3 MOPS，这使得基于锁的方案在之前被认为不可行。

3. **传统 cuckoo hashing 缺乏局部性**：cuckoo hashing 的两个哈希位置是独立随机的，导致 cuckoo path 可能跨越整个表，使得锁获取需要多次 round trip，客户端缓存也无法有效利用。

4. **锁持有期间的客户端故障处理**：完全解耦环境中没有服务端 CPU 来检测和恢复持锁客户端的故障，lock-based 系统需要在纯 one-sided RDMA 操作下实现故障检测与恢复。

---

## 三、洞察与设计

**关键洞察**：通过使 cuckoo hashing 的两个哈希位置之间的距离成为可调参数（dependent hashing），可以概率性地将绝大多数 cuckoo path 限制在较小的内存范围内，从而使锁获取可以在单次 RDMA masked CAS 操作中完成——同时将锁表缩小到能完全放入 NIC 设备内存（256 KB），获得 3× 的原子操作性能提升。

基于这一洞察，RCuckoo 的核心设计包括：

- **Locality-enhanced dependent hashing**：主位置 L₁(K) 均匀随机，副位置 L₂(K) 与 L₁ 的偏移量呈指数衰减分布（由参数 f 控制）。当 f=2.3 时，68% 的键的两个位置相距 ≤5 行，95% 的 cuckoo path 跨度 ≤32 行，99% ≤256 行。
- **NIC 设备内存锁表**：单 bit 锁设计，每个锁保护 16 行，整个锁表可放入 ConnectX-5 的 256 KB 设备内存，避免 PCIe round trip，竞争场景下吞吐提升 3×。
- **Masked CAS 批量锁获取**：利用 RDMA masked CAS 一次操作获取最多 64 个锁，配合 dependent hashing 的局部性，约 99% 的 insert 操作只需一次 MCAS 即可获取所有锁。
- **投机性本地搜索 + 二次搜索**：客户端维护 64 KB 的索引缓存，先用本地缓存做 BFS 找 cuckoo path（投机搜索），获锁后同步缓存并验证，失败则在已锁行内做二次搜索。
- **Lease-based 故障恢复**：通过超时检测持锁故障客户端，repair lease 机制允许其他客户端分区并行回收搁浅锁，确定性状态转换修复表。

操作复杂度：
- **Read**：小值 1 round trip（lock-free），大值 2 round trip
- **Update/Delete**：2 round trip（无竞争时）
- **Insert**：中位数 2 round trip，随表填充率增加而上升

---

## 四、实现细节

- **C++ 实现**：8.7K 行高性能版本，需要 OFED-4.9 以支持 masked CAS 和设备映射内存（ConnectX-5 NIC）。
- **Python 实现**：12K 行模拟版本，用于正确性测试。
- **索引表结构**：每行 8 个关联条目 + 8-bit 版本号 + 64-bit CRC。条目可以是内联 key/value 对或 key + 48-bit extent 指针 + 23-bit 大小字段，最低位标识类型。
- **虚拟锁表**：当表超过 64M 行时，多个逻辑锁映射到同一物理锁（l mod P），支持任意大小的表。
- **哈希函数**：使用 xxHash，三个独立盐值生成 h₁、h₂、h₃。
- **BFS cuckoo path 搜索**：最大搜索深度为 5，客户端缓存 64 KB。
- **Extent 管理**：每个客户端有私有的 RDMA 注册 extent 区域，本地 slab allocator 管理，无竞争。
- **故障超时**：100 ms（远大于 99th percentile insert 时间 50 μs），RDMA 最大重试次数 3。

---

## 五、实验结果

**测试平台**：9 节点集群，双路 Intel Xeon E5-2650 @ 2.20 GHz，256 GB RAM，ConnectX-5 双端口 NIC，100 Gbps Mellanox Onyx 交换机。1 台内存服务器 + 8 台客户端机器。

**对比系统**：FUSEE（完全解耦，lock-free），Clover（部分解耦，有元数据服务器），Sherman（分布式 B-tree，有内存侧 CPU）。

**工作负载**：YCSB，100M 条目表，预填充 90M，32-bit key + 32-bit value，Zipf(0.99) 分布。

| 工作负载 | RCuckoo 优势 | 说明 |
|---------|-------------|------|
| YCSB-C (100% read) | 最高吞吐，~38 MOPS | 内联单 round trip 读，优于所有系统 |
| YCSB-B (95/5 read/update) | 2.5× vs Sherman | Sherman 因锁竞争严重瓶颈 |
| YCSB-A (50/50 read/update) | 7.1× vs Sherman | 320 客户端时 RCuckoo 持续扩展，FUSEE 在 250 客户端后无法扩展 |
| Insert-only (YCSB-W) | 11.5→4.5 MOPS（空→90% 填充） | I/O 放大上限 ~2×，FUSEE 最高 9.1 MOPS 但不受填充率影响 |

**故障容忍**：在约 500 次/秒客户端故障前保持接近满吞吐；细粒度锁恢复更快。

**内联 vs Extent**：内联在 YCSB-B 上提升 21%，YCSB-A 上提升 37%。

---

## 六、批判性分析

1. **评估仅限小值场景**：论文坦承聚焦于 32-bit key + 32-bit value，这是 RCuckoo 内联优势最大的场景。当值增大到 64 字节以上时读性能即受链路速率限制，此时与 extent-based 方案的差距大幅缩小。论文未充分讨论在实际数据中心中小值占比多大。

2. **Insert 性能随填充率退化显著**：在 90% 填充率时 insert-only 吞吐从 11.5 降到 4.5 MOPS（降幅 61%），而 FUSEE 的 insert 性能不受填充率影响。论文以"insert-only workloads are rare in practice"轻描淡写了这一弱点，但混合工作负载下高填充率仍会影响整体性能。

3. **无复制/容错讨论**：RCuckoo 使用单内存服务器，不支持复制。论文将复制推迟到 future work，但对于生产环境这是硬性要求。FUSEE 设计上支持复制，RCuckoo 加入复制后性能如何是未知数。

4. **硬件依赖性强**：要求 ConnectX-5 NIC 的 masked CAS 和设备内存特性（OFED-4.9），这限制了系统的可移植性。256 KB NIC 内存的限制也意味着超大表必须使用虚拟锁（引入额外 false sharing）。

5. **不支持 range query**：RCuckoo 是 unordered KVS，不支持范围查询，而 Sherman 支持。论文在比较中选择了对 RCuckoo 有利的点查询工作负载。

6. **Zipf(0.99) 偏斜度极高**：实验使用极度偏斜的 Zipf(0.99) 分布，这对 RCuckoo 的客户端缓存和局部性优化有利。论文提到 Clover 在均匀分布下性能下降，但未系统展示 RCuckoo 在不同偏斜度下的表现。

---

## 七、总结

RCuckoo 通过 locality-enhanced dependent hashing 将 cuckoo hashing 的随机性转化为可控的局部性，使得基于锁的完全解耦 KVS 成为可能。其核心贡献是将锁表压缩到 NIC 设备内存中并利用 masked CAS 实现高效锁获取，在小值场景下实现单 round trip 读取。系统在 YCSB 基准测试中显著优于 FUSEE、Clover 和 Sherman，特别是在写密集工作负载下可达 7× 吞吐提升。主要局限在于：仅支持小值内联场景下优势明显、insert 性能随填充率退化、不支持复制和范围查询、以及对特定 RDMA NIC 硬件特性的依赖。
