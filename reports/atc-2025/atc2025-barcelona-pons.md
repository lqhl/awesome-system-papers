# Burst Computing: Quick, Sudden, Massively Parallel Processing on Serverless Resources

**作者**：Daniel Barcelona-Pons (Universitat Rovira i Virgili & Barcelona Supercomputing Center), Aitor Arjona, Pedro García-López, Enrique Molina-Giménez, Stepan Klymonchuk (Universitat Rovira i Virgili)
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/barcelona-pons
**源文件**：[[atc2025-barcelona-pons.pdf]]

---

## 一、背景

云计算中，按需获取大规模计算资源一直是核心需求。Function-as-a-Service (FaaS) 因其快速弹性（秒级启动数千函数）和按用量计费模型，成为处理突发并行工作负载（burst-parallel workloads）的热门选择。这类工作负载的特点是：突发、短暂（1-2 分钟内完成）、数据量动态不可预测，常见于交互式数据分析、超参数调优、大规模排序等场景。

传统数据处理引擎（如 Spark、Dask、Ray、Flink）需要预先配置集群，启动时间长达数分钟（Table 1 显示 Spark 需 296-431s），无法满足突发工作负载的低延迟需求。而 FaaS 虽然启动快（AWS Lambda 可在 6s 内启动 960 个函数），但其设计模型存在根本性缺陷，制约了大规模并行协作任务的执行。

---

## 二、要解决的问题

FaaS 在支持大规模并行协作任务时存在三个摩擦点（friction points）：

1. **Worker 隔离（F1）**：FaaS 的多租户隔离粒度是单个函数调用。系统逐个独立创建函数实例，无法感知同一 job 的 worker 之间的协作关系，导致 worker 启动时间离散度高（首尾差距可达 6-44s），无法保证并行性。

2. **Job 碎片化与复杂编排（F2）**：由于 worker 无法确保同时存在，协作式工作负载（如 TeraSort 的 shuffle、PageRank 的迭代聚合）只能通过外部存储异步中转数据，将 job 拆分为多个 stage。这增加了数据搬运开销，需要额外的编排组件监控 job 状态，在迭代算法（如 PageRank）中几乎不可行。

3. **大量数据搬运（F3）**：每个孤立的 worker 都需要独立的远程通信连接，大量细粒度 worker 之间的通信（如 shuffle）产生巨大的远程数据传输量，且 FaaS 不支持直接通信。

---

## 三、洞察与设计

**关键洞察**：FaaS 阻碍 burst-parallel job 的根本原因是缺乏**组感知（group awareness）**——系统以单个函数调用为隔离单元，而协作式 job 中这种细粒度隔离是有害且不必要的。将多租户隔离边界从单个函数提升到 job 级别，就能同时解决并行性保证、worker 打包和局部性利用三个问题。

基于这一洞察，论文提出了 **Burst Computing** 模型，核心包含两个原则：

### 1. Group Invocation（Flare）
提供一个组调用原语 **flare**，一次性启动大规模 worker 组，将整个 job 作为一个调度单元。Flare 保证所有 worker 同时启动并行运行。

### 2. Worker Packing 与局部性利用
Flare 使得系统可以将同一 job 的多个 worker **打包（pack）**到同一容器中运行。n 个 worker 被分配到 m 个 pack 中，每个 pack 包含 g = n/m 个 worker（g 称为 granularity）。Packing 带来三重好处：
- **减少容器创建数量**：创建更少、更大的容器，加速启动
- **共享代码和数据加载**：每个 pack 只需加载一次代码和依赖
- **启用本地通信**：同一 pack 内的 worker 通过共享内存零拷贝通信

Packing 策略分为三种：
- **Heterogeneous**：尽可能大的容器，最大化局部性但易碎片化
- **Homogeneous**：固定大小容器，简化管理但限制局部性
- **Mixed**：固定大小 + 同机合并，兼顾调度效率和局部性

