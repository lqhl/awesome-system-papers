---
type: paper
name: Obscura
full_title: "Obscura: Concealing Recomputation Overhead in Training of Large Language Models with Bubble-filling Pipeline Transformation"
authors: [Yuzhou Huang, Yapeng Jiang, Zicong Hong, Wuhui Chen, Bin Wang, Weixi Zhu, Yue Yu, Zibin Zheng]
venue: ATC
year: 2025
tags: [llm-training, pipeline-parallelism, activation-recomputation, activation-swapping, memory-optimization, scheduling]
source_pdf: "[[atc2025-huang-yuzhou.pdf]]"
source_md: "[[atc2025-huang-yuzhou]]"
---

# Obscura: Concealing Recomputation Overhead in Training of Large Language Models with Bubble-filling Pipeline Transformation (ATC 2025)

> **一句话总结**：Obscura 的关键观察是 [[Pipeline-Parallelism|1F1B pipeline]] 早期 stage 的 recomputation 开销并不总在 critical path 上，backward bubbles 可以隐藏一部分开销而 forward bubbles 原本闲置；它把 forward bubbles 转成可用的 backward bubbles，并用 dependency relaxation、activation swapping-aware recomputation 和 partition adjustment 控制新增内存与负载不均，在 8xA100 上训练 18B-28B Llama-2/GPT-3 时相对 DAPPLE+ full recomputation 约提升 22%-33%，最高 1.33x。

## 问题与动机

LLM 训练常用 [[Pipeline-Parallelism|pipeline parallelism]] 把模型 layer 切到多个 GPU stage 上，micro-batch 沿 stage 流动以降低单卡显存需求。1F1B 相比 GPipe 更省 activation memory，因为 backward 更早开始并释放 activation；但它仍有一个结构性问题：越靠前的 stage 要在第一个 backward 前缓存越多 micro-batch activation，显存压力随 stage id 单调下降。论文在 Llama-2 13B/18B profile 中展示了这个不均衡，早期 stage 比后期 stage 高数十 GB，18B 已会在 stage 0 OOM。

直接用 [[Activation-Checkpointing|activation recomputation]] 可以把 activation 丢掉、backward 时重算，但全 stage full recomputation 会把每个 micro-batch 的 forward 代价再付一遍，训练时间明显拉长。选择性 recomputation 只重算 Norm、SiLU/GELU、Mul 这类 cost-effective operator，开销小但省内存有限；在更严格显存约束下，仍可能不得不重算 MLP 等高成本 activation。

Obscura 的问题定义不是“如何进一步减少 activation footprint”，而是“在必须 recompute 时，能不能把 recomputation 放进 pipeline 本来就存在的 idle bubbles 里”。这把内存优化问题转成了 schedule transformation 问题：如果 recomputation 开销可以被 bubble 吃掉，就可以用更少端到端时间换同样的显存安全。

作者的 claim 边界也要看清：Obscura 针对的是 dense Transformer LLM 的 pipeline training，在 1F1B 风格同步 schedule、固定 sequence length、micro-batch size 1、单节点 4-8 GPU 配置上验证。论文说它不增加 stage 间通信、因此可扩展到多节点，但主实验没有真正跑多节点训练。

## 关键观察 / 隐含假设

- **观察 1：OOM 集中在早期 pipeline stage，所以 on-demand recomputation 比 all-stage recomputation 更合理。** 论文把 recomputation 只施加到超内存 stage，4-stage profile 中 Recomp-0 和 Recomp-1 相比无 recomputation 的执行时间分别增加 19% 和 25%，而 Recomp-All 增加 33%。
  - **依赖假设**：显存压力主要来自 1F1B warmup 中早期 stage 的 activation 累积，而不是 optimizer state、参数 shard、通信 buffer 或 allocator fragmentation。
  - **可能失效场景**：如果使用 [[ZeRO]]/[[FSDP]]、sequence parallelism、uneven partition、interleaved virtual stages 或动态 batch packing 后，显存瓶颈不再集中在前几个 stage，on-demand 选择会变得不稳定。

