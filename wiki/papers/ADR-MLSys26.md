---
type: paper
name: ADR
full_title: "ADR: An Agentic Detection System for Enterprise Agentic AI Security"
authors: [Chenning Li, Pan Hu, Justin Xu, Baris Ozbas, Olivia Liu, Caroline Van, Manxue Li, Wei Zhou, Mohammad Alizadeh, Pengyu Zhang, KK Sriramadhesikan, Ming Zhang]
venue: MLSys
year: 2026
tags: [agent-security, mcp, enterprise, detection, observability, uber]
source_pdf: "[[c0c7c76d30bd3dcaefc96f40275bdc0a.pdf]]"
source_md: "[[c0c7c76d30bd3dcaefc96f40275bdc0a]]"
---

# ADR: An Agentic Detection System for Enterprise Agentic AI Security (MLSys 2026)

> **一句话总结**：面向 MCP 驱动企业 agent 的首个大规模生产验证检测框架：ADR Sensor 重建 prompt→reasoning→tool 因果链，两级在线检测（高召回 triage + MCP 上下文深度推理），离线 Explorer 红队进化硬样本；Uber **10+ 月**、**7200+** host、日均 **1 万+** session，ADR-Bench **0 FP / 67% 召回**，AgentDojo **100% 召回、3 FP/93**。

## 问题与动机

Model Context Protocol（MCP）使 agent 通过标准化工具访问文件、API、数据库，攻击面包括 prompt injection、恶意 MCP server、凭证渗出。传统 EDR 只见文件/网络结果，不见 **为何** 执行；静态 guardrail 难覆盖 17+ 攻击技法且企业流量极度不平衡（恶意极稀）。全量 LLM 语义检测在 **1 万+ session/日** 成本不可承受。

ADR 模仿 SOC 工作流：全面可观测 → 快速分诊 → 深度调查 → 部署前红队强化。

## 关键观察 / 隐含假设

- **观察 1：区分恶意与良性 agent 行为需要四维遥测——user prompt、agent reasoning、MCP tool 序列（含参数/结果）、环境上下文（server 配置、pip/npm 包）。**
  - **依赖假设**：主流 MCP host（Cursor、Cline、Claude Code）本地 SQLite/JSONL 可解析并关联为完整 session。
  - **可能失效场景**：纯 gateway 截流缺环境上下文；streaming 响应 gateway 难完整捕获；新 host 缓存格式变更需适配。

- **观察 2：生产部署必须 **precision-first**：baseline（LlamaFirewall/GuardAgent/ALRPHFS）在 ADR-Bench 上 **30–40 FP/260 benign**，F1 **0.18–0.37**，无法承受误报触发的 incident cost。**
  - **依赖假设**：Tier1 保守 escalate + Tier2 MCP 企业上下文可将 FP 压到零。
  - **可能失效场景**：67% 召回意味着 **33% 攻击漏检**；高对抗自适应攻击可能绕过固定 prompt。

- **观察 3：离线 Explorer 进化算法（fitness \(F=\varepsilon\times\sigma\times\tau^\alpha\)，α=1.2）在沙箱发现难例并写入 threat intel，部署前强化 Tier2。**
  - **证据强度**：**中**——生产 CTF/Agent Flayer 验证多阶段链，但公开 benchmark 召回仍非 100%。

- **假设 1：GPT-4o triage + Claude Sonnet 4 reasoning + 三 MCP 企业源（源码、威胁框架、策略）在成本与精度间可达生产可接受点（\$0.024/task，18.5s mean on ADR-Bench）。**
  - **可能失效场景**：模型 drift/更新需 regression；latency 对 inline blocking 仍偏高。

## 核心方法

**ADR Sensor**：端点轻量 agent，hourly 解析 host 本地 agent 缓存，关联 prompt→reasoning→tool→outcome；均摊 **0.182s/run**；优于 gateway 的完整上下文（Fig. 4）。

**在线两级检测**：
- **Tier 1**：轻量 LLM triage，高召回，可疑一律升级。
- **Tier 2**：reasoning agent 动态查询 MCP——`get_source_code`（工具真实行为）、`get_threat_framework`、`get_policies`；结合 Explorer 产出的 [EAS]/[CURATED] 情报。

**离线 ADR Explorer**：Red-Teaming / Eval / Threat Intelligence 三 agent 协作；变异种子攻击，沙箱测成功与 evasion；收敛后更新 Tier2 知识库。

**ADR-Bench**：302 tasks（42 malicious，13.9%）、133 MCP servers、729 tools、均 **28.5** tool calls/task，覆盖 5 tactics × 17 techniques；YAML 企业策略库。

## 设计取舍

- **Precision vs recall**：ADR-Bench **1.0 precision、0.667 recall**；AgentDojo 反过来 **1.0 recall、0.927 precision**——刻意按场景切换优先级，非单一最优 F1。
- **Sensor 事后取证 vs inline hook**：混合模型——sensor 深度 forensics，高危凭证泄漏 inline block（shift-left **97.2%** precision，206/212 credentials）。
- **成本**：比 GuardAgent 贵 2×、比 LlamaFirewall 便宜 **19×**；40.7% task 仅 triage（\$0.017，2.3s）。
- **Gateway 替代**：需 MCP schema 扩展 Context/Intent 字段才可达 sensor 级语义。

## 实验与结果

**ADR-Bench**：ADR **28/42 TP、0 FP**，F1 **0.800**；ALRPHFS F1 **0.366**（34 FP）；各 tactic 检出 **20–100%**（Permission Abuse 仅 20%）。

**AgentDojo**：38/38 攻击检出，3 FP/55 benign，F1 **0.962**。

**Uber 生产**：10+ 月、7200+ hosts、数百 credential exposure（26 类）；CTF/Agent Flayer 多阶段链可追溯。

**开源**：ADR-Bench、Sensor 与检测框架 GitHub 发布（企业标识符脱敏）。

## Critical Analysis

**强项**：罕见地把 **MCP-native 企业 telemetry + 两级 LLM 检测 + 进化红队** 打通并给出长期生产数字；ADR-Bench 在技法覆盖与 MCP 上下文上明显宽于 AgentDojo 等；零 FP 对 SOC 可运维性至关重要。

**弱点**：67% 召回对高价值渗透仍不够；强依赖闭源 LLM 与 Uber 内部 MCP 策略/源码库，外部复现需自建 context providers；Sensor 解析特定 IDE 缓存，通用性随生态碎片化下降；检测延迟秒级，难做实时逐 token 阻断。

**与 baseline 对比公平性**：baseline 开源适配到 MCP 设置，但 GuardAgent/ALRPHFS 非为 MCP 原生设计，部分差距可能来自工程而非方法论。

## 局限与 Future Work

- 提升 recall 同时维持低 FP 的自适应/ensemble 策略。
- 实时 gateway + sensor 混合架构与 MCP 标准扩展。
- 非 Cursor 系 host、多模态 agent、跨 org federated threat intel。
- 对抗性 prompt 针对 triage/reasoning 的鲁棒性基准扩展。

## 相关

- **协议 / 生态**：MCP、Cursor、Claude Code
- **安全基准**：AgentDojo、MCP-Artifact、RAS-Eval
- **Baseline**：LlamaFirewall、GuardAgent、ALRPHFS
- **主题**：agentic AI security、prompt injection、credential exfiltration