### 3. Burst Communication Middleware (BCM)
提供 MPI 风格的 worker 间通信中间件，包含 send/recv、broadcast、all-to-all、reduce 等原语。通信自动感知局部性：同 pack 内走零拷贝共享内存，跨 pack 走远程后端（Redis/DragonflyDB/RabbitMQ/S3）。

---

## 四、实现细节

系统基于 **Apache OpenWhisk** (v1.0.0) 扩展实现，改动约 2K SLOC。

**平台层改动**：
- Controller 新增 deploy 和 flare 两个 HTTP 端点，实现组调用逻辑和三种 packing 策略
- Invoker 按 CPU（而非 RAM）报告负载，为每个 burst 创建指定大小的 Docker 容器
- Runtime 采用定制的 **Rust 运行时**，每个 worker 对应一个线程，利用 Rust 的内存安全和引用计数实现线程安全的零拷贝通信

**BCM 实现**（约 5K SLOC Rust）：
- 本地通信：利用 Rust 线程间直接传递内存指针（Arc 引用计数），broadcast 时 root worker 发送只读指针，其他 worker 并发安全访问
- 远程通信：每个 pack 共享连接池，大消息分块（chunk）并行发送/接收以最大化带宽利用
- 支持 at-least-once 语义：通过消息计数器处理去重和乱序
- 可扩展后端接口：区分 one-to-one（直连 broker）和 one-to-many（fan-out broker）消息模式

**Worker API**：
- `work(inputParams, burstContext) -> Output` 单一函数接口
- BurstContext 提供 workerID、burstSize、packID、packSize 等信息
- 通信原语：send/recv、broadcast、allToAll、reduce

---

## 五、实验结果

实验在 AWS us-east-1 上进行，使用 Amazon EKS 集群，invoker 机器为 c7i.12xlarge（48 vCPU, 96GB RAM），最多 20 台，支持 960 workers。

### 组调用性能

| 指标 | FaaS (g=1) | Burst (g=48) | 改进 |
|------|-----------|-------------|------|
| 960 worker 启动延迟 | ~20s | ~1.7s | **11.5×** |
| Worker 启动离散度 (range) | 18.8s | 0.44s | **43×** |
| Worker 启动离散度 (MAD) | 2.65s | 0.1s | **26.5×** |

### 通信后端吞吐

DragonflyDB List 表现最优，384 workers 并行时聚合吞吐超过 2.5 GiB/s。Redis 因单线程无法扩展，RabbitMQ 上限约 1 GiB/s。

### 组通信延迟（Broadcast + All-to-All）

- Broadcast (g=48 vs g=1)：延迟降低 **~98%**
- All-to-All (192 workers, g=48, 4 packs)：延迟降低 **~25%**（因半数流量仍需跨 pack）

### 端到端应用

| 应用 | 配置 | FaaS | Burst | 加速比 |
|------|------|------|-------|--------|
| 超参数调优 | 96 workers, 500MiB 数据 | Ready time 17.51s | 2.57s (g=96) | **6.8×** |
| PageRank | 256 workers, 50M 节点, 10 迭代 | 不可行（stage 爆炸） | 13× faster (g=64 vs g=1) | 网络流量降低 **98.5%** |
| TeraSort | 192 workers, 100GiB | ~150s (MapReduce) | ~75s | **2× (1.91× mean)** |

TeraSort 与等规模 Spark 部署对比：Spark 执行 100-110s 但需 5 min 启动集群。

---

## 六、批判性分析

1. **基线选择偏软**：论文的 FaaS 基线是未修改的 OpenWhisk 和 AWS Lambda + 外部存储通信。这是 vanilla FaaS 的最差实践。现有大量优化工作（如 FMI 的直连通信、SAND 的函数共享、ProPack 的打包调度）被放在 related work 而非基线对比中。作者虽然论述了"这些工作可以与 burst computing 结合"，但未量化组合效果，使得 reported speedup 可能被高估。

