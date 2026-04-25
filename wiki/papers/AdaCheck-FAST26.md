---
type: paper
name: AdaCheck
full_title: "AdaCheck: An Adaptive Checkpointing System for Efficient LLM Training with Redundancy Utilization"
authors: [Weijie Liu, Shengwei Li, Zhiquan Lai, Keshi Ge, Qiaoling Chen, et al.]
venue: FAST
year: 2026
tags: [llm-training, checkpointing, fault-tolerance, parallelism, redundancy]
source_pdf: "[[fast2026-liu-weijie.pdf]]"
source_md: "[[fast2026-liu-weijie]]"
---

# AdaCheck: An Adaptive Checkpointing System for Efficient LLM Training with Redundancy Utilization (FAST 2026)

> **一句话总结**：用"tensor redundancy"抽象统一描述任意并行策略（DP/ZeRO/MP/EP/MiCS/auto-planner）下的 model state 分布，通过 hash-based + ring-based detector 在 3 分钟内对 128 worker 完成精确冗余识别；离线只存非冗余状态、在线只存 half-precision gradient，相比 GEMINI 把 checkpoint size 缩小 6.00–896×、checkpoint 频率提升 1.46–111× 实现 1S1C（每 iter 一个 checkpoint）。

## 问题

LLaMA 3.1 训练 54 天 16K GPU 经历 419 次失败（约每 3 小时一次），约 2M GPU hours 浪费在 checkpointing 与回滚。已有 checkpoint 系统针对特定并行（如 DP rank-0 only saves）或特定模型架构定制：异步保存 / I/O 优化系统不适配 ZeRO、MP、EP；in-memory checkpoint（GEMINI 等）忽略冗余仍存全量；都无法适配自动并行规划器生成的不规则并行策略。Yi 34B、MegaScale 530B、DeepSeek-V3、Kimi K2 实测含 25-100% 冗余 model states 未被利用。

## 核心方法

**Tensor Redundancy 抽象**：每个 tensor $t_k$ 在 worker $w_i$ 上的冗余表示为 replica 位置元组列表 $R_i^k = \{(m_1,n_1),...\}$。State redundancy 分 full / partial / no 三类。**关键洞察**：parameter 冗余度 ≠ optimizer state 冗余度（如 ZeRO-1 下 param 冗余但 optimizer state 不冗余），离线方法对二者取交集决定是否入 checkpoint，避免生成不可用 checkpoint。

**Redundancy Detector（三阶段优化）**：
- **Hash-based consistency check**：每 worker 把 tensor 列表打包成 hash tensor（blake2s）跨 worker 比对，碰撞概率 $2^{-512}$ 跨两个 iteration；
- **Comparison scope reduction**：只在 parallel strategy 已定义的 communication group 内比对，去除包含子集的冗余 group；
- **Ring-based communication**：仿 ring-allreduce，并发收发并比对，第三步起传"比对结果"而非 packed tensor。

整体使 128 worker 内冗余识别 < 3 分钟。

**Online Redundancy Utilization（gradient-based incremental checkpointing）**：mixed-precision 训练中相邻 iter checkpoint 差异即为 half-precision gradient。完整 model state 大小为 14M，只存 gradient 即 2M（缩 1/7）。配合 in-memory checkpointing 跨 worker 高速网络传输，按 model parallelism 分 checkpoint group 实现通信与计算重叠。周期性异步保存完整 checkpoint 控制 recovery 长度。

**非侵入 API**：不假设用户训练脚本、并行方法、模型架构；已开源集成至 Merak 框架。

## 关键结果

- 比 SOTA GEMINI checkpoint size 减少最多 130×，frequency 提升最多 3.64×。
- 整体相比各类 SOTA：size 减小 6.00–896×，frequency 提升 1.46–111×。
- 训练吞吐几乎零开销。
- 适配 dense（GPT、LLaMA、Yi、MegaScale）+ sparse（DeepSeek-V3、Kimi K2、MoE）+ irregular auto-generated parallelism。
- 128 worker 冗余识别仅 3 分钟。

## 相关

- **相关概念**：[[Checkpointing]]、[[ZeRO]]、[[Pipeline-Parallelism]]、[[Expert-Parallelism]]、[[MoE]]、[[Mixed-Precision-Training]]
- **同类系统**：GEMINI（in-memory ckpt）、CheckFreq、ServerlessLLM 训练侧、PyTorch native ckpt
- **同会议**：[[FAST-2026]]
