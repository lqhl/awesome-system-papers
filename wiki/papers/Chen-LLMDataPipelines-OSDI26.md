---
type: paper
name: Chen-LLMDataPipelines
full_title: "Teaching The Old Dog New Tricks: Building Efficient Data Pipelines for Large-Scale LLM Pre-training (Operational Systems)"
authors: [Luofan Chen, Chenhan Wang, Weidong Zhang, Jinxin Chi, Hequan Zhang, et al.]
venue: OSDI
year: 2026
tags: [llm-training, data-pipeline, hdfs, checkpoint, multimodal]
source_pdf: "[[osdi26-chen-luofan.pdf]]"
source_md: "[[osdi26-chen-luofan]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 用传统存储构建大规模 [[LLM|LLM]] 预训练数据管线（OSDI 2026）

> **原题**：Teaching The Old Dog New Tricks: Building Efficient Data Pipelines for Large-Scale LLM Pre-training (Operational Systems)

> **一句话总结**：对 ByteDance 90 天、3 万个、约 4K–20K GPU 训练任务的追踪揭示 cross-DC checkpoint 小读 RTT、启动 hot-file storm 和多模态 CPU transformation 三个瓶颈；预测复制、主动 hot-file replication 与 storage-side transformation 分别降低 76.1% evaluation merge latency、40.8% checkpoint load time 和 63.2% data-loading stall。

## 问题与动机

大模型训练持续优化 GPU compute、parallelism 与 collective，却常把 data pipeline 当成被动供数层。production pre-training 实际要在初始化读取 checkpoint、迭代读取/transform dataset，并在异地运行 companion evaluation；千到万卡同步使任何尾部存储或 CPU 延迟都转化为大量 idle GPU。

作者没有替换 exabyte-scale HDFS，而是分析传统 general-purpose storage 与 deterministic training workflow 的 architectural mismatch。目标是用 application signal 提前告知 storage 即将发生的 checkpoint、hot shard 和 transformation work，以低侵入方式升级现有 operational system。

## 关键观察 / 隐含假设

- **观察 1**：cross-DC evaluation 读取 checkpoint 中大量小 tensor，100 ms 级 WAN RTT 而非带宽限制 throughput，且 merge/reshard 流量带来约 1.5× read amplification（§3、表 3）。
  - **依赖假设**：evaluation schedule 与 checkpoint global namespace 可提前预测，远端有容量接收 replication。
  - **可能失效场景**：evaluation 随机触发、checkpoint 快速过期、跨域复制受 compliance 或 egress cost 限制。
- **观察 2**：约 4K–20K rank 同步启动会集中读取少数 global metadata/shared parameter，最慢 rank 成为 barrier；静态高 replica 又浪费常态空间（§4、图 6–8）。
  - **依赖假设**：training framework 能在启动前准确标注即将变热的 file，并在短暂 phase 后回收 replica。
  - **可能失效场景**：读取集合由 failure recovery 临时决定，或 metadata/placement control plane 本身过载。
- **观察 3**：multimodal data 的 video/image decode 会膨胀 50–100× 并消耗训练 host CPU，storage node CPU 在 IO-bound 集群中反而闲置（§5、表 5、图 11）。
  - **依赖假设**：storage CPU 有稳定 spare capacity，transformation deterministic、可安全移到 data side，网络传 transformed result 不成为新瓶颈。
  - **可能失效场景**：all-[[NVMe|NVMe]]/CPU-bound storage、复杂随机 augmentation、加密数据或 CPU 与 storage fault domain 强隔离。

## 核心方法

**Predictive Checkpoint Replication** 利用 companion evaluation 的规律和 global namespace，在 evaluation 真正启动前把 checkpoint 复制到目标 DC；对于异常 gradient 等 urgent feedback，training framework 发送 priority signal，让 storage scheduler 抢占 background replication。它把高 RTT 下的逐 tensor remote read 变成本地、可预测访问。

**Proactive Hotspot Prediction** 由 training framework 在初始化前提供 hot-file 清单，HDFS 临时扩展这些 file 的 replica 并均匀 placement，令大量 rank 分散读取；startup 结束后回收额外副本。它区别于运行时监测热度后才复制，避免 detector 尚未反应时同步 barrier 已经发生。

**Storage-Side Transformation Offloading** 把 deterministic dataloader 的 video/image decode 与部分 preprocessing 放到 storage node spare CPU。训练端与 storage 端同步 schedule，以 just-in-time 方式在需要前 transform，避免永久保存膨胀后的数据；pipeline 还需估计 transformation cost 和批次构成，减少异质 sample 导致的 straggler。

三项优化的共同抽象是把训练层已经知道的 future access、urgency 与 transform semantics 显式传给 storage，而非要求 HDFS 从过去 access 被动推断未来。

## 设计取舍

