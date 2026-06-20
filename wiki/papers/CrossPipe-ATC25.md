---
type: paper
name: CrossPipe
full_title: "CrossPipe: Towards Optimal Pipeline Schedules for Cross-Datacenter Training"
authors: [Tiancheng Chen, Ales Kubicek, Langwen Huang, Torsten Hoefler]
venue: ATC
year: 2025
tags: [llm-training, pipeline-parallelism, cross-datacenter, scheduling, distributed-training, performance-modeling]
source_pdf: "[[atc2025-chen-tiancheng.pdf]]"
source_md: "[[atc2025-chen-tiancheng]]"
---

# CrossPipe: Towards Optimal Pipeline Schedules for Cross-Datacenter Training (ATC 2025)

> **一句话总结**：CrossPipe 的核心观察是跨数据中心训练里静态 [[Pipeline-Parallelism]] 调度会把 latency/bandwidth delay 沿关键路径放大成 pipeline bubble；它把 compute、PP send/recv 和可 overlap 的 [[Data-Parallelism]] 通信统一建模成 latency + bandwidth-aware 调度问题，并用 solver 或 greedy 生成动态 schedule，在相同显存预算下最高比传统 pipeline schedule 减少 33.6% 训练时间。

## 问题与动机

论文讨论的是 LLM pre-training 继续横向扩展时的一个现实约束：单个数据中心的 GPU、电力和基础设施容量越来越难独立承载训练任务，而跨区域抢占 GPU 或多数据中心分摊电力会把训练放到更差的网络条件下。作者列举的环境从 same-campus cluster 到 cross-region cloud 差异很大，latency 可从 10 us 到 30-100 ms，bandwidth 可从 800 Gb/s 到 1.4-5.0 Gb/s。

现有分布式训练通常把 [[Tensor-Parallelism]]、[[Pipeline-Parallelism]]、[[Data-Parallelism]]、sequence parallelism、[[Expert-Parallelism]] 等组合起来用，但不是每个 parallel dimension 都适合跨 DC。TP/SP/EP 有高频或高容量 collective；DP 要同步整模型梯度或 optimizer 相关状态；PP 只在 stage 边界发送 activation/gradient，因此成为跨 DC 维度的主要候选。

CrossPipe 的问题不是重新发明训练系统，而是问：如果跨 DC 的通信 delay 已经不可忽略，传统为单 DC 设计的 hand-tuned pipeline schedule 还能不能保持 bubble 小？作者的回答是否定的：1F1B、interleaved 1F1B、ZB-H1、ZBV 等静态 schedule 的执行顺序默认通信很快；一旦跨 DC delay 进入关键路径，bubble 会按 microbatch 数累积，Megatron-LM 风格的 grouped send/recv 还会额外引入同步等待。

因此论文的中心 claim 是：跨 DC training 需要把网络 delay 作为 first-class scheduling constraint，而不是把单 DC schedule 直接搬过去。CrossPipe 同时提供模型、算法和执行引擎，使 schedule 能随 PP size、memory budget、latency、bandwidth、DP overlap opportunity 改变。

## 关键观察 / 隐含假设

- **观察 1：跨 DC 维度优先选 PP，而不是 TP/SP/EP 或纯 DP。** 论文用通信形态支撑这个判断：TP/SP/EP 的 per-layer collective 对 latency 和 bandwidth 都敏感；DP 的跨 DC 通信量与参数量 N 相关；PP 的跨 DC 通信量主要与 sequence length、hidden dimension 和 DP size 相关。Llama 3 405B 的仿真里，cross-DC PP 在 4 GB/s 跨 DC bandwidth 下最多比 cross-DC DP 快 3.05x，64 GB/s 下相对 ideal single-DC 约 1.3x slowdown。
  - **依赖假设**：模型是层序列结构，stage boundary activation/gradient 的代价小于跨 DC 同步大规模参数/梯度；跨 DC DP 的 collective overlap 或压缩没有强到改变主导瓶颈。
  - **可能失效场景**：模型很小、per-stage compute time 很短、sequence/activation 很大、DP compression/local SGD 可接受、或跨 DC bandwidth 高到 DP 通信不再主导时，PP 的优势可能缩小。论文自己也显示 bandwidth 超过 1024 GB/s 后 PP/DP 差距趋近于无。

