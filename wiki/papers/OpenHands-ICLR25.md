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
last_reviewed: 2026-07-18
---

# OpenHands: An Open Platform for AI Software Developers as Generalist Agents (ICLR 2025)

> **一句话总结**：社区驱动（32K GitHub stars、188+ contributors）的通用 AI 开发者 agent 平台，前身 OpenDevin，核心观察是「软件接口（bash/Python/browser）」足以覆盖人类开发者的大部分交互；以 CodeAct 式 event stream + Docker sandbox 统一 agent/runtime/UI，同一 CodeActAgent 不改 prompt 在 15 个 benchmark 上保持 generality——CodeActAgent v1.8（claude-3.5-sonnet）SWE-Bench Lite 26.0%、WebArena 15.3%、GPQA 52.0%。

## 问题与动机

LLM agent 研究爆发，但现有框架往往**偏科**：[[LangChain]] / [[AutoGen]] 等通用框架缺内置沙箱、browser、标准化 tool library 和统一评测；[[SWE-Agent]]、Aider、AutoCodeRover 等 SWE 专精系统又在 web browsing、多模态辅助任务上缺能力。作者 claim 要解决的是：**如何搭建一个既像人类开发者一样通过软件与世界交互、又能支撑社区扩展与系统评测的通用 agent 平台**。

动机来自两个判断：（1）软件是人类当前最强大的世界交互接口，现有开发/部署 toolchain 成熟；（2）agent 开发与评测本身已成为工程难题——需要统一 action space、安全执行环境、可复用 ACI（Agent-Computer Interface）、multi-agent 协作与人类介入、以及跨 benchmark 的 evaluation harness。OpenHands（f.k.a. OpenDevin）不是只提概念，而是 MIT 许可下的可运行实现：AgentHub 10+ agent、chat UI、15 个集成 benchmark、integration test 框架。

## 关键观察 / 隐含假设

- **观察 1**：人类软件工程师的核心交互可收敛到三类 primitive——bash 命令、Python（IPython）代码、浏览器操作；用 programming language 作为 action space（[[CodeAct]] 思想）比 JSON tool schema 更表达力强，且 agent 可现场写 Python function 扩展 tool。
  - **依赖假设**：目标 task 的 API/环境可通过 PL 调用或包装；LLM 对 bash/Python/browser DSL 的 codegen 足够可靠。
  - **可能失效场景**：强 GUI 原生应用、闭源专有 IDE 插件、需要精细视觉 grounding 的复杂 web（论文也承认 browsing 仍弱）；纯对话式任务用 PL action 反而冗余。

- **观察 2**：[[SWE-Agent]] 证明 **ACI 质量**（file edit、scroll 等专用 tool）对复杂 repo 任务至关重要；但 per-agent 维护 tool 的工程成本高。
  - **依赖假设**：少数「LLM 直接写代码做不好」或「需调外部模型」的 skill 值得标准化进 AgentSkills library，其余交给 LLM 自带知识（如不重复包装 pandas）。
  - **可能失效场景**：新 domain 需要大量 bespoke tool 时，library 膨胀与版本兼容会成为瓶颈；长文件编辑仍是论文明确承认的痛点。

- **观察 3**：**Event stream**（action/observation 时序日志）可同时服务 agent 推理、UI 可视化、runtime 执行与 replay，是 UI/agent/runtime 解耦的正确抽象。
  - **依赖假设**：任务可建模为离散 step；observation 体积可控（browser DOM/HTML/screenshot 可能很大）。
  - **可能失效场景**：超长 horizon 任务导致 context 爆炸——论文未系统测量 tail latency 或 context 截断策略对 SWE-Bench 的影响。

- **假设 1**：每 session 一个 **Docker sandbox** 足以兼顾安全与 fidelity，且用户可提供任意 base image。
  - **证据强度**：中——架构合理、支持 arbitrary image build，但论文未深入讨论容器逃逸、网络 egress 策略、多 tenant 资源隔离。

- **假设 2**：**同一 generalist agent 不改 system prompt** 即可在 SWE / Web / Misc 三类任务上同时有竞争力，这本身是有价值的平台目标。
  - **证据强度**：中强——Table 3 支持该叙事，但 SWE 上仍略低于 Aider（26.3%）/ Moatless（26.7%）/ Agentless（27.3%），WebArena 也低于 Auto Eval & Refine（20.2%）。

## 核心方法

**三大组件**（Fig. 2）：Agent abstraction、Event stream、Runtime。

**Agent abstraction**：核心 API 是 `step(state) -> action`。`State` 含完整 event stream（历史 action/observation、用户消息）、LLM 累计成本、multi-agent delegation 元数据等。社区实现挂到 AgentHub；默认 generalist 为 **CodeActAgent**（基于 [[CodeAct]]），每步可自然语言对话或执行 code action。

