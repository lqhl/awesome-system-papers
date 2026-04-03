# Primus: Unified Training System for Large-Scale Deep Learning Recommendation Models

**作者**：Jixi Shan (ByteDance), Xiuqi Huang (Zhejiang University), Yang Guo, Hongyue Mao, Ho-Pang Hsu, Hang Cheng, Can Wang, Jun Song, Rui Shi (ByteDance), Xiaofeng Gao (Shanghai Jiao Tong University), Jingwei Xu, Shiru Ren, Jiaxiao Zheng, Hua Huang, Lele Yu, Peng Xu (ByteDance), Guihai Chen (Shanghai Jiao Tong University)
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/shan-jixi
**源文件**：[[atc2025-shan-jixi.pdf]]

---

## 一、背景

深度学习推荐模型（DLRM）是字节跳动等互联网公司核心业务（搜索、广告、推荐）的基石。随着用户规模和数据量持续增长，DLRM 的复杂度和计算需求大幅上升。截至 2025 年，字节跳动已投入超过 1000 万 CPU 虚拟核心、数万块 GPU 和 7 EB 总训练数据用于 DLRM 训练，单个模型的训练数据量可超过 20 PB，涉及超 10 亿神经网络参数。过去五年中，字节跳动内部每日 DLRM 训练任务增长了 10 倍，每模型日训练数据从 20 TB 增至 160 TB。

在如此大规模的生产环境下，高效协调训练资源、数据和模型至关重要。现有训练系统在跨调度系统资源管理、多源数据编排、以及在线-离线混合训练范式方面存在明显不足。

---

## 二、要解决的问题

1. **跨集群异构资源管理困难**：生产环境中资源分布在 YARN 和 Kubernetes 等多个调度系统中，现有 ML 调度框架通常只支持单一调度系统。弹性训练策略（如 Oobleck、DynamoML）局限于 Kubernetes 上的 GPU 弹性训练，无法跨调度系统进行水平和垂直扩缩容。

2. **大规模多源数据编排复杂**：DLRM 训练需要从 HDFS、Kafka、Feature Store 等多种存储系统读取 batch 和 stream 数据，缺乏统一的数据描述和编排机制。现有训练系统（如 Horovod、DLRover）通常只支持单一数据源，无法原生支持多源混合数据编排。

3. **在线训练的灾难性遗忘问题**：在线训练虽然能提升模型时效性，但仅依赖 stream 数据会导致模型遗忘历史知识（catastrophic forgetting）。现有系统缺乏统一的离线-在线训练支持，频繁的模型 dump/load 阻碍了高频更新。

---

## 三、洞察与设计

**关键洞察**：DLRM 训练中，batch 数据（历史离线数据）和 stream 数据（实时在线数据）承担本质不同的角色——batch 数据提供稳定的历史知识防止遗忘，stream 数据捕捉最新趋势保证时效性。通过在模型架构层面将两者的学习路径分离（memory tower 和 adapt tower），可以同时兼顾鲁棒性和时效性，而无需在两者之间妥协。

### 系统架构

Primus 采用集中式分层架构，包含三个逻辑平面：

- **统一资源调度**：通过 Unified Resource Controller 标准化 YARN 和 Kubernetes 的资源语义，使用 JobCRD 定义训练拓扑。Dynamic Scaling Manager 基于 MetricCRD 自动选择水平/垂直扩缩容策略。
- **统一数据编排**：定义三层数据抽象（Primus Dataset → Primus Data Stream → Primus Data Source），通过 Data Task Graph Generation (DTGG) 高效生成数据任务，支持 batch 和 stream 数据的混合调度。
- **统一训练范式**：提出 Mixture Training Recommendation Model (MTRM)，包含 memory tower（处理 batch 数据，防止遗忘）和 adapt tower（处理 stream 数据，捕捉最新趋势），两个 tower 的参数更新彼此独立。

### 核心组件

- **Primus APIs**：API-Server 存储 JobCRD、DataCRD 和 MetricCRD，提供 API-Client 进行读写。
- **Primus Master**：中心化训练控制单元，负责资源调度（Unified Resource Controller）、动态扩缩容（Dynamic Scaling Manager）、数据任务规划（Task Planner）和状态/检查点管理。
- **Primus Executors**：分为 Data Executor（数据加载、预处理、通过 RPC 服务数据）和 Training Executor（模型训练计算）。

