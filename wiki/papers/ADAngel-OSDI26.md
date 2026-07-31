---
type: paper
name: ADAngel
full_title: "ADAngel: Accelerating Arbitrary-Precision Quantized LLMs with Adaptive Computing Mapping"
authors: [Yao Liu, Wenjie Wang, Yifei Feng, Bo Peng, Jianguo Yao, Haibing Guan]
venue: OSDI
year: 2026
tags: [llm-inference, quantization, mixed-precision, gpu-kernel]
source_pdf: "[[osdi26-liu-yao.pdf]]"
source_md: "[[osdi26-liu-yao]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# ADAngel：用自适应计算映射加速任意精度量化 LLM（OSDI 2026）

> **原题**：ADAngel: Accelerating Arbitrary-Precision Quantized LLMs with Adaptive Computing Mapping

ADAngel 把 asymmetric-bit mpGEMM 统一为 decomposition–partial-product–reconstruction 模型，并针对目标模型离线穷举 profile 多种 kernel，在运行时按 shape、bit-width 和阶段查表选择最快策略。

## 问题与动机

W4A8 等 APQ 在精度与压缩间表现良好，但 GPU Tensor Core 不原生支持任意不对称 operand。padding、bitwise disaggregation 或 LUT 各自在某些 shape 有效：prefill/decode、sequence length、batch size 和 bit-width 一变，最佳算法会交叉。静态选一种 kernel 会在部分任务上产生 shared-memory explosion、零填充或额外 memory traffic。

## 关键观察 / 隐含假设

### 关键观察

- mpGEMM 可统一表达为对 activation/weight 做不同 bit partition，计算 partial products 后按权重重建。
- 目标 [[LLM|LLM]] 的 GEMM shape 与 bit-width 集合有限，尽管运行时 workload 动态，离线 exhaustive profiling 仍然可行。
- 小 M 的 decode 更重视 weight traffic，短 prefill 与长 prefill 则跨越 memory-bound/compute-bound 区间，必须动态换策略。

### 隐含假设

- 部署模型、GPU 和 kernel 版本相对稳定，offline oracle map 不会因温度、并发或驱动变化快速失准。
- 量化模型的 accuracy 已由上游 [[Quantization|PTQ]] 保证，论文主要优化计算而不重新评估质量。
- 额外 workspace 与 profile 时间可被 edge device 的内存容量和长期推理收益摊销。

## 核心方法

### DPR 计算模型

DPR 将不同 bit-width operand 切成若干逻辑 components，在硬件支持的 precision 上计算两两 partial products，再按 bit significance 重建。不同 partition 对应 padding、bitwise 以及论文提出的 Split 等策略。

### 计算策略集合（Computation Strategy Set）

ADAngel 基于 CUTLASS 等实现并优化多种 DPR kernel，通过 fusion、coalesced layout 和 shared-memory 控制覆盖 memory-bound 与 compute-bound 区间。

### 最优策略映射（Oracle Policy Map）

离线对目标 LLM 的每个 `(M,N,K, WBit, ABit)` task 穷举 strategy，记录最低 latency kernel。约 256 KB 的 policy map 嵌入 runtime，由轻量 dispatcher 直接索引，避免在线 autotuning。

## 设计取舍

- model/hardware specialization 获得接近 oracle 的性能，但每次换模型、GPU 或软件栈都需重新 profile。
- strategy portfolio 比单 kernel 更稳健，却增加实现、验证和 workspace 复杂度。
- exhaustiveness 依赖任务空间有限；dynamic shapes 或更细粒度 quantization 会扩大 map。
- 系统以空间换时间，在 Orin 上额外 GEMM workspace 达 896 MiB。

## 实验与结果

