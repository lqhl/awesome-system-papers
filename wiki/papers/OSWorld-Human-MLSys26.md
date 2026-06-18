---
type: paper
name: OSWorld-Human
full_title: "OSWorld-Human: Benchmarking the Efficiency of Computer-Use Agents"
authors: [Reyna Abhyankar, Qi Qi, Yiying Zhang]
venue: MLSys
year: 2026
tags: [computer-use-agent, benchmark, latency, osworld, efficiency]
source_pdf: "[[6364d3f0f495b6ab9dcf8d3b5c6e0b01.pdf]]"
source_md: "[[6364d3f0f495b6ab9dcf8d3b5c6e0b01]]"
---

# OSWorld-Human: Benchmarking the Efficiency of Computer-Use Agents (MLSys 2026)

> **一句话总结**：首次系统分析 OSWorld computer-use agent 的延迟瓶颈（planning+reflection 占 75–94%），构建 369 任务人工最短轨迹基准 OSWorld-Human，发现 SOTA agent 比必要步骤多 1.4–2.7×，最高 OSWorld 42.5% 成功率在严格效率指标上仅 17.4%。

## 问题

Computer-use agent 在 OSWorld 等 benchmark 上准确率提升显著，但端到端延迟可达数十分钟（人类仅需数分钟），限制实际部署。现有研究几乎只关注 task success rate，未系统研究 **时间效率** 与轨迹冗余。

## 核心方法

**延迟剖析**（Agent S2 + GPT-4.1，37 任务子集）：
- Planning + reflection（大模型调用）占 **75–94%** 总延迟
- 越靠后的 step，prompt 越长（累积历史），LLM 延迟可达早期 step 的 **3×**
- A11y tree 显著增加 token 与延迟；Set-of-Marks 可减少步数

**OSWorld-Human**：为 OSWorld 全部 369 任务标注人工 gold trajectory，提供 single-action 与 grouped-action（可连续执行的动作组）两种粒度。

**Weighted Efficiency Score (WES)**：成功任务按 $t_{exp}/t_{actual}$ 加权，失败任务按 $t_{actual}/S$ 惩罚，同时衡量准确率与效率。

## 关键结果

- Agent S2 完成 OS 任务示例：**50 步、40+ 分钟**；改行距等简单任务 agent 需 **12 分钟** vs 人类 **<30 秒**
- 16 个 CUA 评估：最佳 agent 轨迹比人类必要步骤长 **1.4–2.7×**
- Agent S2 w/ Gemini 2.5：OSWorld **41.4%** → grouped-action WES+ 仅 **17.4%**（2.4× 降幅）
- Planning/reflection 的 prefill 阶段主导 LLM 延迟；grounding 小模型 + [[SGLang]] Serving 相对廉价

## 相关

- **相关概念**：computer-use agent、GUI agent、latency
- **同类系统**：Agent S2、UI-TARS、OpenAI Operator、OSWorld
- **同会议**：[[MLSys-2026]]、[[SGLang]]