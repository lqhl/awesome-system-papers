---
type: paper
name: TiDAR
full_title: "TiDAR: Think in Diffusion, Talk in Autoregression"
authors: [Jingyu Liu, Xin Dong, Zhifan Ye, Rishabh Mehta, Yonggan Fu, et al.]
venue: MLSys
year: 2026
tags: [diffusion-lm, speculative-decoding, llm-inference, hybrid-architecture]
source_pdf: "[[67c6a1e7ce56d3d6fa748ab6d9af3fd7.pdf]]"
source_md: "[[67c6a1e7ce56d3d6fa748ab6d9af3fd7]]"
---

# TiDAR: Think in Diffusion, Talk in Autoregression (MLSys 2026)

> **一句话总结**：TiDAR 在单次 forward 内用 structured attention 并行 diffusion drafting（Think）与 AR rejection sampling（Talk），1.5B 无损质量下 4.71×、8B 5.91× 解码吞吐，首次让 diffusion LM 在 wall-clock 上超越 EAGLE-3 speculative decoding。

## 问题

AR LLM 解码 memory-bound、GPU 利用率低；diffusion LM（Dream、Llada）可并行但 intra-step token independence 损害质量，且缺乏 exact [[KV-Cache]]。现有 [[Speculative-Decoding]] 用小 draft model 或 MTP 层，draft 容量受限且 drafting 与 verification 串行，无法充分利用 H100 上「free token slots」（额外 token 不显著增加 latency）。

## 核心方法

**TiDAR**：单模型双模式——prefix 用 causal attention 学 $P_{AR}$，mask block 用 bidirectional attention 学 $P_{Diff}$（训练时 diffusion 段全 mask，one-step denoising）。

每步三代 token 分区：prefix（复用 KV）/ 上步 draft（AR reject sampling）/ 下步 pre-draft（diffusion 并行，条件于所有可能 accept prefix）。

Structured hybrid mask 使 drafting 与 sampling **同一 forward 完成**；支持 exact KV cache 与 Flex Attention mask 切片复用。

从 Qwen2.5-1.5B / Qwen3-8B continual pretrain（50B/150B tokens）。

## 关键结果

- **4.71×**（1.5B）/ **5.91×**（8B）相对 AR baseline 解码吞吐（H100，bs=1）
- 1.5B **lossless** vs AR counterpart；8B minimal loss，平均 **7.45–8.25 tokens/NFE**
- 首次 diffusion 架构在 wall-clock 上 **超越 EAGLE-3** open weights（conversion rate 更高因单 forward 并行 draft+sample）
- Likelihood 任务可用标准 AR 方式单 NFE 评估，与 generative quality 对齐

## 相关

- **相关概念**：[[Speculative-Decoding]]、[[KV-Cache]]、[[Flash-Attention]]、diffusion LM
- **同类系统**：EAGLE-3、Dream、Llada、Block Diffusion、Medusa
- **同会议**：[[MLSys-2026]]