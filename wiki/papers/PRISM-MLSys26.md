---
type: paper
name: PRISM
full_title: "PRISM: Parametrically Refactoring Inference for Speculative Sampling Draft Models"
authors: [Xuliang Wang, Yuetao Chen, Maochan Zhen, Fang Liu, Xinzhou Zheng, et al.]
venue: MLSys
year: 2026
tags: [speculative-decoding, draft-model, sglang, llm-inference]
source_pdf: "[[65ded5353c5ee48d0b7d48c591b8f430.pdf]]"
source_md: "[[65ded5353c5ee48d0b7d48c591b8f430]]"
---

# PRISM: Parametrically Refactoring Inference for Speculative Sampling Draft Models (MLSys 2026)

> **一句话总结**：PRISM 将不同 draft step 映射到不同 transformer 参数集（总参数量扩展但每步激活参数恒定），在 [[SGLang]] 上比已高度优化的推理引擎再提 **2.6×+** 解码吞吐，acceptance length 与 scaling 优于 EAGLE-3 等堆层方案。

## 问题

[[Speculative-Decoding]] 依赖 draft 质量，趋势是加大 drafter（EAGLE-3、Scylla 等堆更多 transformer layer），但 **容量与每步计算成本纠缠**——更大 drafter 带来更高 draft latency，抵消 acceptance 收益。

## 核心方法

**PRISM**（Parametrically Refactor Inference for Speculative Sampling draft Models）：
- 多个 **processing module**（fusion layer + transformer），draft step 到 module 为 **surjection**（多 step 可共享 module，但每 step 唯一指定）
- 每步只激活一个 module → **总容量↑、per-step 成本恒定**
- 后段 step 更难预测 → 渐进加深有效计算深度（cascaded structure）
- 兼容 tree-based draft；训练用 HASS 式 context alignment，但 backprop 仅限子网络，训练更高效
- 在 [[SGLang]] 中完整实现与评测（非仅 PyTorch toy）

## 关键结果

- 相对高度优化 inference engine：**>2.6×** decoding throughput
- acceptance length 超越现有 draft 架构；扩展数据量时 scaling 优于 naive 堆层
- 首次实证：draft 预测能力可在 **不增加 activated parameter** 下有效 scale
- 集成 SGLang 提供 system-level 证据（对比多数仅在 PyTorch 评测的 drafter）

## 相关

- **相关概念**：[[Speculative-Decoding]]、[[KV-Cache]]、EAGLE、draft-and-verify
- **同类系统**：[[SGLang]]、EAGLE-3、Scylla、HASS、[[vLLM]]
- **同会议**：[[MLSys-2026]]