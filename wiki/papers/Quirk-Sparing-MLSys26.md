---
type: paper
name: Quirk-Sparing
full_title: "Sparing Strategies to Minimize Reliability Impact on Large Training Jobs"
authors: [Kevin J. Quirk, Matthew Lennie, Ehsan K. Ardestani, Satyajeet Singh Ahuja, Matthew R. Bergeron, et al.]
venue: MLSys
year: 2026
tags: [fault-tolerance, llm-training, cluster-design, goodput, sparing]
source_pdf: "[[a684eceee76fc522773286a895bc8436.pdf]]"
source_md: "[[a684eceee76fc522773286a895bc8436]]"
---

# Sparing Strategies to Minimize Reliability Impact on Large Training Jobs (MLSys 2026)

> **一句话总结**：Meta 用 Markov 链 + 闭式公式建模 GPU 训练集群 sparing（spare tray / spare block / block size K），指导生产环境选 spare 粒度与数量以最大化 goodput；72-GPU block + 8 intra-block spare 比次优策略高 1.024× goodput。

## 问题

LLM 预训练 job 同步、长跑，单点故障可打断整 job；Llama 3 预训练 **>70%** 中断来自硬件故障。Sparing（预分配 idle GPU 替换故障单元）与 checkpoint 恢复如何配置（compute block 大小 K、spare block 数 R、spare tray 数 I）直接影响 **CETT**（cluster effective training time）和 goodput，但缺少跨环境可复用的评估框架。

## 核心方法

**Goodput 模型**：`Goodput = GPUs × CETT × TPS_Scale(Hardware) × TPS_Scale(LLM)`。

**CETT 分解**：spare idle 时间、spare 耗尽后 blocking、checkpoint 保存/浪费/检测/重启开销。

**分析方法**：
- **Spare tray**：连续时间 Markov 链求 compute block MTBF（式 3）
- **Spare block**：Markov 稳态求 spare 耗尽概率 P_block（式 4）
- **Checkpoint recovery**：离散 Markov 链建模同步 checkpoint 周期内完成概率（式 5）
- **Job placement**：placement 约束 `L−R = k·P` 可能产生 stranded blocks

配套 simulation 交叉验证；用于早期架构 order-of-magnitude 决策与生产调参。

## 关键结果

生产参数示例（4 sparing zones × 256 racks × 72 GPU/rack）：
- 最优：**K=72 GPU block + 8 intra-block spare tray**，goodput 比次优（72 GPU 无 intra spare）高 **1.024×**
- Block 减半：inter-block spare 比例约减半（8.6% → 4.7%），但 placement stranding 可抵消收益
- Intra-block spare 带来机架级省电，working GPU 功率上限可提 **9%**（TPS scale **1.034×**）
- 对 MTBF/MTTR 敏感：repair 时间缩短可显著改变最优 R/I 组合

## 相关

- **相关概念**：[[Tensor-Parallelism]]、checkpoint、fault tolerance、goodput
- **同类工作**：Varuna、Bamboo、Oobleck、in-memory checkpoint
- **同会议**：[[MLSys-2026]]