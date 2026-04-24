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

> **一句话总结**：把 LLM 服务的 prefill 调度轴从 token 换成 layer-group，每个 iteration 只在一个 layer group 内做 prefill+decode，消除了 [[Chunked-Prefill]] 在 [[MoE]] 上的冗余 expert 权重重载，TTFT 降 70%、端到端延迟降 41%、每 token 能耗降 22%。

## 问题

[[Chunked-Prefill]]（Sarathi-Serve）通过把 prompt 切成小 chunk、和 decode 交错执行来保证 stall-free decoding，稳住 TBT；但在 MoE 模型上有致命弱点：每个 chunk 都要穿过所有层、重复加载同一批 expert 权重，导致 memory traffic 最多放大 39%。小 chunk size 是 TBT SLO 约束下的必须，却让 per-expert token 数远低于 accelerator ridge point（100–300 Op/B），MoE 层彻底 memory-bound，sparsity 的优势被 chunking 抹掉（"sparsity erosion"）。

实测 Qwen3-30B-A3B：chunk size 从 512 到 2048，能耗/token 从 60 mJ 降到 32 mJ（-46%），但 p99 TBT 从 48 ms 飙到 129 ms，超 SLO。效率和延迟两难。

## 核心方法

**Layered Prefill**：调度单位从 token 换成 transformer layer group。模型纵向分成 G 个连续 layer group，每 iteration **恰好一个** group 同时做新请求的 prefill + 所有进行中请求的 decode，其他 group 只做 decode。G 次 iteration 后 prefill 完成，全程 decode 不 stall。

关键性质：
- 每个 layer 只过一遍 prompt（对比 chunked prefill：每层过 ⌈L/chunk_size⌉ 遍），expert 权重重载天然消除
- G 随 prompt 长度自适应：`G(L) = max(1, ⌈L/512⌉)`，对齐 chunked prefill 512-token chunk 的 per-iteration 工作量，保证可比性
- 与 chunked prefill 正交，可组合使用：大 chunk（如 8192）让 MoE 进 compute-bound 区，同时 layered 保证 stall-free
- 在 [[vLLM]] 上实现，[[Flash-Attention]]-3 做 attention，CUDA Graph 加速

## 关键结果

评估环境：2× H100 80GB + NVLink，[[Tensor-Parallelism]]，Qwen3-30B-A3B / GPT-OSS-20B，数据集 ShareGPT + arXiv Summarization。

- TTFT 最多降 70%，端到端延迟最多降 41%，每 token 能耗最多降 22%
- TTFT–TBT Pareto 前沿全面优于 chunked prefill
- 对长 prompt（arXiv，均值 9194 tokens）优势尤其显著
- 减少 off-chip 参数搬运，降 GPU DRAM 活动，降 co-located 服务的总能耗

## 相关

- **相关概念**：[[Chunked-Prefill]]、[[MoE]]、[[Continuous-Batching]]、[[KV-Cache]]、[[Pipeline-Parallelism]]、[[Flash-Attention]]
- **同类系统**：[[vLLM]]、Sarathi-Serve、Orca、FasterTransformer
- **同会议**：[[MLSys-2026]]
