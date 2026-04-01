# FineMem: Breaking the Allocation Overhead vs. Memory Waste Dilemma in Fine-Grained Disaggregated Memory Management

**作者**：Xiaoyang Wang, Yongkun Li (University of Science and Technology of China); Kan Wu (Google); Wenzhe Zhu, Yuqi Li (USTC); Yinlong Xu (USTC & Anhui Provincial Key Laboratory of High Performance Computing)
**会议**：OSDI 2025
**链接**：https://www.usenix.org/conference/osdi25/presentation/wang-xiaoyang
**源文件**：[osdi25-wang-xiaoyang.pdf](../../papers/osdi-2025/osdi25-wang-xiaoyang.pdf)

---

## 一、背景

随着数据中心对内存成本优化的需求日益增长，memory disaggregation（内存解耦）已成为重要的系统架构方向。该架构将内存节点（memory nodes）与计算节点（compute nodes）解耦，允许多个计算节点动态共享远程内存池。RDMA（Remote Direct Memory Access）是实现 disaggregated memory 的主流互连技术，其 one-sided 操作可以绕过内存节点 CPU 直接读写远程内存，实现低延迟高吞吐的数据访问。

当前 DM 系统涵盖 DM-transparent（基于 swap 机制，应用无需修改）和 DM-native（通过显式 API 操作远程内存）两类，且多个异构系统可能共享同一内存池。

---

## 二、要解决的问题

RDMA 在远程内存**分配/释放**环节存在严重瓶颈，导致现有系统面临 "分配开销 vs. 内存浪费" 的两难困境：

1. **MR 注册代价高昂**：RDMA 的 Memory Region (MR) 注册涉及物理页 pinning 和 RNIC 页表更新，注册 4MB 需约 480µs。运行时按需注册会使吞吐降至预注册方案的 26.7%。

2. **粗粒度分配导致内存浪费**：为规避 MR 注册开销，现有系统采用 1GB 级粗粒度预分配。这导致大量内存碎片——未使用的部分无法被其他系统回收。实验显示 1GB 粒度比 2MB 粒度内存浪费显著增加。

3. **细粒度分配的网络开销**：即使预注册避免了 MR 开销，基于 one-sided RDMA 的细粒度分配仍面临元数据搜索的网络放大问题（如遍历 free-chunk array）和高并发下 CAS 重试风暴。

4. **隔离性缺失**：简单的全局 MR 共享方案无法在多系统间提供内存访问隔离，存在安全风险。

---

## 三、洞察与设计

**关键洞察**：RDMA Memory Window (MW) 机制可以在预注册的 MR 之上以极低开销（~1µs/4MB，相比 MR 注册的 ~480µs）生成和撤销细粒度的 rkey，从而将 MR 注册开销从分配路径中完全移除，同时通过 per-chunk rkey 实现多系统间的内存访问隔离。

基于此洞察，FineMem 的整体设计包含三个核心组件：

### 1. 基于 MW 的隔离机制
- 内存节点启动时预注册整个内存空间为单个 MR，并为每个 chunk 预绑定 MW 和 rkey
- 分配时通过 one-sided RDMA 获取/撤销 rkey，无需 RPC
- 引入主备 rkey 对（8 bytes/chunk），释放时用 CAS 原子替换主 rkey 为备用 rkey，异步后台再生新的备用 rkey
- ConnectX-6 单 NIC 支持 16M 个 MW，通过多 VF 可扩展至 128×16M

### 2. 两层 Bitmap Tree 加速并发分配
- **Section 层**：16 个连续 span，32-bit bitmap 追踪各 span 的状态（空/使用中/满/竞争）
- **Span 层**：32 个连续 chunk（每 chunk 4KB），32-bit free map
- 大分配（≥128KB）在 section 层一次 CAS 完成；小分配（4KB-64KB）先定位 section 再在 span 层 CAS
- **竞争控制**：bitmap 中嵌入 2-bit 竞争状态，CAS 失败超过阈值（如 10 次）标记为 contended，引导后续分配去低竞争区域

### 3. 计算节点分配服务与崩溃一致性
- 每个计算节点运行可信分配服务进程，DM 系统通过 IPC 请求分配（开销 2-10µs），保护元数据不被直接访问
- 崩溃一致性：以 span bitmap 的 CAS 成功作为 commit point，结合内嵌的临时 redo-log（7-bit timestamp + 14-bit userID + 5-bit offset + 3-bit size），通过 timestamp 检测过期日志，防止 crash 和 fail-slow 场景下的元数据不一致

---

## 四、实现细节

- **实现语言与规模**：C++ 实现，FineMem 核心 8.5k LOC，FineMem-User（基于 mimalloc 的用户态 DM 对象分配器）1.5k LOC，FineMem-Swap（基于 FastSwap 的内核交换模块）0.7k LOC，FineMem-KV（FUSEE 慢路径替换）300 LOC
- **平台**：Linux (Ubuntu 22.04, kernel 5.15)，Mellanox OFED 5.8 RDMA 驱动，ConnectX-6 100Gb NIC
- **元数据开销**：每 4KB chunk 需 8B rkey + 8B redo-log，约占内存空间的 0.4%（100GB 内存约 400MB 元数据）
- **MW 预生成优化**：单线程 166µs/MW，8 线程并行降至 32µs/MW
- **rkey 再生**：后台线程每 100ms 扫描一次，100GB 空间（25M 个 4KB chunk）耗时 15ms，约占单核 15% CPU
- **FineMem-User**：基于 mimalloc 的 slab 分配器思路，慢路径调用 FineMem 获取/释放 chunk，快路径在本地 slab 完成
- **FineMem-Swap**：包含 page manager（基于 FineMem chunk 的分配器）、remapper（swap offset 到 DM 地址映射）和 swap-out/invalidation 路径的 FineMem 集成

