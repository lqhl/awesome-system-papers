---
type: entity
kind: tool
aliases: [torch, PyTorch-Framework]
status: active
last_updated: 2026-08-18
tags: [machine-learning, training, compiler, runtime]
---

# PyTorch

> PyTorch 是本 wiki 中训练、推理、自动微分、分布式通信和自定义 GPU kernel 的共同编程面。OSDI 2026 的许多系统保留 PyTorch API，但重写了其下方的图捕获、内存、数据布局、通信或正确性路径。

## 是什么

PyTorch 把多层语义连在一起：Python/eager tensor program、module 与 state dict、autograd、allocator、compiler、CUDA runtime，以及 c10d/distributed collective。新系统若与其中一层兼容，就能复用现有模型与工程流程。

但“PyTorch compatible”至少有五种不同含义：Python API 可调用、operator 数值一致、autograd 可用、checkpoint 可互通、distributed contract 不变。论文实现通常只覆盖其中几项。版本、backend、dynamic shape、graph break、in-place alias 和 custom operator 都可能破坏剩余部分。

## 关键观察 / 隐含假设

- **高层 tensor 操作常隐藏纯数据搬运。** [[VTC-OSDI26]] 用“物理指针+索引映射”表示 transpose/split/scatter 后的 virtual tensor，只在有利时让后续 operator 读这个映射。它在 20 个模型组件 case 中相对每项最快 compiler 最高快 1.93 倍，平均 1.28 倍；评测不是完整模型 serving，也没有 multi-GPU 和训练。
- **框架图不会自然变成高质量 CUDA Graph。** [[GraCE-OSDI26]] 发现一个 CPU tensor、replay 期间的大参数拷贝，或一个本来就不值得 capture 的小 graph，都可抵消 kernel-launch 收益。它在 25 个固定 H100 workload 上相对 PyTorch2-CG 平均快 29%，但编译时间平均变成 2.21 倍，不能直接外推到动态在线 serving。
- **allocator 的“快速复用”与“可重映射”不是同一能力。** [[MoonBright-OSDI26]] 指出 PyTorch caching allocator 可避免频繁 driver allocation，但无法把分散 physical pages 重新拼成连续 VA；其 GPU page-table 和 fresh-VA 方案在特定 2 GB mapping microbenchmark 上将 36 ms 降到 14 μs。这个 2,500 多倍是低层 fresh mapping，不是通用 PyTorch 应用加速。
- **兼容现有 tensor/kernel 需要稳定的虚拟地址。** [[Prism-OSDI26]] 的 kvcached 为 SGLang 预留大块 VA，用 elastic tensor 按需映射物理页；它称接入 SGLang 只改 22 行，说明好的下层抽象可以保持 PyTorch/attention kernel 接口。这不代表系统容错、多租户隔离也只需 22 行。
- **分布式 API 是接入点，也是一致性表面。** [[Syncopate-OSDI26]] 保持 local operator 调用形式并可接 PyTorch distributed，但仍需上层给正确通信 plan；[[TrainMover-OSDI26]] 为增量替换 communicator 直接修改 c10d 和 NCCL。“接入 distributed”不等于弹性 membership 和 failure rollback 已自动解决。
- **调试需要主动收紧 PyTorch 的非确定性。** [[OpGuard-OSDI26]] 固定 CPU/CUDA RNG、dataloader、sampler、distributed initialization、cuDNN/cuBLAS 和 NCCL 选项；[[SDCHunter-OSDI26]] 还重写 deterministic reduction、MoE dispatch 与 collective order。这些系统表明，eager API 一样并不保证两次执行逐位相同。
- **隐私和可靠性机制会穿透整个框架。** [[Cocoon-OSDI26]] 在 PyTorch 2.4/fastDP 路径中管理相关噪声历史、CPU/CXL-NMP 数据移动和自定义 GEMV；[[AEGIS-OSDI26]] 则组合在线抽样与离线验证检测 SDC。两者都不是加一个 Python hook 就能完成。

## 设计空间与取舍

