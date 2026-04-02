# DShuffle: DPU-Optimized Shuffle Framework for Large-scale Data Processing

**作者**：Chen Ding, Sicen Li, Kai Lu（华中科技大学武汉光电国家研究中心）; Ting Yao, Daohui Wang, Huatao Wu（华为云）; Jiguang Wan, Zhihu Tan, Changsheng Xie（华中科技大学武汉光电国家研究中心）
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/ding
**源文件**：[atc2025-ding.pdf](../../papers/atc-2025/atc2025-ding.pdf)

---

## 一、背景

分布式数据处理框架（如 Spark、Hadoop）在大规模数据分析中广泛使用。Shuffle 是其中的核心操作，负责在节点间重新分配中间数据。然而，Shuffle 是一个 CPU 和 I/O 密集型操作，在排序类负载中可占总执行时间的 70%，其中大部分时间花在序列化（serialization）和垃圾回收（GC）上。随着网络和存储设备性能的提升，I/O 不再是主要瓶颈，CPU 开销反而成为 Shuffle 的关键瓶颈。

与此同时，DPU（Data Processing Unit）作为一种新型基础设施芯片，已被各大云厂商广泛部署。DPU 集成了通用计算核心、高并发内存访问加速器（DPA）、高速网卡和 PCIe 交换等组件，天然适合卸载数据通路上的 I/O 密集型任务。

---

## 二、要解决的问题

1. **Shuffle 的 CPU 开销巨大**：在 HiBench Sort 负载中，序列化和 GC 占总执行时间约 64%–69%。序列化需要遍历 Java 对象树并编码为字节流，消耗大量 CPU；大量临时对象又加剧 JVM GC 压力。
2. **现有优化方案不够彻底**：软件优化（Kryo、Skyway、ZCOT）仍依赖主机 CPU 进行序列化；硬件加速方案（Cereal、SparkRDMA）只解决 Shuffle 的部分阶段，缺乏端到端方案。
3. **朴素的 DPU 卸载反而更慢**：将 Shuffle 简单卸载到 DPU，由于 DPU 通用核心频率低、板载内存有限，任务完成时间反而增加 1.52×–1.68×。

---

## 三、洞察与设计

**关键洞察**：Shuffle 操作可以被分解为序列化、预处理计算、I/O 三个阶段，而 DPU 的硬件特性恰好与这三个阶段分别对应——DPA 的高并发内存访问适合加速序列化，通用 ARM 核心可执行预处理计算，PCIe P2P 和 RDMA 能力可绕过主机直接完成 I/O。只要将这三个阶段按流水线方式精细编排，就能在 DPU 上高效执行完整的 Shuffle 而不拖慢整体任务。

基于此洞察，DShuffle 提出三项核心技术：

1. **DPA 加速序列化（DPA-Accelerated Serialization）**：利用 DPA 的 256 个硬件线程并发遍历主机 JVM 堆内存中的 Java 对象树，完成序列化并通过 DMA 将结果传到 DPU 内存。预注册 JVM 运行时参数（堆基址、压缩指针配置等），使 DPA 能直接通过 load/store 指令访问主机内存中的任意 Java 对象。通过批量 + 多线程并行，2 个 DPA 核心（32 线程）即可超过主机单核的 Java Native/Kryo 序列化速度。

2. **细粒度流水线 Shuffle（Fine-Grained Pipeline Shuffle）**：将 Shuffle 数据切分为细粒度块，在 DPA Serializer、DShuffle Worker（预处理）、DSpill Worker（I/O）之间形成三级流水线。Worker 间通过 SPSC 无锁队列传递任务。同时引入 Intra-Worker 并行：对慢阶段按 key 分段启动多线程处理；使用 Boost.Fibers 协程进一步提升 DPU 核心利用率。

3. **DPU 直接溢写（DPU-Direct Spilling）**：DPU 通过 PCIe P2P 直接将中间数据写入本地磁盘，或通过 RDMA 发送到远端 DPU 再写盘。完全绕过主机 CPU，消除溢写过程中的数据拷贝和 GC 开销。通过预分配磁盘分区 + 固定大小文件块的方式，解决主机 CPU 感知 DPU 写盘数据的问题。

---

## 四、实现细节

- **平台**：NVIDIA BlueField-3 DPU（16 ARM 核心、32GB DDR5、DPA 16 RISC-V 核心 × 256 硬件线程），DOCA 2.9 编程套件
- **代码量**：约 6,700 行
  - Host 端 DShuffle Agent：~500 行 Java（Spark 集成接口）+ ~1,000 行 C++（JNI，与 DPU 交互）
  - DPU 端 Worker：~4,000 行 C++（统一传输层支持 DMA/RDMA/TCP，Boost.Fibers 协程调度，SPSC 无锁队列）
  - DPA Serializer：~1,000 行 JNI + ~1,200 行 DPA 硬件代码
- **集成方式**：实现了 DShuffleWriter 替换原生 Spark Shuffle Writer，对上层应用透明
- 磁盘分区在节点初始化时预分配，DPU 以 read-write 挂载、Host 以 read-only 挂载，使用 Direct I/O 绕过文件系统缓存保证一致性

---

## 五、实验结果

**测试环境**：2 节点集群，每节点 Intel Xeon 6418H（24 核 @ 4.0GHz，HT 禁用）+ 64GB DDR4 + Samsung 980 Pro 2TB SSD + BlueField-3 DPU

**主要结果**：

| 指标 | Native Spark | Naive Offload | DShuffle |
|------|-------------|---------------|----------|
| Sort 285GB 总执行时间 | 513s | 797s (+55%) | 431s (-16%) |
| Shuffle 阶段执行时间 | — | — | 减少 62.7%（vs Spark）/ 70.7%（vs Naive） |
| Reduce 阶段执行时间 | — | — | 减少 45.6%（vs Spark）/ 50.2%（vs Naive） |

