# FineMem: Breaking the Allocation Overhead vs. Memory Waste Dilemma in Fine-Grained Disaggregated Memory Management

**作者**：Xiaoyang Wang, Yongkun Li（中国科学技术大学）；Kan Wu（Google）；Wenzhe Zhu, Yuqi Li（中国科学技术大学）；Yinlong Xu（中国科学技术大学 & 安徽省高性能计算重点实验室）
**会议**：OSDI 2025（第 19 届 USENIX 操作系统设计与实现研讨会），2025 年 7 月 7–9 日，波士顿，MA
**DOI**：https://www.usenix.org/conference/osdi25/presentation/wang-xiaoyang
**源文件**：[osdi25-wang-xiaoyang.pdf](../../papers/osdi-2025/osdi25-wang-xiaoyang.pdf)

---

## 一、背景

内存分解（Memory Disaggregation，DM）将计算节点与内存节点解耦，通过 RDMA 互联，允许计算节点以 one-sided 操作直接读写远端内存，绕过内存节点 CPU。这一架构已成为超大规模数据中心降低内存成本的关键技术路径，催生了 DM-透明系统（利用内核 swap 机制）和 DM-原生系统（如 KV 存储、内存 malloc 系统）两大类应用。

RDMA 内存管理的核心原语是 Memory Region（MR）：客户端在访问远端内存前，需先在 RNIC 上注册 MR，pinning 物理页、更新片上页表，并生成 rkey。这一注册过程耗时极长（4MB 区域需 ~480µs），且必须在内存节点 CPU 上执行。

---

## 二、要解决的问题

现有 RDMA-based DM 系统面临一个根本性两难困境：

1. **MR 注册开销过大**：运行时按需为每个细粒度 chunk 注册 MR 严重拖累性能（如 FUSEE 采用 on-demand 注册时，吞吐仅为 pre-registered 方案的 26.7%）。

2. **粗粒度分配导致内存浪费**：为摊销注册开销，现有系统（如 FUSEE、FastSwap、AIFM）以 GB 为粒度预分配内存，导致大量内存无法被其他 DM 系统共享或回收。使用 2MB 粒度相比 1GB 已有改善，但仍有 ~17% 的吞吐下降。

3. **one-sided 分配的可扩展性瓶颈**：RPC-based 方案受内存节点 CPU 算力限制，并发超过 16–32 客户端即饱和；而现有 one-sided 方案（如 CXL-SHM）使用简单 chunk 数组，在高并发下 CAS 重试次数爆炸（平均 45 次/分配），延迟不可预测。

4. **缺乏隔离性**：若共享单一 MR（pre-register 整块内存），任何持有 rkey 的系统均可访问他人的内存和元数据，无法支持多租户安全共享。

5. **计算节点崩溃时的元数据一致性**：分配操作跨越多个 RDMA 原语，节点崩溃可能导致元数据不一致，redo log 在 fail-slow 故障中可能出现过时更新。

---

## 三、核心设计

FineMem 围绕三个设计要素构建：

### 3.1 基于 Memory Window 的隔离（移除注册开销）

FineMem 将整块远端内存以单一 MR 预注册（系统启动时一次完成）。针对每个 chunk，预先绑定 RDMA Memory Window（MW），生成独立 rkey。MW rkey 生成仅需 1µs（对比 MR 注册的 480µs），且 MW 操作只在已注册 MR 上控制访问权限，不消耗额外片上资源。

- 每个 chunk/span/section 预生成一对 main rkey + backup rkey（共 8 字节），存入 capability table
- 释放时，计算节点通过 one-sided CAS 将 main rkey 替换为 backup rkey（关键路径）；内存节点后台线程异步扫描并重新生成新 rkey，彻底移除关键路径对内存节点 CPU 的依赖
- 单 NIC（ConnectX-6）支持 16M 个 MW entry（覆盖 64GB 4KB chunk），通过 128 个 VF 突破限制

### 3.2 两层 bitmap 树（高并发、低延迟分配）

FineMem 采用两层 bitmap 层级结构：

