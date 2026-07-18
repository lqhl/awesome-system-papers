---
type: paper
name: AttnRes
full_title: "Attention Residuals (Technical Report)"
authors: [Kimi Team]
venue: arXiv
year: 2026
tags: [llm-architecture, residual-connections, attention, ml-systems, inference]
source_pdf: "[[arxiv26-kimi-attention-residuals.pdf]]"
source_md: "[[arxiv26-kimi-attention-residuals]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# Attention Residuals (Technical Report) (arXiv 2026)

> **一句话总结**：AttnRes 把 [[PreNorm]] Transformer 中“所有先前层固定相加”的 [[Residual-Connections|residual]] 路径改成沿深度维度的 softmax [[Attention|attention]]，核心假设是深层 LLM 的 PreNorm dilution 来自 O(L) hidden-state 增长和不可选择的层间聚合；Block AttnRes 用约 8 个 block representation 把 Full AttnRes 的 O(Ld) 记忆/通信降到 O(Nd)，在 Kimi Linear 48B/3B-active、1.4T token 预训练中以训练开销 <4%、推理开销 <2% 换来 GPQA-Diamond +7.5、Math +3.6、HumanEval +3.1，并在 scaling law 上约等价于 baseline 1.25x compute。

## 问题与动机

这篇 technical report 重新解释了现代 LLM 里最普通的 residual path：它不仅是 gradient highway，也是在“深度维度”上把前面所有 layer output 聚合给后续层的机制。标准 PreNorm residual 展开后近似是所有历史输出的固定单位权重求和，后续层不能选择性地取回某个早期表示，也不能抑制无关层的贡献。

作者声称这个固定聚合会导致 **PreNorm dilution**：hidden state magnitude 随深度单调增长，后面每一层的相对贡献被越来越大的 residual stream 稀释。为了保持影响力，深层必须产生更大的 output；反向传播时，早期层 gradient 也会异常大。这个问题在深层、PreNorm、LLM 训练里尤其重要，因为 norm 只规范化 layer 输入，不约束 residual stream 的累计尺度。

AttnRes 的动机不是“再加一个 skip connection”，而是把 sequence 维度的经验搬到 depth 维度：RNN 被 Transformer attention 替代，是因为每个 token 需要选择性访问历史 token；类似地，深层网络也可能需要选择性访问历史 layer output，而不是只能拿一个固定相加的压缩状态。

系统问题来自 Full AttnRes 的代价。若每层都 attend 到所有先前层输出，普通训练中这些 activation 本来会为 backprop 保存，额外开销很小；但大规模训练常用 activation recomputation 和 [[Pipeline-Parallelism]]，此时先前层输出必须跨 stage 保留/传输，通信和 memory 会重新变成主瓶颈。因此论文提出 Block AttnRes 和对应训练/推理优化，试图把架构想法做成 Kimi Linear 级别可落地的 drop-in replacement。

## 关键观察 / 隐含假设

- **观察 1：PreNorm residual 的固定单位求和会放大 hidden-state magnitude，并稀释深层贡献。** 论文在 Kimi Linear 48B/3B-active 训练动态里显示，baseline 的 output magnitude 随 transformer block index 明显增长，而 Block AttnRes 呈 block 内有界的周期性增长；gradient magnitude 也从 baseline 早期层偏大变得更均匀。
  - **依赖假设**：目标模型采用 PreNorm 风格 residual stream，且深度足够大，使 residual accumulation 成为有效深度和训练稳定性的主导因素之一。
  - **可能失效场景**：PostNorm、DeepNorm、显式 residual scaling、很浅的模型，或已经通过其他 normalization/gating 控制 residual magnitude 的架构，未必有同样瓶颈。

- **观察 2：仅有跨层访问不够，必须是 input-dependent、softmax-normalized 的选择。** DenseFormer 给每层访问所有 previous outputs 但用 input-independent scalar weights，在 16-layer ablation 中 loss 1.767，几乎等于 PreNorm baseline 1.766；mHC 用多 stream 动态 mixing 到 1.747；Full AttnRes 到 1.737。去掉 query/key 变成静态 mixing 后 loss 1.749，换 sigmoid 也退到 1.741。
  - **依赖假设**：不同 token / layer type 确实需要不同历史层；单个 learned pseudo-query 加 RMSNorm key/value 足以捕获这种差异。
  - **可能失效场景**：如果某些模型的层表示高度同质，或最优 depth mixing 必须强依赖当前 hidden state，那么 input-independent pseudo-query 会成为表达瓶颈。论文的 input-dependent query ablation 到 1.731，也暗示默认设计牺牲了部分质量换系统效率。