- **观察 2：backward bubbles 可以隐藏一部分 recomputation，但 forward bubbles 在普通 1F1B 中用不上。** recomputation 发生在 backward 前，因此只能利用第一个 backward 之后的空档；而 1F1B 早期 stage 在第一个 backward 前存在更长的 forward bubbles。论文测到 stage 0 的 forward bubble time 可达 0.50s，高于 backward bubble 的 0.37s。
  - **依赖假设**：recomputation 的额外 forward 可以被重新排序而不改变 micro-batch 依赖，且 pipeline 中确实有足够 idle bubble 而不是已被 communication overlap 或 zero-bubble schedule 填满。
  - **可能失效场景**：如果 baseline 已采用 [[Zero-Bubble-Pipeline]]、interleaved 1F1B、或更激进的 comm/compute overlap，forward bubble 可转化空间会变小。

- **观察 3：forward-bubble-to-backward-bubble transformation 会引入新 activation pressure。** Strawman 把 adjusted stage 的 steady forward 左移到第一个 backward 前，确实能把 Recomp-0/1 的时间开销从 19%/25% 降到 8%/17%；但 warmup 存的 activation 更多，Table 1 中 adjusted stages 的显存接近甚至高于不重算的 1F1B。
  - **依赖假设**：额外 activation 可以通过 swapping 和更精细的 recomputation 策略压回显存上限内。
  - **可能失效场景**：CPU-GPU bandwidth 不足、host memory 争用、activation block 太大、或者 runtime 不允许可靠 overlap swap/load 时，转化出来的 bubble 可能被通信开销吃掉。

- **观察 4：能隐藏多少 recomputation 由最后一个 adjusted stage 决定。** 更靠前的 adjusted stage 有更多 bubble，但整体时间延长不能低于最后一个 adjusted stage 的延长；因此 adjusted stages 越多，Obscura 的 concealability 越差。
  - **依赖假设**：stage k 之后的 non-adjusted pipeline 是主要约束，且 stage 内 computation time 近似可由 forward/backward/recompute 三类 cost model 描述。
  - **可能失效场景**：stage 运行时间高度不均、跨 stage 通信不稳定、或模型 layer 不是规则 Transformer block 时，“最后 adjusted stage”可能不足以概括 critical path。

- **假设 1：cost-effective operator 的 activation/compute 比例稳定。**
  - **证据强度**：中。论文引用 CMB strategy，认为 RMSNorm、SiLU/GELU、Mul 等可减少约 40% footprint 且只带来 2%-3% overhead；这对 Llama-2/GPT-3 成立，但对不同 architecture、fused kernel、MoE 或 attention variant 需要重新 profile。

- **假设 2：少量 warmup iterations 的 profiling 足以生成长期可用 schedule。**
  - **证据强度**：中偏弱。Obscura Planner 离线跑几轮收集 operator time/memory，再求解/枚举配置；主实验是固定 sequence length 4096 和随机输入，不能证明动态长度或真实数据混合下 schedule 不漂移。

## 核心方法

Obscura 分成 offline planner 和 online runtime。Planner 先在原 1F1B schedule 上 profile 每个 stage 的 memory、operator activation size 和 compute time，识别超显存的 adjusted stages；Runtime 则在 [[DeepSpeed]] 上用自定义 scheduler 执行新 pipeline，NCCL send/recv 改为异步并配同步原语，activation swapping 放到独立 CUDA stream。

第一步是 strawman pipeline transformation。对每个 adjusted stage，Obscura 把原本 steady phase 中位于第一个 backward 之后的 forward passes 尽量左移到 forward bubbles 中。这样第一个 backward 之前的闲置时间被 forward work 填充，原 forward bubbles 被推到 backward 区间，变成可以隐藏 recomputation 的 backward bubbles。这个设计直接回应观察 2，但也制造了观察 3 的额外 activation footprint。

