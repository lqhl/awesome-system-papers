---
type: paper
name: Tessera
full_title: "Tessera: A Holistic Pipeline Parallelism Framework for Trillion-Parameter Heterogeneous MoE Training (Operational Systems)"
authors: [Weifang Hu, Langshi Chen, Man Yuan, Youyang Yao, Xiulong Yuan, et al.]
venue: OSDI
year: 2026
tags: [distributed-training, mixture-of-experts, pipeline-parallelism, communication-overlap, load-balancing]
source_pdf: "[[osdi26-hu-weifang.pdf]]"
source_md: "[[osdi26-hu-weifang]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 面向万亿参数异构 MoE 训练的整体流水线并行框架（OSDI 2026）

> **原题**：Tessera: A Holistic Pipeline Parallelism Framework for Trillion-Parameter Heterogeneous MoE Training (Operational Systems)

> **一句话总结**：异构 MoE 中不同 layer pair 的通信重叠效率可相差 3×，且随机 token routing 会在静态计划之外产生气泡；Tessera 联合优化细粒度 overlap schedule 与 pipeline partition，并在运行时把可移动的 Wgrad 注入预测气泡，使 Qwen3/Qwen3-Next 在 4,096–12,288 GPUs 上 MFU 提升 20.0%–32.8%。

## 问题与动机

新一代 MoE 不再重复同一种 Transformer block：Qwen3-Next 混合 Gated DeltaNet、full [[Attention|attention]] 和极稀疏 MoE。传统 pipeline partition 按 layer 的串行 FLOPs 或 latency 平衡，但实际执行会跨 microbatch 重叠 compute、All-to-All 和 pipeline communication；同样串行成本的两个 stage，在 overlap 后可能形成完全不同的关键路径。先分区再套固定 overlap pattern 因而会重新造成 stage imbalance。

即使静态计划已最优，MoE router 每轮产生的 token distribution 仍会改变各 expert/rank 的工作量。在 10K+ GPU 上，小波动会放大为 local idle 和 remote wait bubble。论文要解决的是一个耦合问题：partition 决定哪些工作能够相遇，overlap schedule 决定它们的真实成本，而 routing variation 又使这个成本在运行时漂移。

## 关键观察 / 隐含假设

- **观察 1**：layer combination 与并行拓扑共同决定 post-overlap cost；仅按 serial cost 平衡会选错边界（§2、§3.1）。
  - **依赖假设**：在 reference device group 上 profile 的 overlap interference 能代表生产 mesh，并可跨相同 device-mesh class 复用。
- **观察 2**：异构 overlap pair 可统一表示为 compute/communication 两类资源上的 task DAG；backbone-first、gap-fit 和 conditional deferral 能在低成本下逼近 ILP（§3.1.2）。
  - **可能失效场景**：kernel duration 波动大、资源不止两类或 communication engine 相互干扰时，离线 DAG duration 会失真。
- **观察 3**：router metadata 在 bubble 真正出现前已可用；每个 [[Expert-Parallelism|EP]] group 只交换 per-expert token counts，足以预估 [[MoE|MoE]] boundary 后的 idle slot（§3.2.1）。
  - **依赖假设**：routing 是主要动态性来源，预测和调度能在 target slot 前完成。
- **观察 4**：Wgrad 等任务具有正 deadline slack，可延后但必须在 iteration end 前执行，天然构成 bubble-filling task pool（§3.2.2）。
  - **代价**：延长 activation/gradient lifetime，实测 peak memory 增加 2–4 个百分点。

## 核心方法

Tessera 的 static planner 先从固定 pipeline schedule template 构建 overlap graph：node 是 virtual stage，edge 表示同 rank 上可并发的两个 stage。每个 stage 在 baseline boundary 邻域产生若干连续 layer-range candidates。对每条 edge 的 candidate pair，系统把两个 chunk 展开成 task DAG，task 带 duration、resource type 和 dependency（§3.1.1）。

event-driven scheduler 在 compute/communication 空闲事件上选择任务。它优先保持关键 backbone 前进，再以 gap-fit 对齐另一资源；会延长 makespan 的 movable task 暂缓，最后以 best-fit 回填 residual slot。生成的 schedule 在匹配 [[Tensor-Parallelism|TP]]/EP topology 的 reference group 上实测，得到包含 hardware interference 的 post-overlap cost，并按 chunk/topology 缓存（算法 1、§3.1.2）。

partition selection 用 MILP 给每个 stage 选一个 candidate，以最大 selected-edge post-overlap cost 为 bottleneck objective，同时约束 layer 连续性、topology 和 memory。baseline cost 提供安全 upper bound，任何更慢 pair 可直接剪枝。最终 plan 同时包含 layer assignment 和每个 overlap pair 的细粒度 schedule（式 1、§3.1.3）。

Dynamic Bubble Optimizer（DBO）在运行时读取 EP 内 token counts，预测静态计划预标注位置的 fillable window。它从有 deadline slack 的 bounded movable-task pool 中，按 duration fit 和 deadline urgency 贪心选择任务；没有安全候选便留空，deadline 接近时强制执行以保证 correctness。slot sizing 和 selection 异步完成，开销少于 10 μs（算法 2、§3.2）。

实现为 [[Megatron|Megatron-LM]] 上的独立 library，约 11K Python + 2K C++。C++ plan-agnostic engine 用 lock-free FSM 协调 forward/backward Torch threads，background thread 执行 movable tasks；模型只需在可调度边界调用 probe API（§4）。

## 设计取舍

