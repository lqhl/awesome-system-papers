---
type: entity
kind: org
aliases: ["CMU Catalyst", "Catalyst Group", "CMU Catalyst Group", "CMU automated learning systems group"]
status: active
last_updated: 2026-08-20
tags: [ml-systems, compiler, runtime, ai-infra, automated-optimization]
---

# CMU Catalyst

> CMU Catalyst 是 Carnegie Mellon University 跨机器学习、计算机、电子与计算机工程多个院系的联合研究组，研究如何用编译、运行时和模型—系统协同设计自动完成机器学习系统的跨栈优化。

## 是什么

[CMU 官方介绍](https://www.cs.cmu.edu/news/2026/chen-career-award)称陈天奇领导 Catalyst。根据[Catalyst 官方介绍](https://catalyst.cs.cmu.edu/)，该组织由机器学习系、计算机系和电子与计算机工程系的多位教师与学生共同组成，定位为跨院系的自动化学习系统研究组（automated learning systems group）。

在本仓库中，Catalyst 的路线从编译中间表示、内核和服务运行时延伸到面向智能体的软件。[[Relax-ASPLOS25]] 用符号形状连接计算图、张量程序和外部库；[[FlashInfer-MLSys25]] 把多种 [[KV-Cache|KV 缓存]] 布局与注意力执行统一到可组合模板；[[XGrammar-MLSys25]] 和 [[XGrammar2-CAIS26]] 把结构化生成的语法状态引入推理运行时；[[MPK-OSDI26]] 进一步把整张张量图降到一个长期驻留的图形处理器（graphics processing unit，GPU）巨型内核；[[PithTrain-arXiv26]] 则把代码结构是否易于智能体理解纳入系统评价。

本页依据 Catalyst 官方项目、论文目录和研究活动核验归属。别名不包含裸 `Catalyst`，因为系统文献中还存在同名 GPU 内核卸载方案，使用过宽别名会破坏 Obsidian 的全局名称解析。

## 关键观察 / 隐含假设

- **观察：自动优化需要保留跨层语义，而不是逐层独立调参。** [[Relax-ASPLOS25]] 让符号形状跨计算图、张量中间表示和外部库调用传播；[[MPK-OSDI26]] 把算子依赖细化到流式多处理器（streaming multiprocessor，SM）任务图。两者都把原本被层级接口截断的信息变成优化器输入。
- **观察：结构特化可以减少通用执行开销。** [[XGrammar-MLSys25]] 预计算大部分与上下文无关的合法词元（token，模型一次生成或处理的离散单位），[[XGrammar2-CAIS26]] 再按共享子结构缓存跨语法状态；[[APE-ICLR25]] 则独立预编码多个上下文并校准注意力分布。共同点是先识别稳定结构，再把运行时工作压缩到真正动态的部分。
- **观察：内核与服务运行时必须共同理解动态状态。** [[FlashInfer-MLSys25]] 同时处理 KV 布局、负载均衡与 CUDA Graph（CUDA 图捕获）约束；[[MPK-OSDI26]] 在静态任务图和运行时调度之间折中。单个快速内核不足以保证模型服务端到端更快。
- **观察：智能体改变了软件抽象的成本函数。** [[PithTrain-arXiv26]] 表明，为人类扩展性设计的注册表、跨语言扩展和隐式调用会增加编码智能体的探索成本；紧凑 Python 控制面和可执行操作手册能减少智能体轮次，但不必然减少固定 GPU 工作。
- **假设：规格化和编译成本可以被长期运行摊销。** XGrammar 的语法编译、Relax 的提前编译和 MPK 的模型—GPU—批量专用任务图都依赖重复执行。高度动态、短生命周期或多租户频繁切换的工作负载会削弱这一前提。
- **证据边界：自动化不等于自动获得正确性。** 这些系统仍依赖人工定义的中间表示、等价规则、验证器和目标指标；现有论文主要证明特定模型与硬件上的效率，不证明任意新模型都能无人监督地正确优化。

## 演进时间线

- 2025 ICLR：[[APE-ICLR25]] — 用并行上下文编码和注意力校准加速检索增强生成与上下文学习。
- 2025 MLSys：[[FlashInfer-MLSys25]]、[[XGrammar-MLSys25]] — 分别统一注意力执行模板和结构化生成语法运行时。
- 2025 ASPLOS：[[Relax-ASPLOS25]] — 用跨层符号形状和部分降级连接高层图、张量程序与外部库。
- 2026 OSDI：[[MPK-OSDI26]] — 将张量图降成 SM 级任务图，并在单个长期驻留内核中调度。
- 2026：[[XGrammar2-CAIS26]] — 将结构化生成扩展到动态工具调用和跨语法复用。
- 2026：[[PithTrain-arXiv26]] — 把智能体修改框架的轮次、上下文和 GPU 时间纳入训练系统设计。

## 相关系统

- [[FlashInfer-MLSys25|FlashInfer]]、[[XGrammar-MLSys25|XGrammar]]、[[Relax-ASPLOS25|Relax]]、[[MPK-OSDI26|MPK]]、[[PithTrain-arXiv26|PithTrain]]

## 相关概念

- [[Flash-Attention]]、[[KV-Cache]]、[[Sparse-Attention]]、[[Speculative-Decoding]]、[[MoE]]、[[Pipeline-Parallelism]]

## 相关论文

- [[APE-ICLR25]] — 并行上下文编码和注意力分布校准。
- [[FlashInfer-MLSys25]] — 可组合注意力模板与服务调度约束。
- [[XGrammar-MLSys25]] — 高效、可移植的结构化生成引擎。
- [[Relax-ASPLOS25]] — 支持动态机器学习程序的跨层编译抽象。
- [[MPK-OSDI26]] — 面向张量图的 GPU 巨型内核编译与运行时。
- [[XGrammar2-CAIS26]] — 面向智能体工具调用的动态结构化生成。
- [[PithTrain-arXiv26]] — 面向编码智能体可修改性的紧凑 MoE 训练系统。
