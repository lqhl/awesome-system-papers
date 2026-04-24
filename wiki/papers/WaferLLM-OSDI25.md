---
type: paper
name: WaferLLM
full_title: "WaferLLM: Large Language Model Inference at Wafer Scale"
authors: [Congjie He, Yeqi Huang, Pei Mu, Ziming Miao, Jilong Xue, et al.]
venue: OSDI
year: 2025
tags: [llm-inference, wafer-scale, accelerator, gemm, distributed-memory]
source_pdf: "[[osdi25-he.pdf]]"
source_md: "[[osdi25-he]]"
---

# WaferLLM: Large Language Model Inference at Wafer Scale (OSDI 2025)

> **一句话总结**：首个 wafer-scale LLM 推理系统，提出 PLMR 硬件模型和配套的 MeshGEMM/MeshGEMV/shift-KV-cache 算法，在 Cerebras WSE-2 上把 GEMV 跑到 A100 的 606× 快、端到端 LLM 推理比 [[SGLang]]/[[vLLM]] 多卡 A100 快 10-20×。

## 问题

LLM 推理是 memory-bandwidth bound：weights 反复从 HBM 读入，decode 阶段的 GEMV 尤其吃带宽。Wafer-scale 加速器（Cerebras WSE-2 集成 85 万核、40 GB 片上 SRAM、22 PB/s 带宽）通过 system-on-wafer 把整个模型塞进片上，理论上能消除 HBM 瓶颈。但现有 LLM 系统（vLLM、SGLang）是为 shared-memory GPU 设计的，wafer-scale 是百万核 + distributed on-chip memory + mesh NoC 架构，两类系统放上去性能极差：T10（针对 GraphCore IPU 的 crossbar 架构）和 Ladder（针对 shared memory）都在 wafer 上 scale 不起来，原因是 mesh 架构下远近核之间访存延迟差可达 1000×，每核 local memory 仅 tens KB-几 MB，硬件路由表只能支持 25 条路径左右。

## 核心方法

论文首先抽象出 wafer 硬件的 PLMR 模型：**P**arallelism（百万核，需细粒度切分）、非均匀访存 **L**atency（mesh 上 hop+routing 延迟，α 近距、β 远距路由）、每核 **M**emory 受限、**R**outing 表项受限。任何 wafer-scale 算法必须四项全满足。

基于 PLMR，WaferLLM 重做了 LLM 推理栈：

(1) **并行策略**：prefill 沿 X/Y 双轴切分 activation 和 weights，实现 million-core 并行；decode 因 seq=1 改为 fine-grained replication，沿 y 轴 partition E、沿 x 轴 replicate L；预先转置权重消除 decode 时的 matrix transpose（transpose 在 mesh 上要跨对角线通信，代价极大）。

(2) **MeshGEMM**：用 cyclic shifting + INTERLEAVE 算法，每核只跟两个 "two-hop away" 邻居通信，critical path 常数 2-hop（对比 Allgather/SUMMA 的 $O(N)$ hop、Cannon 的 $O(αN)$），每核内存 $O(1/N^2)$、routing 路径 $O(1)$，理论证明该 2-hop 距离不可再缩短。

(3) **MeshGEMV**：针对 decode 阶段短计算、通信敏感的特点，用 K-tree allreduce 做 local GEMV 聚合，bounding routing resource。

(4) **Shift-based KV cache**：传统 concat 方式会让某一行核持续写入新 KV 导致 skew，WaferLLM 每生成一个 token 就把最旧 KV 行向上 shift，让 KV 均匀分布，满足 M 和 P；充分利用 NoC 并行。

实现约 7000 行 CSL + 2000 行 Python，在 Cerebras WSE-2 跑 LLaMA3-8B/LLaMA2-13B 完整模型，以及 CodeLLaMA-34B/QWen2-72B 的部分层。

## 关键结果

- MeshGEMM 比 SUMMA（Cerebras 默认）和 Cannon（超算默认）快 2-3×
- MeshGEMV 比 Cerebras 自家优化版快 4-8×，比单张 A100 上的 GEMV 快 606×，能效比高 16×
- Shift KV cache 比 GPU 上的 [[PagedAttention]] scalability 高 400×
- 端到端 LLM 推理：比 SGLang on single A100 快 30-40×；比 SGLang on multi-GPU A100+NVLink+RDMA 最优配置快 10-20×，能效 2.5×
- 比 T10（SOTA distributed on-chip memory 编译器）快 100-200×，比 Ladder（SOTA shared-memory 编译器）快 200-400×

## 相关

- **相关概念**：[[PagedAttention]]、[[KV-Cache]]、[[Tensor-Parallelism]]、[[Attention]]
- **同类系统**：[[vLLM]]、[[SGLang]]（作为 GPU baseline）
- **同会议**：[[OSDI-2025]]
