---
type: paper
name: RocketPPA
full_title: "RocketPPA: A Unified LLM Model for Power, Performance, and Area Prediction from Hardware Code"
authors: [Armin Abdollahi, Mehdi Kamal, Massoud Pedram]
venue: MLSys
year: 2026
tags: [eda, verilog, ppa, llm, hardware-design]
source_pdf: "[[9778d5d219c5080b9a6a17bef029331c.pdf]]"
source_md: "[[9778d5d219c5080b9a6a17bef029331c]]"
---

# RocketPPA: A Unified LLM Model for Power, Performance, and Area Prediction from Hardware Code (MLSys 2026)

> **一句话总结**：condition-aware LLM + MoE regression + contrastive learning，从 Verilog 直接预测跨工艺节点/优化目标的 PPA；10% 容差 pass rate 比 MetRex 高 **9.4 pp**（delay），单设计推理 **0.12s**、吞吐约 **20×** 于 prior。

## 问题

RTL 的 power/performance/area 依赖 synthesis regime（工艺节点 + area/delay opt），传统 EDA 估计慢、需手工校准；现有 LLM/graph 方法多在固定 regime 下做 value regression，难以跨节点/目标服务决策时需求。

## 核心方法

- **Condition-aware backbone**：prepend `[NODE=15nm][OBJ=area-opt]` 等 token，LLM 编码 Verilog fragment 后 mean-pool
- **MoE regression head**：6 experts、top-3 gating，分别专攻不同电路 archetype
- **Contrastive learning**：cross-condition consistency、PPA-based similarity、structural complexity alignment 三种 positive pair 策略，训练时 λ=0.5 与 Huber loss 联合优化
- **LoRA** 参数高效微调；20k+ 模块 LLM repair pipeline 清洗训练集

## 关键结果

- VerilogEval @10%：area **71.6%**（+13.6 pp vs MetRex）、delay **57.2%**（+9.4 pp）、static power **56.7%**（+14.7 pp）
- 138 设计全集 16s（**0.12s/design**），比 CircuitFusion/MetRex **20×**、MasterRTL **30×** 快
- contrastive learning 贡献 1.8–2.5 pp；7nm ASAP7 泛化 pass@10% area 70.1%

## 相关

- **相关概念**：[[Quantization]]（正交：PPA 估计 vs 模型压缩）
- **同类系统**：MetRex、MasterRTL、CircuitFusion、ChipNeMo
- **同会议**：[[MLSys-2026]]