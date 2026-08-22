---
type: proposal
name: ElasticMoEP2P
title: "ElasticMoEP2P：多节点 MoE 专家级弹性的归档评估"
status: archived
created: 2026-04-05
last_updated: 2026-08-21
evidence_mode: probe-backed
source_probe: "[[elastic-moe-p2p]]"
target_venue: "当前不投稿；未来若测出具有完整证据链的新机制，使用新名称另建独立提案并重新推导投稿梯度"
tags: [LLM-Serving, MoE, Expert-Parallelism, Elastic-Scaling, P2P-RDMA]
related_papers:
  - "[[MoE-Serving-Tax-MLSys26]]"
  - "[[CRAFT-MLSys26]]"
  - "[[LatencyOptimal-MoELB-INET4AI25]]"
  - "[[Libra-ICLR26]]"
  - "[[UEP-OSDI26]]"
  - "[[UCCL-Tran-OSDI26]]"
  - "[[BlitzScale-OSDI25]]"
  - "[[Aegaeon-SOSP25]]"
related_concepts:
  - "[[MoE]]"
  - "[[Expert-Parallelism]]"
  - "[[RDMA]]"
  - "[[Disaggregation]]"
related_systems:
  - "[[SGLang]]"
  - "[[vLLM]]"
novelty: low
feasibility: medium
effort: high
deprecation_reason: >
  在线 DP/EP 扩缩、专家服务拆分、预测迁移、故障成员修复和 P2P 数据通路
  均已有直接相邻工作；当前没有证据充分、反直觉且不可由这些工作解释的单一核心赌注。
---

# ElasticMoEP2P：多节点 MoE 专家级弹性的归档评估

## 原问题与背景

多节点 MoE 服务会受到专家负载偏斜、权重搬运和固定 EP 成员故障的影响。这个问题是真实的：[[CRAFT-MLSys26]] 讨论显存预算下的专家副本，[[LatencyOptimal-MoELB-INET4AI25]] 把迁移成本纳入均衡目标，[[UEP-OSDI26]] 与 [[UCCL-Tran-OSDI26]] 说明 P2P 数据通路、CPU 代理和跨机架拥塞会直接影响服务结果。

原方向希望通过 P2P RDMA 在线复制、迁移热点专家，并动态调整 DP/EP，在负载变化或局部故障时避免重启整个实例。问题重要，但“动态复制 + P2P + 专家级扩缩”已经不再是空白。

原设想的价值来自三个判断：专家偏斜会持续制造最慢成员；迁移可以隐藏在计算窗口中；把专家作为独立弹性单元会比完整实例扩缩更快。归档不是因为这些判断都错误，而是它们已经分别成为现有系统的设计起点，单纯把三者组合不再形成新的研究问题。

## 为什么归档

[ElasticMoE](https://arxiv.org/abs/2510.02613) 已公开在线 DP/EP 扩缩、P2P 权重搬运和虚拟页重映射；[Expert-as-a-Service](https://arxiv.org/abs/2509.17863) 把专家拆成可独立扩缩的服务；[Director](https://arxiv.org/abs/2607.08782) 与 [FreeBalance](https://arxiv.org/abs/2608.14205) 把预测迁移放入计算窗口；[EEP](https://arxiv.org/abs/2605.10670) 又把故障后的成员、专家覆盖和执行图作为可修复状态。[[MoE-Serving-Tax-MLSys26]] 还给出反例：小批 decode 中的偏斜有时会减少活跃专家，盲目均衡反而可能增加权重流量。

这些工作并不代表所有问题都已解决，但它们分别覆盖了原方案的机制、服务抽象、预测迁移和故障成员。剩余空间主要是统一比较、生产轨迹、P99 分解和二次故障，不足以支撑一个新的“大一统控制器”。把这些组件重新组合，只会得到工程整合而不是新的核心赌注。

证据边界也支持保守归档。ElasticMoE 与 Expert-as-a-Service 仍需逐节复核，Director、FreeBalance 和 EEP 当前主要是摘要证据；这些不足以证明方向永久关闭，却足以说明“首次提出动态专家扩缩”已经不可成立。缺失证据应该推动测量，而不是被当作新颖性。

因此，归档页不再保留旧系统的模块、伪代码和实验路线。那些细节建立在已经过期的新颖性判断上，继续维护只会让读者误以为项目仍处于实施阶段。当前版本只保留问题、证据边界和可客观判定的重启条件。

## 剩余未知与重启条件

仍值得测量三个问题：静态专家方案在真实混合流量中多久失效；偏斜在 prefill 与 decode 中何时帮忙、何时制造最慢成员；复制、迁移、跨层执行和专家服务在同一工作负载下的策略边界是什么。

只有同时满足以下条件才重新立项：

1. 至少三个架构或规模不同的现代 MoE、两类网络拓扑和四类工作负载出现同一策略反转；
2. 反转不能被 CRAFT、ElasticMoE、Director、FreeBalance、EasyBalance 或 EEP 的现有代价与状态模型解释；
3. P99 改善超过由生产 SLO 确定的最小有意义效果（MES），同时有效吞吐、显存和搬运成本不退化；样本量按显著性水平 0.05、功效 0.8 和先导方差确定；
4. 核心论断由 `complete/full-text` 或直接回源全文支撑；`needs-review` 必须先完成复核，`abstract-only` 不得单独支撑；新贡献还须定义现有系统无法表达的状态或正确性语义，而不是多测几个故障。

若只得到策略相图，应作为测量工作发布，并使用新名称；ElasticMoEP2P 保持归档。

最小测量可以从公开模型和可重放路由开始：固定模型、批次、拓扑和请求顺序，同时比较静态副本、预测迁移、跨层执行与专家服务，报告活跃专家、最大成员负载、P2P 字节、P99 词元延迟、有效吞吐和显存。若结果只是“漂移越快，在线方法越好”，现有工作已经能够解释；只有跨模型复现、且现有成本模型无法解释的策略反转才值得重新立项。

## 品味评估

独立评审为 **1/5**。工作负载真实性通过；反直觉性、突破幅度、模型代际独立性和抽象贡献均未通过。归档的核心理由不是问题消失，而是当前候选均被直接覆盖或只剩测量问题。未来发现新的机制规律时，应基于新证据另建 proposal。

*本归档评估基于 [[elastic-moe-p2p]]。*
