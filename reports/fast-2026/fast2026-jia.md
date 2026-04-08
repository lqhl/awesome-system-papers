# CETOFS: A High-Performance File System with Host-Server Collaboration for Remote Storage

**作者**：Wenqing Jia, Dejun Jiang, Jin Xiong（中国科学院计算技术研究所 / 中国科学院大学）
**会议**：USENIX FAST 2026
**链接**：https://www.usenix.org/conference/fast26/presentation/jia
**源文件**：[[fast2026-jia.pdf]]

---

## 一、背景

存储解耦（storage disaggregation）是数据中心实现计算和存储资源独立扩展、提升资源利用率的重要方向。随着高性能 RDMA 网络和现代 NVMe SSD（如 Intel Optane P4800X，亚十微秒级延迟）的发展，基于 NVMe-over-Fabrics（NVMe-oF）协议的 disaggregated NVMe SSD 越来越受关注。NVMe-oF over RDMA 可以在微秒级延迟下远程访问 SSD，现有内核文件系统（如 Ext4、F2FS）可以直接通过 NVMe-over-RDMA 暴露的块设备来访问远程存储。

然而，内核文件系统的数据路径在远程存储场景下面临严重的性能瓶颈。内核软件栈（syscall、文件系统、NVMe 驱动、NVMe-over-RDMA 驱动）的开销占总延迟高达 65%–66%，其中 NVMe-over-RDMA 驱动单独就占 36%。此外，网络延迟加剧了并发访问的序列化开销和 failure-atomic IO 的数据搬运开销。

---

## 二、要解决的问题

1. **内核栈开销过重**：远程存储访问时，内核软件栈延迟占比高达 66%，超过了网络和设备延迟之和。NVMe-over-RDMA 驱动使用中断机制处理命令到达和 RDMA 操作完成，关键路径上有三次中断处理，成为最大瓶颈。

2. **并发序列化开销被放大**：内核文件系统使用 inode 级别的 reader-writer lock 在 host 端串行化并发访问。在远程存储场景下，每个序列化的操作都包含网络往返延迟，导致后续线程等待时间大幅增加。实验显示，并发写吞吐量随线程增加甚至下降 30%。

3. **failure-atomic IO 的数据搬运代价高**：Journaling 机制需要将日志写入远程 SSD，然后 checkpoint 时需将日志从远程读回 host 再写回远程，造成超过两倍的跨网络数据搬运。Copy-on-Write 机制同样导致频繁的远程元数据更新。

4. **用户态文件系统的权限检查难题**：将数据路径放到用户态后，应用可能向远程存储发送任意地址的请求，绕过文件系统的访问控制。已有方案要么依赖硬件修改（SR-IOV、IOMMU、SSD firmware），要么引入进程间通信开销。

---

## 三、洞察与设计

**关键洞察**：远程存储服务器端（target）拥有可用的计算能力，可以用来承担原本在 host 端执行的权限检查、并发控制和日志写入任务。将这些任务卸载到 target 端后，host 到 target 之间只需一次数据传输，无需多次往返或串行等待，从而将网络延迟的影响降到最低。

基于这一洞察，CETOFS 设计了三层协作架构：

**用户态-内核协作架构**：数据平面（read/write）完全放在用户态（U-Lib），避免内核栈开销；控制平面（元数据管理、权限元数据维护）复用内核文件系统（K-FS，基于 Ext4）。U-Lib 为每个打开的文件创建一对 RDMA ring buffer（server_rb 和 host_rb），应用线程通过 RDMA_WRITE_WITH_IMM 直接提交 IO 请求，通过 polling host_rb 检测完成。U-Lib 维护地址转换表（extent tree）将文件偏移映射到块地址。

**权限检查卸载**：在 target 端维护一个反向权限表（reverse permission table），记录每个块的 owner（文件 inode 号）。每个请求队列绑定一个文件 owner 和访问权限标志。T-Handler 检查两条规则：请求的块 owner 匹配队列 owner，且操作类型匹配权限标志。表大小为 SSD 容量的 ~0.2%（1TB SSD 对应 2GB 表），用 radix tree 缓存。

