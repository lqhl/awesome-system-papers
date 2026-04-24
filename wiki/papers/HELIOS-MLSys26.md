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

> **一句话总结**：通过多模型协同（一个模型 exit 不了的 token 换另一个模型常能早退）+ greedy 只加载"最可能用到的层"，把 EE-LLM 的吞吐提升 1.48×、batch size 提升 15.14×，精度几乎无损。

## 问题

Early-Exit LLM（EE-LLM）让简单 token 在中间层就退出，理论上能省算力和延迟，但现有单模型 EE-LLM 框架有两大瓶颈：

1. **延迟**：exit 不了的 token 必须穿过全部层，这些"长尾 token"把平均延迟拉高
2. **显存/batch**：exit 是运行时才知道的，框架保守地加载所有层权重，并 cache 所有层的 KV（应对最坏情况），显存和 vanilla autoregressive 一样重；且批内 token 退出深度不一致带来同步开销，现有实现干脆用 batch=1

Llama3.1-405B 的权重在 8×B100 上占 52% HBM，EE-LLM 没带来显存节省。

## 核心方法

HELIOS 建在两个实验观察上：

**Insight-1（模型互补）**：不同 EE-LLM 的 early exit 分布互补。OPT-1.3B 的 24 层里 74% token 在前 6 层退出；剩下 26% 在 OPT-6.7B 上 57% 能在前 9 层退出。联合使用两模型，92% token 都能早退。

**Insight-2（低信心 ≠ 错）**：即便置信度没达标不退出，预测 token 在穿完剩余层后仍保持不变的比例很高——OPT-6.7B 上 Layer-9 的 token 有 85% 在 Layer-32 输出相同结果；CodeLlama-34B 上 Layer-16 有 90% 不变。所以可以**贪心让低信心 token 也早退**，只加载最可能用到的层，省下的显存扩 batch。

**设计**：
- Step 1：从 Model Repository 按 SLO/硬件选 TopK 候选模型
- Step 2：在线评估候选模型的真实 exit 分布 + perplexity（无需 ground truth），存入 Performance History Table
- Step 3：用最优候选 + greedy 加载到选中 exit layer；遇到置信度不达标的 token 时，用 Confidence Breach Counter 累计，超过阈值（默认 100 个 token 内超过 50 个 breach）才在「加载当前模型更多层」和「切到另一候选模型」之间按开销二选一
- Step 4：每 RI=150 请求重新做一次 profiling，适应请求流变化

贪心固定 exit 层同时消除了 batch 内同步开销（每个 token 固定跑相同层数）。

## 关键结果

- 吞吐 **1.48×** vs 现有 EE-LLM 框架
- batch size **15.14×**
- 精度损失可忽略（依赖 Insight-2 + 多模型 fallback）
- OPT-1.3B+6.7B：92% token 早退 vs 单模型 74%/77%
- 评估数据集：ShareGPT、CNN-Dailymail、GSM8K、CodeXGLUE、HellaSwag
- 模型：OPT-1.3B/6.7B、Llama2-7B/13B、Llama3-8B、CodeLlama-34B、Llama2-70B
- 硬件：4× A100-40GB + NVLink

## 相关

- **相关概念**：Early-Exit、[[Speculative-Decoding]]（相关但不同——一个跳层一个推测）、[[KV-Cache]]、[[Continuous-Batching]]
- **同类系统**：EE-LLM 框架（Chen et al. 2024）、LayerSkip
- **同会议**：[[MLSys-2026]]
