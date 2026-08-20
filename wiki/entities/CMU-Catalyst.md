---
type: entity
kind: org
aliases: ["CMU Catalyst", "Catalyst Group", "CMU Catalyst Group", "CMU automated learning systems group"]
status: active
last_updated: 2026-08-20
tags: [ml-systems, compiler, runtime, ai-infra, automated-optimization]
---

# CMU Catalyst

> CMU Catalyst 是跨机器学习、计算机、电子与计算机工程多个院系的联合研究组；本页汇总其官方论文目录和当前项目中可与仓库对应的 12 篇论文。

## 是什么

[CMU 官方介绍](https://www.cs.cmu.edu/news/2026/chen-career-award)称陈天奇领导 Catalyst。根据[Catalyst 官方介绍](https://catalyst.cs.cmu.edu/)，该组织由多个院系的教师与学生共同组成，研究如何自动完成机器学习系统的跨栈优化。

本页的归属依据是 Catalyst [官方论文目录](https://catalyst.cs.cmu.edu/publications.html)，以及[2026 研究峰会（Research Summit）](https://catalyst.cs.cmu.edu/summit.html)中列出的当前项目。将这些来源与仓库论文页的完整标题对应后，当前共有 12 篇在库论文。

## 在库研究版图

### 编译器、内核与 GPU 运行时

- [[Relax-ASPLOS25]] — 在统一中间表示中连接计算图、张量程序、外部库和动态符号形状。
- [[FlashInfer-MLSys25]] — 用可组合模板统一多种 KV 布局、注意力执行和服务调度约束。
- [[EventTensor-MLSys26]] — 把 GPU 同步事件提升为多维张量，生成支持动态依赖的长期驻留巨型内核。
- [[MPK-OSDI26]] — 将整张张量图降成 SM 级任务图，并在单个巨型内核中调度。
- [[LithOS-SOSP25]] — 以线程处理簇粒度调度和透明内核原子化提高共享 GPU 利用率。

### 推理算法与服务运行时

- [[APE-ICLR25]] — 独立预编码多个上下文，并校准并行编码与顺序编码的注意力分布。
- [[MagicDec-ICLR25]] — 在长上下文和大批量下用稀疏 KV 自草稿实现推测解码。
- [[XGrammar-MLSys25]] — 预计算大部分语法合法词元，并与大模型推理重叠执行。
- [[XGrammar2-CAIS26]] — 支持工具调用中的动态语法切换和跨语法子结构复用。
- [[DistCA-MLSys26]] — 把长上下文训练的核心注意力拆到独立服务池，减少流水线拖尾。

### 训练系统与智能体可修改性

- [[GraphPipe-ASPLOS25]] — 保留多分支神经网络的阶段依赖图，联合搜索切分和微批计划。
- [[PithTrain-arXiv26]] — 用紧凑 Python 控制面和可执行操作手册降低编码智能体修改训练框架的成本。

## 关键观察 / 隐含假设

- **观察：自动优化需要保留跨层语义。** [[Relax-ASPLOS25]] 传播符号形状，[[EventTensor-MLSys26]] 和 [[MPK-OSDI26]] 表达细粒度动态依赖；它们都把原本被层级接口截断的信息重新交给编译器或运行时。
- **观察：稳定结构可以显著压缩动态工作。** [[XGrammar-MLSys25]] 预计算语法合法性，[[APE-ICLR25]] 缓存独立上下文，[[MagicDec-ICLR25]] 用稀疏自草稿；共同策略是把稳定部分提前编译或缓存，只在运行时处理剩余变化。
- **观察：内核与服务运行时必须共同理解动态状态。** [[FlashInfer-MLSys25]] 同时处理 KV 布局、负载均衡与 CUDA 图约束，[[LithOS-SOSP25]] 则在内核粒度协调共享 GPU；单个快速内核不足以保证端到端服务更快。
- **观察：智能体改变了软件抽象的成本函数。** [[PithTrain-arXiv26]] 表明，注册表、跨语言扩展和隐式调用会增加编码智能体理解与修改训练框架的成本。
- **假设：专用编译和评测成本可以被重复运行摊销。** 语法编译、模型—GPU 专用任务图和静态流水计划都依赖长期复用；短生命周期或频繁变化的工作负载会削弱收益。

## 演进时间线

- 2025：在库工作覆盖动态编译、注意力模板、结构化生成、推测解码和图流水线训练。
- 2026：研究重点扩展到巨型内核、GPU 共享、面向智能体的训练系统和长上下文训练解聚。

## 相关系统

- [[FlashInfer-MLSys25|FlashInfer]]、[[XGrammar-MLSys25|XGrammar]]、[[Relax-ASPLOS25|Relax]]、[[MPK-OSDI26|MPK]]、[[PithTrain-arXiv26|PithTrain]]

## 相关概念

- [[Flash-Attention]]、[[KV-Cache]]、[[Speculative-Decoding]]、[[MoE]]、[[Pipeline-Parallelism]]、[[CUDA-Graph]]

## 相关论文（在库完整集合）

- 编译与运行时：[[Relax-ASPLOS25]]、[[FlashInfer-MLSys25]]、[[EventTensor-MLSys26]]、[[MPK-OSDI26]]、[[LithOS-SOSP25]]
- 推理系统：[[APE-ICLR25]]、[[MagicDec-ICLR25]]、[[XGrammar-MLSys25]]、[[XGrammar2-CAIS26]]、[[DistCA-MLSys26]]
- 训练系统：[[GraphPipe-ASPLOS25]]、[[PithTrain-arXiv26]]