- **实测 profile 换准确性**：避免 analytical model 忽略 kernel/network interference，但依赖代表性硬件和离线 profiling。
- **bounded candidate neighborhood 换可解性**：MILP 不搜索任意 partition；若最优边界远离 baseline 会遗漏。
- **最大 edge cost 作为 surrogate**：简化 fixed-template steady-state 优化，但不直接最小化完整 warmup/cooldown critical path。
- **动态填洞而非重排全图**：DBO 只移动 deadline-safe task，保持 graph、operator semantics 和 reduction order不变，换来较小但低风险收益。
- **memory 换 throughput**：pool 越大越能填洞，也让更多 tensor 延长存活；容量需随 headroom 配置。

## 实验与结果

- 生产集群为 NVIDIA Hopper、8-GPU servers 与 [[RDMA|RoCE]]；主评测覆盖 Qwen3/Qwen3-Next、4,096–12,288 GPUs，并与已含 interleaved 1F1B/native overlap 的内部 Megatron-LM 比较（§6.1）。
- 五个生产 workload 的 MFU 提升 20.0%–32.8%；Qwen3-XL 在 8,192 GPUs 从 32.0% 到 39.0%，Qwen3-Next-XL 在 12,288 GPUs 从 15.9% 到 21.1%（表 2）。
- Qwen3-XL phased deployment 中 static plan 带来约 13% throughput，其中约 9% 来自 post-overlap load balance；启用 DBO 后 MFU 达 39.0%，且 deterministic run loss trajectory bit-identical（图 9、§6.2）。
- 256-GPU controlled comparison 上，相对 internal Megatron，Qwen3-235B、DeepSeek-V3、Nemotron-3 Super MFU 分别提高 1.27×、1.24×、1.13×；相对 recipe-tuned Megatron-Core，Qwen3-235B 提高 1.24×，另两者接近（图 11）。
- heuristic overlap scheduler 的 measured post-overlap cost 距 ILP 在 EP32/EP8 分别仅 1.07%/0.76%，而 ILP solving 全部实例需数小时至数天，heuristic 少于 1 分钟（图 13、§6.5）。
- DBO 使 baseline/overlap-aware partition iteration time 再降 5.4%/4.4%，peak memory 增 2–4 个百分点；6,144-GPU Qwen3-L 单独贡献 3.4% throughput（表 3、§6.6）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| partition 必须与 overlap schedule 联合优化 | 图 12 | Qwen3-Next、128/256 GPUs、DBO关闭 | 强 |
| 整体方案能在万卡生产训练稳定增益 | 表 2、图 9 | Alibaba Hopper/RoCE、Qwen3 family | 强 |
| scheduler 接近 ILP 且规划更快 | 图 13 | 536/690 overlap instances、EP8/EP32 | 强 |
| DBO 能利用 routing-induced bubble | 表 3、§6.6 | 256 GPUs ablation + 两个 production case | 强 |
| 可泛化到多种异构 MoE | 图 11 | 256 GPUs、三种公开模型 recipe | 中 |

## 批判性分析

### 论证链条

论文最有说服力之处是把“先平衡 serial layer cost”这一常规抽象直接推翻：图 12 显示无 overlap 时 Partition A 更好，启用 overlap 后 Partition B 反超。设计分别覆盖静态耦合与动态 routing variation，且 component ablation 与 production rollout 都能对上机制。

### 假设压力测试

profile reuse 假设 cluster 内 GPU/network behavior 足够稳定；拥塞、GPU degradation 或跨 job interference 会使 edge cost排序改变。candidate 只围绕既有 partition 扰动，对强非均匀模型可能困在局部范围。DBO主要以 token counts预测 bubble，若 host jitter、collective contention 或 data-dependent kernel是主因，预测能力会下降。

### 实验可信度

规模、持续生产部署、bitwise equivalence 和公开模型 controlled comparison 都很强。限制是最大规模 baseline 为内部 production stack，外部无法复现；Megatron-Core comparison 只有 256 GPUs，且非 Qwen workload只达到 comparable。论文报告 MFU/throughput，缺少不同网络拥塞、失败与长期 planner drift 的 sensitivity。

### 系统性缺陷

Tessera 没有消除 pipeline 固有 warmup/cooldown：较有利 case 仍有 17% iteration time 来自 exposed EP 与 PP idle。它也依赖显式 task boundary/probe 集成；新 operator、不同 autograd结构或多 communication resource 需要重新描述 DAG。MILP与profiling虽然不随 data-parallel replica 数增长，但新 model/topology 的部署前成本仍存在。

## 局限与后续工作

- **局限 1**：生产 baseline 与数据不可公开，万卡收益难独立复现。
- **局限 2**：static objective 聚焦 steady-state bottleneck edge，warmup/cooldown 仍占显著 residual gap。
- **局限 3**：profiling 对硬件、topology 与 software stack有绑定，运行时 drift 的自动重规划未展示。
- **后续工作 1**：加入 online cost calibration，在网络拥塞/GPU slowdown 注入下测 plan robustness 和重规划阈值。
- **后续工作 2**：把 warmup/cooldown critical path 纳入 joint solver，评估能否回收图 10 剩余 17% gap。
- **后续工作 3**：公开 planner trace、candidate/profile dataset 与小规模 reproducible recipe，验证跨 cluster transferability。

## 相关

- **相关概念**：[[Mixture-of-Experts]]、[[Pipeline-Parallelism]]、[[Communication-Computation-Overlap]]、[[Load-Balancing]]、[[Model-FLOPs-Utilization]]
- **相关系统**：[[Megatron-LM]]、[[DeepSeek-V3]]、[[Qwen3]]
- **同会议**：[[OSDI-2026]]
