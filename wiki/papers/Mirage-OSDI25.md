---
type: paper
name: Mirage
full_title: "Mirage: A Multi-Level Superoptimizer for Tensor Programs"
authors: [Mengdi Wu, Xinhao Cheng, Shengyu Liu, Chunan Shi, Jianan Ji, et al.]
venue: OSDI
year: 2025
tags: [gpu, superoptimizer, tensor-compiler, cuda, dnn-kernels]
source_pdf: "[[osdi25-wu-mengdi.pdf]]"
source_md: "[[osdi25-wu-mengdi]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-30
---

# Mirage：张量程序的多级超级优化器（OSDI 2025）

> **原题**：Mirage: A Multi-Level Superoptimizer for Tensor Programs

> **一句话总结**：schedule-only（TVM/Ansor）与 kernel-only（TASO）优化器无法联合代数+调度+自定义 kernel；Mirage 用 µGraph 统一 kernel/block/thread 三层，抽象表达式剪枝 + LAX 上有限域概率等价验证，自动发现含 [[Flash-Attention|FlashAttention]] 类优化，A100/H100 上 **最高 3.3×** 于 SOTA，端到端 LLM **0.9–1.9×**。

## 问题与动机

DNN tensor program 优化需同时做代数变换、schedule 变换与发明新 kernel（如 FlashAttention 需 700+ 行 Triton）。Halide/TVM/Ansor 固定算法；TASO/PET 固定 kernel 库。跨 GPU 层次（device/shared/register）的联合搜索空间现有方法够不到。

## 关键观察 / 隐含假设

- **观察 1**：kernel+block 层访存代价主导 thread 层，可 block/thread 混合搜索（block 穷举小图 + thread 规则生成）。
  - **依赖假设**：LAX fragment（matmul/conv/div/有限 exp）覆盖主流 DNN 子图。
  - **可能失效场景**：非 LAX 算子需切分，可能丢优化机会。
- **观察 2**：抽象表达式剪枝可在保证一定最优性前提下大幅缩搜索空间。
  - **证据强度**：中——有理论保证叙述，依赖 rank 等抽象精度。
- **假设 1**：LAX 程序等价性可用有限域随机测试 + PIT 推广，概率误差可任意小。
  - **可能失效场景**：浮点语义与有限域差异需部署前额外验证（论文针对 tensor 代数）。

## 核心方法

**µGraph**：kernel graph（device mem）→ block graph（shared mem，imap/omap/fmap，for-loop）→ thread graph（register）。

**生成**：expression-guided 穷举 kernel/block 候选 + abstract expression 剪枝。

**验证**：probabilistic equivalence（LAX PIT）。

**优化**：layout、执行序、内存规划后 codegen。

自动发现 FlashAttention/FlashDecoding 及 **2.2×** 更优变体；RMSNorm+MatMul 融合 **1.9×** 等。

## 设计取舍

- **取舍 1**：搜索可达数小时（RMSNorm 表 5），换部署前一次优化；非 interactive compile。
- **取舍 2**：graph-defined kernel 全局↔shared 搬运对轻算子可能亏（nTrans vs TensorRT）。
- **边界条件**：≤5 kernel ops、≤11 block ops（默认）；A100/H100。

## 实验与结果

- 六微基准（GQA、RMSNorm、LoRA 等）：相对最佳 baseline **最高 3.3×**。
- GQA：自动 grid 维度满 SM；device memory 访问最多 **7×** 减少。
- 端到端 Chameleon/LLaMA-3/LoRA/nGPT：**0.9–1.9×** latency。
- 搜索时间：单 LAX 程序最长 ~4 小时（一次性）。

## 批判性分析

### 论证链条

FlashAttention 手工案例 → µGraph 表达力 → 搜索+验证 → 微基准与 E2E 提升，论证充分。等价性为概率保证，生产需接受极低错误率或加回归测试。

### 假设压力测试

搜索空间仍随 op 数指数；更大子图可能不可行。与 cuBLAS/cuDNN 黑盒 kernel 的互操作边界需用户切 LAX。H100 FP8/新指令集扩展工作量未讨论。

### 实验可信度

Baseline 含 TensorRT-LLM、FlashAttention 等强对手；微基准代表 LLM building blocks。E2E 0.9× 个别模型说明并非全胜。

### 系统性缺陷

编译时间、调试可读性、失败时诊断；论文未讨论 multi-GPU 自动并行。

## 局限与后续工作

- **局限 1**：LAX 划分与浮点语义 gap。
- **Future work 1**：与 PyTorch 2 compile 路径的深度集成与缓存策略。
- **Future work 2**：更大子图（>11 block ops）的近似搜索与验证 tradeoff。

## 相关

- **相关概念**：[[Flash-Attention]]、[[Attention]]
- **同会议**：[[OSDI-2025]]