**优化技术逐步开启的效果**：
| 配置 | 相对 Naive Offload 的加速 |
|------|--------------------------|
| + DPA 序列化 | -13.2%（序列化时间从 15% 降至 3%） |
| + 流水线并行 | 再 -17.4% |
| + DPU 直接溢写 | 再 -15.1% |

**不同数据规模下**（Sort 负载）：

| 数据量 | Spark | DShuffle | 加速比 |
|--------|-------|----------|--------|
| 30GB | 89s | 57s | 1.56× |
| 60GB | 125s | 56s | 2.23× |
| 120GB | 216s | 100s | 2.16× |
| 285GB | 513s | 431s | 1.19× |

**HiBench 多种负载**：Shuffle 密集型负载（Sort、TeraSort、Repartition）收益显著；计算密集型负载（WordCount）无显著差异。

**可扩展性**：支持最多 6 个并发 Sort 任务（等效 48 CPU 核心 + 128GB 内存的主机容量），超过后 DPU 资源饱和。

**DPA Serializer 微基准**：单 DPA 核心序列化延迟高于主机（时钟频率低），但 2+ DPA 核心即可超过 Java Native 和 Kryo。DPU Worker 最大吞吐约 10.53 GB/s（15 workers），接近 100Gbps 网络极限。

---

## 六、批判性分析

1. **实验规模过小**：仅 2 节点集群，远不能代表实际生产环境（数百到数千节点）。在大规模集群中，Shuffle 的网络拓扑、数据倾斜、多租户资源竞争等问题会显著改变性能特征，2 节点的结论外推性存疑。

2. **数据规模结果自相矛盾**：在 30GB 和 60GB 时 DShuffle 加速比为 1.56×–2.23×，但在最大数据量 285GB 时反而仅有 1.19×。论文声称"数据量越大优势越明显"，但实验数据并不支持这一结论——285GB 时加速比反而是最差的。作者对此没有给出解释。

3. **缺少与 SmartShuffle 的直接对比**：SmartShuffle 是最相关的工作，但因未开源而仅提供定性分析。Naive Offload 作为替代基线，刻意省略了 SmartShuffle 的动态卸载策略，这使得 DShuffle 相比 Naive Offload 的优势被放大了。

4. **DPU 资源开销被低估**：论文强调"完全消除主机 CPU/内存开销"，但 DPU 本身的 16 核 ARM + 32GB 内存是有成本的。6 个并发任务即饱和，意味着每个 DPU 只能服务有限的工作负载。论文未分析 DPU 的成本效益比——购买更多主机 CPU 核心是否更经济？

5. **仅支持 Spark 2.4.3**：这是 2019 年的版本，当前 Spark 已到 3.5.x。新版本的 Shuffle 机制（如 Spark 3.x 的 push-based shuffle）可能已经解决了部分问题，与旧版本的对比参考价值有限。

6. **压缩被禁用**：所有实验禁用了 Shuffle 压缩以"避免额外 CPU 开销"，但生产环境中压缩是常开的。开启压缩后数据量减小，序列化和 I/O 的相对开销会发生变化，DShuffle 的优势可能缩小。

7. **可移植性存疑**：虽然声称可移植到其他 SoC DPU，但 DPA 加速序列化是核心创新之一，其他 DPU 没有类似的高并发内存访问加速器，移植后需回退到 CPU 序列化，性能增益将大打折扣。

---

## 七、AI Infra / MLSys 视角

1. **DPU 卸载思路对分布式训练通信有借鉴**：分布式训练中的 AllReduce / All-to-All 通信同样涉及大量序列化、内存拷贝和网络 I/O。DShuffle 的"将数据通路分解为三阶段并在 DPU 上流水线化"的思路，可以尝试迁移到梯度通信或 KV cache 传输场景。

2. **DPA 加速序列化的启发**：在 LLM 推理系统（如 vLLM、TensorRT-LLM）中，KV cache 的跨节点迁移涉及大量内存拷贝操作。利用 DPA 的高并发内存访问能力加速 KV cache 的打包/解包，可能是一个有价值的优化方向。

3. **DPU 直接溢写对 Checkpoint 的启发**：大模型训练的 checkpoint 保存是一个经典瓶颈。DShuffle 的 DPU-Direct Spilling（通过 PCIe P2P 直接写盘，绕过主机 CPU）可以迁移到 checkpoint 场景，减少 checkpoint 对训练吞吐的影响。

4. **可跟进的研究方向**：
   - 在 Mixture-of-Experts (MoE) 模型的 All-to-All 通信中引入 DPU 卸载，减少 Expert 间数据交换对 GPU 计算的干扰
   - 利用 DPU 加速 Parameter Server 架构中的梯度聚合和分发
   - 将 DPU-Direct Spilling 应用于 disaggregated memory 场景下的 GPU 显存溢出管理

---

## 八、总结

DShuffle 提出了一个利用 DPU 端到端卸载 Spark Shuffle 的框架，通过 DPA 加速序列化、细粒度流水线并行、DPU 直接溢写三项技术，在 DPU 上高效执行完整的 Shuffle 操作，完全消除了主机端的 Shuffle CPU 和内存开销。在 2 节点 Spark 集群 + BlueField-3 DPU 平台上，Sort 负载的 Shuffle 阶段执行时间减少 62.7%，总任务完成时间减少约 16%。其主要局限在于实验规模过小（仅 2 节点）、仅在老版本 Spark 上验证、且 DPU 资源饱和后扩展性受限。该工作为 DPU 在数据密集型系统中的应用提供了有价值的工程参考。
