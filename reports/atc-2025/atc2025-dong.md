# Understanding and Detecting Fail-Slow Hardware Failure Bugs in Cloud Systems

**作者**：Gen Dong, Yu Hua (华中科技大学), Yongle Zhang (Purdue University), Zhangyu Chen, Menglei Chen (华中科技大学)
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/dong
**源文件**：[[atc2025-dong.pdf]]

---

## 一、背景

云系统是现代应用的基础设施，但硬件故障导致的系统失效会带来严重损失。传统故障注入测试主要针对**粗粒度故障**（如节点崩溃、网络分区），这些故障影响所有关联 I/O 操作，已有成熟的容错机制。然而，近年来 **fail-slow 硬件**（如性能退化的 NIC、NVMe SSD）成为日益严重的问题：硬件仍在运行但性能大幅下降，且只影响**部分** I/O 操作。研究表明，平均 1.41% 的 NVMe SSD 在四个月内会受到 fail-slow 影响，而 99% 的 fail-slow 事件需要数小时甚至数月才能被检测到。

---

## 二、要解决的问题

1. **现有故障注入工具无法有效检测 FSH（Fail-Slow Hardware）bug**：现有工具（如 FATE、Jepsen）主要针对粗粒度故障（节点崩溃、网络分区），忽略了 fail-slow 硬件的细粒度特性。
2. **FSH 故障空间巨大**：云系统包含大量 I/O 操作，穷举所有故障注入点不现实。
3. **缺乏对 FSH 故障特征的系统性理解**：已有 bug study 要么关注 fail-slow 软件，要么关注 fail-slow 硬件本身，缺少对"fail-slow 硬件如何影响软件"的综合分析。
4. **细粒度故障能逃避内部检测机制**：例如 fail-slow NIC 只减慢部分网络操作，heartbeat 线程仍正常工作，导致集群无法感知异常。

---

## 三、洞察与设计

**关键洞察**：(1) 所有被研究的 FSH 故障都是由**同步机制（synchronized）和超时机制（timeout）保护的 I/O 操作**触发的——被 fail-slow 硬件减慢的同步任务会阻塞其他任务，超时任务与超时处理器之间会产生 data race；(2) FSH 故障的**细粒度特性**是触发这些 bug 的必要条件——粗粒度故障会被已有容错机制正确处理，只有细粒度故障才能逃逸检测。

基于这两个观察，作者提出 **Sieve**，一个专门针对 FSH bug 的故障注入测试框架：

- **故障点分析（静态阶段）**：通过轻量级静态分析，在字节码层面识别同步和超时保护的 I/O 操作作为候选故障点。具体包括：
  - **同步 I/O**：识别 critical region（通过 entry/exit point 匹配算法）和 barrier 模式（notify/wait）中的 I/O 操作
  - **超时保护 I/O**：通过匹配 `startTime`/`endTime` 的 get-time 函数对和差值公式，确定 timeout scope 中的 I/O 操作
- **故障注入（运行时阶段）**：在候选故障点前插桩 fail-slow agent，运行时向 Injection Controller 发送 RPC 查询，由 Controller 决定是否注入延迟
- **分组策略（Grouping）**：同一 basic block 内的故障点具有相同的高层系统状态和容错处理器，合并为一组只测试最后一个
- **上下文敏感注入（Context-sensitive）**：记录每次注入的 call stack，避免在相同上下文重复注入，同时发现同一故障点的不同 buggy context

---

## 四、实现细节

- 使用 **Java** 实现，核心组件约 **8,100 SLOC**
- 故障点分析基于 **Soot**（Java 程序分析框架），插桩使用 **Javassist**（字节码操作工具）
- Injection Controller 采用 **client-server 架构**，通过 Java RMI 进行 RPC 通信
- I/O 操作识别：分析 `java.io`、`java.nio`、`java.net`、`javax.net`、`io.netty` 五个通用包，加上系统特定的 I/O 操作（如 ZooKeeper 的 serialize/deserialize）
- 延迟注入策略：
  - 同步 I/O：注入 5 分钟延迟（足以造成 indefinite blocking）
  - 超时保护 I/O：注入 timeout value 的 2/3（触发超时机制并重排超时任务与处理器的执行顺序）
- 故障模型：每次 test run 只注入**一个**延迟（基于 Finding 6：89.6% 的 FSH 故障由单个 fail-slow 硬件引起）
- 失败检查器：Log error checker（扫描 FATAL/ERROR/WARN 日志）+ Gray failure checker（简化版 Panorama，检测差异可观测性）

---

## 五、实验结果

**评估系统**：ZooKeeper 3.9.0、Kafka 3.6.0、HDFS 3.3.6，部署在单台物理机（52 核 Intel Xeon Gold 6230R，192GB DRAM）的 Docker 集群上。每个系统执行 2000 次 test run。

### 未知 Bug 检测

| Bug ID | 系统 | 故障现象 | 状态 |
|--------|------|---------|------|
| ZK-4816 | ZooKeeper | Follower 长时间无法跟随 leader（>30s） | 新发现 |
| ZK-4817 | ZooKeeper | CancelledKeyException 无法捕获断连异常 | 新发现 |
| ZK-4844 | ZooKeeper | Fail-slow disk 导致 follower hang | 新发现 |
| ZK-4836 | ZooKeeper | ACL index 不一致导致 MarshallingError | 已确认 |
| KAFKA-16401 | Kafka | 一个请求耗尽所有 request handler 线程 | 新发现 |
| KAFKA-16412 | Kafka | 未创建的 topic 被误认为已创建 | 已确认 |
| HDFS-15869 | HDFS | Namenode 因 slow sendResponse hang | 已知未修复 |