---

## 五、实验结果

**实验环境**：CloudLab 集群，16 compute nodes + 1 memory node，Intel Xeon 8360Y CPU，ConnectX-6 100Gb NIC，256GB 内存/节点

### 分配性能（微基准测试）

| 指标 | FineMem | Premmap-One-sided |
|------|---------|------------------|
| 平均延迟 (4KB, 512 threads) | 43.2µs | 763.0µs |
| P99 延迟 | 79.3µs | 16143.5µs |
| 平均 CAS 重试次数 | 1.33 | 45.1 |
| 最大 CAS 重试次数 | 142 | 20637 |

- 两层 bitmap 贡献约 52.5% 延迟降低，竞争控制再贡献 44%，合计降低约 95%
- 隔离（rkey 读取 ~5µs）和 redo-log（~5µs）开销仅占 MR 注册成本的 2.5%
- 服务层 IPC 开销 2-10µs

### FineMem-User（内存分配系统）

- 内存利用率比 Premmap 方案提升 2.25×-2.8×
- 在 ThreadTest、Shbench、Larson 等基准测试中性能最优
- 混合大小分配场景下延迟稳定在 100µs 以下

### FineMem-KV（键值存储）

- YCSB-A 工作负载（50% update）：比 Premmap-RPC 吞吐提升 27%-110%
- 4KB 粒度比 2MB 粒度减少 45% 内存开销

### FineMem-Swap（交换系统）

- 远程内存利用率：74.06% vs FastSwap 的 41.39%
- 作业吞吐提升 8.38%-17.71%

### 多系统共享内存池

- KV + Malloc 系统共享运行时，FineMem 吞吐和延迟保持稳定
- Premmap-RPC 带宽下降 46.8%，Premmap-One-sided 带宽下降 75.5%

---

## 六、批判性分析

1. **实验规模有限**：仅使用 1 个内存节点、最多 16 个计算节点的配置。虽然右图展示了多内存节点的微基准测试，但端到端实验均为单内存节点。真实数据中心的内存池可能有数十到数百个内存节点，跨节点的分配协调、故障恢复等问题在当前评估中未充分体现。

2. **MW 机制的硬件依赖性**：论文的核心隔离机制完全依赖 RDMA Memory Window，这是一个 ConnectX 系列特有的特性，且论文承认 CXL 场景需要额外设计。在 CXL 逐渐取代 RDMA 成为 DM 互连主流的趋势下，FineMem 的适用性存疑。

3. **KV-Store 评估偏向 update-intensive 场景**：论文仅展示了 YCSB-A（50:50 read:update）的结果，对 YCSB-B/C/D 等读密集型负载"因增益不明显而未展示"。这意味着 FineMem 对 KV-Store 的优化主要来自 FUSEE out-of-place update 的特殊模式，而非通用的 KV 场景。

4. **竞争控制的阈值调优**：竞争检测依赖于硬编码的高低阈值（如 3 和 10），论文未讨论这些参数对不同负载模式的敏感度，也未提供自适应调优机制。

5. **崩溃一致性的 7-bit timestamp 局限**：timestamp 仅 7 位，溢出周期约 50K 次分配请求（~1s），论文称"足以配合 RDMA 超时设置"，但在高频分配的极端场景下（如 swap storm），这个窗口可能不够充裕。

6. **安全模型的假设**：分配服务依赖每个计算节点上的可信进程和外部私钥授权，在多租户公有云场景下，论文将安全保障推给了云提供商（如 hypervisor 层部署），并未真正解决这一问题。

---

## 七、AI Infra / MLSys 视角

1. **LLM 推理的 KV Cache 管理**：FineMem 的细粒度远程内存分配与 vLLM 的 PagedAttention 思路天然契合。LLM 推理中 KV cache 的动态增长/收缩需要细粒度的内存管理，FineMem 可以将这一能力扩展到 disaggregated memory，实现跨节点的 KV cache 池化——这正是 Mooncake（论文中也提到）等系统的方向。

2. **分布式训练的梯度/参数交换**：大规模训练中的 ZeRO-style 优化器需要频繁在节点间交换参数分片。FineMem 的 one-sided 分配机制可以为 offloading 到远程内存的优化器状态提供更高效的内存管理。

3. **Checkpoint 和弹性训练**：训练 checkpoint 的快照写入是 AI Infra 中的关键路径。FineMem 的细粒度分配可以减少 checkpoint 写入的内存碎片，配合 RDMA one-sided write 实现更高效的异步 checkpoint。

4. **可跟进方向**：
   - 将 FineMem 的两层 bitmap + 竞争控制思路迁移到 CXL-based DM 场景，结合 MPK 实现隔离
   - 探索 FineMem 与 GPU 远程内存（如 NVIDIA GPUDirect RDMA）的集成，用于 GPU 内存池化
   - 基于 FineMem 的 MW 隔离机制构建多租户 AI 推理服务的 KV cache 共享池

---

## 八、总结

FineMem 通过三项核心设计——基于 RDMA Memory Window 的预注册隔离机制、两层 bitmap tree 的高效并发分配结构、以及嵌入式临时日志的崩溃一致性方案——成功打破了 disaggregated memory 中"分配开销 vs. 内存浪费"的两难困境。系统在 4KB 粒度下实现了比现有方案低 95% 的分配延迟，内存利用率提升 2.25×-2.8×，并在 KV-Store、Swap 和通用 Malloc 三类 DM 系统上验证了其通用性和可移植性。主要局限在于对 RDMA MW 硬件特性的强依赖，以及在 CXL 新兴互连技术下的适配尚需进一步探索。
