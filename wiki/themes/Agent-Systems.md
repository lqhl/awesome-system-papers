---
type: theme
topic: Agent-Systems
theme_kind: area
member_tag: area/agent-systems
candidate_tags: [agent-runtime, agent-serving, agentic-workflow, agent-memory, agent-skills, agent-security, software-agent, tool-calling]
paper_count: 14
first_generated: 2026-08-19
last_updated: 2026-08-19
tags: [topic-overview, agent-systems, llm-agent, runtime, memory, orchestration]
---

# 智能体系统（Agent-Systems）综述

> 智能体系统把智能体视为带工具、状态、依赖和外部副作用的程序，而不是一串彼此独立的大语言模型（Large Language Model，LLM）请求；核心问题是如何提供可移植执行、持久状态、程序级调度、资源编排、安全观测和可恢复的正确性边界。

## 定义与边界

进入核心集合的论文必须以可复用系统机制为主要贡献，并显式利用至少一种智能体语义：多轮模型调用、工具执行、程序依赖、持久状态、多智能体通信、运行时反馈或外部副作用。仅把普通模型服务、检索增强生成（Retrieval-Augmented Generation，RAG）、工作流或模型训练称为智能体，不足以进入本主题。

本主题聚焦执行与部署平面，包括运行时（runtime）、软件开发工具包（Software Development Kit，SDK）、隔离沙箱（sandbox）、工具协议、技能可移植性、智能体程序服务、工作流编排、记忆与状态、安全检测和执行期缓存。智能体强化学习训练、轨迹生成和模型更新仍归 [[AI-Infra]]；AI Scientist、量化投研智能体等以应用结果为主要贡献的系统分别归 [[Auto-Research]]、[[Finance]]。若把智能体替换成无状态的单次请求后，论文的主要机制与实验仍基本不变，它通常也不应进入本主题。

本主题与 AI-Infra 有意重叠：部分论文同时管理图形处理器（Graphics Processing Unit，GPU）、键值缓存（Key-Value Cache，KV Cache）或编译器与运行时，但它们被纳入本主题，是因为系统已经利用程序身份、智能体间依赖、技能及其执行框架、工具链或长期状态。状态失效、重启恢复和副作用的统一诊断见 [[Long-Horizon-Agents|长程智能体可靠性]]。

## 阅读提示

- **运行时**负责程序执行期间的调度、状态和资源管理；**控制面（control plane）**负责策略选择、监测与异常处理，通常比实际执行所在的数据路径更慢、更昂贵。
- **快路径（fast path）**处理常见且可预测的情况；遇到失效或不确定状态时回退到慢路径，以更高成本换取校验或重新规划。
- **可重放（replay）**指依据历史事件恢复执行；**崩溃一致性（crash consistency）**要求系统中断后恢复到可解释状态，避免丢失或重复外部副作用。
- 服务级目标（Service-Level Objective，SLO）是系统对延迟、可用性或正确性作出的可测承诺；P99 表示 99% 请求都不超过的尾延迟。
- 应用程序接口（Application Programming Interface，API）供程序调用外部能力；中央处理器（Central Processing Unit，CPU）执行通用计算。高带宽显存（High Bandwidth Memory，HBM）、动态随机存取存储器（Dynamic Random-Access Memory，DRAM）和非易失性存储协议（Non-Volatile Memory Express，NVMe）在表中代表由快到慢的存储层级。
- F1 是精确率与召回率的调和平均值；归一化折损累计增益（normalized discounted cumulative gain，nDCG）衡量排序结果把相关项目放在前面的程度。

## 核心论文

### 平台、技能、工具协议与安全观测（6 篇）

