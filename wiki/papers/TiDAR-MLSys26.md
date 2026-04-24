---
type: paper
name: TiDAR
full_title: "TiDAR: Think in Diffusion, Talk in Autoregression"
authors: [Jingyu Liu, Xin Dong, Zhifan Ye, Rishabh Mehta, Yonggan Fu, "et al."]
venue: MLSys
year: 2026
tags: [llm, diffusion, speculative-decoding, hybrid-architecture, inference]
source_pdf: "[[67c6a1e7ce56d3d6fa748ab6d9af3fd7.pdf]]"
source_md: "[[67c6a1e7ce56d3d6fa748ab6d9af3fd7]]"
---

# TiDAR: Think in Diffusion, Talk in Autoregression (MLSys 2026)

> **一句话总结**：序列级 diffusion-AR 混合架构，单次前向内既用 diffusion 并行 drafting 又用 AR 采样 verification，TiDAR-1.5B 对比 Qwen2.5-1.5B 无损质量下获得 4.71× 吞吐加速，TiDAR-8B 达 5.91×。

## 问题

AR 模型生成受内存带宽限制，每步只出一个 token，GPU 算力利用率低；diffusion LM 能并行生成多个 token，但并行采样会引入 token independence 假设，质量显著退化（Dream-7B 上 GSM8K 从 1→2 token/step 掉 10%）。现有 [[Speculative-Decoding]] 用小 draft 模型牺牲接受率；EAGLE-3、DeepSeek-V3 MTP 的 drafter 仍是 sequential AR，无法充分释放并行潜力。核心观察：在 memory-bound 区间，一次前向塞若干额外 "free token slots" 几乎不增加延迟（Figure 1 的 Qwen3-32B 实测）。

## 核心方法

训练阶段用一种因果+双向混合 attention mask：prefix 部分因果（AR mode，算 NTP loss），decoding block 部分双向（diffusion mode，算 masked token loss）。作者把 diffusion 部分全部设成 mask token（而不是像 Block Diffusion 那样随机 mask），让 diffusion loss 对每个位置都成立，loss 稠密且易与 NTP 平衡，并支持 one-step 推断。

推理阶段单次前向做三件事：(1) 对上一步的 draft token 做 AR rejection sampling；(2) 对下一步做 diffusion 并行 pre-draft，条件覆盖所有可能的 rejection 结果；(3) 保留因果计算的 KV 到 cache、拒掉的 token 对应 KV 被 evict（精确 KV cache 不重算）。相比 [[Speculative-Decoding]]：drafter 就是 base model 本身 capacity 最高，drafting 完全并行，drafting 与 verification 在同一前向里合一。

## 关键结果

- TiDAR-1.5B 从 Qwen2.5-1.5B 续训 50B tokens，相对 Qwen2.5-1.5B 达 **4.71× 吞吐加速**，质量接近（coding+math 平均 44.03% vs Qwen 的 41.64%）。
- TiDAR-8B 从 Qwen3-8B 续训 150B tokens，达 **5.91× 加速**（trust-diff 模式 avg 65.31% vs Qwen3-8B 的 68.09%）。
- 生成任务平均每次 NFE 生成 7.45（1.5B）到 8.25（8B）个 token。
- 对比 EAGLE-3 开源权重：TiDAR 的 token/NFE 和 token/s 转化率都更高；对比 Dream-7B、LLaDA-8B、Block Diffusion 全面领先。
- 似然评估可用纯 AR causal mask 一次 NFE 完成，避免传统 diffusion 的 Monte Carlo sampling 开销。

## 相关

- **相关概念**：[[Speculative-Decoding]]、[[KV-Cache]]、[[Flash-Attention]]
- **同类系统**：Block Diffusion、Dream、LLaDA、EAGLE-3、DeepSeek MTP
- **同会议**：[[MLSys-2026]]
