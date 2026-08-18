---
type: paper
name: Relax
full_title: "Relax: Composable Abstractions for End-to-End Dynamic Machine Learning"
authors: [Ruihang Lai, Junru Shao, Siyuan Feng, Steven S. Lyubomirsky, Bohan Hou, et al.]
venue: ASPLOS
year: 2025
tags: [ml-compiler, dynamic-shapes, symbolic-shapes, tvm, deployment, area/ai-infra]
source_pdf: "[[asplos25-lai-relax.pdf]]"
source_md: "[[asplos25-lai-relax]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-18
---

# Relax：端到端动态机器学习的可组合抽象（ASPLOS 2025）

> **原题**：Relax: Composable Abstractions for End-to-End Dynamic Machine Learning

> **一句话总结**：Relax 在一个 AOT IR 中组合 computation graph、TensorIR 与 external library call，并用跨函数 first-class symbolic shape 支撑 fusion、memory planning 和 partial lowering；在 NVIDIA/AMD/Apple 及移动/WebGPU 上部署动态 [[LLM|LLM]]，NVIDIA decode 最多降 27% latency、静态规划将 activation memory 降 22%–40%。

## 问题与动机

传统 ML compiler 按 graph→tensor program→library 单向 lowering，各层丢失 symbolic shape relation，导致动态 batch/sequence 下无法跨层 fusion、memory planning 或按 shape 选择 library/generated kernel。Relax 把三层保留在统一 cross-level abstraction 中（§1–3）。

## 关键观察 / 隐含假设

- **观察 1：动态 shape 不等于完全未知。** symbolic variables 可跨 subgraph、TensorIR 和 foreign call 保留关系，静态推导失败时再 runtime fallback（§3.2）。
  - **依赖假设**：大部分 shape relation 可表示和求解；data-dependent shape 仍会限制 AOT 优化。
- **观察 2：最优 backend 会随 batch 改变。** batch 1 适合 compiler-generated GEMV，大 batch 适合 cuBLAS partial lowering（§5.1–5.2）。
  - **可能失效场景**：library/version/hardware变化会使 dispatch policy 过期。

## 核心方法

Relax IR 同时容纳高层 function、loop-level TensorIR 和 external call；symbolic shape贯穿它们。passes 做 shape deduction、dynamic fusion、static memory planning、workspace lifting、CUDA Graph offload 与 partial lowering（§3–4）。

## 设计取舍

- cross-level IR 保留优化机会，也扩大 compiler trusted base。
- AOT 一次编译覆盖动态 shape，换取 runtime guard/fallback。
- 广泛 backend coverage 优先于每个平台手写最优 kernel。

## 实验与结果

- Llama3-8B/Gemma-7B/Qwen2-7B 在 RTX4090、7900 XTX、M2 Ultra 上与 vLLM/llama.cpp/PyTorch 等竞争；AMD batch1 最高 1.50×（图 14–16）。
- partial library lowering贡献最高 27%，CUDA Graph约 1%–2%；static planning 将 Llama3 activation memory 在 prefill/decode 降 22%/40%（图 17、表 2）。
- Samsung S23 相对 llama.cpp 吞吐最高增 55%；还覆盖 iPhone、Orange Pi、Steam Deck、Jetson 与 WebGPU（表 3、图 18）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| symbolic cross-level IR 支持动态优化 | ablation 27%、memory 22–40% | Llama3/RTX4090 | 强 |
| Relax 可统一部署多平台 | §5.1/5.3 多设备 | 选定模型/[[Quantization\|quantization]] | 中到强 |
| 性能普遍优于手工系统 | 各平台有胜负 | 不同 baseline 支持面不齐 | 中 |

## 批判性分析

### 论证链条

ablation 把 abstraction 与 fusion/library/memory收益连接起来，多平台证明 deployment breadth。baseline 在不同平台能力不对称，因而“competitive”可信，“统一优于”不成立。

### 假设压力测试

复杂 data-dependent control、[[MoE|MoE]] routing 和在线 graph mutation会削弱 symbolic inference；长期支持更多 library/backend 也会增加 dispatch 与测试矩阵。

### 实验可信度

模型/硬件广、强 baseline与消融充分；缺 compile time、binary/cache size、生产 P99 和长期兼容成本。

### 系统性缺陷

AOT guard、fallback、external ABI 和 shape bug 可能造成 silent wrong-code；论文未展开 fault isolation 与部署回滚。

## 局限与后续工作

- **局限 1**：动态数据依赖和 production SLO 未覆盖。
- **后续工作 1**：在 ragged/MoE serving trace 上报告 compile/cache、guard miss、P99 与 correctness。

## 相关

- **相关概念**：[[Tensor-Compilation]]、[[Dynamic-Shape]]、[[CUDA-Graph]]
- **相关系统**：[[PyTorch]]、[[TVM]]、[[vLLM]]
