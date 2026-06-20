---
type: paper
name: Primus
full_title: "Primus: Unified Training System for Large-Scale Deep Learning Recommendation Models"
authors: [Jixi Shan, Xiuqi Huang, Yang Guo, Hongyue Mao, Ho-Pang Hsu, et al.]
venue: ATC
year: 2025
tags: [dlrm, training-system, recommendation, online-learning, elastic-training]
source_pdf: "[[atc2025-shan-jixi.pdf]]"
source_md: "[[atc2025-shan-jixi]]"
---

# Primus: Unified Training System for Large-Scale Deep Learning Recommendation Models (ATC 2025)

> **一句话总结**：字节跳动生产级 DLRM 统一训练系统，基于「多调度器资源统一 + batch/stream 数据编排 + offline-online 混合训练」三层抽象，在 10M+ CPU core 规模上把 cluster ROI 提升 17.1%、CPU 利用率从 50% 拉到 80%，并在 4 个生产广告模型上带来 0.03%–0.07% AUC 与 0.4%–2.4% 收入提升。

## 问题与动机

[[DLRM]] 在搜索、广告、推荐等互联网核心场景持续膨胀：字节内部 5 年内 daily training job 增长 10×，单模型日训练数据从 20 TB 增至 160 TB，daily CPU vcore 从 150 万增至 900 万；截至 2025 年，DLRM 训练已占用 1000 万+ CPU vcore、万级 GPU、7 EB 总数据，单模型可超 20 PB 数据与 10 亿+ 参数。训练系统必须同时协调资源调度、数据加载与模型更新，直接影响资源利用率、收敛速度与线上效果。

作者 claim 的边界是：Primus 不是新的推荐模型结构论文，而是面向工业级 DLRM 训练的**统一系统层**，把资源、数据、训练范式三件事用 CRD 抽象和中心化 master 串起来。现有方案各自只解决一部分：[[YARN]] / [[Kubernetes]] 弹性训练系统通常只绑定单一调度器；[[GoldMiner]] 等只覆盖 Kubernetes；数据加载框架如 tf.data service、[[Horovod]]、DLRover 多假设单一数据源；纯 online training（[[Monolith]]、[[Persia]]）只用 stream，面临 catastrophic forgetting 与 delayed feedback。offline + online 混合训练若缺乏系统支持，还要靠 model dump/load 切换，难以高频更新。

## 关键观察 / 隐含假设

- **观察 1：大规模 DLRM 训练的主瓶颈在 CPU 侧数据预处理与多源数据编排，而非 GPU 算力本身。** 高维稀疏特征 + 大 embedding table 使 data executor 必须维持极高吞吐；feature engineering pipeline 复杂后，data reading/processing 常成为训练 worker 空等的原因。论文在 56M+ 底层文件、约 4M data task 的生产 workload 上测得 naive task generation 需 58 分钟，而 DTGG 压到 42 秒（4 线程）。
  - **依赖假设**：训练 job 的数据量、源数量、时间窗粒度继续增长；CPU executor 数量与存储元数据查询成本仍是调度关键路径。
  - **可能失效场景**：若 embedding/特征侧硬件 offload、列式存储直读 GPU、或元数据规模不再随时间窗线性膨胀，DTGG 的边际价值会下降。

- **观察 2：纯 stream online training 会 catastrophic forgetting，且不同 batch 数据源存在显著 label/output delay 差异。** 论文用统计检验指出非 MTRM 模型倾向记忆「当前分布」，既浪费历史样本空间，又放大 bias 与 delayed feedback 不稳定；batch 源之间还存在次日/7 日留存等拼接目标带来的输出延迟差。
  - **依赖假设**：生产 DLRM 需要同时保留历史 batch 知识与近期 stream 趋势；24h 延迟 batch 与实时 stream 的时间错位可被 tower 分离 + 参数更新控制消化。
  - **可能失效场景**：若业务转向极短生命周期兴趣、或 label delay 分布剧变，memory/adapt tower 固定切分可能不再最优。

