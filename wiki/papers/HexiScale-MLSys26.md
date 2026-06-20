---
type: paper
name: HexiScale
full_title: "HexiScale: Accommodating Large Language Model Training over Heterogeneous Environment"
authors: [Ran Yan, Fangcheng Fu, Youhe Jiang, Bin Cui, Xiaonan Nie, Binhang Yuan]
venue: MLSys
year: 2026
tags: [llm-training, heterogeneous-gpus, scheduling, pipeline-parallel, mfU]
source_pdf: "[[9a1158154dfa42caddbd0694a4e9bdc8.pdf]]"
source_md: "[[9a1158154dfa42caddbd0694a4e9bdc8]]"
---

# HexiScale: Accommodating Large Language Model Training over Heterogeneous Environment (MLSys 2026)

> **一句话总结**：Megatron 等对称 DP/TP/PP 在 3080+4090+A800 混合集群上无法匹配各卡 FLOPs/带宽/显存，HexiScale 支持**非对称** pipeline（每 stage 不同 TP 度与层数、不同 microbatch）+ 分块梯度同步，两阶段图划分调度；同总峰值 FLOPs 下 MFU 与同质 A800 差距均值仅 **3.5%**（最低 **0.3%**），较 Metis 最高 **1.9×** MFU。

## 问题与动机

[[LLM]] 训练常假设同质 GPU 集群，但云与边缘存在多年代卡混部（K80 至 Hopper）。对称并行要求各 TP/PP/DP 组度一致，强卡降速、弱卡 straggle，显存与带宽浪费。

案例（Llama-2 13B，3×A800 + 3×4090 + 2×3090）：Megatron 最优 plan 仍 **41.52s/iter**（bubble **>22%**、跨机 TP 通信 **1.88s/layer**）；HexiScale 非对称布局 **25.55s（1.6×）**。

## 关键观察 / 隐含假设

- **观察 1：异构环境下「均衡 FLOPs」与「均衡显存」不可同时满足**（Σl 与 Σl² 双约束），对称策略必偏一侧。
  - **依赖假设**：成本模型可解析估计 per-layer comp/comm；FlashAttention-2 + activation recompute 启用。
  - **可能失效场景**：MoE expert 并行、异构 not 仅 FLOPs/带宽差异还有数值格式/驱动差异时模型需额外处理。

- **观察 2：pipeline stage 间带宽差异大时，stage **顺序排列**与每 pipeline 不同 batch size 可平衡端到端时间。** 案例 pipeline-1 大 batch 使两 pipeline 运行时间差 **7%** 尽管 batch 差 **40%**。
  - **依赖假设**：跨 pipeline DP 梯度块可对齐最小 chunk 做子集 AllReduce，不增通信量。
  - **可能失效场景**：极大模型下自定义 FSDP hook 与 ZeRO-3 交互复杂度上升。

- **假设 1：两阶段 multilevel graph partition + 迭代枚举 n_pipeline、带宽 Cut 最大化/最小化可逼近最优并行计划，模拟误差 **<2%**。**
  - **证据强度**：**强**——Table 3 模拟 vs 实测；50 轮收敛，64–320 GPU 调度 **<2min**。

## 核心方法

**非对称并行**：每 pipeline 独立 TP 度、层分配、global/micro batch；leader GPU 跨 stage 传 activation 再 TP broadcast。

**非对称梯度同步**：找最小梯度块，较大梯度切块后在 DP 子集同步。

**调度**：Phase1 全局图划分 → n_pipeline 个 GPU 组；Phase2 组内再划分 → 构造 stage + top-k greedy 定 stage 顺序；迭代优化 n_pipeline、n_sub、Cut 方向（偏 DP 或 PP 带宽）。

实现：FlashAttention-2 TP 层 + 自定义 asymmetric PP + FSDP communication hooks。

## 设计取舍

- **全不对称 vs Metis 部分灵活**：搜索空间更大，实现复杂，但 MFU **最高 1.9×** Metis（§5.4）。

- **Ethernet 跨机（~0.7GB/s）实验 vs 同质 RDMA baseline**：公平对比用同质 Ethernet；HexiScale 同质 RDMA 可与 Megatron 持平。

- **启发式调度 vs ILP**：NP-hard 问题用图划分+贪心，无最优保证但可扩展 320 GPU。

- **边界条件**：Llama-2 7B/13B、Llama 30B；UCloud 租赁异构机；未覆盖长 context 训练。

## 实验与结果

- **MFU vs 同质 A800（同总 FLOPs）**：gap 平均 **3.5%**，最低 **0.3%**（三档异构设置）。
- **vs Megatron/Galvatron 异构**：最高 **2.5×** MFU，平均 **2.1×**；Megatron 30B setting3 OOM。
- **vs Metis**：最高 **1.9×** MFU。
- **Ablation**：去非对称并行平均慢 **15%**（最高 23%）；去 GA 平均慢 **12%**。
- **调度器**：较随机图划分 MFU 高约 **8%**（7B）、**23%**（30B）。

## Critical Analysis

### 论证链条

案例研究定性地展示对称法失败模式 → 非对称系统设计 → 多规模 MFU 近同质 → Metis 对比，论证充分。「民主化训练」claim 依赖云碎片化 GPU 供给假设，经济性与可用性论文未量化。

### 假设压力测试

- **已证明**：三档真实租赁异构集群；模拟器 <2% 偏差。
- **可能失效**：WAN 极不稳定时 DP 同步频率敏感；多租户云 GPU 性能抖动未建模。
- **未覆盖**：与 [[DistCA-MLSys26]] 长 context attention 解耦正交但未集成。

### 实验可信度

同质 baseline 用 Megatron/Galvatron/FSDP grid search；异构互联 **0.7GB/s** 偏慢，有利凸显调度但仍诚实对比 Ethernet 同质。MFU 定义标准。

### 系统性缺陷

故障恢复、弹性扩缩容论文未讨论；非对称调试与 checkpoint 兼容性成本高；跨组织 federated 异构训练安全未涉及。

## 局限与 Future Work

- **局限 1**：实验以 Llama 系为主，MoE/多模态架构未验证。
- **局限 2**：依赖离线调度器模拟，运行时 workload 变化需重搜计划。
- **Future work 1**：与 spot/preemptible GPU 供给联合优化迭代级 re-scheduling。
- **Future work 2**：measurement 对比 HexiScale vs 同质烂集群（慢网）的 TCO break-even。

## 相关

- **相关概念**：[[Pipeline-Parallelism|Pipeline-Parallel]]、[[Tensor-Parallelism|Tensor-Parallel]]、[[Data-Parallelism|Data-Parallel]]
- **同类系统**：Megatron-LM、Galvatron、Metis
- **同会议**：[[MLSys-2026]]
- **对比**：[[DistCA-MLSys26]]