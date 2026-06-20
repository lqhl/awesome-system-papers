---
type: paper
name: ProTrain
full_title: "ProTrain: Efficient LLM Training via Automatic Memory Management"
authors: [Hanmei Yang, Jin Zhou, Yao Fu, Xiaoqun Wang, Ramine Roane, Hui Guan, Tongping Liu]
venue: MLSys
year: 2026
tags: [llm-training, memory-management, zero, gradient-checkpointing, auto-tuning]
source_pdf: "[[a0a080f42e6f13b3a2df133f073095dd.pdf]]"
source_md: "[[a0a080f42e6f13b3a2df133f073095dd]]"
---

# ProTrain: Efficient LLM Training via Automatic Memory Management (MLSys 2026)

> **一句话总结**：DeepSpeed 等暴露 18+ 耦合 ZeRO/offload/checkpointing 旋钮，默认配置仅用 **35.6%** GPU 显存且慢 **1.18×**；ProTrain 将策略抽象为 chunk/block 级少量参数，用 memory-aware profiler（补 transient/unhookable 17.2% 峰值）建 <4% 误差代价模型并穷举搜索，在 GPT-2/OPT/Mistral/LLaMA 上吞吐 **1.43–2.71×**，可训练模型最大达 DeepSpeed **2.47×**、FSDP **7.5×**（单卡 A100）。

## 问题与动机

[[LLM]] 训练内存瓶颈主导：ZeRO、gradient checkpointing、tensor swapping 互斥或争用 PCIe 带宽，DeepSpeed 等需专家手工联调。换硬件（3090→A100）配置常 OOM 或利用率低。

## 关键观察 / 隐含假设

- **观察 1：层间 profiler 漏掉 transient tensor 与 nn.functional 等 unhookable op，10B GPT-2 batch16 峰值低估约 **17.2%（3.06GB）**，导致 OOM 与错误搜索。**
  - **依赖假设**：完整 execution trace + intra/inter-operator delta 可重构任意 {npersist, nswap, ncheckpoint} 下峰值。
  - **可能失效场景**：动态 control flow、自定义 CUDA op 未 hook 时仍可能漏计。

- **观察 2：activation swapping 与 parameter prefetch 争用 CPU–GPU 带宽；粗粒度「全 block checkpoint」或「全 swap」无法按层择优。**
  - **依赖假设**：transformer block 级策略空间足以覆盖最优解；交错 layout（Fig. 2）可降峰值。
  - **可能失效场景**：非 transformer 架构需重新定义 block；极长 sequence 下 block 数爆炸增大搜索。

- **观察 3：persistent vs non-persistent chunk 划分 + 执行序组织 chunk 可预测 overlap，使异步 swapping 的 runtime 可建模。**
  - **依赖假设**：训练 repeat 访问模式稳定；deterministic prefetch/eviction 序列。
  - **可能失效场景**：频繁 dynamic shape 破坏预分配 buffer 假设。

## 核心方法

**Structured memory strategies**：hierarchical chunk management（ZeRO+offload，persistent chunk 留 GPU、其余 offload，CPU 上更新与 GPU backward 重叠）；interleaved block management（每 block 选 swap/checkpoint/none）。

**Memory-aware profiler**：on-demand tensor 管理跑完整 trace；静态补 model state；activation 按执行序分析。

**Automatic memory management**：参数 {npersist, nbuffer, nswap, ncheckpoint}；单遍 profiling 建 runtime/peak memory 代价模型；按内存递增顺序穷举+剪枝。

PyTorch 实现 ~7600 LOC，wrap model/optimizer 即可。

## 设计取舍

- **穷举搜索 vs RL/黑盒**：可解释、<4% 预测误差，但搜索空间随 block 数增长。
- **ZeRO-3 数据并行基础 vs 3D 并行**：专注 DP 内存，未集成 PP/TP 全自动。
- **Block 粒度 vs tensor 粒度**：实现简单、搜索小，可能次优于细粒度。
- **边界条件**：4×3090 / 4×A100、seq 1024；更长 sequence 方法论声称可适配。

## 实验与结果

- 最大可训练模型：单卡 3090 上 34B vs DeepSpeed；4×A100 上 87B vs DeepSpeed 37B 等（Table 2）。
- 吞吐：3090 平均 **2090 tok/s**，**1.77–2.71×** vs DeepSpeed/Colossal-AI/FSDP；A100 上 **1.43–2.85×**。
- 10B GPT-2 扩展：4 卡 **3.5×** 单卡吞吐；代价模型误差 **<4%**。

## Critical Analysis

### 论证链条

「旋钮太多」→ 结构化抽象 + 精确 profiler + 约束优化，实验覆盖多模型/硬件，链条扎实。与 Megatron/FSDP 混合并行结合是未证跳步。

### 假设压力测试

MoE、流水线并行下 chunk 语义变化；NVLink 集群 offload 价值下降；profiler 单次采样能否代表 warmup 后稳定态需验证。

### 实验可信度

强 baseline 调参；多架构。缺用户真实 training trace（多模态、可变 seq）与多节点 scale-out。

### 系统性缺陷

搜索在超大模型上 CPU 时间；故障恢复、checkpoint 与 swapping 交互论文未讨论。

## 局限与 Future Work

- **局限**：seq 1024 受控对比；3D 并行未全自动；非 Transformer 需重定义策略。
- **Future work**：与 parallel strategy 联合搜索；在线 profiler 刷新；MoE expert 内存异构策略。

## 相关

- **相关概念**：[[ZeRO]]、[[Gradient-Checkpointing]]
- **同类系统**：[[DeepSpeed]]、Colossal-AI、[[FSDP]]
- **同会议**：[[MLSys-2026]]