---
type: concept
aliases: [Tensor-Cores, NVIDIA-Tensor-Core]
last_updated: 2026-08-14
tags: [gpu, machine-learning, kernels, mixed-precision]
---

# Tensor Core

> Tensor Core 是 GPU 中专门执行小块矩阵乘加的硬件单元。它能提供很高的峰值算力，但系统能否真正受益，还取决于数据精度、矩阵形状、布局、稀疏模式、搬运流水、寄存器容量和累加语义。

## 核心概念

普通 CUDA Core 可以执行通用标量或向量指令；Tensor Core 更像一条受约束的矩阵快速路径。程序要先把大矩阵切成硬件支持的 tile，再把数据放进寄存器或共享内存，最后用 MMA/WGMMA 等指令完成乘加。硬件代际决定可用的 tile、数据类型和搬运机制，因此“使用了 Tensor Core”并不等于“接近峰值”。

对系统研究来说，Tensor Core 至少有四层含义：

1. **计算能力**：FP16、BF16、TF32、FP8、INT8 等格式对应不同吞吐与累加规则；
2. **映射约束**：矩阵维度、padding、稀疏格式和布局必须适合硬件 tile；
3. **流水约束**：TMA、共享内存、warp 分工和寄存器生命周期决定矩阵单元会不会饿死；
4. **数值语义**：内部累加顺序、精度、舍入和 subnormal 处理可能与 IEEE-754 的直觉不同，也会随 GPU 代际变化。

## 关键观察 / 隐含假设

- **峰值算力常常不是实际瓶颈。** [[Voltrix-SpMM-ATC25]] 发现，上一代 Tensor-Core SpMM 中数据加载可占 kernel 时间的 80% 以上；只有同时压缩稀疏元数据、批量搬运并平衡 SM 工作，矩阵单元的算力才会转成端到端收益。[[ParallelKittens-MLSys26]] 进一步说明，多 GPU kernel 还要把 NVLink 通信与 tile 计算重叠。
  - **隐含假设**：目标算子有足够多、足够规则的矩阵工作，可以摊销打包、同步与 pipeline 开销。小矩阵、低复用或控制流密集的算子可能仍由 launch、访存或同步主导。

- **不受原生支持的精度需要重新映射。** [[ADAngel-OSDI26]] 面对 W4A8、W3A8 等不对称精度，不能直接调用一种 Tensor Core 指令。它在 Padding、Split、Bitwise 三种分解中按 shape 选择：prefill 更偏计算受限，decode 更偏权重带宽受限，所以固定 kernel 不会一直最好。
  - **隐含假设**：模型、GPU 和 shape 空间相对稳定，离线 profile 能代表部署期。动态 [[MoE]] shape、多租户干扰或频率变化会让最佳映射漂移。

- **低精度吞吐要和数值边界一起看。** [[FP8FlowMoE-MLSys26]] 通过 power-of-two scale 和 scaling-aware transpose 避免 FP8 的二次量化误差；[[AEGIS-OSDI26]] 则利用 Tensor Core 内部尚未截断的 float32 accumulator 生成更敏感的校验和。前者说明精度转换本身可能成为性能和误差瓶颈，后者说明内部高精度状态也可成为可靠性观测点。
  - **隐含假设**：实现能够访问或控制内部累加数据流。封闭库、新 dtype 或新指令可能不暴露相同接口。

- **累加语义是架构属性，不是通用常数。** [[FPRev-ATC25]] 从黑盒输出恢复出 V100、A100、H100 不同的多项融合累加树；[[Hawkeye-MLSys26]] 又测得 Ampere 与 Hopper 在累加分组、内部有效位和舍入方式上不同，并用 CPU 模拟器在其自定义 MMA 路径上做到 bit-exact 重放。
  - **隐含假设**：给定架构和指令的微语义是确定的，且生产库使用了已经表征的 MMA 路径。split-K、atomic、融合算子或 driver 变化都可能增加新的非确定性。

- **软件流水与 warp 分工必须联合考虑。** [[Twill-OSDI26]] 给出直接反例：理论最小 initiation interval 可能因寄存器、阻塞同步或跨 warp 通信而不可实现。它把软件流水和 warp specialization 放进同一个约束问题，才能在给定机器模型内找到可执行的最优 schedule。
  - **隐含假设**：抽象的延迟、资源表和 register budget 足够接近真实编译结果。论文中仍出现 `ptxas` 未被模型预测的 spill，说明形式最优不等于实机全局最优。

