---
type: paper
name: Optimus
full_title: "Optimus: Accelerating Large-Scale Multi-Modal LLM Training by Bubble Exploitation"
authors: [Weiqi Feng, Yangrui Chen, Shaoyu Wang, Yanghua Peng, Haibin Lin, Minlan Yu]
venue: ATC
year: 2025
tags: [llm-training, multimodal, 3d-parallelism, pipeline-bubble, distributed-training]
source_pdf: "[[atc2025-feng.pdf]]"
source_md: "[[atc2025-feng]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-30
---

# Optimus：通过流水线气泡利用加速大规模多模态 LLM 训练（ATC 2025）

> **原题**：Optimus: Accelerating Large-Scale Multi-Modal LLM Training by Bubble Exploitation

> **一句话总结**：Optimus 的关键观察是生产级 MLLM 训练里 LLM backbone 的 DP/PP/TP 通信留下约 48% GPU idle cycle，而 encoder 相对小且有独立依赖边界；它用 encoder/LLM 分离的 3D 并行计划和 kernel 级 bubble scheduling 把 encoder 计算塞进 LLM bubble，在 3072 Hopper GPU 的 ViT-22B + GPT-175B 训练上比 Megatron-LM 系 baseline 加速 20.5%-21.3%。

## 问题与动机

MLLM 训练不是简单把视觉 encoder 接到 LLM 前面再套现有 [[Megatron|Megatron-LM]]。典型结构是一个或多个 modality encoder、轻量 projector 和大 LLM backbone；encoder 需要先产出 multimodal feature，LLM 才能开始对应 microbatch 的 forward，反向时又必须等 LLM 先产出 gradient。这个结构同时带来异构计算量和 microbatch 级依赖。

现有大模型训练栈主要为单一 transformer backbone 优化：[[Tensor-Parallelism]]、[[Pipeline-Parallelism]]、[[Data-Parallelism]] 组合成 [[3D-Parallelism]]，再用 1F1B / interleaved 1F1B 降低 pipeline bubble。论文指出，这些优化在大规模 MLLM 上仍留下大量 idle：内部 ViT + GPT backbone 训练任务在 3000+ GPU 上，即使用 MegaScale、Zero Bubble Pipeline 和 fine-grained comm-compute overlap，仍有约 48% GPU cycle idle。

作者的 claim 边界很清楚：Optimus 不是重新设计 MLLM 模型，也不是优化单个 encoder 或 LLM kernel，而是利用 MLLM 的双组件结构，把 encoder computation 当作可被调度的 bubble-filling workload，嵌入 LLM backbone 的通信等待与 pipeline 空档中，目标是降低同步训练 step time。

## 关键观察 / 隐含假设

- **观察 1：大规模 MLLM 训练的主要浪费来自 LLM backbone 的通信和 pipeline bubble，而不是 encoder 本身。** 论文的 production profile 显示，平均 5.12s training step 中 DP all-gather 占 3.3%、DP reduce-scatter 占 8.9%、PP warm-up/cool-down/other 合计 22.9%、TP bubble 占 11.2%，总 idle 接近 48%。
  - **依赖假设**：训练使用同步 3D parallelism，LLM backbone 足够大，DP/PP/TP communication 仍无法被完全 overlap。
  - **可能失效场景**：如果模型或硬件使 LLM communication 已经几乎完全隐藏，或者 pipeline schedule/optimizer 能真正消除这些 bubble，Optimus 可利用的空间会显著变小。

- **观察 2：encoder 比 LLM backbone 小得多，且计算可以沿 microbatch 依赖边界重新排序。** 论文把 projector 归入 encoder，并认为 encoder activation memory 可忽略；最大实验 encoder 是 ViT-22B，而 backbone 可到 GPT-175B，encoder 额外复制带来的 memory overhead 在实验中最高约 12%。
  - **依赖假设**：encoder 参数和 activation 相对 LLM 小，且每个 microbatch 的 encoder forward/backward 只需满足与对应 LLM microbatch 的依赖点。
  - **可能失效场景**：如果未来 MLLM 的 non-text encoder 接近或超过 LLM backbone，或者 encoder activation 很大、分支间有复杂交互，复制 encoder state 和 kernel 级重排的代价会被放大。

