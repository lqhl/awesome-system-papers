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
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-27
---

# OpenHands：面向通用软件开发智能体的开放平台（ICLR 2025）

> **原题**：OpenHands: An Open Platform for AI Software Developers as Generalist Agents

> **一句话总结**：社区驱动（32K GitHub stars、188+ contributors）的通用 AI 开发者智能体平台，前身 OpenDevin，核心观察是「软件接口（bash/Python/browser）」足以覆盖人类开发者的大部分交互；以 CodeAct 式事件流 + Docker 沙箱统一智能体/运行时间/UI，同一 CodeActAgent 不改提示词在 15 个基准上保持通用性——CodeActAgent v1.8（claude-3.5-sonnet）SWE-Bench Lite 26.0%、WebArena 15.3%、GPQA 52.0%。

## 问题与动机

LLM 智能体研究爆发，但现有框架往往**偏科**：[[LangChain]] / [[AutoGen]] 等通用框架缺内置沙箱、browser、标准化工具 library 和统一评测；[[SWE-Agent]]、Aider、AutoCodeRover 等 SWE 专精系统又在 web browsing、多模态辅助任务上缺能力。作者论断要解决的是：**如何搭建一个既像人类开发者一样通过软件与世界交互、又能支撑社区扩展与系统评测的通用智能体平台**。

动机来自两个判断：（1）软件是人类当前最强大的世界交互接口，现有开发/部署 toolchain 成熟；（2）智能体开发与评测本身已成为工程难题——需要统一动作空间、安全执行环境、可复用 ACI（智能体-Computer Interface）、多智能体协作与人类介入、以及跨基准的评测 harness。OpenHands（f.k.a. OpenDevin）不是只提概念，而是 MIT 许可下的可运行实现：AgentHub 10+ 智能体、chat UI、15 个集成基准、integration test 框架。

## 关键观察 / 隐含假设

- **观察 1**：人类软件工程师的核心交互可收敛到三类 primitive——bash 命令、Python（IPython）代码、浏览器操作；用 programming language 作为动作空间（[[CodeAct]] 思想）比 JSON 工具 schema 更表达力强，且智能体可现场写 Python function 扩展工具。
  - **依赖假设**：目标任务的 API/环境可通过 PL 调用或包装；LLM 对 bash/Python/browser DSL 的 codegen 足够可靠。
  - **可能失效场景**：强 GUI 原生应用、闭源专有 IDE 插件、需要精细视觉依据锚定要求高的复杂 web（论文也承认 browsing 仍弱）；纯对话式任务用 PL 动作反而冗余。

- **观察 2**：[[SWE-Agent]] 证明 **ACI 质量**（file edit、scroll 等专用工具）对复杂仓库任务至关重要；但 每个智能体维护工具的工程成本高。
  - **依赖假设**：少数「LLM 直接写代码做不好」或「需调外部模型」的 skill 值得标准化进 AgentSkills library，其余交给 LLM 自带知识（如不重复包装 pandas）。
  - **可能失效场景**：新领域需要大量 bespoke 工具时，library 膨胀与版本兼容会成为瓶颈；长文件编辑仍是论文明确承认的痛点。

- **观察 3**：**Event stream**（动作/观察时序日志）可同时服务智能体推理、UI 可视化、运行时间执行与 replay，是 UI/智能体/运行时间解耦的正确抽象。
  - **依赖假设**：任务可建模为离散步骤；观察体积可控（browser DOM/HTML/screenshot 可能很大）。
  - **可能失效场景**：超长 horizon 任务导致 context 爆炸——论文未系统测量尾延迟或 context 截断策略对 SWE-Bench 的影响。

- **假设 1**：每 session 一个 **Docker 沙箱** 足以兼顾安全与 fidelity，且用户可提供任意 base image。
  - **证据强度**：中——架构合理、支持 arbitrary image build，但论文未深入讨论容器逃逸、网络 egress 策略、多 tenant 资源隔离。