2. **仅支持 Rust，生态局限性大**：当前原型仅有 Rust runtime，Python binding "正在开发中"。但论文中的超参数调优实验使用 sklearn（Python），这意味着要么存在未说明的 Python 支持路径，要么该实验的实现细节被模糊处理了。Burst computing 目标用户（数据科学家、ML 工程师）主要使用 Python，语言限制是重大实用性障碍。

3. **TeraSort 加速比不够亮眼**：对于论文强调的核心优势（局部性 + 同时性），TeraSort 只有 2× 加速令人意外。论文解释 all-to-all 即使只有 2 个 pack 也仍有半数流量走远程——这恰恰暴露了 burst computing 在 all-to-all 重通信模式下的局限性。

4. **容错机制缺失**：论文完全没有讨论 worker 或 pack 失败时的恢复策略。对于 960 个 worker 的大规模 burst，任一容器故障的概率不可忽略。容器"目前不会跨 burst 复用"进一步加剧了这一问题。

5. **粒度选择依赖先验知识**：论文建议将 granularity 选择交给平台而非用户，但未提供任何自动化策略。"Smart burst sizing is left for future work" 意味着当前系统需要人工调参，而 g 对性能影响显著（从 1 到 48 差距 11.5×），选错 g 会严重降低效果。

6. **单 job 视角的局限**：整个评估只考虑单个 burst job 独占集群的场景。多租户环境下，大 granularity 的 packing 如何与其他 tenant 的资源需求竞争？mixed packing 的碎片化问题在多 job 并发时可能更严重，但论文未评估。

---

## 七、AI Infra / MLSys 视角

1. **分布式训练/推理的局部性思路可借鉴**：Burst computing 的 worker packing + 零拷贝本地通信思路，与分布式推理中的 tensor parallelism intra-node / pipeline parallelism inter-node 的通信模式高度类似。可以探索将 packing 策略应用到 serverless inference 场景——例如将同一请求的多个 expert（MoE）打包到同一节点以减少 all-to-all 通信。

2. **超参数调优 / AutoML 的 serverless 化**：Burst computing 天然适合超参数搜索这类 embarrassingly parallel + 共享数据的场景。结合 burst 的数据共享优化（pack 内只下载一次数据），可以为 AutoML 平台提供更高效的 serverless 后端，特别是在数据集较大时。

3. **Flare 原语对 ephemeral cluster 的启示**：Group invocation 的思路可以迁移到按需创建 GPU 集群进行短时训练任务（如 fine-tuning、evaluation）。当前 GPU 集群的启动延迟是主要瓶颈，类似 flare 的组调度原语如果能在 GPU serverless 平台实现，将显著降低短任务的 overhead。

4. **值得跟进的研究方向**：
   - 将 BCM 的零拷贝通信与 NCCL 等 GPU 通信库结合，探索 GPU burst computing
   - 自动 granularity 选择：基于通信模式（broadcast-heavy vs all-to-all-heavy）和数据特征自动决定最优 packing
   - 多 burst 编排：支持 DAG 式的多阶段 burst 工作流，适用于复杂 ML pipeline

---

## 八、总结

Burst Computing 提出了一种面向突发大规模并行任务的新型 serverless 计算模型，通过 group invocation (flare) 原语将 FaaS 的隔离粒度从单个函数提升到 job 级别，实现 worker packing 和局部性利用。在 PageRank 上实现 13× 加速和 98.5% 网络流量削减，在 TeraSort 上实现 2× 加速。该方案适用于短时、突发、需要 worker 协作的并行计算场景，但当前存在语言生态受限（仅 Rust）、容错缺失、多租户未验证等局限。其核心贡献在于证明了 FaaS 平台可以通过相对简单的扩展（组调用 + packing）显著改善大规模并行任务的执行效率。