---

## 四、实现细节

### 多策略动态扩缩容

- **水平扩缩容**：通过分片 operator 降低大集群调度延迟；自动调优 CPU/GPU 协作训练中 data executor 和 training executor 的比例，基于负载值 $L_u = w \cdot u$ 与阈值 $L_\theta$ 比较决定扩缩方向。
- **垂直扩缩容**：实时监控每个 executor 的 CPU/内存/IO/网络指标，使用加权时间序列预测 $D(N_R)$ 计算未来资源需求，更新分配 $R'_{alloc} = R_{used} + R_x + R_s$，设最小调整阈值 $R_\theta$ 避免频繁微调。

### Data Task Graph Generation (DTGG)

DTGG 由四种 OP 组成：
- **Timer OP**：为每个时间窗口生成触发器
- **Data Source OP**：根据时间窗口从对应存储系统定位数据文件，构建数据任务
- **Joiner OP**：收集所有 data source OP 生成的数据任务
- **Sink OP**：按时间顺序推送到缓冲区

通过缓存重复数据任务和融合相同数据源的 OP 来加速任务生成。

### MTRM 训练流程

- Memory tower 处理 batch 数据的 embedding，生成 $h_M$；处理 stream 数据时生成辅助表示 $h_{aux}$（不参与 memory tower 反向传播）
- Adapt tower 将 stream 数据的 embedding 与 $h_{aux}$ 拼接后处理，生成 $h_A$
- 两个 tower 分别计算损失 $L_M$、$L_A$ 并独立更新参数，实现时间和参数层面的隔离

### Mixture Data Prioritization

使用优先级队列动态调整多源数据的处理顺序：$p_i = w_i \cdot \text{sigmoid}(q_i)$，其中 $w_i$ 是数据源权重，$q_i$ 是缓冲区队列长度。stream 数据源权重远高于 batch，确保高峰期优先处理实时数据。

### 容错与稳定性

- 频繁 checkpoint、资源预留和稳定性约束
- Data executor 支持 shuffle 机制处理数据倾斜
- Stream task runner 持续运行不终止，保证 stream 数据加载稳定性

---

## 五、实验结果

### 实验规模

| 类别 | 配置 |
|------|------|
| Data Workers | 800 CPU workers，每个 5 cores + 50 GB 内存 |
| Training Workers | 4 GPU workers，每个 8 GPUs |
| 数据任务 | 0 到 8000 万个任务（约 180–540 天数据） |
| 数据源 | 2–18 个，每个 10–20 PB |
| 训练吞吐 | 200K–600K samples/s |
| 模型大小 | 500 GB – 1 TB |

### 资源调度

| 指标 | Baseline | Primus |
|------|----------|--------|
| CPU 核心使用 | 7200 | 5520（-23.3%） |
| AUC | 0.9385 | 0.9382（基本持平） |
| ROI（吞吐/核心） | 30.26 | 35.44（+17.1%） |

- 垂直扩缩容将 CPU 利用率从 50% 提升到 80%
- 动态内存调整避免 PS executor OOM，吞吐从 275 提升到 496 minibatch/s

### 数据编排

- DTGG 单线程将 400 万数据任务生成时间从 58 分钟降至 149 秒（23×），4 线程进一步降至 42 秒
- 与 Flink 对比，stream 数据加载吞吐 3.97 GB/s vs 3.17 GB/s（1.25×），在 25% 慢节点场景下优势更明显

### 模型效果（MTRM）

| 模型 | AUC 提升 | 广告收入提升 |
|------|----------|------------|
| Model 1 (DSSM, LHUC) | +0.03% | +1.045% |
| Model 2 (FM, Transformer) | +0.06% | +0.806% |
| Model 3 (FM, DIN, Transformer) | +0.05% | +2.438% |
| Model 4 (EMSNet, LHUC) | +0.07% | +0.397% |

- Mixture Data Prioritization 在高峰期大幅减少 stream 数据加载延迟（从 10^7 B 降至 10^2 B 量级）

---

## 六、批判性分析

