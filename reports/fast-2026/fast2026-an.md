# Xerxes: Extensive Exploration of Scalable Hardware Systems with CXL-Based Simulation Framework

**作者**：Yuda An, Shushu Yi (Peking University); Bo Mao (Xiamen University); Qiao Li (MBZUAI); Mingzhe Zhang (IIE, CAS); Diyu Zhou (Peking University); Ke Zhou (HUST); Nong Xiao (Sun Yat-sen University); Guangyu Sun, Yingwei Luo, Jie Zhang (Peking University)
**会议**：FAST 2026 (24th USENIX Conference on File and Storage Technologies)
**链接**：https://www.usenix.org/conference/fast26/presentation/an
**源文件**：[[fast2026-an.pdf]]

---

## 一、背景

随着 AI、生命科学、气候模拟等大规模数据密集型应用的兴起，系统需要聚合海量计算和内存资源。PCIe 作为主流互连标准，虽提供高聚合带宽和兼容性，但缺乏 coherence 机制，无法将外部设备内存无缝扩展为主机本地内存，软件维护一致性的开销极高。

Compute Express Link (CXL) 是建立在 PCIe 物理层之上的新兴标准，提供 cache-coherent 互连能力，支持主机 CPU、加速器和内存设备间的高性能通信。CXL 3.0/3.1 引入了两项关键架构特性：**Port-Based Routing (PBR)** 支持任意非树拓扑，**Device-Managed Coherence (DMC)** 将一致性管理卸载到设备端，使系统可扩展至 rack 级别并实现真正的 peer-to-peer 通信。

然而，支持 CXL 3.0+ 完整特性的硬件尚不可用，现有仿真工具也无法准确建模这些新特性，形成了重要的研究瓶颈。

---

## 二、要解决的问题

现有 CXL 系统探索工具存在三类根本性不足：

1. **NUMA 仿真的局限**：利用远程 NUMA 节点模拟 CXL 内存，但 UPI 与 CXL 存在协议级差异，且物理可扩展性极低（仅支持少量 socket），无法模拟多达 4096 端点的 CXL fabric。

2. **传统架构模拟器的局限**：计算中心型模拟器（如 gem5）采用主机中心的严格层次结构，缺乏灵活的互连层建模能力，其集中式 coherence 引擎与 DMC 的 peer-to-peer 模型不兼容；网络中心型模拟器（如 BookSim、Garnet）无法感知内存和 coherence 语义。

3. **行为级 CXL 模拟器的局限**：MESS 和 CXLMemSim 采用 Latency-Bandwidth 曲线注入延迟的"复现式"方法，只能评估已知设备的性能，无法预测新拓扑或假设性设备的性能，不具备架构设计空间探索能力。

---

## 三、洞察与设计

**关键洞察**：CXL 3.0+ 的核心特性（PBR 和 DMC）从根本上改变了系统的拓扑结构和 coherence 管理方式——从层次化、主机中心转变为图结构、peer-to-peer，因此仿真框架必须将互连层与设备层解耦，用图建模拓扑、用 peer 模型建模设备，才能从 first principles 出发准确预测新架构的性能。

基于此洞察，Xerxes 采用两层架构：

- **Interconnect Layer**：以图（而非树）表示系统拓扑，原生支持 PBR 的任意非树互连。提供默认最短路径路由策略，复杂组件（如 switch）可查询拓扑图实现自定义路由。包含 Bus 组件（详细建模 PCIe 6.0 full-duplex 传输，双向独立分配带宽）和 Switch 组件（实现完整 PBR 转发表）。

- **Device Layer**：所有组件（主机、加速器）统一建模为 active peer agent（Requester），各自独立生成流量、管理 coherence 状态。实现了 device-side inclusive snoop filter 作为 DCOH 的具体实现，支持 BISnp/BIRsp 的完整流程。

两层解耦使 Xerxes 可灵活集成现有模拟器：已与 gem5（处理器微架构）、DRAMsim3（DRAM 端点）、SimpleSSD（SSD 端点）集成。