- **观察 3：生产环境资源池跨 YARN/Kubernetes 且 CPU/GPU 协作训练，executor 比例与 per-executor 资源难以静态预设。** 论文用 load metric $L_u = \mathbf{w}\cdot\mathbf{u}$（buffer/CPU/memory 利用率加权）自动调节 data/training executor 数；vertical scaling 用加权历史指标 $D(N_R)$ 预测 CPU/内存需求，把 per-job CPU 利用率从 50% 提到 80%。
  - **依赖假设**：metric 采集稳定、分钟级扩缩不会破坏训练收敛；多集群 idle 状态可被 Primus 统一视图感知并跨池调度。
  - **可能失效场景**：gang scheduling 延迟极高、checkpoint 成本过大、或 metric 噪声导致频繁抖动时，动态扩缩可能伤害 tail stability。

- **观察 4：高峰 stream 突发会使 data loading lag，单纯 horizontal scale-out 在有限算力下不经济。** mixture data prioritization 用 $p_i = w_i \cdot \frac{1}{1+e^{-q_i}}$ 在 serving buffer 间做 sigmoid 加权选择，高峰时优先保 stream。
  - **依赖假设**：stream 源权重显著高于 batch；buffer 队列长度能反映 backpressure；限资源下「牺牲部分 batch 时效」可接受。
  - **可能失效场景**：若 batch 延迟样本对某类转化目标更关键，或 surge 持续时间超出 buffer 策略可吸收范围，优先级启发式可能掉点。

- **假设 1：中心化 master + 频繁 checkpoint 在百万 core 规模仍可控。**
  - **证据强度**：强。论文给出 5 年生产部署与开源版本，但 fault-tolerance 细节与 master 单点压力定量分析较少。

## 核心方法

Primus 采用 layered centralized 架构，三大 plane 通过 JobCRD、DataCRD、MetricCRD 声明式对接 API-Server，组件分为 Primus APIs、Primus Master、Primus Executors。

**Unified Resource Scheduling** 用 unified resource controller 把 JobCRD 翻译成 YARN container manager 或 Kubernetes operator 请求，自动从多 YARN/K8s 集群按 idle 状态选资源；dynamic scaling manager 读 MetricCRD，一次只执行一种策略。horizontal scaling 支持逐步增加 training executor（论文 Fig.7 显示 0→400 每 10s 扩缩仍可达 210 minibatch/s，AUC 还比固定 400 executor baseline 高约 0.4%），并按 $L_u$ 与阈值 $L_\Theta$ 调节 data/training executor 比例。vertical scaling 对每个 executor 收集 CPU/内存/I/O/网络指标，用式 (2)(3) 计算 $R'_{alloc}$，并设最小调整阈值 $R_\Theta$ 避免抖动。大集群还用 sharded operator + job name hash 降 scheduling latency。

**Unified Data Orchestration** 提出三层定义：Primus Dataset（无界有状态输入）→ Primus Data Stream（多 source 按小时/日 sliding window 混合调度）→ Primus Data Source（特定存储系统上某时间段数据，负责格式统一）。DTGG 把 stream 编译成 Timer / Data Source / Joiner / Sink 四类 OP 的 task graph，并行生成 batch 与 stream task，并缓存重复 task、融合同源 OP 以减少 HDFS/Feature Store 扫描。data driver 中心化分发 task，data executor 上多 task runner 并行，样本经 [[Apache Arrow]] 标准化后由 dataset server 通过 RPC 提供给 training executor；stream 模式支持 Forward 与 Rebalance shuffle 应对 skew。

**Unified Training Paradigm** 的核心是 MTRM（Mixture Training Recommendation Model）：memory tower 学 24h 延迟 batch（小网络、长期参数），adapt tower 学 stream（结构接近原模型）；stream 样本经 memory tower 得 $\mathbf{h}_{aux}$ 但不回传更新 memory 参数，避免信息泄露。dataset remote reader 维护 batch/stream 双队列，mixture data prioritization 决定入队速率与 serving 顺序。Primus 同时支持纯 batch、纯 stream、batch-then-stream 等模式。数据访问层用 Arrow + NativeClient 重构后 CPU 降 40%；master 用 ClassLoader 隔离集成 Iceberg/Hudi 等数据湖。

开源：https://github.com/bytedance/primus

## 设计取舍