- 在 Jetson AGX Orin 上的 Llama-3-8B W4A8 prefill，ADAngel 相比 TensorRT-LLM 的 TTFT speedup 为 1.17–2.38 倍；短 prompt 下相比 llama.cpp 从 126 ms 降至 43 ms，latency 降低 65.9%（§6.2，图 8）。
- 长 prefill 的 ABQ-LLM 因 partial-product shared memory 膨胀，在 batch 8、prompt length 1024 时远慢于 ADAngel；后者 latency 为 5.27 s，获得 448.69 倍 speedup，但这个巨大比值主要来自基线病理退化。
- decode 阶段 ADAngel 相比 llama.cpp 的 TPS speedup 最高 7.35 倍；摘要采用更保守的跨设置结果，报告最高 5.10 倍。
- 相比 TensorRT-LLM W8A8，ADAngel decode throughput 最高提高 1.95 倍，并在另一配置超过基线 1.82 倍，收益来自避免把低 bit weights 上填充为 8-bit。
- batch 8、prompt 1024、生成 128 tokens 时，ADAngel peak memory usage 为 18.80 GiB，约占 Orin device memory 31.5%，其中 workspace 896 MiB。
- 跨精度与 A100 实验中，相比 QServe，ADAngel TTFT 提高 2.12 倍、TPS 提高 1.72 倍；证明方法不只适用于 Orin，但 GPU/模型覆盖仍有限。

## 论断—证据表

| 论断 | 机制 | 证据 | 边界 |
|---|---|---|---|
| 静态 mpGEMM 策略无法覆盖 APQ 异构任务 | DPR portfolio 与按 shape 查表 | TTFT 相比 TensorRT-LLM 提高 1.17–2.38 倍 | 目标 shape 集合需提前已知 |
| adaptive mapping 能避免极端退化 | Bitwise/Split/Padding 动态切换 | 长 prefill 相比 ABQ-LLM 最高 448.69 倍 | 极端比值来自基线 shared-memory explosion |
| edge decode 可显著加速 | 小 M 使用低 traffic strategy | TPS 相比 llama.cpp 最高 5.10–7.35 倍 | 单模型、少数 GPU 与 quantization 配置 |
| offline oracle 可低成本部署 | 约 256 KB map 与直接 lookup | dispatcher 开销可忽略 | 重新部署需再次 exhaustive profile |

## 批判性分析

### 论证链条

论文先展示不同策略随 M/bit-width 的 crossover，再用 DPR 统一解释 design space，最后以 oracle ablation 和端到端推理证明动态 mapping 的价值。理论抽象、kernel 工程与系统收益衔接明确。

### 假设压力测试

若模型使用 per-group mixed bits、动态 sequence 或多租户并发，有限 map 可能迅速膨胀且单进程 profile 不再代表实际最优。频繁更新模型的 edge 产品也可能无法摊销 specialization；内存只有 16 GB 时 18.80 GiB 配置不可部署。

### 实验可信度

评估覆盖 prefill/decode、不同 bits、Orin/A100 和多基线，且披露 memory footprint。缺少量化 accuracy、能耗、端到端 request p99、多请求 [[Continuous-Batching|continuous batching]]，以及离线 profiling 的总时间与能耗。

### 系统性缺陷

ADAngel 将 kernel selection 问题转换为每个部署的离线穷举，没有建立可跨硬件预测的性能模型。策略数量与维护成本会随新 precision、Tensor Core ISA 和模型结构增长；超大 speedup 容易掩盖相对成熟基线仅约 1–2 倍的真实边际。

## 局限与后续工作

- 支持 per-layer/per-group bit-width、dynamic batching 与多租户 interference 下的在线校准。
- 报告 quantization accuracy、energy/token、p99 latency 和 offline profile 成本。
- 用可迁移 cost model 缩减每个模型与 GPU 的 exhaustive search。
- 降低 896 MiB workspace，并验证更小内存 edge devices。

## 相关

- [[LLM-Quantization]]
- [[Mixed-Precision-GEMM]]
- [[TensorRT-LLM]]
- [[QServe]]
