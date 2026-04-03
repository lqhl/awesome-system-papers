# PopFetcher: Towards Accelerated Mixture-of-Experts Training Via Popularity Based Expert-Wise Prefetch

**作者**：Junyi Zhang, Chuanhu Ma, Xiong Wang, Yuntao Nie (华中科技大学); Yuqing Li (武汉大学); Yuedong Xu (复旦大学); Xiaofei Liao, Hai Jin (华中科技大学); Bo Li (香港科技大学)
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/zhang-junyi
**源文件**：[[atc2025-zhang-junyi.pdf]]

---

## 一、背景

Mixture-of-Experts (MoE) 架构通过将 Transformer 的 MLP 层拆分为多个稀疏激活的 expert，使模型参数可以扩展到万亿规模，同时训练计算量仅线性增长。然而 MoE 的稀疏激活特性带来了严重的训练效率问题：Expert Parallelism (EP) 模式下，token 需要通过 All-to-All 通信被路由到远端 GPU 上的 expert 进行计算，每个 MoE 层需要两次 All-to-All（dispatch + combine），实测占据单层 56%–58% 的时间。此外，gate 模块的路由不均衡会导致 hot expert 问题，进一步加剧通信拥塞和计算负载不均。

现有优化方案包括：FasterMoE 通过 shadow 机制将热门 expert 广播到所有 GPU，但引入额外的参数同步开销；Janus 尝试将 expert 拉到本地而非推送 token，但当 expert 参数远大于 token 数据时反而更昂贵。这些方案都在 All-to-All 通信的关键路径上进行 expert 调度，无法从根本上消除通信瓶颈。

---

## 二、要解决的问题

1. **All-to-All 通信瓶颈**：EP 模式下每个 MoE 层需要两次同步 All-to-All 通信，占据训练时间的 50%–60%，且无法与计算有效重叠
2. **负载不均衡**：gate 路由的 skewed 分布导致 hot expert 集中在少数 GPU 上，加重通信和计算的不对称
3. **现有 expert 调度方案粒度过粗**：shadow（广播所有 expert）和 pull-all（拉取全部 expert）方案要么引入额外同步开销，要么因 expert 参数过大导致通信量更高；且它们都与 All-to-All 通信争抢带宽
4. **backward pass 中的带宽竞争**：prefetch expert 产生的 All-Reduce 梯度聚合与原有 All-to-All 和 non-MoE All-Reduce 争抢有限网络带宽

---

## 三、洞察与设计

**关键洞察**：MoE 模型中 expert 的选择分布具有显著的时序稳定性和跨层相关性——即在相邻训练迭代之间 expert 热度变化缓慢，且相邻 MoE 层之间的 expert 选择存在可预测的条件概率关系。利用这两个统计特性，可以在当前 MoE 层的非 MoE 计算阶段（如 Attention 层）提前预取下一层的热门 expert，从而将 expert 调度与 token dispatch 在时间上错开，利用空闲网络链路完成数据传输。

基于此洞察，PopFetcher 设计了三个核心模块：

1. **Routing Information Collector**：在每个 worker 上轻量级记录 gate 的路由信息，通过 sliding window（窗口大小 s=10 迭代）追踪 expert 的时序热度，并结合跨层条件概率（Eq. 2-3）预测下一层的 expert popularity
2. **Prefetching Decision-Maker**：基于端到端训练延迟的精确建模（Eq. 6-7），在 GPU 内存约束和传输时间约束下（Eq. 8-9），搜索全局最优的 expert prefetching 方案。通过 pruning 策略将搜索空间缩减至 k×N 个 candidate expert
3. **Asynchronous Scheduling Executor**：异步执行 expert prefetch，利用 non-MoE 层计算期间的空闲网络链路拉取远端 expert 参数到本地

此外，PopFetcher 引入了**混合 push-pull 范式**：当某个 expert 对应的 token 数量超过 expert 参数大小（阈值约 2048 tokens）时，选择 pull expert 到本地；否则继续 push token 到远端。这种细粒度决策避免了纯 pull 或纯 push 的局限性。

在 backward pass 中，PopFetcher 将 All-to-All、All-Reduce（non-MoE 梯度）和 prefetched expert 的 All-Reduce 拆分为 micro-operation，以流水线方式交错执行，并严格优先保证 All-to-All stream 的带宽。

---

## 四、实现细节

- 基于 PyTorch 实现，总计超过 8000 行代码（Python + C++ + CUDA）
- Routing Information Collector 用 Python 实现，通过 `torch.distributed.all_reduce` 同步轻量的 popularity 向量
- Expert prefetching 的核心逻辑用 C++ 和 CUDA 实现
- 利用 `torch.cuda.Stream` 管理专用的 prefetching stream，实现计算与通信的并行
- 通过 `torch.autograd.Function` 自定义 MoE operator 的 forward/backward 行为，封装所有计算、通信和预取逻辑
- 实现为 PyTorch plugin，可独立使用或集成到 Megatron-LM 框架
- 内部 expert 共享机制：同一机器内的 GPU 通过 CPU 内存作为中介共享已预取的 expert，避免重复从远端拉取
- 利用异构网络拓扑（NVLink > PCIe > InfiniBand）优先从高带宽链路获取 expert
- Expert popularity 预测和 prefetching 方案搜索在 CPU 上异步执行，不阻塞 GPU 训练，开销 <100ms

---

## 五、实验结果

**硬件环境**：

| 集群 | 配置 | 互联带宽 |
|------|------|---------|
| Cluster A | 2 机 × 4 NVIDIA RTX 4090 (24GB) | 100Gbps InfiniBand |
| Cluster B | 8 机 × 4 NVIDIA A10 (24GB) | 32Gbps |

