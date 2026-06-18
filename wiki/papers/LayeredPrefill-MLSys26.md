---
type: paper
name: LayeredPrefill
full_title: "From Tokens to Layers: Redefining Stall-Free Scheduling for LLM Serving with Layered Prefill"
authors: [Gunjun Lee, Jiwon Kim, Jaiyoung Park, Younjoo Lee, Jung Ho Ahn]
venue: MLSys
year: 2026
tags: [llm-inference, moe, scheduling, chunked-prefill, energy-efficiency]
source_pdf: "[[02e74f10e0327ad868d138f2b4fdd6f0.pdf]]"
source_md: "[[02e74f10e0327ad868d138f2b4fdd6f0]]"
---

# From Tokens to Layers: Redefining Stall-Free Scheduling for LLM Serving with Layered Prefill (MLSys 2026)

> **一句话总结**：把 prefill 调度轴从 token 换成 layer group，每 iteration 仅一个 group 同时做 prefill+decode，消除 [[Chunked-Prefill]] 在 [[MoE]] 上的 expert 权重重载（traffic -39%），TTFT 最多降 70%、端到端延迟降 41%、每 token 能耗降 22%，SLO attainment 比 chunked prefill 高 14–45%。

## 问题

[[Continuous-Batching]] 把调度粒度降到 iteration 级，但长 prompt 下单次大 prefill 仍会 stall decode，触发 TBT SLO 违规。[[Chunked-Prefill]] 把 prompt 切成小 chunk 与 decode 交错，保证 stall-free decoding；在 [[MoE]] 上却有结构性代价：每个 chunk 都要穿过全部层、重复加载 expert 权重，memory traffic 最多放大 **39%**（sparsity erosion）。

小 chunk 是 TBT 约束下的必须，却让 per-expert token 数远低于 accelerator ridge point（~100–300 Op/B），MoE 层彻底 memory-bound。Qwen3-30B-A3B 上 chunk 512→2048 能耗/token 从 60→32 mJ（-46%），但 p99 TBT 48→129 ms 超 SLO——效率与延迟两难。

## 核心方法

**Layered Prefill**：模型纵向切成 G 个连续 layer group；每 iteration **恰好一个** group 对新请求做 prefill 并与所有进行中请求 decode，其余 group 只 decode。G 次 iteration 完成 prefill，全程 decode 不 stall。

- 每层只遍历 prompt 一次（对比 chunked：每层过 ⌈L/chunk_size⌉ 遍），消除冗余 expert 加载
- `G(L) = max(1, ⌈L/512⌉)` 对齐 chunked prefill 512-token chunk 的 per-iteration 工作量
- 与 chunked prefill 正交，可组合：大 chunk 让 MoE 进 compute-bound，layered 仍保 stall-free
- 在 [[vLLM]] 上实现，[[Flash-Attention]]-3 + CUDA Graph

## 关键结果

2× H100 80GB + NVLink，[[Tensor-Parallelism]]，Qwen3-30B-A3B / GPT-OSS-20B，ShareGPT + arXiv Summarization：

- SLO attainment（90% 阈值）：layered 可持续 request rate 比 chunked 高 **14–45%**（arXiv 长 prompt 优势更大）
- TTFT：同等 rate 下 mean TTFT 最多降 **70%**；SLO 工作点 Qwen 1.3→1.6 req/s（+23%）、GPT 2.1→2.7 req/s（+29%）
- 端到端延迟：arXiv+Qwen 单请求 9.4→5.5 s（**-41%**）
- Expert-load traffic（100 请求）：ShareGPT **-12%**、arXiv **-39%**
- 能耗：Qwen 56.6→44.2 mJ/tok（**-22%**）、GPT 37.4→29.8 mJ/tok（**-20%**）
- TBT attainment 两者均近 100%；layered 主要赢在 TTFT 与能耗

## 相关

- **相关概念**：[[Chunked-Prefill]]、[[MoE]]、[[Continuous-Batching]]、[[KV-Cache]]、[[Flash-Attention]]、[[Tensor-Parallelism]]
- **同类系统**：[[vLLM]]、Sarathi-Serve、Orca
- **同会议**：[[MLSys-2026]]