---
type: paper
name: Murakkab
full_title: "Murakkab: Resource-Efficient Agentic Workflow Orchestration in Cloud Platforms"
authors: [Gohar Irfan Chaudhry, Esha Choukse, Haoran Qiu, Íñigo Goiri, Rodrigo Fonseca, Adam Belay, Ricardo Bianchini]
venue: OSDI
year: 2026
tags: [agentic-workflows, cloud-orchestration, profile-guided-optimization, resource-management, slo]
source_pdf: "[[osdi26-chaudhry.pdf]]"
source_md: "[[osdi26-chaudhry]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 面向云平台的资源高效智能体工作流编排（OSDI 2026）

> **原题**：Murakkab: Resource-Efficient Agentic Workflow Orchestration in Cloud Platforms

> **一句话总结**：智能体工作流把模型、工具和控制流暴露成彼此割裂的调用，Murakkab 将其声明为可优化的 DAG，并用 profile-guided optimizer、运行时自动扩缩容和跨工作流复用联合选择工作流配置、模型与硬件；在 Azure trace 上相对 LangGraph 最多减少 2.8× GPU、3.7× 能耗和 4.3× 成本，同时满足质量与延迟 SLO。

## 问题与动机

现有 LangGraph、LlamaIndex 等框架要求开发者同时决定工作流结构、每个 agent 使用的模型与参数，以及 CPU/GPU 和并行度。云平台看到的通常只是孤立的模型请求，无法根据完整的数据依赖和控制流调整部署。开发者因此很难针对准确率、延迟、能耗和成本做端到端取舍。

论文把 agentic workflow 视为由多个模型和工具组成的计算图。Video Q/A 包含场景检测、抽帧、语音转写、目标检测和多模态回答；代码生成则包含多轮辩论、测试和执行。不同请求的中间输出长度和执行路径差异很大，固定配置会在简单请求上浪费资源，在困难请求上又可能达不到质量目标。

## 关键观察 / 隐含假设

- **观察 1：工作流级和 agent 级旋钮共同改变质量与负载。** Video Q/A 中启用语音转写、抽取帧数和回答模型都会改变准确率；代码生成中辩论者数量、轮数和模型选择也会改变准确率。DeepSeek-Qwen-32B 在代码生成中位数约生成 20,000 tokens，Gemma-3-27B 约为 2,500 tokens（图 2）。
  - **依赖假设**：这些配置的质量和 token 负载可由代表性数据集或生产反馈建立 profile。
  - **可能失效场景**：新领域、输入分布漂移或工具行为改变后，profile 可能无法预测质量与负载。
- **观察 2：硬件配置不存在单一最优点。** 不同模型在 GPU 类型、并行度和负载下有不同的 TTFT、TPOT、吞吐和能效曲线（图 3）。因此模型选择与硬件选择必须联合优化。
  - **依赖假设**：云平台可以获得足够准确且可复用的模型 profile，并能及时获得资源可用性。
- **观察 3：agentic workflow 的负载具有重尾和动态控制流。** Video Q/A 中同一配置的 token 量可从约 250 到接近 1,000；LLaVA-OneVision-7B 的示例在 P50/P99 约为 600/1,200 tokens。论文用较长期优化器处理趋势，用短窗口自动扩缩容吸收偏差。
  - **可能失效场景**：突发流量持续时间超过扩缩容和模型加载时间时，预留资源仍可能不足；过度保守又会抵消节省。

## 核心方法

Murakkab 将开发者给出的任务和依赖转换为逻辑工作流 DAG。每个 executor 可以是 LLM、结构化模型组合或工具。executor 暴露描述、接口和可调参数，工作流声明不绑定具体模型、硬件或资源数量。编排器使用带工具调用能力的 LLM 做任务到 executor 的映射，并做类型检查。

系统分别维护 workflow profiles 和 model profiles。前者记录工作流配置的准确率及 prompt/completion token 分布，后者记录模型在不同 GPU、并行度和负载下的 TTFT、TPOT、能耗和成本。两类 profile 分离，使新模型可以接入已有工作流，但结论仍取决于 profile 是否覆盖目标输入分布。

优化器把每个工作流-SLO 组合、候选配置、模型 profile、预测到达率和资源预算输入 MILP。它联合决定工作流旋钮、executor 对应的模型或工具、实例数量及路由比例。目标可以是最小能耗、最小成本，或在成本预算下最大化准确率。实例数按预测峰值配置，路由按平均负载优化，以支持跨工作流多路复用。

运行时每 60 分钟重新优化，并由自动扩缩容器在秒到分钟级监控实例负载。负载显著偏离预测时提前触发优化。DAG 可见性还允许系统选择 CPU/GPU 混合执行：例如图 12 中将 OmDet 放到 GPU、Whisper 放到 CPU，在满足 30 秒延迟 SLO 的同时比两者都放 GPU 少用一张 A100。

## 设计取舍

- **集中控制换取全栈效率**：平台获得重配置模型、工具和硬件的权限，减少手工调优，但开发者对具体执行路径的控制变弱，且错误的 executor 映射或 profile 会直接影响结果。
- **MILP 的全局规划换取优化延迟**：联合考虑多租户复用和资源预算，代价是每个优化 epoch 都要求解组合问题。论文使用 Gurobi，时间上限为 300 秒；短期突发仍交给自动扩缩容。
- **声明式抽象换取适应性**：工作流逻辑与执行配置解耦，便于模型和硬件替换；代价是需要维护 executor 库、类型接口、评测数据和持续 profile 更新。
- **峰值预留与平均复用并存**：该策略兼顾 SLO 和利用率，但预测错误会带来过度配置或请求丢弃。论文的优化周期敏感性实验显示约 60 分钟在其设置下最平衡，不能直接视为普适参数（图 13）。