- **观察 3：Block-level depth attention 保留了 Full AttnRes 的主要结构，同时把系统代价压到可用范围。** Block size sweep 中，Full AttnRes 即 S=1 loss 1.737；S=2/4/8 都在约 1.746 附近；S=16/32 才明显退化。Scaling law 最大配置下 Full 1.692、Block 1.693，差距只剩 0.001。
  - **依赖假设**：相邻若干层的输出可以被 block sum 表示，后续层多数时候只需要 block-level source，而不是每个单独 layer output。
  - **可能失效场景**：超深网络、强 alternating layer roles、或需要精细跨层检索的任务可能更依赖 Full AttnRes 的 per-layer granularity；block sum 也可能掩盖 block 内互相抵消的信息。

- **观察 4：AttnRes 似乎改变了最佳 depth/width tradeoff。** 在固定约 6.5e19 FLOPs 和约 2.3e8 active parameters 的 25 点架构 sweep 中，AttnRes 每个配置都比 baseline 低 0.019-0.063 loss，且 optimum 从 baseline 的 d_model/L_b≈60 移到 AttnRes 的 d_model/L_b≈45，指向更深更窄的偏好。
  - **依赖假设**：训练 loss 的 architecture sweep 能代表最终部署中的质量/成本 tradeoff。
  - **可能失效场景**：更深模型推理有更长的 sequential layer latency；论文自己也提醒这个 sweep 不直接等价于部署推荐。

## 核心方法

AttnRes 的形式化入口是 depth mixing matrix。标准 residual 展开后，每层输入都是 embedding 与所有前层 output 的 lower-triangular all-ones 聚合；Highway、DeepNorm、mHC 等方法都可以看成对这个 depth mixing matrix 加权或扩展 state rank。论文把这些归为 depth-wise linear attention / recurrence 系列，而 AttnRes 是 depth-wise softmax attention。

**Full AttnRes** 为每个 layer l 学一个 d 维 pseudo-query `w_l`，把 embedding 和所有前层 `f_i(h_i)` 作为 key/value，经 RMSNorm 后计算 softmax weight：

```text
h_l = sum_i alpha_{i -> l} v_i
alpha_{i -> l} = softmax(w_l^T RMSNorm(k_i))
```

RMSNorm 的角色很关键：如果 key 直接用 layer output，较大 magnitude 的 source 会天然支配 softmax，反而复现 residual magnitude bias。Ablation 中去掉 RMSNorm，Full AttnRes loss 从 1.737 退到 1.743，Block AttnRes 从 1.746 退到 1.750。

默认 query 不依赖输入，而是每层一个 learned vector。这降低表达力，但带来两个系统收益：第一，query 可在 block 内提前批量计算，不需要等当前 hidden state；第二，推理时可以把 inter-block attention 一次性算完，再用 [[Online-Softmax]] 合并 intra-block partial sum。论文明确说明 input-dependent query 质量更好（1.731），但需要每层 d x d projection，并破坏 decoding 中的顺序 I/O 优化。

**Block AttnRes** 把 L 层分成 N 个 block。block 内仍用普通 residual sum 得到 partial block representation；跨 block 时，每层只 attend 到 embedding、已完成的 block representations，以及当前 block 的 partial sum。这样 Full AttnRes 的 per-token memory / communication 从 O(Ld) 降到 O(Nd)，其中 N≈8 在实验里已经恢复大部分增益。

训练侧的系统设计主要服务 [[Pipeline-Parallelism]]。朴素做法会在 interleaved pipeline 的每个 virtual stage transition 重传完整 block history；cross-stage caching 让每个 physical rank 缓存已经收到的 block，后续 virtual stage 只传 incremental blocks，把 peak transition cost 从 O(C) 降到 O(P)，其中 C=P*V。

推理侧是 two-phase computation。Phase 1 把一个 block 内 S 个 layer 的 inter-block queries 合并成 batched attention，只读一次 block KV；Phase 2 顺序处理 intra-block partial sum，并用 online softmax 的 max/LSE 统计做精确合并。长上下文 prefill 时，block representations 原本需要 N*T*d elements；论文用 sequence sharding 让每个 TP device 保存 N*(T/P)*d，再配合 chunked prefill，把 128K context、8 blocks 的例子从总 15GB 降到约 1.9GB/device，进一步到 <0.3GB/device。

## 设计取舍

