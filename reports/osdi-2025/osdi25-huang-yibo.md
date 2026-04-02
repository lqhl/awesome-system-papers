# Tigon: A Distributed Database for a CXL Pod

**作者**：Yibo Huang, Haowei Chen, Newton Ni (The University of Texas at Austin); Yan Sun (University of Illinois Urbana–Champaign); Vijay Chidambaram, Dixin Tang, Emmett Witchel (The University of Texas at Austin)
**会议**：OSDI 2025
**链接**：https://www.usenix.org/conference/osdi25/presentation/huang-yibo
**源文件**：[[osdi25-huang-yibo.pdf]]

---

## 一、背景

构建高效的分布式事务数据库是数据库领域数十年来的核心挑战。现有分布式数据库通过网络同步跨主机的并发数据访问，需要大量消息交换，引入显著的性能开销。传统 shared-nothing 架构在多分区事务（multi-partition transactions）比例增高时性能急剧下降，因为需要频繁的跨主机消息传递和两阶段提交（2PC）协议。近年来 RDMA 被用于加速分布式事务处理，但 RDMA 网络的延迟仍比本地 DRAM 高一到两个数量级。

CXL（Compute Express Link）是一种基于 PCIe 5.0/6.0 的高性能互连标准，允许 CPU 通过普通 load/store 指令直接访问 CXL 内存，延迟远低于 RDMA。CXL 3.0/3.2 规范支持多主机共享 CXL 内存并提供硬件缓存一致性。一个 CXL pod 由少量机器（如 8-16 台）通过多端口直连共享 CXL 内存设备组成，提供了介于共享内存多处理器和分布式系统之间的新型计算架构。

---

## 二、要解决的问题

1. **CXL 内存的硬件限制**：CXL 内存相比本地 DRAM 延迟更高（214-394 ns vs. 111-117 ns）、带宽更低（18-52 GB/s vs. 218-246 GB/s），不能简单地将所有数据放在 CXL 内存中。

2. **硬件缓存一致性区域有限**：由于 snoop filter 面积预算限制，CXL 设备能提供硬件缓存一致性的内存区域仅为数十到数百 MB，远小于总 CXL 内存容量。数据库的同步结构必须重新组织以最小化对该区域的使用。

3. **跨主机并发数据访问的高效同步**：传统方案依赖网络消息传递和 2PC，开销巨大。需要一种新的方法利用 CXL 内存的原子操作能力来高效同步跨主机的并发访问，同时在数据动态移动时保证事务语义。

---

## 三、洞察与设计

**关键洞察**：虽然数据库总量可能很大，但在任意时刻被不同主机上运行的事务并发读写的 tuple 集合（Cross-host Active Tuples, CAT）很小。例如 TPC-C 中，每个事务平均访问 39 个 tuple（约 7KB 数据），1000 核系统的 CAT 仅约 7MB。因此，只需在 CXL 内存中高效维护这个小的 CAT 集合，即可将大量跨主机消息交换转化为数据结构操作。

基于此洞察，Tigon 的核心设计包括：

**数据组织与分离存储**：按同步需求分离数据——同步密集型元数据（索引、latch、lock）存储在硬件缓存一致性区域（HWcc），tuple 数据存储在软件缓存一致性区域（SWcc）。每个 HWcc record 仅 8 字节，包含 latch、2PL lock、dirty bit、SWcc-bitmap 和指向 SWcc row 的指针。

**软件缓存一致性协议**：与数据库内部同步机制协同设计，复用 HWcc-latch 中嵌入的 SWcc-bitmap（每主机一位）追踪各主机的缓存状态。当一个主机更新 SWcc row 时，清除其他主机的 bitmap 位，迫使它们下次访问时刷新缓存。

**避免 2PC**：通过在 CXL 内存中维护 CAT，单个主机可以完成事务涉及的所有 tuple 修改并在本地记录日志。索引修改无需记录日志（恢复时可从 tuple 重建），因此事务提交无需跨主机协调。