1. **AUC 提升幅度极小但收入提升显著**：四个模型的 AUC 提升仅 0.03%–0.07%，但广告收入提升 0.4%–2.4%，跨度很大。论文未充分解释 AUC 微小提升如何转化为如此大幅度的收入增长，也未讨论 A/B 测试的统计显著性和置信区间。考虑到推荐系统中 AUC 和收入之间的非线性关系，这一结果需要更严谨的统计分析支撑。

2. **实验缺乏统一基线**：资源调度、数据编排、训练范式三个模块分别评估，缺少端到端的整体对比。读者无法判断三者组合的真正增益，也无法区分各模块的边际贡献。

3. **MTRM 的适用性边界不清**：论文将 MTRM 作为通用的混合训练框架，但只在 CVR/CTR 广告模型上验证。对于其他 DLRM 场景（如搜索排序、内容推荐），memory tower 和 adapt tower 的分离是否同样有效未做讨论。

4. **垂直扩缩容的预测模型过于简化**：使用简单的加权线性趋势预测资源需求（Eq. 2），对于突发流量、周期性负载等复杂模式可能不够准确。论文未讨论预测失败的情况及其对训练的影响。

5. **与 Flink 的对比不够公平**：Primus 的 data executor 是专门为 DLRM 训练设计的，而 Flink 是通用流处理框架。在 25% 慢节点场景下对比，更多是在展示专用系统 vs 通用系统的差异，而非同等设计目标下的技术优劣。

6. **开源版本与生产版本差距**：论文提供了 GitHub 开源链接，但生产环境中依赖字节跳动内部的 YARN/Kubernetes 集群、Feature Store、Kafka 等基础设施，开源版本的实际可复现性和可用性未做说明。

---

## 七、AI Infra / MLSys 视角

### 启发与借鉴

- **跨调度系统的统一抽象**：Primus 通过 CRD 标准化 YARN 和 Kubernetes 的资源语义，这种设计思路可迁移到 LLM 训练场景。随着企业同时运营多个集群和调度系统，统一的资源抽象层将成为刚需。
- **CPU-GPU 协作训练的自动调优**：DLRM 中 CPU（数据预处理）和 GPU（模型计算）的比例调优问题，在 LLM 推理的 prefill/decode 分离、MoE 模型的 expert 调度等场景中同样存在。Primus 的负载感知水平扩缩容机制值得参考。
- **数据编排的三层抽象**：Dataset → Data Stream → Data Source 的层级设计，对持续预训练（continual pre-training）和增量学习场景有参考价值，这些场景同样需要混合历史和实时数据。

### 值得跟进的方向

1. **LLM 持续训练的混合数据编排**：将 MTRM 的 memory/adapt tower 思路迁移到 LLM 的持续预训练中——用 frozen 参数保留基础能力，用 adapter 参数学习新知识，配合 Primus 式的数据优先级机制。
2. **推理系统的弹性资源调度**：Primus 的垂直扩缩容（实时调整 CPU/内存）可应用于 LLM 推理服务，根据请求负载动态调整 KV cache 内存和计算资源。
3. **多集群训练的统一控制面**：随着 LLM 训练规模扩大到多数据中心，Primus 的跨调度系统抽象可以作为多集群训练控制面的设计参考。

### 最有价值的切入点

基于 DTGG 的数据任务并行生成思路，构建面向 LLM 持续预训练的多源数据编排系统。LLM 的持续训练同样面临多数据源（预训练语料、指令数据、RLHF 数据、实时反馈数据）的混合调度问题，Primus 的三层数据定义和优先级机制可以直接迁移。

---

## 八、总结

Primus 是字节跳动部署五年的大规模 DLRM 统一训练系统，通过跨调度系统的资源统一抽象、三层数据定义与 DTGG 数据编排、以及 MTRM 混合训练范式三大创新，实现了训练效率和模型效果的双重提升。系统在水平扩缩容上节省 17.1% 资源，垂直扩缩容将 CPU 利用率从 50% 提升到 80%，数据任务生成加速 23×，混合训练带来 0.4%–2.4% 的广告收入增长。主要局限在于系统深度绑定字节内部基础设施，MTRM 的验证范围局限于广告 CVR/CTR 模型，且部分实验的统计严谨性有待加强。
