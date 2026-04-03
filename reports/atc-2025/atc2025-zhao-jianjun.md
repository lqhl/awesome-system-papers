# Towards High-Performance Transactional Stateful Serverless Workflows with Affinity-Aware Leasing

**作者**：Jianjun Zhao, Haikun Liu, Shuhao Zhang, Haodi Lu (Huazhong University of Science and Technology); Yancan Mao (National University of Singapore); Zhuohui Duan, Xiaofei Liao, Hai Jin (Huazhong University of Science and Technology)
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/zhao-jianjun
**源文件**：[[atc2025-zhao-jianjun.pdf]]

---

## 一、背景

Function-as-a-Service (FaaS) 是当前最主流的 Serverless 计算范式，被 AWS Lambda、Azure Durable Functions、阿里云函数计算等广泛采用。为了支持复杂应用，FaaS 平台允许开发者将函数组合成 workflow（通常抽象为 DAG）。

然而，许多实际应用（如银行转账、旅行预订、库存管理）需要多个函数共享状态并保证事务一致性。当前的 stateful FaaS 平台依赖外部数据存储（如 DynamoDB、S3）管理共享状态，存储与计算的解耦导致频繁的远程状态访问开销。同时，RDMA 技术已在 HPC 和云计算中广泛应用，但尚未有工作将 RDMA 应用于事务性有状态 Serverless workflow 的场景。

---

## 二、要解决的问题

1. **并发控制的高通信开销**：现有 stateful FaaS 平台（Boki、Beldi、T-Statefun）使用 2PL 或 OCC 协议，需要频繁与远程数据存储交互来获取/释放锁或验证冲突。即使使用 RDMA 网络，锁管理、RMA、冲突验证仍占函数执行时间的主要部分（Figure 1）。

2. **并发控制协议削弱了缓存效益**：在 2PL 中，即使本地缓存有效，函数仍需获取远程锁，降低了缓存命中的价值；频繁的状态更新还会导致缓存失效。在 OCC 中，乐观读写本地缓存后需要在提交前验证冲突，冲突时需要中止和重试，抵消了缓存带来的收益。

---

## 三、洞察与设计

**关键洞察**：如果将一组相互关联的数据对象通过排他性租约（exclusive lease）分配给单个 worker 缓存，大多数事务就可以在本地缓存上执行，避免频繁的远程锁获取和冲突验证；而跨 worker 的数据访问可以通过预先构建的任务优先图（TPG）序列化，用 RDMA 单边原语高效完成租约转移，从而将一致性保障与函数执行解耦。

基于此洞察，RTSFaaS 设计了两个核心机制：

### 1. Affinity-aware Lease Assignment

RTSFaaS driver 维护一个统计表，记录每个 worker 处理的请求总数和对每个 KV 对象的访问频率。当请求到达时：
- 计算每个 worker 的 **affinity score**（该 worker 对请求涉及所有 key 的访问计数之和）
- 计算 **load balancing score**（函数分配越少得分越高）
- 两者归一化后加权求和，选择得分最高的 worker
- 每批请求分发后，根据统计表指定每个对象的 lease holder（访问频率最高的 worker）

### 2. RDMA-capable Dynamic Lease Transfer

每批请求的处理分为两个不重叠阶段：

**Planning 阶段**：
- 每个 worker 在本地构建 local TPG：将函数按访问的 KV 对象分组，按时间戳排序，识别 temporal dependency（不同 workflow 访问同一对象）和 parametric dependency（同一 workflow 内函数间的数据依赖）
- 各 worker 交换远程函数的元数据（virtual vertex），协作构建 global TPG

**Execution 阶段**：
- Lease holder 预取对象到本地缓存，每个 KV 对象全局只有一个缓存副本
- 按 global TPG 的 BFS 顺序执行函数
- 本地函数直接访问本地缓存；远程函数通过 one-sided RDMA verbs 访问远程 worker 的缓存
- 通过更新 lease flag 动态转移租约，确保顺序数据访问

### 事务中止处理

在每个事务 workflow 开头插入 condition-variable check，失败时传播 disabled signal 给后续函数，避免级联中止。

---

## 四、实现细节

- **RDMA Channel**：采用 push-based 模型（RDMA write 而非 read），减少往返延迟和 CPU 开销。消息布局包含 start flag、total length、每个 message block 的长度（block 数 = executor 数，支持并行处理）、finish flag
- **Circular Buffer**：每对 sender/receiver 维护一个环形缓冲区。接收方在 head 轮询新消息，发送方在 tail 写入。接收方处理过半缓冲区后才更新发送方的 head 副本，保证未处理消息不被覆盖
- **Phase Transition**：类似 Chandy-Lamport 算法，driver 广播 transition flag + 全局 lease table 确保 planning → execution 阶段的一致转换
- **Fault Tolerance**：每批请求完成后创建本地缓存 snapshot，写回 TiKV 前记录轻量级 log（操作进度）。故障恢复策略：写回完成前故障 → 从 snapshot 恢复重试（233ms）；完全数据丢失 → 重载数据 + 重执行（729ms）
- **存储层**：使用 TiKV 作为 KV 存储，支持地理分布式副本实现高可用
- **部署**：driver + workers 各运行在独立 Docker 容器中
- 源代码开源：https://github.com/CGCL-codes/RTSFaaS

---

## 五、实验结果

### 实验环境

