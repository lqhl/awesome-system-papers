# ScaleSwap: A Scalable OS Swap System for All-Flash Swap Arrays

**作者**：Taehwan Ahn, Chanhyeong Yu, Sangjin Lee, Yongseok Son（Chung-Ang University, Systems and Storage Laboratory）
**会议**：FAST 2026（24th USENIX Conference on File and Storage Technologies）
**链接**：https://www.usenix.org/conference/fast26/presentation/ahn
**源文件**：[[fast2026-ahn.pdf]]

---

## 一、背景

随着机器学习、大数据处理、图计算、科学计算、虚拟机和容器等内存密集型应用的兴起，应用的内存需求常常远超物理内存容量。OS swap 系统作为防止 OOM（Out-of-Memory）的关键组件，正重新受到学术界、工业界和内核社区的重视。Alibaba Cloud、Meta 等公司已在生产环境中引入了异步回收和内存敏感度监测等 swap 优化机制。

与此同时，NVMe SSD 的价格远低于 DRAM（DDR4 约 $4.22/GB vs PCIe 4.0 NVMe SSD 约 $0.16/GB，相差约 26 倍），使用多块 SSD 组成 all-flash swap array 成为扩展内存容量、降低 TCO 的可行方案。Google Cloud 已支持每 VM 最多 8 块本地 SSD（共 3TB）作为 swap 空间；存储实验室使用 30 块 Solidigm SSD（共 921.6TB）作为 swap 空间加速计算。

---

## 二、要解决的问题

现有 Linux swap 系统在 all-flash swap array 上存在严重的扩展性瓶颈：

1. **SSD 扩展性差**：使用 128 核、128 swap 文件配置，随 SSD 从 1 增加到 8，Linux swap 吞吐量几乎不变（约 4 GB/s），而 raw 设备性能从 3.4 线性增长到 11.2 GB/s。
2. **核心扩展性差**：超过 32 核后，Linux swap 性能不再提升，128 核时吞吐量仅为 raw 设备的 38%。
3. **根本原因——all-to-all 模型**：
   - **Per-node LRU 锁争用**（lru_lock）：所有核共享同一 node 的 LRU 列表，swap in/out 时争抢 lru_lock，占总执行时间 53.27%。
   - **Swap 元数据锁争用**（si_lock）：所有核以 round-robin 方式访问全局共享的 swap 空间，频繁争抢 si_lock。
4. **Direct reclaim 加剧争用**：当空闲页低于最低水位线时，应用线程直接参与页面回收，虽然提供了并行性，但大量线程同时争抢 LRU 锁导致延迟飙升。

---

## 三、洞察与设计

**关键洞察**：Linux swap 系统的扩展性瓶颈根源在于其 all-to-all 的资源管理模型——每个核都可以访问任意 swap 资源。如果将 swap 资源（元数据、缓存、空间）按核独占分配，采用 one-to-one 模型，就能从根本上消除锁争用，释放 all-flash swap array 的全部带宽。

基于这一洞察，ScaleSwap 采用去中心化的 core-centric 设计，包含三大策略：

### 策略 1：Core-centric swap 资源管理

每个核独占管理自己的 swap 元数据、swap cache 和 swap 空间（一个独立的 swap 文件）。空间分配时，每个核直接从自己的 swap info 中获取 cluster，无需竞争全局 available swap space list 或 si_lock。

为支持超过 23 个 swap 文件（Linux 默认限制），ScaleSwap 将 swap entry 的 type 字段从 5 bit 扩展到 8 bit，支持最多 247 个专用 swap 空间，同时将 offset 从 50 bit 缩减到 47 bit（仍可表示 128TB）。

### 策略 2：Opportunistic inter-core swap assistance

