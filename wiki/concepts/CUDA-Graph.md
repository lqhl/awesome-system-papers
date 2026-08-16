---
type: concept
aliases: [CUDA-Graphs]
last_updated: 2026-08-14
tags: [gpu, runtime, scheduling, kernel-launch]
---

# CUDA Graph

> CUDA Graph 把一组 GPU kernel、内存复制和它们的依赖先捕获成有向无环图，之后用一次 replay 重复提交整张图。它主要减少 CPU 逐个发射 kernel 的空隙；它不会消除 kernel 本身的计算，也不会自动打破 kernel 之间的全局边界。

## 核心思想

普通 CUDA 程序由 CPU 连续调用 kernel。一次 launch 常有数微秒开销；当一个 iteration 含几百个很短的 kernel 时，GPU 会在两次 launch 之间空等。CUDA Graph 先捕获这些操作，实例化后再反复 replay，因而把大量 host dispatch 合成少量提交。

这种加速来自“重复”和“稳定”。捕获时通常要固定依赖、地址和资源生命周期；输入内容可以变，但 runtime 必须把新内容放进稳定 buffer，或者更新 graph node 的参数。shape、控制流、allocator 行为和请求集合变化太大时，系统需要 padding、多张 graph、重新 capture，或退回普通 eager execution。

## 为什么重要

GPU 越快、模型并行切得越细，单个 kernel 越短，launch gap 所占比例就越大。OSDI 2026 的 [[GraCE-OSDI26]] 表明，CUDA Graph 的难点已不只是调用 API，而是编译器和 runtime 能否正确处理 CPU tensor、可变参数以及“用了反而更慢”的候选图。

[[ECHO-OSDI26]] 从另一面说明，在线推理中的动态 cache 管理也必须改写成固定形状、GPU 内执行的操作，才能保留 graph replay。CUDA Graph 因此既是性能机制，也会反过来约束上层数据结构和调度接口。

## 关键观察 / 隐含假设

- **少量高层代码可能阻断很大一段图。** [[GraCE-OSDI26]] 的 XLNet 案例中，一个 CPU tensor 使含 413 个 kernel 的区域无法 capture。把 tensor 放到 GPU 可以扩大覆盖率，但前提是 host 不需要观察或修改它，而且新增显存可接受。
- **稳定地址带来的复制可能吃掉收益。** PyTorch2 常把可变输入复制到静态 placeholder。GraCE 用参数间接寻址把大块数据复制变成地址更新，但 vendor kernel 需要额外 prelude 和 graph-node update，参数很小时可能更慢。
- **不是每张图都值得 replay。** GraCE 的初始分析里，116 个候选 graph 有 29 个变慢，最差退化 397%。它在目标机器上分别 profile eager、graph 和 graph 加间接寻址版本。这个选择只对所测 shape、GPU 和软件版本可靠。
- **动态状态可以改写为固定张量，但要付元数据成本。** [[ECHO-OSDI26]] 把 KV slot 映射、free bitmap、priority 和输出 buffer 都预分配，并用 GPU 原子操作管理。这样能 capture 整个路径，但约占 610 MB HBM，且每层都要维护状态。
- **按长度分桶能提高图复用，也会增加等待。** [[LAPS-MLSys26]] 在短 prefill 池内用 length bucket、waiting window 和 CUDA Graph。结果来自 Qwen2.5-32B/H200；极低延迟 SLO 或长度分布突变时，等待和 graph pool 的取舍会变化。
- **CUDA Graph 仍保留 kernel 边界。** [[EventTensor-MLSys26]] 用动态 persistent megakernel 作为对照：它能表达 tile 级依赖和动态 shape，但实现、编译与调试更复杂。其多 GPU 端到端结果并未全面胜过成熟 serving runtime。
- **图执行扩大了抢占和诊断范围。** [[GPreempt-ATC25]] 指出 reset-based 抢占对含多 kernel 状态的 graph 更脆；[[StriaTrace-OSDI26]] 的生产案例也发现 CUDA Graph 从启动时被误关会成为稳定慢基线，按历史异常检测未必报警。
- **隐含假设是配置能长期复用。** 训练循环和固定 batch 推理容易摊薄 capture/compile；短作业、频繁 shape 变化、动态 adapter 或多租户干扰可能让预热成本大于收益。

## 设计空间与取舍

- **整图或子图 capture**：整图提交最少，但任一不可捕获操作都可能阻断全图；子图更稳健，仍会保留 CPU 调度空隙。[[DynaFlow-MLSys26]] 选择子图级 CUDA Graph 来承载动态执行策略。
- **静态 buffer 或参数更新**：复制到静态 buffer 容易保证正确性，大 tensor 成本高；pointer indirection 少搬数据，却需要 compiler/kernel 配合并扩大 alias 风险。
- **固定 graph pool 或重新 capture**：按 batch/shape 缓存多张图可降低运行时开销，但增加预热、显存和 binary cache；重新 capture 更灵活，尾延迟更难控制。
- **全部启用或选择性启用**：全量策略简单，可能出现负优化；profile-guided selection 更安全，编译时间更长，而且 profile 会随硬件和负载漂移。
- **CUDA Graph 或 persistent megakernel**：前者保留成熟 kernel 和库边界，部署较容易；后者能跨算子流水，但架构绑定、调试和公平性问题更重。
- **graph replay 或普通动态调度**：稳定主路径可以 replay，异常 shape 和控制流走 fallback；双路径会增加测试面，尤其要验证 RNG、allocator、stream 和错误处理语义一致。

## 引用本概念的论文

- [[GraCE-OSDI26]]：编译器定位 capture 阻塞点、用参数间接寻址减少 replay copy，并逐图拒绝负优化。
- [[ECHO-OSDI26]]：把动态 KV cache 的分配、释放和召回改成 graph-friendly GPU 操作。
- [[DynaFlow-MLSys26]]：以子图级 capture 保留低开销，同时在子图之间表达动态执行顺序。
- [[LAPS-MLSys26]]：对短 prefill 分桶并用 CUDA Graph 批量执行。
- [[EventTensor-MLSys26]]：把 CUDA Graph 作为仍有 kernel 边界、动态 shape 需多次 capture 的基线。
- [[GPreempt-ATC25]]：从 GPU 抢占角度说明多 kernel 图不适合简单 reset 后重跑。
- [[StriaTrace-OSDI26]]：生产追踪发现 graph 配置错误可能成为长期稳定退化，而不是偶发异常。
- [[Torpor-ATC25]]：在 serverless GPU remoting 中讨论模型执行图与异步 API 路径；它不是 CUDA Graph 编译器，也不能作为 capture 收益的直接证据。

## 已知局限 / 开放问题

- 需要系统化验证 host observation、input mutation、alias、RNG、allocator 和多 stream 顺序；性能正确不代表语义正确。
- graph cache 应把 GPU 型号、驱动、CUDA、kernel binary、shape 和配置纳入 key，并在环境变化后失效。
- continuous batching、speculative decoding、MoE routing 和动态 adapter 会产生大量形状或数据依赖，固定 graph pool 是否仍划算需要按 workload 测量。
- graph replay 的资源占用、抢占延迟、MIG/MPS 隔离和多租户公平性缺少统一模型。
- 评测应同时报告 capture/编译时间、预热内存、低负载延迟和 fallback 比例，而不只报告稳定阶段吞吐。