**模型与数据集**：MoE-GPT 和 MoE-BERT，12/24 层，16/32/64 experts，OpenWebText + PILE + OSCAR-2201

**基线**：DeepSpeed-MoE, FasterMoE, Megablocks, Tutel, Janus

**主要结果**：

| 指标 | Cluster A | Cluster B |
|------|-----------|-----------|
| 端到端加速比（vs 最慢基线） | 1.28×–2.4× | 1.18×–18.3× |
| vs FasterMoE（per-iteration time） | ~1.3× | ~10× |
| Token 传输减少 | MoE-GPT 14.85%, MoE-BERT 13.46% | — |
| GPU 负载差距降低 | MoE-GPT 43.1%, MoE-BERT 57.1% | — |
| 最大可训练模型规模提升（vs FasterMoE） | 12.3%–20.1% | — |
| 最大可训练模型规模提升（vs Janus） | 49.0%–58.2% | — |

**消融实验**：
- Popularity-based prefetching vs random prefetching：MoE-GPT 加速 1.30×，MoE-BERT 加速 1.26×
- Stream scheduling 额外降低 per-iteration time 10%–10.9%
- Sliding window size=10 在 naive top-k 路由下预测准确率 77.04%，GShard 下 69.62%
- 训练 loss 曲线与标准 FasterMoE 完全一致，保持统计等价性
- Janus（pull-all 方案）在该实验配置下频繁 OOM

---

## 六、批判性分析

1. **实验规模偏小**：所有实验在 8–32 GPU（RTX 4090 / A10）上进行，这些都是消费级或中低端数据中心 GPU。论文声称的 15%–94.5% 加速范围中，94.5% 仅在 Cluster B（32Gbps 极低带宽）上出现。在真实大规模 MoE 训练场景（数百到数千 GPU，NVLink + NVSwitch + 400Gbps RDMA）下，compute-to-bandwidth ratio ε 的条件可能截然不同，加速效果存疑

2. **模型规模严重不足**：实验使用的 MoE-GPT 和 MoE-BERT 最大约 2B 参数、64 experts。而当前主流 MoE 模型（DeepSeek-V3、Mixtral）动辄 600B+ 参数、数百个 expert。论文未展示在大模型上的可扩展性

3. **Janus 基线不公平**：论文承认 Janus 源码未公开，自行重实现为"prefetch all experts"，这与 Janus 原论文的策略可能存在差异。Janus 在所有实验中 OOM 被排除，无法直接比较

4. **Sliding window 预测在训练初期的局限性**：论文 Figure 3 显示训练早期 expert 选择分布剧烈变化，但 sliding window 预测依赖历史数据的稳定性。论文未分析早期预测准确率下降对整体训练效率的影响

5. **GShard 路由下预测准确率显著下降**：Table 4 显示在 GShard 路由下，sliding window 从 5 到 100 的准确率从 68.13% 骤降至 45.30%，表明预测方法对路由策略高度敏感。但论文所有端到端实验均使用 GShard 路由，并未讨论此矛盾

6. **混合 push-pull 的 2048 token 阈值**：论文推导出 pull expert 比 push token 更优的条件是 token 数 > 2048（基于 float32、H=1024），但未讨论 bf16/fp16 训练、不同 hidden size、不同 expert 结构下该阈值的变化

7. **缺乏与 pipeline parallelism 和 tensor parallelism 的组合分析**：实际大规模 MoE 训练通常混合使用 TP+EP+PP+DP，论文仅考虑 EP+DP 场景

---

## 七、AI Infra / MLSys 视角

**启发与借鉴**：

1. **利用稀疏激活的统计特性做系统优化**是一个重要方向。PopFetcher 证明了 expert 选择的时序局部性和跨层相关性可以被有效利用，这个思路可以推广到 MoE 推理（KV cache 预测、expert offloading 策略）

2. **混合 push-pull 范式**的细粒度决策逻辑具有普适价值。在 MoE 推理的 prefill/decode 阶段，token 数量差异巨大，类似的自适应通信策略可能带来显著收益

3. **backward pass 的 stream 优先级调度**：将 All-to-All、All-Reduce 拆分为 micro-operation 并做优先级流水线，这个思路可以用于任何涉及多种通信 pattern 混合的分布式训练场景

**值得跟进的方向**：

- **大规模 MoE 训练的 expert placement 与 prefetching 联合优化**：PopFetcher 假设 expert 已经静态放置，但如果将 expert placement 也纳入优化（类似 FlexMoE），与 prefetching 联合决策，可能获得更大收益
- **MoE 推理中的 expert prefetching**：推理阶段的 expert offloading（GPU ↔ CPU/SSD）面临类似问题，PopFetcher 的 popularity prediction 方法可以迁移
- **与 DeepSeek 的 shared expert 架构结合**：DeepSeek-V3 使用 shared expert + routed expert 的混合架构，prefetching 策略需要相应调整

---

## 八、总结

PopFetcher 提出了一种基于 expert popularity 预测的异步预取机制来加速 MoE 训练，通过 sliding window 预测 expert 热度、混合 push-pull 通信范式、以及 backward pass 的 stream 优先级调度，在小规模 GPU 集群上实现了 15%–94.5% 的训练时间缩减，同时保持训练等价性。其核心贡献在于将 expert 调度从 All-to-All 关键路径上解耦，利用 non-MoE 计算期间的空闲链路完成预取。主要局限在于实验规模偏小（最大 32 GPU、~2B 参数），未验证在大规模真实 MoE 训练场景下的效果，且预测准确率对路由策略敏感。