当核的专用 swap 空间满或需要访问其他核的 swap 空间（如共享页面、进程迁移）时，通过 per-core delegator 机制委托操作：
- 请求线程将 swap task（96 字节）插入目标核的 task queue
- 目标核的 delegator（单消费者）按 FIFO 顺序处理
- 委托仅涉及内存操作（平均 29.99 ns），实际 I/O 由请求线程直接执行
- 等待期间，请求线程协作处理自己核的 task queue（cooperative swapping）

### 策略 3：Core-affinity page 和 LRU 管理

- 将 per-node LRU 列表改为 per-core LRU 列表，每个列表由独立 spinlock 保护
- 修改 page flag，利用 4 个未使用位 + 3 个扩展位记录页面的核编号（支持 128 核）
- 页面分配时插入对应核的 LRU 列表；swap in 时根据 page flag 恢复到原核的 LRU 列表
- 实现了 9.15% 的 page fault 减少

---

## 四、实现细节

- **内核版本**：基于 Linux kernel 6.6.8 实现
- **Swap entry 布局**：8 bit type + 47 bit offset + 9 bit flags（原为 5+50+9）
- **Page flag 布局**：26 bit flags + 7 bit cpuid + 21 bit Last_CPUPID + 3 bit zone + 7 bit node（原 node 为 10 bit）
- **Swap task 结构**：96 字节，包含请求类型、swap 位置信息等，使用 per-core 预分配内存池（默认每核 1500 个 task，128 核共 17.57MB）
- **Task queue**：基于 concurrent list 实现，支持多生产者单消费者模式
- **Delegator 线程**：每核一个 delegator 线程，作为该核 swap 元数据的唯一访问者
- **NUMA 感知**：swap out 委托时优先在同 node 内查找可用空间，再跨 node
- **开源**：https://github.com/syslab-CAU/ScaleSwap

---

## 五、实验结果

**实验平台**：128 核（2× AMD EPYC 7713 64-core）、96GB DRAM、8× Seagate FireCuda 530 NVMe SSD（每块 2TB，混合读写 3.5 GB/s，8 块 RAID-0 聚合 11.4 GB/s）、Ubuntu 22.04 LTS。

### Microbenchmark（stress tool，128 线程，288GB 总内存）

| 指标 | Linux swap | ScaleSwap | 提升 |
|------|-----------|-----------|------|
| 吞吐量（8 SSD） | 4.34 GB/s | 14.81 GB/s | 3.41× |
| 平均延迟（8 SSD） | 768.67 µs | 66.34 µs | 11.5× |
| 尾延迟 P99.9（8 SSD） | 2395.20 µs | 87.94 µs | 27.2× |
| 内核 CPU 占用（8 SSD） | 92.41% | 83.06% | 降低 ~25% |

### 端到端应用（8 SSD，128 核）

| 应用 | 总内存需求 | ScaleSwap 吞吐提升 |
|------|-----------|-------------------|
| BFS | 184 GB | 2.40× |
| DNA Visualization | 640 GB | 2.57× |
| Python List | 256 GB | 1.70× |
| Image Gray-Scale | 384 GB | 1.72× |
| Image Flip | 384 GB | 1.91× |

### Apache Spark（CommonCrawl 数据集）

100,000 records/core 时，ScaleSwap 达到 6.3 GB/s，比 Linux swap 高 1.75×。

### 与先前系统对比

| 对比系统 | ScaleSwap 优势 |
|---------|---------------|
| TMO（Meta） | 最高 64% 性能提升 |
| ExtMEM | 最高 5.02× 操作吞吐 |

### 委托开销

即使 96/128 个 swap 文件满（极端场景），ScaleSwap 仍维持峰值 84% 的吞吐量，平均委托时间仅 81.76 ns。

---

## 六、批判性分析