**CLOCK 替换策略**：用 1-bit clock-bit 代替 LRU 来决定将哪些 tuple 从 CXL 内存移回本地 DRAM，减少 HWcc 内存用量和同步开销。

---

## 四、实现细节

- 基于 Lotus 代码库用 C++ 实现，Lotus 约 18,000 LoC，Tigon 新增约 5,000 LoC。
- 本地索引和 CXL 索引均使用 B+-tree 实现，采用 optimistic crabbing 并发控制，扩展支持 next-key locking 以解决 phantom 问题。
- CXL 内存通过 Linux CPU-less NUMA node 暴露给应用，修改 mimalloc 内存分配器管理 CXL 内存区域。
- 跨主机通信使用 CXL 内存上的 lock-free MPSC ring buffer 实现，元数据（head/tail）在 HWcc 区域，buffer entries 在 non-HWcc 区域。
- 使用 offset pointer 实现位置无关的数据结构。SWcc-row-ptr 为 36-bit offset，可寻址 64GB 内存（cacheline 粒度下达 2TB）。
- 采用 epoch-based group commit（改编自 SiloR），每个 worker thread 独立生成 log record，由专用 logger thread 批量刷盘。
- 使用 epoch-based reclamation (EBR) 实现内存安全回收，每个 worker 的 local epoch number 存储在 HWcc 区域。
- 开源：https://github.com/ut-datasys/tigon

---

## 五、实验结果

**实验平台**：Intel Xeon Platinum 8568Y+ CPU，512GB 本地 DRAM，128GB CXL 1.1 内存设备（DDR5 4800，PCIe 5.0 x8）。CXL 延迟 259ns vs. 本地 DRAM 159ns（1.6×），CXL 带宽 31.8 GB/s vs. 238.3 GB/s（13%）。运行 8 个 VM 模拟 CXL pod，每个 VM 5 vCPUs + 10GB 本地 DRAM。HWcc 区域限制为 200MB。

**基线**：Sundial+、DS2PL+（均升级为 CXL 传输 + 额外 worker thread）、Motor（RDMA 分布式数据库）。

| 实验 | Tigon 表现 |
|------|-----------|
| TPC-C (60/90 multi-partition) | 比 Sundial+ 高 75%，比 DS2PL+ 高 2.5× |
| TPC-C vs Motor | 15.9×–18.5× 更高吞吐 |
| TPC-C (0/0 无跨分区) | 比 Sundial+ 低 37%，比 DS2PL+ 低 8.5% |
| YCSB (100% multi-partition, 50R/50W) | 比 Sundial+ 高 2.0×–2.3× |
| 扩展性 (1→8 hosts, TPC-C 60/90) | Tigon 5.7×, Sundial+ 2.4×, DS2PL+ 2.1× |
| HWcc 预算 50MB vs 无限 | 仅下降 5.8% |
| Next-key locking 开销 | 10%–12% |
| Shortcut pointer 优化 | TPC-C 吞吐提升 16% |
| is-dirty 优化 | YCSB read-only 提升 27%–60% |
| CLOCK vs LRU | CLOCK 在受限 HWcc 下快 2.4×，无限 HWcc 下快 17% |

**延迟**（10ms epoch, 无 multi-partition）：TPC-C p50 22.6ms, p99 54.9ms; YCSB 50R/50W p50 24.6ms, p99 62.3ms。

---

## 六、批判性分析

1. **模拟环境的有效性存疑**：实验使用单机 8 VM 模拟 CXL pod，VM 间的缓存一致性由物理机的缓存一致性实现，论文承认这比真实的跨主机硬件缓存一致性更快。但文中对此影响仅做了粗略估算（保守假设 back-invalidation 慢 4×，性能下降 41.4%），缺乏精确建模。目前不存在支持跨主机缓存一致性的物理 CXL 设备，这使得所有实验结果的外部有效性受限。

