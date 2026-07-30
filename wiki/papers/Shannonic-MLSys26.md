---
type: paper
name: Shannonic
full_title: "Shannonic: Efficient Entropy-Optimal Compression for ML Workloads"
authors: [Kareem Ibrahim, Mohammadjavad Maheronnaghsh, Andreas Moshovos]
venue: MLSys
year: 2026
tags: [lossless-compression, quantization, federated-learning, ans, edge-inference]
source_pdf: "[[98dce83da57b0395e163467c9dae521b/98dce83da57b0395e163467c9dae521b.pdf]]"
source_md: "[[98dce83da57b0395e163467c9dae521b]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-30
---

# Shannonic：ML 工作负载的高效熵优化压缩（MLSys 2026）

> **原题**：Shannonic: Efficient Entropy-Optimal Compression for ML Workloads

> **一句话总结**：8-bit 量化张量分布偏斜但通用 ANS 需 **4–16KB** 状态；Shannonic 将符号编码为 (range ANS index, fixed-width offset)，**530B** codec 状态达 Shannon 限 **1%** 内，Theorem 1 证明分区在 ML 张量上优于标准 tANS；联邦学习 WiFi/LTE 上 **1.3–3.1×** 更快，边云 Llama2-7B 推理延迟降 **29–32%**。

## 问题与动机

[[Federated-Learning]]、边云协同 [[LLM]]、多级内存（[[FlexGen]] 类）使**数据移动**成瓶颈。[[Quantization]] 有损且训练场景需在线精度决策；通用无损压缩（zlib、zstd）表大、状态重，难进 ML 热路径。

目标：**(1)** 接近熵极限压缩；**(2)** 推理/训练吞吐匹配；**(3)** 仅数百字节状态、每符号少量 op。

## 关键观察 / 隐含假设

- 观察 1：量化后 INT8 张量 histogram 高度偏斜，少数值占大部分概率质量，但 alphabet 仍为 256。 标准 tANS 需 L≥4N（~1024 states）才近最优，表 4–16KB。
  - **依赖假设**：offline 预处理可为 weights/embeddings 用静态 histogram；activations 用少量 calibration 样本，分布漂移时刷新表（成本计入端到端）。
  - **可能失效场景**：极度均匀分布张量（分区 offset 惩罚 > tANS 量化增益）；动态范围剧变需频繁重 profiling。

- 观察 2：将 alphabet 分为 K=16 非均匀 range 后，range 内分布近均匀，固定宽度 offset 效率接近逐符号 ANS；range 索引用更小 L=128 的 tANS 即可。 Llama-3.1-8B layer.16 k_proj：tANS 5.592 b/sym vs Shannonic 5.336 b/sym（H=5.307），状态 8× 更少。
  - **依赖假设**：DP 在 256 符号上求最优 16 连续分区可离线完成；runtime 仅查 rangeId[x] + ANS 转移。
  - **可能失效场景**：K 过小无法拟合多峰分布；定理条件 (3) 在一般分布上不一定成立（论文针对 NN 张量实证验证）。

- 假设 1：530B working set 可常驻 L1，使软件 codec 达 100MB/s–9.76GB/s（平台/线程数相关），不拖慢训练/推理主路径。
  - **证据强度**：**中**——Pi5/i9 微基准有力；端到端 FL/边云实验确认收益，但未测与 GPU kernel 并发争用 L1 的极端情况。

## 核心方法

**预处理**：histogram → DP 求 K=16 连续区间最小化 entropy(range)+Σ N_s,e·⌈log2|E|⌉；建 rangeId[256]、128-state enc/dec table（base, nb, bias, start）。

**Runtime**（L=128）：Encode 发 offset nb[s] bits → 归一化 state X∈[128,255) → encTable 转移；Decode 逆过程。每符号 O(1) lookup/shift/add。

**Theorem 1**：给出 Shannonic 平均码长低于 tANS 的充分条件——分区减少 D_KL 量化损失超过 offset 开销 H(p|P)。

## 设计取舍

- **Range partition vs 纯 tANS/rANS**：赢得状态 footprint 与 L1 友好；代价是离线 per-tensor 表 + 分布漂移时需 refresh。

- **固定 K=16, L=128 vs 自适应**：实现简单、530B 固定；非最优张量可能浪费码率。

- **Lossless vs 量化**：零精度损失，可与 INT8/FP8 正交叠加以再压带宽；不能替代低比特有损压缩的最大倍率。

- **静态表 vs 在线 adaptive coding**：前者适合 ML 部署低延迟；训练态 activation 需 calibration 管线。

- **边界条件**：主攻 8-bit 张量；硬件 RTL 实现提及但未作为主线评估。

## 实验与结果

- **码率**：多样 8b 模型 codec 效率在 Shannon 限 **1%** 内；状态 **530B** combined encoder/decoder。
- **吞吐**：Pi5 单流 decode **286MB/s**，4 线程 **1.14GB/s**；i9 24 线程 decode **9.76GB/s**。
- **联邦学习**：ResNet-18 over WiFi/LTE，训练通信加速 **1.3–3.1×**（含表 refresh 成本）。
- **边云推理**：Llama2-7B 激活传输，端到端延迟降 **29–32%**。
- **分布漂移**：Table 2 显示仅显著 cross-range 概率质量迁移才明显伤码率（分区部分免疫）。

## 批判性分析

### 论证链条

定理 + Llama 层实例 + 多模型验证形成「ML 张量偏斜 → 分区 ANS 更优」闭合论证。系统案例（FL、边云）把码率优势映射到 wall-clock，非仅 b/sym 微观指标。

### 假设压力测试

- **已证明**：8b weights/activations 广泛有效；漂移 refresh 成本纳入 FL 测量。
- **可能失效**：FP16/BF16 直接上 Shannonic 需重新划 alphabet；多流并行每流一套表复制状态（论文讨论 replication 成本）。
- **未覆盖**：与 zstd GPU、NVComp 等硬件压缩器头对头；训练 all-reduce 压缩与 NCCL 集成。

### 实验可信度

FL/边云场景贴合动机；ResNet-18 与 Llama2-7B 代表两类 workload。缺少与「仅量化、不无损」的带宽-精度 Pareto 曲线。

### 系统性缺陷

Per-tensor 预处理在超大模型上表管理复杂度论文未详述；多 tenant 共享 codec 状态隔离未讨论；错误解压对 ML 数值影响（bit-exact 要求）依赖无损保证。

## 局限与后续工作

- **局限 1**：主要针对 8-bit 离散张量；更低 bit 或浮点需扩展分区策略。
- **局限 2**：Activation 分布漂移需 refresh 机制，极端 non-stationary 训练增加运维负担。
- **Future work 1**：measurement 驱动找 K、L 与 per-layer vs per-tensor 表粒度的 Pareto（带宽 vs CPU cycles）。
- **Future work 2**：与 [[FlexGen]] 式 tiered memory 集成，量化跨 tier 传输的端到端 energy。

## 相关

- **相关概念**：[[Quantization]]、[[Federated-Learning]]、asymmetric-numeral-systems
- **同类系统**：[[FlexGen]]、zstd FSE
- **同会议**：[[MLSys-2026]]