- **观察 3：TP bubble 多为子毫秒级，layer-level scheduling 粒度太粗。** 论文测得 GPT-175B layer 中 TP communication 造成的 compute-stream idle 平均约 300us，而 ViT-22B 单层 forward/backward 约 1.4ms/2.0ms，整层塞不进这些小空档。
  - **依赖假设**：encoder layer 可以拆成可预测的 kernel sequence，且 encoder compute kernel 与 LLM communication、encoder communication 与 LLM compute 的资源竞争可控。
  - **可能失效场景**：kernel runtime 波动、CUDA Graph/编译器融合改变 kernel 边界、或者 encoder communication 与 LLM compute 争抢网络/SM 资源时，离线 schedule 可能偏离真实执行。

- **假设 1：生产训练 step 的时间结构足够稳定，离线 profiling 产生的 schedule 可以长期复用。**
  - **证据强度**：中。论文在 production cluster 上验证了性能，但也在 Discussion 承认未处理 CUDA kernel runtime fluctuation，需要 online monitoring 才能动态修正 schedule。

- **假设 2：正确性主要是依赖顺序问题，而不是数值或优化器语义问题。**
  - **证据强度**：中。Optimus 用 EF_i <= F_i、EB_i >= B_i 检查 microbatch 依赖，并保持同步 training iteration 内调度；但论文没有深入讨论 kernel interleaving 对 determinism、debuggability、profiling 可观测性或异常恢复的影响。

## 核心方法

Optimus 分成 model planner 和 bubble scheduler 两层。model planner 先为 LLM backbone 选择常规 3D parallel plan，再枚举 encoder 的 `(DP_enc, PP_enc, TP_enc)`，要求 `PP_enc` 整除 `PP_llm`、`TP_enc` 整除 `TP_llm`，并用 memory model 剪掉 OOM 配置。这样每张 GPU 同时拥有 LLM 和 encoder model state，避免传统统一 pipeline 中只有第一段 GPU 能跑 encoder 的问题。

分离并行计划引入了新的 data layout：同一组 GPU 上可能有 `m = DP_enc / DP_llm` 条 encoder pipeline 对应一条 LLM pipeline。Optimus 进一步枚举 LLM microbatch 在这些 encoder pipeline 间的划分，例如 8 个 microbatch、2 条 encoder pipeline 时枚举 `[1,7]` 到 `[7,1]`。这个设计回应了观察 2：多复制一点 encoder state，换取更多 GPU 都能把 bubble 变成有效 encoder work。

bubble scheduler 先做 coarse-grained exploitation：把 encoder forward 尽量放到 LLM computation 开始前的 DP all-gather + PP warm-up 大 bubble，把 encoder backward 放到 LLM computation 结束后的 PP cool-down + DP reduce-scatter 大 bubble。若还有 encoder work 没被覆盖，再做 fine-grained exploitation：找当前 end-to-end critical path 上的 encoder pipeline，将一个 microbatch 的 encoder computation 拆到 LLM computation 间的 PP/TP 小 bubble。

fine-grained scheduling 的关键是 kernel 粒度。Optimus 不再以 encoder layer 为单位调度，而是把 encoder layer 拆成 kernel sequence；compute kernel 优先塞进 LLM communication bubble，encoder communication kernel 则放到 LLM compute 期间，避免两个 communication kernel 同时抢链路带宽。这正面回应了观察 3：300us 级 TP bubble 装不下一层，但可以装一串更短 kernel。