### 与替代方案对比（2000 test runs）

| 方案 | 检测 Bug 数 | 故障点选择 | 注入策略 |
|------|------------|-----------|---------|
| Random | 0 | 所有 I/O | 随机 |
| FATE | 2 | 所有 I/O | 上下文敏感 |
| Legolas | 3 | 所有 I/O | 抽象状态+bsrr |
| Chronos | 2 | 超时 I/O | Deep-priority |
| **Sieve** | **7** | **同步/超时 I/O** | **分组+上下文敏感** |

### 故障点剪枝效果（静态故障点数）

| 系统 | 所有 I/O | 同步/超时 I/O | +分组 |
|------|---------|-------------|------|
| ZooKeeper | 1905 | 1266 | 856 |
| Kafka | 1953 | 1090 | 780 |
| HDFS | 4216 | 1974 | 1568 |

### 已知 Bug 复现

Sieve 成功复现 48 个已知 FSH bug 中的 **34 个**（70.8%）。未复现的 14 个 bug 主要因为：需要多次故障注入（5 个）、缺乏准确检查器（6 个）、需要复杂线程交织（1 个）、静态分析无法处理同步数据结构（2 个）。

### 运行时开销

| 系统 | Baseline (s) | 信息收集 (s) | 平均 Test Run (s) |
|------|-------------|-------------|------------------|
| ZooKeeper | 9.41 | 13.17 | 37.64 |
| Kafka | 7.12 | 34.89 | 44.86 |
| HDFS | 24.87 | 27.36 | 52.23 |

静态分析在 3 分钟内完成，内存消耗不超过 8GB。

---

## 六、批判性分析

1. **单故障注入的局限性被低估**：论文承认 5 个 bug 需要多次故障注入无法复现，但将此仅作为"future work"轻描淡写。实际上，真实的 fail-slow 场景中多个硬件同时退化并不罕见（论文自己的数据也显示 10.4% 的 FSH 故障涉及多个 fail-slow 硬件），这意味着 Sieve 在设计上排除了一类重要场景。

2. **Bug study 的代表性存在显著偏差**：48 个 bug 全部来自 Java 生态的 Hadoop/ZooKeeper/Cassandra 系统，Sieve 的静态分析也基于 Java bytecode。论文声称"Sieve is designed for most cloud systems"，但实际上对 C/C++/Go/Rust 编写的云系统完全不适用。

3. **实验评估在同一台物理机上用 Docker 模拟集群**，与真实的分布式环境存在差距——真实的 fail-slow 硬件行为（如 NIC 性能波动、磁盘 latency spike）比固定延迟注入要复杂得多。Sieve 用 `Thread.sleep` 注入固定延迟，这是对 fail-slow 行为的过度简化。

4. **False positive 分析不够严谨**：论文承认 gray failure checker 和 log error checker 都会产生误报，但依赖人工确认来消除误报（"we manually check whether their symptoms and system logs are consistent"）。在 2000 次 test run 中，论文没有报告 suspicious test runs 的总数和手动确认的工作量。

5. **与 Chronos 的比较不完全公平**：Chronos 的核心组件不可用，作者自行重新实现了其策略。重新实现的效果可能与原始工具有差距，且 Chronos 使用原始 failure checker 只检测 crash 和 hang，而 Sieve 用了更广泛的 checker——论文也承认 Chronos 本不应检测到 ZK-4817 和 KAFKA-16412。

6. **Kafka 作为"out-of-study"系统的验证价值有限**：论文强调 Kafka 不在 bug study 的 5 个系统中，以此证明 Sieve 的泛化性。但 Kafka 同属 Java 生态、使用相同的并发原语（synchronized、java.util.concurrent），与 study 系统高度同质。

---

## 七、AI Infra / MLSys 视角

本文的核心关注是分布式云系统的可靠性测试，与 AI Infra 的直接关联有限，但有以下借鉴价值：

1. **GPU/加速器的 fail-slow 问题更为严峻**：AI 训练集群中，GPU 性能退化（如显存错误导致降频、PCIe 链路降速、NVLink 带宽下降）是常见问题，且会导致整个 data-parallel 或 pipeline-parallel 训练被 straggler 拖慢。Sieve 的"识别同步+超时保护的 I/O 操作"思路可以迁移到分析分布式训练框架中的 collective communication（AllReduce、AllGather）和 pipeline bubble 相关代码。

2. **可操作的研究方向**：为 PyTorch Distributed / DeepSpeed / Megatron-LM 等框架构建类似 Sieve 的 fail-slow fault injection 工具——注入单个 GPU 的 NCCL 通信延迟或计算延迟，测试框架的超时重试、straggler mitigation、故障检测机制是否能正确处理。

3. **AI 推理服务（如 vLLM、TensorRT-LLM）中的 fail-slow 问题**：单个推理实例的 GPU 性能退化会导致请求 latency spike，但 load balancer 可能无法及时感知。这与论文中 heartbeat 正常但实际服务已降级的 gray failure 模式高度相似。

---

## 八、总结

本文对 48 个真实 FSH 故障进行了系统性研究，发现同步和超时机制是 FSH bug 的主要触发点，并据此提出 Sieve——通过静态分析识别候选故障点、结合分组和上下文敏感策略进行高效故障注入的测试框架。Sieve 在 ZooKeeper、Kafka、HDFS 上检测到 6 个未知 bug（2 个已确认），显著优于现有工具。主要局限在于仅支持 Java 系统、单故障注入模型、以及 failure checker 的精度不足。