第二步是 dependency relaxation。Strawman 仍受相邻 stage 的 tight dependency 限制：stage s 的 backward 必须等 stage s+1 同 micro-batch backward 完成，导致某些 backward bubbles 只能隐藏相邻 recomputation，无法被后续 recomputation 使用。Obscura 把剩余 forward 左移、把 backward 右移，并像 1F1B 一样交错它们，让 stage 内 execution 不再紧贴相邻 stage 的原始顺序。随后 migration refinement 会减少不必要的 forward 左移：早期 adjusted stage 不必拥有比最后 adjusted stage 更多的 backward bubbles，因为多出来的 bubbles 不决定整体 critical path。

第三步是 swapping-aware recomputation。Obscura 把每个 micro-batch 的 activation 视为 activation block，在 warmup 做 eviction，在 steady 做 eviction-loading，在 ending 做 loading；用参数 `lambda` 表示 warmup 期间移出的 activation block 数，用 `beta` 表示每个 block 传输比例。Planner 同时枚举 swapping 配置和 recomputation operator set，把 execution time、memory limit、CPU-GPU bandwidth overlap 约束写成一个小规模 IP/枚举问题，目标是最小化 stage 0 makespan。直觉上，recompute 多会降低需要 swap 的数据但增加计算；swap 多会减少 recomputation 但可能被 PCIe/host memory 带宽拖慢。

第四步是 CMB-Identifying 和 partition adjustment。CMB-Identifying 在把某个 stage 标成 adjusted 前，先尝试只 recompute cost-effective operators；如果这样就能过显存限制，就避免把它纳入 adjusted set，从而保护最后 adjusted stage 位置和 bubble concealment 能力。partition adjustment 则把 Transformer layer 拆成 attention 和 MLP 两个更细粒度单元，从 adjusted stages 往 non-adjusted stages 迁移 layer，降低 adjusted side 的 `3f+r` 计算时间并填掉 non-adjusted side 的 idle bubbles。

这里有一个“简单但有用”的建模取舍：partition adjustment 近似忽略了它对 swapping-aware recomputation 和 concealment capacity 的反馈，只按当前模型迭代搬 layer。这牺牲了全局最优，但让实现复杂度保持可控，也符合论文的系统工程风格。

## 设计取舍

- **用 schedule 自由度换 recomputation 成本隐藏**：Obscura 不消灭 recomputation，而是把它移出 critical path；这在 bubble 充足时收益大，但在 bubble 已被更强 baseline 填满时收益自然收缩。
- **用 activation swapping 补 pipeline transformation 的显存副作用**：forward 左移会多存 activation，swapping 把显存压力转成 CPU-GPU 通信压力；如果 bandwidth 或 host memory 不是瓶颈，这个取舍成立，否则会把隐藏掉的 recomputation 换成显式通信等待。
- **用 offline planner 换 runtime 简单性**：几轮 profiling 后生成固定配置，online runtime 不做复杂动态决策；代价是对动态 sequence length、kernel runtime jitter、network contention 和 allocator 行为比较敏感。
- **用近似 partition adjustment 换工程可落地**：attention/MLP 半层粒度比整层更灵活，但算法没有联合优化 recomputation、swapping 和 partition；在非规则 block、MoE 或异构 GPU 上可能需要重新设计。
- **保持训练语义，增加调试复杂度**：Obscura 仍遵守 forward/backward dependency，不应改变数学训练语义；但异步 NCCL、手工内存管理和多 stream swapping 会让 deadlock、determinism、trace attribution、fault recovery 更难排查。
- **边界条件**：最适合 dense Transformer、规则 layer、固定序列长度、早期 stage 显存瓶颈明显、baseline 有未利用 pipeline bubble、CPU-GPU bandwidth 可被 overlap 的训练场景；最脆弱的是动态输入、跨节点拥塞、显存碎片严重、或已有 zero-bubble/overlap runtime 的场景。

