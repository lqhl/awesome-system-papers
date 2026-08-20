---
type: entity
kind: org
aliases: ["Berkeley Sky Computing Lab", "Sky Computing Lab", "Sky Lab", "UC Berkeley Sky Computing Lab"]
status: active
last_updated: 2026-08-20
tags: [cloud-computing, distributed-systems, ai-infra, open-source]
---

# Berkeley Sky Computing Lab

> Berkeley Sky Computing Lab 是 UC Berkeley 面向数据密集型系统的协作实验室；本页汇总其官方论文目录和项目页中可与仓库对应的 24 篇论文。

## 是什么

[Sky Computing Lab 官方介绍](https://sky.cs.berkeley.edu/)将自身定位为 Berkeley 数据密集型系统研究的下一阶段，目标是降低应用对单一云厂商的绑定。研究范围横跨分布式系统、安全、编程语言和机器学习，而不只是大模型服务。

本页以[官方论文目录](https://sky.cs.berkeley.edu/publications/)和项目页为归属依据，并与仓库论文页的完整标题对应。目录中的 SkyLB、Autellix 和 UCCL-EP 在仓库中分别对应 [[SkyWalker-EuroSys26]]、[[Agentix-NSDI26]] 和 [[UEP-OSDI26]]。当前共有 24 篇在库论文；其中 SGLang 同时出现在非营利组织 LMSYS 的官方项目列表。

## 在库研究版图

### 大模型推理、训练与资源管理

- [[vLLM-SOSP23]] — 用 [[PagedAttention]] 把动态 KV 状态变成可分页、可共享的服务内存对象。
- [[SGLang-NeurIPS24]] — 用 RadixAttention 和前端—运行时协同执行结构化语言模型程序。
- [[NEO-MLSys25]] — 将部分注意力和 KV 状态卸载到闲置主机处理器，扩展单机在线推理容量。
- [[MoE-Lightning-ASPLOS25]] — 在显存受限 GPU 上重叠专家权重传输、注意力和专家计算。
- [[Jenga-SOSP25]] — 用层属性接口联合管理异构模型的内存和前缀缓存。
- [[PrefillOnly-SOSP25]] — 针对只生成一个词元的工作负载移除通用解码引擎的多余状态管理。
- [[SuperServe-NSDI25]] — 在共享权重的子模型之间快速切换，处理不可预测负载。
- [[BlendServe-ASPLOS26]] — 联合优化离线请求的前缀复用与 GPU 计算、内存资源互补。
- [[Prism-OSDI26]] — 以 GPU 内存气球统一共享模型权重、KV 状态和执行时间。
- [[SparseSpec-MLSys26]] — 用同一推理模型的稀疏注意力路径做自推测解码。
- [[SpecDecodeBench-MLSys26]] — 在生产级 vLLM 上测量推测解码的收益边界和理论上限。
- [[DistCA-MLSys26]] — 把长上下文训练的核心注意力拆到独立服务池，减少流水线拖尾。
- [[SkyServe-EuroSys25]] — 利用跨区域抢占式实例的低相关性降低模型服务成本。
- [[SkyWalker-EuroSys26]] — 利用区域日周期错峰，并以跨区域前缀感知路由维持 KV 局部性。
- [[Agentix-NSDI26]] — 将智能体程序进度纳入抢占与优先调度，减少两层队首阻塞。
- [[RLBoost-NSDI26]] — 把强化学习生成阶段迁移到抢占式资源，并保留词元级中间状态。
- [[UCCL-Tran-OSDI26]] — 保留网卡数据面，将拥塞控制和路径选择移到可编程主机软件。
- [[UEP-OSDI26]] — 用主机代理屏蔽不同 GPU 与网卡的专家并行通信差异。

### 数据、检索与复合系统优化

- [[LLMQueryReordering-MLSys25]] — 重排行与字段，使批量关系分析中的大模型调用复用更多前缀。
- [[LEANN-MLSys26]] — 查询时重算嵌入，以很小的存储索引完成检索增强生成。
- [[GEPA-ICLR26]] — 用运行轨迹和评估反馈反思式演化提示词，扩展到复合人工智能系统优化。

### 安全与分布式协议

- [[Compass-OSDI25]] — 在环形不经意随机存取存储上执行加密嵌入图搜索。
- [[Pesto-SOSP25]] — 用按需快照和语义并发控制支持无需全序的拜占庭容错数据库查询。
- [[Picsou-OSDI25]] — 以累计确认原语降低复制状态机之间的通信成本。

## 关键观察 / 隐含假设

- **观察：资源浪费在不同层次反复出现。** [[vLLM-SOSP23]] 找到 KV 显存碎片，[[NEO-MLSys25]] 利用闲置主机处理器，[[SkyServe-EuroSys25]] 和 [[RLBoost-NSDI26]] 利用跨故障域的抢占式容量。共同方法是先找出未被现有抽象表达的剩余资源，再重写状态和调度边界。
- **观察：云资源可替换性必须建立在状态可移动之上。** SkyServe 迁移模型副本，SkyWalker 迁移或预推送前缀状态，RLBoost 保存生成状态；若权重、KV 或训练角色仍与单机绑定，跨云选择只能停留在部署层（[[SkyServe-EuroSys25]]、[[SkyWalker-EuroSys26]]、[[RLBoost-NSDI26]]）。
- **观察：前缀和程序结构逐渐成为公共调度信号。** [[SGLang-NeurIPS24]]、[[LLMQueryReordering-MLSys25]]、[[BlendServe-ASPLOS26]] 和 [[Agentix-NSDI26]] 分别在单请求、批处理和智能体程序层利用结构信息，说明请求不应只被视为独立词元流。
- **观察：实验室路线并不限于人工智能基础设施。** [[Compass-OSDI25]]、[[Pesto-SOSP25]] 和 [[Picsou-OSDI25]] 延续了隐私与容错协议研究；这些论文与推理系统共享“把昂贵全局协调改成小而可组合的状态”的方法，但指标不可混合比较。
- **假设：开放系统可以作为稳定研究底座。** [[vLLM]] 和 [[SGLang]] 被大量后续论文修改或比较；版本、后端和本地补丁因此是解释性能数字的必要条件。

## 演进时间线

- 2023–2024：[[vLLM-SOSP23]]、[[SGLang-NeurIPS24]] 建立分页 KV 管理和程序结构感知运行时。
- 2025：研究范围扩到主机卸载、异构内存、跨云服务、数据库和安全协议。
- 2026：工作重点进一步延伸到智能体服务、强化学习弹性、长上下文训练和可移植 GPU 通信。

## 相关系统

- [[vLLM]]、[[SGLang]]

## 相关概念

- [[LLM-Inference]]、[[KV-Cache]]、[[PagedAttention]]、[[Prefix-Caching]]、[[Disaggregation]]、[[MoE]]、[[RDMA]]

## 相关论文（在库完整集合）

- 推理与训练：[[vLLM-SOSP23]]、[[SGLang-NeurIPS24]]、[[NEO-MLSys25]]、[[MoE-Lightning-ASPLOS25]]、[[Jenga-SOSP25]]、[[PrefillOnly-SOSP25]]、[[SuperServe-NSDI25]]、[[BlendServe-ASPLOS26]]、[[Prism-OSDI26]]、[[SparseSpec-MLSys26]]、[[SpecDecodeBench-MLSys26]]、[[DistCA-MLSys26]]
- 云与智能体系统：[[SkyServe-EuroSys25]]、[[SkyWalker-EuroSys26]]、[[Agentix-NSDI26]]、[[RLBoost-NSDI26]]、[[UCCL-Tran-OSDI26]]、[[UEP-OSDI26]]
- 数据与复合系统：[[LLMQueryReordering-MLSys25]]、[[LEANN-MLSys26]]、[[GEPA-ICLR26]]
- 安全与协议：[[Compass-OSDI25]]、[[Pesto-SOSP25]]、[[Picsou-OSDI25]]