- **观察 2：静态 pipeline schedule 的关键路径会放大跨 DC delay。** 论文指出 1F1B 在 2 DC 情况下存在包含 O(n_mb) 次跨 DC PP communication 的关键路径，Figure 6 和 Appendix C 用 bubble strides 展示 delay 沿 schedule 累积。Figure 8 中，Loop schedule 因每个 microbatch 跨 DC communication 更多，对 delay 最敏感；UD schedule 在高 delay 下反而更稳。
  - **依赖假设**：pipeline block 执行顺序主要由静态 schedule 决定，且 send/recv 的到达时间不能被底层通信系统自动重排到足以消除 bubble。
  - **可能失效场景**：如果底层 runtime 有真正 delay-aware 的 one-sided communication、message reordering、或充足异步 buffer，静态 schedule 的损失可能下降。但论文在 NCCL rendezvous 语义下观察到 receiver 未及时 post receive 会阻塞 sender，这正是 CrossPipe execution engine 要处理的实现层问题。

- **观察 3：大模型跨 DC PP 中 bandwidth 往往比 latency 更难隐藏。** 在 Llama 3 405B 仿真中，4-128 ms latency 对 runtime 影响较小，因为 per-stage forward time TF 约 109 ms，latency ratio 不高；但 bandwidth 明显影响 PP/DP 差距和 PP slowdown。Figure 11/表 5 也显示，当 T_bw/TF = 2 时，dynamic schedule 仍有明显 bubble，额外 GBS/memory 才能进一步缓解。
  - **依赖假设**：alpha-beta model 足以描述跨 DC link 的主要代价，且通信 control message 不在 critical path 上。论文的 bandwidth occupancy model 假设消息完成后可用 range-based 窗口近似链路排队。
  - **可能失效场景**：真实 WAN 的 congestion、packet loss、route change、multi-tenant traffic、transport retransmission 或控制面握手如果进入 critical path，alpha-beta 加简单 occupancy 的预测会偏乐观。

- **观察 4：额外 activation memory 和更大的 GBS 可以转化为更好的 schedule slack。** 表 5 中，M70 2-DC 下在高 latency 场景 (T_lat/TF, T_bw/TF) = (2, 0.25)，Case 3 的 CrossWave 达到 0.115 s/microbatch，接近无 delay 情况；在 bandwidth-heavy 场景 (2, 2)，CrossUD 从 Case 1 的 0.196 s/microbatch 改善到 Case 3 的 0.147 s/microbatch。
  - **依赖假设**：训练允许更大的 global batch size 或更多 in-flight microbatch，且设备有足够 activation memory；schedule 改变不会引入不可接受的 convergence 或 optimizer 调参成本。
  - **可能失效场景**：如果 batch size 被收敛性、数据并行 shard、显存或 activation recomputation 开销限制，CrossPipe 可利用的调度自由度会减少。论文也发现 2-DC 下 layer-wise recomputation 对 dynamic schedule 通常不能改善 runtime，因为 backward recomputation 抵消了内存收益。

- **假设 1：跨 DC 数量较小且 DC 内部相对同质。**
  - **证据强度**：中。论文显式假设 n_DC <= 4，并主要在 homogeneous GPUs/nodes 上评估；讨论部分说明 formulation 支持 stage-specific 参数，但 heterogeneous DC 的 layer assignment 和 failure behavior 没有实测。

