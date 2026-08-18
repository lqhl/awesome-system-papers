---
type: paper
name: SuperServe
full_title: "SuperServe: Fine-Grained Inference Serving for Unpredictable Workloads"
authors: [Alind Khare, Dhruv Garg, Sukrit Kalra, Snigdha Grandhi, Ion Stoica, Alexey Tumanov]
venue: NSDI
year: 2025
tags: [ml-serving, supernet, slo, reactive-scheduling, bursty-workloads, area/ai-infra]
source_pdf: "[[nsdi2025-khare.pdf]]"
source_md: "[[nsdi2025-khare]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-17
---

# SuperServe：面向不可预测负载的细粒度推理服务（NSDI 2025）

> **原题**：SuperServe: Fine-Grained Inference Serving for Unpredictable Workloads

> **一句话总结**：SuperServe 挑战“模型切换太慢，所以只能粗粒度预测调度”的共识，将多个 latency–accuracy 点压进 weight-sharing SuperNet，再由 SubNetAct 即时激活子模型、SlackFit 逐 batch 调度；Microsoft Azure Functions trace 上同 SLO attainment 的准确率提高 4.67%，同准确率的 SLO attainment 提高 2.85×（§6，图 8–12）。

## 问题与动机

生产推理的请求率可在亚秒级剧烈变化。固定模型在低负载时浪费准确率，在 burst 时又错过 SLO；部署多个独立模型浪费显存，临时换模型的加载时间则可高于 inference latency 14.1×，使 SLO miss 最多增加 75×（§2.1，图 1）。

SuperServe 的目标是在单一内存 footprint 内保留完整的 latency–accuracy frontier，使调度器能够响应当前 queue slack，而不是预测未来 burst。

## 关键观察 / 隐含假设

- **观察 1**：真正限制 reactive scheduling 的是 model actuation delay，而不是在线决策本身（§2.1，图 1）。
- **观察 2**：SuperNet 已共享所有 SubNet 权重，静态抽取和分别加载是不必要的（§2.2–3）。
- **假设 1**：应用已有训练良好的 SuperNet，且不同 SubNet 的准确率/延迟 frontier 可离线画像。
  - **证据强度**：中；论文覆盖 vision/NLP SuperNet，但不等同于任意独立模型集合。

## 核心方法

SubNetAct 向 SuperNet 插入 LayerSelect、ChannelSelect 等控制流 operator，根据请求指定的 depth/width 动态选择子图，无需复制权重或加载新模型。它把大量候选模型收敛到一个部署，显存最多降低 2.6×。

SlackFit 根据请求剩余 slack、候选 SubNet latency/accuracy 和 batch size 贪心选择执行点。SuperServe 将两者实现为异步 serving runtime，并允许替换 scheduler（§4–5）。

## 设计取舍

- **共享权重换快速切换**：显存和 actuation 更好，但模型必须来自同一 SuperNet，不能任意混合独立 architecture。
- **逐 batch reactive policy**：无需预测 burst，代价是依赖稳定的 latency profile。
- **边界条件**：不适用于只有一个固定模型、准确率不可降级或请求不允许不同模型质量的服务。

## 实验与结果

- Azure Functions-derived burst trace 上，同 SLO attainment 的 accuracy 提高 4.67%；同 accuracy 的 SLO attainment 提高 2.85×（§6.3，图 10–12）。
- SubNetAct 相对部署独立模型最多降低 2.6× memory，并把切换从 model loading 降为 request-level control flow（§6.2）。
- 覆盖 CNN 与 transformer SuperNet、多个 10–100 ms latency target；headline 依赖 trace 与准确率 frontier（§6.1）。
- SlackFit 接近论文定义的 oracle objective，但未测模型 profile 随硬件温度、共租户与版本漂移的情况。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 快速 SubNet actuation 使 reactive scheduling 可行 | SLO/accuracy 分别改善 2.85×/4.67%（§6.3） | Azure-derived trace、SuperNet workload | 强 |
| 权重共享降低多模型 footprint | 最高 2.6× memory reduction（§6.2） | 候选模型必须来自同一 SuperNet | 强 |
| SlackFit 可追踪 burst | 与 coarse policy/ideal objective 对照（图 10–12） | profile 准确、单服务 workload | 中 |

## 批判性分析

### 论证链条

论文很好地将“模型加载慢”转化为“不要加载模型”，SubNetAct 与 SlackFit 的机制—结果对应清楚。真正受限之处是 workload abstraction：大量生产服务使用独立模型或 [[LLM|LLM]]，而非可训练的 weight-sharing SuperNet。

### 假设压力测试

profile error、异构 GPU、batch interference 或模型质量不可用单一 accuracy 表达时，SlackFit 的选择可能失真。频繁切换 SubNet 也可能影响 kernel specialization 和 cache locality。

### 实验可信度

生产 trace 与多个 architecture 提供较好证据，baseline 同时覆盖预测与 reactive policy。缺少真实线上 A/B、P99 confidence interval 和多租户干扰。

### 系统性缺陷

训练/维护 SuperNet 是前置成本；模型更新后需重做 frontier profiling。控制流 operator 扩展到生成式 LLM 的 KV state 和连续 batching 并不直接成立。

## 局限与后续工作

- 在生成式 LLM、异构 GPU 与 profile drift 下验证 request-level model actuation。
- 把 accuracy scalar 扩展为 calibration、安全阈值和 tenant-specific quality constraint。

## 相关

- **相关概念**：[[Continuous-Batching]]、[[LLM-Inference]]
- **同类系统**：Clipper、INFaaS
- **同会议**：NSDI 2025

