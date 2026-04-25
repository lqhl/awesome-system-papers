---
type: paper
name: Jenga
full_title: "Jenga: Effective Memory Management for Serving LLM with Heterogeneity"
authors: [Chen Zhang, Kuntai Du, Shu Liu, Woosuk Kwon, Xiangxi Mo, et al.]
venue: SOSP
year: 2025
tags: [llm-inference, kv-cache, memory-management, vllm, heterogeneous-attention]
source_pdf: "[[3731569.3764823.pdf]]"
source_md: "[[3731569.3764823]]"
---

# Jenga: Effective Memory Management for Serving LLM with Heterogeneity (SOSP 2025)

> **一句话总结**:针对异构 LLM(混合 full-attention / sliding window / Mamba / VLM / 推测解码)的 KV cache 管理框架,用 LCM(最小公倍数)两层 slab 分配器消除碎片,并按每层 attention 属性定制 prefix cache 淘汰策略,在 vLLM 基线上把内存利用率提升 79.6%,吞吐提升 1.46× 平均(最高 4.92×),单节点能跑 Llama 4 完整 10M context。

## 问题

[[PagedAttention]]([[vLLM]] 的核心算法)假设所有层的 [[KV-Cache]] embedding 大小一致、所有层都做全注意力。但现代 LLM 架构严重异构:
- **embedding 大小不同**:VLM(图像 token embedding vs 文本 token KV)、[[Mamba]] 与 [[Attention]] 混合(Mamba state 远大于单 token KV)
- **attention 机制不同**:Gemma-3 把 full attention 和 sliding window 交错;Hymba 加入 Mamba;Llama 4 local attention;交叉注意力 VLM

这造成 PagedAttention 内存利用率极低——Llama 3.2 11B Vision 浪费 79.6% 内存,Gemma-3 在 Mooncake trace 上浪费 73.6%。朴素方案如 max-page(取最大页大小)或静态分区均无法适应动态 workload。

## 核心方法

Jenga 针对异构性提出两个关键组件:

1. **LCM allocator(两层 slab)**:底层用固定大小大页,大小为所有 embedding 大小的最小公倍数(例如 2KB、3KB 的 LCM 是 6KB),上层把大页按需切成不同 embedding 的小页。这是经典 [[Slab-Allocator]] 的一个特例,能完全消除内部碎片同时适应 workload 变化。
2. **属性感知的 prefix cache**:基于每层 attention 机制的访问模式(sliding window 只需最后若干 token、Mamba 只需最后 1 个 token、cross-attention 与 full-attention 分别处理 image/text token)定制淘汰策略,同时保持各层 cache hit 长度均衡(因为任何一层 miss 都会触发全模型重算)。引入 **common-prefix predictor** 指导哪些 token 该 cache,再用 **prefix cache simulator** 在 cache hit 和 batch size 之间找 tradeoff。

实现为 [[vLLM]] 插件,覆盖 VLM、推测解码 draft/target 双模型 KV、异构 attention 层等多种场景。

## 关键结果

- GPU 内存利用率提升 up to 79.6%(相对 vLLM)
- 吞吐提升 up to 4.92×,平均 1.80×(另一版本数字:up to 2.16×,平均 1.46×)
- 单个 8×H200 节点能跑 Llama 4 完整 10M context length(vLLM 只到 3.6M)
- 端到端延迟无退化
- 已被工业伙伴部署到生产

## 相关

- **相关概念**:[[KV-Cache]]、[[PagedAttention]]、[[Prefix-Caching]]、[[Sliding-Window-Attention]]、[[Mamba]]、[[Slab-Allocator]]
- **同类系统**:[[vLLM]]、[[SGLang]]
- **同会议**:[[SOSP-2025]]
