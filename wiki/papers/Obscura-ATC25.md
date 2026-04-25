---
type: paper
name: Obscura
full_title: "Obscura: Concealing Recomputation Overhead in Training of Large Language Models with Bubble-filling Pipeline Transformation"
authors: [Yuzhou Huang, Yapeng Jiang, Zicong Hong, Wuhui Chen, Bin Wang, et al.]
venue: ATC
year: 2025
tags: [llm-training, pipeline-parallelism, recomputation, memory-optimization, swapping]
source_pdf: "[[atc2025-huang-yuzhou.pdf]]"
source_md: "[[atc2025-huang-yuzhou]]"
---

# Obscura: Concealing Recomputation Overhead in Training of Large Language Models with Bubble-filling Pipeline Transformation (ATC 2025)

> **一句话总结**：通过 pipeline 变换把 forward bubbles 转成 backward bubbles 来掩盖重计算开销，结合依赖松弛 + 交换感知重计算 + 分区调整，在 13B-28B Llama-2/GPT-3 上吞吐提升最多 1.33×。

## 问题

[[Pipeline-Parallelism|1F1B pipeline]] 的早期 stage 内存压力大（stage 0 比 stage 7 多用 35GB），常用 recomputation（[[Activation-Checkpointing]]）来省内存但带来计算开销。已有工作要么对所有 stage 做 recomputation（开销线性叠加），要么仅对 cost-effective 算子做 selective recomputation（在严苛内存约束下仍需重算大量非 cost-effective 算子）。BPipe 用 inter-GPU swapping 缓解但后期 stage 备用内存不足、与重计算缺乏协同。

## 核心方法

三个关键观察：a) On-Demand Recomputation（只在内存超限的 stage 重算）比 All-Stage 更优；b) Backward Bubbles（首尾 backward 之间的气泡）能掩盖重计算开销；c) Forward Bubbles（首 forward 到首 backward 之间）从未被利用——因 recomputation 发生在 backward 阶段。

由此提出**把 forward bubbles 转成 backward bubbles**：在「adjusted stage」（超限 stage）中，把 steady 阶段的 forward pass 左迁到 forward bubbles 里，从而让原 forward bubbles 转换为可吸收重计算开销的 backward bubbles。Strawman pipeline 之后再加三件事：

- **Dependency Relaxation**：原相邻 stage 数据依赖紧——前 stage 的 backward 必须等后 stage 同 micro-batch 的 backward 完成，导致 backward bubbles 仍未充分使用。Obscura 改为左移剩余 forward 同时右移 backward 并交错（仿 1F1B），松弛 stage 间依赖让 bubbles 充分利用。
- **Swapping-Aware Recomputation**：把 activation swapping 与 recomputation 联合建模为带通信约束的 IP 优化问题，权衡重算成本与 PCIe 通信成本，求解最优重计算策略；引入 "CMB-Identifying" 在判定 OOM 前先尝试 cost-effective 重计算策略以减少 adjusted stage 数量。
- **Partition Adjustment**：通过把 transformer layer 拆成 attention 和 MLP 子层迁移，使 adjusted stage 少 layer、non-adjusted stage 多 layer，平衡两类 stage 的总计算时间。

基于 [[DeepSpeed]] 实现，自定义 scheduler 替换原生，NCCL 改异步并加同步原语；swapping 用独立 CUDA stream。深度细节回 [[atc2025-huang-yuzhou]]。

## 关键结果

- 8×A100-80G 单节点，Llama-2 18B/23B 提速 29-31%，28B 提速 22-27%（vs DAPPLE+ Full recomputation）
- GPT-3 用 GELU 比 SiLU 更 cost-effective，提速 30-33%
- 4×A800（无 NVLink）配置下相比 BPipe 跨 stage 通信开销低，仍有 27-31% 提升
- 23B 模型上 Obscura 计算时间仅比无重算的 DAPPLE 多 13%（DAPPLE+ 多 33%），bubble 时间在 adjusted stage 减少约 1.7s
- batch size 128 极端场景下，依赖松弛+SAR+CB 仍保持优势

## 相关

- **相关概念**：[[Pipeline-Parallelism]]、[[Activation-Checkpointing]]、[[1F1B]]、Swapping
- **同类系统**：DAPPLE、BPipe、OHP-CMB、GPipe、Megatron-LM
- **同会议**：[[ATC-2025]]
