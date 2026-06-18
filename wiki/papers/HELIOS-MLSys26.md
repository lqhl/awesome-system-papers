---
type: paper
name: HELIOS
full_title: "HELIOS: Adaptive Model and Early-Exit Selection for Efficient LLM Inference Serving"
authors: [Avinash Kumar, Shashank Nag, Jason Clemons, Lizy John, Poulami Das]
venue: MLSys
year: 2026
tags: [llm-inference, early-exit, model-switching, serving, throughput]
source_pdf: "[[1f0e3dad99908345f7439f8ffabdffc4.pdf]]"
source_md: "[[1f0e3dad99908345f7439f8ffabdffc4]]"
---

# HELIOS: Adaptive Model and Early-Exit Selection for Efficient LLM Inference Serving (MLSys 2026)

> **一句话总结**：多 EE-LLM 互补 early-exit + greedy 只加载高概率层 + 在线 profiling 动态切模型，相对单模型 EE-LLM 框架吞吐 **1.48×**、batch size **15.14×**，精度几乎无损。

## 问题

Early-Exit LLM（EE-LLM）让置信度够高的 token 在中间层退出以省算力，但现有框架只用 **单个模型**，有两处硬伤：exit 不了的 token 仍要穿完全部层，平均延迟被长尾拖住；exit 深度运行时才知道，框架保守加载 **全部层权重** 并为所有层建 [[KV-Cache]]，显存与 vanilla decoding 一样——Llama3.1-405B 权重在 8×B100 占 52% HBM。批内退出深度不一致还迫使 EE-LLM 常用 batch=1。

## 核心方法

**HELIOS** 两条洞察：

**Insight-1（模型互补）**：一个模型退不出的 token，换另一个模型常能更早退出。OPT-1.3B+6.7B 联合可把早退比例从 74%/77% 提到 **92%**。

**Insight-2（低置信 ≠ 错）**：未达阈值的 early-exit token，穿完剩余层仍不变的比例很高（OPT-6.7B Layer-9 上 **85%** 与 Layer-32 相同）。因此可 **greedy 早退** 并只加载「最可能用到的层」，省显存扩 batch；固定层数也消除 batch 内同步。

四步流程：Model Repository 选 TopK 候选 → 在线评估 exit 分布与 perplexity（Performance History Table）→ 最优模型 + greedy partial load；Confidence Breach Counter 超阈值才在「补层」与「换模型」间选开销更小者 → 每 RI=150 请求重 profiling。

## 关键结果

- 吞吐 **1.48×**、batch size **15.14×** vs 现有 EE-LLM 框架（Chen et al. 2024），精度损失可忽略。
- CodeLlama-34B + Llama2-70B：相对 vanilla 吞吐 +45%（EE-LLM 仅 +16%）。
- 硬件：4×A100-40GB；模型覆盖 OPT/Llama/CodeLlama 系列。

## 相关

- **相关概念**：[[KV-Cache]]、[[Continuous-Batching]]、[[Speculative-Decoding]]
- **同类系统**：EE-LLM 框架、LayerSkip
- **同会议**：[[MLSys-2026]]