- **假设 2**：**同一 generalist 智能体不改系统提示词** 即可在 SWE / Web / Misc 三类任务上同时有竞争力，这本身是有价值的平台目标。
  - **证据强度**：中强——表 3 支持该叙事，但 SWE 上仍略低于 Aider（26.3%）/ Moatless（26.7%）/ Agentless（27.3%），WebArena 也低于 Auto Eval & Refine（20.2%）。

## 核心方法

**三大组件**（图 2）：智能体 abstraction、Event stream、运行时间。

**智能体 abstraction**：核心 API 是 `step(state) -> action`。`State` 含完整事件流（历史动作/观察、用户消息）、LLM 累计成本、多智能体 delegation 元数据等。社区实现挂到 AgentHub；默认 generalist 为 **CodeActAgent**（基于 [[CodeAct]]），每步可自然语言对话或执行代码动作。

**Action space**：
- `CmdRunAction`：沙箱内 bash
- `IPythonRunCellAction`：Jupyter 执行 Python
- `BrowserInteractiveAction`：BrowserGym DSL 驱动 Playwright Chromium

与 JSON function-calling 兼容：用户可用 Python 定义工具再暴露给智能体；智能体也可自建工具（写函数即用）。

**运行时间**：每任务 session 启动隔离 Docker 容器，内嵌 OpenHands 动作执行 API（REST）。挂载用户 workspace；支持任意 base image——build 流程把运行时间 client 注入镜像（hash tag + generic tag 双标签保证可复现与迭代）。Client 负责壳层、IPython、browser 执行并把结果写回事件流。

**AgentSkills library**：标准化 ACI。收录 `edit_file`、`scroll_up/down`、`parse_image`、`parse_pdf` 等——原则是不重复 LLM 已会的基础库，只补「直接写代码困难」或「需外部模型」的能力。通过 IPython 自动 import，所有智能体共享。

**Multi-智能体 delegation**：`AgentDelegateAction` 把子任务转给专用模块（如 CodeActAgent 把 web 任务 delegate 给 BrowsingAgent）。

**Evaluation 框架**：集成 15 个基准（software / web / misc），统一 harness；强调与**未针对基准内容手工提示词工程** 的开源基线对比。

**智能体 QC**：借鉴软件 integration test——mock LLM 做确定性提示词 regression，覆盖多平台沙箱（Linux/Mac、局部/SSH/exec），避免每次改代码跑全量基准。

**GUI**：chat UI 直连事件流，可实时查看 bash/Python/browser 行为并 interrupt 给反馈（人类参与闭环）。

## 设计取舍

- **取舍 1：PL-first 动作空间 vs 纯工具-calling**——获得表达力与可扩展性（智能体可写代码造工具），牺牲对非编程任务的简洁性，且 codegen 错误会直接在沙箱里爆炸，依赖 Docker 隔离兜底。
- **取舍 2：Generalist single 提示词 vs per-基准专用模块**——一个 CodeActAgent 跨 15 个基准不改提示词，换取任一单项榜单未必 SOTA；对比 Aider/Agentless 等 SWE 专精优化，OpenHands 选择平台通用性。
- **取舍 3：AgentSkills 最小集 vs 大而全工具 hub**——降低维护负担，但把领域特化能力推给社区 micro 智能体或自写 Python。
- 取舍 4：Docker-per-session 安全 vs 启动开销——安全边界清晰，但冷启动、镜像 build、长任务资源占用成本高；论文报告 SWE-Bench Lite 上 claude-3.5-sonnet 平均 $1.10/instance。
- **边界条件**：在「需要仓库级编辑 + 测试反馈」的 SWE 任务上架构合适；在「需 RL 训练专用模块模型」的 MiniWoB++ 全量集（CC-NET 91.1%）上，zero-shot LLM 智能体明显吃亏；在「24h 持续迭代」的 ML 工程（见 [[MLE-Bench-ICLR25]]）上，OpenHands 脚手架弱于 AIDE 的树搜索 persistence。

