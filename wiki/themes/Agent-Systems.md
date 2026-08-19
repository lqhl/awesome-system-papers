---
type: theme
topic: Agent-Systems
theme_kind: area
member_tag: area/agent-systems
candidate_tags: [agent-runtime, agent-serving, agentic-workflow, agent-memory, agent-skills, agent-security, software-agent, tool-calling]
paper_count: 13
first_generated: 2026-08-19
last_updated: 2026-08-19
tags: [topic-overview, agent-systems, llm-agent, runtime, memory, orchestration]
---

# 智能体系统（Agent-Systems）综述

> Agent-Systems 把智能体视为带工具、状态、依赖和外部副作用的程序，而不是一串彼此独立的 LLM 请求；核心问题是如何提供可移植执行、持久状态、程序级调度、资源编排、安全观测和可恢复的正确性边界。

## 定义与边界

进入核心集合的论文必须以可复用系统机制为主要贡献，并显式利用至少一种智能体语义：多轮 LLM 调用、工具执行、程序依赖、持久状态、多智能体通信、运行时反馈或外部副作用。只把普通 LLM serving、RAG、工作流或模型训练称为 agent，不足以进入本主题。

本 theme 聚焦**执行与部署平面**：runtime、SDK、sandbox、tool protocol、skill portability、agent program serving、workflow orchestration、memory/state、安全检测和执行期 cache。Agentic RL training、rollout generation 和模型更新仍归 [[AI-Infra]]；AI Scientist、量化投研 agent 等以应用结果为主的系统分别归 [[Auto-Research]]、[[Finance]]。如果把 agent 替换成无状态单请求后，论文的主要机制与实验仍基本不变，它通常也不应进入 Agent-Systems。

与 AI-Infra 的重叠是有意的：部分论文同时管理 GPU、KV cache 或 compiler/runtime，但它们进入本主题的依据是系统已经利用 program identity、inter-agent dependency、skill/harness、工具链或长期状态。状态失效、restart/recovery 和副作用的统一诊断见 [[Long-Horizon-Agents|长程智能体可靠性]]。

## 核心论文

### 平台、技能、工具协议与安全观测（5 篇）

- [[OpenHands-ICLR25|OpenHands]] — 用 CodeAct、事件流和 Docker sandbox 统一智能体、运行时间、UI 与评测，展示同一通用平台跨软件、浏览和知识任务的可复用性。
- [[OpenHands-SDK-MLSys26|OpenHands SDK]] — 将单体平台重构为 event-sourced SDK，以不可变组件、单一 ConversationState、可选 sandbox 和统一 local/remote workspace 支撑生产集成。
- [[SkVM-SOSP26|SkVM]] — 把 skill 当作面向模型、harness 和环境编译的程序，通过 AOT/JIT、环境绑定和代码固化改善跨 target 可移植性。
- [[XGrammar2-CAIS26|XGrammar-2]] — 将 request 内外的 grammar switching、子结构复用和 token mask 变成 agent tool-call protocol 的运行时能力。
- [[ADR-MLSys26|ADR]] — 关联 user prompt、agent reasoning、MCP tool 与环境遥测，以两级检测和离线红队支持企业 agent 安全运营。

### Serving、调度与 Workflow 编排（4 篇）

- [[Agentix-NSDI26|Agentix]] — 把多调用 agent program 而非单个 request 作为调度单位，用调用进度和抢占缓解 request/program 两级队首阻塞。
- [[FlashAgents-MLSys26|FlashAgents]] — 利用多智能体的 producer–consumer token 依赖，重叠上游 decode 与下游 incremental prefill，并复用同轮共享 prefix。
- [[Murakkab-OSDI26|Murakkab]] — 以声明式 DAG、两层画像、MILP 和 autoscaling 联合选择 workflow 参数、模型、工具、硬件与路由。
- [[Matrix-MLSys26|Matrix]] — 用 message-carried state、stateless Ray actors 和 row-level scheduling 去掉大规模多智能体 workflow 的中心 orchestrator。

### 记忆、状态与执行期 Cache（4 篇）

