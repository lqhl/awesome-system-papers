---
type: paper
name: DP-ZeRO
full_title: "ZERO REDUNDANCY DISTRIBUTED LEARNING WITH DIFFERENTIAL PRIVACY"
authors: [Zhiqi Bu, Ruixuan Liu, Justin Chiu, Sheng Zha, George Karypis]
venue: MLSys
year: 2026
tags: [differential-privacy, zero, distributed-training, large-models]
source_pdf: "[[da4fb5c6e93e74d3df8527599fa62642.pdf]]"
source_md: "[[da4fb5c6e93e74d3df8527599fa62642]]"
---

# ZERO REDUNDANCY DISTRIBUTED LEARNING WITH DIFFERENTIAL PRIVACY (MLSys 2026)

> **一句话总结**：[[DP]] 分布式训练长期困于 [[DDP]] 内存与 [[Pipeline-Parallel]] bubble，而 [[ZeRO]]/混合精度未与 DP 结合；DP-ZeRO 在不变 DP 数学前提下对接 ZeRO1/2/3 + Book-Keeping [[GhostClip]]，首次 DP 训练 **GPT-100B** 级可训参数，通信/计算效率对齐标准 ZeRO，混合精度显存约 **减半**。

## 问题与动机

大模型 + [[Differential-Privacy]]（per-sample clip + noise）在单卡上 BK/GhostClip 已接近非私有开销（ViT-Large **1.08×** 时间），但 **DDP** 无法装下超大模型且缓存 per-sample gradient 贵；**PipeP** + DP 有 pipeline bubble。业界需要与 [[DeepSpeed]]/[[FSDP]] 同级的 DP 分布式方案以训练十亿级可训参数（GPT2-XL、ViT-10B、GPT-100B 等）。

## 关键观察 / 隐含假设

- **观察 1：DP 的数学梯度分组（all-layer vs layer-wise clip）与 ZeRO 的物理分片可分离组合，细粒度 clip 更省内存。**
  - **依赖假设**：各 group clip 的 noise 与 accounting 仍正确。
  - **可能失效场景**：极端 layer-wise 分组与 ZeRO3 通信模式交互未充分边界测试。

- **观察 2：混合精度 DP 的 loss scaling 与 master weight 更新需专门处理，否则 ZeRO 的 fp16 grad + fp32 state 路径破坏 DP 正确性。**
  - **依赖假设**：修复后数值稳定与 non-DP ZeRO 等价。
  - **可能失效场景**：更大模型/更低 precision 数值漂移需额外验证。

- **观察 3：DP-ZeRO 可达数百 GPU 扩展，通信量与标准 ZeRO 同级。**
  - **依赖假设**：per-sample norm 计算用 mixed ghost norm 避免第二遍 backward。
  - **可能失效场景**：极大 micro-batch 时 clip 统计方差与 privacy budget 权衡仍由用户负责。

- **假设 1**：一行代码接入 DeepSpeed/FSDP 可覆盖一般任务/架构。**
  - **证据强度**：**中**——承诺开源；Table 1 对比全面但生产长尾算子未穷尽。

## 核心方法

**DP-ZeRO**：在 ZeRO 三阶段 partition（optimizer state / grad / params）各阶段插入 DP clip+noise；利用 BK：mixed ghost norm + 单次 backward book-keeping。

**Mixed-precision DP**：解决 loss scaling，使 fp16/bf16 训练通信减半。

**Scale**：首次 DP 全参微调 **>1B**（GPT2-XL、ViT-G、GPT-100B 等 Figure 1）。

## 设计取舍

- **ZeRO3 vs ZeRO1/2**：更低内存更高通信；DP 噪声与分片顺序需小心。
- **PipeP+DP vs DP-ZeRO**：避开 bubble，但需 ZeRO 生态成熟。
- **Privacy vs accuracy**：更大模型更好 DP accuracy 但算力贵——论文不解决 budget 选择。
- **边界条件**：AWS 作者；classification/NLU 任务为主。

## 实验与结果

- 效率：与标准 ZeRO 同级通信/计算（claim）。
- 内存：混合精度约 **50%** 降 vs 非混合 DP 分布式。
- 规模：GPT-100B 等红字 surpass 既有 DP 模型规模图（Figure 1）。
- 对比 Table 1：优于 DDP+DP、PipeP+DP 等组合。

## Critical Analysis

### 论证链条

DP 单卡已高效 → 瓶颈在分布式分片 → 将 BK 嵌入 ZeRO 各 stage → 首次 billion-scale DP，逻辑清晰。GPT-100B 的 **utility**（下游精度）相对 non-DP 外推需读全文数字。

### 假设压力测试

LLM generative DP（大词汇 softmax clip）成本仍高；ZeRO+EP+DP 未谈。多租户 GPU 上 side-channel 与 DP 正交。

### 实验可信度

系统论文+规模里程碑；baseline 表格完整。缺：与最新 Opacus/FSDP-DP 公开栈长期维护对比。

### 系统性缺陷

论文未讨论 privacy accounting 自动化运维、checkpoint 泄露、failure recovery 对 DP 保证影响。

## 局限与 Future Work

- **局限 1**：极大 generative 模型 DP utility 与 ε 权衡仍难。
- **局限 2**：与 MoE/EP 组合复杂度未展开。
- **Future work 1**：DP+[[FSDP]]2+[[Context-Parallel]] 全栈 profiling。
- **Future work 2**：生产级 privacy dashboard  tied to DP-ZeRO steps。

## 相关

- **相关概念**：[[Differential-Privacy]]、[[ZeRO]]、[[FSDP]]、[[GhostClip]]
- **同类系统**：Opacus、TensorFlow Privacy
- **同会议**：[[MLSys-2026]]