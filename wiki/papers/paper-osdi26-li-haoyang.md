---
type: paper
name: HetuV2
full_title: "Hetu v2: A General and Scalable Deep Learning System with Hierarchical and Heterogeneous Single Program Multiple Data Annotations"
authors: [Haoyang Li, Fangcheng Fu, Hao Ge, Sheng Lin, Xuanyu Wang, Jiawen Niu, Yuming Zhou, Xupeng Miao, Bin Cui]
venue: OSDI
year: 2026
tags: [distributed-training, spmd, heterogeneous-devices, elastic-training, pipeline-parallelism, deep-learning-systems]
source_pdf: "[[osdi26-li-haoyang.pdf]]"
source_md: "[[osdi26-li-haoyang]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 面向异构训练的 Hetu v2（OSDI 2026）

> **原题**：Hetu v2: A General and Scalable Deep Learning System with Hierarchical and Heterogeneous Single Program Multiple Data Annotations

> **一句话总结**：标准 SPMD 假定设备和样本负载对称，但异构 GPU、故障和混合长度数据会破坏这一前提；Hetu v2 的 HSPMD 在保留单设备编程视图的同时引入非对称分片、分层通信、渐进式图特化和动态图切换，在 32B 模型、最多 48 张混合 H800/H20 GPU 及故障/长短序列场景中取得不低于专用系统的训练性能。

## 问题与动机

分布式深度学习通常用 SPMD（Single Program Multiple Data）表达并行策略：用户从单个设备的视角写程序，再用声明式标注描述张量或层的分片。系统据此推导通信和设备映射。这个抽象在硬件同质、设备稳定、样本计算量接近时很有效。

论文关注三类现实中的不对称性。GPU 代际不同会带来算力、显存和互联带宽差异；GPU 或节点故障会让可用设备集合动态变化；原始文本、图像和视频数据的长度差异会使每一步的计算量变化。传统 SPMD 的对称分片会迫使慢设备承担与快设备相同的工作，也无法优雅地利用部分失效后的剩余资源。场景专用系统虽然加入了异构 pipeline 或弹性调度器，但调度逻辑通常与某一场景紧耦合。

Hetu v2 试图把问题下沉到声明式原语层：用户仍写一份模型程序和一套标注，系统再从中生成每个设备的执行图。论文的目标不是为每种异构场景增加一个调度器，而是提供可组合的非对称分片与通信机制。

## 关键观察 / 隐含假设

- **观察 1：异构性同时具有空间和时间维度。** 混合 GPU 的能力差异在训练期间相对固定，属于空间异构；故障和每步最大序列长度会随时间变化，属于时间异构。论文用图 2、图 3 将三类场景统一到这两个维度。
  - **依赖假设**：异构差异可以被表示为有限的并行策略和 annotation plan；策略切换的收益大于规划、图特化和重分片的成本。
  - **可能失效场景**：设备性能抖动细到单个 step、输入长度频繁变化或候选策略数量很大时，切换开销可能吞噬收益。
- **观察 2：多数计算算子不需要新的异构语义。** 表 2 显示，绝大多数算子的标注可从输入传播到输出；只有 Reshard 以及改变分片结构的少数算子（如 Dot）需要专门推导规则。
  - **证据强度**：强。论文给出了算子分类和推导规则，但覆盖的算子集合与未测试的模型结构仍决定泛化范围。
- **观察 3：通信规划的难点在于分片拥有者和需求者不再一一对应。** 非对称分片下，一个 slice 可能有多个发送者和接收者。最优发送方案可归约为 NP-hard 的 Generalized Assignment Problem，因此系统采用启发式 BSR（Batched Send-Receive）。
  - **依赖假设**：最细粒度 slice 数量主要由单张张量的分片粒度决定，而不是随 DP 复制规模增长；论文据此认为 O(pq) 启发式在大规模下可控。
  - **可能失效场景**：模型采用更细的张量分片、网络拓扑更复杂或通信负载高度倾斜时，启发式可能产生明显次优方案。
- **假设 1：为故障恢复保留数据并行冗余是可接受的。** 弹性实验中 HSPMD 和 Oobleck 都关闭 ZeRO-1，用复制的权重隔离 pipeline 故障，避免 checkpoint-and-restart。
  - **证据强度**：强。论文明确说明这一取舍；但它增加显存占用，使弹性模式下单步时间从 6.05s 增至 6.91s，约慢 15%（图 15、图 16）。

