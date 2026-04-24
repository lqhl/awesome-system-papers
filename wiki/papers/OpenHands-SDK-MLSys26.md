---
type: paper
name: OpenHands-SDK
full_title: "The OpenHands Software Agent SDK: A Composable and Extensible Foundation for Production Agents"
authors: [Xingyao Wang, Simon Rosenberg, Juan Michelini, Calvin Smith, Hoang Tran, "et al."]
venue: MLSys
year: 2026
tags: [agent, sdk, software-engineering, swe-bench, production]
source_pdf: "[[5fd0b37cd7dbbb00f97ba6ce92bf5add.pdf]]"
source_md: "[[5fd0b37cd7dbbb00f97ba6ce92bf5add]]"
---

# The OpenHands Software Agent SDK (MLSys 2026)

> **一句话总结**：把 64k stars 的 OpenHands 从 monolith 重构成四包 modular SDK（sdk/tools/workspace/agent-server），用 event-sourced state + opt-in sandboxing + 100+ LLM 路由，在 SWE-Bench Verified 和 GAIA 上达 SOTA，并在 31 项特性中有 16 项独一无二（vs OpenAI/Claude/Google Agent SDK）。

## 问题

软件工程 agent 从辅助工具演化成能跑数小时异步任务的自主系统（Devin、Claude Code、OpenHands），production 部署需要：持久状态管理、沙箱安全执行、跨环境一致行为（本地到云容器）。OpenHands V0 是 monolithic 架构，暴露出四大架构张力：

1. **Universal sandboxing vs local flexibility**：V0 假设所有 tool 调用都在 Docker 里，MCP 场景下需要大量 bypass 层
2. **Mutable config vs deterministic state**：140+ 配置字段、15 个类、2.8K 行配置代码，覆盖层叠乱
3. **Monorepo vs modular**：agent core、eval、frontend、backend、CLI 挤一起，依赖冲突严重
4. **Monolith vs extensible**：缺少 composability，小改动都要 hack core

## 核心方法

V1 四原则 → 四包架构：

- `openhands.sdk`：核心抽象（Agent、Conversation、LLM、Tool、MCP）+ 事件系统
- `openhands.tools`：具体 tool 实现
- `openhands.workspace`：执行环境（Docker、hosted API）
- `openhands.agent_server`：REST/WebSocket 服务器

**九大 SDK 组件**：

- **Event-Sourced State Management**：所有交互 append 到 immutable event log；`ConversationState` 是唯一 mutable component，维护 metadata + `EventLog`；支持 deterministic replay 和断点续传（只写新 event 到 disk，不重写历史）
- **LLM 抽象层**：LiteLLM 桥 100+ providers；原生支持 reasoning/thinking block（Anthropic ThinkingBlock、OpenAI ReasoningItemModel）；`NonNativeToolCallingMixin` 对无 function calling 的模型做 prompt-based fallback；`RouterLLM` 提供 multi-LLM 路由（例：text→cheap 模型、images→multimodal 模型）
- **Tool System**：Action-Execution-Observation 三段式，Pydantic 验证 LLM 生成的参数；统一 custom tool 与 [[MCP]] tool
- **Workspace 抽象**：同一 agent 可本地跑或远程容器化跑，代码改动最少
- **Security Analyzer**：LLM 对每个 action 打 LOW/MEDIUM/HIGH 风险，HIGH 触发人工确认；可自定义 `ConfirmationPolicy`
- **Context Condensation**：上下文窗口接近上限时自动 summarize，写入 `CondensationSummaryEvent`
- **Secrets Registry**：自动检测 bash 命令里的 API key/password 并 mask
- **Lifecycle Control**：pause/resume、sub-agent delegation、history restore

**设计原则总结**：
1. Optional isolation（sandbox opt-in）
2. Stateless by default（only `ConversationState` mutable）
3. Strict separation of concerns（SDK 是 shared library，不重复逻辑）
4. Two-layer composability（deployment package 层 + typed component 层）

## 关键结果

- 与 OpenAI Agents SDK / Claude Agent SDK / Google ADK 对比 31 项特性：15 项共享，**16 项 OpenHands 独有**（原生远程执行、生产 server+sandbox、100+ LLM 路由、security analyzer、pause/resume、auto context condensation、secrets masking、auto conversation titling 等）
- SWE-Bench Verified 和 GAIA 跨多个 LLM backend（Claude、GPT-5、Qwen3 等）达到 SOTA
- 最小使用例仅 6 行 Python：`LLM(...)` → `get_default_agent(llm)` → `Conversation(agent, workspace)` → `send_message` → `run`
- 核心仓库 64k+ GitHub stars，V1 全面 MIT 开源

## 相关

- **相关概念**：[[MCP]]、[[Agent]]、Event-Sourcing、Sandbox
- **同类系统**：OpenAI Agents SDK、Claude Agent SDK、Google ADK、LangGraph、Devin、Claude Code
- **相关 benchmark**：[[SWE-Bench]]、[[GAIA]]
- **同会议**：[[MLSys-2026]]
