# HDTX: Fast Distributed Transactions for RDMA-based Disaggregated Memory

**作者**：Haodi Lu, Haikun Liu*, Yujian Zhang, Zhuohui Duan, Xiaofei Liao, Hai Jin, Yu Zhang（华中科技大学）
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/lu
**源文件**：[[atc2025-lu.pdf]]

---

## 一、背景

资源解耦（Resource Disaggregation）是数据中心架构的重要演进方向，将传统单体服务器拆分为独立的计算节点和内存节点，通过 RDMA 或 CXL 高速网络互连。这种解耦内存（Disaggregated Memory, DM）架构显著提升了内存利用率和弹性扩展能力，已获得学术界和工业界广泛关注（如 Microsoft、Google 等）。

在 DM 架构中，当多个计算节点并发访问相关联的远程数据对象时，需要通过分布式事务（distributed transactions, dtxns）保证数据一致性。然而，DM 架构下的远程内存访问延迟远高于本地内存，且内存节点 CPU 资源极为有限，使得传统基于 RDMA 的分布式事务系统难以高效运行。

---

## 二、要解决的问题

现有 RDMA 分布式事务系统在 DM 架构下存在三个核心挑战：

1. **多阶段协议导致的高 RTT 开销（C.1）**：传统 OCC + PBR 协议需要 5 个阶段（Execution → Locking → Validation → Commit Backup → Commit Primary），每阶段至少 1 个 RTT。即使 FORD 优化后仍需 4 个阶段（3 RTT）。多次网络往返显著增加事务延迟。

2. **Commit 阶段数据同步效率低（C.2）**：DM 节点缺乏 CPU 资源来执行数据同步，计算节点必须分两轮将日志和最新数据从计算节点传到所有内存节点，造成 RDMA 带宽消耗大。

3. **DM 节点无法调度关键事务（C.3）**：传统 priority-based locking 依赖存储节点 CPU 进行全局调度，但 DM 节点 CPU 资源不足，无法支持灵活的事务优先级调度，导致关键任务尾延迟高。

---

## 三、洞察与设计

**关键洞察**：通过采用 redo log 而非 undo log，Validation 阶段和 Commit 阶段之间不存在数据依赖，因此可以合并执行；同时 redo log 已包含最新数据，数据同步操作可以通过 RDMA Wait/Enable 原语卸载到内存节点的 RNIC 上自主完成，无需 CPU 参与。

基于这一洞察，HDTX 提出三项核心设计：

### 1. Fast Commit Protocol (FCP)

- 使用 redo log + visibility control 技术，将传统 5 阶段协议压缩为 3 阶段：
  - **Execution & Locking**（1 RTT）：通过批量 RDMA FAA + RDMA Read 同时加锁并读取数据
  - **Validation & Commit**（1 RTT）：同时验证 read-only set 版本并将 redo log 写入所有副本，用 RDMA FAA 原子标记数据为 invisible
  - **Background Release**（异步）：更新数据、版本号、释放锁
- 关键在于 redo log 的写入与 visibility control 的 RDMA 原语天然保序（RDMA Write + Atomic 顺序有保证），无需额外 Fence，因此一个 RTT 内即可完成

### 2. RDMA-enabled Release Phase Offloading

- 在初始化时预先在内存节点创建两个 work queue，配置 RDMA Wait/Enable 原语链
- Release 阶段，计算节点只需发一个 RDMA Send 触发内存节点 RNIC 自主执行：用 RDMA Write 将 redo log 复制到数据区、更新版本号，用 RDMA FAA 修改 visibility bit 并释放锁
- 整个过程无需内存节点 CPU 介入，避免了额外的跨节点数据传输

### 3. Decentralized Priority-based Locking

- 将 64-bit 锁对象分为 prioritized queue（<Pc, Pm>）和 normal queue（<Nc, Nm>）两个 FIFO 队列
- 基于 Lamport's Bakery 算法，通过 RDMA FAA 原子操作获取 token
- 高优先级请求插入 prioritized queue，释放锁时优先服务该队列
- 支持动态优先级提升：多次获锁失败的事务自动升级为高优先级

---

## 四、实现细节

- **数据存储**：内存节点使用 hash table 存储 key-value 对象，最大对象 1KB；元数据和数据可分区存储，通过批量 RDMA Read 一次 RTT 获取
- **元数据缓存**：计算节点缓存 GB 级元数据，大多数事务可以一个 RTT 完成锁获取和数据读取
- **持久化**：利用 Intel Optane DCPMM（App Direct Mode），通过 RDMA read-after-write（RDMA Write + RDMA Read）在一个 RTT 内保证远程持久化
- **Write-only 优化**：纯写事务可在单个 RTT 内提交——直接生成 redo log 发送并同时加锁
- **锁溢出处理**：每个 segment 最高位作为 canary value 检测溢出；当前持锁节点检测到溢出后通过 RDMA CAS 重置锁
- **死锁处理**：基于 lease 机制，当数据可见但 elapsed time 超过 2 倍 lease 过期时间，任一协调者通过 RDMA CAS 将锁移交给后继者
- **故障恢复**：非拜占庭故障模型，支持计算节点/内存节点/网络故障恢复
- 源代码开源于 GitHub

---

## 五、实验结果