## 实验与结果

- **实验环境**：主实验在单节点 8x NVIDIA A100-SXM-80GB，GPU 之间 NVLink 双向 P2P 带宽 600 GB/s，CPU 为双 Xeon Platinum 8352S、2 TB DRAM；另有 4x A800 PCIe 4.0、无 NVLink 的验证。
- **workload**：Llama-2 和 GPT-3 style dense Transformer，13B/18B/23B/28B，sequence length 4096，micro-batch size 1，global batch size 16/32/64 为主，敏感性分析到 128；输入是训练循环前生成的随机序列。
- **baselines**：DAPPLE 1F1B even partition、DAPPLE+ all-stage full recomputation、OHP-CMB cost-effective operator recomputation、BPipe activation balancing + selective recomputation，以及 Strawman full recomputation adjusted stages。
- **主性能**：13B 下 DAPPLE 不 OOM，Obscura/Strawman 不实际应用；18B-28B 下 DAPPLE OOM，Obscura 相对 DAPPLE+ 在 Llama-2 上提升 29%-31%（18B/23B）、22%-27%（28B），在 GPT-3 上提升 32%-33%（18B/23B）、30%-32%（28B），Figure 12 最高约 1.33x。
- **大 batch 极端点**：global batch size 64、28B 下，Llama-2 仍有约 22% speedup，GPT-3 约 30%；论文解释为 GPT-3 使用 GELU，比 Llama-2 的 SiLU 更适合 cost-effective recomputation。
- **显存分析**：Llama-2 28B、global batch size 32 中，DAPPLE 只有 stage 6/7 在 80GB 内，stage 0 约为 stage 7 的 2x；OHP-CMB 省约 40% activation 仍 OOM；BPipe 不加 MLP recomputation 时峰值约 106GB，加后约 76GB；Obscura 让 stage 0-4 贴近显存上限，stage 5 用 CMB，stage 6/7 类似 DAPPLE。
- **bubble/compute 分解**：Llama-2 23B、global batch size 32 中，DAPPLE+ 因 full recomputation 使 computation、bubble、total time 都比 DAPPLE 增约 1/3；Obscura adjusted stages 0-2 只比 DAPPLE 多 13% computation，adjusted stages 的 bubble time 比 DAPPLE 少约 1.7s，stage 2 仍保留 bubble，说明 recomputation 几乎被隐藏。
- **低 P2P bandwidth 验证**：4x A800 PCIe 无 NVLink 下，BPipe 在 10.4B 模型上因跨 stage activation transfer 比 DAPPLE 低 11%/17%；Obscura 不引入额外 inter-stage activation transfer，整体仍报告 27%-31% gains。
- **ablation/sensitivity**：Llama-2 23B、global batch 16/32/64/128 下，DR-only 在 batch 16 有 1.26x，但 batch 64/128 降到 1.11x/1.07x；加 SAR 后 batch 32/64/128 分别约 1.30x/1.28x/1.22x；再加 CB 在 batch 128 提到 1.24x，说明 swapping-aware recomputation 是主稳定器，partition adjustment 主要在大 batch 负载不均时补尾。

## Critical Analysis

### 论证链条

论文的核心链条比较闭合：1F1B 的内存瓶颈集中在 early stages -> on-demand recomputation 避免拖慢所有 stages -> backward bubbles 能隐藏部分 recomputation 而 forward bubbles 原本闲置 -> pipeline transformation 把 forward bubbles 变成 backward bubbles -> dependency relaxation 和 migration refinement 提高 bubble 利用率并避免无用左移 -> swapping-aware recomputation 与 partition adjustment 处理 transformation 带来的额外显存和负载不均 -> end-to-end throughput 提升。

最有价值的地方是它没有把 bubble 当成一个总量指标，而是区分 forward bubble/backward bubble 以及最后 adjusted stage 的 concealment capacity。这是一个可迁移的系统观察：不是所有 idle 都能隐藏任意 work，idle 的时间位置和依赖方向决定它是否可用。