- **Section 层**（第一层）：每个 entry 代表一组 chunk（128KB 对齐），以紧凑 bitmap 形式标记该组是否全满/全空/有竞争。单次 CAS 可完成 128KB 以上大块分配
- **Span 层**（第二层）：细粒度 bitmap（64 chunks/8B entry），用于定位具体空闲 chunk
- **竞争控制**：在 bitmap entry 中嵌入竞争信息，当某组 chunk 竞争激烈时，分配器可快速跳过该组，减少无效 CAS；实测可将高并发下的平均 CAS 次数从 45 次降至 1.3 次

### 3.3 计算节点分配服务（元数据保护）

每个计算节点运行一个受信任的分配服务进程：
- DM 系统通过 IPC（共享内存 + 信号量）提交分配请求（IPC 开销 2–10µs）
- 只有该服务进程持有操作元数据所需的 rkey，防止恶意或故障系统直接篡改元数据
- 支持外部私钥授权防止服务伪造；在多租户环境中可部署于 hypervisor 层（如 FreeFlow）

### 3.4 崩溃一致性（两阶段提交 + redo log）

分配操作分两步：
1. **commit point**：写入临时 redo log，记录本次分配的 section/span 层信息
2. **flush**：将临时 redo log 持久化到 chunk 全量 redo log，并更新 bitmap

使用 7-bit 时间戳检测过时的 redo log 条目（覆盖约 1ms 窗口，足以与正常 RDMA 超时配合）。恢复时扫描元数据重建分配状态，速度约 1M 分配条目/秒，对正在运行的分配操作影响极小。

---

## 四、实现细节

- C++ 实现，约 8.5k LOC
- **FineMem-User**：基于 mimalloc 构建的用户态 DM 对象 malloc 系统，约 1.5k LOC，处理 object-size 分配完全在计算节点完成，仅 slow-path 向 FineMem 请求 chunk
- **FineMem-KV**：重写 FUSEE 的块分配 slow path，约 300 LOC 改动，实现完全 one-sided KV store（无需内存节点 block server）
- **FineMem-Swap**：将 FastSwap 移植至 FineMem，内核模块新增 remapper 和 chunk manager，约 0.7k LOC
- MW 预生成：初始化时 8 线程并行，每 MW 约 32µs；ConnectX-6 单 NIC 支持 16M MW，通过 128 VF 扩展
- 内存节点仅用 1 个核心，运行 rkey 再生线程（每 100ms 扫描，15ms 处理 100GB，约 15% CPU 占用）+ 故障检测线程（每秒心跳）
- 元数据开销：每个 4KB chunk 消耗 8B rkey + 8B redo log = 16B，100GB 约 400MB（0.4%）

---

## 五、实验结果

**测试平台**：CloudLab，16 计算节点 + 1 内存节点，Intel Xeon 8360Y CPU，Mellanox ConnectX-6 100Gb NIC，各节点 256GB 内存，Ubuntu 22.04 + Linux 5.15

**基线**：Premmap-One-sided（CXL-SHM 方案）、Premmap-RPC（FUSEE/Patronus 方案）、OnDemand-RPC（细粒度注册方案）

### 分配性能

| 指标 | FineMem | Premmap-One-sided |
|------|---------|-------------------|
| 平均延迟（4KB，512 线程）| 43.2µs | 763µs |
| P99 延迟 | 79.3µs | 16143µs |
| 平均 CAS 重试次数 | 1.33 | 45.1 |
| 最大 CAS 重试 | 142 | 20637 |

- 相比 OnDemand-RPC（on-demand 注册），FineMem 降低分配延迟 **95%**
- 两层 bitmap 设计贡献 52.5% 延迟降低，竞争控制机制贡献额外 44% 降低
- 隔离机制（rkey + redo log）引入的开销仅为注册成本的 **2.5%**

### 应用层性能（FineMem-User）

- ThreadTest、Shbench、Larson benchmark 上，内存利用率提升 **2.25×–2.8×**（相比静态 pre-mmap）
- 混合大小分配（jemalloc/ptmalloc/tcmalloc/mimalloc 各种 workload）下，延迟稳定在 100µs 以内

### KV 存储（FineMem-KV，YCSB-A）

- 相比 Premmap-RPC 最优情况，带宽提升 **27%–110%**；4KB 块大小相比 2MB 可节省 **45%** 内存成本

### Swap 系统（FineMem-Swap）

- 内存利用率从 FastSwap 的 **41.39%** 提升至 **74.06%**
- 作业吞吐提升 **17.71%**（500 个随机 workload 平均 8.38%–10.69%）