- [[HIPPOCAMPUS-MLSys26|HIPPOCAMPUS]] — 以 token-ID 流、语义二进制签名和 Dynamic Wavelet Matrix 构建压缩域长期记忆。
- [[Tag2Graph-MLSys26|Tag2Graph]] — 用在线偏好本体、graph–dense 一致性和动态 router 恢复跨 session 的隐式用户状态。
- [[AgenticCache-MLSys26|AgenticCache]] — 将高频计划转移放入缓存快路径，由后台 LLM updater 异步确认、纠错和替换失效计划。
- [[CacheSlide-FAST26|CacheSlide]] — 针对 agent prompt 中相对顺序稳定、绝对位置漂移的片段，联合位置适配、选择性重算与 KV spill 优化实现跨位置复用。

## 主题综述

### 系统抽象从 request 上升到 program

OpenHands 的事件流和 OpenHands SDK 的 ConversationState 暴露完整执行历史，XGrammar-2 暴露动态 tool-call grammar，Agentix 为请求补充 program identity 和进度，FlashAgents 暴露 producer–consumer token 依赖，Murakkab 直接把 workflow 表达为 DAG，Matrix 则把状态随消息传递到无状态 worker。抽象越接近完整程序，系统越能优化关键路径、调度和恢复；代价是 framework instrumentation、版本兼容和应用语义耦合都会增加。

### Agent state 不是一种数据

执行日志要求顺序、replay 和 crash consistency；长期记忆要求检索、更新、删除与租户隔离；计划 cache 要求失效检测和安全回退；KV cache 还绑定 model、tokenizer、位置编码与 prompt template。OpenHands SDK、HIPPOCAMPUS、Tag2Graph、AgenticCache 和 CacheSlide 管理的是不同生命周期，不能统一塞进长 context 后便认为状态问题已经解决。

### 快路径与慢控制面成为共同结构

SkVM 用 AOT/JIT variant 和固化代码减少重复推理，ADR 用便宜 triage 筛选需要深度调查的 session，Murakkab 用离线画像支撑周期性全局优化，Tag2Graph 把本体校验移出 serving hot path，AgenticCache 用缓存执行并由异步 LLM 纠错。共同假设是常见 workload 具有稳定结构；真正未解决的是如何检测模型、工具、prompt 和用户行为已经漂移，以及何时必须回退到昂贵慢路径。

### 性能优化必须保留任务语义

Agentix、FlashAgents、Matrix 和 CacheSlide 报告显著 throughput 或 latency 收益，但 program progress、token 因果依赖、row independence 和 prompt template 都只是有限代理。ADR 的安全检测、OpenHands SDK 的 event replay、Tag2Graph 的用户状态和 AgenticCache 的 task success 进一步说明：Agent-Systems 不能只报告 token/s，还要证明优化没有改变工具副作用、状态一致性、任务成功率和租户公平性。

## 设计空间矩阵