**并发控制卸载（Request Group）**：允许 host 端并发提交冲突请求到 target，由 target 端按 group 顺序执行。U-Lib 用轻量级 spin-lock 分配单调递增的 group ID：每个 write 请求创建新 group，相邻 read 请求共享同一 group。请求可并行发送到 target，T-Handler 通过 poller/finisher 算法保证 group 间的执行顺序。进一步的 merging group 策略使用两棵红黑树检测读写范围冲突，将无冲突的相邻 group 合并，使它们可以在 target 端并行执行。

**Redo logging 卸载**：应用通过 atomic_write_start/commit API 发起原子写。数据只需从 host 传输一次到 target，T-Handler 在 target 端执行 redo logging（先写 t_log，commit 后异步 checkpoint）。结合 transaction-aware 的批量提交和完成机制，减少 RDMA doorbell 的 MMIO 开销。

---

## 四、实现细节

- **U-Lib**：用户态 shim 库，通过拦截 syscall 透明接入应用。每个打开文件分配一个请求队列（最多 64K 并发打开文件）。每个 initiator 线程分配一个 RDMA QP（非每文件一个 QP，避免 QP 扩展性问题）。使用 fiemap ioctl 按需从 K-FS 获取偏移-块映射。
- **K-FS**：基于 Ext4，管理所有元数据，维护 admin queue 与 T-Handler 通信。块分配/释放时同步更新反向权限表（修改作为文件系统 journal 的一部分保证一致性）。
- **T-Handler**：target 端用户态进程，使用可配置数量的 worker 线程。每个 worker 交替执行 poller（接收请求、权限检查、提交 SSD IO）和 finisher（处理完成、推进 group）任务。维护 curr_gid、first_rid_table、curr_fin_reqs、curr_max_rid、rid_to_queue_pos 五个状态量保证 group 间顺序。
- **Append 处理**：分两阶段——先 fallocate 让 K-FS 分配块并设权限条目，再在用户态写数据。可用后台线程预分配优化 append-only 负载。
- **Transaction 管理**：mt_table（内存中事务表）、pt_table（持久化恢复表）、t_log（日志数据区）、log_index（原地址到日志地址映射，服务读请求）。

实验平台：两台 24 核 Intel Xeon 8260 服务器，Ubuntu 20.04，Linux 5.5.0，Mellanox ConnectX-5 RDMA NIC，Intel Optane P4800X SSD（375GB，峰值 2.3 GB/s）。

---

## 五、实验结果

对比系统：Ext4、F2FS、uFS（最新用户态文件系统，扩展支持 disaggregated SSD）。

### 单线程性能

| 指标 | vs Ext4 | vs F2FS | vs uFS |
|------|---------|---------|--------|
| 顺序/随机读吞吐 | +10%~1.12X | +9%~1.23X | 平均 +16% |
| 顺序/随机写吞吐 | 平均 +74% | 平均 +65% | 平均 +24% |
| Append 吞吐 | 平均 +52% | 平均 +50% | 平均 +12% |
| 4KB 随机读延迟 | 19µs vs 42µs（-52%） | — | 19µs vs ~24µs |

### 并发性能（FxMark DWOM，共享文件写）

- CETOFS 是唯一能随线程数扩展的系统，达到 19X 吞吐提升
- 其他系统因 reader-writer lock 串行化，吞吐不增反降

### 宏观基准（Filebench）

| 负载 | vs Ext4 | vs F2FS | vs uFS |
|------|---------|---------|--------|
| Fileserver（写密集） | +75% | +72% | +64% |
| Webserver（读密集） | +25%~33% | — | — |
| Webproxy | +14%~50% | — | — |
| Varmail | 与 F2FS 接近 | — | — |

### 真实应用（LevelDB db_bench）

| 操作 | Ext4 (µs) | F2FS (µs) | uFS (µs) | CETOFS (µs) |
|------|-----------|-----------|----------|-------------|
| Writesync | 196.29 | 120.78 | 92.34 | 84.38 |
| Writeseq | 3.55 | 3.27 | 3.09 | 2.82 |
| Writerand | 35.98 | 31.99 | 29.34 | 26.38 |
| Readrand | 4.03 | 4.03 | 3.89 | 3.62 |

### Atomic Write

- 单线程：CETOFS 平均优于 J-Undo 1.8X，优于 J-Redo 58%
- 多线程：CETOFS 吞吐最高，约 12 线程饱和 SSD 带宽

### 开销分析

