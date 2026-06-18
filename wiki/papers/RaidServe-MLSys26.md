---
type: paper
name: RaidServe
full_title: "RaidServe: High-Performance Resilient Serving"
authors: [Ziyi Xu, Zhiqiang Xie, Swapnil Gandhi, Christos Kozyrakis]
venue: MLSys
year: 2026
tags: [fault-tolerance, tensor-parallelism, llm-serving, kv-cache, resilience]
source_pdf: "[[f033ab37c30201f73f142449d037028d.pdf]]"
source_md: "[[f033ab37c30201f73f142449d037028d]]"
---

# RaidServe: High-Performance Resilient Serving (MLSys 2026)

> **一句话总结**：RaidServe 在 [[Tensor-Parallelism]] 服务中容忍不规则 GPU 数量：Cyclic [[KV-Cache]] Placement + Hybrid Attention + load-aware routing 消除恢复后算存倾斜，配合 proactive KV backup 与 on-demand weight recovery，在 8×H100 上吞吐最高 **2×**、恢复延迟比标准方案低 **两个数量级**（183×）。

## 问题

[[Tensor-Parallelism]] 把同一 scale-up 域内 GPU 紧耦合：单卡故障会丢该 rank 上全部权重与 [[KV-Cache]]，in-flight 请求需昂贵 re-prefill，幸存 GPU 还要 resharding，引发 latency spike。恢复后 GPU 数不规则（如 8→7）又打破 attention head 均分假设，造成持久算存失衡——某些 rank 多扛 head / 更多 KV，有效 batch size 被拖垮。

## 核心方法

**Memory & compute balancer**：
- **Cyclic KVCache Placement**：attention head 与 KV 按层轮换到各 rank，n 层窗口内聚合 KV 近似均衡
- **Hybrid Attention**：每个 TP worker 持相同 head 数，剩余 head 用 [[Tensor-Parallelism|TP]] + data parallel 复制处理，消除 intra-layer straggler
- **Fine-grained load-aware routing**：DP rank 按 pending token 负载贪心分配；adaptive chunked prefill 在 token budget 内给 least-loaded GPU 塞多请求 chunk

**Lightning Recovery**：
- **Proactive KVCache Backup**：decode 时异步增量备份 KV 到 host DRAM；故障后只恢复缺失分片并按新 layout 迁移
- **On-demand Weight Recovery**：FFN 用固定 shard 粒度，幸存权重原地保留，只拉缺失 shard；attention 权重分片经 NVLink 交换，避免冗余 PCIe

基于 ~7k 行轻量 serving engine，兼容 [[vLLM]] / [[SGLang]] 类基础设施。

## 关键结果

- 8×H100、GCP 真实 fault trace：LLaMA-3.1-70B 平均吞吐 **1.28×** Standard TP、**20%** 高于 Non-Uniform TP；Mixtral-8x22B **1.71×** / **17%**
- 在线 Mooncake trace、7 GPU：prefill TTFT≤10s 吞吐 **2×** Standard-TP4；decode TBT≤40ms **2×** / **1.85×** vs Non-Uniform-TP7
- TP7 decode：memory balancing +34% 峰值吞吐，再加 compute balancing 再 +43%
- 恢复：Recompute >20s；host KV restore **41.5×** 更快；RaidServe-Full 再 **4.4×**，P99 TBT **572ms→229ms**；端到端恢复加速 **183×**
- 最多 3/8 GPU 故障仍可维持高吞吐与均衡利用率

## 相关

- **相关概念**：[[Tensor-Parallelism]]、[[KV-Cache]]、[[Chunked-Prefill]]、[[Continuous-Batching]]、Fault-Tolerant Serving
- **同类系统**：[[vLLM]]、[[SGLang]]、SpotServe、Llumnix、DejaVu、Bamboo、Oobleck
- **同会议**：[[MLSys-2026]]