- **表达力 vs. 系统可批量性**：input-dependent query 的 loss 最好，但默认 learned pseudo-query 让 inter-block attention 能提前批量算，推理 I/O 更像一个可融合的 residual mechanism。
- **Full fidelity vs. block compression**：Full AttnRes 是最直接的“每层访问所有前层”实现；Block AttnRes 把一段 layer outputs 压成 block sum，牺牲粒度换 O(Nd) memory/communication。
- **softmax competition vs. residual highway 直通性**：softmax 让 source 之间竞争概率质量，能抑制无关层，也可能产生 depth-wise attention sinks 或让某些 source 长期被压低；论文观察到 embedding source 仍保有非平凡权重。
- **drop-in architecture vs. runtime coupling**：论文把方法描述为 residual replacement，但高效实现依赖 pipeline cache、activation checkpointing、online-softmax merge、sequence-sharded prefill 等 runtime 配合，真正落地并不只是改一行 residual add。
- **更深更窄的质量偏好 vs. inference latency**：AttnRes 让模型更能利用深度，但深度增加通常拉长 sequential layer path；服务端吞吐/latency 可能不随 training loss 同步改善。

## 实验与结果

- **Scaling law**：5 个 MoE active-parameter scale 上，Baseline / Full AttnRes / Block AttnRes 都用相同 baseline-tuned hyperparameters。最大 528M active-parameter 配置上，validation loss 从 baseline 1.719 降到 Block 1.693、Full 1.692；在 5.6 PFLOP/s-days 附近，Block AttnRes 达到 1.692，而 baseline 拟合曲线约 1.714，等价 1.25x compute advantage。
- **主模型结果**：Kimi Linear 48B total / 3B active、27 transformer blocks / 54 layers，Block AttnRes 每 6 层一个 block，共 9 个 block 加 embedding source；1T token WSD pre-training + 约 400B high-quality mid-training 后，Table 3 中所有 benchmark 持平或提升。
- **下游任务**：GPQA-Diamond 36.9 -> 44.4（+7.5），Math 53.5 -> 57.1（+3.6），HumanEval 59.1 -> 62.2（+3.1），C-Eval 79.6 -> 82.5（+2.9），MMLU 73.5 -> 74.6（+1.1）；MMLU-Pro Hard 持平 52.2。
- **Ablation**：16-layer 模型中 baseline 1.766；DenseFormer 1.767 说明静态跨层访问无效；mHC 1.747；Full AttnRes 1.737；Block S=4 1.746；sliding-window access W=1+8 只有 1.764，说明只看近邻不够。
- **训练动态**：Block AttnRes validation loss 全程低于 baseline，decay phase gap 变大；baseline output magnitude 随深度增长到约 12，而 AttnRes 在每个 block 内周期性重置；baseline early layers gradient 最大，AttnRes 更均匀。
- **系统开销**：无 [[Pipeline-Parallelism|PP]] 时训练 overhead 近似 0；PP 下 end-to-end overhead <4%；典型推理 workload latency overhead <2%。不过论文没有展开完整 p50/p95 latency、batch size、context length、并行配置矩阵。

## Critical Analysis

### 论证链条

论文的核心链条相当清楚：PreNorm residual 固定求和造成 magnitude growth 和 contribution dilution；depth-wise softmax attention 提供 selective retrieval；Full AttnRes 证明设计上限；Block AttnRes 加系统优化让上限接近可部署。这个链条被 scaling law、component ablation、training dynamics 和 48B/3B-active 下游结果共同支撑。

最强的证据是 ablation 分解：DenseFormer 失败说明“访问所有前层”本身不是关键，input-independent mixing 失败说明“可学习静态权重”也不够，sigmoid 与 no-RMSNorm 退化说明 softmax competition 和 magnitude normalization 都不是装饰件。Block size sweep 又说明 block compression 是一个连续 tradeoff，而不是拍脑袋的工程简化。

跳步主要在“drop-in replacement”和“普适架构规律”。实验主体是 Kimi Linear hybrid KDA/MLA + [[MoE]] 架构、Moonshot/Kimi training recipe、内部数据和评测流程；论文没有证明同样收益会出现在 dense GPT-style Transformer、PostNorm/DeepNorm 系列，或不同 optimizer/data mixture 上。作者的表述比纯方法论文更像“在我们的下一代训练栈里有效”，但 abstract 的语气更接近通用 residual replacement。

### 假设压力测试

如果 residual magnitude 不是主瓶颈，AttnRes 可能只是在增加一个轻量 routing mechanism，而不是解决 fundamental depth bottleneck。比如已经用 scaled residual、hybrid norm、multi-stream recurrence 的模型，可能没有同样的 PreNorm dilution；此时 AttnRes 的 softmax competition 是否还带来收益，需要单独实验。

Block representation 的可压缩性也需要压力测试。论文的 block sum 在 Kimi Linear 上表现好，但不同 layer type、不同 depth、不同 MoE routing 稀疏性可能让 block 内 source 更异质。特别是 attention / MLP / expert routing 在不同 token 上产生的功能差异，是否能被一个 block-level key/value 概括，目前只由 loss sweep 间接支持。

