# FiDe: Reliable and Fast Crash Failure Detection to Boost Datacenter Coordination

**作者**：Davide Rovelli (Università della Svizzera Italiana & SAP SE), Pavel Chuprikov (Télécom Paris & Institut Polytechnique de Paris), Philipp Berdesinski (turba), Ali Pahlevan (SAP SE), Patrick Jahnke (turba), Patrick Eugster (Università della Svizzera Italiana)
**会议**：USENIX ATC 2025
**链接**：[USENIX](https://www.usenix.org/conference/atc25/presentation/rovelli)
**源文件**：[[atc2025-rovelli.pdf]]

---

## 一、背景

故障检测（Failure Detection, FD）是分布式容错系统中最基础的原语之一。高可用的核心服务（如复制存储、数据库、同步服务）依赖 FD 来保证 liveness。传统的 crash FD 基于心跳 + 超时机制：进程周期性发送"I am alive"消息，超时未收到则判定对方故障。

然而，数据中心中的网络拥塞和端侧处理器资源竞争导致交互延迟不可预测，timeout 不得不设得很大以避免误判（false positive）。这使得故障检测延迟高达毫秒甚至秒级，严重制约了日益增长的 µs 级服务（如 µs-scale KV store、状态机复制等）的性能。现有的 gray failure detector（如 Falcon、Panorama）虽然能检测更多类型的故障，但增加了软件复杂性和侵入性，且在 crash failure 检测上仍受限于不稳定的超时。

---

## 二、要解决的问题

1. **超时不可靠且过大**：现有 crash FD 建立在尽力而为的通信和 OS 抽象之上，网络和 CPU 抖动导致必须使用保守的超时值（数百 µs 到数百 ms），延缓了对真实故障的响应。
2. **侵入性强**：Falcon 等 system-tailored FD 需要在应用内部插入大量 probe/spy 代码（数百行应用特定代码），增加复杂性，且 probe 自身也可能失败，形成"monitor the monitor"的困境。
3. **quorum-based 算法效率低下**：由于 FD 不可靠，分布式协调协议只能采用异步 quorum-based 设计（如 Raft/Zab），只能容忍不到一半的进程故障，且需要多轮消息交换，性能受限。
4. **网络故障的脆弱性**：单一心跳路径上的网络故障会导致 false positive，现有系统缺乏系统性的网络冗余和恢复机制。

---

## 三、洞察与设计

**关键洞察**：现有 crash FD 之所以不可靠、不及时，根本原因在于它们是作为"模块"（module）而非"组件"（component）实现的——它们运行在与应用共享的尽力而为环境中，没有充分利用现代 OS 和网络硬件的精确性和可编程性。如果从底层构建一个专用的、隔离的系统基底（system substrate），使 FD 进程的端到端交互延迟稳定且有界，就可以在实践中近似实现理论上不可能的"完美故障检测器"（Chandra & Toueg 的 P 类）。

基于此洞察，FiDe 采用**系统驱动**（system-driven）和**外部观察**（externally observed）的设计：

### 架构
- **双域隔离**：系统分为"尽力而为域"（应用运行环境）和"FiDe 域"（特权系统基底）。FiDe 进程运行在隔离的 CPU 核上，屏蔽 OS 中断，使用 XDP 绑定专用 NIC 队列，实现不间断的心跳发送和接收。
- **SDN 辅助的 traffic engineering**：FiDe 控制器通过 SDN 为心跳流量分配最高优先级队列、构建冗余 multicast tree，并通过速率限制保证带宽预留，使网络延迟有界。
- **冗余 multicast tree + 恢复机制**：每个集群部署一对 vertex-disjoint 的 multicast tree。单个网络故障可通过另一棵树检测并触发恢复，只有极罕见的 critical compound failure（两棵树在恢复时间窗内同时失效）才会影响可靠性。
- **外部观察的故障检测**：通过 Linux Kernel Module (LKM) 中的 kprobe 注册在 `do_exit` 上，在进程退出前即检测到故障（技术上是"负延迟"）。无需应用修改。

### FiDe-based 新算法
利用 FiDe 近似 P 类检测器，设计了三个新原语：
- **OSRB**（Optimistic Stabilizing Reliable Broadcast）：带 STABILIZE 机制的可靠广播，限制缓冲区增长。
- **HSUC**（Hierarchical Stabilizing Uniform Consensus）：3 轮消息、O(N) 复杂度、容忍 N-1 个 crash failure。
- **HUC**（Heartbeat Uniform Consensus）：2 轮消息、O(N) 复杂度、容忍 N-1 个 crash failure，利用 FiDe piggyback 直接在心跳中搭载决策消息。

对比 Raft/Zab 只能容忍 ⌊(N-1)/2⌋ 个故障，FiDe-based 算法在 failure-free 路径上更高效且容错能力更强。

---

## 四、实现细节

- **FiDe 核心**：4032 行 C 代码，分为 LKM、XDP (eBPF) hooks 和 userspace API。使用 libbpf v0.5.0 和 Linux kernel eBPF (v5.9.8)。
- **CPU 隔离**：使用 `isolcpus` 内核启动参数、设置 `smp_affinity` 屏蔽标准 IRQ、`local_irq_save()` 屏蔽处理器间中断、最大 C-state (C0) 避免休眠、hugepages 避免分页抖动、禁用 RCU stall detector。
- **网络处理**：LKM 管理自己的 socket kernel buffers (SKBs)，使用 active pacemaker loop 精确发送心跳。接收侧使用 XDP hooks 绕过网络栈，通过 `BPF_MAP_TYPE_ARRAY` eBPF maps 实现内核/用户空间高效通信。
- **应用集成**：HSUC 和 HUC 实现为 Redis 模块（分别 910 和 810 行代码），使用 batch 优化。Zookeeper 变体通过修改配置参数实现，无需修改内部代码。
- **API**：简洁的 C API（downcalls: `monitor`, `unmonitor`, `join`, `quit`, `piggyback`; upcalls: `on_failure`, `on_piggyback_recv`, `on_timeout_changed`），集成仅需约 6 行代码。

---

## 五、实验结果

实验在 SAP 生产数据中心进行，6 台服务器（Intel Xeon E5-2680 v4, 28 核, 1TB RAM, Mellanox ConnectX-4 / Intel XL710 10GbE NIC, Arista 7280CR-48 交换机）。

### 交互稳定性（RQ1）

| 方法 | 最大 P2P 延迟 | 稳定性 |
|------|-------------|--------|
| FiDe | < 45 µs（2.3 万亿包后稳定） | 有界、无跳变 |
| RDMA | 243 µs（周期性跳变） | 不稳定 |
| X-Lane | 100-550 µs | 较稳定 |
| Falcon | 最差（CPU 负载相关跳变） | 不稳定 |

### 故障检测性能（RQ2）

| 方法 | 平均检测延迟 | 最大检测延迟 | 最小可靠超时 | 最坏情况超时 |
|------|------------|------------|------------|------------|
| FiDe | 4.58 µs | 26.54 µs | 48 µs | 45 µs |
| uKharon-FD | 17.39 µs | 193.56 µs | ~800 µs | 1000 µs |
| X-Lane | 354.75 µs | 718.54 µs | ~800 µs | 600 µs |
| Falcon | 496.29 µs | 169 ms | ~204 ms | 300 s |

FiDe 比 SOTA（uKharon-FD）快 3.8×（平均）和 7.2×（最大）。

### 应用集成性能（RQ3 & RQ4，Redis/Zookeeper SET 请求）

| 方法 | 吞吐量提升 | 延迟降低 |
|------|----------|---------|
| Redis-FiDe HUC vs Redis Raft | 平均 1.22×, 最大 1.7× | 平均 0.79×, 最大 0.46× |
| Zookeeper-HUC vs Zookeeper | 平均 1.71×, 最大 2.23× | 平均 0.64×, 最大 0.57× |

### 网络故障与部署规模（RQ5）

| Tree Height | 平均应用故障检测 | OS 故障超时 | Critical Compound Failure 频率 |
|-------------|---------------|-----------|------------------------------|
| 1（理想） | 6.34 µs | 45 µs | 1/22.7 年 |
| 2 | 13.62 µs | 65 µs | 1/11.3 年 |
| 3 | 20.89 µs | 80 µs | 1/6 年 |

FiDe 比 TCP 的 packet corruption 概率还可靠 3 个数量级以上。

---

## 六、批判性分析

1. **同步假设的实质性依赖**：FiDe 的正确性和效率完全依赖于同步假设（有界延迟）。虽然论文声称 critical compound failure 概率极低（22.7 年一次），但这个估算基于 2011 年 Gill et al. 的故障统计数据，距今十多年且来自不同规模的数据中心。现代超大规模数据中心的故障模式可能不同，该概率估算的可信度存疑。

2. **不处理 slow process 是重大局限但被淡化**：论文承认 HSUC/HUC 不容忍进程变慢（只处理 crash），一个慢进程会阻塞整个 consensus。论文建议"结合 gray FD"来处理，但未给出具体实现或评估。在生产环境中，slow process 比 crash 更常见（GC pause、I/O 阻塞等），这严重限制了实用性。

3. **实验规模偏小**：所有评估仅在 6 台服务器上进行，且论文明确将目标限定在 3-9 节点的复制集群。虽然这是合理的目标场景，但论文未评估当数据中心中部署多个独立 FiDe 集群时，共享网络优先级队列带来的干扰效应。

4. **资源开销被低估**：每个 FiDe 进程独占一个 CPU 核（最高功耗状态 C0）、一个 NIC 队列和网络优先级队列。论文称这只占 1/56 核（1.79%），但在真实部署中，每台机器可能运行多个需要 FiDe 监控的服务，核数开销会累积。且 C0 状态意味着持续最大功耗。

5. **TE 算法复杂度较高**：traffic engineering 算法的复杂度为 O(|V|^{2K} · K! · d)，虽然 K=2（冗余度）时可控，但论文未讨论 TE 重配置对运行中系统的影响（如 multicast tree recovery 时的短暂不一致）。

6. **Piggyback 消息大小限制**：HUC 的吞吐量受限于 piggyback payload（最大 1418B）和心跳间隔，论文虽声称"ample in practice"，但对于大 value 的 KV 操作或复杂的 consensus 数据，需要额外的预广播步骤，这会抵消部分性能优势。

---

## 七、AI Infra / MLSys 视角

1. **可靠故障检测对分布式训练的启发**：大规模分布式训练中，节点故障检测和快速恢复是关键问题。FiDe 的 µs 级故障检测和双域隔离思路可以迁移到训练场景，但需要扩展到处理 GPU 故障、NCCL hang 等 AI 特有的故障模式——这些更接近 gray failure 而非 crash failure。

2. **SDN + TE 的思路可用于训练/推理流量调度**：FiDe 通过 SDN 控制器为关键流量预留优先级和构建冗余路径的做法，可以借鉴到 collective communication 的流量工程中，特别是在多租户 GPU 集群中隔离训练流量和管理流量。

3. **外部观察 vs 内部观察的权衡**：FiDe 选择外部观察以保证非侵入性，这对 AI 推理服务特别有价值——推理框架（vLLM、SGLang 等）已经非常复杂，嵌入内部 probe 代价高且不稳定。基于 kprobe 的外部监控值得借鉴。

4. **可能的延伸方向**：
   - 将 FiDe 的可靠通信基底用于 parameter server 或 all-reduce 的 membership management
   - 利用 HUC 的 2 轮共识改进推理集群的 leader election（如 KV cache 的 primary-backup 切换）
   - 探索 eBPF/XDP 在 GPU 集群健康监控中的应用

---

## 八、总结

FiDe 是一个专注于 crash failure 的高可靠、低延迟故障检测器，通过系统驱动的双域隔离设计（CPU 核隔离 + SDN 辅助 TE + XDP 网络处理）实现了 < 30 µs 的故障检测（比 SOTA 快 7.2×），并在此基础上设计了 3 个新的分布式协调原语，将 Redis 吞吐提升 1.7×、Zookeeper 吞吐提升 2.23×。主要局限在于不处理 slow process / gray failure、需要专用硬件资源、目标场景限于小规模复制集群（3-9 节点），以及同步假设的概率论证依赖较老的故障统计数据。
