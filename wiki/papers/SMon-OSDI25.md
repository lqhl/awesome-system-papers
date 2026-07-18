---
type: paper
name: SMon
full_title: "Understanding Stragglers in Large Model Training Using What-if Analysis"
authors: [Jinkun Lin, Ziheng Jiang, Zuquan Song, Sida Zhao, Menghan Yu, et al.]
venue: OSDI
year: 2025
tags: [llm-training, stragglers, distributed-training, what-if-analysis, bytedance]
source_pdf: "[[osdi25-lin-jinkun.pdf]]"
source_md: "[[osdi25-lin-jinkun]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# Understanding Stragglers in Large Model Training Using What-if Analysis (OSDI 2025)

> **一句话总结**：基于字节跳动 5 个月、3079 个 ≥128 GPU 预训练 job 的 NDTimeline trace，what-if 模拟显示 42.5% job 因 stragglers 慢 ≥10%、集群 10.4% GPU-hour 浪费；主因是 PP 阶段不均、序列长度不均与 Python GC，而非硬件故障——分析流水线已产品化为 SMon。

## 问题与动机

[[Pipeline-Parallelism]]、[[Tensor-Parallelism]]、DP/FSDP 等混合并行使 LLM 训练对 straggler 极度敏感——慢 worker 通过频繁同步拖住全体。传统 backup worker / 异步 SGD 要么不适用于高频同步训练，要么改变收敛语义。业界缺乏大规模 production trace 上对 straggler 频率、模式与根因的定量证据。

## 关键观察 / 隐含假设

- **观察 1**：在专用训练集群（无网络拥塞、job 独占 GPU、同质硬件）上，42.5% job 的 slowdown S≥1.1；尾部 1% job 浪费 45% 分配 GPU-hour；步级 slowdown 与 job 级高度一致（median normalized=1.0）——straggler 多为持久性而非偶发环境抖动。
  - **依赖假设**：NDTimeline 采 10% step、OpDuration 理想化（compute 用均值、comm 用 median transfer-duration）能近似 straggler-free 时间线；模拟误差 <5% 的 trace 才纳入。
  - **可能失效场景**：CPU data loading 延迟未入 trace 导致模拟偏差；TP/CP 组内 straggler 被聚合到 microbatch 粒度无法分解。
- **观察 2**：资源浪费主要来自 **compute** straggling，而非 communication——与 FALCON 等「网络主导」观察相反，因集群带宽充裕 + 网优。
  - **依赖假设**：ByteDance 网络拓扑与 in-house 优化代表未来大规模训练网络环境。
  - **可能失效场景**：拥塞多租户集群、通信 bound 模型或 CP 主导 workload。
- **假设 1**：仅修复最慢 3% worker 对绝大多数 job 几乎无帮助（仅 1.7% job 的 slowdown >50% 可归因）——硬件故障不是主因。
  - **证据强度**：强；与 health-check 预期一致，但挑战「straggler=坏机器」运维直觉。

## 核心方法

**What-if 模拟器**：按 step×microbatch×PP×DP 张量组织 OpDuration；从 Megatron-LM 依赖模型（stream 内顺序、DP/PP 通信 collective 约束）重放 ideal timeline，得 T_ideal 与 waste = 1−1/T_ideal。

**根因归因**：逐 worker/last PP stage/sequence correlation/GC 等固定 MW、MS 指标；手工检查补充。

**SMon**：将分析流水线部分自动化部署到 ByteDance on-call。

## 设计取舍

- **取舍 1**：粗粒度 profile（整 microbatch forward/backward）换低开销与可扩展性——牺牲 TP/CP 细粒度诊断。
- **取舍 2**：丢弃 50% 无法解析/步数过少/损坏 trace——分析 fidelity 优先于覆盖率。
- **边界条件**：仅 Megatron 系、≥128 GPU、2024/01–05 预训练。

## 实验与结果

- 3079 jobs：10.4% 总 GPU-hour 因 stragglers 浪费；S>3 的极端 case 多由 <3% worker 导致。
- 39.3% job 的 majority slowdown 来自 last PP stage（loss layer 过重）。
- 21.4% job（F-B correlation≥0.9）受 sequence length imbalance 影响，avg S=1.34。
- Planned GC（同步全员 GC）在 128 DP job 上 +12.6%；序列重分布原型 +23.9% throughput（32K context 代表 job）。
- 模拟 vs 实际 step 时间 median 误差 1.3%，p90 5.5%；人工注入 straggler 估计与实测接近。

## Critical Analysis

### 论证链条

「ideal OpDuration + 依赖模拟 → waste 指标 → 分类型 MW/MS」逻辑清晰，且与手工案例（loss layer 9×、Σsᵢ² 与时长线性）互证。将 ByteDance 专用集群规律外推为「LLM 训练普遍规律」需更多云厂商 trace 交叉验证。

### 假设压力测试

- **已证明**：在该集群配置下 compute straggler 主导；PP/seq/GC 为可量化主因。
- **可能失效**：共享集群、不同 framework（FSDP 主导）、推理/微调 workload；MoE EP 不平衡论文 §7 明确未系统分析。
- **论文未覆盖**：自动修复 at scale（序列平衡 prototype 未 production 验证）；跨 job 调度器交互。

### 实验可信度

Production trace 规模大、时间跨度 5 个月；但 50% job 丢弃可能低估 straggler 普遍性。NDTimeline bug 后处理透明。缺与外部集群（Meta/Google）对照。

### 系统性缺陷

依赖用户手动调 ε（PP 层数）、GC interval；planned GC 非默认；模拟不含 CPU loader 尖刺；SMon 自动化程度论文未给 SLO。

## 局限与 Future Work

- **局限 1**：TP/CP 组内 straggler 不可分解；trace 覆盖不全（50% 丢弃）。
- **局限 2**：根因集合非穷尽（CUDA 碎片化、false dependency 仅 case study）。
- **Future work 1**：production 部署序列长度重平衡的内存开销与 scale 测量。
- **Future work 2**：扩展 NDTimeline 到 TP/CP 与 CPU pipeline，降低模拟偏差。

## 相关

- **相关概念**：[[Pipeline-Parallelism]]、[[Tensor-Parallelism]]、[[Expert-Parallelism]]、[[MoE]]、straggler、Megatron-LM
- **同类系统**：NDTimeline、DistTrain、DynaPipe
- **同会议**：[[OSDI-2025]]
