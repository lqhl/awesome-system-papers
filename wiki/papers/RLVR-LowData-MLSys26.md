---
type: paper
name: RLVR-LowData
full_title: "Learning from Less: Measuring the Effectiveness of RLVR in Low Data and Compute Regimes"
authors: [Justin Bauer, Thomas Walshe, Derek Pham, Harit Vishwakarma, Armin Parchami, Frederic Sala, Paroma Varma]
venue: MLSys
year: 2026
tags: [rlvr, data-scaling, procedural-data, fine-tuning, slm]
source_pdf: "[[7f1de29e6da19d22b51c68001e7e0e54.pdf]]"
source_md: "[[7f1de29e6da19d22b51c68001e7e0e54]]"
---

# Learning from Less: Measuring the Effectiveness of RLVR in Low Data and Compute Regimes (MLSys 2026)

> **一句话总结**：三套 procedural benchmark（counting/graph/spatial）+ Qwen3-4B GRPO 显示：低数据下 mixed-difficulty 训练比纯 easy 样本效率高最高 5×，easy-only 可泛化到更难测试题。

## 问题

RLVR 扩展律多假设充足数据与算力；资源受限时 dataset size/composition 如何影响 SLM 推理能力尚不清楚。

## 核心方法

**Procedural datasets**：Counting（1–7 步 filter+op）、Graph（5–25 节点算法题）、Spatial（2D 动作链）；均可控 size/diversity/complexity。

**Curation**：10 模型打分校准 Easy/Medium/Hard；训练 100/200/500 easy 或 mixed（各难度 ~33%）。

**Training**：Qwen3-4B + [[LoRA|LoRA]] r=64 + GRPO；verifiable outcome reward（counting/graph/spatial 各异）。

## 关键结果

- Counting：mixed-100 达 50% solve，easy-500 才 40%；**5×** sample efficiency vs easy-only
- Mixed-100 训练稳定，easy-100 在 step 150 后 collapse（gradient norm 850× spike）
- Graph：mixed 常负 reward（超长 rollout 超 token budget）；easy-500 test 最强
- Spatial：1000 step 二元 reward 稳步提升

## 相关

- **相关概念**：[[LoRA]]
- **同类系统**：DeepMath-103K ScaleRL、LIMR 数据选择
- **同会议**：[[MLSys-2026]]