1. **Microbenchmark 与端到端收益差距显著**：microbenchmark 达到 3.41× 吞吐提升，但端到端应用仅 1.70×–2.57×。论文解释为应用有更多计算操作（user CPU 占比 2.91%–45.21%），但这恰恰说明 swap 不是所有场景的瓶颈——在计算密集部分，ScaleSwap 的优势被稀释。
2. **单 SSD 场景无优势**：从 Figure 13 可见，1 块 SSD 时 ScaleSwap 与 Linux swap 性能几乎相同。这意味着 ScaleSwap 的价值完全依赖于多 SSD 配置，而许多实际部署可能只有 1-2 块 SSD。
3. **128 核上限硬编码**：page flag 中仅分配 7 bit 给 cpuid（支持 128 核），node 从 10 bit 缩减到 7 bit（64 nodes）。随着核数持续增长（AMD 已有 192 核 CPU），这个设计将需要重新调整 bit 分配，可能引入更复杂的权衡。
4. **内存开销虽小但固定**：per-core 预分配 1500 个 swap task × 96 字节，128 核共 17.57MB。论文称可配置，但未讨论 task pool 耗尽时的性能退化模式（仅提到"等待"）。
5. **评估缺少真实数据中心工作负载**：所有应用都是批处理型（stress、BFS、图像处理、Spark）。论文在 motivation 中提到 Web 服务器突发请求、延迟敏感的数据中心应用，但评估中完全没有这类工作负载。对于延迟敏感的在线服务，cooperative swapping 中的 busy waiting 和 delegator 唤醒延迟可能是问题。
6. **与 TMO 的对比不够公平**：TMO 的核心目标是通过 PSI 监控减少对应用性能的影响（同时节省 DRAM 成本），而非最大化 swap 吞吐量。两个系统的设计目标不同，直接用 swap 吞吐量比较有利于 ScaleSwap。
7. **缺少对 folio/large folio 的讨论**：Linux 内核正在积极推进 large folio 支持（论文引用了 LWN 文章 [27]），这可能显著改变 swap 路径的性能特征，但论文未讨论 ScaleSwap 如何与之交互。

---

## 七、AI Infra / MLSys 视角

1. **LLM 推理内存扩展**：LLM 推理的 KV cache 管理面临类似的内存容量挑战。ScaleSwap 的 core-centric 资源管理思路可借鉴到 KV cache offloading——将 KV cache 的 SSD 卸载按 GPU/CPU 核分区管理，减少共享元数据争用。
2. **训练 checkpoint 写出**：大模型训练的 checkpoint 写出涉及大量并发写操作，ScaleSwap 的 per-core delegator 模式可用于协调多 GPU 到 NVMe 的并发写入。
3. **GPU 内存 oversubscription**：vLLM 等推理系统使用 swap 机制在 GPU 和 CPU 内存间迁移 KV cache。ScaleSwap 的 one-to-one 模型可启发 GPU 端的内存管理——为每个 CUDA stream 或 SM 分配独立的 swap 元数据，减少 host 端锁争用。
4. **值得跟进的方向**：
   - 将 ScaleSwap 的 core-centric swap 与 CXL 内存扩展结合，为 AI 工作负载提供多层内存（DRAM → CXL → NVMe）的高效页面迁移
   - 探索 swap 感知的 ML 训练调度：根据各核 swap 压力动态调整数据并行的 micro-batch 分配

---

## 八、总结

ScaleSwap 通过将 Linux swap 系统从 all-to-all 模型重构为 core-centric 的 one-to-one 模型，从根本上消除了 LRU 锁和 swap 元数据锁争用，在 128 核 + 8 NVMe SSD 的 all-flash swap array 上实现了最高 3.4× 吞吐提升和 11.5× 延迟降低。其设计包含三个互补策略：per-core swap 资源独占管理、opportunistic inter-core 委托、以及 core-affinity 页面和 LRU 管理。该系统适用于多 SSD、多核环境下的内存密集型批处理工作负载，但其优势在单 SSD 或计算密集型场景下会大幅缩减，且 128 核的硬编码上限和缺少在线服务评估是主要局限。
