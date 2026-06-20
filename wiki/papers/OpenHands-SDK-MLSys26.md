---
type: paper
name: OpenHands-SDK
full_title: "The OpenHands Software Agent SDK: A Composable and Extensible Foundation for Production Agents"
authors: [Xingyao Wang, Simon Rosenberg, Juan Michelini, Calvin Smith, Hoang Tran, "et al."]
venue: MLSys
year: 2026
tags: [agent, sdk, sandbox, software-engineering, mcp, event-sourcing]
source_pdf: "[[5fd0b37cd7dbbb00f97ba6ce92bf5add.pdf]]"
source_md: "[[5fd0b37cd7dbbb00f97ba6ce92bf5add]]"
---

# The OpenHands Software Agent SDK: A Composable and Extensible Foundation for Production Agents (MLSys 2026)

> **一句话总结**：基于 [[OpenHands-ICLR25|OpenHands]] V0 规模化痛点（强制 sandbox 双进程状态分裂、140+ 可变配置字段、monorepo 与 benchmark 泄漏），V1 重构为四包模块化 SDK——默认本地单进程、event-sourced 单一可变状态、opt-in sandbox、内置 REST/WebSocket server；在 SWE-Bench Verified 达 **72%**、GAIA val **67.9%**，并相对 OpenAI/Claude/Google SDK 宣称 **16** 项独有生产特性。

## 问题与动机

生产级 software engineering agent 需要三类能力：**灵活实验**（自定义 tool、memory、routing）、**可靠安全执行**（sandbox、状态恢复、跨 local→remote 可移植）、**多界面交互**（CLI、Web UI、VS Code/VNC/browser）。[[OpenHands-ICLR25|OpenHands]] 在 18 个月内获 64k+ GitHub stars，但 V0 monolithic 架构在规模化后暴露结构性张力：

- **强制 universal sandboxing**：agent 与 sandbox 为两个独立进程，状态可能分叉（一方 crash 另一方继续），多租户下资源密集型 action（如大截图）可拖垮共享容器；支持本地 CLI/MCP 时又需 duplicated local 版 MCP/tool 实现。
- **Mutable configuration sprawl**：140+ 字段、15 类、2.8K 行配置代码，CLI/Web/GitHub App/SaaS 各有一套 override 层级，相同参数两次运行仍可能微妙分歧。
- **Monorepo 边界模糊**：agent core、evaluation、frontend/backend/CLI 同仓，benchmark 重依赖泄漏进主应用，部署变重且脆弱。

作者 claim：需要一次**完整架构重设计**，把 agent core 抽成可复用 SDK，同时不牺牲 agentic 能力。本文交付 **OpenHands Software Agent SDK**（OpenHands V1 的 foundation），并配套 CLI/GUI 等应用层。

## 关键观察 / 隐含假设

- **观察 1：V0 的「所有 tool call 必须进 Docker sandbox」与 MCP 的 local-first 假设冲突。** 本地 workflow 需要直接访问 credential、文件、IDE；V0 为兼容 CLI 不得不旁路 sandbox，导致 MCP/tool 双份实现、架构 brittle。
  - **依赖假设**：多数开发/调试场景默认在 host 单进程执行足够安全；真正需要隔离的是不可信代码执行或多租户 SaaS。
  - **可能失效场景**：agent 在 host 上持 elevated privilege（sudo、生产 API key）时，opt-in sandbox 若被开发者忽略则风险回归 V0 旁路模式；论文未量化「多少用户实际开启 sandbox」。

- **观察 2：配置可变性与 session 可恢复性互斥——V0 的 hidden override 使 deterministic replay 不可能。** 同一参数两次运行可因 entry point 不同而分歧。
  - **依赖假设**：Agent/Tool/LLM 等组件在 construction 时 immutable + Pydantic 校验；**唯一**可变实体是 ConversationState（metadata + append-only EventLog）。
  - **可能失效场景**：mid-conversation 动态更新 ConfirmationPolicy、SecretRegistry 或 RouterLLM 路由规则时，replay 语义是否仍 deterministic **论文未形式化证明**；跨 SDK 版本 replay 兼容性未讨论。