**Action space**：
- `CmdRunAction`：sandbox 内 bash
- `IPythonRunCellAction`：Jupyter 执行 Python
- `BrowserInteractiveAction`：BrowserGym DSL 驱动 Playwright Chromium

与 JSON function-calling 兼容：用户可用 Python 定义 tool 再暴露给 agent；agent 也可自建 tool（写函数即用）。

**Runtime**：每任务 session 启动隔离 Docker 容器，内嵌 OpenHands action execution API（REST）。挂载用户 workspace；支持任意 base image——build 流程把 runtime client 注入镜像（hash tag + generic tag 双标签保证可复现与迭代）。Client 负责 shell、IPython、browser 执行并把结果写回 event stream。

**AgentSkills library**：标准化 ACI。收录 `edit_file`、`scroll_up/down`、`parse_image`、`parse_pdf` 等——原则是不重复 LLM 已会的基础库，只补「直接写代码困难」或「需外部模型」的能力。通过 IPython 自动 import，所有 agent 共享。

**Multi-agent delegation**：`AgentDelegateAction` 把子任务转给 specialist（如 CodeActAgent 把 web 任务 delegate 给 BrowsingAgent）。

**Evaluation framework**：集成 15 个 benchmark（software / web / misc），统一 harness；强调与**未针对 benchmark 内容手工 prompt engineering** 的开源 baseline 对比。

**Agent QC**：借鉴软件 integration test——mock LLM 做确定性 prompt regression，覆盖多平台 sandbox（Linux/Mac、local/SSH/exec），避免每次改代码跑全量 benchmark。

**GUI**：chat UI 直连 event stream，可实时查看 bash/Python/browser 行为并 interrupt 给反馈（human-in-the-loop）。

## 设计取舍

- **取舍 1：PL-first action space vs 纯 tool-calling**——获得表达力与可扩展性（agent 可写代码造 tool），牺牲对非编程 task 的简洁性，且 codegen 错误会直接在 sandbox 里爆炸，依赖 Docker 隔离兜底。
- **取舍 2：Generalist single prompt vs per-benchmark specialist**——一个 CodeActAgent 跨 15 个 benchmark 不改 prompt，换取任一单项榜单未必 SOTA；对比 Aider/Agentless 等 SWE 专精优化，OpenHands 选择平台通用性。
- **取舍 3：AgentSkills 最小集 vs 大而全 tool hub**——降低维护负担，但把 domain 特化能力推给社区 micro agent 或自写 Python。
- 取舍 4：Docker-per-session 安全 vs 启动开销——安全边界清晰，但冷启动、镜像 build、长任务资源占用成本高；论文报告 SWE-Bench Lite 上 claude-3.5-sonnet 平均 $1.10/instance。
- **边界条件**：在「需要 repo 级编辑 + 测试反馈」的 SWE 任务上架构合适；在「需 RL 训练 specialist 模型」的 MiniWoB++ 全量集（CC-NET 91.1%）上，zero-shot LLM agent 明显吃亏；在「24h 持续迭代」的 ML engineering（见 [[MLE-Bench-ICLR25]]）上，OpenHands scaffold 弱于 AIDE 的树搜索 persistence。

## 实验与结果

- **SWE-Bench Lite**（300 instances，无 hint）：CodeActAgent v1.8 + claude-3.5-sonnet **26.0%** resolve rate（$1.10/instance）；gpt-4o **22.0%**；gpt-4o-mini **7.0%**（$0.01）。对比 SWE-Agent 18.0%、AutoCodeRover 19.0%、Aider 26.3%、Moatless 26.7%、Agentless 27.3%
- **HumanEvalFix Python**（0-shot）：CodeActAgent v1.5 **79.3%**（$0.14/instance），约为 StarCoder2-15B（48.6%）两倍；低于 SWE-Agent **87.7%**（但后者 1-shot demo）
- **BIRD text-to-SQL**（300 dev）：gpt-4o **47.3%** execution accuracy（$0.11）
- **ML-Bench**（quarter subset）：gpt-4o **76.5%**（$0.25），低于 Aider 64.4% 的对比项中 SWE-Agent 42.6%——OpenHands 在 ML repo 任务上靠前
- **WebArena**（812 tasks）：BrowsingAgent + claude-3.5-sonnet **15.5%**；CodeActAgent v1.8 delegate browsing **15.3%**；WebArena Agent 基线 14.4%
- **MiniWoB++**（125 envs 全量）：BrowsingAgent + gpt-4o **40.8%**（远低于 CC-NET 91.1%  specialist）
- **GAIA L1 val**：GPTSwarm + gpt-4o **32.1%**（$0.05）
- **GPQA**：CodeActAgent v1.8 + claude-3.5-sonnet **52.0%**（$0.065），高于 gpt-4 few-shot CoT **38.8%**
- **AgentBench OS subset**：gpt-4o **57.6%**（$0.085）
- **MINT math**：gpt-4o **77.3%**（$0.07）
- **核心叙事验证**：同一 CodeActAgent 不改 prompt 在 SWE / Web / Misc 均有竞争力，而 column-specialist baseline 通常只强于一类