| 论文 | 系统抽象 | 暴露的状态或语义 | 主要机制 | 管理资源 | 契约或指标 | 证据边界 |
|---|---|---|---|---|---|---|
| [[OpenHands-ICLR25\|OpenHands]] | 通用 agent platform | action–observation 事件流、tool、session | CodeAct、Docker、AgentSkills | 容器、工具、LLM 成本 | task success、安全边界 | 15 个 benchmark；缺恢复和多租户 SLO |
| [[OpenHands-SDK-MLSys26\|OpenHands SDK]] | 可组合 SDK | ConversationState、EventLog、workspace | event sourcing、optional sandbox、server | 状态、secret、容器 | replay、task success、安全策略 | SWE-Bench/GAIA；缺生产故障 trace |
| [[SkVM-SOSP26\|SkVM]] | skill VM/compiler | target capability、skill DAG、执行反馈 | AOT/JIT、binding、solidification | token、API、CPU、harness | task score、rollback | 8 models、3 harnesses、118 tasks |
| [[XGrammar2-CAIS26\|XGrammar-2]] | dynamic tool-call protocol | tag、grammar fragment、parser state | TagDispatch、Cross-Grammar Cache、JIT | CPU、memory、token mask | protocol correctness、compile latency | 结构合法不等于 tool 语义正确；缺生产 P99/隔离 |
| [[ADR-MLSys26\|ADR]] | agent security control plane | prompt、reasoning、MCP tool、环境上下文 | sensor、两级检测、Explorer | telemetry、LLM 调用、SOC 工时 | precision、recall、cost、latency | 生产 alert queue FP 明显高于 benchmark |
| [[Agentix-NSDI26\|Agentix]] | agent program scheduler | program ID、已完成调用数 | progress-aware scheduling、抢占 | GPU decode slot | program JCT、throughput | 4–15×；未测 tool 副作用与 task success |
| [[FlashAgents-MLSys26\|FlashAgents]] | 多智能体 serving pipeline | producer–consumer token dependency | streaming prefill、radix reuse | GPU、KV、prefill | 因果等价、端到端 latency | workflow latency 最多降约 40%；未测跨机 |
| [[Murakkab-OSDI26\|Murakkab]] | 云端 workflow control plane | DAG、SLO tier、profile、arrival rate | MILP、multiplexing、autoscaling | 模型、GPU、工具实例 | quality、latency、cost、energy | 24h 映射 trace；非线上 agent trace |
| [[Matrix-MLSys26\|Matrix]] | P2P multi-agent runtime | message-carried state、row dependency | stateless actor、row-level scheduling | actor、queue、inference service | token throughput、agreement/reward | 缺 fault injection、全局事务和生产质量审计 |
| [[HIPPOCAMPUS-MLSys26\|HIPPOCAMPUS]] | 长期记忆模块 | token 流、语义签名 | Dynamic Wavelet Matrix、Hamming 检索 | memory、CPU、query token | F1、latency、token | 缺并发一致性、删除和恢复实验 |
| [[Tag2Graph-MLSys26\|Tag2Graph]] | 个性化记忆系统 | ontology、vector、引用反馈 | graph–dense 对齐、router | graph/vector store、CPU | Recall、nDCG、P95、faithfulness | 依赖用户反馈与周期性 retraining |
| [[AgenticCache-MLSys26\|AgenticCache]] | 异步计划 cache | plan transition、metadata、correction | 2-gram cache、后台 updater | API token、agent-local cache | success rate、latency、cost | 4 个仿真 benchmark；未部署真实机器人 |
| [[CacheSlide-FAST26\|CacheSlide]] | agent KV reuse runtime | chunk role、relative order、KV deviation | CCPE、WCA、SLIDE | HBM、DRAM、NVMe | quality、latency、throughput | 模板/adapter 依赖；单节点 A100、缺 P99 |

## 共同观察

1. **单请求 abstraction 会丢失最有价值的优化信号。** Event、program identity、DAG、message state 和 inter-agent dependency 分别暴露不同层级的结构；系统不必理解自然语言计划，但至少要知道哪些调用属于同一程序、哪些状态可重放、哪些依赖位于关键路径。
2. **效率收益普遍依赖可复用结构。** FlashAgents 依赖 prefix 与 producer–consumer overlap，Agentix 依赖调用进度，SkVM 依赖稳定 procedure，AgenticCache 依赖计划局部性，CacheSlide 依赖 prompt template；动态分支、低复用或分布漂移会同时削弱这些收益。
3. **快路径必须有失效与回退语义。** ADR、SkVM、Murakkab、Tag2Graph 和 AgenticCache 都把异常交给更贵控制面，但很少系统测量错误 proxy、stale profile、poisoned memory 或模型升级后的 invalidation。
4. **生产级功能多于生产级证据。** OpenHands SDK、ADR、Murakkab 和 Tag2Graph 都包含 production-oriented 组件；除 ADR 外，长期生产 trace 很少，且 session crash、网络分区、side-effect retry、profile drift 和多租户干扰几乎没有统一注入实验。
5. **系统指标必须与任务结果共同报告。** 更低 TTFT、更多 token/s、更高 retrieval recall 或更少 GPU 都不能自动推出 task success、安全性与公平性不退化。