- **观察 3：Monorepo 把 research benchmark 依赖带进 production path，拖慢 QA 与 release。** 学术社区贡献的 benchmark 引入 version conflict，agent core 吸收 application-specific hack。
  - **依赖假设**：四包分离（`openhands.sdk` / `tools` / `workspace` / `agent server`）可独立测试、选择性依赖、增量发布。
  - **可能失效场景**：跨包 API 版本 skew（client SDK vs remote agent server）时的兼容性矩阵 **论文未给出**；四包协调仍增加集成测试面。

- **观察 4：生产 agent 需要「notebook 级 local 原型」与「containerized multi-user 部署」之间**仅换 workspace 类型**的透明迁移。**
  - **依赖假设**：LocalWorkspace 与 RemoteWorkspace 共享 BaseWorkspace 接口；Conversation factory 序列化 agent config 到 agent server，WebSocket 流式回传 event。
  - **可能失效场景**：remote 路径引入网络分区、WebSocket 重连、容器冷启动延迟；local 与 remote 的 tool 执行语义（路径、环境变量、secret 注入）是否 bit-identical **未做对照实验**。

- **假设 1**：与 OpenAI Agents SDK、Claude Agent SDK、Google ADK 的 **31 项 feature 对比**（截至 2025-10-29）足以支撑「OpenHands 独有 16 项生产特性」的定位 claim。
  - **证据强度**：**弱–中**——附录逐项文档引用较详，但竞品快速迭代，对比表为 snapshot；部分特性标「∼ partial」边界主观。

- **假设 2**：SWE-Bench Verified / GAIA 分数可证明「架构重构未牺牲 agent 能力」。
  - **证据强度**：**中**——数字 competitive，但最优分依赖 Claude Sonnet 4.5 extended thinking；未与 V0 同配置 head-to-head，也未隔离「SDK 架构」与「默认 tool/prompt 套件」的贡献。

## 核心方法

四条设计原则映射 V0 痛点：

1. **Optional isolation**：默认 LocalConversation 单进程跑完整 agent loop；需隔离时换 `DockerWorkspace` 即可（Fig. 5 仅改 import）。
2. **Stateless by default, one source of truth**：组件 immutable；ConversationState 持 metadata + EventLog，FIFO lock 双路径更新（state-only vs event-append）；持久化时 metadata→`state.json`、events→逐文件 JSON，resume 靠 replay。
3. **Strict separation of concerns**：SDK 为 library；CLI/Web/GitHub App 消费 API，不 fork core logic。
4. **Two-layer composability**：部署层四包组合；能力层 typed component（Tool、LLM、AgentContext、Skill）可声明式扩展。

**Event-sourced 状态**：多级 Event 层次（Table 1）——LLMConvertibleEvent（action/observation）vs internal Event（condensation、state update）；支持 deterministic replay 与 pause/resume。

**LLM 层**：LiteLLM 统一 100+ provider；支持 Chat Completions 与 OpenAI Responses API（reasoning model）；`NonNativeToolCallingMixin` 为无 native function calling 的模型做 prompt-based 解析；`RouterLLM` 子类按消息内容选模型（Fig. 3 多模态路由示例）。

**Tool 系统**：Action–Execution–Observation 三段式 + Pydantic 校验；MCP tool 自动转 Action/Observation；Tool Registry 用 JSON-serializable spec + lazy resolver 支持跨进程/网络 distributed execution。

**Agent**：stateless event processor，`on_event` 回调分离生成与控制；支持 Skill（`.openhands/skills/`、`.cursorrules`、`agents.md`）、sub-agent delegation tool（blocking parallel）。

**Context**：Condenser 在超窗时写 CondensationEvent 摘要替换旧 event；默认 LLMSummarizingCondenser 据称 API 成本最高 **2×** 降幅且无性能退化（引用 blog，非本文主实验）。

**安全**：SecurityAnalyzer（LOW/MEDIUM/HIGH/unknown）+ ConfirmationPolicy；内置 LLMSecurityAnalyzer + ConfirmRisky；WAITING_FOR_CONFIRMATION 状态可动态调 policy。

**SecretRegistry**：per-conversation 隔离、执行时 late-bind、输出 mask、可加密序列化、mid-conversation 轮换。

**部署**：Agent Server（FastAPI REST + WebSocket）；官方 Docker 镜像 bundling VSCode Web、VNC、Chromium；RemoteConversation 与 LocalConversation API 一致。

最小示例 7 行（Fig. 2）：

