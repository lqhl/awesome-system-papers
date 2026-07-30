---
type: paper
name: Jenga
full_title: "Jenga: Effective Memory Management for Serving LLM with Heterogeneity"
authors: [Chen Zhang, Kuntai Du, Shu Liu, Woosuk Kwon, Xiangxi Mo, Yufeng Wang, Xiaoxuan Liu, Kaichao You, Zhuohan Li, Mingsheng Long, Jidong Zhai, Joseph Gonzalez, Ion Stoica]
venue: SOSP
year: 2025
tags: [llm-serving, kv-cache, memory-management, heterogeneous-models, vllm]
source_pdf: "[[3731569.3764823.pdf]]"
source_md: "[[3731569.3764823]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# Jenga：为异构 LLM 提供有效的内存管理（SOSP 2025）

> **原题**：Jenga: Effective Memory Management for Serving LLM with Heterogeneity

> **一句话总结**：Jenga 以 layer-property interface 驱动 LCM 分配与 attention-specific prefix cache；在 Table 2 的异构模型和 MMLU-pro/MMMU-pro/arXiv-QA 上，相对 [[vLLM]] 的吞吐在 H100 最高 **1.73×**、L4 最高 **2.16×**（§8.1），不代表所有模型或负载。

## 问题与动机

[[PagedAttention]]/[[vLLM]] 假设每层 KV 同质、固定 page size、每层都需要全 prefix pages。现代模型 heterogeneous：Gemma-3/Hymba 混 full+sliding window；Mamba state 远大于 per-token KV；VLM 有 vision embedding；speculative decoding 有 draft/target 两套 cache。短请求 Mamba 层主导内存，长请求 full-attention 主导——均匀 per-layer 分区造成浪费与 batch 上限降低。

## 关键观察 / 隐含假设

- **观察 1**：异构 LLM 仅 2–3 种 allocation size，buddy/sl uniform partition 产生 <最小粒度的碎片（Gemma-3 27B 例：18.75% waste）。
  - **依赖假设**：层类型有限且 embedding size 可预知；LCM page size 可一次算定。
  - **可能失效场景**：新层类型频繁加入需重算 LCM，page size 膨胀导致 internal fragmentation。
- **观察 2**：prefix cache hit length 受 **最短 hit 层** 限制；不同 attention 机制需 cache 不同 token 数（Mamba 仅最后 token vs full-attention 全 prefix）。
  - **依赖假设**：layer property 静态可知；common-prefix predictor + cache simulator 能在线权衡 hit vs batch size。
  - **可能失效场景**：高度动态 prompt 分布使 predictor 失效；simulator 开销在超大 batch 下未充分测量。
- **观察 3**：层间 runtime memory exchange 是提 utilization 的关键，但碎片在 LLM 场景比通用 allocator 更致命。
  - **依赖假设**：实现已集成 vLLM 生产路径且有 industry partner 部署。
  - **证据强度**：中。有 production claim，但公开细节有限。

## 核心方法

1. **Two-level LCM allocator**：底层大 page，顶层按 embedding size 切分；page size = 各 token embedding size 的 LCM，最小化 internal fragmentation。
2. **Attention-property-aware prefix caching**：按 SWA/Mamba/local/cross-attention 定制 hit/eviction；common-prefix predictor 指导 cache 哪些 token；prefix cache simulator 平衡 hit rate 与 batch size。
3. **vLLM 集成**：覆盖 heterogeneous layers、speculative decoding draft/target、VLM vision embeddings。

## 设计取舍

- **LCM page size vs 动态多种 page pool**：数学简单，但 LCM 可能很大。
- **Layer-specific cache policy vs 统一 prefix cache**：提高 hit 平衡，但实现与运维复杂度上升。
- **绑定 vLLM 内存 manager**：直接生效，但 portability 到其他 serving engine 需移植。

## 实验与结果

- 吞吐指标：Table 2 模型/任务上，H100 相对 [[vLLM]] 平均 **1.46×**、最高 **1.73×**；L4 平均 **1.65×**、最高 **2.16×**（§8.1，Fig.14）。
- 延迟边界：Llama 3.2 Vision 在少于 1.2 req/s 时平均 latency 差 **4.2%**；较高负载下 Jenga E2E latency 最多 **1.90×**、TTFT 最多 **23.40×** 更好（§8.1，Fig.15）。
- 最大 context：Llama 4 109B 的 8×H100 为 1.3M→5.2M，8×H200 为 3.7M→14.7M（§8.1，Table 3）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| Jenga 用 layer-property interface 驱动 LCM 分配与 attention-specific prefix cache | page size、active pages、valid prefix-hit lengths 均由 layer 声明；LCM 为 embedding sizes 的最小公倍数（§4–5，Fig.8–10） | 与 [[PagedAttention]] 的同质 layer/page partition 对照 | high |
| 异构模型吞吐提高 | H100 最高 1.73×/平均 1.46×，L4 最高 2.16×/平均 1.65× vs [[vLLM]]（§8.1，Fig.14） | Table 2 的模型、MMLU-pro/MMMU-pro/arXiv-QA、H100 80GB 或 L4 24GB | high |
| 低/高负载 latency 结果不同 | 低负载平均差 4.2%；高负载 E2E 最多 1.90×、TTFT 最多 23.40×更好（§8.1，Fig.15） | Llama 3.2 Vision、变化 request rate，不泛化至所有 workload | high |
| Ministral trace 的 KV-cache 浪费降低 | [[vLLM]] 平均浪费 38.2%，Jenga 0.04%（§8.2，Fig.17） | static/dynamic request-length traces；不是所有模型的内存占用 | high |
| Llama 4 的最大 context 提升 | 8×H100 1.3M→5.2M；8×H200 3.7M→14.7M（§8.1，Table 3） | Llama 4 109B、八 GPU 节点 | high |

## 批判性分析

### 论证链条

「heterogeneity 破坏同质 paging」→ LCM + per-attention cache policy → vLLM 吞吐/内存/context 提升，链条在评测模型集上闭合。production deployment 作为外部验证，但缺公开 A/B 数字。

### 假设压力测试

- 新架构（e.g. 动态 token drop）可能超出 layer property 枚举。
- LCM 随 embedding size 种类增长可能爆炸。
- Prefix predictor 错误可能导致 batch shrink 超过 cache 收益。

### 实验可信度

- vLLM 是正确 baseline；覆盖 Gemma/Hymba/VLM/spec decode/Llama4 等。
- 「不影响 latency」需结合具体 SLA 定义审视；P99 under overload 未强调。
- Industry deployment 细节不足，独立复现难度中等。

### 系统性缺陷

- 论文未讨论跨节点 KV tier 与 Jenga 本地 allocator 协同。
- Predictor/simulator CPU 开销与 scheduler 单点风险未讨论。

## 局限与后续工作

- **局限**：LCM 膨胀风险；依赖静态 layer metadata；vLLM 耦合。
- **Future work**：动态 page size pool；与 [[Disaggregation]]/远端 KV 协同；开源 predictor 调参工具。

## 相关

- **相关概念**：[[KV-Cache]]、[[PagedAttention]]、[[vLLM]]、[[Prefix-Caching]]、Sliding-Window-Attention
- **同类系统**：[[vLLM]]、[[DiffKV-SOSP25]]
- **同会议**：[[SOSP-2025]]
