---
type: entity
kind: tool
aliases: [torch, PyTorch-Framework]
status: active
last_updated: 2026-07-30
tags: [machine-learning, training, compiler, runtime]
---

# PyTorch

> PyTorch 是本 wiki 中训练、推理、自动微分、分布式 tensor 与自定义 GPU kernel 的共同编程面；论文常保留其 API，却重写下层执行、内存或验证路径。

## 是什么

PyTorch 将 eager tensor program、autograd、module/state dict、allocator、distributed collective 和 compiler/runtime 连接起来。它的重要性不只在易用性，而在于系统方案若能兼容 PyTorch，便可进入现有模型、checkpoint 与工程 workflow。

同一个“兼容 PyTorch”可能只覆盖 Python API、operator semantics、checkpoint format 或 distributed contract 的一部分。版本、backend、dynamic shape、custom op 和 graph break 都会改变结果，不能把单项兼容等同于完整 drop-in replacement。

## 关键观察 / 隐含假设

- **高层 tensor 语义会隐藏低层 data movement**：[[VTC-OSDI26]] 用 virtual tensor 消除 reshape/transpose materialization；[[Umap-OSDI26]] 则表明 data-parallel matrix access 需要显式 remote block/cache semantics。
- **框架默认执行并非天然适合 CUDA Graph**：[[GraCE-OSDI26]] 发现一个 CPU tensor 即可阻止数百 kernels capture，并用 compiler transformation 稳定 pointer 与 graph state。
- **privacy/correctness 扩展会穿透框架层**：[[Cocoon-OSDI26]] 在 PyTorch 训练路径管理 correlated-noise history；[[TrainCheck-OSDI25]]、[[FPRev-ATC25]] 通过 framework hook 检查训练行为。
- **可编程性与 specialization 存在张力**：[[MPK-OSDI26]]、[[TritorX-MLSys26]]、[[PyLO-MLSys26]] 通过编译或 kernel DSL 获得性能，但依赖固定 shape/configuration 与额外编译成本。

## 演进时间线

- 2025 OSDI：[[TrainCheck-OSDI25]] — 在 PyTorch training stack 内加入在线正确性检查。
- 2025 ATC：[[VTC-OSDI26|VTC]] 的前序系统生态由 [[SAVE-ATC25]]、[[FPRev-ATC25]] 展示 framework-level memory/verification hook。
- 2026 MLSys：[[TritorX-MLSys26]]、[[PyLO-MLSys26]]、[[Flashlight-MLSys26]] — 分别扩展 operator、layout 与调试/性能分析能力。
- 2026 OSDI：[[GraCE-OSDI26]] — 用 compiler support 扩大 PyTorch CUDA Graph capture coverage。
- 2026 OSDI：[[VTC-OSDI26]]、[[Cocoon-OSDI26]] — 分别把 virtual data movement 与 differential-private correlated noise 融入 DNN execution。

## 相关概念

- [[Automatic-Differentiation]]、[[CUDA-Graph]]、[[Tensor-Compiler]]、[[Data-Parallelism]]、[[GPU-Kernel]]

## 相关论文

- [[GraCE-OSDI26]] — 自动修复 data placement、mutable parameter 和 RNG 等 CUDA Graph 障碍。
- [[VTC-OSDI26]] — 以 virtual tensor mapping 延迟或消除 physical data movement。
- [[Cocoon-OSDI26]] — 在 DP training 中管理超大 correlated-noise history。
- [[MPK-OSDI26]] — 将 PyTorch tensor program 编译成 persistent mega-kernel。
- [[WAVE-MLSys26]] — 在 PyTorch workload 上重构执行/调度边界。
- [[TrainCheck-OSDI25]] — 面向生产训练的 framework-integrated validation。
