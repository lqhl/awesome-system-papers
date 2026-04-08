# DMTree: Towards Efficient Tree Indexing on Disaggregated Memory via Compute-side Collaborative Design

**作者**：Guoli Wei, Yongkun Li (通讯作者), Haoze Song, Tao Li, Lulu Yao, Yinlong Xu, Heming Cui（中国科学技术大学、香港大学）
**会议**：USENIX FAST 2026
**链接**：https://www.usenix.org/conference/fast26/presentation/wei
**源文件**：[[fast2026-wei.pdf]]

---

## 一、背景

Disaggregated Memory（DM）架构将计算和存储资源分离为独立的资源池，计算服务器拥有大量 CPU 但内存有限（1~10GB），内存服务器拥有大内存（100s~1000s GB）但 CPU 极少（1~2 核）。两者通过 RDMA 快速网络通信。One-sided RDMA 允许计算服务器直接访问远程内存而不占用内存服务器 CPU，因此成为 DM 架构上的主流通信模式。

在 DM 上构建高性能 range index 是数据库和 KV 存储等应用的关键需求，需要同时高效支持 point 操作（search、insert、update）和 range 操作（scan）。现有 DM 上的 range index 包括 B+-tree（Sherman）、learned index（ROLEX）、ART（SMART）、LSM-tree（dLSM）以及 hybrid index（CHIME）等。

---

## 二、要解决的问题

现有 DM 上的 range index 在 RDMA 资源利用上存在根本性的权衡困境：

1. **连续范围存储类（B+-tree、learned index）的带宽瓶颈**：每个 leaf node 存储多个 KV entry，point 操作读取单个 entry 需要读整个 node，导致 ~32× 读放大，Sherman/ROLEX 仅达到期望搜索性能的 16.3-18.8%。

2. **精确定位类（ART）的 IOPS 瓶颈**：每个 leaf node 只存一个 KV entry，scan 需要大量小粒度 RDMA 请求，SMART 的 scan 性能仅为 Sherman 的 35.5%，insert 性能也仅为期望值的 35.8%。

3. **混合方案（CHIME、FP-B+-tree）的残余瓶颈**：虽然结合了连续存储与精确定位（hashing/fingerprint），但额外的 RDMA 请求用于 fingerprint 读取和 leaf node 加锁，仍然加剧 IOPS 瓶颈。FP-B+-tree 搜索性能仅为期望值的 42.7%，CHIME/FP-B+-tree 的 insert 性能仅为期望值的 23.9-45.4%。

4. **计算服务器 RDMA 资源未被充分利用**：所有现有方案的网络请求都聚集在内存服务器上，而计算服务器之间的 RDMA 资源始终未饱和。

---

## 三、洞察与设计

**关键洞察**：在 DM 架构中，内存服务器的 RDMA 网络资源（IOPS 和带宽）容易成为瓶颈，而计算服务器之间的 RDMA 资源始终处于未饱和状态。可以将数据定位（data locating）和锁操作（locking）从内存服务器卸载到计算服务器，利用计算服务器之间的空闲 RDMA 资源来缓解内存服务器的网络瓶颈。

基于此洞察，DMTree 提出 **compute-side collaborative design**，包含两个核心组件：

### 1. Compute-side Collaborative Cache（§3.2）

DMTree 采用 FP-B+-tree 结构（leaf node 包含多个 KV entry + fingerprint table），在此基础上：

- **Private internal cache**：每台计算服务器私有缓存 internal tree（与 Sherman 类似），减少远程 internal tree 遍历。仅缓存 bottom-level internal nodes，上层本地构建。
- **Collaborative fingerprint storage**：fingerprint table 不再从内存服务器读取，而是分布存储在计算服务器上。每个 fingerprint table 有一个 primary 副本（通过一致性哈希确定归属），其他服务器持有 cached 副本。搜索时先从 peer 计算服务器读取 fingerprint table，再根据定位结果从内存服务器读取 KV entry，将 fingerprint 读取的 IOPS 开销从内存服务器转移到计算服务器。

**一致性机制**：
- Fingerprint 一致性：primary 同步更新，cached 异步更新；不一致时回退到 primary 重读。
- Internal cache 一致性：通过 entry-level version ID 验证缓存与远程数据的一致性，version 不匹配时触发 cache invalidation。

### 2. Compute-side Collaborative Concurrency（§3.3）

- **Collaborative locking**：将 leaf node 的 lock field 存储在计算服务器的 primary fingerprint table 中，通过计算服务器间的 RDMA_CAS 完成加锁，避免对内存服务器的 IOPS 消耗。
- **Collaborative embedded unlocking**：将解锁操作嵌入到 fingerprint table 的写回中（lock field 放在 fingerprint table 末尾），insert 操作的 fingerprint 写入和解锁合并为一次 RDMA_WRITE。
- **Optimistic locking for read-write conflicts**：使用 CRC checksum 检测读写冲突，避免读操作加锁。

通过以上设计，update 操作的 5 次 RDMA 请求中有 3 次可以从内存服务器转移到计算服务器。

---

## 四、实现细节