## 实验与结果

- **SWE-Bench Lite**（300 instances，无 hint）：CodeActAgent v1.8 + claude-3.5-sonnet **26.0%** resolve rate（$1.10/instance）；gpt-4o **22.0%**；gpt-4o-mini **7.0%**（$0.01）。对比 SWE-智能体 18.0%、AutoCodeRover 19.0%、Aider 26.3%、Moatless 26.7%、Agentless 27.3%
- **HumanEvalFix Python**（0-shot）：CodeActAgent v1.5 **79.3%**（$0.14/instance），约为 StarCoder2-15B（48.6%）两倍；低于 SWE-智能体 **87.7%**（但后者 1-shot demo）
- **BIRD text-to-SQL**（300 dev）：gpt-4o **47.3%** 执行准确率（$0.11）
- **ML-Bench**（quarter subset）：gpt-4o **76.5%**（$0.25），低于 Aider 64.4% 的对比项中 SWE-智能体 42.6%——OpenHands 在 ML 仓库任务上靠前
- **WebArena**（812 任务）：BrowsingAgent + claude-3.5-sonnet **15.5%**；CodeActAgent v1.8 delegate browsing **15.3%**；WebArena 智能体基线 14.4%
- **MiniWoB++**（125 envs 全量）：BrowsingAgent + gpt-4o **40.8%**（远低于 CC-NET 91.1%  专用模块）
- **GAIA L1 val**：GPTSwarm + gpt-4o **32.1%**（$0.05）
- **GPQA**：CodeActAgent v1.8 + claude-3.5-sonnet **52.0%**（$0.065），高于 gpt-4 few-shot CoT **38.8%**
- **AgentBench OS subset**：gpt-4o **57.6%**（$0.085）
- **MINT math**：gpt-4o **77.3%**（$0.07）
- **核心叙事验证**：同一 CodeActAgent 不改提示词在 SWE / Web / Misc 均有竞争力，而 column-专用模块基线通常只强于一类

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 同一 CodeActAgent 能在多类任务上取得有竞争力的结果 | §4，表 2–4：SWE-Bench Lite 26.0%、WebArena 15.5%、GPQA 52.0% | 各任务使用的基础模型和工具不同；不能归因于单一组件 | 中 |
| OpenHands 在软件修复上接近同期专用方法 | 表 2：SWE-Bench Lite 26.0%，Aider 26.3%、Moatless 26.7%、Agentless 27.3% | 300 个 Lite 实例；Claude 3.5 Sonnet；无提示 | 强 |
| 通用平台在高度专门化的浏览任务上仍明显落后 | 表 3：MiniWoB++ 为 40.8%，专用 CC-NET 为 91.1% | 125 个环境；模型、训练方式和工具不同 | 强 |
| 模型选择显著影响同一平台的表现与成本 | 表 2：SWE-Bench Lite 上 Claude 26.0%、GPT-4o 22.0%、GPT-4o-mini 7.0% | CodeActAgent v1.8；每实例成本从 0.01 到 1.10 美元 | 强 |

## 批判性分析

### 论证链条

论文链条是：软件接口足够通用 → CodeAct 式 PL 动作 + Docker 运行时间实现该接口 → AgentSkills 补 ACI 短板 → 事件流统一 UI/智能体/评测 → 15 基准上单一 generalist 仍 competitive。链条在「平台工程」层面闭合度高：架构图、API、开源规模、基准集成都有证据。

薄弱环节在「generalist 足够好」向「生产环境 digital worker」的外推：SWE 26% 只是略入专用模块区间，距离可靠自主修 issue 仍远；WebArena 15% 说明真实 web 规划仍极难。论文诚实承认未夺魁，但表 1 框架对比表部分 OCR 损坏，削弱了对竞品缺口的定量说服力。

### 假设压力测试

