---
type: paper
name: GPreempt
full_title: "GPreempt: GPU Preemptive Scheduling Made General and Efficient"
authors: [Ruwen Fan, Tingxu Ren, Minhui Xie, Shiwei Gao, Jiwu Shu, Youyou Lu]
venue: ATC
year: 2025
tags: [gpu, preemption, scheduling, context-switch, latency-critical]
source_pdf: "[[atc2025-fan.pdf]]"
source_md: "[[atc2025-fan]]"
---

# GPreempt: GPU Preemptive Scheduling Made General and Efficient (ATC 2025)

> **一句话总结**：用 NVIDIA 开源驱动里未文档化的 timeslice 分配机制 + hint-based pre-preemption（与 LC 任务的 data prepare 阶段重叠 context-switch）实现 < 40 µs 的 GPU context-switch preemption，既无 wait-based 的高延迟也无 reset-based 对 idempotent 的依赖。

## 问题

GPU 上 LC（latency-critical，如自驾、实时推理）与 BE（best-effort，如离线推理）共置时需 preemption。已有方案两难：(1) **Wait-based**（block-level，如 Effisha）通用但要等 thread block 跑完，可达 5 ms 延迟；(2) **Reset-based**（如 REEF）快但只对 idempotent kernel 适用，对 graph computing/scientific computing/CUDA Graph 失效。直接做 context switch 又面临 GPU 调度对用户 opaque（无 yield 接口）+ 单 GPU context 高达 44 MB 的 switch overhead。

## 核心方法

GPREEMPT 引入 switch-based preemption：

1. **Timeslice-based yield**：通过分析 NVIDIA open GPU kernel module 发现 GPU 硬件按 timeslice 在 task 间循环这一未文档化机制。把 BE task 的 timeslice 调到极短（如 200 µs），LC task 的 timeslice 调到很长，BE 自然在 t1/2 平均时间内 yield；BE 任务间因属同 scheduling group 不会互相切换，避免无 LC 时的开销。A100 context save 约 40 µs。
2. **Hint-based pre-preemption**：利用 LC 任务必经的 data preparation（图像 crop/normalize ~ 几百 µs；CPU→GPU cudaMemcpy ~ 80 µs）阶段——CPU 与 GPU compute engine 独立——提前注入 preemption kernel 占据 BE timeslice，让 LC kernel 准备好就立即接管。GDRCopy 直接 HBM 映射通知 preemption kernel 完成，~ 1 µs。Scheduled pre-preemption 让 user 指定预约时机避免提前过头浪费 GPU。

AMD GPU：MES (Micro Engine Scheduler) 同样基于 timeslice，可同方法实现；老 AMD GPU 通过修改 ROCm debug 机制手动切换。详细 driver 修改见 [[atc2025-fan]]。

## 关键结果

- NVIDIA A100 端到端延迟：相比 LCO（仅 LC），no-preemption +58.4%、SEQ +96.3%、wait-based +15.3%、GPREEMPT 仅 +2.4%。
- AMD MI100：vs reset-based REEF +13.2% / GPREEMPT +10%（且 GPREEMPT 兼容非 idempotent）。
- 单 LC 任务 workload preemption 延迟 < 40 µs；10 个并发 LC+BE workload E 仅增 ~ 500 µs。
- Pre-preemption 可减约 160 µs，scheduled 版本再提 BE throughput 4-10%。
- BE throughput 相比 wait-based 提升 17-26%；GPU 总吞吐 NVIDIA 88.6%、AMD 82.2%（vs no-preempt 100% 基线）。

## 相关

- **相关概念**：[[GPU-Scheduling]]、[[Preemption]]、[[Context-Switch]]、[[CUDA-Graph]]
- **同类系统**：REEF（reset-based）、Effisha、GPES、Chimera、SRM
- **同会议**：[[ATC-2025]]
