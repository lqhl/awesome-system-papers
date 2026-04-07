# The OpenHands Software Agent SDK: A Composable and Extensible Foundation for Production Agents

**作者**：Xingyao Wang, Simon Rosenberg, Juan Michelini, Calvin Smith, Hoang Tran, Engel Nyst, Rohit Malhotra, Xuhui Zhou, Valerie Chen, Robert Brennan, Graham Neubig（All Hands AI）
**会议**：MLSys 2026
**链接**：[GitHub](https://github.com/OpenHands/software-agent-sdk)
**源文件**：[[5fd0b37cd7dbbb00f97ba6ce92bf5add.pdf]]

---

## 一、背景

AI 软件工程 Agent 已从辅助工具（GitHub Copilot、Cursor）演进为能自主执行复杂任务的系统（Devin、Claude Code、OpenHands）。将 Agent 可靠部署到生产环境需要持久状态管理、安全沙箱执行、以及在本地到容器化云部署等多种环境中保持一致行为的系统基础。OpenHands 作为开源软件 Agent 框架，已获 64k+ GitHub Stars，但其早期单体架构（V0）在扩展过程中暴露了严重的架构瓶颈。

---

## 二、要解决的问题

OpenHands V0 的单体架构存在四个核心痛点：

1. **强制沙箱化的灵活性缺失**：V0 假设所有 tool call 必须运行在 Docker 容器内，导致 Agent 与沙箱两个独立进程状态可能不一致，容器崩溃会腐蚀会话。当需要支持本地执行（如 CLI、MCP）时，不得不添加旁路层和冗余的本地实现，架构日益脆弱。

2. **可变配置导致不确定状态**：配置系统混杂了部署、Agent 行为、LLM 路由、沙箱设置等多个域，跨 CLI/Web UI/GitHub App/SaaS 存在重叠的覆盖层级，导致相同参数的两次运行可能产生不同结果。配置膨胀至 140+ 字段、15 个类、2.8K 行代码。

3. **单体仓库的边界模糊**：Agent 核心、评估套件与应用（前端、后端、CLI）混在同一代码库，benchmark 依赖泄漏到主应用，部署笨重且脆弱。

4. **缺乏可组合的扩展架构**：添加新行为需要修改核心逻辑或为特定入口创建分支，缺乏结构化的可组合性和可扩展性。

---

## 三、洞察与设计

**关键洞察**：软件工程 Agent 的核心与其应用（CLI、Web UI、GitHub App）之间必须严格分离，Agent 组件（LLM、Tool、Agent 本身）应当是不可变的，所有可变状态应集中在唯一的会话状态对象中——这样才能实现确定性重放、故障恢复和跨环境一致性。

基于此洞察，OpenHands V1 围绕四个设计原则重构：

**1. 可选隔离（Optional Isolation）**：Agent 默认本地运行，沙箱化为 opt-in。统一 Agent 与工具执行在单一进程中，与 MCP 的本地执行假设对齐。

**2. 默认无状态，状态单一来源（Stateless by Default）**：Agent、Tool、LLM 等组件均为不可变的 Pydantic 模型，在构造时验证。唯一可变实体是 `ConversationState`，包含元数据字段和 append-only 的 `EventLog`。

**3. 事件溯源状态管理（Event-Sourced State）**：所有交互作为不可变事件追加到日志。事件系统采用多层继承：`Event` → `LLMConvertibleEvent` → `ActionEvent`/`ObservationBaseEvent`。会话恢复通过加载 `base_state.json` 并重放事件目录实现。

**4. 四包模块化设计**：
- `openhands.sdk`：核心抽象（Agent、Conversation、LLM、Tool、MCP、事件系统）
- `openhands.tools`：具体工具实现
- `openhands.workspace`：执行环境（Docker、远程 API）
- `openhands.agent_server`：REST/WebSocket API 服务器

**工具系统**采用 Action–Execution–Observation 模式，Action 定义输入 schema（Pydantic 验证），ToolExecutor 执行逻辑，Observation 封装输出。MCP 工具被视为一等公民，自动转换 JSON Schema 到 Action 模型。工具注册表支持分布式架构，工具规格可作为纯 JSON 跨进程/网络传输。

**LLM 抽象层**通过 LiteLLM 支持 100+ 提供商，原生支持推理/扩展思考（Anthropic ThinkingBlock、OpenAI ReasoningItemModel），`NonNativeToolCallingMixin` 让不支持 function calling 的模型也能使用工具，`RouterLLM` 支持多模型路由。

**安全机制**包含 `SecurityAnalyzer`（对每个 tool call 评估风险等级）和 `ConfirmationPolicy`（决定是否需要用户确认），支持动态调整信任策略。

---

## 四、实现细节

**事件持久化**：双路径设计——元数据字段序列化到 `base_state.json`，事件作为独立 JSON 文件增量写入事件目录，避免重写大型历史。

**上下文窗口管理**：`Condenser` 系统在历史过长时丢弃事件并替换为摘要。`LLMSummarizingCondenser`（默认）可将 API 成本降低 2× 而不降低性能。凝缩结果作为 `CondensationEvent` 存入事件日志，保持凝缩器无状态。

**本地到远程转换**：`Conversation` 作为工厂入口，传入 `LocalWorkspace` 返回 `LocalConversation`（进程内执行），传入 `RemoteWorkspace` 透明构建 `RemoteConversation`（通过 HTTP/WebSocket 委托到 Agent Server）。切换仅需更换 workspace 类型，其余代码不变。

**Agent Server**：基于 FastAPI 实现，REST 端点管理会话生命周期，WebSocket 实时流式传输事件。官方 Docker 镜像捆绑完整 Agent Server 栈（API Server、VSCode Web、VNC 桌面、Chromium 浏览器），每个 Agent 实例运行在独立容器中。

**Secret Registry**：每会话实例，工具仅在执行时访问密钥，输出中自动掩码敏感值。Bash Tool 扫描命令中的 secret key，导出为环境变量并替换结果中的出现。支持可加密序列化和会话中动态更新。

**Agent 卡住检测**：自动检测病态状态（无限循环、重复冗余 tool call），检测到后自动终止。

**测试体系**：三层策略——Programmatic Tests（每次提交，mock LLM），LLM-based Tests（每日/PR 触发，使用真实模型，$0.5–$3/次），Benchmark Evaluation（按需，$100–1000/次）。

---

## 五、实验结果

| Benchmark | 模型 | 性能 |
|---|---|---|
| SWE-Bench Verified | Claude Sonnet 4.5 | 72.8% |
| SWE-Bench Verified | Claude Sonnet 4 | 68.0% |
| SWE-Bench Verified | GPT-5 (reasoning=high) | 68.8% |
| SWE-Bench Verified | Qwen3 Coder 480B A35B | 65.2% |
| GAIA (val set) | Claude Sonnet 4.5 | 67.9% |
| GAIA (val set) | Claude Sonnet 4 | 57.6% |
| GAIA (val set) | GPT-5 (reasoning=high) | 62.4% |
| GAIA (val set) | Qwen3 Coder 480B A35B | 41.2% |

与 OpenAI Agents SDK、Claude Agent SDK、Google ADK 的 31 项功能对比中，OpenHands SDK 独有 16 项功能，包括原生远程执行、内置生产服务器、模型无关的多 LLM 路由、非 function-calling 模型支持等。其他 SDK 均未提供内置 REST/WebSocket 服务器、Agent 环境沙箱化、VNC/VSCode/Chromium 交互式工作空间。

---

## 六、批判性分析

1. **Benchmark 选择有限且缺乏消融实验**：仅在 SWE-Bench Verified 和 GAIA 两个 benchmark 上评估，且没有任何消融实验来验证架构各组件（事件溯源、Condenser、安全分析器等）的独立贡献。论文声称的架构优势完全缺乏实验支撑。

2. **功能对比表存在明显偏见**：Tab. 3 的 31 项功能中有大量 OpenHands 特有的生产服务器功能（VNC、VSCode Web、内置 Chromium 等），这些是 OpenHands 作为完整平台的特性而非 SDK 核心能力。将库级 SDK（OpenAI、Claude）与全栈平台对比，不在同一抽象层级上，比较不够公平。

3. **性能基线不充分**：没有与 OpenHands V0 在相同 benchmark 上的对比，无法验证架构重构是否带来了实际性能提升。论文称性能"与 OpenHands-Versa 相当"，但 Versa 是研究系统而非生产 SDK，这个对比不能说明架构重构的价值。

4. **安全分析器的有效性未经验证**：`LLMSecurityAnalyzer` 用 LLM 本身来评估 tool call 风险等级，但没有任何实验数据证明其准确率和误报率。在生产环境中，LLM 对安全风险的判断可靠性是关键问题，论文对此完全回避。

5. **可扩展性声明缺乏数据支撑**：论文反复强调"生产就绪"和"可扩展部署"，但没有提供任何并发会话数、延迟、吞吐量或资源利用率的数据。多租户场景下的隔离性和性能表现完全未知。

6. **Condenser 效果的引用不足**：声称 LLMSummarizingCondenser 可将 API 成本降低 2× 而不降低性能，但仅引用了一篇博客文章作为证据，缺乏系统性的实验验证。

---

## 七、AI Infra / MLSys 视角

1. **事件溯源架构对 Agent 系统的启示**：将所有 Agent 交互建模为不可变事件并支持确定性重放，这一设计对长时间运行的 AI Agent 系统（如自动化代码审查、持续集成 Agent）具有直接参考价值。事件溯源使得 Agent 调试、故障恢复和行为审计成为可能。

2. **多 LLM 路由的实用价值**：`RouterLLM` 抽象允许根据输入内容（文本 vs 图像）、成本或延迟动态选择模型。在 AI Infra 中，这对异构模型部署和成本优化有直接应用——例如将简单任务路由到小模型、复杂推理路由到大模型。

3. **沙箱化执行的设计取舍**：从"强制沙箱"到"可选沙箱"的转变，为 Agent 执行环境的设计提供了有价值的经验。在推理服务系统中，类似的"默认本地、按需隔离"模式可以减少不必要的容器开销。

4. **值得跟进的方向**：
   - **Agent 成本优化**：Condenser 机制与模型路由结合，系统化地优化长时间 Agent 会话的推理成本
   - **Agent 可观测性**：基于事件溯源的 Agent 行为追踪和异常检测框架
   - **安全 Agent 执行**：更可靠的 tool call 风险评估机制（不依赖 LLM 自身判断），如基于静态分析或策略引擎

---

## 八、总结

OpenHands Software Agent SDK 通过对 OpenHands V0 的完整架构重构，提出了一个基于事件溯源、不可变组件和四包模块化设计的软件工程 Agent 框架。其核心贡献在于统一了本地开发与远程生产部署的执行模型，提供了类型安全的工具系统和灵活的 LLM 抽象。SDK 在 SWE-Bench 和 GAIA 上展现了跨多模型的竞争力性能。主要局限在于缺乏架构消融实验、安全机制有效性验证以及生产规模可扩展性数据——论文更多是一篇系统设计论文而非实验驱动的研究。