- [[Cordis-TechReport26|Cordis]] — 把组件副作用撤销与依赖重连统一为可撤销效应、反应式协效应和 fiber 生命周期；Koishi 提供采用证据，DeepSeek Harness 则是直接的智能体运行时落地。
- [[OpenHands-ICLR25|OpenHands]] — 用 CodeAct、事件流和 Docker 沙箱统一智能体、运行时、用户界面与评测，展示同一通用平台跨软件、浏览和知识任务的可复用性。
- [[OpenHands-SDK-MLSys26|OpenHands SDK]] — 将单体平台重构为采用事件溯源（event sourcing，即按顺序保存状态变化事件）的 SDK，以不可变组件、单一 ConversationState、可选沙箱和统一的本地或远程工作空间支撑生产集成。
- [[SkVM-SOSP26|SkVM]] — 把技能视为面向模型、执行框架和环境编译的程序，通过预先编译（ahead-of-time，AOT）、即时编译（just-in-time，JIT）、环境绑定和代码固化改善跨目标可移植性。
- [[XGrammar2-CAIS26|XGrammar-2]] — 将请求内外的语法切换、子结构复用和词元掩码变成智能体工具调用协议的运行时能力。
- [[ADR-MLSys26|ADR]] — 关联用户提示、智能体推理、模型上下文协议（Model Context Protocol，MCP）工具与环境遥测，以两级检测和离线红队测试支持企业智能体安全运营。

### 服务、调度与工作流编排（4 篇）

- [[Agentix-NSDI26|Agentix]] — 把包含多次调用的智能体程序而非单个请求作为调度单位，用调用进度和抢占缓解请求级与程序级的队首阻塞。
- [[FlashAgents-MLSys26|FlashAgents]] — 利用多智能体的生产者—消费者词元依赖，重叠上游解码与下游增量预填充，并复用同一轮共享的前缀。
- [[Murakkab-OSDI26|Murakkab]] — 以声明式有向无环图（Directed Acyclic Graph，DAG）、两层画像、混合整数线性规划（Mixed-Integer Linear Programming，MILP）和自动扩缩容，联合选择工作流参数、模型、工具、硬件与路由。
- [[Matrix-MLSys26|Matrix]] — 用消息携带状态、无状态 Ray 执行单元和行级调度，去掉大规模多智能体工作流的中心编排器。

### 记忆、状态与执行期缓存（4 篇）

- [[HIPPOCAMPUS-MLSys26|HIPPOCAMPUS]] — 以词元编号流、语义二进制签名和动态小波矩阵（Dynamic Wavelet Matrix）构建压缩域长期记忆。
- [[Tag2Graph-MLSys26|Tag2Graph]] — 用在线偏好本体、图与稠密向量的一致性和动态路由器，恢复跨会话的隐式用户状态。
- [[AgenticCache-MLSys26|AgenticCache]] — 将高频计划转移放入缓存快路径，由后台模型更新器异步确认、纠错和替换失效计划。
- [[CacheSlide-FAST26|CacheSlide]] — 针对智能体提示中相对顺序稳定、绝对位置漂移的片段，联合分块上下文位置编码（Chunked Contextual Position Encoding，CCPE）、加权修正注意力（Weighted Correction Attention，WCA）与 SLIDE 键值缓存溢写机制，优化跨位置复用。

## 主题综述

### 系统抽象从请求上升到程序

Cordis 把组件的副作用、依赖和生命周期提升为运行时对象；OpenHands 的事件流和 OpenHands SDK 的 ConversationState 暴露完整执行历史，XGrammar-2 暴露动态工具调用语法，Agentix 为请求补充程序身份和进度，FlashAgents 暴露生产者—消费者词元依赖，Murakkab 直接把工作流表达为有向无环图，Matrix 则把状态随消息传递到无状态执行单元。抽象越接近完整程序，系统越能优化关键路径、调度和恢复；代价是框架埋点、版本兼容和应用语义耦合都会增加。

### 智能体状态不是一种数据

组件效应要求可撤销和依赖有序卸载；执行日志要求顺序、重放和崩溃一致性；长期记忆要求检索、更新、删除与租户隔离；计划缓存要求失效检测和安全回退；键值缓存还绑定模型、分词器、位置编码与提示模板。Cordis、OpenHands SDK、HIPPOCAMPUS、Tag2Graph、AgenticCache 和 CacheSlide 管理的是不同生命周期，不能把它们统一塞进长上下文后便认为状态问题已经解决。