**测试环境**：5 台服务器，128GB DRAM + 1TB Intel Optane DCPMM，Intel Xeon Gold 6230 (20 cores, 2.10GHz)，Mellanox ConnectX-3 40/56 GbE RNIC。2 台内存节点（2-way replication），1-3 台计算节点。

**基线**：FORD（DM 系统 SOTA）、FaRM（经典 RDMA 事务系统，适配 DM 版本）

### 端到端性能（16 threads × 7 coroutines）

| 指标 | TPC-C vs FORD | TPC-C vs FaRM | SmallBank | TATP |
|------|------|------|------|------|
| 平均延迟降低 | 72.1% | 88.3% | 显著降低 | 与 FORD 相当 |
| P99 延迟降低 | 60.9% | 82.7% | 显著降低 | — |
| 吞吐提升 | 84.7% | 2.08× | 显著提升 | 与 FORD 相当 |

### 各组件效果（微基准测试）

| 技术 | 效果 |
|------|------|
| FCP | skewed 访问下延迟降低最高 67.7% |
| Release Phase Offloading | 带宽消耗降低最高 19.1%，吞吐提升最高 18.5% |
| Priority-based Locking | 关键事务平均延迟降低 57.1%/52.8%，尾延迟降低 50.2%/63.3%（vs CAS/FAA） |

### 扩展性

- 3 个计算节点（420 并发协调者）下，TPC-C 吞吐比 FORD 提升 81.8%，比 FaRM 提升 2.06×
- 高竞争场景（8 warehouses）：延迟比 FORD/FaRM 降低 61.8%/83.4%，吞吐提升 83.2%/2.3×

---

## 六、批判性分析

1. **Validation 失败的代价被低估**：FCP 将 Validation 与 Commit 合并，意味着验证失败时 redo log 已经写入所有副本。论文声称回滚开销"rather low"，但只报告了 TPC-C 下 8.1%-9.8% 的 validation 失败率。在更极端的热点场景（如社交网络热门对象）中，这一比例可能远高于此，导致大量无效的 redo log 写入浪费带宽。

2. **RNIC 资源竞争问题未充分讨论**：RDMA offloading 依赖 RNIC 执行额外的 Wait/Enable/Write 操作链，在高并发场景下 RNIC 成为瓶颈的风险未被量化。论文仅承认"Wait/Enable primitives may slow down the RNIC pipeline"，但缺乏 RNIC 资源利用率的分析。

3. **硬件依赖性强**：系统依赖 Intel Optane DCPMM（已停产）实现持久化，依赖 ConnectX-3（较旧型号）的 Wait/Enable 原语语义。在新一代 CXL 内存或 ConnectX-7 RNIC 上的适配性未讨论。

4. **Priority-based locking 的公平性问题**：高优先级事务可能持续抢占 normal queue，造成普通事务饥饿。论文仅提到动态升级机制，但未分析升级阈值如何设置、在混合优先级负载下普通事务的性能退化程度。

5. **实验规模偏小**：仅使用 2 个内存节点 + 最多 3 个计算节点，与实际数据中心的 DM 池规模（数十到数百节点）差距很大。跨 rack 网络延迟、RNIC 异构性等问题未涉及。

6. **与 CXL-based DM 的关系未讨论**：CXL 正在成为 DM 的主流互连技术（延迟远低于 RDMA），HDTX 的设计假设（高 RTT 延迟、RNIC offloading）在 CXL 场景下是否仍然成立存疑。

---

## 七、AI Infra / MLSys 视角

1. **RDMA offloading 思路可迁移到分布式训练**：在分布式训练的 AllReduce 或参数同步中，利用 RNIC 的 Wait/Enable 原语自主完成梯度聚合和参数更新，减少 CPU 开销。特别是在 disaggregated GPU 集群中，类似的 RNIC offloading 技术可以降低通信延迟。

2. **Priority-based locking 对推理调度的启发**：LLM 推理场景中不同请求有不同 SLO 要求（如在线 vs 批处理），HDTX 的去中心化优先级锁机制可以借鉴到 KV cache 的共享访问调度中，优先服务延迟敏感的请求。

3. **Phase coalescing 方法论的通用价值**：通过深入分析 RDMA 原语的 ordering 语义来合并协议阶段的方法论，可以应用于分布式 checkpoint、模型状态同步等 AI 训练基础设施的协议优化。

4. **值得跟进的方向**：
   - 在 CXL-based disaggregated memory 上重新设计事务协议，探索 CXL 原子操作与 RDMA 原子操作的语义差异对系统设计的影响
   - 将 RNIC offloading 技术应用于分布式 KV cache（如 Mooncake、MemServe）的一致性管理
   - 探索 priority-based locking 在多租户 GPU 集群资源调度中的应用

---

## 八、总结

HDTX 是一个面向 RDMA 解耦内存架构的高性能分布式事务系统，通过三项创新将事务提交从传统的 5 RTT 压缩到 2 RTT：fast commit protocol 合并 Validation 与 Commit 阶段，RDMA offloading 将 Release 阶段卸载到 RNIC 自主执行，decentralized priority-based locking 支持关键事务的低延迟调度。系统在 TPC-C 等标准基准上相比 FORD 和 FaRM 取得显著的延迟和吞吐改进，尤其适合写密集、高竞争的 OLTP 场景。主要局限在于实验规模较小、强依赖特定 RDMA 硬件语义、以及在 CXL 新架构下的适用性尚不明确。