- 权限检查全命中时仅增加 0.2µs 延迟
- 最差情况（翻译表 + 权限表均 miss）延迟 36.7µs，仍低于 Ext4 的 42.34µs
- 文件 open 的额外开销约 5µs（约占 open 总时间 31%），为一次性成本

---

## 六、批判性分析

1. **实验硬件较老旧**：使用 Intel Optane P4800X（7µs 延迟）和 ConnectX-5，这些是 2018-2019 年代的硬件。现代 NVMe SSD 延迟更低（<3µs）、IOPS 更高，ConnectX-7 等新网卡也有更低延迟。在更快硬件上，内核栈开销占比会更高，CETOFS 的优势可能更大，但也可能暴露 T-Handler 自身成为瓶颈的问题——论文未讨论这一点。

2. **单 target 单 SSD 限制了评估的说服力**：论文讨论了多 SSD/多 target/多 initiator 的扩展性，但全部标注"留作未来工作"。实际部署中，disaggregated storage 通常涉及多个 target 和多个 initiator 并发访问，缺乏这方面的实验数据是显著的不足。

3. **安全模型假设值得商榷**：论文假设 target 端是"可信实体"（trusted entity），但在多租户数据中心场景下，存储服务器可能被共享使用。T-Handler 作为用户态进程运行在 target 上，其自身的安全隔离和攻击面未被讨论。

4. **Varmail 性能接近暴露了元数据操作的瓶颈**：CETOFS 在元数据密集型负载（Varmail）下优势不明显，因为元数据操作仍走内核 K-FS。这意味着对小文件密集型工作负载（如邮件服务器、容器镜像层），CETOFS 的收益有限。

5. **64K 并发打开文件上限**：虽然论文提到可通过 permission grouping 缓解，但未给出该方案的实际开销和限制。在大规模存储系统中，64K 文件限制可能成为实际部署的障碍。

6. **Crash consistency 语义较弱**：CETOFS 的 append crash consistency 与 Ext4 metadata-journaling/write-back 模式相同，这意味着 crash 后可能丢失最近的 append 数据。论文轻描淡写了这一限制。

---

## 七、AI Infra / MLSys 视角

1. **Checkpoint/模型存储加速**：大模型训练中的 checkpoint 写入是 IO 密集型操作，通常涉及大量并发写入共享存储。CETOFS 的并发控制卸载和 merging group 策略可以显著加速多 GPU/多节点并发 checkpoint 写入的场景，避免序列化等待。

2. **Disaggregated storage for GPU cluster**：AI 集群越来越多采用计算-存储分离架构（如 GPU 节点 + 远程 NVMe 存储池）。CETOFS 的用户态数据路径可以与 GDS（GPU Direct Storage）结合，减少 CPU 参与，进一步降低训练数据加载和 checkpoint 的延迟。

3. **KV cache offloading**：LLM 推理中 KV cache 卸载到 SSD 需要低延迟的远程存储访问。CETOFS 将 4KB 随机读延迟从 42µs 降到 19µs，对于 KV cache swap-in/out 的性能有直接帮助。

4. **可迁移的 insight——target 端计算卸载**：将并发控制和日志管理卸载到存储服务器端的思路，可以推广到 DPU/SmartNIC 上运行的存储服务，与 AI 集群中越来越普遍的 DPU-based 存储架构（如 NVIDIA BlueField）天然契合。

5. **值得跟进的方向**：(a) 将 CETOFS 扩展到多 target 场景，评估在大规模 AI 训练集群中的 checkpoint 和数据加载性能；(b) 结合 CXL 内存扩展，探索 CETOFS 在 CXL-attached 存储上的适用性；(c) 将 T-Handler 移植到 DPU ARM 核心上，评估实际的 CPU 节省效果。

---

## 八、总结

CETOFS 通过 host-target 协作设计，将文件系统数据路径完全放到用户态以消除内核栈开销，并将权限检查、并发控制和 redo logging 三项关键任务卸载到远程存储服务器端，从根本上减少了网络往返次数和串行化等待。在单线程场景下延迟降低最多 52%，在并发共享文件写入场景下吞吐提升最高 19X。其核心贡献在于识别了远程存储访问中网络延迟对并发控制和 failure-atomic IO 的放大效应，并通过 request group 和 target-side logging 两种卸载机制系统性地解决了这些问题。主要局限在于假设可信 target、单 target 评估、元数据操作仍依赖内核路径，以及缺少多节点规模化实验。