主要跳步是从固定单节点实验外推到一般 LLM training stack。Obscura 证明了在 Llama-2/GPT-3 style dense Transformer、固定 sequence length、规则 layer partition 上，schedule transformation 可以吃掉 recomputation 开销；它还没有证明在 multi-node、dynamic workload、异构 GPU、MoE、packed variable-length sequence 或 production trace 下同样稳定。

### 假设压力测试

**workload assumption**：实验使用随机序列、固定 sequence length 4096、micro-batch size 1。真实训练常有 packing、curriculum、不同 corpus mixture、variable sequence length 和 occasional long documents；这些都会改变 activation size、operator runtime 和 pipeline imbalance。若 Obscura 的 offline plan 不重新生成，可能出现显存贴线或 bubble 预测失准。

**resource bottleneck assumption**：论文默认主瓶颈是 activation memory 与 recomputation compute，CPU-GPU swapping 可以被 overlap 到足够小。A800 实验说明 Obscura 比 BPipe 更不依赖 inter-GPU P2P，但它仍依赖 host memory/PCIe 路径；在共享节点或 PCIe 拓扑复杂的机器上，swap/load stream 可能和 dataloader、checkpoint、offload optimizer 或其他 jobs 竞争。

**hardware/deployment assumption**：主平台是 8xA100-SXM-80GB + NVLink，属于显存和带宽都很强的单机。未来 HBM 容量更大时，13B/18B 这类 OOM 场景可能消失，Obscura 的收益下降；反过来，模型/sequence/context 继续增大时 early-stage activation memory 仍会回来。论文缺的是不同 HBM 容量、PCIe generation、NVLink/NVSwitch、跨节点 IB 下的系统性 sweep。

**scaling assumption**：论文说 Obscura 不增加 inter-stage communication，因此可 seamless scale to multiple nodes。这个判断在通信量层面合理，但多节点会引入更高 latency、NCCL rendezvous 风险、跨节点 jitter、failure domain 和 profiling drift；主实验没有验证这些因素是否会破坏 bubble filling。

**correctness/SLO assumption**：Obscura 的 schedule 仍遵守 micro-batch data dependency，所以训练数学语义应保持；但论文没有深入讨论 determinism、loss equivalence、checkpoint/restart、OOM recovery、deadlock detection 或 observability。系统论文里这不一定推翻性能结果，但会影响生产可用性。

### 实验可信度

实验强项是比较对象覆盖了三个重要方向：all-stage full recomputation、cost-effective recomputation、activation balancing/swapping。Figure 14 的 computation/bubble decomposition 也很好地支撑了“收益来自隐藏 recomputation，而不是某个未解释的实现优化”。

但 baseline frontier 仍有边界。DAPPLE 是 1F1B 基线，DAPPLE+ 是强但朴素的 full recomputation；OHP-CMB 和 BPipe 是合理邻居，但没有直接对比 AdaPipe/zero-bubble/interleaved schedule 与 recomputation/offload 的组合。BPipe 在 23B/28B 上被迫加 MLP recomputation，这既是现实限制，也让 baseline 不是原始 BPipe。

13B 下 Obscura 不应用，因为 DAPPLE 本身不 OOM；这提醒我们 Obscura 是“显存约束下的训练加速”，不是无条件加速 pipeline training。论文对 18B-28B 的速度提升很清楚，但对于更大模型只是通过添加 layer 扩展，没有展示 70B/175B 级别真实模型配置。

另一个实验边界是 workload 真实性。随机输入足以测系统 runtime，但不能覆盖真实数据造成的 sequence length 分布、activation sparsity、kernel cache 行为或 dataloader/checkpoint 干扰。论文也没有报告长时间训练中的 planner stability、memory fragmentation 或偶发 OOM。

### 系统性缺陷