- **中心化 master 换一致语义**：统一 CRD 监视、task 编排、扩缩决策都收敛到 master，简化 multi-source chronological serving，但 master 成为调度与元数据热点；论文用频繁 checkpoint、资源预留与 stable constraints 换 fault tolerance，未展开 master HA 分片。
- **跨 YARN/Kubernetes 抽象换可移植复杂度**：用户只见 JobCRD，底层却要维护两套 container/operator 路径；YARN 上每 job 独立 API-Server，K8s 用集群 API-Server——一致体验靠 Primus 中间层隔离，迁移期工程成本高（论文 Lessons 节有记录）。
- **MTRM tower 分离换模型改动侵入性**：不要求重写全部 DLRM 结构，但要求开发者接受双 tower 训练逻辑与 24h batch 延迟设定；memory tower 过小可能欠拟合历史，过大则抵消「小 tower 低开销」初衷。
- **mixture prioritization 换 batch 公平性**：高峰优先 stream 保护 online 效果，但可能牺牲部分 delayed batch 的及时消费；权重 $w_i$ 需人工/经验设定，论文未给自动标定方法。
- **边界条件**：最优雅于字节式多集群 DLRM、batch+Kafka+Feature Store 混合、广告/推荐高频更新场景；脆弱于单一调度器小集群、单数据源、或模型结构无法拆成双 tower 的任务。

## 实验与结果

- **资源横向扩缩**：固定 900×8-core data executor + 8 training executor baseline 对比动态调比，最终 690 data executor，CPU core 节省 23.33%，训练时间 1.86→1.90 天、AUC 0.9385→0.9382 基本持平；生产 cluster ROI 30.26→35.44（+17.1%）。
- **资源纵向扩缩**：400×10-core data executor 场景 CPU 总分配降 1600 core，利用率 50%→80%，吞吐与 AUC 不变；496 PS executor ×16GB 场景动态加内存至 9920 GB，避免 OOM failover，吞吐 275→496 minibatch/s，AUC 0.62→0.78。
- **DTGG**：20 天生产 Feature Store 数据、56M+ 文件、~4M task；单线程 PyTorch baseline 58 min → DTGG 149 s（23×），4 线程 42 s。
- **Stream 加载**：40 executor（10 台故意降速模拟故障），Primus shuffle 达 3.97 GB/s，[[Apache Flink]] 3.17 GB/s（约 1.25×）；慢节点利用率相近但 Flink 双层 task manager backpressure 更易拖垮全局。
- **MTRM**：4 个生产 CVR/CTR 模型（600GB–3.7TB），一年历史预训练后 7 天 AUC 平均 +0.03%–0.07%；A/B 广告收入 +0.397% / +0.806% / +1.045% / +2.438%。
- **mixture prioritization**：60 executor、1024 分区 Kafka 600 MB/s + Feature Store 历史副本，高峰 loading lag 显著下降（Fig.11）。

## Critical Analysis

### 论证链条

论文链条较完整：生产规模趋势（Fig.1）→ 三类系统痛点（多调度器、多源数据、online 时效）→ 三层 unified 设计各自对应 metric → 生产/准生产实验验证效率与收入。最强贡献是把 DLRM 训练里**资源弹性、数据时序编排、batch-stream 学习**绑成同一 CRD 语义，而不是三个独立工具。

需警惕的外推：收入与 AUC 提升主要来自 MTRM + prioritization，资源与 DTGG 优化证明的是**成本与吞吐**；论文把「统一系统」与「模型效果」放在同一叙事，但消融上并未严格分离「仅系统层优化」对收入的贡献。另外，5 年部署证据强，但 ATC 论文中的 controlled experiment 仍是字节内部模型与基础设施，外推到其他云厂商环境需要重新测量 scheduling latency 与存储 API 行为。

### 假设压力测试

**workload assumption**：实验覆盖 2–18 个数据源、10–20 PB 级数据、20 万–60 万 samples/s，典型是广告推荐 CTR/CVR。若 tenant 模型更小、特征维度更低、或 stream 占比极低，Primus 的复杂编排可能是 overkill。

**resource bottleneck assumption**：默认 CPU 数据面是主导瓶颈，GPU 主要用于 embedding 更新。若未来 DLRM 向 dense 化、GPU 预处理、或 embedding 全 GPU 化，data executor 弹性与 DTGG 价值结构会变。

**hardware/deployment assumption**：深度绑定 YARN + Kubernetes 双栈、HDFS/Kafka/Feature Store、Parameter Server 训练形态。换 Ray/Flink 一体化、纯 GPU PS、或多云对象存储时，unified resource controller 与 data source OP 需重写。

