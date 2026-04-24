---
type: paper
name: XSched
full_title: "XSched: Preemptive Scheduling for Diverse XPUs"
authors: [Weihang Shen, Mingcong Han, Jialong Liu, Rong Chen, Haibo Chen]
venue: OSDI
year: 2025
tags: [gpu-scheduling, preemption, xpu, npu, accelerator]
source_pdf: "[[osdi25-shen-weihang.pdf]]"
source_md: "[[osdi25-shen-weihang]]"
---

# XSched: Preemptive Scheduling for Diverse XPUs (OSDI 2025)

> **一句话总结**：用统一的「preemptible command queue (XQueue)」抽象 + 三级硬件模型（Lv1 pending / Lv2 in-flight / Lv3 running 命令抢占），在 10 种 XPU（GPU/NPU/ASIC/FPGA）上实现软件抢占式调度，高优任务尾延迟降 2.10×，带宽分区平均开销 1.5%。

## 问题

XPU（GPU、NPU、ASIC、FPGA）硬件调度只支持 FCFS 或简单 RR，多租云、实时车载、AI PC 这些需要优先级/公平/ SLO 的多任务场景里会爆出 20×+ 的 tail latency 退化。已有软件抢占方案（EffiSha、FLEP、REEF、TimeGraph）都绑死于某一家 GPU：依赖 kernel 重写需要通用可编程性（NPU/ASIC 不行），或依赖 AMD microcontroller、NVIDIA Tegra 的 ioctl。三大可移植性难题——Portability / Uniformity / Evolvability——没人解。

## 核心方法

- **XQueue 抽象**：类比 CPU thread，每个 XQueue 持有一条顺序 command 序列（GPU kernel、memcpy、NPU tensor op、ASIC color conversion…）。接口 `submit/wait/suspend/resume` 四件套。调度策略（固定优先级、bandwidth partition、SRTF、EDF）直接写在这层，完全硬件无关。
- **多级硬件模型**：灵感来自数据库事务隔离级别。
  - **Lv1 — Pending 抢占**：所有 XPU 都支持（submit 前卡住不让 launch）。
  - **Lv2 — In-flight 抢占**：需要 hwQueue 可 deactivate/reactivate。作者在 Intel NPU 上用 microcontroller stalling、在 NVIDIA GPU 上用 command flushing 两种实现。
  - **Lv3 — Running 抢占**：interrupt 当前正在执行的 command，Pascal 之后的 NVIDIA GPU 支持。
  - 层次化：上层依赖下层，XPU 只需实现 Lv1 就能被支持，有能力的 XPU 再追加 Lv2/Lv3 以降低抢占延迟。
- **Progressive command launching**：不走 per-command 同步（否则 modern GPU 8–150% 退化），而是维护小量 in-flight command（到阈值就等一半完成），平衡 preemption latency 与运行时 overhead。关键在于既保留异步流水线、又把大多数命令留在 host 控制下可调度。
- **实现**：XShim 透明拦截 driver API；XPreempt 实现 XQueue；XAL 封装多级硬件接口；XScheduler daemon 做跨进程全局协调，通过 shared-memory IPC。Lv1 实现通常 214–841 行 C++ 就能跑起来。

## 关键结果

- 覆盖 10 种 XPU × 7 个软件平台：NVIDIA (Kepler/Volta/Ampere) / AMD / Intel GPU；Ascend / Intel / NVIDIA NPU；NVIDIA (PVA/OFA) ASIC；Xilinx FPGA
- 固定优先级：高优任务 P99 尾延迟降最多 2.10×
- Bandwidth partition：平均开销 1.5%
- 跨设备协同调度：NPU 前台任务在 NPU+GPU 后台干扰下 P99 降 2.63×
- 案例研究：
  - 多租 GPU：收获 2.74× 更多 GPU 资源，同时保证生产容器性能（对比 TGS）
  - 视频会议（Intel NPU 上 real-time 背景 + 语音转写）：P99 帧延迟降 9.26×
  - 多模型推理：Triton 上 P99 降 30%，与硬件专用方案 Paella 持平——**接入仅需十几行代码**

## 相关

- **相关概念**：[[Preemptive-Scheduling]]、[[GPU-Multitenancy]]、[[Priority-Inversion]]
- **同类系统**：REEF、TimeGraph、EffiSha、FLEP、TGS、Paella
- **同会议**：[[OSDI-2025]]