## 实验与结果

- 在 Azure 的 A100/H100 VM 上，使用 vLLM、speachesai 和 OmDet，并将 24 小时 Azure LLM serving trace 映射到 Video Q/A 与代码生成工作流。
- 多工作流实验中，Murakkab 加跨工作流复用需要 912 张 A100，相比单独优化的 1,164 张减少 21.6%；能耗从 27.7 MWh 降至 22.1 MWh，成本从 57,224 美元降至 47,238 美元（表 2）。
- 单工作流中，Video Q/A 的准确率从 best 的 66.2% 放宽到 good 的 64.4% 时，能耗从 5.1 MWh 降至 3.9 MWh；成本从 18.5k 美元降至 14.3k 美元。准确率降至 61.4% 时成本约 6.9k 美元（图 7）。
- 代码生成的 best 到 good 准确率 SLO 切换模型后，能耗约下降 10.5×、成本约下降 8.7×（图 8）。动态 coding pipeline 在 LiveCodeBench-v5 上显示 cost-accuracy 前沿跨越约一个数量级 completion tokens，review 阶段对不同模型和任务组合并非总有益（图 10）。
- 当 H100 可用量从 0 增至 495 张时，Murakkab 将能耗从 24.7 MWh 降至 11 MWh，同时减少 A100 使用（表 3）。Math Q/A 与代码生成的组合实验相对静态基线约减少 2.7× GPU、3.2× 能耗和 3.5× 成本（表 4）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 联合优化工作流、模型和资源能减少多租户资源开销 | 表 2：912 vs. 1,164 张 A100，成本 47,238 vs. 57,224 美元 | 两类工作流、24 小时 Azure trace、A100/H100 VM | 强 |
| 放宽质量 SLO 可换来数量级成本/能耗变化 | 图 7、图 8：Video Q/A 成本约 4×，代码生成能耗约 10.5× | 论文构造的 Video Q/A、代码生成配置与固定 SLO tiers | 中 |
| profile 可迁移到未见输入 | 图 14：Math-500 profile 与 MathEval test 的准确率和 token 分布趋势相近 | 数学工作流、相近领域的两个 benchmark | 中 |
| 60 分钟优化周期平衡适应性和转换开销 | 图 13：20 分钟至 6 小时敏感性分析 | 假设实例启动和模型传输需 20 分钟，EWMA α=0.5 | 中 |

## 批判性分析

### 论证链条

论文的主链条较完整：配置空间存在质量-资源前沿，声明式 DAG 暴露跨层结构，profile 将候选配置转成可计算的负载和性能，MILP 选择部署计划，运行时再处理短期波动。多工作流复用和 DAG 调度实验分别验证了全局视图的收益。

但最强的 2.8×、3.7×、4.3× 汇总数字来自特定 trace 映射和手工 LangGraph 基线。实验没有展示真实 agent 生产 trace，也没有系统比较更强的自适应工作流规划器。因而结果更直接支持“在论文设定下联合优化有效”，不足以证明所有云端 agent 平台都能达到相同收益。

### 假设压力测试

profile 假设是主要脆弱点。输入分布、模型版本、提示词、工具耗时或外部 API 限流变化，都会使准确率和 token 分布过时。论文用 Math-500 到 MathEval 的迁移实验提供了一个相近领域的正例，但没有覆盖跨领域或长期漂移。

MILP 使用预测到达率和第 90 百分位 token 负载，自动扩缩容负责剩余波动。持续突发、相关性很强的多租户峰值，或模型加载时间超过 20 分钟时，这一分工可能造成 SLO 违约。论文也没有报告重配置期间请求如何排队、迁移或保持 KV cache。

### 实验可信度

硬件、软件版本、工作负载和主要指标均有说明，且包含模型切换、资源可用性、优化周期、未见 benchmark 和 DAG 调度实验。局限在于生产 trace 只提供到达模式，工作流输入和质量映射是论文构造的；成本与能耗主要由 profile 推演，不是完整云端部署的实测账单。LangGraph 基线是手工配置，公平性和代表性仍影响绝对收益。

### 系统性缺陷

论文未详细讨论故障恢复、配置回滚、租户隔离、profile 版本管理、模型下载期间的服务连续性，以及外部模型 API 的错误和限流。使用 LLM 编排器将自然语言任务映射到 executor 还引入了映射错误和可复现性问题，类型检查只能发现接口不匹配，不能保证任务语义正确。MILP 在规模更大的 workflow、模型和租户集合上的求解时间也未评估。

## 局限与后续工作

- **局限 1**：评测使用 Azure LLM trace 的到达模式，而非完整生产 agent trace；输入分布、工具调用和执行失败模式的真实性有限。
- **局限 2**：质量 profile 依赖 benchmark、开发者数据或用户反馈，论文没有给出 profile 更新、漂移检测和错误配置回滚机制。
- **局限 3**：优化周期和 20 分钟实例启动假设限制了对快速变化负载的结论；应测量不同启动时间、突发形状和预测器下的 P99 SLO 违约率。
- **后续工作 1**：在多租户真实 DAG trace 上比较 Murakkab 与自适应路由、工作流规划和资源调度系统，分别报告求解时间、重配置开销、请求排队、P99 延迟和质量漂移。
- **后续工作 2**：为 profile 增加置信区间与在线校准，在检测到预测误差超过阈值时自动降级、回滚或切换到安全配置。

## 相关

- **相关概念**：[[Agent-Systems]]、[[LLM-Serving]]、[[Profile-Guided-Optimization]]、[[SLO]]、[[DAG-Scheduling]]
- **同类系统**：[[LangGraph]]、[[vLLM]]、[[Parrot]]、[[Autellix]]、[[Loki]]
- **同会议**：[[OSDI-2026]]