## 假设冲突与脆弱点

1. **通用接口 vs 程序语义暴露。** OpenHands、OpenHands SDK 和 SkVM 强调跨模型、工具和环境复用；Agentix、FlashAgents、Murakkab 与 Matrix 需要越来越多 program topology 和运行信息。应比较额外语义带来的收益与 instrumentation、迁移和版本兼容成本。
2. **默认隔离 vs local-first 可组合性。** OpenHands 默认每 session Docker，OpenHands SDK 改为 local-first、sandbox opt-in，SkVM 还会生成 setup script 和固化代码。ADR 的生产数据说明 prompt injection、恶意 MCP 和凭证泄漏不是边缘情况，需要统一 red-team 与 least-privilege contract。
3. **轻量 proxy vs 动态控制流。** Agentix 用调用数、AgenticCache 用 2-gram、SkVM 用 capability、Murakkab 用 profile、CacheSlide 用固定 chunk role。Retry、递归、动态 fan-out 和 workload shift 都可能使 proxy 与剩余工作或正确性反相关。
4. **记忆与 cache 复用 vs stale、poisoned 和不可删除状态。** HIPPOCAMPUS 优化压缩检索，Tag2Graph 在线晋升关系，AgenticCache 强化历史 transition，CacheSlide 复用模型状态；错误状态如何传播、删除、回滚和跨版本重放仍缺统一语义。
5. **吞吐优先 vs task success、fairness 与副作用。** Program completion 优化可能让新任务等待，跨 workflow multiplexing 会扩大共享故障域，重试带副作用工具还可能改变可观察行为。
6. **执行期优化 vs training plane。** RollArt 等 agentic RL 系统同样处理 environment、reward 和 rollout 长尾，但其主要对象是模型训练；若纳入本 theme，会把边界扩张到整个 AI lifecycle，因此当前保留在 AI-Infra。

## 邻接与排除案例

- [[RollArt-OSDI26]] — agentic RL training 系统，主要优化 rollout/reward/training pipeline，归 [[AI-Infra]]。
- [[SpanQueries-MLSys26]] — 声明式 cache/attention locality IR 可服务 agent，但机制同样适用于 chat 与 RAG，不依赖 agent program 语义。
- [[AI-Scientist-arXiv24]]、[[RD-Agent-Quant-arXiv25]] — 分别以自动科研和量化投研结果为主要贡献，不因使用 agent 自动进入本 area。

## 值得关注的方向

### 1. Agent program trace 与统一系统 benchmark

建立可跨 OpenHands SDK、AutoGen 和 LangGraph 导出的 event-sourced trace，记录 LLM/tool 调用、依赖、状态版本、外部副作用、失败与 task outcome。先用 trace replay 比较 Agentix、FlashAgents、Murakkab 和 Matrix 类策略；关键问题是哪些最小语义足以支持调度、恢复和公平比较。

### 2. Crash-consistent、exactly-once 的 agent runtime

在事件流上加入 checkpoint、idempotency key、补偿动作和跨版本 replay，对 LLM timeout、tool crash、网络分区与进程重启做故障注入。评价指标应包含恢复成功率、重复副作用率、状态丢失和额外成本。

### 3. 同时感知关键路径与正确性的 program scheduler

以 program-aware scheduler 为起点，加入 DAG critical path、tool latency、retry probability 和 verifier failure，而不是只用调用数估计进度。必须同时报告 P99 JCT、throughput、starvation、task success 和取消安全。

### 4. Agent state 生命周期 benchmark

把 execution log、长期记忆、用户本体、计划 cache 和 KV state 放入统一生命周期测试：append、update、delete、contradiction、poisoning、crash、rollback 和多 agent 并发。需要区分 retrieval miss、stale policy、模型版本失配和 durable-state corruption。

### 5. Drift-aware 的快路径控制面

联合研究 skill variant、workflow profile、ontology、plan transition 和 prompt chunk 何时失效。目标是用少量 probe 检测性能或正确性漂移，并选择 rollback、局部 recompile、reprofile 或回退到 LLM 慢路径。
