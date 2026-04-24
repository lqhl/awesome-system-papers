---
type: paper
name: OpenHands
full_title: "OpenHands: An Open Platform for AI Software Developers as Generalist Agents"
authors: [Xingyao Wang, Boxuan Li, Yufan Song, Frank F. Xu, Xiangru Tang, "et al."]
venue: ICLR
year: 2025
tags: [agent, software-engineering, swe-bench, codeact, open-platform]
source_pdf: "[[2407.16741v3.pdf]]"
source_md: "[[2407.16741v3]]"
---

# OpenHands: An Open Platform for AI Software Developers as Generalist Agents (ICLR 2025)

> **一句话总结**：社区驱动（32K GitHub stars、188+ contributors、2.1K+ contributions）的通用 AI 开发者 agent 平台，前身 OpenDevin，基于 CodeAct 的 event stream 架构在 15 个 benchmark 上评测，CodeActAgent v1.8（claude-3-5-sonnet）在 SWE-Bench Lite 拿 26%，与 Aider / Moatless / Agentless 等 SWE 专精 agent 持平，同时在 WebArena / GAIA 等跨类任务上保持 generality。

## 问题

LLM agent 框架百花齐放（AutoGPT、LangChain、MetaGPT、AutoGen、SWE-Agent 等），但各有偏向：要么只做通用 tool calling 缺沙箱 & browser，要么只做 SWE 专精缺 web / 多任务能力。一个想做「通用 digital worker」的平台需要同时满足：

1. 通用 action space（bash / Python / browser）贴近人类开发者
2. 安全沙箱执行任意代码
3. Tool 可扩展（SWE-Agent 已证明 Agent-Computer Interface 质量至关重要）
4. Multi-agent delegation + human-in-the-loop
5. 统一 evaluation framework 跨多个 benchmark
6. 社区可扩展（agent hub）

## 核心方法

**三大组件 + Event Stream 架构**：

- **Agent abstraction**：`step(state) -> action`，state 包含完整 event stream（action/observation 历史）。极简 API，社区可轻松实现新 agent（AgentHub 已收录 10+ 实现）
- **Event Stream**：action/observation 时序日志，驱动 UI、agent、runtime 三方通信；支持 replay、multi-agent delegation 元数据
- **Runtime**：每个 session 起一个 Docker sandbox，内置 REST API server 暴露：
  - Bash shell（CmdRunAction）
  - Jupyter IPython server（IPythonRunCellAction）
  - Playwright-based Chromium browser（BrowserInteractiveAction，走 BrowserGym DSL）
  - 支持任意 base Docker image，脚本自动注入 action execution API

**CodeAct 思想**：action space 用 programming language（bash/Python/browser DSL）而非 JSON schema，简洁表达力强且可以即时 define 新 tool（写 Python function 塞进 AgentSkills library 即可）。

**AgentSkills library**：标准化 agent-computer interface 工具箱，只收录「LLM 直接 coding 不方便」或「需要调外部模型」的 skill（file editing / scroll / parse_image / parse_pdf 等），不重复包装 pandas 这类 LLM 已会的库。

**Multi-agent delegation**：`AgentDelegateAction` 允许 generalist CodeActAgent 把 web browsing 子任务转给 BrowsingAgent，打开 specialist 组合的空间。

**Evaluation framework**：集成 15 个 benchmark，覆盖 software（[[MLE-Bench-ICLR25|MLE-Bench]] 前身相关 ML-Bench、SWE-Bench、HumanEvalFix、BIRD、BioCoder、Gorilla APIBench）、web（WebArena、MiniWoB++、ToolQA）、misc（GAIA、GPQA、AgentBench、MINT、EDA、ProofWriter）。

## 关键结果

- **SWE-Bench Lite（300 instances, 无 hint）**：CodeActAgent v1.8 + claude-3.5-sonnet 达 26.0%，Aider 26.3%、AutoCodeRover 19.0%、SWE-Agent 18.0%。平均成本 $1.10/instance
- **HumanEvalFix Python**：CodeActAgent v1.5 达 79.3%，显著好于 StarCoder2-15B（48.6%）等非 agentic 方法，虽未达 SWE-Agent 1-shot 的 87.7% 但 OpenHands 是 0-shot
- **WebArena**：BrowsingAgent + claude-3.5-sonnet 达 15.5%，与 WebArena Agent（14.4%）、Auto Eval & Refine（20.2%）同档
- **GAIA**：CodeActAgent（gpt-4o）32.1%；**GPQA**：53.1%，超过 gpt-4 few-shot 38.8%
- 单一 CodeActAgent 不改 prompt 在三大任务类别（SWE / Web / Misc）同时有竞争力，这是 SWE 专精 agent 做不到的
- Released under **MIT license**，定位为 research & industry 的共享基础设施

## 相关

- **相关概念**：CodeAct、Agent-Computer Interface (ACI)、Event-Sourcing、Docker Sandbox、BrowserGym
- **同类系统/框架**：SWE-Agent、AutoCodeRover、Aider、Moatless、Agentless、AutoGen、MetaGPT、LangChain、GPTSwarm
- **相关 benchmark**：SWE-Bench、[[MLE-Bench-ICLR25]]、WebArena、GAIA、HumanEvalFix
- **后续工作**：[[OpenHands-SDK-MLSys26]]（V1 把 monolith 重构成四包 modular SDK）
- **同主题**：[[Auto-Research]]
