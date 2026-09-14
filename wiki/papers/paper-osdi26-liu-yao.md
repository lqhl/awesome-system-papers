---
type: paper
name: ADAngel
full_title: "ADAngel: Accelerating Arbitrary-Precision Quantized LLMs with Adaptive Computing Mapping"
authors: [Yao Liu, Wenjie Wang, Yifei Feng, Bo Peng, Jianguo Yao, Haibing Guan]
venue: OSDI
year: 2026
tags: [llm-inference, arbitrary-precision-quantization, mixed-precision-gemm, edge-gpu, kernel-optimization]
source_pdf: "[[osdi26-liu-yao.pdf]]"
source_md: "[[osdi26-liu-yao]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# ADAngel：面向任意精度量化 LLM 的自适应计算映射（OSDI 2026）

> **原题**：ADAngel: Accelerating Arbitrary-Precision Quantized LLMs with Adaptive Computing Mapping

> **一句话总结**：论文观察到 APQ 推理中矩阵形状、prefill/decode 阶段和量化位宽会改变最优 mixed-precision GEMM 策略，因此用 DPR 统一生成 Padding、Split、Bitwise 内核，离线穷举建立策略表；在 Jetson AGX Orin 上 decode 相对 llama.cpp 最高 5.10×，prefill 相对 TensorRT-LLM 提升 1.17–2.38×。

## 问题与动机

任意精度量化（APQ）允许权重和激活采用不同位宽，例如 W4A8，以减少模型存储和计算成本，同时尽量保持精度。但现有边缘 GPU 通常没有高效的非对称位宽 GEMM/GEMV 硬件。padding 将低位宽权重扩展到激活位宽，bit-disaggregation 则把操作拆成多个 1-bit 矩阵运算；两者都只代表一种固定的执行路径。

论文的核心问题是：LLM 推理的矩阵形状随 prompt 长度、batch size 和模型层结构变化，固定映射无法持续匹配硬件瓶颈。ADAngel 试图把策略选择从编译期固定决策变成针对目标模型和硬件的运行时映射。

## 关键观察 / 隐含假设

- **观察 1：prefill 与 decode 的最优策略不同。** prefill 的 GEMM 更偏计算密集，decode 的 GEMV 更偏内存访问；padding 与 bit-disaggregation 在两阶段的相对性能发生反转（图 4a）。
  - **依赖假设**：模型采用典型自回归推理，prefill/decode 的工作负载差异足以影响算术强度。
  - **可能失效场景**：持续 batching、不同 KV cache 管理方式或专用非对称算力硬件可能改变交叉点。
- **观察 2：同一阶段内部也存在交叉点。** Llama-2-7B 上，prefill 长度不超过 8 时 bit-disaggregation 更快，之后 padding 更快；decode batch size 约为 16 时也出现交叉（图 4b–c）。
  - **依赖假设**：M 维度、N/K 维度和 tile 形状是影响算术强度及资源占用的主要因素。
- **观察 3：位宽会改变计算和访存成本。** 在 A8 下，权重位宽增加会使 bit-disaggregation 的 1-bit 操作数量增长，而 padding 的执行路径相对稳定（图 5）。
  - **证据强度**：强；论文在 W2A8、W3A8、W4A8、W5A8 等配置上进行了比较，但覆盖的模型和硬件仍有限。

## 核心方法

DPR（Decomposition–Partial Product–Reconstruction）是一个统一的混合精度计算抽象：先把权重和激活按位分解，再计算部分乘积，最后重构输出。通过选择不同的位分区方案，可以表达 padding、bit-disaggregation 以及论文提出的 Split 策略（§4.2–§4.3）。这使策略生成从手工枚举变成了有统一表示的设计空间。

ADAngel 针对目标 LLM 和硬件实现三类高度优化的内核，组成 Computation Strategy Set。离线脚本遍历目标模型可能出现的 `(M,N,K)` 和位宽组合，用 CUDA events 测量每个内核，选择最低延迟者，生成 Oracle Policy Map（§4.4、§5）。运行时 dispatcher 只需按矩阵形状和位宽查表，再调用对应内核。

Split 是方法中承担折中角色的策略：它避免 padding 的权重扩展和小 M 下的零填充，又避免完整 bit-disaggregation 产生的大量中间结果。策略表按目标模型定制，因此不要求运行时做复杂搜索，但也牺牲了跨模型直接复用的能力。

## 设计取舍

