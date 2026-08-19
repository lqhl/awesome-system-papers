---
type: paper
name: ADR
full_title: "ADR: An Agentic Detection System for Enterprise Agentic AI Security"
authors: [Chenning Li, Pan Hu, Justin Xu, Baris Ozbas, Olivia Liu, et al.]
venue: MLSys
year: 2026
tags: [agent-security, mcp, enterprise, detection, observability, uber, area/agent-systems]
source_pdf: "[[c0c7c76d30bd3dcaefc96f40275bdc0a.pdf]]"
source_md: "[[c0c7c76d30bd3dcaefc96f40275bdc0a]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# ADR：用于企业智能体 AI安全的代理检测系统（MLSys 2026）

> **原题**：ADR: An Agentic Detection System for Enterprise Agentic AI Security

> **一句话总结**：作者称 ADR 是面向 MCP 企业 agent 的首个大规模生产验证检测框架；在 ADR-Bench 的 302 tasks 上，它得到 28/42 TP、0 FP、recall 0.667，而在 AgentDojo 的 93 tasks 上检出 38/38 attacks、对 55 个 benign tasks 产生 3 FP（§5.1–5.2，Table 2）。这些 benchmark 口径不代表生产 alert queue 的 FP rate。

## 问题与动机

Model Context Protocol（[[MCP]]）使 [[agent]] 通过标准化工具访问文件、API、数据库，攻击面包括 [[Prompt-Injection]]、恶意 MCP server、凭证渗出。传统 [[EDR]] 只见文件/网络结果，不见 **为何** 执行；静态 guardrail 难覆盖 17+ 攻击技法且企业流量极度不平衡（恶意极稀）。全量 [[LLM]] 语义检测在 **1 万+ session/日** 成本不可承受。

ADR 模仿 SOC 工作流：全面可观测 → 快速分诊 → 深度调查 → 部署前红队强化。

## 关键观察 / 隐含假设

- **观察 1：区分恶意与良性 agent 行为需要四维遥测——user prompt、agent reasoning、MCP tool 序列（含参数/结果）、环境上下文（server 配置、pip/npm 包）。**
  - **依赖假设**：主流 MCP host（Cursor、Cline、Claude Code）本地 SQLite/JSONL 可解析并关联为完整 session。
  - **可能失效场景**：纯 gateway 截流缺环境上下文；streaming 响应 gateway 难完整捕获；新 host 缓存格式变更需适配。

- **观察 2：生产部署采用 precision-first 取舍；在 ADR-Bench 的 260 benign tasks 上，LlamaFirewall、GuardAgent、ALRPHFS 分别产生 40、30、34 个 FP，而 ADR 为 0 FP（§5.1–5.2，Table 2）。**
  - **依赖假设**：Tier1 保守 escalate + Tier2 MCP 企业上下文可将 FP 压到零。
  - **可能失效场景**：67% 召回意味着 **33% 攻击漏检**；高对抗自适应攻击可能绕过固定 prompt。

- **观察 3：离线 Explorer 进化算法（fitness \(F=\varepsilon\times\sigma\times\tau^\alpha\)，α=1.2）在沙箱发现难例并写入 threat intel，部署前强化 Tier2。**
  - **证据强度**：**中**——生产 CTF/Agent Flayer 验证多阶段链，但公开 benchmark 召回仍非 100%。

- **假设 1：GPT-4o triage + Claude Sonnet 4 reasoning + 三 MCP 企业源（源码、威胁框架、策略）在成本与精度间可达生产可接受点（\$0.024/task，18.5s mean on ADR-Bench）。**
  - **可能失效场景**：模型 drift/更新需 regression；latency 对 inline blocking 仍偏高。

## 核心方法

**ADR Sensor**：端点轻量 agent，hourly 解析 host 本地 agent 缓存，关联 prompt→reasoning→tool→outcome；均摊 0.182s/run。作者认为 gateway 会遗漏 environment/reasoning context，但未提供直接比较实验（Fig. 4）。

**在线两级检测**：
- **Tier 1**：轻量 LLM triage，高召回，可疑一律升级。
- **Tier 2**：reasoning agent 动态查询 MCP——`get_source_code`（工具真实行为）、`get_threat_framework`、`get_policies`；结合 Explorer 产出的 [EAS]/[CURATED] 情报。

