---
type: paper
name: PopFetcher
full_title: "PopFetcher: Towards Accelerated Mixture-of-Experts Training Via Popularity Based Expert-Wise Prefetch"
authors: [Junyi Zhang, Chuanhu Ma, Xiong Wang, Yuntao Nie, Yuqing Li, et al.]
venue: ATC
year: 2025
tags: [moe, expert-parallelism, prefetch, all-to-all, distributed-training]
source_pdf: "[[atc2025-zhang-junyi.pdf]]"
source_md: "[[atc2025-zhang-junyi]]"
---

# PopFetcher: Towards Accelerated Mixture-of-Experts Training Via Popularity Based Expert-Wise Prefetch (ATC 2025)

> **一句话总结**：观察到 [[MoE]] 专家选择在层间相关且训练中期趋于稳定，PopFetcher 用 sliding-window + 层间条件概率预测下一层 hot expert，在 [[Attention]] 等非 MoE 计算的空闲网络窗口异步 prefetch 专家，配合 hybrid push-pull 与 backward 阶段 All-to-All 优先调度，在 8–32 GPU 集群上相比 FasterMoE / Tutel / Megablocks 等 SOTA 将 per-iteration 训练时间缩短 15%–94.5%（Cluster B 最高 18.3×），并减少 13%–15% 的 token 传输量。

## 问题与动机

[[MoE]] 通过 gate 稀疏激活专家，使参数量可扩到万亿级而计算量仅次线性增长；但训练时必须用 [[Expert-Parallelism]] 把专家分布到多 GPU，每层 MoE 需要两次 [[All-to-All]]（token dispatch + result collect），且 hot expert 造成计算与通信双重倾斜。作者在 8-worker MoE-GPT 上测得 **All-to-All 占单层时间 56%–58%**，这是系统瓶颈而非次要开销。

已有路线各有硬伤。**FasterMoE** 把 partial expert shadow 到所有 worker，减少 token 传输，但周期性广播专家参数带来同步干扰。**Janus** 在训练开始前静态决定「拉专家到 token」还是「推 token 到专家」，当专家参数与 token 数据量相对大小变化时失效。**Tutel / Megablocks / DeepSpeed-MoE** 等主要优化 dispatch/combine 流水线或 kernel，并未把 expert scheduling 与 All-to-All 在时间上错开。更关键的是，现有 coarse-grained scheduling 往往与 All-to-All **并发执行**，scheduling 本身也会抢带宽。

PopFetcher 的核心问题是：能否利用 MoE block 内 **non-MoE 层（Attention 等）计算期间网络链路空闲** 的窗口，提前为下一层 MoE 拉取热门专家，从而在不打断当前层 All-to-All 的前提下减少未来 token dispatch 量，并分摊 hot expert 负载？

## 关键观察 / 隐含假设

- **观察 1：专家 token 分布高度偏斜，且训练早期波动后趋于稳定。** Figure 3 显示 MoE-GPT 单层内少数 expert 持续接收更多 token；frontier layer 偏斜更明显，deep layer 更平稳。hot expert 直接放大 All-to-All 同步等待。
  - **依赖假设**：gate routing 在足够多 iteration 后呈现可预测的 temporal locality，而非每步剧烈重排。
  - **可能失效场景**：强负载均衡 gate（GShard loss、expert-choice routing）、课程学习、数据分布突变、或 fine-tuning 阶段 routing 重排，都会削弱「历史即未来」的假设。