- **复用 legacy HDFS**：迁移风险和工程侵入小，保留 exabyte capacity/economics；代价是依赖额外 signal、replica lifecycle 和 storage-side execution，接口仍非通用标准。
- **提前复制换 latency**：消耗 network、capacity 与 write IO，预测错误会变成无收益开销。
- **storage CPU offload**：回收闲置计算并减轻 trainer CPU，却扩大 storage node resource contention、安全面和 failure blast radius。
- **确定性换专用优化**：规则 schedule 与 data transform 越稳定，收益越强；在线 sampling、elastic training 和 irregular agent-generated data 越多，方法越脆。

## 实验与结果

- characterization 覆盖连续 90 天 30,000 个 production job，模型从 billion 到 trillion parameters、约 4K–20K GPU，并含 FSDP/FSDP2/[[Megatron|Megatron]] 与 text/multimodal workload（§2.2）。
- 3,589 次 companion evaluation 的 trace 显示 cross-DC small-read RTT 陷阱；预测复制和 signal priority 将平均 checkpoint merging latency 降低 76.1%，个别改善更大（§3.4）。
- 原先慢 evaluation 每次约浪费 16,800 GPU-hours，优化后约 4,000 GPU-hours；该数字依赖 evaluation cluster size 与等待定义（摘要、§3）。
- 临时扩展 hot-file replica 后，平均 checkpoint read latency 从约 38.5 s 降至 22.78 s，checkpoint loading time 改善 40.8%（§4.4、图 9）。
- storage-side transformation 将 P99 data-loading latency 降低，并使 transformation straggler 引起的 stall 减少 63.2%，对应 MFU 相对提高 10.8%（§5.4）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| legacy data pipeline 在 LLM scale 出现三类系统性瓶颈 | §2–5：90 天、30k jobs 的 cross-DC/startup/multimodal trace | 单一 hyperscaler 与 HDFS 架构 | 强 |
| 预测复制显著缩短 companion evaluation | §3.4：平均 merge latency 降 76.1% | 3,589 次 production evaluation、特定 WAN/DC | 强 |
| 主动 hot-file replica 缩短同步启动 | §4.4、图 9：38.5 s 到 22.78 s，降 40.8% | MM-S trace 与生产 HDFS checkpoint | 强 |
| storage CPU offload 降低训练 stall | §5.4：stall 降 63.2%，MFU 相对增 10.8% | production multimodal workload、现有 idle CPU | 强 |

## 批判性分析

### 论证链条

论文以大规模 production trace 定位三个 bottleneck，再分别用可预测性、提前告知和资源错配设计机制，observation→design→result 链条很直接。三项优化彼此松耦合，更像 operational lessons 的组合而非统一新系统；其共同贡献是“训练语义下沉”的设计原则，而非某个单一 scheduler。

### 假设压力测试

最关键假设是未来 access 可预测。elastic restart、spot preemption 或 failure burst 会让 checkpoint/time/DC 变化，复制可能来不及；多租户 storage CPU 也可能在 compaction/scrub 高峰不再 idle。若数据 transformation 包含随机 augmentation，storage-side execution 还需传递 seed、version 和 exactly-once semantics，否则可能改变 training reproducibility。

### 实验可信度

production scale、跨 training/storage tracing 与明确 operational metric 是最大优势，远强于小型 synthetic benchmark。可复现性则受匿名 trace、内部 system 和 planned trace release 限制；缺少与 modern AI-native storage 的统一硬件对比，也未把额外 replica bytes、cross-DC traffic、storage CPU-hours 与控制面开销完整折算为 cost。

### 系统性缺陷

application hint 错误、过期或恶意时，storage 需要 admission/fairness，否则一个大 job 可抢占 WAN、制造 replica storm 或占满 storage CPU。论文未深入讨论 hint authentication、multi-tenant isolation、transform sandbox、node failure 和 rollout rollback。临时 replica 与 checkpoint dedup/erasure coding 的交互也可能让 space/network amplification 比 file-level 估计更复杂。

## 局限与后续工作

- **局限 1**：结论来自单一 hyperscaler 的 HDFS，generalizability 主要靠架构论证而非跨系统实验。
- **局限 2**：收益未减去完整 network、replica capacity、CPU 和 operational cost。
- **局限 3**：failure、prediction error、tenant contention 与 transformation correctness 未做系统压力测试。
- **后续工作 1**：按 prediction precision/lead time 扫描三种优化的 break-even 点，报告净 GPU-dollar 与 storage/network-dollar。
- **后续工作 2**：注入 restart burst、storage node failure 和错误 hot-file hint，验证 admission、rollback 与最慢 rank tail latency。
- **后续工作 3**：在随机 augmentation 下记录 seed/version/hash，比较 offload 前后 batch byte 与 model convergence，客观验证语义等价。

## 相关

- **相关概念**：[[LLM-Pretraining]]、[[Checkpointing]]、[[Data-Pipeline]]、[[Cross-Datacenter-Storage]]
- **同类系统**：[[HDFS]]、[[FSDP]]、[[Megatron-LM]]
- **同会议**：[[OSDI-2026]]