- **工作负载变化**：仓库更大、单文件更长时，file editing 瓶颈可能压过动作空间设计——§A 已承认 long-file editing 是主要痛点。
- **模型变化**：结果强依赖 claude-3.5-sonnet / gpt-4o；换弱模型（gpt-4o-mini SWE 7%）后 generalist 叙事仍成立但实用价值骤降。
- **部署变化**：Docker 假设在 K8s 多租户、无 Docker 桌面环境或物理隔离（air-gapped）集群中需要额外工程；论文未讨论。
- **评测变化**：默认 SWE-Bench **Lite** 且**无 hint** 节省成本，但与生产环境 issue 分布是否一致未验证；若干基准用子集（ML-Bench quarter、ToolQA easy、GAIA L1 only）。

### 实验可信度

- **正面**：基线选择覆盖 SWE/Web/Misc 多条线；报告 avg 成本；强调 0-shot、无基准专用提示词 hacking；15 个基准集成对平台论文合适。
- **疑点**：部分数字标注版本不一致（如 GPQA 53.1% 标注来自 v1.5 而主表用 v1.8）；与专用模块对比时 HumanEvalFix 的 1-shot vs 0-shot 不对等；缺少延迟、步骤数、失败模式分布等系统指标。
- **缺失**：无尾延迟、无沙箱启动时间、无多智能体 delegation 相对单智能体的消融实验、无 AgentSkills 逐项消融。

### 系统性缺陷

- **安全**：Docker 隔离 + 人类参与闭环 UI 是主要防线；§B 讨论伦理但未量化 red-team（命令注入、数据外泄、恶意 browsing）。生产级 egress 控制、secret 管理论文未讨论。
- **可观测性**：事件流利于 replay/调试，但是否支持 distributed 轨迹、成本 cap、步骤预算论文未展开。
- **故障恢复**：容器崩溃、browser hang、LLM 超时的恢复语义未系统描述。
- **运维成本**：每 instance 美元成本可测，但 15 基准全跑仍昂贵；integration test 缓解开发回归，不能替代端到端 SLA 验证。
- **社区治理**：32K stars / 188 contributors 证明吸引力，但 also 带来 API 稳定性、智能体质量参差等维护风险——论文未深入。

## 局限与后续工作

- **局限 1**：复杂长任务、长文件编辑、强 browsing 仍明显弱于专用模块或训练型智能体（§A）。
- **局限 2**：工作流仍大量 handcraft，缺自动工作流生成（作者寄望 GPTSwarm / LangGraph 类图优化）。
- **局限 3**：多模态支持依赖零散 skills，缺 principled IPython/browser 多模态管线。
- **局限 4**：评测子集与成本裁剪（SWE-Lite、无 hint）可能高估或低估真实场景表现——需生产环境轨迹验证。
- **后续工作 1**：集成 Auto Eval & Refine + Reflexion 到 browsing 智能体，用可测的重试-on-error 提升 WebArena。
- **后续工作 2**：以 GPTSwarm 图结构做 RL/meta-prompting 自动优化智能体工作流，减少 handcraft。
- **后续工作 3**：针对 long-file editing 做 ACI 或 diff 策略对照实验，量化对 SWE-Bench 的边际收益。
- **后续演进**：[[OpenHands-SDK-MLSys26]] 将 monolith 拆为四包模块化 SDK，面向更可维护的生产集成。

## 相关

- **相关概念**：[[CodeAct]]、智能体-Computer Interface、Event Stream、Docker Sandbox、BrowserGym、Integration Testing
- **同类系统**：[[SWE-Agent]]、AutoCodeRover、Aider、Moatless、Agentless、[[AutoGen]]、MetaGPT、[[LangChain]]、GPTSwarm、AutoGPT
- **相关基准**：SWE-Bench、[[MLE-Bench-ICLR25]]、WebArena、GAIA、GPQA、HumanEvalFix、AgentBench、MINT
- **后续工作**：[[OpenHands-SDK-MLSys26]]
- **同主题**：[[Auto-Research]]
