---
type: paper
name: GMI-DRL
full_title: "GMI-DRL: Empowering Multi-GPU DRL with Adaptive-Grained Parallelism"
authors: [Yuke Wang, Boyuan Feng, Zheng Wang, Guyue Huang, Tong Geng, et al.]
venue: ATC
year: 2025
tags: [reinforcement-learning, multi-gpu, gpu-multiplexing, drl, scaling]
source_pdf: "[[atc2025-wang-yuke.pdf]]"
source_md: "[[atc2025-wang-yuke]]"
---

# GMI-DRL: Empowering Multi-GPU DRL with Adaptive-Grained Parallelism (ATC 2025)

> **一句话总结**：把 GPU 切成大小可调的子 GPU（GMI），按 DRL 异构任务自适应映射 + 高效 inter-GMI 通信，DGX-A100 上训练吞吐提升至 2.34×、GPU 利用率提升 40.8%。

## 问题

DRL 训练在多 GPU 平台（如 DGX-A100）上利用率低：

- DRL 由 Simulator / Agent / Trainer 三种异构组件组成，计算模式差异大（物理仿真 vs GEMM）
- 简单增大 batch size（fine-grained parallelism）超过阈值反而吞吐下降——不同组件竞争固定 GPU 资源
- 现有 GPU 空间复用（MPS、MIG）只针对独立同构任务（如 DNN serving），缺少 sub-GPU 间通信支持

## 核心方法

提出 **Adaptive-Grained Parallelism (AGP)**：让 GPU 资源大小适配 workload 而非反过来。引入 **GPU Multiplexing Instance (GMI)** 作为统一可调资源的 sub-GPU 抽象。

三个组件：

1. **Adaptive Coordinator**：task-aware GMI mapping，针对 DRL serving / synchronized training / asynchronized training 各自分析 DP-MP / MP-DP / DP-only / DP-MP(EA-T) / DP-MP(E-AT) 等映射模板，结合 resource-performance 模型量化吞吐（DRL serving 中 DP-only 比 MP-DP 高 ~2.5×；同步训练 DP-only 比 DP-MP(EA-T) 高 ~5×）；workload-GMI 联合优化 num_env 和 GMIperGPU
2. **Specialized Communicator**：处理 inter-GMI 通信（intra-GPU 与 inter-GPU），latency-optimized inter-trainer 同步与 throughput-optimized 经验共享
3. **GMI-centric programming support**：方便 DRL-like 应用按 GMI 切分

深度细节回 [[atc2025-wang-yuke]]。

## 关键结果

- 训练吞吐相对 SOTA（Isaac Gym + MSRL）提升至 **2.34×**
- GPU 利用率提升 **40.8%**
- 在 Anymal / Humanoid 等多个 PPO benchmark 上一致改进

## 相关

- **相关概念**：[[Tensor-Parallelism]]、[[Pipeline-Parallelism]]
- **同会议**：[[ATC-2025]]