- **假设 2：profiling 得到的 F/D/W runtime、memory 和 alpha/beta 在一个 schedule 生命周期内足够稳定。**
  - **证据强度**：中偏弱。论文提供 schedule hot-switching 和 periodic reprofiling 思路，但主评估使用受控 injection，不能完全覆盖真实跨区域网络分钟级变化、拥塞和故障。

## 核心方法

CrossPipe 先把 pipeline execution 拆成统一的 dependency graph。每个 pipeline stage 上的 compute block 包括 F、DGrad(D) 和 WGrad(W)，其中 D/W split 借鉴 zero-bubble pipeline 的细粒度调度思想。PP 的 activation/gradient send/recv 和可能 overlap 的 DP communication 也被建成 operation，而不是隐藏在 compute block 之外。

性能模型使用 alpha-beta communication model：alpha 表示 latency，beta 表示 bandwidth inverse；多个 pending message 会产生 bandwidth occupancy 和 queueing delay。block 的 start time 取决于同 stage 上一个 block 完成时间，以及数据依赖 block 完成加通信 delay 之后的到达时间。这个模型直接回应观察 2 和观察 3：通信 delay 不再是事后加的常数，而是能改变 critical path 和 schedule order 的约束。

solver-based optimal schedule 把问题写成 constraint optimization：每个 compute/communication operation 有 start time；共享 device 或 link 的 operation 通过 order variable 保证 non-overlap；数据依赖、microbatch order、device memory capacity 都进入约束；目标是 minimize makespan。DP overlap 也被纳入模型：vanilla DP 的通信在最后一个 microbatch 的 W block 后触发，[[ZeRO]] stage 1 的 Allgather 需要排在每个 model chunk 第一个 F block 前。

由于 solver search space 会随 PP stage 数量快速膨胀，CrossPipe 还给出 greedy schedule generator。greedy 的关键工程折中是把 F/D/W block 切成 n_sub 个 sub-block，让局部决策有更细粒度的填 bubble 能力。调度循环每次选择 earliest schedulable stage，再按阶段 heuristic 选 operation：warm-up 优先 F，steady phase 交错 F/D，tear-down 优先 D 而不是 W；当 memory constraint 阻止继续放 F/D 时才调度 W。bandwidth occupancy 用 range-based 模型找下一个可用传输窗口。

执行层是 CrossPipe 的另一个实质贡献。它不是只输出 schedule 图，而是在 Megatron-LM 训练框架里加入 CrossPipe module：先轻量 profiling 收集 F/D/W runtime、memory、PP communication alpha/beta；生成 static/dynamic candidate schedule；用性能模型选择最优；再 lower 成 concrete execution plan。执行计划把 block scheduling 和 communication arrangement 解耦，PP communication 使用非阻塞操作和多个 GPU streams 分方向/角色拆开：{Send, Recv} x {Next, Prev}，并提前 post Recv 以匹配 delayed Sends，减少 NCCL rendezvous 导致的 sender wait 和 deadlock risk。

实现评估中，作者还扩展 PyTorch ProcessGroupNCCL 做 latency/bandwidth injection，用单一 homogeneous cluster 模拟跨 DC link。latency 在 receiver wait 路径注入，bandwidth 通过在 communication stream 上插入 spin kernel 节流。这个机制让评估可控，但也把真实网络问题抽象成模型里的 alpha/beta delay。

## 设计取舍

- **把通信作为 first-class operation，换取 schedule 可解释性和优化空间。** 好处是 PP、DP overlap、link contention、memory budget 都能进同一个模型；代价是系统必须相信 profiling 和 communication model，真实网络偏离越大，schedule 越可能错配。

- **solver 给理论上更强的 schedule，greedy 给生产可用性。** CO solver 适合静态或慢变化配置，可用于生成 optimal/near-optimal reference；greedy 放弃全局最优证明，换来更快响应 dynamic system condition。论文用 CrossUDSub 接近 CrossUD 的实验证明 greedy 足够好，但没有给出形式化 worst-case bound。

