---
type: paper
name: SuperInfer
full_title: "SuperInfer: SLO-Aware Rotary Scheduling and Memory Management for LLM Inference on Superchips"
authors: [Jiahuan Yu, Mingtao Hu, Zichao Lin, Minjia Zhang]
venue: MLSys
year: 2026
tags: [llm-inference, slo, gh200, nvlink-c2c, offloading, scheduling]
source_pdf: "[[8f14e45fceea167a5a36dedd4bea2543.pdf]]"
source_md: "[[8f14e45fceea167a5a36dedd4bea2543]]"
---

# SuperInfer: SLO-Aware Rotary Scheduling and Memory Management for LLM Inference on Superchips (MLSys 2026)

> **一句话总结**：在 GH200 Superchip 上，用 OS 风格的 RotaSched（VLT + LVF 主动 rotation）和 DuplexKV（全双工 KV rotation engine）把 NVLink-C2C 带宽利用率从 <5% 拉到近峰值，高负载下 TTFT SLO 达成率比 SOTA 高最多 **74.7%**，TBT 与吞吐持平。

## 问题

LLM serving 在严格 TTFT/TBT SLO 与有限 GPU memory 之间拉扯：高请求率下 [[KV-Cache]] 爆满引发 HOL blocking。PCIe offload（FlexGen、NEO 等）带宽仅 32–64GB/s，swap 太慢；SLO-aware scheduler（Sarathi-Serve、SOLA）又假设 all-on-GPU。GH200 的 NVLink-C2C 有 900GB/s，但直接移植 PCIe offload 方案只用到 **<5%** 有效带宽（[[vLLM|vLLM]] ~10GB/s），瓶颈在软件栈。

## 核心方法

**RotaSched**：借鉴 OS time-slicing，引入 rotary state（KV 暂 swap 到 Grace DRAM），用 **Virtual Lag Time (VLT)** 衡量请求偏离 SLO 的程度，**Largest-VLT-First (LVF)** 主动在 running / waiting / rotary 间 rotation，而非 OOM 时才 passive preempt。

**DuplexKV**：针对 [[PagedAttention]] 碎片化小段导致的 C2C 低利用率，做 (1) eager block rotation 消除 H2D/D2H race、(2) layout 变换合并大段 batch transfer、(3) cross-iteration pipeline overlap。

## 关键结果

- GH200 上多模型多负载：TTFT SLO 达成率最高 **+74.7%**，TBT 与吞吐与 SOTA 相当
- 低负载 memory 充足时与 baseline 持平
- C2C 有效带宽从 ~10GB/s 提升到 ~200GB/s 量级

## 相关

- **相关概念**：[[KV-Cache]]、[[PagedAttention]]、[[Continuous-Batching]]、[[Chunked-Prefill]]
- **同类系统**：[[vLLM]]、[[SGLang]]、Sarathi-Serve、FlexGen、Pie
- **同会议**：[[MLSys-2026]]