2. **无跨分区事务时 Tigon 反而更慢**：在 0/0 配置下，Tigon 比 Sundial+ 慢 37%，比 DS2PL+ 慢 8.5%。这说明 Tigon 的 CXL 数据管理机制（如 shortcut pointer 维护、next-key locking 等）引入了不可忽视的固定开销。对于以单分区事务为主的负载，Tigon 可能不是最优选择，但论文对此讨论不足。

3. **扩展性上限未知**：论文坦承因硬件限制无法验证超过 8 节点的扩展性。CXL pod 本身设计为 8-16 台机器，而 CXL 原子指令在高竞争下的扩展性、HWcc 区域固定大小等都可能成为瓶颈。论文未提供任何模拟或分析来预测这些极限。

4. **Group commit 导致高尾延迟**：1ms epoch 下 p99 延迟分别为 345ms（TPC-C）和 373ms（YCSB），这对延迟敏感型应用是不可接受的。虽然论文声明 Tigon 优先优化吞吐，但未讨论是否可以在保持 CXL 优势的同时降低尾延迟。

5. **仅支持 2PL，不支持 OCC/MVCC**：论文将支持 OCC 和 MVCC 留作 future work，但在无跨分区事务的场景下 Sundial+ 的 OCC 方案已明显优于 Tigon 的 2PL。这限制了 Tigon 在读密集型负载下的竞争力。

6. **基线选择与公平性**：Motor 使用的硬件（25Gbps NIC）远低于原论文配置，其吞吐（约 30K/s）受限于网络带宽而非系统设计。论文虽提及原论文报告约 100K/s，但 18.5× 的比较数字仍有误导性。

---

## 七、AI Infra / MLSys 视角

1. **CXL 内存层级对 AI 推理系统的启发**：Tigon 的 HWcc/SWcc 分离存储思路可迁移到 LLM 推理场景。例如，KV cache 管理可借鉴类似策略——将频繁被多请求共享的 KV cache 元数据（如 page table）放在硬件一致性区域，而实际 KV 数据放在更大的 CXL 内存中，降低 GPU 显存压力。

2. **CAT 概念对参数服务器的借鉴**：在分布式训练中，不同 worker 并发访问的参数子集（类似 CAT）远小于全量参数。可以利用 CXL pod 架构将热门参数动态迁移到 CXL 共享内存，减少基于 AllReduce 或 PS 的通信开销。

3. **软件缓存一致性协议的通用化**：Tigon 的 SWcc-bitmap 机制可以推广为 CXL pod 上通用的共享数据结构同步原语，用于 AI 推理中的 tensor 共享、模型权重更新广播等场景。

4. **值得跟进的方向**：
   - 在真实 CXL 3.0/3.2 硬件上验证跨主机缓存一致性的实际开销
   - 基于 CXL pod 构建 disaggregated KV cache 系统，服务于多实例 LLM 推理
   - 探索 CXL 内存上 MVCC 的高效实现，适配 AI workload 中读密集型的 checkpoint 和模型加载操作

---

## 八、总结

Tigon 是首个利用 CXL 内存原子操作同步跨主机并发数据访问的分布式内存数据库。其核心贡献在于：通过 CAT 概念将跨主机共享数据限制在小范围内，分离 HWcc/SWcc 存储以适配 CXL 硬件限制，设计软件缓存一致性协议扩展可用 CXL 容量，并通过改进的 2PL + epoch-based logging 避免 2PC。在多分区事务比例高的场景下，Tigon 比优化后的 shared-nothing 基线提升最高 2.5×，比 RDMA 方案提升最高 18.5×。主要局限包括：实验基于模拟环境（无真实跨主机 CXL 一致性硬件）、扩展性上限未验证、无跨分区事务时性能不及传统方案、仅支持 2PL 并发控制。