### 快路径与慢控制面成为共同结构

SkVM 用预先编译、即时编译的多个版本和固化代码减少重复推理，ADR 用便宜的初筛判断哪些会话需要深度调查，Murakkab 用离线画像支撑周期性全局优化，Tag2Graph 把本体校验移出在线服务热路径，AgenticCache 用缓存执行并由异步模型纠错。它们共同假设常见工作负载具有稳定结构；真正未解决的是如何检测模型、工具、提示和用户行为已经漂移，以及何时必须回退到昂贵慢路径。

### 性能优化必须保留任务语义

Agentix、FlashAgents、Matrix 和 CacheSlide 报告显著吞吐或延迟收益，但程序进度、词元因果依赖、行间独立性和提示模板都只是有限的代理信号。ADR 的安全检测、OpenHands SDK 的事件重放、Tag2Graph 的用户状态和 AgenticCache 的任务成功率进一步说明：智能体系统不能只报告每秒词元数，还要证明优化没有改变工具副作用、状态一致性、任务成功率和租户公平性。

## 设计空间矩阵

| 论文 | 系统抽象 | 暴露的状态或语义 | 主要机制 | 管理资源 | 契约或指标 | 证据边界 |
|---|---|---|---|---|---|---|
| [[Cordis-TechReport26\|Cordis]] | 动态组件元框架 | 副作用逆操作、依赖键、fiber 生命周期 | 可撤销效应、反应式协效应、配置协调 | 组件、服务、事件与宿主资源句柄 | 撤销、依赖有序卸载、合流 | 形式证明与 Koishi 超过 4000 个插件；无性能对照，DeepSeek Harness 仍处预览期 |
| [[OpenHands-ICLR25\|OpenHands]] | 通用智能体平台 | 动作—观察事件流、工具、会话 | CodeAct、Docker、AgentSkills | 容器、工具、模型调用成本 | 任务成功率、安全边界 | 15 个基准；缺少恢复和多租户 SLO |
| [[OpenHands-SDK-MLSys26\|OpenHands SDK]] | 可组合 SDK | ConversationState、EventLog、工作空间 | 事件溯源、可选沙箱、服务器 | 状态、凭证、容器 | 重放、任务成功率、安全策略 | SWE-Bench 与 GAIA；缺少生产故障轨迹 |
| [[SkVM-SOSP26\|SkVM]] | 技能虚拟机与编译器 | 目标能力、技能有向无环图、执行反馈 | 预先编译、即时编译、绑定、固化 | 词元、API、CPU、执行框架 | 任务得分、回滚 | 8 个模型、3 个执行框架、118 个任务 |
| [[XGrammar2-CAIS26\|XGrammar-2]] | 动态工具调用协议 | 标签、语法片段、解析器状态 | TagDispatch、Cross-Grammar Cache、即时编译 | CPU、内存、词元掩码 | 协议正确性、编译延迟 | 结构合法不等于工具语义正确；缺少生产 P99 和隔离实验 |
| [[ADR-MLSys26\|ADR]] | 智能体安全控制面 | 提示、推理、MCP 工具、环境上下文 | 传感器、两级检测、Explorer | 遥测、模型调用、安全运营中心工时 | 精确率、召回率、成本、延迟 | 生产告警队列的误报明显高于基准 |
| [[Agentix-NSDI26\|Agentix]] | 智能体程序调度器 | 程序编号、已完成调用数 | 感知进度的调度、抢占 | GPU 解码槽位 | 程序完成时间、吞吐量 | 4–15 倍；未测工具副作用与任务成功率 |
| [[FlashAgents-MLSys26\|FlashAgents]] | 多智能体服务流水线 | 生产者—消费者词元依赖 | 流式预填充、基数树复用 | GPU、键值缓存、预填充资源 | 因果等价、端到端延迟 | 工作流延迟最多降低约 40%；未测跨机器部署 |
| [[Murakkab-OSDI26\|Murakkab]] | 云端工作流控制面 | 有向无环图、SLO 等级、画像、到达率 | 混合整数线性规划、多路复用、自动扩缩容 | 模型、GPU、工具实例 | 质量、延迟、成本、能耗 | 24 小时映射轨迹；不是线上智能体轨迹 |
| [[Matrix-MLSys26\|Matrix]] | 点对点多智能体运行时 | 消息携带的状态、行间依赖 | 无状态执行单元、行级调度 | 执行单元、队列、推理服务 | 词元吞吐、共识与奖励 | 缺少故障注入、全局事务和生产质量审计 |
| [[HIPPOCAMPUS-MLSys26\|HIPPOCAMPUS]] | 长期记忆模块 | 词元流、语义签名 | 动态小波矩阵、汉明距离检索 | 内存、CPU、查询词元 | F1、延迟、词元数 | 缺少并发一致性、删除和恢复实验 |
| [[Tag2Graph-MLSys26\|Tag2Graph]] | 个性化记忆系统 | 本体、向量、引用反馈 | 图与稠密向量对齐、路由器 | 图存储、向量存储、CPU | 召回率、nDCG、P95、忠实度 | 依赖用户反馈与周期性重新训练 |
| [[AgenticCache-MLSys26\|AgenticCache]] | 异步计划缓存 | 计划转移、元数据、修正 | 二元计划缓存、后台更新器 | API 词元、智能体本地缓存 | 成功率、延迟、成本 | 4 个仿真基准；未部署到真实机器人 |
| [[CacheSlide-FAST26\|CacheSlide]] | 智能体键值复用运行时 | 片段角色、相对顺序、键值偏差 | CCPE、WCA、SLIDE | HBM、DRAM、NVMe | 质量、延迟、吞吐量 | 依赖模板与适配器；单节点 A100，缺少 P99 |

