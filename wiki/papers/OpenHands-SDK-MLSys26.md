---
type: paper
name: OpenHands-SDK
full_title: "The OpenHands Software Agent SDK: A Composable and Extensible Foundation for Production Agents"
authors: [Xingyao Wang, Simon Rosenberg, Juan Michelini, Calvin Smith, Hoang Tran, Engel Nyst, et al.]
venue: MLSys
year: 2026
tags: [agent, sdk, sandbox, software-engineering, mcp]
source_pdf: "[[5fd0b37cd7dbbb00f97ba6ce92bf5add.pdf]]"
source_md: "[[5fd0b37cd7dbbb00f97ba6ce92bf5add]]"
---

# The OpenHands Software Agent SDK: A Composable and Extensible Foundation for Production Agents (MLSys 2026)

> **一句话总结**：OpenHands V1 将 64k+ star 的 monolithic agent 重构为四包模块化 SDK（可选 sandbox、event-sourced 状态、100+ LLM 路由、内置 REST/WebSocket server），在 SWE-Bench Verified 与 GAIA 上达到强 benchmark 表现，比 OpenAI/Claude/Google SDK 多 16 项独有生产特性。

## 问题

生产级 software engineering agent 需要：灵活实验、安全可靠执行、多界面交互。OpenHands V0 的 monolithic 设计（强制 sandbox、140+ 配置字段、agent 与 app 紧耦合）在规模化后暴露 rigid sandboxing、mutable config sprawl、benchmark 依赖泄漏等问题，亟需 V1 架构重设计。

## 核心方法

四条设计原则驱动 **OpenHands Software Agent SDK**：

1. **Optional isolation**：默认本地单进程执行，sandbox 按需开启
2. **Stateless by default**：Agent/Tool/LLM 为不可变 Pydantic 模型，仅 ConversationState 可变
3. **Strict separation**：SDK 与 CLI/Web/GitHub App 解耦
4. **Two-layer composability**：SDK / Tools / Workspace / Agent Server 四包可组合

核心组件：event-sourced EventLog、Action–Execution–Observation 工具体系、MCP 集成、RouterLLM 多模型路由、Security analyzer、本地/远程 workspace 透明切换。对比 31 项特性，独有 16 项（native remote execution、production server、sandboxing、model-agnostic routing 等）。

## 关键结果

- 多 LLM backend 在 **SWE-Bench Verified** 与 **GAIA** 上达到 competitive / SOTA 级结果
- 最小示例 7 行代码即可启动 agent conversation
- MIT 开源：https://github.com/OpenHands/software-agent-sdk
- 相比 V0：消除 duplicated local MCP/tool 实现，支持 deterministic replay 与 session recovery

## 相关

- **相关概念**：software agent、MCP、event sourcing
- **同类系统**：OpenHands V0、Claude Agent SDK、OpenAI Agents SDK、Google ADK、Devin
- **同会议**：[[MLSys-2026]]