- **跨 DC PP 降低跨域通信体积，但把训练 step 的关键路径跨越多个故障域。** CrossPipe 保持同步 training semantics，避免异步训练的收敛问题；但任何跨 DC link 抖动、node failure 或 checkpoint/recovery 成本都会直接影响 step time。论文把 node failure 交给 higher-level checkpointing，没有在 schedule 层闭环解决。

- **用更多 GBS/memory 换更小 bubble。** 这符合系统优化直觉，也在表 5/6 中有效；但 larger GBS 是训练算法参数，不只是系统参数。论文没有评估扩大 GBS 后的收敛、样本效率或 optimizer retuning。

- **用 delay injection 换可控实验。** 这种方法可以隔离 latency/bandwidth 两个变量，并验证性能模型；但它不能覆盖真实 cross-region cloud 的 congestion control、共享链路、路由变化、丢包和价格模型。

## 实验与结果

- **schedule sensitivity 仿真**：4 stages、8 microbatches、2 DC 情况下，WGrad-split schedule 普遍优于 unified backward，因为粒度更细；Wave schedule 在低 delay 下效率好，UD schedule 在 delay 增大后更稳；Loop schedule 因每个 microbatch 跨 DC communication 更多而最敏感。CrossUDSub 在多数 delay regime 接近 solver-based CrossUD。

- **cross-DC PP vs DP 仿真**：Llama 3 405B、2 DC 设置中，latency 4-128 ms 对 runtime 影响相对小，bandwidth 是主导因素。cross-DC PP 在 4 GB/s bandwidth 下最多比 cross-DC DP 快 3.05x；64 GB/s 下 cross-DC PP 相比 ideal single-DC 约 1.3x slowdown；bandwidth 超过 1024 GB/s 后 PP/DP 差距变小。

- **Alps/GH200 emulation 主评估**：作者在 Alps supercomputer 上用 GH200 节点评估 M8 和 M70 两类 Llama-style 模型，测试 1F1B、IV1F1B、ZBH1、ZBV、CrossUD、CrossUDSub、CrossWave。延迟和带宽 delay ratio 取 0、0.5、1、2；dynamic schedule 使用和对应 static base schedule 相同 peak memory budget。

- **主收益数字**：Figure 11 中，CrossPipe schedules 相比原始 static schedule 最多减少 33.6% runtime，相比加入 delay-aware communication orchestration 的 optimized static schedule 最多减少 21.9%，该结果出现在 M70、T_bw/TF = 2 的配置。

- **现实映射**：以 M70、n_DP = 16 为例，PP message size 约 1 GB，TF = 0.038 s；实验 delay ratio 对应 19-76 ms latency 和 105-421 Gb/s simulated bandwidth。这个范围更像高端 cross-campus 或高带宽专线，而不是最差 cross-region public cloud。

- **进一步 bubble reduction**：表 5 的 2-DC M70 结果表明，增大 GBS 和 memory budget 后 dynamic schedule 能进一步填 bubble；高 latency 场景下 CrossWave 可以接近 no-delay runtime，高 bandwidth-delay 场景下 CrossUD 从 0.196 s/microbatch 改善到 0.147 s/microbatch。bandwidth delay 比 latency delay 更难隐藏。

- **4 DC 扩展**：表 6 显示 4 homogeneous DC 下 CrossPipe 仍优于 static schedule；在 (T_lat/TF, T_bw/TF) = (2, 2)、Case 3 中 CrossUD 达到 0.178 s/microbatch，相比对应 2-DC 场景慢 22.8%。4-DC 下 bubble 更大，layer-wise recomputation 反而比 2-DC 更有帮助。

- **PP/DP 配比 trade-off**：固定总 node 数和 GBS，把 n_PP x n_DP 固定后测试 n_PP = 4/8/16。Figure 12 显示 schedule efficiency 对 PP/DP 切分相对不敏感，作者解释为 CrossPipe 能用足 memory 和 GBS 的自由度，同时较大 n_PP 降低每次通信体积但提高通信频率。