## 共同观察

1. **单请求抽象会丢失最有价值的优化与恢复信号。** Cordis 的组件效应与依赖、OpenHands 的事件、Agentix 的程序身份、有向无环图、消息状态和智能体间依赖分别暴露不同层级的结构。系统不必理解自然语言计划，但至少要知道哪些调用属于同一程序、哪些状态可重放、哪些依赖位于关键路径、哪些修改应随组件卸载而撤销。
2. **效率收益普遍依赖可复用结构，正确恢复则依赖可归属结构。** FlashAgents 依赖前缀与生产者—消费者重叠，Agentix 依赖调用进度，SkVM 依赖稳定过程，AgenticCache 依赖计划局部性，CacheSlide 依赖提示模板；Cordis 还要求副作用可归属到组件并具备有效逆操作。动态分支、低复用、分布漂移或绕过运行时的外部副作用会分别削弱性能与恢复保证。
3. **快路径必须有失效与回退语义。** ADR、SkVM、Murakkab、Tag2Graph 和 AgenticCache 都把异常交给成本更高的控制面；Cordis 则把组件失效导向依赖有序卸载和效应撤销。很少有系统测量错误代理信号、过时画像、受污染记忆、模型升级后的缓存失效，或撤销期间再次失败的恢复结果。
4. **生产级功能多于生产级证据。** OpenHands SDK、ADR、Murakkab 和 Tag2Graph 都包含面向生产的组件；除 ADR 外，长期生产轨迹很少，而且会话崩溃、网络分区、带副作用操作的重试、画像漂移和多租户干扰几乎没有统一的故障注入实验。
5. **系统指标必须与任务结果共同报告。** 更低的首词元延迟（Time to First Token，TTFT）、更多每秒词元、更高检索召回率或更少 GPU，都不能自动推出任务成功率、安全性与公平性不退化。

## 假设冲突与脆弱点