**scaling assumption**：DTGG 加速在 4M task 量级成立；若 task 数再上一个数量级，单 data driver 是否仍够用论文只提到 centralized driver 的 load balance/fault tolerance，未给 driver 水平扩展数据。百万 core 横向扩缩依赖 sharded operator，但是否覆盖所有 job 类型未细述。

**correctness/SLO assumption**：论文强调 AUC 与收入，对训练 job 尾延迟 SLO、跨租户隔离、扩缩引发的重调度一致性、checkpoint 恢复时间分布讨论很少；dynamic scaling「minute-level」对需要稳定 gang 的 job 是否可接受，论文未量化 tail job completion time。

### 实验可信度

强项是生产尺度与多维度指标：资源 ROI、task generation、stream 吞吐、真实 A/B 收入，比纯 microbenchmark 更有说服力。MTRM 对比是同一 stream 数据、同一预训练历史，AUC 微增但收入增幅更大，符合广告系统对排序尾部敏感的常识。

baseline 方面，资源实验多是 Primus 自带 fixed-allocation 对比，而非 [[Oobleck]]、[[ElasticFlow]]、GoldMiner 等近年系统；数据加载对比 Flink 有代表性，但未对比 tf.data service、DLRover-RM 在同等多源场景下的端到端训练时间。MTRM baseline 是 single-tower 混合读 batch/stream，而非 Monolith/Persia 等 online-only 强基线——合理，因为论文论点正是「混合范式」而非「纯 online 最快」。

### 系统性缺陷

中心化 data driver + task service 在在线模型上若出故障，影响面是整个 job 的数据时序；论文描述 checkpoint 对齐 model checkpoint，但未讨论 driver failover 时 stream offset 与 batch task 重建的 exactly-once 语义。

CRD 驱动扩缩依赖 MetricCRD 质量；式 (1)–(3) 含多个阈值与权重，生产调参成本高，论文给推荐权重但缺少 sensitivity analysis。vertical scaling 在 PS OOM 场景有效，但是否会引发资源「租过量」导致 cluster 级碎片化，未讨论。

可观测性：分钟级扩缩、DTGG 并行、buffer prioritization 同时作用，线上出现吞吐下降时 root cause 可能跨资源/数据/范式三层；论文未描述统一 trace 或 replay 工具。安全与多租户隔离（ClassLoader 读数据湖）有提及，但无威胁模型。

## 局限与 Future Work

- **局限 1**：评估绑定字节内部基础设施与广告推荐 workload，开源版与生产版能力是否一致需自行验证。
- **局限 2**：MTRM 依赖 24h batch 延迟与双 tower 手工设计，对不同 label delay 分布的自适应性未系统扫描。
- **局限 3**：与 SOTA 通用 DL 调度器、多源数据系统的 head-to-head 端到端对比有限。
- **局限 4**：master/driver 中心化扩展性与故障恢复语义论文未充分量化；论文未讨论扩缩对训练 tail latency 的影响。
- **Future work 1**：在多种 label delay 与 stream/batch 比例下自动搜索 tower 切分与 prioritization 权重，用 offline replay 衡量 AUC–吞吐 Pareto。
- **Future work 2**：测量 DTGG + data driver 在 10M+ task/job 时的水平扩展与 failover 恢复时间，明确 stream offset 一致性保证。
- **Future work 3**：与 Kubernetes-only elastic ML 系统（GoldMiner、Oobleck 等）在同等 heterogeneous CPU/GPU DLRM job 上对比 ROI、重调度开销与运维复杂度。

## 相关

- **相关概念**：[[DLRM]]、[[Online-Learning]]、[[Catastrophic-Forgetting]]、[[Feature-Store]]、[[Elastic-Training]]、[[Apache-Arrow]]、[[Parameter-Server]]
- **同类系统**：[[GoldMiner]]、[[Monolith]]、[[Persia]]、[[Horovod]]、DLRover-RM、[[Apache-Flink]]、tf.data service、[[XDL]]、[[ElasticFlow]]
- **同会议**：[[ATC-2025]]
- **对比**（如有）：Primus vs Flink online training（stream 加载与 shuffle 设计）