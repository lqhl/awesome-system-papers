# Building an Elastic Block Storage over EBOFs Using Shadow Views

**作者**：Sheng Jiang (Carnegie Mellon University), Ming Liu (University of Wisconsin-Madison)
**会议**：NSDI 2025 (22nd USENIX Symposium on Networked Systems Design and Implementation)
**链接**：https://www.usenix.org/conference/nsdi25/presentation/jiang
**源文件**：[[nsdi2025-jiang.pdf]]

---

## 一、背景

存储解耦（storage disaggregation）因其独立扩展、高利用率和成本效率的优势，近年来受到广泛关注。随着 400+GbE 网络和快速远程存储协议（如 NVMe-oF）的发展，远程存储服务器已能提供百万级 IOPS 和十到百微秒级延迟，接近直连存储的性能水平。

EBOF（Ethernet-Bunch-Of-Flash）是一种新兴的解耦存储平台，它将 Ethernet 交换机与 NVMe 驱动器集成在一个 SoC 中。与传统 server-based JBOF 相比，EBOF 消除了通用 CPU 在 I/O 路径上的开销，避开了 DRAM 和 PCIe 子系统的瓶颈，显著提升了 I/O 可扩展性和能效。以 Fungible FS1600 为例，它封装了 12×100GbE 端口和 24 块 NVMe SSD，可处理 1.2 Tbps 存储流量，读/写能效分别达到 200K 和 5.9K IOPS/Joule，比现有 JBOF 高出近一个数量级。

---

## 二、要解决的问题

尽管 EBOF 具有高性能和高能效优势，其静态、不透明的 I/O 处理流水线存在三个关键缺陷：

1. **位置无关的块放置（Location-oblivious block placement）**：EBOF volume 静态映射到单块 NVMe SSD，无法利用内部海量 I/O 带宽。一个 physical volume 的带宽上限仅为单块 SSD 的极限（读 ~2.1 GB/s，写 ~0.9 GB/s），远低于 EBOF 的总带宽容量。即使通过 logical volume 的 striping 方案，由于 extent layout 的位置无关性，小块随机 I/O 仍无法充分利用并行 I/O 路径。

2. **容量依赖的带宽分配（Size-dependent bandwidth allocation）**：EBOF 以 IOPS/GB 作为 per-volume 带宽预留指标，带宽仅随 volume 容量线性增长，与实际工作负载需求脱节。吞吐密集型小容量工作负载（如元数据服务）不得不申请大容量 volume 来获取足够带宽，造成容量浪费；而大容量低吞吐工作负载（如日志服务）则隐式预留了过多带宽。

3. **租户无感知与设备状态无感知的干扰（Tenant-unconscious interference）**：EBOF 仅在 volume 粒度执行性能隔离（per-volume rate limiter），完全忽略 NVMe 驱动层面的干扰。共置 volume 在同一 SSD 上时，victim volume 的 P999 延迟可从 169us 飙升到数毫秒。此外，EBOF 不感知 SSD 碎片化程度、读写混合比等因素对 I/O 代价的影响。

---

## 三、洞察与设计

**关键洞察**：不断提升的数据中心网络速度使得服务器间通信和数据同步可以在个位数微秒内完成，而单次存储 I/O 延迟通常在数十到数百微秒量级。因此，在 EBOF 和存储客户端之间构建一个软件层面的分布式遥测系统（shadow view），其引入的边际延迟开销对存储应用的影响可以忽略不计。

基于此洞察，论文提出了 **shadow view**——一个分布式遥测系统，持续监控 EBOF 的运行状态。它将 EBOF 建模为一个两层多交换机架构（上层网络交换机连接 Ethernet 端口和 I/O 背板端口，下层存储 I/O 交换机连接 I/O 端口和 NVMe 驱动），并定义三个性能监控域：

- **Port Statistics**：捕获 Ethernet/IO 端口的流量使用情况
- **Pipe Statistics**：报告 NetPipe 和 IOPipe 的处理吞吐和排队延迟
- **SSD Statistics**：估算可用读写带宽、I/O 延迟和 NAND 碎片程度

在 shadow view 之上，论文构建了 **Flint**——一个弹性块存储系统，包含三个核心技术：

