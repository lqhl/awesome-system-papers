---
type: paper
name: MorphServe
full_title: "MORPHSERVE: EFFICIENT AND WORKLOAD-AWARE LLM SERVING VIA RUNTIME QUANTIZED LAYER SWAPPING AND KV CACHE RESIZING"
authors: [Zhaoyuan Su, Zeyu Zhang, Tingfeng Lan, Zirui Wang, Haiying Shen, Juncheng Yang, Yue Cheng]
venue: MLSys
year: 2026
tags: [llm-serving, dynamic-quantization, kv-cache, autoscaling, slo]
source_pdf: "[[fc490ca45c00b1249bbe3554a4fdf6fb.pdf]]"
source_md: "[[fc490ca45c00b1249bbe3554a4fdf6fb]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-16
---

# MORPHSERVE: EFFICIENT AND WORKLOAD-AWARE LLM SERVING VIA RUNTIME QUANTIZED LAYER SWAPPING AND KV CACHE RESIZING (MLSys 2026)

> **一句话总结**：突发 [[LLM]] workload 下静态 [[AWQ]] 永远掉点、纯 FP16 会 SLO 违约；MorphServe 在内存压力高时异步 **LayerSwapper**（低敏感层换量化权重）+ **KVResizer** 扩 [[KV-Cache]]，压力降后无损还原，Azure/BurstGPT trace 上 SLO 违约 **92.45%↓**、P95 TTFT **2.2–3.9×**、相对静态量化 F1/ROUGE 退化最高 **88.85%↓**。

## 问题与动机

[[vLLM]]/Orca 假设固定精度与稳定负载；真实流量突发（Azure/BurstGPT）。过载只能排队或静态量化——前者 TTFT 违约，后者低载也损精度。需 **runtime reversible** 在 accuracy–efficiency Pareto 上滑动。

## 关键观察 / 隐含假设

- **观察 1：saturation point 后 FP16 serving TTFT 陡升；静态 INT4 在低载也持续掉 F1（GovReport）。**
  - **依赖假设**：morph 仅在压力超阈值触发（如 KV>85%、queue>100ms）。
  - **可能失效场景**：阈值抖动导致频繁 swap 开销。

- **观察 2：量化层与扩 KV 可协同：减权重 footprint 换 KV blocks，且 state-preserving 无需 flush/re-prefill。**
  - **依赖假设**：LayerSwapper 与 KVResizer 异步 CUDA stream 不破坏 decode 正确性。
  - **可能失效场景**：[[GQA]]/[[MLA]] 特殊布局下 resize 实现复杂（论文 claim 兼容）。

- **观察 3：相对 LLM-PQ，MorphServe 在 accuracy mode 平均缩小 41.3% 的 accuracy gap；PyramidKV 比较仅限该实验配置。**
  - **依赖假设**：offline sensitivity profiling 识别低影响层准确。
  - **可能失效场景**：新任务分布下 sensitivity 过时。

- **假设 1**：token-level 混合精度层可共存，非整模型切换。**
  - **证据强度**：**强**——多模型四数据集 trace。

## 核心方法

**Serving Monitor → Morphing Controller → Morphing Executor** 闭环。

**LayerSwapper**：压力高时 selective 层换预量化权重（可 INT8→INT4 阶梯）。

**KVResizer**：弹性增减 [[PagedAttention]] blocks；与 swap 协调内存。

**异步 overlap**：预分配 buffer；prefill/decode 均可触发。

## 设计取舍

- **Runtime morph vs 静态/规划量化**：赢得 burst 适应，增控制面与 kernel 双路径。
- **扩 KV vs 压 KV（PyramidKV）**：过载时倾向扩 batch 容量减排队，非减 context。
- **vs [[BOUTE]]**：MorphServe 单模型弹性，非 routing/heterogeneous GPU。
- **边界条件**：Llama2/3、CodeLlama、Vicuna；Azure+BurstGPT traces。

## 实验与结果

- SLO violations avg **-92.45%** vs FP16。
- P95 TTFT **2.2–3.9×** better vs FP16。
- vs AWQ static：F1/ROUGE degradation up to **-88.85%**；memory util **+29.29%**。
- vs LLM-PQ：**-41.3%** avg accuracy degradation；vs PyramidKV P95 TTFT **2.4×** lower。

## Claim–Evidence Map

| Claim | Evidence | Evaluation boundary | Confidence |
|---|---|---|---|
| LayerSwapper and KVResizer preserve inference state while reallocating | swaps KVC/layers without flush, re-prefill, or restart (§1, §3) | mechanism claim; performance tested on four models/two traces | high |
| Accuracy mode lowers P95 TTFT vs FP16 | 2.2–3.9× lower; quality drop 0.11–2.18% (§5.1, Fig.4) | named models, L4/A100, downsampled Azure/BurstGPT traces | high |
| Dynamic policy improves the stated AWQ configuration | DuReader/BurstGPT Llama2-7B accuracy degradation reduced 83.57%; P95 TTFT over 77% lower vs FP16 (§5.2, Table 4) | distinct AWQ and FP16 baselines | high |
| Dynamic reallocation helps under saturation | KVC utilization +29.29%, accuracy +3.58%, queue delay up to 3.8× lower (§5.1, Fig.5) | trace-driven saturation; comparisons use static quantization/FP16 capacity separately | high |
| Throughput/TPOT gains depend on workload | DuReader 1.6–1.83× vs FP16; Azure P95/P99 TPOT up to 1.06/1.23× (§5.1, Fig.6–7) | separate request-rate and Azure-trace tests | high |

## Critical Analysis

### 论证链条

突发负载+静态方案双失败 → reversible coordinated morph → 大幅 SLO/精度 win，运维叙事清晰。频繁 morph 的长期稳定性与 kernel 正确性需压力测试。

### 假设压力测试

与 [[Kitty]] KV 量化、[[FlexiCache]] offload 同时启用可能冲突。多租户 fairness：高压时 morph 是否影响邻租户未谈。

### 实验可信度

真实 cloud trace；多 baseline（AWQ、LLM-PQ、PyramidKV）。缺：与 [[Disaggregation]] 多池联合 burst。

### 系统性缺陷

论文未讨论 morph 失败回滚、审计量化层版本、合规可复现输出。Controller 调参运维成本。

## 局限与 Future Work

- **局限 1**：sensitivity profile 维护。
- **局限 2**：双精度路径测试矩阵爆炸。
- **Future work 1**：与 [[BOUTE]] 异构 GPU 弹性联动。
- **Future work 2**：auto-threshold 从 SLO 违约反馈学习。

## 相关

- **相关概念**：[[KV-Cache]]、[[Quantization]]、[[PagedAttention]]、[[SLO]]
- **同类系统**：[[vLLM]]、LLM-PQ、PyramidKV、[[AWQ]]
- **同会议**：[[MLSys-2026]]
