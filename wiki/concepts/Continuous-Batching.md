---
type: concept
aliases: [continuous batching, Continuous Batching, iteration-level scheduling, in-flight batching, dynamic batching, Orca-style batching]
parent: "[[LLM-Inference]]"
introduced_by: "[[Orca-OSDI22]]"
last_updated: 2026-05-26
tags: [llm-inference, scheduling, batching]
---

# Continuous-Batching

> 在 LLM serving 里把调度粒度从「请求级」降到「迭代级」：不再等整个 batch 跑完再接新请求，而是每 decode 一步就让已完成的请求退出、新请求插入。由 Orca (OSDI '22) 提出（iteration-level scheduling），[[vLLM]] 实现后成为事实标准。解决的问题是 LLM 请求输出长度高度异构——静态 batch 总被最长那条拖死。

## 核心思想

LLM 请求有两个阶段：

- **Prefill**：一次性算完 prompt 的 K/V，compute-bound
- **Decode**：一次一 token，memory-bound，可能持续 100-2000 步

如果按传统 batch serving 做（先凑齐 batch、跑完再释放），两个问题：

1. **短请求等长请求**：batch 里的短请求早就 EOS 了，但 GPU 仍给长请求的尾部算 decode，短请求的延迟 = 长请求的延迟
2. **新请求等当前 batch**：新请求到达时，要等当前 batch 整体完成才能入场

**Continuous batching** 的调度循环：

```
loop every iteration:
  remove finished sequences from running set
  admit new requests up to memory/compute budget
  run one decode step over current running set
```

每个 iteration 运行的 batch 是动态的：有的请求在 prefill，有的在 decode 第 5 步，有的在第 500 步，全都被拼成一个大 kernel call。

## 需要配套的基础设施

continuous batching 只是个调度原则，真正让它高效需要三个底层支撑：

1. **[[PagedAttention]] / [[KV-Cache]] 动态分配**：请求退出时立即释放 block，新请求按需分配，否则 batch 动态变化无法塞下
2. **varying-length kernel**：[[FlashAttention-2-ICLR24|FA2]]/[[FlashAttention-3-NeurIPS24|FA3]] 的 variable-length 支持，让一个 kernel call 能处理多条不同长度的序列（packing + cu_seqlens）
3. **prefill vs decode 混合**：纯 decode-only batch 算力闲置，混入 prefill 提升 utilization；但 prefill 步延迟大会 stall 所有 decode → [[Chunked-Prefill]] 把 prefill 切片插入 decode 步

## 衍生概念

- **[[Chunked-Prefill]]**：把 prefill 切成小块与 decode 共享 iteration，平滑 TTFT 与 TBT
- **Disaggregated serving ([[Disaggregation]])**：反向思路——承认 prefill/decode 冲突不可调和，直接拆到两组 GPU
- **Priority / SLO-aware 调度**：在 continuous batching 框架上加优先级，区分 P50/P99 目标

## 引用本概念的论文

- [[Meta-LLM-Deploy-MLSys26|Meta-LLM-Deploy]] — Meta 数百万配置模拟：在线 SLO 场景 disagg 优于 continuous batching，离线吞吐场景两者接近

- [[BatchLLM-MLSys26|BatchLLM]]、[[LayeredPrefill-MLSys26|LayeredPrefill]]、[[MixLLM-MLSys26|MixLLM]]、[[Stream2LLM-MLSys26|Stream2LLM]]、[[SuperInfer-MLSys26|SuperInfer]]、[[LAPS-MLSys26|LAPS]]、[[MorphServe-MLSys26|MorphServe]] — 进阶 serving 调度
- [[HELIOS-MLSys26|HELIOS]]、[[EventTensor-MLSys26|EventTensor]]、[[OptiKit-MLSys26|OptiKit]]、[[AXLearn-MLSys26|AXLearn]] — 训练 / multi-modal serving 里的 batching 变体
- [[OPKV-MLSys26|OPKV]] — recallable sparsity 需在 attention layer 间更新 metadata，与 iteration 级调度粒度不匹配；Sub Block Manager 本地化层间 recall
- [[BEAM-MLSys26|BEAM]] — 事件驱动联合调 batching 旋钮与 DVFS，在 TTFT/TBT SLO 下 GPU 能耗 -51%
- [[AgenticCache-MLSys26|AgenticCache]] — embodied agent 规划缓存减少逐步 LLM 调用，与 serving batching 正交互补
- [[TeleRAG-MLSys26|TeleRAG]] — batched RAG 用 prefetching scheduler 聚类 query 最大化 IVF cluster overlap
- [[AIRS-MLSys26|AIRS]] — Google Search Quality autorater 共享 TPU pool + batch=12 提 duty cycle
- [[CDLM-MLSys26|CDLM]] — block-causal DLM 并行 unmask 与 AR serving batching 对照
- [[ReSpec-MLSys26|ReSpec]] — RL 生成阶段按 active batch 动态开关 speculation
- [[FlashAgents-MLSys26|FlashAgents]] — MAS 链式依赖下 iteration 级 overlap 与 continuous batching 正交，专注 inter-agent 调度

## 相关概念

- 上游：[[LLM-Inference]]
- 互补：[[PagedAttention]]、[[KV-Cache]]、[[Chunked-Prefill]]
- 替代 / 正交：[[Disaggregation]]、[[Prefix-Caching]]
- 实现：[[vLLM]]、[[SGLang]]
