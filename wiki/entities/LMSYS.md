---
type: entity
kind: org
aliases: [LMSYS, "LMSYS Org", "Large Model Systems", "Large Model Systems Organization", "LMSYS Corp."]
status: active
last_updated: 2026-08-20
tags: [llm-systems, open-source, serving, evaluation]
---

# LMSYS

> LMSYS 是由跨校研究协作发展而来的非营利开源组织，围绕开放大模型、推理系统、数据集和评测工具建立公共基础设施；本 wiki 当前最完整覆盖的是其 [[SGLang]] 路线。

## 是什么

[LMSYS 官方介绍](https://www.lmsys.org/about/)将组织全称写为 Large Model Systems，并说明它于 2023 年从 UC Berkeley、Stanford、UCSD、CMU 和 MBZUAI 的协作中产生，2024 年 9 月注册为非营利组织。它不是单一大学实验室，也不能用某一所学校的作者单位替代；组织身份更接近开源项目的孵化、维护和社区协作载体。

LMSYS 的公开项目覆盖模型、服务引擎和评测平台。本仓库目前有充分论文证据的是 [[SGLang-NeurIPS24]]：它把语言模型程序的前端结构与推理运行时联合设计，以 [[RadixAttention]] 管理跨调用共享前缀，并将结构化生成约束下沉到执行路径。FastChat、Vicuna、Chatbot Arena 和 RouteLLM 尚无对应论文 wiki 页，因此本页只把它们作为官方项目背景，不替代后续单篇收录。

LMSYS 与 [[Sky-Computing-Lab|Berkeley Sky Computing Lab]] 存在人员和项目重叠，但二者边界不同：Sky Computing Lab 是 Berkeley 的阶段性协作实验室，LMSYS 则是跨机构发起、后来独立注册的非营利组织。[[SGLang]] 同时出现在双方官方项目页面，不能据此把两个组织合并，也不能把双方所有论文相互归属。

## 关键观察 / 隐含假设

- **观察：开源组织的贡献不只是一篇起点论文。** [[SGLang-NeurIPS24]] 定义了 RadixAttention、前端提示和运行时协同的初始设计；后续模型支持、硬件适配、确定性执行和生产问题修复主要通过持续维护发生。阅读组织页时，应区分经过论文评审的结论与官方博客或工程发布中的版本性结果。
- **观察：复杂语言模型程序需要跨请求保存结构。** [[SGLang-NeurIPS24]] 发现智能体、少样本提示和分支—求解—合并程序会反复使用公共前缀，因而把 [[KV-Cache|KV 缓存]] 从单请求临时状态提升为跨调用索引对象；这条路线构成 LMSYS 当前系统工作的核心之一。
- **观察：前端语义只有进入运行时才会转化为系统收益。** 分支（fork）、共享前缀和结构化输出约束若只停留在应用层，运行时仍会重复计算；SGLang 让前端提供复用提示，并让压缩状态机一次跳过多个确定词元（token，模型一次生成或处理的离散单位）（[[SGLang-NeurIPS24]]）。
- **假设：开放社区可以在保持兼容性的同时持续吸收硬件特定优化。** SGLang 需要接入不同模型、注意力后端和加速器，同时保留统一服务接口。这个假设支持快速扩展，却也使任意论文中的版本、后端和开关成为性能比较的必要边界（[[SGLang]]）。
- **归属边界：共同作者不等于组织所有权。** 本页只把 LMSYS 官方列出的项目或明确以 LMSYS 名义发布的工作归入组织演进；仅因成员参与的外部合作论文不会自动列入。

## 演进时间线

- 2023：LMSYS 以跨校协作形式出现，围绕开放模型、服务与评测基础设施开展项目；该组织沿革来自[官方介绍](https://www.lmsys.org/about/)。
- 2024 NeurIPS：[[SGLang-NeurIPS24]] — 将结构化语言模型程序、跨调用前缀复用和约束生成整合成前端—运行时协同系统。
- 2024：LMSYS 注册为非营利组织，组织角色从研究协作扩展到开源项目孵化和社区治理。
- 2025–2026：SGLang 持续扩展模型、硬件和生产执行能力；这些变化属于工程演进，具体性能结论需回到对应版本和公开复现实验。

## 相关系统

- [[SGLang]] — LMSYS 当前最主要、且在本仓库有论文与长期实体页双重覆盖的推理系统。

## 相关概念

- [[LLM-Inference]]、[[KV-Cache]]、[[Prefix-Caching]]、[[RadixAttention]]、[[Continuous-Batching]]

## 相关论文

- [[SGLang-NeurIPS24]] — 本仓库中 LMSYS 系统路线的主要论文证据，定义前端—运行时协同与 RadixAttention。
