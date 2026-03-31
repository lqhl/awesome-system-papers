# Tigon: A Distributed Database for a CXL Pod

**作者**：Yibo Huang, Haowei Chen, Newton Ni（The University of Texas at Austin）；Yan Sun（University of Illinois Urbana–Champaign）；Vijay Chidambaram, Dixin Tang, Emmett Witchel（The University of Texas at Austin）
**会议**：OSDI 2025（19th USENIX Symposium on Operating Systems Design and Implementation），July 7–9, 2025, Boston, MA
**DOI**：https://www.usenix.org/conference/osdi25/presentation/huang-yibo
**源文件**：[osdi25-huang-yibo.pdf](../../papers/osdi-2025/osdi25-huang-yibo.pdf)

---

## 一、背景

分布式事务数据库是数据库领域数十年来的核心挑战。传统的 shared-nothing 架构将数据分区到各主机，跨分区事务需要大量网络消息交换和两阶段提交（2PC），性能随多分区事务比例提升而急剧下降。RDMA 技术的兴起推动了共享/分离内存架构的研究，将数据集中存储以避免多分区事务问题，但 RDMA 的访问延迟仍在微秒级，同步开销依然显著。

CXL（Compute Express Link）作为新兴的高性能互联标准，基于 PCIe 5.0/6.0，允许多个主机通过普通 load/store 指令直接访问共享 CXL 内存，延迟远低于 RDMA。CXL 3.0/3.2 进一步支持跨主机硬件缓存一致性。一组共享 CXL 内存的主机被称为 **CXL pod**（通常 8–16 台机器连接到一个多端口 CXL 内存设备）。这为构建更高效的分布式数据库提供了新的机会。

---

## 二、要解决的问题

**CXL 内存本身的硬件限制**使得直接利用并不简单：

1. **更高延迟**：CXL 内存延迟（214–394 ns）是本地 DRAM（111–117 ns）的 1.6–3× 倍，带宽（18–52 GB/s）仅为本地 DRAM（218–246 GB/s）的 8–25%。
2. **有限的硬件缓存一致性（HWcc）容量**：CXL 3.0 虽然支持跨主机硬件缓存一致性，但由于 snoop filter 的面积限制，只有几十到几百 MB 的内存区域能被设置为硬件缓存一致。无法将所有数据库数据都放入 HWcc 区域。
3. **多分区事务开销**：传统方案无论是 shared-nothing（需要消息交换+2PC）还是 RDMA shared memory（高延迟），跨主机数据同步代价均很高。

核心问题是：**如何利用 CXL 内存的低延迟优势来高效同步跨主机并发数据访问，同时避免 CXL 内存的各种限制？**

---

## 三、核心设计

Tigon 的核心洞察是：尽管数据库总量可能很大，但**在任意时刻被不同主机并发读写的 tuple 集合（CAT，Cross-host Active Tuples）非常小**。例如 TPC-C 中，假设 1000 个 CPU core 各执行一个事务，每个事务访问约 39 个 tuple（约 7 KB），则 CAT 最多只有约 7 MB。

**关键设计原则：将 CAT 维护在 CXL 内存中，其余数据留在本地 DRAM。**

### 数据按同步需求分层

- **HWcc 区域**（硬件缓存一致，有限）：存放需要频繁跨主机同步的元数据，如 CXL 索引、latch、2PL 锁元数据。每个 HWcc record 仅 8 字节，包含：1-bit latch、8-bit 2pl-lock、1-bit has-next-key、1-bit is-dirty、1-bit clock-bit、16-bit SWcc-bitmap、36-bit SWcc-row-ptr。
- **SWcc 区域**（非硬件缓存一致的 CXL 内存）：存放实际 tuple 数据（SWcc row），通过软件缓存一致协议管理。
- **本地 DRAM**：存放各主机自己的分区数据（local row + local index），低延迟高带宽访问。

### 软件缓存一致性协议（SWcc）

