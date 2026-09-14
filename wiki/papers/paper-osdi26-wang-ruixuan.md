---
type: paper
name: DrsNAS
full_title: "Drs.NAS: Ultra-Efficient Neural Architecture Search for Recommendation Systems"
authors: [Ruixuan Wang, Xun Jiao]
venue: OSDI
year: 2026
tags: [neural-architecture-search, recommender-systems, zero-cost-proxy, model-efficiency, training-free-search]
source_pdf: "[[osdi26-wang-ruixuan.pdf]]"
source_md: "[[osdi26-wang-ruixuan]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-06-24
---

# 面向推荐系统的超高效神经架构搜索（OSDI 2026）

> **原题**：Drs.NAS: Ultra-Efficient Neural Architecture Search for Recommendation Systems

> **一句话总结**：Drs.NAS 假设推荐模型初始化时的多个 zero-cost proxy 能共同预测架构质量，在不训练 supernet 或候选模型的情况下，用七维 superproxy 和梯度搜索把 NAS 搜索压缩到商品 CPU 上约两分钟；在 Criteo、Avazu、KDD 上，它相对 NAS 基线平均减少 34.9× 参数量和 14.7× FLOPs，同时 AUC 平均高 0.0056。

## 问题与动机

深度推荐系统（DRS）的架构通常由人工设计，或用 NAS 在大量候选结构中搜索。现有 DRS NAS 方法依赖 supernet 训练、候选子网验证和微调，搜索成本达到数 GPU 小时到数天；搜索结果也往往只优化 AUC 或 Log Loss，没有把参数量和计算量纳入目标。

论文提出 Drs.NAS，目标是同时缩短架构搜索时间、降低部署架构的计算和内存成本，并维持预测质量。它把候选算子映射为由参数量、FLOPs、权重范数、梯度范数、Zico、SynFlow、Meco 组成的七维 superproxy，再在该表示上构造可微 DAG 搜索空间。

## 关键观察 / 隐含假设

- **观察 1：传统 NAS 的主要成本来自训练与验证，而非候选结构本身。** NASRec 等方法需要训练 supernet，并对候选架构继续验证；论文报告 Drs.NAS 的搜索在 CPU 上约两分钟，而 NAS 基线需要 5–18 GPU-hours（表 1、§5.1）。
  - **依赖假设**：少量初始化样本上计算的 proxy 与最终训练后的预测质量存在稳定相关性。
  - **可能失效场景**：模型初始化、随机种子、数据分布或搜索空间变化后 proxy 排序不稳定；论文只在三个 CTR 数据集和固定架构族上验证。
- **观察 2：单一 proxy 不能可靠代表架构质量。** 参数量和 FLOPs 较高的架构并不总有更好的 AUC；论文据此将多个性能、梯度和开销 proxy 组合（§5.4）。
  - **依赖假设**：不同 proxy 的互补性足以抵消单个 proxy 的偏差，且归一化和可学习权重不会造成某一 proxy 主导优化。
- **假设 3：推荐模型的 backbone 是主要可优化对象。** 论文固定 embedding tables，不把其参数计入搜索和模型大小比较（§4.1）。
  - **证据强度**：中。该设定便于公平比较 backbone，但在线推荐中 embedding 往往占据主要内存，因而不能直接推出端到端服务成本下降。

## 核心方法

Drs.NAS 先按照 NASRec 构造包含 dense、sparse 和 feature-fusion 算子的 supernet。每个算子的参数量、FLOPs、权重范数和梯度范数作为开销相关 proxy；Zico、SynFlow、Meco 作为性能与可训练性相关 proxy。七个值拼成算子的 superproxy，候选层和候选边的 superproxy分别由组成算子或端点逐元素相加得到。

搜索空间是 DAG：每层选择一个候选层，并从候选输入边中选择子集。论文用 Gumbel-Softmax 将离散选择连续化，再用梯度下降优化架构权重。最终每个顶点选权重最高的候选层，每层保留权重排名前 50% 的输入边。

复合损失由三部分组成：`L_vertex` 使用参数量、梯度范数和权重范数推动候选层选择，Zico、SynFlow、Meco 作为正则项；`L_edge` 优化数据流和梯度流；`L_cost` 同时惩罚 FLOPs 和参数量。三部分损失的权重可学习，并通过 softmax 归一化。该设计对应观察 2：不把任何单一 proxy 当作完整质量指标。

搜索使用训练集随机抽取的 2,048 个样本和 BCE 梯度，运行 10,000 次迭代；隐藏维度从 4 到 32 的连续整数中选择，模型深度测试 5–9。搜索在 AMD Ryzen 5975WX CPU 上执行，搜索完成后在 NVIDIA A6000 上训练和评估生成架构。

## 设计取舍

- **搜索速度与 proxy 偏差**：跳过 supernet 训练和候选架构验证，把成本降到 CPU-minutes，但最终质量依赖初始化 proxy 与真实训练质量的相关性。
- **精细、低维搜索空间与表达能力**：4–32 的连续隐藏维度有利于找到小模型，却可能排除需要更宽层的任务；Full search space 还会带来更多算子选择。
- **固定 50% 输入边**：提供简单的复杂度控制，但这个阈值是启发式设定，不能保证不同数据集或硬件上的最佳延迟。
- **参数量和 FLOPs 作为成本代理**：它们容易计算并能解释搜索方向，但没有直接建模 embedding 内存、访存、并行效率或尾延迟。