## Critical Analysis

### 论证链条

论文的主链条是闭合的：跨 DC link 有 latency/bandwidth delay -> 静态 PP schedule 的关键路径会积累 delay -> 把 communication 加入 scheduling model 可以重排 block 并减少 bubble -> execution engine 需要避免 grouped send/recv 和 rendezvous 同步把模型假设打破 -> controlled implementation evaluation 证明 runtime 改善。

最强的部分是作者没有只停留在算法仿真，而是把 schedule lowering、NCCL stream 拆分、Recv/Sends 对齐、delay injection 都做进系统里，证明“调度模型”和“训练 runtime”之间不是断开的。33.6%/21.9% 的收益也区分了原始 static baseline 和 communication-arrangement optimized static baseline，避免把所有收益都归功于 schedule generation。

主要跳步在“cross-datacenter production”外推。真实跨 DC 网络不是固定 alpha/beta，加上训练作业往往还要考虑 checkpoint、failure recovery、cloud pricing、数据放置、安全隔离和多租户 contention。CrossPipe 的模型抓住了 pipeline scheduling 的核心变量，但离完整 geo-distributed training stack 还有距离。

### 假设压力测试

如果跨 DC 环境是 same-campus 或低 delay、高 bandwidth，CrossPipe 仍能接近 static schedule，但收益有限；此时系统复杂度是否值得，要看是否已经有统一 schedule engine。论文的结果也显示 no-delay 下 ZBV 这类手工 schedule 很强，CrossPipe 主要价值来自 delay-aware adaptation。

如果环境是低 bandwidth public cloud cross-region，论文的 M70 主实验映射到 105-421 Gb/s，可能比真实 cloud cross-region 1.4-5.0 Gb/s 乐观很多。Section 5 的仿真覆盖到 4 GB/s 量级，但真正把 Megatron-LM 跑在这种 WAN 上的系统开销、稳定性和价格没有被证明。

如果模型是 [[MoE]]，论文认为 DP communication volume 会因 expert MLP 放大而更偏向 PP，这个方向合理；但 EP 本身的 dynamic Alltoall 不适合跨 DC，MoE 的 routing skew、expert imbalance 与 CrossPipe schedule 之间是否会互相影响，论文没有展开。

如果 batch size 不能随意增大，CrossPipe 在表 5/6 中通过 GBS/memory 换 bubble reduction 的部分收益会变脆。尤其是 pre-training 的最终指标不只看 seconds/iteration，还要看 tokens-to-quality 和 optimizer stability；论文默认系统层 runtime 改善不会被训练动力学抵消。

### 实验可信度

baseline 覆盖了 1F1B、IV1F1B、ZBH1、ZBV 等主流 pipeline schedule，并且单独评估了 delay-aware communication orchestration 的优化版本，比较较为扎实。M8/M70、2 DC/4 DC、latency/bandwidth sweep、memory/GBS case study 也覆盖了 schedule 本身的主要参数。

不足是主系统实验基于 single-cluster injection，而不是真实 WAN。delay injection 的 validation 证明注入机制接近目标 delay，但不能证明真实网络里的 jitter、packet loss、route change、multi-flow fairness 和 congestion control 对 schedule 没有额外影响。论文讨论了 network dynamics 和 hot-switching，但没有展示长时间训练 trace。

另一个边界是 workload 以 Llama-style dense Transformer 为主。虽然表 2 和讨论涉及 Mixtral、DeepSeek V3 等 MoE model，但主评估没有真正跑 MoE training，也没有评估 expert routing 造成的通信动态性。

### 系统性缺陷