| 配置项 | 规格 |
|--------|------|
| 集群规模 | 5 台物理机（1 driver + 4 workers） |
| CPU | Intel Xeon Gold 6230 |
| 内存 | 128 GB DDR-4 / 每 worker |
| 网络 | Mellanox ConnectX-3 40/56 GbE，RDMA RTT 7 µs |
| 容器配置 | 8 CPU + 32 GB 内存 / 容器，2 GB 本地数据缓存 |
| 存储 | TiKV（3 PD + 3 TiKV nodes） |

### 基线对比

| 系统 | 并发控制 | 存储 | 部署 |
|------|---------|------|------|
| Beldi | 2PL (wait-die) | DynamoDB | 8 function nodes, c5d.2xlarge |
| Boki | OCC + local cache | Shared log | 3 storage + 3 sequence + 8 worker nodes |

### 端到端性能（中位延迟 700ms 时的吞吐量提升）

| Workload | vs. Boki | vs. Beldi |
|----------|----------|-----------|
| Movie Review | 2.0× | 6.0× |
| Travel Reservation | 4.0× | 20× |
| Banking Service | 5.0× | 17× |

### RDMA 环境下并发控制协议对比

将 Boki 和 Beldi 的并发控制协议移植到 RDMA 环境后，RTSFaaS 仍然实现 **1.7×**（vs. Remote OCC + Cache）和 **2.1×**（vs. Remote Lock）的性能提升。

### 关键影响因素

- **数据访问偏斜**（Zipfian θ）：RTSFaaS 在所有 skew 级别均保持最高吞吐；Remote OCC 在 θ=0.6 达到峰值后因冲突增多急剧下降
- **只读事务比例**：RTSFaaS 在低只读比例时优势尤为明显
- **事务 workflow 长度**：RTSFaaS 随长度增加性能下降最缓，Remote OCC 在高 skew + 长 workflow 时下降最快
- **Batch size**：吞吐量在 n=25600 时达到平台期，但 P99 延迟随 batch size 增大而显著增加

---

## 六、批判性分析

1. **基线对比不完全公平**：RTSFaaS 使用 RDMA 集群（7µs RTT），而 Beldi 和 Boki 运行在 AWS EC2 VM 上（100-120µs RTT）。虽然论文通过将 Beldi/Boki 的并发控制协议移植到 RDMA 环境做了补充实验，但端到端的 5×/20× 加速数字本质上包含了网络硬件的巨大优势，容易给读者造成误导。

2. **Batch 机制引入的固有延迟被轻描淡写**：RTSFaaS 在低负载时也有恒定的延迟（batch interval 500ms），这意味着单个请求的最低延迟约 500ms。对延迟敏感的交互式应用场景，这个代价是不可接受的。论文虽然在实验中提到了这一点，但没有深入讨论其对适用场景的限制。

3. **Dependent reads 的处理代价被低估**：论文承认 dependent reads 需要 driver 做 early reads 来解析完整访问集，并且未解析的依赖需要广播到所有 workers。在实际应用中（如条件分支、动态查询），dependent reads 可能非常普遍，但论文没有量化这种情况下的性能退化。

4. **可扩展性未充分验证**：实验仅使用 4 个 worker，数据集仅 20,000 项。在更大规模（数十/数百 worker）下，global TPG 的构建、lease table 的同步、driver 的集中式调度都可能成为瓶颈。论文没有讨论或实验验证。

5. **Hotspot contention 的解决方案仅停留在展望**：论文在 Limitations 节承认单一 lease holder 模型在高热点场景下可能成为瓶颈，提出了 replicated-state model 的设想，但没有实现和验证。

6. **Fault tolerance 恢复时间较长**：Docker startup + reconnection 需要 20.31s + 15.66s，这对于生产环境的 FaaS 平台来说恢复时间过长，论文仅轻描淡写地提到可以用 MITOSIS 等优化。

---

## 七、AI Infra / MLSys 视角

1. **Lease-based 缓存亲和性调度的启发**：RTSFaaS 的 affinity-aware lease assignment 思路可以借鉴到分布式推理系统中的 KV cache 管理——将频繁被同一组请求访问的 KV cache 分片通过排他性租约固定在特定 GPU/节点上，减少跨节点的 cache 迁移。

2. **TPG 解耦规划与执行**：将一致性保障前置到 planning 阶段，execution 阶段无锁执行的思路，与 AI 推理中 prefill/decode 分离的架构设计理念类似。可以探索在多租户推理服务中，用类似的 TPG 机制预先规划请求的资源分配和调度顺序。

3. **值得跟进的方向**：
   - 将 lease-based 并发控制应用于分布式 KV cache（如 Mooncake、DistServe 场景），研究如何在 disaggregated memory 架构下通过 RDMA 实现低开销的 cache coherence
   - 探索 batch scheduling + affinity-aware placement 在 LLM serving 中的应用：按请求的 prefix sharing 模式分配到特定 worker，类似 RTSFaaS 的 data-function affinity 思想

---

## 八、总结

RTSFaaS 提出了一种基于 RDMA 的事务性有状态 FaaS 框架，通过 affinity-aware lease assignment 提高缓存命中率，通过 TPG 将一致性保障与执行解耦，利用 one-sided RDMA 原语实现高效的动态租约转移。在端到端评测中相比 Boki/Beldi 实现 5×/20× 吞吐提升，在公平的 RDMA 环境下仍有 1.7×/2.1× 优势。主要局限在于 batch 机制引入的固有延迟、小规模实验验证、以及 dependent reads 和热点场景下的性能退化问题。