1. **Elastic Volume Manager**：跨所有 SSD 按需分配 extent（2MB 固定大小），采用加权评分函数综合考虑分配历史、可用容量、繁忙程度、碎片化程度和用户偏好，实现灵活的数据放置。使用 lazy allocation 延迟实际分配时机。

2. **eIO PIFO Scheduler**：基于排名（rank）概念的优先级 I/O 调度器，根据 I/O 特征（大小、类型）、排队时间和分配带宽动态计算每个 I/O 的优先级，低 rank 的 I/O 优先出队，缓解 head-of-line blocking。

3. **View-enabled Bandwidth Auction**：结合 Deficit Round-Robin (DRR) 和 gang scheduling，为每个 NVMe-oF session 维护三元组 deficit counter（NetPipe、IOPipe、SSD），全局性地在竞争 volume 之间以 max-min fairness 方式分配带宽。

---

## 四、实现细节

- **代码规模**：约 7600 行 C++ 代码，从零构建
- **I/O 引擎**：使用 io_uring 异步 I/O 接口
- **RPC 框架**：基于 eRPC 实现跨节点通信，使用 Protobuf 序列化
- **Extent 映射表**：内存中使用哈希表存储，每条映射 16 字节（SSD index + physical extent number + replication node），1TB eVol 仅需 8MB 内存。持久化存储在 RocksDB 中，底层由 Ceph 等复制文件系统备份
- **View 同步协议**：使用单调递增 counter 标识 view 新鲜度，类似分布式 cache-coherence 协议。支持 PUSH（controller 定期发布）和 PULL（agent 主动拉取过期 partial view）两种模式
- **Bottleneck 分析**：采用反向传播分析算法（Algorithm 1），从 SSD 向上追溯到 IOPipe、NetPipe，识别拥塞区域和受影响的 NVMe-oF sessions
- **Fast/Slow Path**：读 I/O 在带宽 slice 充足时直接发送（fast path），不足时向 arbiter 请求新 slice（slow path 1）；写 I/O 可能额外触发 extent 分配（slow path 2），但由于 extent 大小为 2MB，此额外 RPC 开销可忽略
- **Chain Replication**：可选配置，以 extent 粒度复制数据到三个不同 SSD，通过客户端侧链复制协调器实现（因 FS1600 不暴露 recirculation 接口）

---

## 五、实验结果

**测试平台**：Dell R7525 服务器（AMD 7302 处理器，256GB DDR4，Mellanox 100GbE CX6 NIC）+ Dell Z9264F-ON ToR 交换机 + Fungible FS1600 EBOF

| 实验 | 关键结果 |
|------|---------|
| eVol 基础性能 | 128KB 随机读/4MB 顺序写带宽达 9.3/9.2 GB/s，分别比 1-physical-volume 高 14.5×/13.6× |
| 小 I/O 延迟 | P50 延迟与 physical volume 相当；P99 延迟降低 48.1%（4KB 随机读）和 13.4%（4KB 顺序写） |
| Chain Replication | 4KB/128KB 写延迟分别恶化 2.9×/3.5×（读延迟不受影响） |
| 带宽公平分配 | 在 5 种混合工作负载场景下，Flint 确保相同需求的 I/O 流获得相似带宽，无论 volume 大小 |
| I/O 干扰缓解 | 4KB 随机读与 128KB 随机读共置时，P50/P99/P999 延迟分别降低 4.8×/2.6×/7.5× |
| 拥塞 SSD 感知 | 在读/写拥塞场景下，平均延迟分别降低 40.1%/29.8% |
| 对象存储（YCSB） | YCSB-A/B/C 吞吐提升 2.8×/2.8×/2.9×，读延迟降低 66.4%/63.7%/61.9% |
| Shadow View 开销 | view_query: 24/31us (P50/P99), 21.5 MRPS; view_sync: 38/67us (P50/P99), 5.8 MRPS |
| vs. LVM | 在 SSD 拥塞场景下，eVol 吞吐比 LVM 高 2.3×–3.8× |

---

## 六、批判性分析

1. **实验规模过小**：整个评估仅使用 2 台存储客户端和 1 台 FS1600 EBOF。在真实数据中心部署中，可能有数十到数百个客户端同时访问多台 EBOF，shadow view 的 centralized controller 能否应对大规模场景的同步开销未被验证。论文未讨论 controller 的可扩展性瓶颈。