Obscura 的实现会把训练栈推向更精细的手工调度：custom scheduler、async NCCL、手动 memory management、separate CUDA stream swapping、operator-level profiling 和 IP/枚举 planner。性能收益来自这些部件配合，但任何一个部件漂移都可能很难定位。

资源隔离风险没有展开。activation swapping 使用 host DRAM 和 CPU-GPU bandwidth；在单作业独占节点上容易成立，在共享训练平台或同时启用 ZeRO-Offload/checkpoint/dataloader prefetch 时，host-side traffic 可能成为隐藏瓶颈。论文没有给出 bandwidth utilization trace 或 host memory pressure trace。

故障恢复和可观测性也基本缺席。pipeline schedule 改变后，某个 micro-batch 的 forward/recompute/backward 被分散到不同时间窗口；如果出现 hang、OOM、silent performance regression，需要能把事件映射回 adjusted stage、activation block、swap phase 和 recomputation strategy。论文的系统接口没有覆盖这一层。

最后，partition adjustment 的近似会在复杂模型上变脆。把 Transformer block 拆成 attention/MLP 足够服务 Llama-2/GPT-3；但 MoE、GQA/MQA、long-context attention、residual attention variants 或 heterogeneous layer cost 会让“搬一层”不再是简单的负载平衡操作。

## 局限与 Future Work

- **局限 1：多节点 claim 未实测。** 下一步应在至少 2-4 节点 pipeline 上测 iteration time、bubble utilization、NCCL wait、planner prediction error 和 failure/restart 行为，区分“无额外通信量”和“实际可扩展”。
- **局限 2：固定 sequence length 和随机输入低估 workload drift。** 可验证实验是用真实 packed pretraining trace，扫描 sequence length 分布、micro-batch count 和 global batch size，记录 Obscura 配置失效、OOM headroom 和 speedup 方差。
- **局限 3：host-side swapping 资源没有被系统性刻画。** 需要报告 PCIe/host DRAM bandwidth utilization、swap/load overlap 失败率，以及与 dataloader、checkpoint、ZeRO-Offload 同时运行时的 interference。
- **局限 4：baseline 没覆盖新一代 zero-bubble/overlap schedule 组合。** 需要把 Obscura 与 interleaved 1F1B、zero-bubble PP、AdaPipe 类 adaptive recomputation/partitioning 的组合对比，判断收益来自 bubble transformation 还是当前 baseline 留下的空档。
- **Future work 1：online planner 或 guardrail。** 在训练中持续采样 stage runtime、activation peak 和 swap delay，当预测误差超过阈值时重跑 planner 或降级到更保守 recomputation 策略。
- **Future work 2：architecture sensitivity。** 对 MoE、GQA/MQA、long-context attention、fused Transformer block、不同 activation function 做 operator activation/compute profile，找出 CMB-Identifying 和 partition adjustment 的适用边界。
- **Future work 3：schedule-aware observability。** 为每个 micro-batch 输出 forward/recompute/backward/swap phase 的 trace id，支持定位 deadlock、bubble miss、OOM 和 regression。
- **Future work 4：time-to-quality 评估。** 在固定 validation loss 或 tokens-to-quality 下比较 Obscura 与 recomputation/offload baselines，确认 schedule transformation 的吞吐收益不会被 batch/partition/数值稳定性调整抵消。

## 相关

- **相关概念**：[[Pipeline-Parallelism]]、[[Activation-Checkpointing]]、[[Pipeline-Bubble]]、[[1F1B]]、[[ZeRO]]、[[FSDP]]、[[NCCL]]
- **同类系统**：[[DAPPLE]]、[[BPipe]]、OHP-CMB、GPipe、PipeDream、AdaPipe、[[Megatron-LM]]、[[DeepSpeed]]
- **同会议**：[[ATC-2025]]
- **原始材料**：[[atc2025-huang-yuzhou]]、[[atc2025-huang-yuzhou.pdf]]