**离线 ADR Explorer**：[[Red-Teaming]] / Eval / Threat Intelligence 三 agent 协作；变异种子攻击，沙箱测成功与 evasion；收敛后更新 Tier2 知识库。

**ADR-Bench**：302 tasks（42 malicious，13.9%）、133 MCP servers、729 tools、均 **28.5** tool calls/task，覆盖 5 tactics × 17 techniques；YAML 企业策略库。

## 设计取舍

- **Precision vs recall**：ADR-Bench **1.0 precision、0.667 recall**；AgentDojo 反过来 **1.0 recall、0.927 precision**——刻意按场景切换优先级，非单一最优 F1。
- **Sensor 事后取证 vs inline hook**：混合模型——sensor 深度 forensics，高危凭证泄漏 inline block（shift-left **97.2%** precision，206/212 credentials）。
- **成本**：比 GuardAgent 贵 2×、比 LlamaFirewall 便宜 **19×**；40.7% task 仅 triage（\$0.017，2.3s）。
- **Gateway 替代**：需 MCP schema 扩展 Context/Intent 字段才可达 sensor 级语义。

## 实验与结果

- **ADR-Bench**：ADR 为 28/42 TP、0 FP、precision 1.000、recall 0.667、F1 0.800；ALRPHFS / GuardAgent / LlamaFirewall 的 F1 为 0.366 / 0.222 / 0.178，并产生 34 / 30 / 40 FP（§5.1–5.2，Table 2，Fig. 6；302 tasks、17 techniques、5 tactics，baseline 由作者适配到 MCP，硬件未披露）。
- **AgentDojo**：检出 38/38 attacks，对 55 benign tasks 产生 3 FP，precision 0.927、recall 1.000、F1 0.962（§5.1–5.2，Table 2；93 tasks，非 MCP-native）。
- **Cost/latency**：ADR-Bench 平均为 $0.024/task、18.5 秒；GuardAgent 为 $0.012/9.4 秒，LlamaFirewall 为 $0.459/93.8 秒，Tier 1 单独处理 40.7% tasks（§5.2，Fig. 6b–c；价格依模型版本）。
- **Ablation**：移除 triage 后 recall 0.667→0.805、F1 0.800→0.868，但出现 2 FP，成本 $0.024→$0.031、latency 18.5→28.1 秒；移除 source-code MCP 后 recall 降至 0.571（§5.3，Fig. 7；仅 ADR-Bench）。
- **Production**：作者报告部署超过 10 个月、覆盖 7,200+ hosts 和每日 10,000+ sessions；送人工复核的 alerts 中 34% 为 TP、17% 为 true-positive non-malicious、49% 为 FP。credential hook 在 212 个 unique credentials 上为 206 TP、6 FP，即 precision 97.2%，但未报告 recall（§6–6.2，Fig. 8）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| ADR 在 ADR-Bench 上达到 0 FP 与 0.667 recall | §5.1–5.2, Table 2, Fig. 6 | 302 tasks；42 malicious/260 benign；17 techniques；adapted baselines | medium |
| ADR 在 AgentDojo 上检出全部 38 个 attacks | §5.1–5.2, Table 2 | 93 tasks；55 benign；非 MCP-native；硬件未披露 | medium |
| Two-tier routing 的平均成本/延迟为 $0.024 与 18.5 秒 | §5.2, Fig. 6b–c | ADR-Bench；GPT-4o + Claude Sonnet 4；价格随版本变化 | medium |
| Triage/source-code context 对 recall、FP、cost 有可测取舍 | §5.3, Fig. 7 | ADR-Bench；固定 prompts；非生产 traffic | medium |
| 生产规模已达 7,200+ hosts，但人工复核 queue 的 FP 为 49% | §6–6.1, Fig. 8 | Uber internal telemetry；超过 10 个月；无外部 baseline | medium |

## 批判性分析

### 论证链条