## Critical Analysis

### 论证链条

论文链条是：软件接口足够通用 → CodeAct 式 PL action + Docker runtime 实现该接口 → AgentSkills 补 ACI 短板 → event stream 统一 UI/agent/评测 → 15 benchmark 上单一 generalist 仍 competitive。链条在「平台工程」层面闭合度高：架构图、API、开源规模、benchmark 集成都有证据。

薄弱环节在「generalist 足够好」向「production digital worker」的外推：SWE 26% 只是略入 specialist 区间，距离可靠自主修 issue 仍远；WebArena 15% 说明真实 web 规划仍极难。论文诚实承认未夺魁，但 Table 1 框架对比表部分 OCR 损坏，削弱了对竞品缺口的定量说服力。

### 假设压力测试

- **Workload 变化**：repo 更大、单文件更长时，file editing 瓶颈可能压过 action space 设计——§A 已承认 long-file editing 是主要痛点。
- **模型变化**：结果强依赖 claude-3.5-sonnet / gpt-4o；换弱模型（gpt-4o-mini SWE 7%）后 generalist 叙事仍成立但实用价值骤降。
- **部署变化**：Docker 假设在 K8s 多租户、无 Docker 桌面环境、air-gapped 集群中需要额外工程；论文未讨论。
- **评测变化**：默认 SWE-Bench **Lite** 且**无 hint** 节省成本，但与 production issue 分布是否一致未验证；若干 benchmark 用子集（ML-Bench quarter、ToolQA easy、GAIA L1 only）。

### 实验可信度

- **正面**：baseline 选择覆盖 SWE/Web/Misc 多条线；报告 avg cost；强调 0-shot、无 benchmark-specific prompt hacking；15 个 benchmark 集成对平台论文合适。
- **疑点**：部分数字标注版本不一致（如 GPQA 53.1% 标注来自 v1.5 而主表用 v1.8）；与 specialist 对比时 HumanEvalFix 的 1-shot vs 0-shot 不对等；缺少 latency、step 数、失败模式分布等系统指标。
- **缺失**：无 tail latency、无 sandbox 启动时间、无多 agent delegation 相对单 agent 的 ablation、无 AgentSkills 逐项消融。

### 系统性缺陷

- **安全**：Docker 隔离 + human-in-the-loop UI 是主要防线；§B 讨论伦理但未量化 red-team（命令注入、数据外泄、恶意 browsing）。生产级 egress 控制、secret 管理论文未讨论。
- **可观测性**：event stream 利于 replay/debug，但是否支持 distributed trace、cost cap、step budget 论文未展开。
- **故障恢复**：容器崩溃、browser hang、LLM timeout 的恢复语义未系统描述。
- **运维成本**：每 instance 美元成本可测，但 15 benchmark 全跑仍昂贵；integration test 缓解开发回归，不能替代端到端 SLA 验证。
- **社区治理**：32K stars / 188 contributors 证明吸引力，但 also 带来 API 稳定性、agent 质量参差等维护风险——论文未深入。

## 局限与 Future Work

- **局限 1**：复杂长任务、长文件编辑、强 browsing 仍明显弱于 specialist 或训练型 agent（§A）。
- **局限 2**：workflow 仍大量 handcraft，缺自动 workflow generation（作者寄望 GPTSwarm / LangGraph 类图优化）。
- **局限 3**：多模态支持依赖零散 skills，缺 principled IPython/browser 多模态管线。
- **局限 4**：评测子集与成本裁剪（SWE-Lite、无 hint）可能高估或低估真实场景表现——需 production trace 验证。
- **Future work 1**：集成 Auto Eval & Refine + Reflexion 到 browsing agent，用可测的 retry-on-error 提升 WebArena。
- **Future work 2**：以 GPTSwarm 图结构做 RL/meta-prompting 自动优化 agent workflow，减少 handcraft。
- **Future work 3**：针对 long-file editing 做 ACI 或 diff 策略对照实验，量化对 SWE-Bench 的边际收益。
- **后续演进**：[[OpenHands-SDK-MLSys26]] 将 monolith 拆为四包 modular SDK，面向更可维护的生产集成。

## 相关

- **相关概念**：[[CodeAct]]、Agent-Computer Interface、Event Stream、Docker Sandbox、BrowserGym、Integration Testing
- **同类系统**：[[SWE-Agent]]、AutoCodeRover、Aider、Moatless、Agentless、[[AutoGen]]、MetaGPT、[[LangChain]]、GPTSwarm、AutoGPT
- **相关 benchmark**：SWE-Bench、[[MLE-Bench-ICLR25]]、WebArena、GAIA、GPQA、HumanEvalFix、AgentBench、MINT
- **后续工作**：[[OpenHands-SDK-MLSys26]]
- **同主题**：[[Auto-Research]]
