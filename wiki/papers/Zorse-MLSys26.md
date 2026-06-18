---
type: paper
name: Zorse
full_title: "Zorse: Optimizing LLM Training Efficiency on Heterogeneous GPU Clusters"
authors: [Runsheng Benson Guo, Utkarsh Anand, Khuzaima Daudjee, Rathijit Sen]
venue: MLSys
year: 2026
tags: [distributed-training, heterogeneous-gpu, pipeline-parallelism, zero, llm-training]
source_pdf: "[[26657d5ff9020d2abefe558796b99584.pdf]]"
source_md: "[[26657d5ff9020d2abefe558796b99584]]"
---

# Zorse: Optimizing LLM Training Efficiency on Heterogeneous GPU Clusters (MLSys 2026)

> **一句话总结**：Pipeline-Efficient ZeRO DP 用 interleaved ministage + CPU offload 同时压低 PP+ZeRO-3 的通信和 PP+ZeRO-2 的显存，planner 自动搜配置，在 128 GPU 异构集群上训练吞吐最高 **3×** 于 HexiScale/Cephalo/TorchTitan-Het。

## 问题

组织往往只能凑出 **异构 GPU 集群**（不同代际、跨 region、带宽差 35×），但现有 3D 并行框架假设同构。PP 跨慢链路、DP 组内要快链路——组合 ZeRO 与 PP 有经典 trade-off：PP+ZeRO-2 通信省但显存爆（大模型 OOM）；PP+ZeRO-3 显存省但每个 microbatch 每层 AllGather，通信爆炸；加 [[Tensor-Parallelism]] 又吃带宽。需要同时处理算力、显存、网络三重异构。

## 核心方法

**Zorse** 提出 **Pipeline-Efficient ZeRO DP**：

- 每张 GPU 挂多个 **ministage**（非传统 1F1B interleaving），按 ministage 顺序跑完所有 microbatch 的 forward/backward，再切下一个 ministage；任意时刻 GPU 上只保留当前+下一个 ministage 参数（显存接近 ZeRO-3），通信仍是每层一次 AllGather（接近 ZeRO-2）。
- **Interleaved optimizer update**：每个 ministage backward 完立刻更新并释放 gradient，降峰值显存、overlap 梯度同步。
- **Activation checkpointing + CPU offload**：层边界 activation 也 offload，prefetch 隐藏 PCIe。
- **Heterogeneous PP**：stage 间 GPU 数量/型号可不对称；microbatch 按各 GPU 剩余算力重分配，跨 stage many-to-many 通信用 NCCL+GLOO 混合避免死锁。

**Planner** 两阶段：Phase 1 用 min-k cut（SPLIT 近似）按带宽把集群切成 k 个 DP 组；Phase 2 枚举 batch/ministage 配置，用 latency+memory 模型选最优。

基于 PyTorch FSDP 实现，开源。

## 关键结果

- 三类代表集群（4H100+16A100 / 8A100+16A10G+16V100+24T4 / 双 region 128 GPU）：相对 TorchTitan-Het、HexiScale、Cephalo 吞吐最高 **3×**（Cluster B 上 1.5–4×）。
- 大模型（65B）在异构集群上避免 OOM，HFU 接近同构子集群训练效率。
- 加更快 GPU 进训练组：吞吐随集群扩大而升，HFU 基本稳定或提升。
- ministage 数增加：显存降、吞吐在 sweet spot 附近平衡 PP+ZeRO-2 与 PP+ZeRO-3。

## 相关

- **相关概念**：[[Pipeline-Parallelism]]、[[Tensor-Parallelism]]、ZeRO、FSDP
- **同类系统**：HexiScale、Metis、Cephalo、Megatron-LM、TorchTitan
- **同会议**：[[MLSys-2026]]、[[HexiScale-MLSys26]]