- **树结构**：基于 FP-B+-tree，每个 leaf node ~1.3KB（span size=32），包含 32 个 KV entry + fingerprint table（每个 fingerprint 1 byte）+ metadata（Kmax、Kmin、right pointer、version）。
- **Fingerprint 分配**：通过一致性哈希（consistent_hash(fp_offset)）将 fingerprint table 的 primary 归属分配到计算服务器，支持虚拟节点做负载均衡。
- **Scan 优化**：利用 fingerprint table 过滤 leaf node 中的空 entry，避免读取未写入的空间，节省带宽。
- **Batch 优化**：沿用 read delegation 和 write combining 设计，将同一计算服务器的并发请求合批，但设置 batch size 上限以控制尾延迟。
- **故障处理**：计算服务器故障时，通过一致性哈希重新分配 primary fingerprint table，新 primary 可从远程内存的 KV 数据重建 fingerprint。
- **CXL 兼容性**：设计原则与 CXL 兼容，one-sided RDMA 语义对应 CXL 的 load/store 指令。
- **源码**：https://github.com/muouim/DMTree

---

## 五、实验结果

**实验环境**：7 台机器（6 计算 + 1 内存），Intel Xeon Gold 80 核，128GB DRAM，100Gbps Mellanox ConnectX-6 RNIC，100Gbps Ethernet switch。内存服务器分配单个 CPU 核。每台计算服务器 25GB 内存。预加载 10 亿 KV entry（32B key + 8B value）。

**基线**：Sherman（B+-tree）、dLSM（LSM-tree）、ROLEX（learned index）、SMART（ART）、CHIME（hybrid index）。

### Micro-benchmark 结果（Uniform + Zipfian）

| 操作 | DMTree vs 最优基线 | DMTree vs 最差基线 | 关键原因 |
|------|-------------------|-------------------|---------|
| Search | 接近 expected search | 4.5-5.2× vs Sherman/ROLEX | 消除读放大 |
| Insert | 接近 expected insert | 2.1-5.7× vs dLSM | 卸载 fingerprint 和 lock 到 compute-side |
| Update | 1.4-4.3× vs baselines（Uniform） | — | collaborative locking 减少 IOPS |
| Scan | 3.2× vs SMART | 1.1-1.3× vs Sherman/CHIME | 连续存储 + 空 entry 过滤 |

### YCSB 混合负载

- 搜索/写密集型（A-D, F）：DMTree 比 Sherman/ROLEX 高 3.8-9.7×，比 dLSM 高 1.4-8.6×，比 CHIME 高 1.1-1.7×。
- Scan 密集型（E）：DMTree 比 SMART 高 3.2×，与 Sherman/ROLEX 相当。

### 尾延迟（P99）

- Search 尾延迟比 Sherman/ROLEX 降低最多 64%，比 SMART/CHIME 降低 26-31%。
- Insert 尾延迟比 baselines 降低 28-80%。
- Scan 尾延迟比 SMART 降低 70%。

### 内存开销

- 计算服务器：DMTree 5.4GB（internal tree 2.3GB + fingerprint 3.1GB），Sherman 2.1GB，SMART 22.5GB，CHIME 4.5GB。
- 内存服务器：10 亿 32B entry，DMTree 60.1GB vs Sherman 54.2GB（额外 version + CRC 字段）。

### 计算开销

- Fingerprint 遍历仅占搜索总延迟的 5%，写操作中 fingerprint 遍历 + 同步占 19.4%。

---

## 六、批判性分析

1. **实验规模与部署场景的差距**：实验仅使用 6 计算 + 1 内存服务器的小规模集群，而 DM 架构的核心优势在于大规模资源池。Fingerprint table 的一致性维护和同步开销在数十或上百台计算服务器时是否仍然可控，论文未给出充分验证。§3.2.3 的 scalability 讨论仅停留在定性分析层面。

2. **内存服务器单核假设过于简化**：论文将内存服务器限制为单个 CPU 核以体现 DM 架构特征，但实际 DM 部署中内存服务器可能有少量但不止一个核。这一设置倾向于放大 IOPS 瓶颈，使 DMTree 的 compute-side offloading 收益显得更大。

3. **Fingerprint 异步一致性的隐藏代价**：论文声称 fingerprint cache 不一致可以"直接检测"并回退，但未量化不一致发生的频率及其对实际负载的性能影响。在写密集负载下，高频的 primary fingerprint 回读可能抵消 collaborative caching 的收益。

4. **故障恢复的轻描淡写**：§4.3 声称 DMTree 兼容轻量级故障检测和恢复协议，但 fingerprint table 重建需要扫描远程内存中的 KV 数据，在大规模数据下恢复时间可能很长，论文未给出任何恢复延迟的实测数据。

5. **Scan 场景的优势有限**：DMTree 对 scan 的提升主要来自空 entry 过滤（1.1-1.3× vs Sherman/CHIME），而非核心 collaborative design 带来的，ROLEX 也达到了类似的 scan 性能。论文的 scan 改进并不如 point 操作那样令人信服。

6. **CXL 兼容性的讨论缺乏实质验证**：§4.3 关于 CXL 兼容性的讨论纯粹是推测性的，没有任何 CXL 环境下的实验。考虑到 CXL 的延迟和带宽特征与 RDMA 显著不同，compute-side collaborative design 在 CXL 下的实际收益存疑。

---

## 七、总结

DMTree 针对 DM 架构上 range index 的 RDMA 资源利用困境，提出 compute-side collaborative design，将 fingerprint 存储和 lock 操作从内存服务器卸载到计算服务器之间的空闲 RDMA 资源上。实验表明 DMTree 在 point 和 range 操作上均优于现有 SOTA（最高 5.7× 提升）。其核心局限在于：仅在小规模集群上验证，fingerprint 一致性的异步机制在大规模高并发写场景下的表现不明，以及故障恢复机制缺乏实测验证。该工作的思路——利用计算节点间的空闲网络资源来缓解存储节点瓶颈——对 DM 架构上的系统设计具有普遍参考价值。
