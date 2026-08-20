---
type: entity
kind: org
aliases: ["Berkeley Sky Computing Lab", "Sky Computing Lab", "Sky Lab", "UC Berkeley Sky Computing Lab"]
status: active
last_updated: 2026-08-20
tags: [cloud-computing, distributed-systems, ai-infra, open-source]
---

# Berkeley Sky Computing Lab

> Berkeley Sky Computing Lab 是 UC Berkeley 面向数据密集型系统的协作实验室；在本 wiki 中，它把“跨云资源成为可替换公共设施”的愿景推进到大模型推理、训练和开放系统基础设施。

## 是什么

[Sky Computing Lab 官方介绍](https://sky.cs.berkeley.edu/)将自身定位为 Berkeley 数据密集型系统研究的下一阶段，目标是降低应用对单一云厂商的绑定。它延续 AMPLab 和 RISELab 的阶段性协作模式，研究范围横跨分布式系统、安全、编程语言和机器学习（machine learning，ML），而不是只做大模型服务。

本仓库覆盖最密集的是人工智能系统路线。[[vLLM-SOSP23]] 从单机图形处理器（graphics processing unit，GPU）的 [[KV-Cache|KV 缓存]] 分页开始；[[SkyServe-EuroSys25]] 和 [[RLBoost-NSDI26]] 把资源选择扩到跨区域抢占式实例；[[NEO-MLSys25]]、[[MoE-Lightning-ASPLOS25]] 和 [[SuperServe-NSDI25]] 分别利用闲置主机处理器、分层内存和可快速切换的子模型；[[BlendServe-ASPLOS26]] 又把请求排序与 GPU 资源互补放到同一调度问题中。

实验室与 [[LMSYS]] 并非上下级关系。[[SGLang-NeurIPS24]] 同时出现在双方官方页面，反映跨组织协作和项目治理的重叠；本页只依据 Sky 官方项目、论文目录或论文明确归属收录，不因 Ion Stoica、Matei Zaharia 等成员署名而自动吸收所有合作论文。

## 关键观察 / 隐含假设

- **观察：资源浪费在不同层次反复出现。** [[vLLM-SOSP23]] 测得连续预分配让大部分 KV 显存闲置；[[NEO-MLSys25]] 利用推理时闲置的主机处理器；[[SkyServe-EuroSys25]] 和 [[RLBoost-NSDI26]] 则利用跨故障域的廉价抢占式资源。共同方法是先找出未被现有抽象表达的剩余容量，再重写调度或状态迁移边界。
- **观察：云资源可替换性必须建立在状态可移动之上。** SkyServe 需要跨区域复制和按需回退，RLBoost 需要保存并迁移词元级生成状态；若模型权重、KV 状态或训练角色仍与单台机器绑定，跨云选择只会停留在部署脚本层（[[SkyServe-EuroSys25]]、[[RLBoost-NSDI26]]）。
- **观察：统一服务接口掩盖不了工作负载差异。** [[SuperServe-NSDI25]] 面向可切换精度—延迟点，[[BlendServe-ASPLOS26]] 面向可离线重排请求，[[SGLang-NeurIPS24]] 面向有程序结构和共享前缀的调用。它们不能用一个“吞吐最高”结论排序。
- **观察：开放系统既是贡献，也是后续研究的实验底座。** [[vLLM]] 和 [[SGLang]] 被大量论文作为基线或宿主；这提高了研究可接入性，也意味着版本、后端和本地修改会直接改变结论。
- **假设：跨层复杂性可以被较小的公共抽象封装。** 分页块、前缀树、子模型激活和词元级迁移都试图让上层保留简单接口。硬件异构、故障恢复和多租户隔离越强，这个假设越需要端到端证据而非单点微基准。

## 演进时间线

- 2023 SOSP：[[vLLM-SOSP23]] — 用 [[PagedAttention]] 把动态 KV 状态变成可分页、可共享的服务内存对象。
- 2024 NeurIPS：[[SGLang-NeurIPS24]] — 将语言模型程序结构、前缀复用和运行时调度协同设计。
- 2025 MLSys、ASPLOS：[[NEO-MLSys25]]、[[MoE-Lightning-ASPLOS25]] — 分别利用主机处理器执行注意力，以及主机处理器、GPU 与 PCI Express（PCIe）互连流水重叠来扩展单机推理容量。
- 2025 EuroSys、NSDI：[[SkyServe-EuroSys25]]、[[SuperServe-NSDI25]] — 把系统控制面扩到跨云实例选择和按批次模型切换。
- 2026 ASPLOS、NSDI：[[BlendServe-ASPLOS26]]、[[RLBoost-NSDI26]] — 分别研究离线请求重排，以及强化学习生成阶段在抢占式资源上的迁移。

## 相关系统

- [[vLLM]] — 从 KV 内存管理起步，成为通用大模型服务引擎和研究底座。
- [[SGLang]] — 以语言模型程序为对象，把前端结构与服务运行时连接起来。

## 相关概念

- [[LLM-Inference]]、[[KV-Cache]]、[[PagedAttention]]、[[Prefix-Caching]]、[[Disaggregation]]、[[MoE]]

## 相关论文

- [[vLLM-SOSP23]] — 分页式 KV 内存管理路线的起点。
- [[SGLang-NeurIPS24]] — 程序结构感知的推理运行时。
- [[NEO-MLSys25]] — 利用主机 CPU 扩展在线推理容量。
- [[MoE-Lightning-ASPLOS25]] — 面向显存受限 GPU 的 MoE 分层流水。
- [[SkyServe-EuroSys25]] — 跨区域和跨云抢占式模型服务。
- [[SuperServe-NSDI25]] — 面向不可预测负载的细粒度模型切换。
- [[BlendServe-ASPLOS26]] — 联合优化前缀复用与 GPU 资源互补的离线调度。
- [[RLBoost-NSDI26]] — 在抢占式资源上弹性执行强化学习生成阶段。
