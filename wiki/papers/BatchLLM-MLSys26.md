---
type: paper
name: BatchLLM
full_title: "BatchLLM: Optimizing Large Batched LLM Inference with Global Prefix Sharing and Throughput-oriented Token Batching"
authors: [Zhen Zheng, Fanghao Zhou, Xin Ji, Chuanjie Liu, Taosong Fang, Gang Peng]
venue: MLSys
year: 2026
tags: [llm-inference, batch-inference, prefix-sharing, throughput, vllm]
source_pdf: "[[a97da629b098b75c294dffdc3e463904.pdf]]"
source_md: "[[a97da629b098b75c294dffdc3e463904]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# BatchLLM: Optimizing Large Batched LLM Inference with Global Prefix Sharing and Throughput-oriented Token Batching (MLSys 2026)

> **一句话总结**：离线/大批量场景（搜索 snippet 等）prompt 全局可知、指标是吞吐而非尾延迟；[[vLLM]] LRU [[PagedAttention]] 仅 **35.8%** token 节省 vs 最优 **58.1%**；BatchLLM 先建全局 prefix 树、按共享前缀分组重排（高 decode/prefill 比优先）、memory-centric token batching + 水平融合 attention kernel，相对 vLLM/[[SGLang]] **1.3–10.8×**。

## 问题与动机

工业 batch/offline [[LLM]] 任务（同一文档多 query）共享长前缀；在线 serving 引擎为 FCFS/chunked-prefill 公平性优化，导致 decode token 与长 prefill chunk 混合不足、「valley」低 GPU 利用率（Fig. 2）。

## 关键观察 / 隐含假设

- **观察 1：整批 prompt 已知时，runtime LRU 会过早驱逐即将复用的 KV block。**
  - **依赖假设**：batch 在调度前可静态分析；dominant prefix 为长文档非 system prompt。
  - **可能失效场景**：streaming 在线 batch 无全局视图；前缀 dominated by 短 instruction 时多级树仍重要。

- **观察 2：先调度高 decode/prefill 比请求可与后续长 prefill chunk 更好混合（Fig. 1 chunked-prefill）。**
  - **依赖假设**：chunked-prefill 已启用；吞吐优先可牺牲一定公平性。
  - **可能失效场景**：极低 decode 长 prefill 批重排收益有限。

- **观察 3：按 request/token 数阈值限制 batch 会在 decode-heavy 迭代人为压低 token 数。**
  - **依赖假设**：KV 内存有余量时应用 memory-centric 上限扩 batch。
  - **可能失效场景**：极长 generation KV 爆内存时需保守 cap。

## 核心方法

**Ahead-of-time prefix**：全局树 + DP 将多级前缀合并为单层（工业任务中长 context 主导）；按组调度。

**Reorder**：组级按 decode/prefill 比降序。

**Memory-centric token batching**：按 KV 占用形成更大 token-batch。

**Horizontal fused prefix-shared attention**：多 KV chunk 单 kernel，减 launch/tail。

基于 vLLM 实现；NVIDIA/AMD GPU + 工业 workload。

## 设计取舍

- **静态全局优化 vs 在线 LRU**：吞吐优，不适用低延迟在线。
- **单层 prefix 简化 vs 完整 radix 多级**：降复杂度，略损多级共享比。
- **重排 vs FCFS**：赢混合，输 latency fairness。
- **边界条件**：大批量 prefix-shared；单请求 streaming 非目标。

## 实验与结果

- Microbenchmark + 工业任务：**1.3–10.8×** vs vLLM/SGLang（多硬件）。
- 工业集：最优节省 **58.1%** prefill tokens，vLLM **35.8%**。
- Ablation：显式 prefix、重排、memory batching、水平 fusion 均有贡献。

## Critical Analysis

### 论证链条

「全局可知」洞察贯穿三优化 + kernel，与微软工业场景一致，倍数跨度大需看具体 workload 形态。

### 假设压力测试

batch 边到边到达需周期性重规划；多租户混合在线+离线队列时静态假设失效；AMD vs NVIDIA kernel 维护双倍。

### 实验可信度

工业 workload 是亮点；baseline 为调优 vLLM/SGLang。缺公开 trace。

### 系统性缺陷

预处理 prefix 树 CPU 成本；超大批次内存峰值；与 speculative decoding 集成未讨论。

## 局限与 Future Work

- **局限**：面向 offline/batch；在线 SLO 场景不适用；依赖 chunked-prefill。
- **Future work**：增量 batch 到达时的局部重规划；与 [[Disaggregation]] 预填充分离结合。

## 相关

- **相关概念**：[[PagedAttention]]、[[KV-Cache]]
- **同类系统**：[[vLLM]]、[[SGLang]]
- **同会议**：[[MLSys-2026]]