---

## 四、实现细节

**核心组件**：

- **Requester**：包含 request queue（建模 on-the-fly 请求数）、address translation unit（支持多种 interleaving 策略）、cache coherence management unit（维护内部 cache 状态，响应 BISnp）。支持合成流量和 trace 回放。

- **Bus**：建模 PCIe 6.0 full-duplex，双向独立追踪并行传输，参数可配（带宽、延迟、半双工模式及 turnaround overhead）。

- **Switch**：初始化时从 interconnect layer 获取路由信息构建转发表，实现完整 PBR 功能。

- **Snoop Filter**：全关联 buffer，每条 entry 跟踪 cacheline 的 coherence 元数据。支持 entry 分配、元数据更新、冲突处理（发起 BISnp）、victim 选择（可插拔策略）。

**与 gem5 集成**：通过 XerxesWrapper 对象桥接，UpInterface 和 DownInterface 在 gem5 内存包与 Xerxes 请求间转换，复用 gem5 事件队列。通过 SLICC 实现 coherence interface 以支持 DMC 的 back-invalidation。

**与 DRAMsim3/SimpleSSD 集成**：为 cycle-based 模拟器注册周期性 clock event；为 event-driven 模拟器转换事件格式并注册到 Xerxes 事件引擎。

代码以 C++ 编写，开源于 https://github.com/ChaseLab-PKU/Xerxes。

---

## 五、实验结果

### 验证（与真实 CXL 硬件对比）

硬件平台：双路 Intel Xeon Gold 6416H + DDR5-4800，一路连接 Montage MXC CXL 2.0 内存扩展器（PCIe 5.0 ×16，128GB HDM-H）。

| 指标 | Xerxes 误差 | MESS 误差 | CXLMemSim 误差 | NUMA 仿真误差 | gem5-garnet 误差 |
|------|-----------|----------|--------------|-------------|----------------|
| Idle latency | 与硬件高度吻合 | — | — | 偏差大 | — |
| Loaded latency (L-BW curve) | 平均 4.3% | 9.3% | 16.6% | 完全偏离 | — |
| SPEC CPU2017 (gcc) | +0.7% (standalone) | +6.0% | -16.5% | +2.0% | -5.8% |
| SPEC CPU2017 (mcf) | +5.6% (standalone) | -28.3% | +11.2% | -9.2% | -9.0% |

PBR 验证（0-7 hop）：平均延迟预测误差 10.4%。DMC dirty write 验证：误差 1.4%。

Xerxes 集成 gem5 后仅增加 ~2% 仿真时间开销（gem5-garnet 为 22.5%）。

### 设计空间探索

**拓扑影响**（5 种拓扑：chain、tree、ring、spine-leaf、fully-connected）：

| 拓扑 | 带宽可扩展性 | 延迟特征 |
|------|------------|---------|
| Chain / Tree | 受限于 bridge 路由瓶颈，带宽不随规模增长 | 高 hop 数请求延迟为低 hop 数的 2×（chain）或 1×（tree） |
| Ring | 提供额外路由路径，带宽可达 2× port 容量 | 仍有 bridge 瓶颈 |
| Spine-leaf | 高可扩展，带宽达 N/2 × port 容量 | 延迟稳定 |
| Fully-connected | 最优，带宽达 N × port 容量 | 延迟最低且稳定，但内存开销二次增长 |

真实 workload（BTree、liblinear、redis、silo、XSBench）验证：spine-leaf 和 fully-connected 吞吐量比 chain 高达 3.63×。

**DMC Back-Invalidation 分析**：

- Snoop filter victim 选择：LIFO/MRU 优于传统 FIFO/LRU（带宽提升 5%，延迟降低 15%），因为到达 SF 的请求大多为 cache miss（冷数据），"最近插入"的 entry 才是合适的 victim。
- InvBlk 命令：长度 = 2 时性能最优（减少等待时间），长度 > 2 后因 cache 访问开销和带宽竞争收益递减。

**Full-Duplex 分析**：