- **稀疏性只有映射到合适路径才有用。** [[GeneralSparse-ATC25]] 用 CUDA-Core autotuning 适配不同剪枝模式，[[Voltrix-SpMM-ATC25]] 则针对 Hopper Tensor Core 重写稀疏格式与流水。两条路线说明“不规则但通用”与“硬件专用但高吞吐”之间没有单一赢家。

## 设计空间

### 精度与表示

- 原生精度直接走硬件支持的 MMA，接口简单，但受支持格式限制；
- 不对称或任意 bit-width 可用 padding、bit-plane 或分块重建，代价是额外计算、中间结果或多份权重布局；
- FP8 等低精度可以减少算力、显存和通信压力，但 scale、累加精度与转换位置必须共同设计；
- 若目标是数值复现或故障检测，还要显式记录硬件代际、指令路径与内部累加规则。

### 数据供给与执行流水

- 小 tile 要经过 global memory、shared memory、register 多级搬运；任何一级跟不上，Tensor Core 都会空闲；
- Hopper 的 TMA、WGMMA 与 warp specialization 可把 loader 和 consumer 分开，但会增加 barrier、共享内存和寄存器约束；
- 多 GPU 时还要选择 intra-SM 或 inter-SM 通信重叠，并处理 NVLink/NVSwitch 的消息粒度；
- 持久化 kernel 和预取能减少 launch 与等待，但会占住 SM，可能损害共置任务的隔离。

### 通用性与专用化

- 手写 kernel 能利用特定 GPU 的最新指令，性能高，但需要为新架构、dtype 和 shape 维护多套实现；
- compiler/solver 可以搜索更大的 schedule 空间，但依赖准确机器模型、可靠 lowering 和可接受的离线时间；
- 离线查表适合长期运行的固定模型，在线变化大的 workload 则需要回退、重校准或更稳健的 cost model。

## 证据边界

- [[ADAngel-OSDI26]] 的主结果来自 Llama-3-8B 与 Orin/A100；TensorRT-LLM 基线并非始终使用相同精度，不能把加速直接解释为同等质量下的纯 kernel 优势。
- [[AEGIS-OSDI26]] 的 0.86% 是生产采样开销，不是每个 Tensor Core 操作都被完整校验的成本；3,500 万 GPU-hours 证明问题真实，但没有完整故障 ground truth。
- [[Twill-OSDI26]] 的最优性只对单层、稳定循环和给定抽象机器模型成立；论文主要评测 Attention，尚未自动覆盖通用 GPU 程序。
- [[Voltrix-SpMM-ATC25]] 深度依赖 H100 的 TMA/WGMMA，且主要是图/GNN 稀疏矩阵；[[GeneralSparse-ATC25]] 的结果则集中在 A100/V100 的剪枝 LLM，两者不能互相替代为普适结论。
- [[Hawkeye-MLSys26]] 的 bit-exact 结果针对被表征的自定义 MMA 路径；从 tile 扩展到 cuBLAS、融合 Attention 和分布式归约仍需额外证据。

## 研究判断

Tensor Core 的研究重点已经从“怎样调用矩阵指令”转向“怎样让整个数据流配得上这条快速路径”。性能论文需要同时报告矩阵单元利用率、数据搬运、同步、资源占用与端到端结果；可靠性论文则需要说明 dtype、累加器、舍入和硬件版本。只报理论 TFLOPS 或单个 microkernel speedup，通常不足以支持系统级结论。

更值得继续追问的是三类接口：一是让 compiler 获得可验证的机器资源模型；二是给运行时提供精度、布局和 shape 漂移时的安全回退；三是把内部 accumulator 与执行语义暴露给可靠性和复现工具，而不要求每个项目逆向硬件。

## 引用本概念的论文

- [[ADAngel-OSDI26]] — 为任意精度量化按 shape 选择 Tensor Core 计算映射。
- [[AEGIS-OSDI26]] — 从 float32 accumulator 生成低噪声训练校验信号。
- [[Twill-OSDI26]] — 联合求解软件流水与 warp specialization。
- [[FP8FlowMoE-MLSys26]] — 让 MoE 的 FP8 数据流减少转换并避免二次量化误差。
- [[FPRev-ATC25]] — 黑盒恢复 Tensor Core 的多项融合累加顺序。
- [[Hawkeye-MLSys26]] — 逆向并模拟多代 GPU 的 MMA 数值语义。
- [[GeneralSparse-ATC25]] — 展示不规则稀疏场景中 CUDA-Core autotuning 的适用面。
- [[Voltrix-SpMM-ATC25]] — 用 Hopper 专用搬运和负载均衡释放 Tensor-Core SpMM 性能。
- [[ParallelKittens-MLSys26]] — 用 tile 级通信 primitive 让多 GPU 计算与通信重叠。
