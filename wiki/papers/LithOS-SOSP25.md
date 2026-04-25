---
type: paper
name: LithOS
full_title: "LithOS: An Operating System for Efficient Machine Learning on GPUs"
authors: [Patrick H. Coppock, Brian Zhang, Eliot H. Solomon, Vasilis Kypriotis, Leon Yang, et al.]
venue: SOSP
year: 2025
tags: [gpu, ml-systems, scheduling, multitenancy, power-management]
source_pdf: "[[3731569.3764818.pdf]]"
source_md: "[[3731569.3764818]]"
---

# LithOS: An Operating System for Efficient Machine Learning on GPUs (SOSP 2025)

> **一句话总结**：以 OS 视角重构 GPU 资源管理——在 TPC 粒度做时空调度 + 透明地把 kernel 拆成 atoms + 动态 right-sizing + 细粒度功耗管理；与 MPS 相比 inference stacking 尾延迟降 13×、hybrid inference-training 尾延迟降 4.7×，同时 ~25% GPU 容量或能耗节省。

## 问题

GPU 在数据中心利用率普遍很低：Microsoft 52%、Alibaba 10%、Meta inference service 常 <30%、Llama 3 训练也只 ~40%。Dedicated 部署浪费大，但现有共享方案都不够：

- **MPS / MIG**：粒度粗到整张 GPU 或 GPC，MIG 重配置 >5s
- **软件 cooperative multitenancy**：绑死框架版本、需要 kernel 源码修改，不透明
- **temporal 方案**（如 Clockwork、Clipper、TGS）：一次只跑一个任务，不能并行
- 空间方案（REEF、Orion 等）仍在 inference request / kernel 粒度，有严重 HoL blocking

## 核心方法

LithOS 把 GPU 调度从 proprietary driver/hardware 拉回软件层，用 Rust 实现，对 ML 栈完全透明。四个关键机制：

- **TPC Scheduler**：在 Texture Processing Cluster 粒度做时空调度（H100 上 72 TPC），配合 online kernel latency predictor 和 **TPC Stealing**（idle 的 TPC 临时借给别的任务），比 MPS/MIG 细很多
- **Kernel Atomizer**：不改编译器/runtime/PTX，透明地把一个 kernel 拆成若干 **atoms**（thread block 子集），每个 atom 独立调度；解决无硬件抢占下的 HoL blocking、支持执行中途重配 TPC
- **Hardware Right-sizing**：用轻量模型预测每个 kernel/atom 实际需要的最小 TPC 数，空出来的 TPC 还给别人
- **细粒度 Power Management**：根据 in-flight work 的特征动态调 GPU 频率

## 关键结果

- Inference stacking：尾延迟比 MPS 降 **13×**，比 best SotA 降 **4×**，aggregate goodput 提升 1.3×
- Hybrid inference + training stacking：尾延迟比 MPS 降 **4.7×**，比 best SotA 降 1.18×，aggregate throughput 提升 1.35×
- Right-sizing：<4% 性能损失换 **~25% GPU 容量节省**
- Power management：7% 性能损失换 **~25% 能耗节省**

## 相关

- **相关概念**：GPU scheduling、Spatial multiplexing、DVFS
- **同类系统**：REEF、Orion、MuxFlow、TGS、Clockwork
- **同会议**：[[SOSP-2025]]