## 核心方法

HSPMD（Hierarchical and Heterogeneous SPMD）扩展普通 SPMD 的声明式分片标注。每个张量的标注包含设备组、组内分片以及层级维度等信息，使不同设备可以获得不同的分片和 pipeline 角色。用户仍以统一的单设备程序描述模型，非对称性由 annotation plan 表达。

通信解析分为底层和顶层。底层在各 sharding subgroup 内选择 Identity、all-reduce、reduce-scatter、all-gather 或点对点 send-receive；顶层处理不同 subgroup 之间的分片维度变化，使用 SplitAR、SplitRS、SplitAG 等组合原语。若两个层级同时变化，系统先对齐设备组，再对齐顶层分片。BSR 根据 slice 的拥有者和需求者建立表，并优先使用高带宽链路、均衡各发送者负载。图 8–11 展示了这些解析过程。

渐进式图特化处理空间异构。系统先从叶节点和 Reshard 的标注推导完整图，再解析通信，并删除不涉及本地设备的非局部算子，最后为每个设备实例化不同的 executable graph。图特化后的图可按 GPipe 或 1F1B 组织成 pipeline；每个设备可以执行不同数量和大小的 micro-batch。这使并行策略与具体执行调度解耦，对应论文的观察 1 和观察 2。

动态图切换处理时间异构。当设备集合或输入长度发生变化，planner 选择新的 annotation plan，系统不从 checkpoint 重新加载权重，而是用 BSR 在旧图之间直接重分片。多个权重的 BSR 表会融合，设备对之间的 send-receive 也会融合，以减少 kernel launch 和不均衡流量。该机制对应观察 3，并将切换成本限制在规划、图特化和一次权重重分片。

## 设计取舍

- **通用原语换取实现复杂度**：HSPMD 避免为异构设备、故障和混合长度分别维护调度器，但需要标注推导、层级通信解析、设备特定图和 pipeline 构造四套机制。
- **弹性换取显存与吞吐**：关闭 ZeRO-1 保留副本，能在 pipeline 失效后继续训练，却不能使用最省显存的策略。论文报告弹性配置的单步时间由 6.05s 变为 6.91s。
- **启发式换取可扩展性**：BSR 不求解 NP-hard 的全局最优分配，而以 O(pq) 扫描生成通信方案。其实际效果依赖 slice 粒度和拓扑。
- **预生成候选策略换取在线响应**：混合长度场景提前生成策略，在线只按当前 step 的最大序列长度选择。候选策略覆盖不足时，系统仍可能错过更好的并行配置。

## 实验与结果

- **异构设备**：在 H800/H20 混合 GPU 配置及不同模型规模上，HSPMD 在异构配置中持续超过 DeepSpeed、Megatron 和 HexiScale；在同质设备上各系统表现接近，说明差异主要来自异构策略而非基础工程实现（图 15）。
- **不稳定设备**：使用 32B 模型和包含 GPU、节点故障的两条 trace。DeepSpeed/Megatron 采用 checkpoint-and-restart，且受对称分片限制，无法充分利用残余设备；HSPMD 可重构异构 pipeline 并继续训练，与 Oobleck 比较时同样关闭 ZeRO-1（图 16）。
- **混合长度数据**：在 32 张 H20、32B 模型、CommonCrawl 和 GitHub 上训练 100 steps，batch size 为 200K tokens，测试 32K 和 16K context。CommonCrawl 的 32K 配置中，97% 序列短于 8K（图 18），HSPMD 因而在长短序列间切换策略，优于固定对称策略的 DeepSpeed/Megatron 和只能使用同质策略的 HotSPa（图 17）。
- **切换开销**：C1 到 C2 的图特化通常在 10s 内完成，标注推导开销可忽略（图 20）。融合 BSR 在总通信量相同的情况下改善 NVLink 利用率并均衡各 rank 流量，端到端切换开销最低（表 4、图 20）。
- **收敛性**：C1 与 Megatron 的 loss 曲线接近；异构 C2 与 C1 基本一致，说明非对称分片和通信没有破坏训练收敛（图 22）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| HSPMD 能在异构 GPU 上平衡不同设备的工作量并提升训练性能 | 图 15；32B 等模型、H800/H20 配置，与 DeepSpeed、Megatron、HexiScale 对比 | 主要是 H800/H20 集群和论文选定模型 | 强 |
| HSPMD 能在故障后重构策略而不依赖 checkpoint 重启 | 图 16；GPU/节点故障 trace；与 checkpoint-and-restart 方案及 Oobleck 对比 | 弹性配置关闭 ZeRO-1，牺牲部分显存效率 | 强 |
| 按序列长度切换策略能改善混合长度训练 | 图 17、图 18；32B、32 张 H20、100 steps、32K/16K context | 使用 CommonCrawl/GitHub，策略按 step 最大长度选择 | 中 |
| BSR 融合可降低切换开销 | 表 4、图 20；比较无启发式、逐 tensor BSR 和 fused BSR | 结论依赖当前 NVLink/InfiniBand 拓扑和分片粒度 | 中 |

