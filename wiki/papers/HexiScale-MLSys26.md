---
type: paper
name: HexiScale
full_title: "HexiScale: Accommodating Large Language Model Training over Heterogeneous Environment"
authors: [Ran Yan, Fangcheng Fu, Youhe Jiang, Xiaonan Nie, Bin Cui, "et al."]
venue: MLSys
year: 2026
tags: [heterogeneous-training, llm-training, parallelism, graph-partitioning, asymmetric]
source_pdf: "[[9a1158154dfa42caddbd0694a4e9bdc8.pdf]]"
source_md: "[[9a1158154dfa42caddbd0694a4e9bdc8]]"
---

# HexiScale: Accommodating Large Language Model Training over Heterogeneous Environment (MLSys 2026)

> **一句话总结**：支持全 asymmetric 的 data/tensor/pipeline 三维并行（每条 pipeline 可以有不同 batch size / TP degree / 层数）再用分层 graph partition 求调度，在异构 GPU 集群（A800+4090+3090 混合）上训练 7-30B LLM 达到与同构高端 GPU 相同 peak FLOPS 集群相当的 MFU（平均差 3.5%，最小 0.3%），比 Metis 最高快 1.9×。

## 问题

LLM 训练极耗算力（数千 GPU 跑数月），同构高端 GPU 集群成本高企。但全球数据中心里各代 GPU（Turing/Ampere/Hopper/Blackwell，K80 到 H100）并存，**把 LLM 训练部署到异构 GPU 上**能显著降本、扩大可用算力。

但现有训练系统（[[Megatron]]、[[DeepSpeed]]、Galvatron、FSDP）**只支持 symmetric 切分**：所有 TP group 同 degree、PP group 同 degree、DP group 同 degree——所有 GPU 承担同等 workload。这在异构场景下两个硬伤：

1. 强 GPU 被当弱 GPU 用（被 bottleneck 拖累）
2. 并行策略被网络限制（如跨机 TP 在 1Gbps Ethernet 上延迟爆炸）

**Case study**（Llama-2-13B，A800×3 + 4090×3 + 3090×2，不同带宽）：Megatron 的最优对称方案 iteration 41.52s；HexiScale 非对称方案 25.55s，快 **1.6×**。

## 核心方法

**1. Fully asymmetric parallelism（系统支持）**：

- **Asymmetric pipeline**：每条 pipeline 可以有不同 batch size、不同 TP degree、不同层数
- **Asymmetric gradient sync**：不同 pipeline 的同一层因 TP degree 不同，gradient chunk 大小不同。方法：以最小 chunk 为单位切分大 chunk，然后各子集 GPU 组独立做 allreduce，不增加 comm 开销
- **Per-stage leader GPU**：每 pipeline stage 选一个 leader（与相邻 stage 通信延迟最小的），forward 时 leader 收到 activation 后在 TP group 内 broadcast
- 基于 FlashAttention-2 + FSDP custom hook 实现，支持 gradient accumulation + activation recompute

**2. 调度问题形式化**：

$$\sigma^* = \arg\min_\sigma [\text{Comm-Cost}(\sigma) + \text{Comp-Cost}(\sigma)]$$ s.t. $\text{Mem-Cumsum}(d) \leq m_d$

NP-hard（candidate allocation 指数级）。

**3. 两阶段分层 graph partitioning**：

**Phase 1：GPU 分组成 pipeline**（全局 graph $G=(D,E)$，顶点权重 = 算力 $c_d$，边权重 = 带宽 $\beta_{d,d'}$）：
- (i) **Coarsen**：Heavy Edge Matching (HEM)，把高带宽相连的 GPU 合并
- (ii) **Partition**：$D_{dp}$-way 递归二分，最小化 Cut（被切断的边权重和），约束 balance factor（顶点权重均衡）
- (iii) **Project**：反推到原图
- (iv) **Refine**：Kernighan-Lin 局部调整

**Phase 2：pipeline 内布局**（对每个 pipeline 用的 GPU 子集 $D_i$）：
- (i) **Group for stages**：子图 $G_i$ 再次做 multi-level graph partition 分成 $k_i$ 个组
- (ii) **Construct stages**：每组内用 cost model 搜索本地最优 TP/PP 策略（机内 parallelism）
- (iii) **Stage order**：top-$\tau$ greedy 搜索——把每组视为一个顶点，从不同起点按 inter-group bandwidth 最大的邻居走 pipeline path

**4. Iterative optimization**：
- 迭代 $D_{dp}$（pipeline 数）
- 自适应选择：**maximize inter-group bandwidth**（高 DP 带宽，适合 pipeline 少/batch 小时）vs **minimize inter-group bandwidth**（低 DP 带宽，适合 pipeline 多/batch 大时）。根据历史移动平均 cost 选择
- 迭代 $k_i$（每 pipeline 内组数）
- Cost model 包括 compute、comm、memory、network latency $\alpha_{d,d'}$（大量 micro-batch 下 NCCL 链路成本不可忽略），simulator 误差 < 2%

## 关键结果

- Llama-2 7B/13B + Llama 30B 多模型规模
- vs 同构高端 GPU + SOTA 系统（Megatron、Galvatron、FSDP）同等 peak FLOPS 下：
  - **MFU gap 平均 3.5%，最小 0.3%**——异构集群接近同构集群性能
- vs SOTA 异构训练系统 [[Metis]]：**最高 1.9× MFU**
- Simulator 偏差 < 2%

**意义**：降低 LLM 训练门槛，让老 GPU 和消费级 GPU（3090/4090）有机会参与大模型训练，为跨地区、跨代 GPU 的去中心化训练铺路。

## 相关

- **相关概念**：[[Tensor-Parallelism]]、[[Pipeline-Parallelism]]、Data-Parallelism、FSDP、Graph-Partitioning、ZeRO
- **同类系统**：[[Megatron]]、[[DeepSpeed]]、Galvatron、Metis、Alpa、Whale、SDPipe、FlashAttention-2
- **同会议**：[[MLSys-2026]]