```python
conversation = Conversation(agent=agent, workspace="/path/to/project")
conversation.send_message("Write 3 facts about this project into FACTS.txt.")
conversation.run()
```

## 设计取舍

- **取舍 1：默认 local 单进程 vs universal sandbox**——换 MCP 对齐、零容器开销、调试简单；牺牲默认开箱的安全隔离，把风险转给 deployment 配置 discipline。
- **取舍 2：Immutable 组件 + 单一可变 ConversationState vs 运行时灵活改 agent**——换 replay/recovery 一致性；改 LLM/tool/security policy 常需新 conversation 或显式 API，不如 V0 原地 patch 配置「方便」。
- **取舍 3：完整 EventLog 保留 + Condenser 摘要喂 LLM vs 硬截断**——换审计/replay 完整性；condensation 可能丢细节，长 horizon SWE 任务的信息损失 **未系统 ablate**。
- **取舍 4：内置 production server + 交互 workspace（VNC/VSCode/browser）vs library-only 轻量**——换 remote execution、human-in-the-loop、multi-tenancy 开箱能力；增加镜像体积、运维面、攻击面（暴露 VNC/browser 端口）。
- **取舍 5：LLM 自评 action 风险（LLMSecurityAnalyzer）vs 规则/外部 guardrail**——换 context-aware、累积风险推理；同一 LLM 既提案又评审，存在 prompt injection 与「自我批准」循环信任风险。
- **边界条件**：个人开发者 local 迭代、需要快速换 100+ LLM 的 research harness 最契合；强合规、强隔离 multi-tenant SaaS 仍需显式启用 DockerWorkspace + 自定义 ConfirmationPolicy，且要自行验证 server 层 SLO。

## 实验与结果

- **SWE-Bench Verified**（commit 54c5858 SDK / 88f1d80 benchmarks）：Claude Sonnet 4.5 + extended thinking **72%** resolution rate
- **GAIA val**：Claude Sonnet 4.5 **67.9%** accuracy
- **开源模型**：Qwen3 Coder 480B **41.21%**（SWE-Bench Verified）
- 相对 OpenHands-Versa **略优**，作者解读为架构重构未牺牲 agentic capability
- **Feature 对比**（Tab. 3，2025-10-29）：31 项中 15 项与至少一家竞品共有，**16 项 OpenHands 独有**（native remote execution + sandbox、built-in REST/WebSocket server、LLM action-level security analysis、model-agnostic routing + non-FC fallback 等）
- **QA 成本**：programmatic tests 每 commit 秒级；LLM integration tests **$0.5–$3**/run、**<5 min**；benchmark eval **$100–$1000**、数小时

## Critical Analysis

### 论证链条

链条 **V0 工程痛点（定性）→ 四原则 + 四包架构 → benchmark 不降反升 + feature 表** 对「production foundation」叙事基本闭合，但证据类型不均：架构论证偏 **case study + design rationale**，能力论证靠 **标准 benchmark 点估计**，中间缺少 **V0 vs V1 同 workload 的生产指标**（session 损坏率、恢复成功率、p99 延迟、多租户隔离事件）。

较强环节：V0 问题与 V1 设计的 **一一映射**清晰（Fig. 1）；Local→Remote 仅换 workspace 的 factory 模式有代码级可验证性；QA 三层金字塔（mock / real LLM / benchmark）与 SDK 定位一致。

较弱环节：(1) 「production-ready」claim 主要建立在 **feature checklist**，非大规模 deployment trace；(2) 72% SWE-Bench 高度依赖 **单一 frontier model + extended thinking**，难分离 SDK 与 model/prompt 贡献；(3) 与竞品的差异化部分来自 **snapshot 对比**，未量化「这些特性对真实用户留存/故障率的影响」。

### 假设压力测试

