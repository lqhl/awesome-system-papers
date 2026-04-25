---
type: paper
name: Toppings
full_title: "Toppings: CPU-Assisted, Rank-Aware Adapter Serving for LLM Inference"
authors: [Suyi Li, Hanfeng Lu, Tianyuan Wu, Minchen Yu, Qizhen Weng, et al.]
venue: ATC
year: 2025
tags: [llm-serving, lora, cpu-offload, multi-tenant, scheduling]
source_pdf: "[[atc2025-li-suyi-toppings.pdf]]"
source_md: "[[atc2025-li-suyi-toppings]]"
---

# Toppings: CPU-Assisted, Rank-Aware Adapter Serving for LLM Inference (ATC 2025)

> **一句话总结**：用 CPU 同时跑 LoRA prefill 来掩盖 GPU 上的 adapter loading 冷启动，配合 rank-aware 集群调度，相对 S-LoRA/dLoRA 在 Llama2-7B/70B 多租户 LoRA serving 上平均延迟降 1.7×、SLO 满足率 99%。

## 问题

LoRA 多租户 serving 系统（Punica、S-LoRA）把 base LLM pin 在 GPU、LoRA 在 host memory，按需 load。两个核心问题：

1. **累积 decoding-interruption 开销**：[[Continuous-Batching]] 下，新请求到达要先 load LoRA（rank=64 ≈ 100MiB，几十 ms PCIe 传输）再 prefill。这期间所有 inflight 请求 decoding 被打断。RPS=9 时单请求被中断 25 次中位数，累积延迟占总服务时间 29%。预 cache 所有 LoRA 不可行：rank=64 单 LoRA 100MiB ≈ 200 token 的 KV cache，trace 50% 命中率需缓存 200+ LoRA（>20GiB）
2. **rank 异构调度**：用户请求的 LoRA rank 各异。Punica 的 BGMV kernel 把小 rank padding 到最大 rank（决定 latency）；S-LoRA 的 MBGMV 不 pad（latency 看平均 rank）。同 batch size 下 rank 异构能让 decoding latency 涨 28%。集群调度需要根据 rank-aware 性能模型而非简单 round-robin

## 核心方法

**CPU-assisted LoRA serving**：

- 新请求到达时，GPU 后台异步从 host load adapter（pipelined：分 M 个 layer group，profile 让 CPU compute 与 GPU loading 时间对齐）
- 同时 **CPU 立即开始 prefill 的 LoRA 计算**（xAB 仅 ~1 GFLOPs，CPU 能扛）
- adapter 一旦完整在 GPU，切回 GPU 完成剩余层 + decoding

efficient 协调三大优化：

- **Sync-free CPU LoRA invocation**：自定义 CUDA operator 把 async MemCpy 与 CUDA signaling kernel 融合（信号写 host shared memory 的 semaphore），消除 PyTorch 显式 sync，让 base model 后续 kernel 不阻塞 launch。prefill latency 降 15%
- **Shared memory 数据传输**：base process 与多个 CPU LoRA process 间用 shared memory + semaphore polling，data transfer < 1ms，避开 PyTorch 内置 IPC 的拷贝/序列化
- **Profiling-guided 多 CPU 并行**：profile 单核能处理多少 token，按需开 ⌈L/c⌉ 个 CPU 进程并行算 prefix 切片。比 PyTorch native multithreading 在 16 核下快 1.4×

**Rank-aware 调度**：建 performance model（基于 BGMV/MBGMV kernel profiling）预测「把请求 r 路由到 instance i 后该 instance 的 batch decoding latency」。新请求到达时对所有持有该 LoRA 的 instance 算 cost score（额外延迟 + SLO 违反风险），路由到 cost 最低者。深度细节回 [[atc2025-li-suyi-toppings]]。

## 关键结果

- Llama2-7B/70B 上 vs S-LoRA、dLoRA：平均请求延迟降 **最高 1.7×**
- 相对「全 LoRA 预 cache GPU」的理想（不可实现）baseline 仅 7% 额外开销
- 长 prompt（2k–30k token）下优势保持
- rank-aware 调度 vs 现有 rank-agnostic 策略：avg TPT 降 57%，**SLO 达成率 99%**
- 同时解决 dLoRA 的 GPU OOM 问题（dLoRA 全预 cache 在 LoRA 多时 OOM）

## 相关

- **相关概念**：[[LoRA]]、[[Continuous-Batching]]、[[Multi-Tenant-Serving]]、[[CPU-Offload]]
- **同类系统**：Punica（BGMV kernel）、S-LoRA（MBGMV kernel + unified memory pool）、dLoRA（dynamic merge/unmerge）
- **同作者**：[[Katz-ATC25]]（同一作 Suyi Li，做 diffusion 的 adapter serving）
- **同会议**：[[ATC-2025]]
