---
type: paper
name: Sirius
full_title: Colocating ML Inference and Training with Fast GPU Memory Handover
authors: [Jiali Wang, Yankui Wang, Mingcong Han, Rong Chen]
venue: ATC
year: 2025
tags: [gpu-sharing, ml-inference, ml-training, colocation, memory-management]
source_pdf: "[[atc2025-wang-jiali.pdf]]"
source_md: "[[atc2025-wang-jiali]]"
---

# Colocating ML Inference and Training with Fast GPU Memory Handover (ATC 2025)

> **一句话总结**：SIRIUS 用毫秒级 GPU 显存交接（5 ms 平均）让 inference + training 真正空间共享 GPU，inference SLO 合规率平均 +57%（最高 +97%），训练吞吐 2.2× 起（最高 13.7×）。

## 问题

MLaaS 推理服务为保 latency SLO（如 100 ms）超额预留 GPU，利用率常 < 15%。颠倒过来 colocate inference + training 已有方案皆有缺陷：temporal sharing（PipeSwitch/Lyra）切换上下文几百 ms 易违 SLO；static partition 配比无法跟随负载；UM dynamic swapping 走 PCIe 性能掉 93%。核心痛点是显存交接慢——典型 250 ms（gradient compute 等待 + cudaMalloc + 初始化）。

## 核心方法

三大关键技术：

- **Instant Memory Adjustment**：把训练 batch 拆成 gradient compute (GC, >95% 时间) 与 model update (MU, <10ms) 两阶段。GC 阶段不改 training state，可直接 discard 当前 batch；用 software queue 替代直接 launch GPU kernel，dispatcher 接到调整请求后停止入队、等少量 in-flight kernel 完成、丢弃队列剩余 op。多 GPU 训练通过 set NCCL `abort flag` 跳出 in-flight AllReduce 而保持 NCCL 连接（避免 ncclCommAbort 几百 ms 的重连）。Batch 在 GPU 间动态再分配防止 straggler。
- **Safe Memory Handover**：用 GPU VMM 维护 inference/training 共享 memory pool，绕过 framework cache 与 cudaMalloc。仅在 memory adjustment 时显式回收训练已释放但还可能被 in-flight op 访问的内存（避免 data pollution）；零填充防泄漏，开销可忽略。
- **SLO-aware Reallocation**：基于 M/G/1 queueing model 推导 inference SLO 合规率（含 cold start 转移 α、liveness time T_idle、watermark W）。idle model 不立即释放，先在 reserved memory 中等待；reserved 满 2W 时一次性放回 W 给 training，做 coarse-grained 调整减少抖动。

## 关键结果

- 4 generated trace（LIGHT/HEAVY/BURST/SKEWED）+ 2 真实 trace（MAF、BurstGPT）评估。
- 单 GPU：相比 TaskSwitch（PipeSwitch 风格）P99 latency 改善 12.6×、SLO 合规 +72.6%、训练吞吐 4.6×；相比 SP-50（静态切半）P99 改善 261.9×；相比 SP-75 改善 64.3×。
- 整体 inference SLO 合规率达到 inference-alone 的 98%（高强度负载下）。
- discarded batch 仅浪费 1.4% 训练计算时间。

## 相关

- **相关概念**：GPU Sharing、Spatial Sharing、Memory Handover、SM Mask、Gradient Accumulation
- **同类系统**：PipeSwitch、Lyra、NVIDIA MPS、TGS
- **同会议**：[[ATC-2025]]