dependency management 分两步。local scheduling 保证同一 encoder pipeline 内的 iteration dependency 和 encoder pipeline dependency，例如 forward 必须从上游 encoder stage 到下游 stage，backward 反向。global ordering 则把所有 encoder forward 完成时间排序成 `EF_i`，把 encoder backward 可开始时间排序成 `EB_i`，并检查每个 LLM microbatch 的 forward dependency point `F_i` 和 backward dependency point `B_i`：forward 要满足 `EF_i <= F_i`，backward 要满足 `EB_i >= B_i`。

论文还对 interleaved [[1F1B]] 做了一个小但重要的调度调整：把后半部分 microbatch 的 forward dependency point 往后推，只要不增加 LLM pipeline 总时长，就能给 encoder forward 留出更多可用 bubble。对多 encoder MLLM，Optimus 为每个 encoder 独立应用 encoder parallel plan，再把多个 encoder 的 kernel 当作一组无相互依赖的 bubble-filling workload 来调度。

## 设计取舍

- **用 memory 换可调度性**：所有 GPU 同时持有 encoder 和 LLM state，让 bubble filling 从少数 pipeline stage 扩展到全 GPU，但代价是额外复制 encoder state。这个取舍在 ViT-22B vs GPT-175B 的设定下成立；如果 encoder 继续变大，memory headroom 会成为第一瓶颈。
- **用离线 schedule 换运行时简单性**：Optimus 依赖 profiling 得到的 LLM timeline 和 encoder kernel runtime，避免在线调度器进入训练 critical path。但这也让它对 runtime jitter、网络拥塞、kernel fusion、dynamic sequence length 更敏感。
- **用 kernel 级控制换实现复杂度**：layer-level schedule 简单但浪费 TP bubble；kernel-level schedule 能吃掉子毫秒空档，却要求框架精确知道 kernel 类型、duration、stream/resource 竞争关系，工程侵入性高于普通 pipeline schedule。
- **保持同步训练语义，牺牲跨 iteration 弹性**：Optimus 只在当前 training iteration 内填 bubble，不像 Pipefisher/Bamboo 那样跨 step 利用空档。这简化了 convergence/correctness 论证，但也放弃了更激进的空档利用方式。
- **边界条件**：最优雅的场景是大 LLM backbone + 相对小 encoder + 稳定 3D parallel timeline + 充足 GPU memory；脆弱场景是复杂 multimodal graph、动态输入 shape、异构/拥塞网络、或者 baseline 已经通过新 pipeline schedule 大幅压低 bubble。

## 实验与结果

- **主结论**：在生产 Hopper GPU 集群上，ViT-22B + GPT-175B、batch size 1536、3072 GPU 强扩展实验中，Optimus 相比 Megatron-LM 最高约 1.21x，相比 Megatron-LM balanced 最高约 1.20x，对应论文总结的 20.5%-21.3% 加速。
- **weak scaling**：在 64-512 GPU、ViT-11B/22B + LLAMA-70B/GPT-175B 配置上，Optimus 相比 Megatron-LM 最高 1.22x，相比 Megatron-LM balanced 最高 1.18x；Alpa 和 FSDP 在这些大模型配置上 OOM。
- **小模型对比**：在 8 张 A100、ViT-3B + GPT-11B 上，Optimus iteration time 为 2.78s；对比 Alpa 8.61s 是 3.09x，对比 FSDP 3.20s 提升 15.1%，对比 Megatron-LM balanced 3.04s 也有收益。
- **strong scaling 趋势**：固定 batch size 扩 GPU 数时，baseline MFU 随 bubble ratio 上升而下降；Optimus 在 1536/2048/3072 GPU 上 MFU 保持约 34.4%-34.6%，说明它更能吃掉扩展后增加的 bubble。
- **multi-encoder**：在 512 GPU、GPT-175B + 双 ViT encoder 上，Optimus 相比 Megatron-LM 最高 1.25x、1.26x、1.27x；作者解释为 Megatron-LM 把所有 encoders 放第一 pipeline stage，异构 pipeline imbalance 更严重。
- **memory overhead**：相对最省内存 baseline，Optimus 最大 GPU memory overhead 约 12%；在 Model C 上还低于两个 Megatron 系 baseline，说明异构 stage partition 本身也可能造成 memory imbalance。
- **scheduler efficiency**：对 ViT-22B + GPT-175B 的模拟中，fine-grained exploitation 明显提升可塞入 bubble 的 encoder work：1536 GPU 从 34.3% 到 57.5%，2048 GPU 从 45.8% 到 69.3%，3072 GPU 从 68.7% 到 85.0%。scheduler 单核 runtime 分别约 322.2s、89.6s、15.1s，是一次性开销。

