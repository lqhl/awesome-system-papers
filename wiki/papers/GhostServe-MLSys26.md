---
type: paper
name: GhostServe
full_title: "GHOSTSERVE: A Lightweight Checkpointing System in the Shadow for Fault-Tolerant LLM Serving"
authors: [Shakya Jayakody, Youpeng Zhao, Chinmay Nehate, Jun Wang]
venue: MLSys
year: 2026
tags: [llm-inference, fault-tolerance, kv-cache, erasure-coding, serving]
source_pdf: "[[1c383cd30b7c298ab50293adfecb7b18.pdf]]"
source_md: "[[1c383cd30b7c298ab50293adfecb7b18]]"
---

# GHOSTSERVE: A Lightweight Checkpointing System in the Shadow for Fault-Tolerant LLM Serving (MLSys 2026)

> **一句话总结**：用 erasure coding 在 shadow 里只存 [[KV-Cache]] parity shard（8:2 比全量复制省 75% 内存/73% checkpoint 延迟），chunk 级 round-robin 调度 + hybrid recovery，在 [[SGLang]] 上 checkpoint 快 2.7×、恢复快 2.1×，故障下 P50 延迟改善 1.2×。

## 问题

百万 token agent 任务让 LLM serving 变成长时间有状态作业；单 GPU 软故障（内存错误、kernel fault、资源泄漏）会丢掉不断增长的 [[KV-Cache]]，只能从头重算 prefill——405B 模型 1M context 可浪费 20 分钟。训练侧 checkpoint 方案（复制整份 KV、写 SSD）对 serving 不适用：tensor parallelism 下 I/O 难 overlap，64K 输入可把 prefill 延迟拉高 113%；全量复制 300GB+ host memory，和 [[PagedAttention]] 式 KV offload 抢资源。

## 核心方法

**GhostServe** 把存储系统里的 erasure coding 搬到 serving：N 个 data shard 只生成 K 个 parity shard（K ≪ N），parity 异步落到 host memory，故障时用幸存 shard + parity 重建，而非复制整份 [[KV-Cache]]。

关键设计：
- **FP16 → uint16 无损编码**：标准 XOR/RDP/Reed-Solomon 在 bit 域工作，论文把 FP16 按 IEEE-754 重解释为整数，再用融合 CUDA kernel 做 encode/reconstruct（比 PyTorch 实现快很多）。
- **Chunk-level checkpointing**：对齐 [[Chunked-Prefill]]，每个 token chunk 生成后由 round-robin 指定的一张 GPU gather 全 TP shard、算 parity、PCIe 异步下刷；GPU 只需小块临时 buffer，不占持久 HBM。
- **Hybrid recovery**：短序列全量 recompute；长序列只 recompute 前 r 个 chunk，其余用 parity 重建，overlap I/O 与计算。
- **实现**：~4K Python + 1.5K C++/CUDA 插件，后端 [[SGLang]] 0.5.1 + FlashInfer；也声称可移植到 [[vLLM]]。

主要面向 **intra-node TP** 单设备内存软错误；不解决 NCCL 拓扑静态、跨 node 硬故障等 full-stack 问题。

## 关键结果

- Checkpoint 延迟平均 **2.7×** 快于 CPU 复制（DejàVu 风格），恢复 **2.1×**；I/O 开销比 CPU checkpoint 降 **13×**、比 SSD checkpoint 降 **132×**。
- LLaMA-3-70B、64K 输入：恢复 <5s vs SSD 基线 ~2 分钟；在线 serving 故障率 15% 时 P50/P99 分别 **1.2× / 1.1×** 优于 naive recompute，EITR >90%。
- 1M token prefill：相对无 checkpoint 基线 overhead <6%；相对 DejàVu checkpoint 从 2.6 分钟降到 **9 秒**。
- 8:2 parity：host memory 与 checkpoint 延迟各降约 **75% / 73%** vs 全量复制。

## 相关

- **相关概念**：[[KV-Cache]]、[[Chunked-Prefill]]、[[Tensor-Parallelism]]、[[Continuous-Batching]]、[[Disaggregation]]
- **同类系统**：[[SGLang]]、[[vLLM]]、Mooncake、DejàVu（Strati et al. 2024）
- **同会议**：[[MLSys-2026]]