1. **通用接口与程序语义暴露。** OpenHands、OpenHands SDK 和 SkVM 强调跨模型、工具和环境复用；Agentix、FlashAgents、Murakkab 与 Matrix 需要越来越多的程序拓扑和运行信息。应比较额外语义带来的收益与埋点、迁移和版本兼容成本。
2. **默认隔离与本地优先的可组合性。** OpenHands 默认每个会话使用 Docker，OpenHands SDK 改为本地优先、按需启用沙箱，SkVM 还会生成环境配置脚本和固化代码。ADR 的生产数据说明提示注入、恶意 MCP 和凭证泄漏不是边缘情况，需要统一的红队测试与最小权限契约。
3. **轻量代理信号与动态控制流。** Agentix 用调用数、AgenticCache 用相邻两步计划、SkVM 用能力、Murakkab 用画像、CacheSlide 用固定片段角色作为代理。重试、递归、动态扇出和工作负载变化都可能使代理信号与剩余工作或正确性反相关。
4. **记忆及缓存复用与状态失效。** HIPPOCAMPUS 优化压缩检索，Tag2Graph 在线提升关系，AgenticCache 强化历史转移，CacheSlide 复用模型状态；错误、过时、受污染或不可删除的状态如何传播、删除、回滚和跨版本重放，仍缺少统一语义。
5. **吞吐优先与任务结果。** 优化程序完成时间可能让新任务等待，跨工作流多路复用会扩大共享故障域，重试带副作用的工具还可能改变可观察行为。系统必须同时衡量任务成功率、公平性和副作用。
6. **执行期优化与训练平面。** RollArt 等智能体强化学习系统同样处理环境、奖励和轨迹长尾，但其主要对象是模型训练；若纳入本主题，会把边界扩张到整个 AI 生命周期，因此当前保留在 AI-Infra。
7. **形式化组合保证与真实外部副作用。** Cordis 证明的是经上下文执行、逆操作正确且跨组件独立的效应；智能体工具却经常发送消息、修改远端数据库或启动不可控进程。DeepSeek Harness 的采用证明抽象已进入完整 agent runtime，但尚未公开证明这些外部副作用满足撤销或补偿前提。

## 邻接与排除案例

- [[RollArt-OSDI26]] — 智能体强化学习训练系统，主要优化轨迹、奖励和训练流水线，归 [[AI-Infra]]。
- [[SpanQueries-MLSys26]] — 声明式缓存与注意力局部性中间表示可服务智能体，但机制同样适用于聊天与 RAG，不依赖智能体程序语义。
- [[AI-Scientist-arXiv24]]、[[RD-Agent-Quant-arXiv25]] — 分别以自动科研和量化投研结果为主要贡献，不因使用智能体而自动进入本系统领域。

## 值得关注的方向

### 1. 智能体程序轨迹与统一系统基准

建立可从 OpenHands SDK、AutoGen 和 LangGraph 导出的事件溯源轨迹，记录模型与工具调用、依赖、状态版本、外部副作用、失败与任务结果。先用轨迹重放比较 Agentix、FlashAgents、Murakkab 和 Matrix 类策略；关键问题是哪些最小语义足以支持调度、恢复和公平比较。

### 2. 具有崩溃一致性和恰好一次语义的智能体运行时

把 Cordis 的组件效应累加器、配置事务与 DeepSeek Harness 或 OpenHands SDK 的持久事件流统一起来，加入检查点（checkpoint）、幂等键（idempotency key，即重复提交仍只产生一次效果）、补偿动作和跨版本重放。对模型超时、工具崩溃、网络分区、进程重启和卸载期间再次失败做故障注入，评价恢复成功率、重复副作用率、状态丢失和额外成本。

### 3. 同时感知关键路径与正确性的程序调度器

以程序感知调度为起点，加入有向无环图关键路径、工具延迟、重试概率和验证器失败，而不是只用调用数估计进度。必须同时报告程序完成时间 P99、吞吐量、饥饿现象、任务成功率和取消安全性。

### 4. 智能体状态生命周期基准

把执行日志、长期记忆、用户本体、计划缓存和键值状态放入统一生命周期测试，覆盖追加、更新、删除、冲突、污染、崩溃、回滚和多智能体并发。需要区分检索遗漏、策略过时、模型版本失配和持久状态损坏。

### 5. 感知漂移的快路径控制面

联合研究技能版本、工作流画像、本体、计划转移和提示片段何时失效。目标是用少量探测检测性能或正确性漂移，并选择回滚、局部重新编译、重新画像或回退到模型慢路径。