- **观察 2：相邻 MoE 层之间存在可度量的专家选择相关性。** 给定第 \(i\) 层选中 expert \(x\)，下一层选中 \(x'\) 的条件概率 \(\Pr(E^{h,j+1}|E^{i,j})\) 并非均匀（Figure 6）；结合当前层 sliding-window 热度 \(p_{\mathrm{seq}}^{i,j}\)，可预测下一层 popularity。
  - **依赖假设**：层间相关结构在 prediction window（\(s=10\) iterations）内足够稳定；prediction 在 CPU 上异步完成，不阻塞 GPU forward。
  - **可能失效场景**：深层 MoE、更多 expert、不同 top-\(k\) gate、或 routing 策略改变时，GShard gate 的 top-5 预测准确率仅约 70%（Table 4），错 prefetch 会浪费显存与带宽。

- **观察 3：non-MoE 计算阶段网络空闲，而 expert prefetch 收益取决于 compute-to-bandwidth ratio。** 作者推导 prefetch 仅当 \(\varepsilon = P_w/W_{n,w} > 3\alpha H\) 时有净收益；在 DGX B200（高算力、相对有限跨机带宽）与消费者级 GPU + 低带宽集群（Cluster B 32Gbps）上该条件成立。H=1024、float32 下单 expert 约 16MB，每 token 跨机传输 2H，**token 数超过约 2048 时拉 expert 比推 token 更划算**。
  - **依赖假设**：GPU 算力相对跨 worker 网络带宽充足；non-MoE 层计算时间足以覆盖 expert 参数传输（Eq. 9 约束）。
  - **可能失效场景**：NVLink 全互联、超高速 fabric、或 non-MoE 层极短（小 batch、极浅模型）时，prefetch 窗口消失；专家参数量随 \(H\) 增长，临界点会上移。

- **假设 1：prefetch 的 expert 副本只需在 backward 时做额外 All-Reduce 同步梯度，不改变 forward 的 statistical training behavior。**
  - **证据强度**：中。Figure 10 显示 naive top-k 与 GShard gate 下 PopFetcher 与 FasterMoE 的 loss 曲线完全重合；但实验仅限 MoE-GPT/MoE-BERT、中小规模，未覆盖 production-scale MoE（如 DeepSeek、Switch Transformer 量级）。

- **假设 2：跨机异构拓扑可被显式利用——同机 NVLink ≫ PCIe ≫ GDR NIC，且 CPU memory 可作机内 expert 共享缓存。**
  - **证据强度**：中。设计合理（Figure 8 拓扑），但实验集群规模有限（最多 32 GPU），未验证数百/数千 GPU EP 下 cache 一致性与调度开销。

## 核心方法

PopFetcher 是 PyTorch 插件（8000+ LOC，可接 [[Megatron|Megatron-LM]]），在 [[Expert-Parallelism]] 之上维护每 worker 的 **expert pool**（本地专家 + prefetched 副本），由三模块协作：

**Routing Information Collector** 在 forward 中记录每层 gate 选择，维护 sliding window（\(s=10\)）内的 token 分配统计，并通过 `all_reduce` 同步 popularity 向量（开销可忽略）。热度预测分两步：式 (1) 得序列热度 \(p_{\mathrm{seq}}\)；式 (2)(3) 用层间条件概率传播到下一层 \(p(E^{h,j+1})\)。

**Prefetching Decision-Maker** 在 CPU 上异步运行，为即将到来的 MoE 层求解 prefetch 集合 \(\delta_{n,w}^i\)。目标是最小化式 (7) 的 end-to-end layer latency（max over workers）。搜索空间通过 **expert prefetch pruning** 从指数级降到 **≤ \(k \times N\)**（\(k\) 为 gate top-\(k\)，\(N\) 为 worker 数），并受 GPU 空闲显存（式 8）与 non-MoE 计算窗口（式 9）约束。只有满足式 (13) 的 expert 才被 prefetch；按 popularity 贪心填满显存。

**Hybrid push-pull**：对每个 expert-token 对，动态选择推 token 或拉 expert，而非 Janus 式的全局静态策略。prefetch 成功的 expert 在本地直接算 token，省去 dispatch；未 prefetch 的仍走常规 All-to-All。**机内 expert sharing**：server 级 CPU memory cache manager 避免同一 expert 被多台本地 GPU 重复从远端拉取；优先走高带宽链路（NVLink > PCIe > NIC）。

**Asynchronous Scheduling Executor** 在 Attention 等 non-MoE 计算时启动独立 prefetch stream（`torch.cuda.Stream`），与主计算重叠。Backward 阶段，prefetch 副本引入额外 expert gradient All-Reduce；PopFetcher 将 All-to-All、non-MoE All-Reduce、prefetched-expert All-Reduce 拆成 **micro-operation 流水线**，并 **优先 All-to-All stream**（Figure 9），减轻 backward 通信阻塞。

训练中后期 expert 热度进一步稳定，系统可降低 replan 频率或采用固定 prefetch 策略，减少决策开销（<100ms/iter，论文称可忽略）。

## 设计取舍

- **预测式 prefetch 换显存与梯度同步复杂度**：每份 prefetched expert 占用 \(2\alpha H^2\) 显存，backward 需把梯度回传 primary worker 做 reduction；收益是减少 All-to-All token 体积与 hot-worker 倾斜。显存紧时（Janus 式全量 pull 直接 OOM）只能 prefetch 少量 hot expert。
- **层间相关预测换实现简单性**：不做在线 RL 或全局最优 MILP 实时求解，而用 sliding window + 条件概率 + 贪心 pruning；实现轻量，但 GShard gate 预测准确率低于 naive top-k（69.6% vs 77% @ s=10）。
- **与 All-to-All 时间错开换系统侵入性**：需要自定义 `torch.autograd.Function` MoE operator，封装 forward/backward 的计算、通信、prefetch 与 stream 调度；集成成本高于纯通信库 patch。
- **边界条件**：在 **带宽受限、算力相对充足** 的集群（Cluster B：32×A10、32Gbps）收益最大；在 **高带宽、低 compute-to-bandwidth ratio** 环境，式 (12) 可能不满足，prefetch 净收益变小甚至为负。论文未讨论 **inference / serving** 场景——serving 的 batch 与 routing 分布可能与 training 不同。

## 实验与结果

- **硬件**：Cluster A（2 机×4 RTX 4090，100Gbps IB）；Cluster B（8 机×4 A10，32Gbps 跨机）。PyTorch 2.3 + NCCL。
- **模型 / 数据**：MoE-GPT、MoE-BERT（12 层，H=1024，α=2）；OpenWebText / PILE / OSCAR-2201。配置见 Table 3（8–32 worker，16–64 experts/layer）。
- **主结果**：相对各 baseline 最慢者，PopFetcher 在 Cluster A 上 **1.28–2.4×**，Cluster B 上 **1.18–18.3×** per-iteration 加速；摘要级 claim 为训练时间减少 **15%–94.5%**。Janus 复现（prefetch all experts）常 OOM，未纳入 Figure 11。
- **统计等价性**：naive top-k 与 GShard gate 下 loss 曲线与 FasterMoE 完全对齐（Figure 10）。
- **Ablation — popularity vs random prefetch**：MoE-GPT **1.30×**、MoE-BERT **1.26×** 于随机 prefetch。
- **Ablation — stream scheduling**：iteration time 再降 **10.9%**（GPT）、**10%**（BERT）。
- **通信量**：全局 prefetch 使 All-to-All token 传输减少 **14.85%**（GPT）、**13.46%**（BERT）。
- **负载均衡**：最轻/最重 worker 收 token 数差距缩小 **43.1%**（GPT）、**57.1%**（BERT）。
- **显存效率**：最大可训练规模 MoE-GPT **2.071B**（FasterMoE 1.844B，Janus 1.390B）；MoE-BERT **2.262B**（FasterMoE 1.884B）。
- **预测参数**：sliding window \(s=10\) 在准确率与内存间最优；naive top-k top-5 准确率约 77%，GShard 约 70%。

## Critical Analysis

### 论证链条

论文链条清晰：**测量**（All-to-All 占 50%–60%、hot expert、层间相关）→ **机会**（non-MoE 空闲链路）→ **设计**（predict + prefetch + hybrid push-pull + stream priority）→ **结果**（多 baseline、多集群加速）。ablation 分别验证了 popularity prediction 与 backward stream scheduling 的独立贡献，token 传输量与负载均衡数字支撑「减少 dispatch + 分摊 hot load」的机制叙述。

薄弱处在于 **「全局最优 prefetch」表述偏强**：实际求解是 pruning + popularity 贪心，并非对每个 iteration 解完整 MILP；大规模下 \(k \times N\) 仍可能不小，且论文承认中后期可用固定策略，说明在线最优求解并非必要。另一个跳步是把 Cluster B 上相对 Megablocks 的 **18.3×** 外推为「带宽受限环境普适」——Megablocks 本身极度依赖跨机通信，对比可能放大差距，而非对所有 MoE 训练栈的普适加速比。

### 假设压力测试

**Routing 稳定性**是最脆假设。Table 4 显示 GShard gate 的 top-5 预测准确率仅约 70%，且窗口增大反而下降；若生产训练使用更强 load-balance loss、expert dropout、或数据混合比例频繁变化，「bad prefetch」频率会上升。论文称 bad prefetch 可退回常规模式且 overhead 重叠在 non-MoE 阶段，但 **错误 prefetch 仍消耗显存槽位**，挤占真正 hot expert 的位置——这一交互未量化。

**Scale 外推**存疑。实验最多 32 GPU、64 experts/layer，距离论文引用的 256 GPU × 128 experts/worker（Azure 设定）差两个数量级。popularity `all_reduce` 虽轻量，但 prefetch 决策与机内 CPU cache 的一致性、跨 rack 拓扑、以及与 [[Tensor-Parallelism]] / [[Pipeline-Parallelism]] 混部时的 stream 干扰，均未被验证。

**Baseline 公平性**：Janus 无开源，作者用「prefetch all experts」复现，导致 OOM Excluded——这合理但削弱了与 data-centric 路线的直接对比。未与最新 MoE 训练栈（如 [[MoEBlaze-MLSys26|MoEBlaze]]、TurboMoE、DeepSeek 生产训练框架）比较。

### 实验可信度

**可信之处**：双集群、双模型、多 expert 规模；统计等价性实验打消正确性疑虑；ablation 与 token 传输、负载均衡指标形成交叉验证；runtime overhead 有量级估计（<100ms）。

**不足**：全是 **training throughput / iteration time**，未报告 **端到端 convergence time-to-target-loss**（虽 loss 曲线等价，但每 iter 更快是否线性转化为 wall-clock 训练完成尚未单独强调）。硬件为消费级/中端 GPU，与论文动机中的 frontier MoE（DeepSeek、Qwen、Phi）存在鸿沟。Workload 以语言模型 pretraining 为主，未覆盖 **MoE fine-tuning、多模态 MoE、expert parallelism + EP 混合** 等生产变体。

### 系统性缺陷

- **故障恢复 / 一致性**：prefetched expert 是 primary 的副本，论文未讨论 worker 宕机、partial prefetch、网络重传时的恢复策略与训练正确性。
- **尾延迟 / straggler**：优化目标基于 max worker latency 建模，但实验只报平均 iteration time，未给 per-iteration 尾延迟或 straggler 分布。
- **可观测性与运维**：8000 LOC 自定义 MoE operator + 多 CUDA stream，调试 prefetch 决策、诊断 bad prefetch、与现有 DeepSpeed/Megatron 配置共存的成本，论文未讨论。
- **与 inference 的割裂**：PopFetcher 针对 training；若同一集群混训推，prefetch 策略是否适用、是否影响 checkpoint 一致性，论文未涉及。
- **多租户 / 资源隔离**：论文未讨论。

## 局限与 Future Work

- **局限 1**：预测准确率有限，GShard gate 下 top-5 仅约 70%。Future work：在线监测 prefetch hit rate，对低置信度层退化为 push-only 或缩短 window，并量化 bad prefetch 的 opportunity cost。
- **局限 2**：规模限于 ≤32 GPU。Future work：在 128–1024 GPU EP 上测量 popularity 同步、CPU 决策、机内 cache 命中率与 NCCL stream 干扰，验证 \(k \times N\) pruning 是否仍足够。
- **局限 3**：仅 MoE-GPT / MoE-BERT，未覆盖 SwiGLU、更大 \(H\)、更多 top-\(k\)、或与 TP/PP 混部。Future work：用 DeepSeek-V3 / Qwen-MoE 等真实配置 replay routing trace，检验层间相关是否仍成立。
- **局限 4**：Janus baseline 为复现近似。Future work：与开源 MoE 通信优化（[[MoEBlaze-MLSys26|MoEBlaze]]、FlexMoE、EPLB 类 expert placement）做正交组合或 head-to-head，分离「少传 token」与「少做通信 op」的收益。
- **局限 5**：固定 \(s=10\) 窗口。Future work：按 layer depth、训练阶段自适应 window，或结合 recent work（如 expert load stabilizing prediction）做 drift detection。

## 相关

- **相关概念**：[[MoE]]、[[Expert-Parallelism]]、[[All-to-All]]、[[Attention]]、[[Tensor-Parallelism]]、[[Pipeline-Parallelism]]
- **同类系统**：[[FasterMoE]]、[[Janus]]、[[Tutel]]、Megablocks、DeepSpeed-MoE、FlexMoE、[[MoEBlaze-MLSys26|MoEBlaze]]
- **同会议**：[[ATC-2025]]
- **对比**：PopFetcher 用 **时间错开 + 热度预测 prefetch** 减 token dispatch；FasterMoE 用 **expert replication/shadow**；Janus 用 **静态 data-centric vs expert-centric 选择**