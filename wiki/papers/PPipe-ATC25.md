---
type: paper
name: PPipe
full_title: "PPipe: Efficient Video Analytics Serving on Heterogeneous GPU Clusters via Pool-Based Pipeline Parallelism"
authors: [Z. Jonny Kong, Qiang Xu, Y. Charlie Hu]
venue: ATC
year: 2025
tags: [video-analytics, inference-serving, heterogeneous-gpu, pipeline-parallelism, milp]
source_pdf: "[[atc2025-kong.pdf]]"
source_md: "[[atc2025-kong]]"
---

# PPipe: Efficient Video Analytics Serving on Heterogeneous GPU Clusters via Pool-Based Pipeline Parallelism (ATC 2025)

> **一句话总结**：在异构 GPU 集群上用 pool-based pipeline parallelism 给 CNN 视频分析做模型分区服务，MILP 解最优分区 + 资源预留式自适应 batching，相对各 baseline 提升吞吐 32.2–75.1%、低端 GPU 利用率提升 41.1–65.5%。

## 问题

视频分析依赖 CNN（YOLO、ResNet、EfficientNet 等）做 200ms SLO 的实时推理。云厂商和私有集群 GPU 越攒越异构（V100、L4、T4、P4 共存），但低端 GPU（如 P4）单独跑大模型连 SLO 都满足不了——P4 比 L4 慢 3.0×–7.9×，仅 22% DNN 在 P4 上 batch=4 不超 200ms。

直觉上把模型切给低端 GPU 跑一部分会拖慢，但作者发现**两种 diversity 的协同**：(1) DNN 不同层在不同 GPU 上的相对 latency 差异巨大（EfficientNet-B8 早期层在 P4/L4 上 latency ratio 仅 1.7，后期层显著更高）；(2) 不同 GPU 设计 trade-off（SM 数、ops:bytes ratio）让 latency ratio 趋势在 P4 vs L4 和 P4 vs V100 上甚至完全相反。结论：**GPU-aware 模型分区 + 让每段跑在它最擅长的 GPU 类型上**可以挖出低端 GPU 的潜力。

但 chain pipeline（如训练用的 [[Pipeline-Parallelism]]）要求各 stage latency 严格匹配，约束太死。

## 核心方法

**Pool-based pipeline parallelism**：每个 partition 不是绑定一个 GPU 而是一个 pool of GPUs（同类型）。每个请求按序经过所有 partition，但在每个 partition 可走 pool 内任意 GPU。允许各 pool 用不同 GPU 数、不同 batch size、不同 latency，只要各 pool throughput 匹配且总 latency 满足 SLO。

**控制面（MILP）**：给定每模型每层在每 GPU 类型每 batch size 下的 profile、集群 GPU 数、SLO，输出最优分区点 + GPU pool 分配 + 各 pool batch size，目标最大化 throughput。
- 减搜索空间：把 600+ 层 **pre-partition** 成 N=10 个等运行时 block，MILP 只在 block 边界选分区点（求解时间从 7h 降到 3.5s）
- **Batch size unification**：用 1/1、1/2、1/3、1/4 virtual GPU（[[MPS]] 实现）让同一 pipeline 各 partition 用相同 batch size，避免 batch split/merge 的复杂度

**数据面（resource-reservation adaptive batching）**：runtime 请求是异步且 bursty 的，会引入 D1 初始 batching 延迟、D2 inter-partition 排队、D3 网络竞争。scheduler 维护当前与未来 GPU/网络资源占用，对每批请求：(1) 用 `probe()` 找 waiting time 最低的 pipeline；(2) 从 MILP batch size 起逐渐缩小直到 SLO 能满足；(3) `reserve()` 占用对应资源 interval。`probe()` 贪心选每段最早完成的 GPU，同时考虑 uplink/downlink 带宽 simultaneity 约束。深度细节回 [[atc2025-kong]]。

## 关键结果

- 100-GPU 模拟 + 16-GPU GCP testbed（V100/L4/T4/P4）实测，18 个 CNN 模型
- 相对各 baseline 提升 throughput 32.2–75.1%
- 低端 GPU 利用率提升 41.1–65.5%，同时维持高端 GPU 利用率
- 99% 请求无 drop / 无 SLO 违反
- MILP 求解从 7 小时（80 层直接搜）降到 3.5s（pre-partition + virtual GPU）

## 相关

- **相关概念**：[[Pipeline-Parallelism]]、[[MPS]]、[[Heterogeneous-Cluster]]、[[Adaptive-Batching]]
- **同类系统**：Clockwork、INFaaS、Nexus（chain-based 推理服务）
- **同会议**：[[ATC-2025]]