Tigon 将 SWcc-bitmap（16-bit，每 bit 代表一个主机）嵌入 HWcc record 中，与数据库自身的 latch 协议联合设计。当某主机首次读 SWcc row 时，flush 相关 cacheline，从 CXL 内存加载数据并设置对应 bit；只要无其他主机写入（bit 保持置位），该主机可使用 cacheable load 复用 CPU cache。写入方在修改后清除所有其他主机的 bit。

### 避免 2PC

Tigon 通过两个关键 insight 避免 2PC：
1. 将 CAT 中的 tuple 移入 CXL 内存后，单个主机（transaction worker）可以完成事务涉及的所有 tuple 修改（通过 CXL 原子操作上锁）。
2. 索引修改无需记录日志——恢复时可从 tuple 重建索引。

因此一个主机可独立完成事务的执行+提交+日志记录，无需 2PC。

### 并发控制

- 2PL（SS2PL）+ NO_WAIT 死锁避免策略
- next-key locking 防止 phantom 问题：在 CXL index 中为每个 tuple 增加 has-next-key 标志，指示其在 CXL index 中的下一个 key 是否也是 local index 中的下一个 key，从而安全处理跨主机的 next-key lock 获取。

---

## 四、实现细节

- 基于 Lotus 代码库（约 18K LoC）构建，新增约 5K LoC，语言为 C++。
- CXL 内存通过 Linux 暴露为无 CPU 的 NUMA 节点；修改 mimalloc 内存分配器以使用 CXL 内存区域。
- Local index 和 CXL index 均采用现有 B+ 树实现，扩展支持 next-key locking 和 optimistic crabbing 索引并发控制。
- 使用 offset pointer 使 CXL 内存中的数据结构位置无关（position-independent）。
- CXL-based 消息传输层：在 CXL 内存中实现 lock-free MPSC ring buffer，ring buffer 元数据（head/tail）存于 HWcc 区域，buffer 条目存于 SWcc 区域。
- 数据替换策略：使用 CLOCK 算法（而非 LRU）决定哪个 tuple 移回本地 DRAM，以减少 HWcc 内存中 metadata 维护开销。CLOCK 比 LRU 少用 33% HWcc 内存，且避免了 LRU list 维护的锁竞争。
- Epoch-based group commit：基于 SiloR 的日志协议，全局 epoch 存于 HWcc 区域，周期推进（约 10ms）；每个 worker thread 独立生成日志记录，由专用 logger thread 持久化到本地 SSD。
- Epoch-based 内存回收（EBR）：每个 worker thread 的本地 epoch 存于 HWcc 区域。

---

## 五、实验结果

**实验平台**：在单台机器（Intel Xeon Platinum 8568Y+，512GB DRAM，128GB CXL 1.1 内存设备）上模拟 8 个 VM 组成的 CXL pod，每个 VM 5 vCPUs、10GB 本地 DRAM，通过 SR-IOV 虚拟化网络（100Gbps NIC，VM 间 TCP over Ethernet）。CXL 延迟约为本地 DRAM 的 1.6×，带宽约为 13%。HWcc 预算固定为 200MB。

**基线**：Sundial+（OCC+2PL，CXL 消息传输）、DS2PL+（2PL，CXL 消息传输）、Motor（RDMA shared memory，25Gbps NIC）

**测试负载**：TPC-C（24 warehouses，2.2GB）和 YCSB 变体（2.4M tuples，2.2GB，Zipfian 分布）

### 端到端性能（TPC-C）

| 多分区事务比例 | Tigon vs Sundial+ | Tigon vs DS2PL+ | Tigon vs Motor |
|---|---|---|---|
| 0/0（无多分区） | −37%（Sundial+ 更快） | −8.5%（DS2PL+ 更快） | N/A |
| 10/15（默认） | ≈持平 | 略优 | 15.9×–18.5× |
| 60/90 | +75% | +2.5× | 15.9×–18.5× |

### 可扩展性（1→8 主机）

| 负载 | Tigon 提升 | Sundial+ 提升 | DS2PL+ 提升 |
|---|---|---|---|
| TPC-C 60/90 | **5.7×** | 2.4× | 2.1× |
| YCSB 95%R/5%W | **3.5×** | 1.4× | 1.5× |