- 读写混合可将 full-duplex 带宽提升近 2×（零 header 开销时），但 header-to-payload 比增大会显著削弱收益。
- 真实 workload 中 mix degree 每增加 0.1，带宽提升约 9%。

---

## 六、批判性分析

1. **CXL 3.1 特性验证缺乏硬件 ground truth**：PBR 和 DMC 仅与理论模型对比（误差 10.4% 和 1.4%），而非真实硬件。理论模型本身是基于 Xerxes 的延迟参数计算的，这构成了一定程度的循环验证——验证的是内部一致性而非绝对准确性。

2. **端到端验证规模有限**：SPEC CPU2017 仅展示 gcc 和 mcf 两个 workload（表 3 用 "..." 省略了其他结果），难以全面评估 Xerxes 在多样化应用场景下的准确性。

3. **拓扑探索中的理想化假设**：实验假设所有 switch 端口带宽恒定、路由为最短路径，未考虑实际部署中的链路故障、自适应路由、拥塞控制等因素。Fully-connected 拓扑在大规模下的布线成本和物理可行性未讨论。

4. **DMC 实验场景单一**：snoop filter 实验使用 90/10 skewed 访问模式和特定的 cache/SF 大小配比，结论（LIFO 优于 LRU）是否在其他访问模式（如 uniform、zipf 不同参数）下成立未验证。

5. **缺少与更多模拟器的公平对比**：行为级模拟器被赋予了硬件实测的 L-BW 曲线作为输入（"best-case accuracy"），但 Xerxes 在 PBR/DMC 探索中的优势场景下缺乏可对比的 baseline。

6. **仿真速度评估不够充分**：仅报告了与 gem5 集成时的开销比（2%），standalone 模式下 64 节点的绝对仿真时间（<90s）缺少明确的 workload 规模说明。

---

## 七、AI Infra / MLSys 视角

1. **CXL 内存池化对 AI 训练/推理的启示**：论文中 Bert、Pagerank 等 AI workload 在 tree 拓扑下内存扩展至 16 端点时延迟增加约 9×，这对 LLM 推理中通过 CXL 扩展 KV cache 内存池的方案是重要的量化参考——简单的树形扩展会引入严重的性能退化，spine-leaf 或更高级拓扑是必要的。

2. **DMC snoop filter 设计对 GPU 集群互连的借鉴**：LIFO 优于 LRU 的发现源于"到达 SF 的请求多为 cache miss"这一独特模式。在 GPU 集群的 coherent 互连（如 NVLink 未来可能支持的 CXL 语义）中，类似的请求模式分析可指导硬件设计。

3. **Full-duplex 优化对 disaggregated memory 系统的价值**：论文量化了 header overhead 对 full-duplex 增益的影响，这对设计 CXL-based 的分离式内存系统（如 AI 训练中的 parameter server）有直接的工程指导意义——需要在协议层最小化 header 占比。

4. **可跟进的研究方向**：
   - 基于 Xerxes 探索 CXL fabric 上的分布式 KV cache 共享方案，量化不同拓扑下 LLM 推理的 TTFT/TBT 影响
   - 研究 DMC 在多 GPU coherent 内存共享场景下的 snoop filter 扩展性问题
   - 利用 Xerxes 框架评估 CXL-based memory pooling 对 MoE 模型 expert 调度的性能影响

---

## 八、总结

Xerxes 是首个能够全面仿真 CXL 3.1 关键特性（PBR、DMC、PCIe 6.0 full-duplex）的模拟框架，采用互连层与设备层解耦的双层架构，以图建模拓扑、以 peer 模型建模设备。在真实 CXL 硬件上验证误差低至 0.1%-10%，显著优于行为级模拟器。通过三组设计空间探索实验，揭示了树形拓扑的可扩展性瓶颈、snoop filter 需要定制化 victim 策略、以及 full-duplex 增益受协议开销制约等关键发现。局限在于 CXL 3.1 特性的验证缺乏硬件 ground truth，实验场景覆盖面有待扩展。