- **离线成本换运行时开销**：Jetson AGX Orin 上为 W4A8 Llama-3-8B 构建策略表约需 5.7 小时和 1.7 GB 峰值内存；运行时 dispatch 开销低于 3 ms（§5、§6.5）。
- **专用化换通用性**：策略表依赖目标硬件、模型层的 N/K 组合和可见的 M 范围。模型结构、驱动或 GPU 变化后需要重新 profiling。
- **策略数量换实现维护成本**：多个手工优化的 CUDA kernel 覆盖更多区域，但增加了调试、正确性验证和版本适配负担；论文未详细讨论长期运维成本。

## 实验与结果

- Jetson AGX Orin 上，decode 吞吐相对 llama.cpp 最高提升 **5.10×**；prefill 的 TTFT 相对 TensorRT-LLM 提升 **1.17–2.38×**（摘要、图 8–9）。
- 长 prompt 场景中，ABQ-LLM 因 int32 中间状态占用 shared memory，在 batch size 8、prompt length 1024 时 TTFT 约 **39.4 分钟**；ADAngel 为 **5.27 秒**，相对提升 **448.69×**（§6.2）。
- decode 的单 batch 场景相对 TensorRT-LLM W8A8 提升 **1.95×**；batch size 2–8 时相对该基线平均提升 **1.82×**（§6.2）。
- W2A8、W3A8、W5A8 交叉位宽测试中，prefill 相对 llama.cpp 平均提升 **3.43×**，decode 相对 llama.cpp 最高提升 **7.35×**（§6.3）。
- A100 上相对 QServe 的 TTFT 提升 **2.12×**、TPS 提升 **1.72×**；表明方法不只适用于 Orin，但云端大 batch 下的收益边界仍需更多规模测试（§6.4）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| APQ 推理不存在对所有矩阵任务都最优的固定映射 | 不同 M、prompt length、batch size 的交叉结果，图 1、图 4 | 主要为 Llama-2-7B/Llama-3-8B、Orin | 强 |
| DPR 能覆盖并组织多种混合精度执行路径 | 三类策略和 W4A8 映射，§4.2–§4.3、图 7 | 依赖已有 GPU 指令和实现的策略集合 | 中 |
| 离线策略表能改善端到端推理 | 图 8–9；最高 5.10× decode、1.17–2.38× TTFT | Orin 为主，A100 补充；模型和位宽组合有限 | 强 |
| 自适应策略可避免 bit-disaggregation 的长序列资源爆炸 | ABQ-LLM 39.4 分钟 vs ADAngel 5.27 秒，§6.2 | 特定 batch size、prompt length 和硬件 | 强 |

## 批判性分析

### 论证链条

从矩阵形状和位宽导致性能交叉，到用离线 profiling 选择 kernel，论文的论证链条是闭合的。ADAngel 的收益主要来自避免明显的 padding 零填充和 bit-disaggregation 中间状态开销。所谓 oracle 只是在有限的候选策略和预先枚举的工作负载空间内最优，并非对所有未来任务全局最优。

### 假设压力测试

策略表覆盖 M∈[1,8192]，但真实服务可能出现更长 prompt、动态 batching、不同序列到达模式或新的模型层形状。运行时若遇到表外任务，论文没有充分说明 fallback 和性能保证。跨硬件测试只有 Orin 与 A100，难以判断在更新 GPU、不同 shared-memory 配置或多 GPU 拓扑上是否保持相同交叉点。

### 实验可信度

论文包含端到端 TTFT、decode TPS、跨位宽、跨硬件和消融实验，且报告了策略表构建成本。ABQ-LLM 在长 prefill 中的异常延迟也给出了 shared-memory 资源分析。仍需注意，基线、模型规模和 batch 范围偏窄；没有展示多租户隔离、持续 batching、能耗或服务 P99 的结果。

### 系统性缺陷

每个目标模型都可能需要数小时 profiling，部署流程增加了校准和缓存管理。多个 CUDA kernel 会增加对 CUDA 版本、硬件指令和量化格式的依赖。论文未讨论 kernel 选择错误、模型热更新、故障恢复、监控和策略表版本管理。

## 局限与后续工作

- **局限 1**：策略表依赖有限的模型形状和 M 范围；表外任务的 fallback、插值和性能上界没有充分说明。
- **局限 2**：实验集中在少数 Llama 模型、Orin/A100 和短 batch 范围，尚不能推出对长上下文、continuous batching 或多租户服务的结论。
- **后续工作 1**：在公开生产 trace 上测量 M/N/K 分布，并比较静态表、在线 bandit 选择和基于硬件计数器的自适应策略，在 TTFT、TPOT、P99、能耗和 profiling 成本上统一评估。

## 相关

- **相关概念**：[[Mixed-Precision]]、[[LLM-Inference]]、[[KV-Cache]]
- **同类系统**：[[llama.cpp]]、[[TensorRT-LLM]]、[[QServe]]、[[ABQ-LLM]]
- **同会议**：[[OSDI-2026]]