硬件假设同样明显：当前结论把 Full AttnRes 受限于 memory/communication，Block AttnRes 是 practical point。若未来 interconnect 或 activation memory 约束变化，Full 或更细 block 可能成为更优点；若服务系统更受 tail latency / kernel launch / cache residency 约束，Block AttnRes 的 <2% overhead 也可能不稳。

### 实验可信度

实验覆盖面比一般架构 technical report 强：有小规模 scaling law、主模型训练、ablation、architecture sweep、training dynamics、attention pattern visualization。所有 variants 共享 baseline 选出的 hyperparameters，理论上偏向 baseline，使得 AttnRes gain 更可信。

但系统论文角度仍有缺口。训练 overhead 只给 aggregate number，缺少 pipeline stage count、V/P、microbatch、网络拓扑、overlap 成功率、activation checkpointing 策略的系统表。推理 overhead 的“typical workloads”没有具体 workload matrix，也没有展示长上下文、batching、prefill/decode 分离、cache eviction、TP/PP/CP 组合下的 p95 latency。

下游结果也主要是 quality table，没有展示方差、重复训练、statistical significance，或 instruction/post-training 后收益是否保留。GPQA / Math / HumanEval 的提升很大，符合“compositional reasoning benefits from depth retrieval”的解释，但还不能排除训练动态、architecture preference、或 recipe interaction 的共同作用。

### 系统性缺陷

论文未讨论 fault tolerance 和 checkpoint/restore：Block AttnRes 增加了跨 stage 的 block history cache，训练失败恢复、pipeline flush、microbatch replay 时需要确保 cache state 与 activation checkpoint 完全一致。

论文未讨论 serving cache management：block representations 类似一条额外的 per-sequence [[KV-Cache]]，长上下文 prefill 可用 sharding/chunking 降低 peak memory，但 decode 阶段的 cache residency、eviction、paged allocation、multi-tenant isolation 没有展开。

论文未讨论 observability 和 debugging：depth attention weights 可能成为新的训练健康信号，也可能出现 attention sink、layer collapse、source starvation。Figure 8 做了平均权重可视化，但没有给出线上可监控指标或异常处理策略。

论文未讨论 compatibility surface：AttnRes 与 FSDP/ZeRO、context parallel、sequence parallel、expert parallel、kernel fusion、quantization、speculative decoding 的相互作用都可能影响真实部署成本。当前 report 更像证明“可在 Kimi stack 内实现”，不是完整开源系统评估。

## 局限与 Future Work

- **局限 1：架构外推有限**。主要实证在 Kimi Linear hybrid KDA/MLA + MoE 上完成；Future work 应在 dense Transformer、DeepNorm/PostNorm、mHC/Hyper-Connections、不同 depth/width recipe 下做 matched-compute scaling law。
- **局限 2：系统评估粒度不够**。论文给出 <4% training 和 <2% inference overhead，但缺少端到端 profiling 表；Future work 应公开 PP/TP/CP 配置、batch size、context length、prefill/decode mix、p50/p95 latency、HBM traffic 和 network traffic。
- **局限 3：block granularity 是固定手工点**。N≈8 是经验结论；Future work 可以让 block size 随 depth/layer type 自适应，或用 objective search 在 quality、HBM、pipeline communication 和 latency 之间找 Pareto frontier。
- **局限 4：pseudo-query 是质量/系统折中**。Input-dependent query loss 更低但系统代价更高；Future work 可测试 low-rank query、grouped query、periodic input-dependent refresh 等中间点，目标是接近 1.731 loss 同时保持 batched inter-block I/O。
- **Future work 1：depth attention health metrics**。客观指标可以包括 attention entropy、embedding-source mass、off-diagonal retrieval frequency、source starvation rate，并与 pruning robustness、gradient distribution、downstream reasoning gain 关联。
- **Future work 2：serving runtime integration**。把 block representation 做成可分页、可迁移、可 checkpoint 的 cache 对象，测量 multi-tenant long-context serving 下的 memory fragmentation、eviction policy 和 tail latency。

## 相关

- **相关概念**：[[Residual-Connections]]、[[PreNorm]]、[[Attention]]、[[Online-Softmax]]、[[Pipeline-Parallelism]]、[[KV-Cache]]、[[MoE]]
- **集成架构**：[[Kimi-Linear]]（48B/3B-active，hybrid KDA + MLA + MoE）
- **对比方法**：DenseFormer、mHC、Hyper-Connections、Highway Networks、DeepNorm、SiameseNorm、MRLA、Sliding-Window Aggregation
- **相邻论文**：[[Transformer-NeurIPS17]]、[[DeepSeek-V4-arXiv26]]
- **同年 arXiv / Kimi 方向**：[[arXiv-2026]]、[[DeepSeek-V4-arXiv26]]