## 批判性分析

### 论证链条

论文的主链条比较闭合：production profile 证明 MLLM 训练存在大量 LLM bubble；MLLM encoder 相对小且有明确依赖边界；separate parallel plan 让每张 GPU 有能力执行 encoder；kernel-level bubble scheduler 让子毫秒 TP bubble 也能被利用；大规模实验显示 iteration time 下降。这里最有价值的不是某个单点优化，而是把「MLLM 异构结构」转化成「bubble-filling workload」这个系统抽象。

但有一个外推要小心：论文证明的是在特定 Megatron-LM/MegaScale 风格 3D parallel stack、Hopper GPU、ViT/GPT 类模型上的收益。它没有证明所有 MLLM 训练都天然有可利用 bubble，也没有证明该 schedule 在更动态的 multimodal workload 上仍稳定。Optimus 的贡献更像是对现有同步训练栈的机会利用，而不是一个完全模型无关的训练编排原则。

### 假设压力测试

**workload assumption**：实验主要是 image encoder + LLM backbone，sequence length 固定 2048，batch/microbatch 配置也较规整。真实 MLLM 训练可能混合 image/audio/video、不同分辨率、不同 token expansion ratio，encoder runtime 和 activation size 会更不稳定。若 microbatch 间 runtime 差异变大，离线 global ordering 需要更多保守 slack。

**resource bottleneck assumption**：Optimus 默认主要可利用的是 LLM communication bubble，且 encoder compute 与 LLM communication 互补、encoder communication 与 LLM compute 可 overlap。如果未来 GPU compute 进一步变快但网络没有同步提升，这个假设更强；反过来，如果新 collective overlap 技术已经让 TP/DP communication 更隐身，Optimus 的边际收益会缩小。

**hardware/deployment assumption**：评估在生产 Hopper 集群，80GB GPU、NVLink + high-bandwidth RDMA。跨 region、异构 GPU、拥塞网络、或者更小规模 commodity 集群可能有不同 bubble 形态。尤其是 encoder communication 被安排到 LLM compute 期间时，网络拓扑和 stream priority 的细节会决定它是 overlap 还是制造新瓶颈。

**scaling assumption**：Optimus 在 fixed batch strong scaling 中越大规模越有利，因为 microbatch 数下降、bubble ratio 上升。这个趋势成立于 batch size 固定且 parallel plan 类似的设定；如果训练按 weak scaling 增 batch，或者为了收敛调大 microbatch/gradient accumulation，bubble pattern 可能不同。

**correctness/SLO assumption**：论文关注 training throughput/MFU，没有深入讨论故障恢复、profiling drift、debug trace 可读性、determinism、checkpoint/rollback 与调度状态的一致性。对生产训练平台来说，这些不一定改变数学 correctness，但会显著影响可运维性。

### 实验可信度

实验的强项是规模和工程真实性：3072 Hopper GPU、ViT-22B + GPT-175B、300 iteration 平均、Megatron-LM based baselines，足够支撑「在工业大规模 MLLM 训练栈中有实际收益」。Table 1 的 bubble breakdown 也让问题动机比纯模拟更可信。

