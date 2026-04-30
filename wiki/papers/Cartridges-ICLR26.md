---
type: paper
name: Cartridges
full_title: "Cartridges: Lightweight and general-purpose long context representations via self-study"
authors: [Sabri Eyuboglu, Ryan Ehrlich, Simran Arora, Neel Guha, Dylan Zinsley, Emily Liu, Will Tennien, Atri Rudra, James Zou, Azalia Mirhoseini, Christopher Ré]
venue: ICLR
year: 2026
tags: [kv-cache, long-context, test-time-training, prefix-tuning, self-study, memory-compression]
source_pdf: "[[iclr26-eyuboglu-cartridges.pdf]]"
source_md: "[[iclr26-eyuboglu-cartridges]]"
---

# Cartridges: Lightweight and general-purpose long context representations via self-study (ICLR 2026)

> **一句话总结**：不通过 prefill 构建 [[KV-Cache]]，而是用梯度下降把长文档离线「训练」成紧凑的 KV 表示（Cartridge），推理时直接加载；配合 self-study 合成对话 + context distillation 保证通用性，匹配 ICL 质量的同时用 38.6× 更少内存、26.4× 更高吞吐，还能 4× 外推 context length，多个 Cartridge 可拼接使用。

## 问题

长 context LLM serving 的瓶颈在于 [[KV-Cache]] 随输入长度线性膨胀——Llama 70B 处理 128K context 需要 84 GB 显存，单 H100 上 Llama 8B 从 1K 扩到 120K context 时峰值吞吐骤降 77×。已有的 KV cache 压缩方法（prompt compression / KV compression）在 >2× 压缩比下质量急剧退化。核心观察是：**同一份长文档经常被多次查询引用**（代码库、法律文件、病历），prefill 的成本可以离线摊销。

## 核心方法

**Cartridge 范式**：给定语料 C，冻结 LLM，反向传播损失到 key/value 向量上训练一个更小的 KV cache（本质等价于 [[Prefix-Tuning]]）。推理时直接加载训练好的 Cartridge，取代 prefill。一个 Cartridge = 一份文档的紧凑表示，训练一次、多次复用。

**Self-Study 训练配方**（解决 naive next-token prediction 只会死记硬背的问题）：

1. **合成对话生成**：用 LLM 自己出题考自己对文档的理解，生成多样化的对话 trace。文档过长时 chunk + 带 seed prompt（偏向全局推理以保证结构感知）
2. **Context Distillation**：用 context-distillation 目标（而非 next-token prediction）训练 Cartridge——让 Cartridge 增强的模型在 next-token 分布上尽可能接近「文档在 context 中」的原始 ICL 分布

**参数化选择**：Cartridge 用 KV cache parameterization（即 prefix-tuning 风格，把虚拟 token 的 K/V 作为可训练参数）优于 LoRA parameterization——在 in-domain 和 out-of-domain 任务上均表现更好。

## 关键结果

- **LongHealth**（医学推理，需理解整份病历）：0.96 GB Cartridge 精度 55.1%（**超过 full ICL**），13.8× 显存压缩
- **52 MB Cartridge**（256× 压缩 / 121× 吞吐提升）仍在 LongHealth 上 47.7%，vs DuoAttention @ 6.77 GB 仅 43.0%
- **Context length extrapolation**：Llama-3.1-8B 原生 128K context，用 self-study 处理 484K token 的 MTOB 翻译任务，0.54 GB Cartridge 达 36.1 chrF，**超过 Llama 4 Scout（109B 参数）在完整 context 下的 36.3 chrF**
- **可组合**：多个 Cartridge 无需联合训练即可拼接 query——模拟 ICL 在多文档拼接场景下的灵活性

## 相关

- **相关概念**：[[KV-Cache]]、[[Prefix-Tuning]]、[[LoRA]]、[[PagedAttention]]
- **同类方法**：DuoAttention、prompt compression (LLMLingua)、KV cache compression (SnapKV, H2O, PyramidKV)、prefix-tuning 原始工作
- **知识注入路线**：LoRA-based knowledge injection、context-distillation 近期工作
- **架构路线**：GQA (de-facto)、MLA (DeepSeek)、Linear Attention (Mamba/RWKV)、Titans/TTT (gradient-based memory)
- **同会议**：ICLR 2026