CrossPipe 的工程复杂度集中在两处：调度器需要准确建模 compute/memory/communication，执行引擎需要把 schedule 正确 lower 到异步 NCCL 操作而不死锁。论文给出四个 stream、Recv reorder 和提前 post receive 的方案，但这类 runtime 一旦和 activation recomputation、gradient clipping、mixed precision anomaly detection、checkpoint、fault recovery 组合，调试复杂度会上升。

资源隔离和多租户方面论文基本未讨论。跨 DC link 通常不是训练作业独占，保守估计 alpha/beta 可以抗短期 spike，但如果其他业务造成持续拥塞，schedule hot-switching 的频率、稳定性和 overhead 都需要实测。

故障恢复没有纳入 CrossPipe 的核心抽象。同步 PP 横跨多个 DC 后，一个 node 或 link failure 可能让整条 pipeline 停住；论文把 node failure 交给 asynchronous checkpointing 或 in-memory checkpointing，但没有说明 schedule 与 checkpoint placement、restart granularity 如何协同。

可观测性方面，CrossPipe 需要知道 schedule 预测和真实执行哪里偏离。论文展示了性能模型大体能预测测试配置，但 production 系统还需要 per-link/per-stage attribution，才能判断是 profiling 过期、链路变差、某 stage straggler，还是 NCCL orchestration 问题。

## 局限与 Future Work

- **局限 1：真实跨 DC 网络验证不足。** 主系统实验通过 GH200 cluster 上的 delay injection 实现，适合隔离变量，但还没有证明在真实 cross-campus/cross-region WAN 上面对 jitter、loss、congestion 和 multi-tenant traffic 时仍稳定。

- **局限 2：heterogeneous DC 只做了设计讨论。** CrossPipe 支持 stage-specific 参数，但没有实测不同 GPU generation、不同 memory capacity、不同 intra-DC topology 下的 layer assignment 和 schedule quality。

- **局限 3：训练收敛影响未覆盖。** 增大 GBS、增加 in-flight microbatch、改变 recomputation 策略都可能影响 optimizer setting 或 convergence；论文主要报告 runtime，没有报告 tokens-to-quality。

- **局限 4：failure recovery 不在调度闭环内。** 跨 DC training 的可用性依赖 checkpoint/restart，但 CrossPipe 的 schedule optimization 没有把 checkpoint interval、state placement、recovery time 纳入目标函数。

- **Future work 1：真实 WAN trace replay。** 用实际 cross-region/cross-campus latency、bandwidth、loss、congestion trace 驱动 CrossPipe profiling 和 hot-switching，比较 predicted makespan 与真实 step time 的误差。

- **Future work 2：heterogeneous layer assignment + scheduling 联合优化。** 把不同 DC 的 GPU speed、memory、network link 和 failure rate 纳入同一个 optimization，客观指标可以是 step time、memory headroom 和 predicted recovery cost。

- **Future work 3：schedule-aware fault tolerance。** 让 pipeline stage placement、checkpoint placement 和 schedule generation 一起优化，评估 link/node failure 下的 lost work、restart time 和 steady-state overhead。

- **Future work 4：训练质量约束下的 GBS/memory trade-off。** 在固定 target loss 或 validation metric 下比较 Case 1/2/3，而不只比较 seconds per microbatch，验证系统层 bubble reduction 是否真的转化为 end-to-end time-to-quality 改善。

## 相关

- **相关概念**：[[Pipeline-Parallelism]]、[[Data-Parallelism]]、[[Tensor-Parallelism]]、[[Expert-Parallelism]]、[[MoE]]、[[RDMA]]、[[ZeRO]]、[[1F1B]]、[[Zero-Bubble-Pipeline]]、[[Cross-Datacenter-Training]]
- **同类系统**：[[Megatron-LM]]、[[Varuna]]、[[Oobleck]]、[[SWARM]]、[[DiLoCo]]
- **同会议**：[[ATC-2025]]
- **原始材料**：[[atc2025-chen-tiancheng]]、[[atc2025-chen-tiancheng.pdf]]
