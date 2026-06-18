---
type: paper
name: VeriMoA
full_title: "VERIMOA: A Mixture-of-Agents Framework for Spec-to-HDL Generation"
authors: [Heng Ping, Arijit Bhattacharjee, Peiyu Zhang, Shixuan Li, Wei Yang, Anzhe Cheng, Xiaole Zhang, Jesse Thomason, Ali Jannesari, Nesreen Ahmed, Paul Bogdan]
venue: MLSys
year: 2026
tags: [llm-agent, hdl, verilog, mixture-of-agents, code-generation]
source_pdf: "[[35f4a8d465e6e1edc05f3d8ab658c551.pdf]]"
source_md: "[[35f4a8d465e6e1edc05f3d8ab658c551]]"
---

# VERIMOA: A Mixture-of-Agents Framework for Spec-to-HDL Generation (MLSys 2026)

> **一句话总结**：VERIMOA 用 quality-guided caching + C++/Python 多路径 MoA，在 VerilogEval 2.0 / RTLLM 2.0 上 Pass@1 提升 15–30%，无需 fine-tuning 即可让小模型逼近大模型与专用微调方案。

## 问题

LLM 生成 HDL（Verilog）受限于语料稀疏与并发/时序约束，prompt 工程与 fine-tuning 成本高且难协作。现有多 agent 框架要么线性 pipeline 传播噪声，要么 unstructured debate 探索混乱，缺乏过滤错误与系统探索解空间的能力。

## 核心方法

**Quality-guided caching**：全局 cache 存所有层中间 HDL 与仿真质量分，深层 agent 从全历史 top-n 选取参考，打破 MoA 层间级联依赖，保证知识单调累积。

**Multi-path generation**：每层并行 Base（直出 HDL）、C++、Python 三路径，spec→高级语言→HDL 两阶段，利用 LLM 在 C++/Python 上的强先验扩展解空间。

**Quality evaluator**：仿真 + HDL 领域规则（reset、综合、风格）分层打分，可选 simulator self-refinement。

## 关键结果

- VerilogEval 2.0 / RTLLM 2.0 上 **Pass@1 提升 15–30%**（多 backbone）
- 小模型可匹配更大模型与 fine-tuned 基线
- 理论分析证明 global cache 下最小质量单调不降

## 相关

- **相关概念**：[[MoE]]
- **同类系统**：MAGE、CoopetitiveV、RTLCoder
- **同会议**：[[MLSys-2026]]