2. **Centralized arbiter 的单点问题**：论文承认 arbiter 不做复制，仅提到"可以做到可靠"。然而在带宽 auction 机制中，每个 I/O 都可能触发与 arbiter 的 RPC 交互（slow path），arbiter 故障时虽然客户端可继续对已打开 volume 执行 I/O，但无法进行 extent 分配和带宽重分配，这对写密集工作负载影响重大。

3. **Shadow view 精度依赖于 I/O 覆盖率**：view 的构建完全依赖于客户端发出的 I/O 统计向量的反向推断。如果某些 SSD 或 pipeline 路径在当前时间窗口内没有被任何客户端访问，shadow view 将无法获得这些组件的状态信息。论文未讨论这种 cold path 场景下的 view 准确性。

4. **SSD 状态估算的局限性**：论文坦言 SSD 内部状态（碎片化程度、GC 触发、FTL 映射等）高度不透明，采用端到端延迟作为间接指标来推断。这种启发式方法在 GC 等突发事件中可能产生严重的估计滞后。碎片化程度用 dynamic write cost 近似，但其准确性未经系统验证。

5. **与现有 JBOF 方案缺乏直接对比**：论文仅对比了 EBOF 的默认 volume 和 LVM，未与 Gimbal、RackBlox 等已有的 SmartNIC JBOF 多租户方案进行端到端性能对比，难以评估 shadow view 相比直接在 SmartNIC 上实现调度的优劣。

6. **EBOF 平台的通用性存疑**：论文的所有设计和实验都基于 Fungible FS1600 这一特定 EBOF 产品。Fungible 公司已被收购，其产品未来的市场存在不确定性。论文声称硬件模型是"通用的"，但未在其他 EBOF 平台（如 Ingrasys ES2000）上验证。

---

## 七、AI Infra / MLSys 视角

1. **存储解耦对 AI 训练/推理的启发**：大规模 AI 训练中 checkpoint 存储和推理中 model/KV cache 的加载场景都面临类似问题——需要从远程存储高带宽、低延迟地读写大量数据。Shadow view 的遥测思路可迁移到 AI 存储场景，用于监控存储节点负载并智能调度 checkpoint 写入和模型加载请求。

2. **弹性带宽分配的借鉴**：AI Infra 中多租户 GPU 集群共享存储后端时，不同训练/推理任务对存储带宽的需求差异巨大（如 embedding lookup vs. dense checkpoint）。Flint 的 bandwidth auction + DRR 机制可作为 AI 存储调度器的参考设计，实现训练任务间的公平带宽分配。

3. **EBOF 作为 AI 推理的存储后端**：EBOF 的高能效特性（200K IOPS/Joule）与 AI 推理场景对 TCO 的敏感性天然契合。如果能将 Flint 的弹性 volume 管理与 vLLM 等推理系统的 PagedAttention KV cache 管理相结合，有望实现 KV cache 到远程存储的高效 offload。

4. **可操作的研究方向**：
   - 在 EBOF 上构建专为 AI checkpoint 优化的存储系统，利用 shadow view 感知 SSD 负载来调度并行 checkpoint 写入
   - 将 eIO scheduler 的 rank-based 调度思路应用于 GPU 集群的存储 I/O 调度，区分 checkpoint（吞吐优先）和参数加载（延迟敏感）

---

## 八、总结

本文针对 EBOF 这一新兴解耦存储平台的三个固有缺陷（静态块放置、容量耦合带宽、租户无感知干扰），提出了 shadow view 分布式遥测系统和 Flint 弹性块存储。核心思路是利用数据中心网络的低延迟特性，在不修改 EBOF 硬件的前提下，通过客户端侧的 I/O 统计追踪和集中式分析，重建 EBOF 内部运行状态，并基于此实现弹性 volume 管理、优先级 I/O 调度和公平带宽分配。在 Fungible FS1600 上的实验表明，Flint eVol 可达 9.3/9.2 GB/s 读写带宽，对象存储场景下吞吐提升最高 2.9×。主要局限在于评估规模有限（单台 EBOF）、centralized arbiter 的可扩展性未经验证、以及对特定 EBOF 平台的依赖。