观察（MCP 企业 [[agent]] 需 prompt→reasoning→tool 因果链才能区分恶意；全量 [[LLM]] 语义检测在 **1 万+ session/日** 不可承受；precision-first 才能承受 incident cost）→ 设计（Sensor 四维遥测 + Tier1 高召回 triage + Tier2 MCP 上下文推理 + Explorer 进化红队）→ 结果（Uber **10+ 月** 生产、ADR-Bench **0 FP / 67% 召回**、AgentDojo **100% 召回**）链条**闭合良好**。SOC 式分诊叙事与两级成本结构（40.7% task 仅 triage）相互支撑，说明「高召回入口 + 深度调查」是为稀疏恶意流量定制的可运维路径。

主要跳步是把 ADR-Bench 的 precision-first（1.0 precision、0.667 recall）与 AgentDojo 的 recall-first（1.0 recall、0.927 precision）并列为「按场景切换优先级」——这合理，但论文未给出生产环境中两类指标如何按 tactic 动态切换的 operational playbook。ADR-Bench 仍有 14/42 attacks 未检出；更重要的是，§6.1 的生产 escalation queue 中 49% alerts 被 analyst 标为 FP，因此 benchmark 的 0 FP 不能外推为生产精度。

### 假设压力测试

- **Telemetry 完整性**：Sensor 依赖 Cursor/Cline/Claude Code 等 host 本地 SQLite/JSONL 可解析；纯 gateway 截流缺环境上下文、streaming 响应难完整捕获、新 host 缓存格式变更需持续适配——通用性随 MCP 生态碎片化下降。
- **企业上下文可得性**：Tier2 动态查询源码、威胁框架、策略库强依赖 Uber 内部 MCP context providers；外部复现需自建等价情报源，闭源 [[LLM]]（GPT-4o triage + Claude Sonnet 4 reasoning）与策略 drift 带来 regression 风险。
- **对抗自适应**：固定 triage/reasoning prompt 与进化红队（fitness \(F=\varepsilon\times\sigma\times\tau^\alpha\)）可发现难例，但高对抗攻击者针对 Tier1/Tier2 的 prompt 绕过论文未系统评测；67% 召回暗示仍有技法组合可 evade。
- **延迟与阻断形态**：检测均值 **18.5s**（ADR-Bench）、秒级延迟适合事后取证与 shift-left 凭证 block（**97.2%** precision），难做实时逐 token 阻断——与 inline hook 场景的 threat model 边界需读者自行判断。
- **Baseline 可比性**：LlamaFirewall/GuardAgent/ALRPHFS 开源适配到 MCP 设置，但非 MCP 原生设计；ADR-Bench 上 **30–40 FP/260 benign** vs ADR **0 FP** 的部分差距可能来自工程集成与 MCP 上下文访问权，而非纯方法论优势。

### 实验可信度

- **强项**：罕见提供 **MCP-native 企业 telemetry + 两级 LLM 检测 + 进化红队** 的长期生产数字（**7200+** host、数百 credential exposure）；ADR-Bench 覆盖 5 tactics × 17 techniques、133 MCP servers、729 tools，技法与 MCP 上下文宽度明显优于 AgentDojo 等；Uber CTF/Agent Flayer 多阶段链可追溯，增强「真实攻击形态」说服力。
- **Baseline 选取**：在 ADR-Bench 与 AgentDojo 双基准上报告 precision/recall 分场景切换，对比意图清晰；但 GuardAgent/ALRPHFS 的 MCP 适配公平性存疑（见上）。
- **Metric 缺口**：主报 F1/precision/recall，未量化漏检攻击的 business impact、SOC analyst 工时、或 Tier2 MCP 查询失败率；Permission Abuse 仅 **20%** 检出率提示 tactic 级不均衡，但未展开根因。检测延迟分布、模型版本 drift 下的 regression 测试、跨 org federated threat intel 均未覆盖。

## 局限与后续工作

- 提升 recall 同时维持低 FP 的自适应/ensemble 策略。
- 实时 gateway + sensor 混合架构与 MCP 标准扩展。
- 非 Cursor 系 host、多模态 agent、跨 org federated threat intel。
- 对抗性 prompt 针对 triage/reasoning 的鲁棒性基准扩展。

## 相关

- **协议 / 生态**：MCP、Cursor、Claude Code
- **安全基准**：AgentDojo、MCP-Artifact、RAS-Eval
- **Baseline**：LlamaFirewall、GuardAgent、ALRPHFS
- **主题**：agentic AI security、prompt injection、credential exfiltration
