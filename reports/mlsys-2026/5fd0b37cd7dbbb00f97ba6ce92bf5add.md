---
title: "The OpenHands Software Agent SDK: A Composable and Extensible Foundation for Production Agents"
authors: [Xingyao Wang, Simon Rosenberg, Juan Michelini, Calvin Smith, Hoang Tran, et al.]
year: 2026
venue: MLSys
tags: [agent-framework, software-agent, sdk, sandboxing, event-sourcing]
---

# The OpenHands Software Agent SDK: A Composable and Extensible Foundation for Production Agents

**作者**：Xingyao Wang, Simon Rosenberg, Juan Michelini, Calvin Smith, Hoang Tran, Engel Nyst, Rohit Malhotra, Xuhui Zhou, Valerie Chen, Robert Brennan, Graham Neubig
**单位**：All Hands AI 等(论文未列明完整 affiliation)
**会议**：MLSys 2026
**链接**：[OpenHands/software-agent-sdk](https://github.com/OpenHands/software-agent-sdk) · [proceedings](https://proceedings.mlsys.org/paper_files/paper/2026)
**源文件**：[[5fd0b37cd7dbbb00f97ba6ce92bf5add.pdf]]

---

## 1. 背景

软件工程领域的 AI agent 已从 GitHub Copilot、Cursor 这类辅助编程工具,演进为可执行数小时长任务的自主系统(Devin、Claude Code、OpenHands 等)。这种转变对底层系统提出了全新要求:可恢复的状态管理、安全的沙箱执行、跨本地/容器/云环境的一致性行为 —— 这些都是早期"由用户驱动 + 本地短交互"的助手类工具不需要操心的能力。

OpenHands 项目从 2024 年发布以来,18 个月内拿到 64k+ GitHub stars 和数百名贡献者,成为开源软件 agent 的事实标准之一。但项目早期为追求快速原型设计采用的 monolithic 架构(本文称为 V0),将 agent 逻辑、评估代码和应用代码全部塞在一个 codebase 里,逐渐暴露出严重的架构问题。本文是 OpenHands 团队对 V0 的彻底重构,即 OpenHands V1,其核心交付物是一个独立的 Software Agent SDK。

---

## 2. 要解决的问题

V0 架构在四个维度上累积了不可忍受的债务:

1. **强制沙箱化的僵化性**:V0 假设所有工具调用都跑在 Docker 沙箱里,导致 agent 进程与 sandbox 进程双向漂移、多租户场景下单用户的资源滥用会拖垮其他 agent。后来为支持本地 CLI 执行,被迫加入大量 bypass 逻辑和重复实现的 MCP/tool 路径,与 MCP 协议本身的"本地直接执行"假设也不一致。
2. **配置爆炸**:配置系统跨 CLI/Web UI/GitHub App/SaaS 多套并行入口,每个入口各自演化出 override 规则。最终 140+ 字段、15 个类、2.8K 行配置代码,小改动经常引发不相关的级联失败。
3. **monorepo 边界模糊**:agent 核心、benchmark 套件、前后端、各种 runtime provider 全部混在一个仓库里,benchmark 的重型依赖污染主应用,部署变得脆弱。
4. **核心逻辑不可扩展**:加新功能往往需要直接改 core,缺少结构化的 composability,小改动也要 hack。

本文的目标是用一次彻底的架构重写解决以上问题,同时保持(并扩展)V0 已经积累的 agent 能力。

---

## 3. 洞察与设计

**关键洞察**:作者从 V0 的 18 个月运维与社区反馈中提炼出四条原则,这些是整个 V1 架构成立的前提 ——

- **沙箱应是 opt-in 而非默认**。MCP 协议本身假设 agent 可以本地直接访问凭证、文件、IDE,把沙箱设为默认与协议生态对立;只在确实需要隔离时才付沙箱代价。
- **状态应该集中、单点、不可变以外**。Agent / Tool / LLM 等组件全部声明为 immutable Pydantic model,只有 `ConversationState` 是可变的,这样即使长会话、跨进程恢复,也能做到 deterministic replay。
- **agent core 必须从 application 中分离**。下游 CLI、Web UI、GitHub App 应该把 agent core 当作共享库消费,而不是把应用逻辑反向注入到 core。
- **composability 必须是一等公民**,且分两层:部署层(SDK / Tools / Workspace / Server 四个独立 package 自由组合)和能力层(用户通过类型化的 Tool / LLM / Context 抽象进行声明式扩展)。

围绕这四条原则,V1 把整个项目拆成四个 Python package:

- `openhands.sdk`:核心抽象(Agent、Conversation、LLM、Tool、MCP)和事件系统
- `openhands.tools`:具体工具实现
- `openhands.workspace`:执行环境(Docker、API 托管 runtime 等)
- `openhands.agent_server`:暴露 REST/WebSocket 的 web server

架构上的几个核心设计:

- **事件溯源(event-sourcing)的 ConversationState**:所有交互都是 append-only 的不可变事件;事件分两大类——LLM-convertible(Message/Action/Observation/SystemPrompt 等)和 internal(状态更新、condensation 触发等)。一个 FIFO 锁保护两条更新路径(纯元数据更新 vs. 事件追加)。
- **Local 与 Remote 同接口**:`Conversation(agent, workspace)` 是工厂入口;传 `LocalWorkspace` 返回 in-process 执行的 `LocalConversation`,传 `RemoteWorkspace` 则透明序列化 agent 配置并通过 HTTP/WebSocket 委托给远端 agent server,从原型到容器化部署只需改 `workspace=` 参数。
- **Tool 抽象的 Action–Execution–Observation 三段式**:LLM 输出 JSON tool call → Pydantic 验证为 Action → 由 `ToolExecutor` 执行 → 包装为 Observation。MCP tool 通过 `MCPToolDefinition` 与原生 tool 走同一接口,JSON Schema 自动翻译为 Action 模型。
- **Tool Registry 解决跨进程问题**:Python executor 不可序列化,所以 tool spec 仅记录注册名 + JSON 参数,跨进程后由 server 端按名解析,实现 lazy 实例化。
- **Multi-LLM Routing**:`RouterLLM` 是 `LLM` 的子类,通过 `select_llm()` 根据消息内容(如是否含图像)选择不同模型,文本走便宜模型、图像走多模态模型。
- **Security & Confirmation 框架**:`SecurityAnalyzer` 给每个 tool call 打风险等级(low/med/high/unknown),`ConfirmationPolicy` 决定是否需要人工审批,支持 mid-conversation 动态调整(adaptive trust)。

---

## 4. 实现细节

- **Condenser**:管理上下文窗口。当事件历史增长到接近 LLM context 上限时,生成 `CondensationEvent` 删除历史并插入摘要。Condenser 本身保持 stateless,完整的事件日志仍保留在磁盘。默认的 `LLMSummarizingCondenser` 在不损失 agent 性能的前提下把 API 成本降低 ~2×。
- **持久化**:`ConversationState` 双路径写盘:元数据每次修改写入单个 `base_state.json`,事件追加为独立 JSON 文件到对应目录。恢复时加载 base + 重放事件;agent 自动检测未完成的 conversation 并从最后处理的事件继续。
- **Skills / AgentContext**:用户可以通过 markdown 文件(如 `.openhands/skills/`、`.cursorrules`、`agents.md`)给 agent 注入永久或基于关键字触发的 skill,skill 还可携带 MCP tool。
- **Sub-agent Delegation**:作为 `openhands.tools` 中的一个标准 tool 实现,父 agent 通过工具调用 spawn 阻塞式并行的 sub-agent —— 复杂编排(异步委派、动态调度、容错)都可以纯粹在 user-defined tool 层实现而不动 core。
- **Secret Registry**:per-conversation 的凭证管理,Bash Tool 在执行前扫描命令、把引用的 secret export 为环境变量,在结果中统一替换为 `<secret-hidden>`。支持 callable secret(如 token refresher)和 mid-conversation 旋转。
- **Agent Server**:基于 FastAPI,`POST /conversations` 接受序列化的 agent 配置,reconstruct 后启动本地执行循环,通过 WebSocket 流式回传事件。官方 Docker 镜像捆绑 API server + VSCode Web + VNC 桌面 + Chromium 浏览器,每个 agent instance 独立容器,天然支持多租户隔离。
- **三层测试体系**:(1) Programmatic tests 在每次 commit 跑,mock LLM 调用、秒级反馈;(2) LLM-based tests(integration + example)每天跑,使用真实模型(Claude Sonnet 4.5、GPT-5 Mini、DeepSeek Chat),单次 \$0.5–\$3,5 分钟内完成;(3) Benchmark evaluation 按需触发,\$100–\$1000、数小时。

---

## 5. 实验结果

主要实验是在 SWE-Bench Verified(软件工程任务)和 GAIA validation set(通用 agent 任务)上的端到端跑分:

| Benchmark | Model | Performance |
| --- | --- | --- |
| SWE-Bench Verified | Claude Sonnet 4.5 | **72.8%** |
| | Claude Sonnet 4 | 68.0% |
| | GPT-5 (reasoning=high) | 68.8% |
| | Qwen3 Coder 480B A35B | 65.2% |
| GAIA (val) | Claude Sonnet 4.5 | **67.9%** |
| | Claude Sonnet 4 | 57.6% |
| | GPT-5 (reasoning=high) | 62.4% |
| | Qwen3 Coder 480B A35B | 41.2% |

作者声称这些数字略好于 OpenHands-Versa(Soni et al., 2025),验证 V1 的架构重构没有牺牲 agent 能力。

此外还做了一份与三家竞品 SDK(OpenAI Agents SDK、Claude Agent SDK、Google ADK)的功能对照(Tab. 3,共 31 项)。OpenHands 在 31 项中独占 16 项,典型的差异化能力包括:

- 内建 REST + WebSocket production server(其他三家都是 library-only)
- 原生 sandbox + 远程执行(其他三家或者完全本地、或者要求外接 Temporal)
- LLM-based security analyzer + confirmation policy
- Multi-LLM routing 和 100+ provider 支持(Claude Agent SDK 锁死 Anthropic)
- Stuck detection、auto-generated conversation titles、secrets auto-masking、context condensation 等运维向能力

---

## 6. 批判性分析

这是一篇典型的"系统工程经验报告"论文,亮点在于把一个真实开源项目的演进与教训系统化总结,但放在 MLSys 这种学术会议下评审时有不少弱项:

- **缺乏对 V1 设计本身的定量验证**。paper 反复声称 V1 比 V0 更好(更易扩展、更可靠、更易部署),但没有任何对比 V0 vs V1 的定量数据 —— 没有故障率、配置代码行数、添加新工具的工程量、状态恢复成功率等指标。所有的 V0 痛点都是叙事性的,缺少可重复验证的证据。
- **Benchmark 数字与设计选择脱节**。Tab. 2 给出了 SWE-Bench 72.8%、GAIA 67.9% 的成绩,但这些数字主要由底层模型 + 默认 agent loop 决定,与 V1 的架构设计(event-sourcing、模块化、optional sandboxing)关联很弱。论文没有做 ablation 来证明任何一个设计决策对最终性能有可量化的贡献,benchmark 更多是"架构没拖后腿"的存在性证明。
- **与竞品的对比表偏自我描述**。Tab. 3 是 OpenHands 团队在 2025-10-29 自己整理的功能矩阵,直接由作者打勾。多个细分能力是否真的"完全不存在"于 OpenAI/Claude/Google SDK,缺乏第三方核验;某些条目(如 "TODO List Planner")更接近实现细节而非架构能力,放进 31 项里有凑数嫌疑。
- **OpenHands V0 的 strawman 化**。V0 被描述得几乎一无是处(配置代码 2.8K 行被反复强调),但 V0 在 18 个月内拿到 64k stars 也说明它在实际落地中是 work 的。作者把所有问题都归因于"架构错误",但有些问题(如 multi-tenant 资源争抢)其实与 monorepo / sandbox 没有直接关系,而是与隔离粒度的工程实现有关。
- **"opt-in sandbox"的安全权衡未深入**。论文说默认本地执行符合 MCP 假设,但本地执行意味着 agent 可以直接接触用户机器上的所有凭证、SSH key、浏览器 cookie。这在生产环境是高风险的;`SecurityAnalyzer` 依赖另一个 LLM 判断"high/medium/low",本身既增加成本又有 prompt injection 攻击面,论文没有对这个 LLM 判官的准确率、误报率做评估。
- **Condensation 的 2× 成本下降数字来源是博客**(Smith, 2025),没有放在论文里复现,且没说在哪些任务上、哪些模型上、哪种 condenser 配置下成立。
- **"deterministic replay"是 event-sourcing 的常见 selling point,但 LLM 输出本身是随机的**(temperature/采样),严格意义上的 deterministic replay 需要把 LLM response 也视为事件持久化下来。论文没有说清楚 replay 的语义是"重放 LLM 输出"还是"重新调用 LLM",这两者对调试和成本影响极大。

---

## 7. AI Infra / MLSys 视角

这篇论文对 AI infra 研究者有几个值得关注的角度:

- **agent runtime 是一个被低估的系统问题**。Inference engine(vLLM、SGLang)和 training framework(DeepSpeed、Megatron)拿走了大量学术注意力,但 agent runtime —— 调度 LLM 调用、管理工具沙箱、维护可恢复状态 —— 实际承载着越来越多生产 token,反而几乎没有学术研究。OpenHands SDK 暴露的几个工程问题(状态可恢复性、condensation 策略、security analyzer 的 LLM 调用开销)都是非常具体的研究切入点。
- **event-sourcing + 不可变组件的设计模式可以反向影响推理系统**。例如 KV cache 也可以视为一种 immutable 的 event log;current vLLM 的 prefix cache 已经在朝这个方向走,但 agent 层面的 state 与 inference 层面的 cache 没有打通。一个研究方向:能否让 agent 的 ConversationState 直接驱动 inference engine 的 cache 重用策略?当 condensation 触发时,KV cache 应该如何同步失效或重建?
- **Multi-LLM routing 是个尚未被认真研究的调度问题**。论文里的 `RouterLLM` 实现非常朴素(基于 message 属性的硬规则),实际上"哪个请求该路由到哪个模型/哪个 provider"是一个可以引入学习/优化的调度问题,涉及成本、延迟、能力 trade-off。AI infra 角度的延伸工作:可以在 router 层做 batch-aware 调度、跨 provider 的 SLO 优化、甚至引入 RL/bandit 学习路由策略。
- **agent server 多租户**:每个 agent instance 一个容器虽然简单,但成本高。能否引入轻量级隔离(gVisor、Firecracker、WASM)、cold-start 优化、容器池化?这是 serverless inference 已经研究过的问题,但 agent runtime 的 working set(文件、tmux 会话、VSCode 状态)比无状态推理大得多,迁移过来有新的挑战。
- **sub-agent delegation 与分布式调度**:论文目前的实现是阻塞式并行,父 agent 需要等待所有 sub-agent 完成。引入异步调度后,sub-agent 可以是不同模型、不同 workspace、不同优先级的混合负载,这就变成了一个真正的分布式 agent scheduler 设计问题,与 inference 层面的 continuous batching 可以联动。
- **可借鉴的研究问题**:(1) 真实 agent workload 的 trace 采集与回放(目前学术界对 agent 真实流量的认识极少);(2) 长会话场景下 condenser 的最优策略学习;(3) sandbox cold-start 与 warm-pool 调度;(4) 跨 SDK 的 agent benchmark 标准化(每家 SDK 自己跑出来的 SWE-Bench 分数可比性差)。

---

## 8. 总结

OpenHands V1 用四个独立 Python 包 + 事件溯源的 ConversationState + 不可变组件设计,将一个 64k stars 的开源 agent 项目从"难以维护的 monorepo"重构为"可独立扩展的生产 SDK"。论文的核心价值不在于某个新算法,而在于把一个真实运行 18 个月的 agent 项目踩过的坑系统化,提炼出 optional sandboxing、stateless-by-default、separation of concerns、composability 四条设计原则,并给出可工程化的实现。SWE-Bench Verified 72.8% 和 GAIA 67.9% 的成绩证明这次重构没有牺牲 agent 能力。主要局限在于学术意义偏弱:缺少 V0 vs V1 的定量对比、关键设计决策没有 ablation、与竞品的功能对照表来自作者自评。对于想要落地生产 agent 系统的团队,本文是高质量的工程参考;对于 AI infra 研究者,论文揭示的 agent runtime 各种系统级问题(调度、隔离、状态管理、condensation)是很有价值的研究入口。