### 内存池共享

- Co-run 场景下，FineMem 保持 KV 吞吐和分配延迟稳定；Premmap-RPC 因 RPC core 竞争降低带宽 46.8%；Premmap-One-sided 带宽降低 75.5%，延迟增加 2.1×

---

## 六、批判性分析

**测试规模较保守**：主要实验使用 16 计算节点 + 1 内存节点，内存节点仅限 1 核心，刻意凸显 RPC 瓶颈。现实数据中心通常有多个内存节点且计算资源更充裕，RPC 方案的实际劣势可能被夸大。

**KV 存储结果选择性报告**：论文仅报告 YCSB-A（50% 更新），声称 read-heavy workload（YCSB-B/C/D）优势不明显而未展示。这恰恰暗示 FineMem 的优势高度依赖 out-of-place 更新场景，普适性存疑。

**IPC 开销被轻描淡写**：2–10µs 的 IPC 开销在整体 43µs 分配延迟中占比约 5–23%，论文称之为"合理的 trade-off"，但未深入评估高频 small allocation 场景下 IPC 是否会成为新瓶颈。

**MW 预生成开销被回避**：论文提到初始化 1M MW 需要一定时间，但仅给出单个 NIC 的测量数据（166µs/个串行，32µs/个并行），未报告总初始化时间对系统启动的影响，实际部署中可能成为问题。

**崩溃一致性评估不足**：仅展示了正常路径下的恢复速度（1M 条目/秒），未进行实际崩溃注入实验，无法验证 redo log 机制在各种并发崩溃场景下的正确性。

**与 CXL 的兼容性存在较大障碍**：论文声称 FineMem 可"无缝"映射到 CXL，但随即承认 CXL 的 MPK binding 和 memory cache 机制存在本质差异，需要额外设计工作。这一声明过于乐观。

---

## 七、AI Infra / MLSys 视角

FineMem 与 AI 基础设施有直接关联，尤其体现在以下方面：

**KV Cache 分离与细粒度管理**：LLM 推理系统（如 Mooncake、vLLM）正在探索将 KV cache 卸载到远端内存池。FineMem 解决的恰好是 RDMA-based 内存池上细粒度分配的核心问题——当 token-level KV cache 大小分布极不规律时，GB 级粗粒度分配导致的内存碎片会严重拖累 cache 命中率。论文已将 Mooncake 列为 DM 系统的典型案例。

**分布式推理的内存解耦**：随着模型规模增大，prefill/decode 分离部署需要在多节点间动态迁移 KV cache。FineMem 的细粒度分配 + 内存池共享机制，为异构推理节点按需借用内存提供了基础设施支撑。

**值得跟进的研究方向**：
1. **KV cache 感知的分配策略**：FineMem 目前以 power-of-2 对齐管理 chunk，但 KV cache 的大小取决于 sequence length 和 layer 数，存在特定分布规律。定制化的 slab 分配器可能进一步降低碎片。
2. **与 CXL 内存池的集成**：随着 CXL 2.0/3.0 的普及，将 FineMem 的 MW 机制映射到 CXL MPK 是自然延伸，但需要解决缓存一致性和 MPK 绑定的设计差异。
3. **多内存节点故障容错**：论文未处理内存节点崩溃，而推理场景对服务可用性要求高，结合 Hydra 等复制机制的 FineMem 扩展值得探索。
4. **与 disaggregated prefill/decode 架构的联合优化**：在 prefill 密集期快速申请大量 KV cache 内存，decode 期缓慢释放，FineMem 的竞争控制机制能否适应这种脉冲式分配模式值得验证。

---

## 八、总结

FineMem 提出了一套基于 one-sided RDMA 的细粒度远端内存管理系统，通过 RDMA Memory Window 消除运行时 MR 注册开销、两层 bitmap 树降低并发 CAS 竞争、计算节点分配服务保护元数据隔离，将远端内存分配延迟降低高达 95%，内存利用率提升 2.25×–2.8×。其设计在 DM malloc、KV 存储和 swap 系统上均得到验证，尤以更新密集型 workload 收益最为显著。主要局限在于测试规模偏小、部分实验结果选择性呈现、CXL 适配尚需大量工作，以及 IPC 分配服务在极高并发下的瓶颈尚未充分评估。