- **Local-default 安全性**：在开发者本机直接 `subprocess.run` 执行 agent 提议的 bash 时，LLMSecurityAnalyzer 误判或用户一键 approve 即可造成 host 破坏——**论文未报告**误报/漏报率或 red-team 结果。
- **Event replay 跨版本**：EventLog 逐文件 JSON + Pydantic schema 演进时旧 session 是否可 replay **未讨论**；对「durable state management」claim 是缺口。
- **Remote 多租户**：V0 已观察到「一用户大截图拖垮共享容器」；V1 每 agent 独立 container 缓解，但 **资源 limit、noisy neighbor、WebSocket fan-out 规模** 无定量评估。
- **Condenser 2× 成本**：引用外部 blog（Smith, 2025），本文 Tab. 2 未含 condensation ablation；长对话 SWE 任务上摘要是否丢关键 stack trace **未验证**。
- **Sub-agent delegation**：当前 blocking parallel；异步 fault-tolerant orchestration 标为 user-defined tool 可扩展，但 production 级超时、partial failure 语义 **论文未定义**。

### 实验可信度

- **Benchmark**：SWE-Bench Verified + GAIA 代表 software engineering 与 general computer use，合理；**缺** WebArena、OSWorld、多租户 trace、安全 red-team benchmark。
- **Baseline**：与 OpenHands-Versa 对比偏内部；**未与** Claude Code、Devin、SWE-Agent 等同期系统在同 commit 下 head-to-head（可理解，因本文主题是 SDK 非 SOTA 竞赛）。
- **Ablation**：无「关掉 event-sourcing / 关掉 condenser / local-only vs remote」的架构组件分解实验。
- **Metric**：resolution rate / accuracy 覆盖能力面；**缺** end-to-end latency、token 成本分布、session recovery 成功率、security analyzer 拦截率、server 层 p99 event delivery delay。
- **可复现性**：给出具体 commit hash + MIT 开源 repo，加分；benchmark 与 SDK 分仓，依赖版本 pin 策略 **正文未详述**。

### 系统性缺陷

- **尾延迟与可用性**：WebSocket event streaming 在弱网下行为、重连后 state 同步 **论文未讨论**。
- **可观测性**：event stream 利于 UI，但 distributed trace（client→server→tool→sandbox）统一关联 ID **论文未讨论**。
- **运维成本**：Docker 镜像 bundling VSCode+VNC+Chromium 的镜像大小、启动时间、GPU 需求 **未量化**；对比 library-only SDK 的 TCO 缺失。
- **兼容性**：深度绑定 LiteLLM、FastMCP、Pydantic discriminated unions；provider API 变更的 shim 维护成本由用户承担，**论文未讨论** SLA。
- **正确性**：security analyzer 与 agent 共用 LLM，无独立 verifier；confirmation 拒绝后的 retry 策略可能导致行为非确定性。

## 局限与 Future Work

- **局限 1**：生产就绪性论证以 **架构特性 + benchmark 点估计** 为主，缺 multi-tenant production trace（故障率、恢复时间、成本）。
- **局限 2**：V0→V1 迁移的 **定量收益**（配置 bug 数、session 损坏率、release 周期）未报告，外推「解决了 V0 痛点」主要靠叙事。
- **局限 3**：Feature 对比表截至 2025-10-29，竞品快速迭代后差异化可能缩水。
- **局限 4**：LLM-based security analysis 的 adversarial robustness、误报漏报率 **未评估**。
- **Future work 1**：在真实 SaaS 部署上测量 **session recovery 成功率、p99 event latency、per-tenant 资源隔离事件率**，把「production foundation」从 feature claim 落到 SLO。
- **Future work 2**：对 Condenser 做 **task-success vs context-length** 曲线，量化摘要导致 SWE-Bench 回归的临界点。
- **Future work 3**：独立 security evaluator（规则 + 小模型 + LLM ensemble）与 **red-team benchmark**，量化 LLMSecurityAnalyzer 相对硬编码 guardrail 的 tradeoff。
- **Future work 4**：V0 vs V1 **controlled migration study**——同 model、同 task、同 hardware 下的可靠性、成本、开发者迭代时间对比。

## 相关

- **相关概念**：event sourcing、MCP、software agent、Action–Observation loop
- **前置平台**：[[OpenHands-ICLR25]]
- **同类系统**：Claude Agent SDK、OpenAI Agents SDK、Google ADK、LangGraph、Devin、Claude Code
- **评测**：SWE-Bench Verified、GAIA、OpenHands-Versa
- **同会议**：[[MLSys-2026]]
- **互补方向**：[[ADR-MLSys26]]（企业 agent 安全）、[[HIPPOCAMPUS-MLSys26]]（agent 记忆）、[[OSWorld-Human-MLSys26]]（computer-use 延迟）