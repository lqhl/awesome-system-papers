---
type: paper
name: Krypton
full_title: "Efficient Performance-Aware GPU Sharing with Compatibility and Isolation through Kernel Space Interception"
authors: [Shulai Zhang, Ao Xu, Quan Chen, Han Zhao, Weihao Cui, et al.]
venue: ATC
year: 2025
tags: [gpu-sharing, virtualization, kernel-space, mig, scheduling]
source_pdf: "[[atc2025-zhang-shulai.pdf]]"
source_md: "[[atc2025-zhang-shulai]]"
---

# Efficient Performance-Aware GPU Sharing with Compatibility and Isolation through Kernel Space Interception (ATC 2025)

> **一句话总结**：在 Linux 内核空间拦截 GPU command buffer + MIG 空间切分 + 反馈式 CPU token 调度，跨 CUDA/Vulkan runtimes 兼容并保证性能目标，相比 SOTA 减少所需 GPU 数 32.1%。

## 问题

GPU 共享方案要同时满足：兼容（多种 runtime / 版本）、隔离（fault + 性能）、高利用率。但现有方案均有缺陷：API-remoting（TGS / GaiaGPU / Orion）只覆盖特定 CUDA 版本（TGS 仅 CUDA 11.2），且无法捕获隐式 GPU 操作导致 OOM；MPS-based（GSlice）共享同一 GPU context，单进程 crash 会让所有 8 个 victim 同时挂；MIG 硬件隔离但分区固定，不灵活；Time-sharing 利用率仅 44%（SM 闲置），spatial sharing 时间片闲置。

## 核心方法

两个 insight：(1) 把拦截下沉到 kernel space 即可同时拿下兼容与隔离；(2) Spatio-temporal orchestration 比固定配额更能减少 fragment。

- **Kernel-space Command Buffer Interception**：通过 ioctl 系统调用追踪 NVIDIA KMD 分配的 command buffer 地址，用 `do_mprotect_pkey` 把 buffer 页改成 read-only 来"锁住"进程 GPU 访问；进程写时触发 segfault → 自定义 signal handler → 阻塞等内核解锁。这样跨 runtime（CUDA / Vulkan / OpenGL）通用，无需逐 API 适配。
- **GPU Memory Management**：在 kernel space 拦截 ioctl 中的 memory 分配请求，包括 CUDA context 创建时隐式分配的 ~400MB，避免 OOM 攻击。
- **Feedback-controlled CPU Token Scheduling**：CPU token 长度默认 100ms，结合 NVML / DCGM 的实时 GPU utilization 信号，挑选 util/quota 最低的 app 激活；异步 kernel 累积导致超额时下个时间窗补偿对方。
- **Two-stage Bin-Packing Orchestrator**：(1) 给每个 workload 选最小可行 MIG instance；(2) 时间维 fuse 同 spatial 配置；(3) 迁移 fragment；(4) instance bin-pack 减少 GPU 数。复杂度 O(MP)。

详见 [[atc2025-zhang-shulai]]。

## 关键结果

- 相比 Temporal / Best-fit-MIG / GPUlet-MIG，GPU 数减少 32.1%。
- 应用性能相对误差仅 3.3%（适应 token 控制误差 ≤ 0.9%，无 feedback 控制 5.3%）。
- 在 A100 上验证 CUDA 12.1 + Vulkan 1.3 兼容；adversary 起 48 个进程不会击穿 victim。

## 相关

- **相关概念**：[[GPU-Sharing]]、[[MIG]]、[[MPS]]
- **同会议**：[[ATC-2025]]