## 批判性分析

### 论证链条

论文的链条基本闭合：对称 SPMD 无法表达异构负载，非对称标注提供表达能力，图特化将统一程序变成设备特定执行图，分层通信和 BSR 处理由此产生的通信，动态图切换处理策略变化。三类场景覆盖了固定空间差异、故障引起的变化和输入驱动的变化。

仍有一处外推。论文把异构性归结为空间和时间两个维度，但 planner 如何在大规模候选策略、连续性能抖动和多资源约束下找到近优方案，实验没有系统量化。论文主要展示系统能表达并执行策略，而不是证明其自动规划在所有拓扑和模型上接近最优。

### 假设压力测试

HSPMD 依赖可提前描述的设备能力和输入长度分布。若负载变化在一个 micro-batch 内发生，按 step 切换可能太粗；若 GPU 性能因共享云环境持续抖动，静态图特化的收益会下降。BSR 的复杂度论证依赖 DP 复制而非更细分片来扩展规模，超大 TP/EP 组或专家负载强倾斜时需要重新测量。

故障实验通过复制权重保持正确性，但复制也限制了显存受限模型的可用规模。论文没有报告频繁故障、网络分区、恢复期间数据重放或优化器状态一致性的长期成本。

### 实验可信度

基线覆盖了通用 SPMD 系统和三个场景专用系统，且异构设备实验使用穷举搜索为 DeepSpeed/Megatron 找策略，比较相对公平。混合长度实验把重配置开销计入两种 hot-switch 方案，这是合理的端到端口径。局限是硬件组合、模型规模和数据集仍较集中；没有给出更多 GPU 代际、跨地域网络或更大集群的结果，也没有完整呈现 planner 在候选策略数量增长时的成本曲线。

### 系统性缺陷

图特化会创建设备特定图和通信组，增加调试、监控和故障定位复杂度。论文展示了执行时间和通信量，但未讨论生产环境中图缓存、版本回滚、检查点格式兼容和在线可观测性。非对称 pipeline 还可能使资源隔离和负载公平更难维护。BSR 是启发式方案，论文证明了当前案例中的收益，却没有给出拓扑变化下的近似界或失败案例。

## 局限与后续工作

- **规划质量未充分评估**：需要在更多设备类型、拓扑和并行维度上报告 planner 与穷举或整数规划最优解的差距。
- **弹性模式的显存代价**：关闭 ZeRO-1 后可用模型规模受限。可验证的后续方向是设计同时支持非对称恢复和优化器状态分片的容错方案。
- **动态粒度有限**：当前混合长度策略以 step 为切换单位。应测量按 micro-batch 或 token bucket 更细粒度切换在切换成本、吞吐和收敛上的收益。
- **规模与故障模型边界**：需要在更大规模、跨节点拓扑变化、网络分区和连续故障 trace 上验证 BSR 与图切换的尾延迟和恢复时间。

## 相关

- **相关概念**：[[SPMD]]、[[Pipeline Parallelism]]、[[Tensor Parallelism]]、[[Data Parallelism]]、[[Resharding]]
- **同类系统**：[[DeepSpeed]]、[[Megatron]]、[[Oobleck]]、[[HexiScale]]、[[HotSPa]]
- **同会议**：[[OSDI-2026]]
- **源码**：[Hetu](https://github.com/PKU-DAIR/Hetu)