baseline 方面，Megatron-LM 和 Megatron-LM balanced 是合理强基线，尤其 balanced 用 DP 算法平衡异构 layer partition，避免只打朴素 Megatron-LM。Alpa/FSDP 只在小模型上比较，因为大模型 OOM；这说明 Optimus 的目标确实更接近 hand-optimized LLM training stack，而不是通用 auto-parallel compiler。

较弱处是排除 DiffusionPipe 和 DistTrain 的论证主要是适用性/开源性，而不是实验。论文也没有给出与未来更强 pipeline schedule、online overlap runtime、或者专门为 MLLM 改造的 zero-bubble variant 的直接对比。因此「20.3% average speedup over existing systems」可信，但它并不等价于「比所有可能的 MLLM-aware scheduler 都好」。

### 系统性缺陷

Optimus 增加了训练栈的状态维度：每张 GPU 同时持有 encoder/LLM states，microbatch 在 encoder pipelines 间重新分配，P2P send/recv 需要按 global ordering 插入。论文说明了 dependency check，但没有详细展开异常路径：某个 rank fail、某个 kernel runtime 飘移、某条 P2P 边阻塞时，如何定位和恢复。

kernel-level schedule 也会让 profiling 和性能回归分析更复杂。原本一个 layer 或 pipeline stage 的慢点，现在可能分散在多个 LLM bubble 内；如果线上出现 MFU 下降，需要同时看 LLM communication、encoder compute、encoder communication overlap 是否仍按预期发生。论文没有讨论 observability interface。

最后，Optimus 对模型结构的覆盖仍偏线性：典型 MLLM 是 encoders followed by one LLM。作者在 Discussion 承认复杂 computation graph 需要新的 partitioning algorithm，把 graph 切成 backbone pipeline 和 bubble-filling workload。这个问题不是小扩展，因为复杂图可能引入跨 encoder dependency 或共享 state，直接破坏「多个 encoder 独立可调度」的简化。

## 局限与后续工作

- **局限 1：离线 schedule 对 runtime jitter 敏感。** 可验证的后续问题是：在动态 sequence length、不同 image resolution、网络拥塞注入下，测量 Optimus schedule 的 miss rate、额外 waiting time 和 MFU 波动。
- **局限 2：复杂 multimodal graph 尚未覆盖。** 可以构造 video/audio/text 多分支且带 cross-modal fusion 的模型，测试「backbone pipeline + bubble-filling workload」切分是否仍能保持 dependency check 简单。
- **局限 3：系统可观测性和恢复没有展开。** 后续应给出 schedule-aware tracing，把每个 encoder kernel 映射回 microbatch、pipeline、dependency point，并测试 checkpoint/rollback 后 schedule state 是否可重建。
- **局限 4：baseline frontier 仍会移动。** 需要和 MLLM-aware zero-bubble pipeline、online runtime scheduler、以及更激进的 TP communication overlap 直接比较，区分 Optimus 的收益来自 MLLM 双组件抽象还是来自当前 baseline 的未利用 bubble。
- **Future work 1：online bubble scheduler。** 用每步采样到的 kernel runtime 和 communication delay 动态调整 schedule，并客观比较 offline vs online 在稳定集群和扰动集群下的收益/开销。
- **Future work 2：encoder size sensitivity。** 系统扫描 encoder/LLM 参数比、activation size、DP_enc/DP_llm 比例，找出 Optimus 从 memory-efficient 变成 memory-bound 的阈值。

## 相关

- **相关概念**：[[Tensor-Parallelism]]、[[Pipeline-Parallelism]]、[[Data-Parallelism]]、[[3D-Parallelism]]、[[Pipeline-Bubble]]、[[1F1B]]、[[Zero-Bubble-Pipeline]]
- **同类系统**：[[Megatron|Megatron-LM]]、[[MegaScale]]、[[DistMM]]、[[FSDP]]、Alpa、Chimera、DistTrain、DiffusionPipe
- **同会议**：[[ATC-2025]]