### HWcc 内存预算影响

- 50MB HWcc：性能仅比 200MB（无限）慢 5.8%（TPC-C）
- 10MB HWcc：性能明显下降，大量 tuple 在 CXL 与 DRAM 之间频繁移动

### 日志延迟权衡（TPC-C，无多分区事务）

| Epoch 时长 | 吞吐量（Ktx/s） | p50 延迟（ms） | p99 延迟（ms） |
|---|---|---|---|
| 1ms | 508 | 17.7 | 345.0 |
| 10ms | 525 | 22.6 | 54.9 |
| 50ms | 540 | 43.3 | 86.8 |

---

## 六、批判性分析

**1. 实验平台的根本性局限**

Tigon 使用单台物理机上的 8 个 VM 模拟 CXL pod，VM 间"硬件缓存一致性"实际上是同一台物理机的 CPU 缓存一致性协议，比真实跨主机 CXL 一致性**快得多**。作者承认这个问题，并提供了一个保守估计：若跨主机 back-invalidation 比本地慢 4×，Tigon 对比 Sundial+ 的优势从 75% 缩减到仅 2.8%（60/90 TPC-C）。这意味着在关键场景下，Tigon 相对于改进后的 shared-nothing 数据库的优势几乎消失。**核心的实验在真实 CXL 硬件上尚无法验证**，结论的可靠性存疑。

**2. Motor 对比的公平性问题**

Motor 只使用 25Gbps NIC（作者在原始 Motor 论文中获得的最大吞吐量为 100K/s，而 Tigon 在相同配置下达到 460K–528K/s）。作者承认 Motor 受限于测试机器的有限网络带宽。因此 Motor 的对比基本上是 CXL 内存与慢速网络的对比，而非 CXL 与现代高速 RDMA 的真实比较。

**3. 无多分区事务时性能劣势被轻描淡写**

在 0/0（无多分区事务）配置下，Sundial+ 比 Tigon 快 37%，DS2PL+ 快 8.5%。作者将此归因于 next-key locking 的额外开销（10–12%）。然而在许多真实工作负载中，多分区事务并不占主导（10/15 是 TPC-C 的默认配置），Tigon 的优势在接近默认配置时相当有限。

**4. 故障模型过于简化**

Tigon 采用 fail-stop 模型，任何单个组件的故障都会导致整个系统失败并需要恢复。这与生产级分布式数据库（通常需要高可用性和局部故障容忍）的要求相差甚远。日志记录也只写到本地 SSD，没有跨主机复制，单节点磁盘故障即导致数据丢失。

**5. 可扩展性上限未知**

由于硬件限制，作者无法实验验证 Tigon 超过 8 主机后的行为，而列举了多个潜在瓶颈（原子指令在 CXL 内存上的争用、HWcc 区域的固定大小等）。CXL pod 本身的规模上限（16 主机）也意味着 Tigon 不是一个适合大规模集群的方案。

**6. 并发控制协议未充分探索**

作者承认未实现 OCC 和 MVCC，理由是"超出本文范围"，但已有大量研究表明 OCC/MVCC 在读密集型工作负载下性能更好（YCSB 100%R 的结果已显示 Tigon 在此类场景并不突出）。这一选择使得 Tigon 在读密集场景下相比 Sundial+ 缺乏竞争力。

---

## 七、总结

Tigon 是第一个利用 CXL 内存同步跨主机并发数据访问的分布式内存数据库，核心贡献在于通过维护 Cross-host Active Tuples（CAT）于 CXL 共享内存中，将多分区事务的消息传递开销转化为内存数据结构操作，并通过软件缓存一致性协议克服 CXL 硬件缓存一致区域有限的问题，同时避免两阶段提交。在多分区事务比例较高时，Tigon 相比改进版 shared-nothing 数据库提升明显（最高 2.5×），可扩展性也显著更好。主要局限在于：实验基于 VM 模拟而非真实 CXL 跨主机硬件、故障模型过于简化、CXL pod 规模上限限制扩展性，且在低多分区事务比例场景下优势有限。
