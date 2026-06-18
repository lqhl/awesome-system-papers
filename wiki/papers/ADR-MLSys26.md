---
type: paper
name: ADR
full_title: "ADR: An Agentic Detection System for Enterprise Agentic AI Security"
authors: [Chenning Li, Pan Hu, Justin Xu, Baris Ozbas, Olivia Liu, Caroline Van, et al.]
venue: MLSys
year: 2026
tags: [agentic-security, mcp, enterprise, detection, prompt-injection]
source_pdf: "[[c0c7c76d30bd3dcaefc96f40275bdc0a.pdf]]"
source_md: "[[c0c7c76d30bd3dcaefc96f40275bdc0a]]"
---

# ADR: An Agentic Detection System for Enterprise Agentic AI Security (MLSys 2026)

> **一句话总结**：Uber 生产 10+ 个月的 MCP 智能体安全框架 ADR：Sensor 全链路遥测 + 两层在线检测（triage + MCP 上下文推理）+ 离线 Explorer 红队，ADR-Bench 上 **0 FP**、F1 **0.800**（基线 2–4× 低），AgentDojo **100% recall**。

## 问题

MCP 智能体把 LLM 接到文件/API/代码执行，攻击面含 prompt injection、tool rug pull、凭证外泄。传统 EDR 只见 syscall/网络，不见 prompt→reasoning→tool 因果链；静态规则难泛化；全量 LLM 推理在 **10k+ sessions/天** 规模成本过高。企业环境类别极不平衡（恶意极少）。

## 核心方法

**ADR Sensor**（端点 hourly 0.18 s）：解析 Cursor/Cline/Claude Code 本地缓存，重建 prompt / reasoning / MCP tool call / 环境上下文。

**在线 Detector**：
- **Tier 1 Triage**：轻量 LLM 高 recall 筛查
- **Tier 2 Reasoning**：GPT-4o triage + Claude Sonnet 4 深度分析，动态查询 MCP——源码检查、威胁情报、企业 policy

**离线 ADR Explorer**：进化算法红队（fitness = ε×σ×τ^α），发现难例写入 threat repo 强化 Tier 2。

**ADR-Bench**：302 tasks、133 MCP servers、17 techniques、42 malicious / 260 benign（13.9% 攻击率）。

## 关键结果

- 生产（Uber）：**7200+** hosts、**10k+** sessions/天；发现数百凭证暴露（26 类）；shift-left 阻断 precision **97.2%**（206/212 credentials）
- ADR-Bench：Precision **1.000**、Recall **0.667**、F1 **0.800**；ALRPHFS/GuardAgent/LlamaFirewall F1 仅 0.178–0.366（FP 高达 30–40）
- AgentDojo：Recall **1.000**、Precision **0.927**、仅 3 FP / 93 tasks
- 成本：\$0.024/task（ADR-Bench），triage 处理 40.7% 任务仅 \$0.017

## 相关

- **相关概念**：MCP、prompt injection、agentic AI security
- **同类系统**：LlamaFirewall、GuardAgent、ALRPHFS、MCP Guardian
- **同会议**：[[MLSys-2026]]