## 实验与结果

- 在 Criteo、Avazu、KDD 上，Drs.NAS 的搜索时间相对 PROFIT、AutoCTR、NAS-CTR、NASRec 平均分别减少 461×、692×、193×、230×；搜索在商品 CPU 上约两分钟完成（表 1、§5.1）。
- 相比 handcrafted 基线，三个数据集上的平均 Log Loss 分别降低 0.0028、0.0078、0.0046；相对 NAS 基线分别降低 0.0011、0.0022、0.0026（§5.2）。
- 相比 handcrafted 基线，AUC 分别提高 0.0022、0.0137、0.0211；相比 NAS 基线分别提高 0.0004、0.0043、0.0121（§5.2）。
- 相比 NAS 基线，参数量在 Criteo、Avazu、KDD 上平均减少 54.8%、36.7%、13.3%，FLOPs 分别减少 25.2%、10.2%、8.7%；三者平均为 34.9× 和 14.7× 的相对缩减（图 4、§5.3）。
- 生成架构的 CPU 推理时间平均降低 60.8%，GPU 推理时间平均降低 24%；测试固定深度 D=7，每个测量重复三次（表 3）。
- Small search space 的 AUC 更高，Full search space 的参数量和 FLOPs 更低：三数据集参数量减少 56–64%，FLOPs 减少 14–21%（§5.4）。模型深度变化时 AUC 的 CV 为 0.0002–0.0006，说明在该实验范围内结果较稳定。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| superproxy 能替代搜索阶段的反复训练与验证 | 搜索时间、CPU-only 设置，表 1、§5.1 | 三个 CTR benchmark；未与更多 proxy 集成方法比较 | 中 |
| Drs.NAS 保持或提升预测质量 | Log Loss/AUC，图 4(a)–(f)、§5.2 | Criteo、Avazu、KDD；embedding table 不计入架构成本 | 中 |
| 搜索出的架构更省计算和内存 | 参数量、FLOPs，图 4(g)–(l)、§5.3 | backbone 指标，不是端到端服务内存；FLOPs 与真实延迟的关系受硬件影响 | 中 |
| 复合 proxy 比单一 proxy 更稳健 | 深度、学习率、搜索空间消融，图 5、§5.4 | 10,000 次迭代和给定超参数范围；没有逐 proxy 的完整消融 | 弱到中 |

## 批判性分析

### 论证链条

从“训练验证成本高”到“使用训练前 proxy”再到“CPU 上完成搜索”的链条是闭合的，搜索时间结果直接支持成本主张。预测质量结果也覆盖了三个公开 benchmark。但论文把 proxy 与架构质量的关系主要作为整体结果呈现，缺少每个 proxy、不同随机初始化和 proxy 排序相关性的系统分析，因此不能判断收益来自七维组合、特定损失权重，还是低维细粒度搜索空间。

### 假设压力测试

所有模型质量都在最终训练后评估，搜索 proxy 却只使用一个随机抽取的 2,048 样本批次。若样本长尾、稀疏特征分布或线上流量与该批次不同，候选排序可能改变。实验也只覆盖 CTR 推荐模型；论文明确承认其对其他模型族（例如 LLM）的适用边界未知（§6）。此外，参数量和 FLOPs 排除 embedding tables，无法说明 embedding 主导的生产推荐服务是否同样受益。

### 实验可信度

基线包含 handcrafted DRS 和四个代表性 NAS 方法，三个数据集也便于与既有工作比较。论文报告 AUC、Log Loss、参数量、FLOPs 和单样本推理时间，覆盖了质量和部分成本维度。限制在于推理时间每项只重复三次，未报告 P99、批大小、embedding 查表开销、内存峰值或多租户干扰；CPU/GPU 延迟也不能替代线上服务的端到端测量。

### 系统性缺陷

论文未讨论搜索结果的可复现性、训练随机种子、模型更新期间的架构回滚和线上监控。可学习损失权重和 50% 边阈值减少了手工调参，但仍引入实现细节。若部署硬件、编译器或 batch 规模改变，FLOPs 降低未必按比例转化为延迟降低。

## 局限与后续工作

- **局限 1**：embedding table 被固定并排除在成本指标外，端到端内存收益可能被高估。
- **局限 2**：只使用一个 batch 计算 gradient-based proxy，尚未测量多 batch、不同随机种子和时间切片对架构排序的影响。
- **局限 3**：复合 superproxy 缺少逐项消融，无法定量解释七个 proxy 各自的贡献。
- **后续工作 1**：在相同搜索空间下，对每个 proxy 做 leave-one-out 和多随机种子实验，报告候选排序与最终 AUC 的 Spearman 相关性。
- **后续工作 2**：把 embedding 查表、内存带宽、batch size 和 P99 延迟加入硬件实测成本模型，验证 FLOPs/参数量缩减是否能转化为生产 SLO 改善。
- **后续工作 3**：在更多推荐任务和不同模型族上测试 proxy 的迁移边界，并比较跨任务复用的 superproxy 是否仍能保持搜索质量。

## 相关

- **相关概念**：[[Neural Architecture Search]]、[[Zero-Cost Proxy]]、[[Differentiable NAS]]、[[Recommendation Systems]]
- **同类系统**：[[NASRec]]、[[AutoCTR]]、[[NAS-CTR]]
- **同会议**：[[OSDI-2026]]