| 保留的层 | 可替换的实现 | 好处 | 主要风险 |
|---|---|---|---|
| Python/operator API | virtual tensor、custom kernel、external runtime | 现有模型易迁移 | alias、in-place、dynamic shape 语义可漏掉 |
| tensor address/shape | elastic VA、paged backing | 旧 kernel 可不改指针接口 | page mapping、TLB、生命周期错误下沉到 runtime |
| autograd/module boundary | verifier、fingerprint、privacy operator | 可看到模型语义 | compiler fusion/graph break 可让 boundary 消失 |
| distributed API | 新 chunk lowering、增量 communicator | 复用现有并行代码 | membership、ordering、failure 需要额外协议 |
| checkpoint/state dict | 自定义存储和迁移 | 与旧工作流程互通 | optimizer/RNG/layout 版本必须一起管理 |

## 演进时间线

- **2025**：[[TrainCheck-OSDI25]]、[[FPRev-ATC25]]、[[SAVE-ATC25]] 使用 framework hook 扩展训练检查与内存管理。
- **2026·MLSys**：[[TritorX-MLSys26]]、[[PyLO-MLSys26]]、[[Flashlight-MLSys26]]、[[WAVE-MLSys26]] 分别扩展 operator、layout、profiling 与执行调度边界。
- **2026·agent-native training**：[[PithTrain-arXiv26]] 用约 11 KLoC 的 Python-native PyTorch 控制面、`torch.compile(fullgraph=True)` 和外部 operator library 组成 MoE 训练栈；可读 traceback 降低了固定 coding agent 的调试成本，但底层仍依赖 NCCL、DeepGEMM、FlashAttention 与 Triton。
- **2025–2026 compiler / agent 对照**：[[Relax-ASPLOS25]] 将 PyTorch-style model 降到 cross-level AOT IR；[[VibeTensor-arXiv26]] 重建独立 PyTorch-style runtime；[[SOL-ExecBench-arXiv26]] 与 [[AdaExplore-arXiv26]] 则把 PyTorch reference 作为 kernel-agent 的 correctness/performance 起点，提醒 eager speedup 不是硬件效率上限。
- **2026·OSDI**：[[GraCE-OSDI26]]、[[VTC-OSDI26]]、[[MoonBright-OSDI26]]、[[Prism-OSDI26]] 把图捕获、数据搬运和虚拟内存下沉到 PyTorch 之下。
- **2026·OSDI**：[[OpGuard-OSDI26]]、[[SDCHunter-OSDI26]]、[[Cocoon-OSDI26]]、[[TrainMover-OSDI26]] 证明正确性、隐私与容错会同时跨越 framework、compiler、collective 和 hardware。

## 相关概念

- [[CUDA-Graph]]
- [[Data-Parallelism]]
- [[Tensor-Parallelism]]
- [[Pipeline-Parallelism]]
- [[Quantization]]

## 相关论文

- [[GraCE-OSDI26]] — 扩大 PyTorch CUDA Graph capture coverage，并逐 graph 判断是否值得 capture。
- [[VTC-OSDI26]] — 以 virtual tensor mapping 延后或消除物理数据搬运。
- [[MoonBright-OSDI26]] — 把 page-table construction 下沉到 GPU，解决 allocator 不能快速重映射的缺口。
- [[Prism-OSDI26]] — 用 elastic tensor 将物理 GPU page 在权重和 KV 间弹性分配。
- [[Syncopate-OSDI26]] — 保持 PyTorch distributed 接入面，重写 chunk/tile 级计算—通信重叠。
- [[TrainMover-OSDI26]] — 直接修改 c10d/NCCL 支持低中断 rank 替换。
- [[RobustRL-OSDI26]] — 用 DLPack 将 PyTorch tensor 零拷贝桥接到 CuPy/UCX 路径，说明 tensor 兼容与 communicator 兼容是两回事。
- [[DirectKV-OSDI26]] — 以 PyTorch extension 接入专用 Grace–Hopper attention kernel；API 可用不代表普通 PCIe 平台也有相同性能。
- [[OpGuard-OSDI26]]、[[SDCHunter-OSDI26]] — 将 PyTorch 训练收紧成可重放、可对齐的诊断执行。
- [[Cocoon-OSDI26]] — 在 PyTorch 训练路径中分层管理相关噪声历史。
