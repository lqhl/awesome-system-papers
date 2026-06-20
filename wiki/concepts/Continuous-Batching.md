---
type: concept
aliases: [continuous batching, Continuous Batching, iteration-level scheduling, in-flight batching, dynamic batching, Orca-style batching]
parent: "[[LLM-Inference]]"
introduced_by: "[[Orca-OSDI22]]"
last_updated: 2026-06-20
tags: [llm-inference, scheduling, batching]
---

# Continuous-Batching

> 把 LLM serving 调度粒度从「请求级」降到「迭代级」：每 decode 一步就让已完成请求退出、新请求插入，不再等整个 batch 跑完。由 Orca (OSDI '22) 提出 iteration-level scheduling，[[vLLM]] 实现后成为事实标准——解决输出长度高度异构下静态 batch 被最长请求拖死的问题。

## 核心思想

LLM 请求分两阶段：
- **Prefill**：一次性算完 prompt 的 K/V，compute-bound
- **Decode**：一次一 token，memory-bound，可能持续数百至数千步

传统 request-level batching 的问题：短请求 EOS 后仍占 GPU 等长请求；新请求须等当前 batch 整体完成。Continuous batching 每 iteration 重组 running set：

```
loop every iteration:
  remove finished sequences
  admit new requests up to memory/compute budget
  run one decode step over current running set
```

每步 batch 动态混合：有的在 prefill，有的在 decode 第 5 步，有的在第 500 步，拼成一个大 kernel call。[[vLLM-SOSP23|vLLM]] 强调：Orca 解决时间维 interleaving，[[PagedAttention]] 解决空间维 memory utilization——二者互补。

## 为什么重要

Continuous batching 是 modern serving 栈的默认调度范式，但论文反复指出它只解决「时间维」问题，不自动解决 memory、phase 冲突与 SLO 权衡：

[[Meta-LLM-Deploy-MLSys26|Meta-LLM-Deploy]] 用近十亿 MAU 生产模拟器发现：在线严格 SLO 下 [[Disaggregation]] 比 continuous batching QPS 高 1.5–2.2×，因 decode batch 可远大于 mixed batch；离线吞吐场景两者趋同。[[LayeredPrefill-MLSys26|LayeredPrefill]] 指出 [[MoE]] + [[Chunked-Prefill]] 的 hybrid batch 会触发 sparsity erosion——小 chunk 激活几乎全部 expert 却达不到 ridge point。[[OPKV-MLSys26|OPKV]] 发现 recallable sparsity 需在每层 attention 间毫秒级更新 metadata，与 iteration 级中心化 RPC 粒度不匹配。

这些观察说明 continuous batching 是必要基础设施，但不是 serving 优化的终点——需要 [[PagedAttention]]、chunked/layered prefill、disaggregation 或 SLO-aware scheduler 配套。

## 关键观察 / 隐含假设

- **观察 1：输出长度高度异构使 request-level batching 在延迟与利用率上双重低效。** [[vLLM-SOSP23|vLLM]] 引用 ShareGPT/Alpaca trace 中输入/输出长度分布高度偏斜；短请求延迟被长请求绑架。
- **观察 2：iteration 级调度需要 varying-length kernel 与动态 KV 分配配套。** [[FlashAttention-2-ICLR24|FlashAttention-2]] 的 variable-length 支持（packing + cu_seqlens）让一个 kernel call 处理多条不同长度序列；无 [[PagedAttention]] 则 batch 动态变化无法塞下。
- **观察 3：prefill 与 decode 混跑改善 utilization，但大 prefill 步会 stall 所有 decode。** [[Chunked-Prefill]] 切片 prefill 与 decode 共享 iteration；[[LayeredPrefill-MLSys26|LayeredPrefill]] 在 MoE 上进一步把调度轴从 token 换到 layer group。
- **观察 4：在线严格 SLO 下 disagg 常优于 co-located continuous batching。** [[Meta-LLM-Deploy-MLSys26|Meta-LLM-Deploy]]：70B online disagg QPS 1.5–1.8×、405B 1.8–2.2×；decode batch 可远大于 mixed batch（如 112 vs 28）。
- **观察 5：iteration 级 metadata 更新与层间 recall 时间尺度冲突。** [[OPKV-MLSys26|OPKV]] 的 Sub Block Manager 本地化层间 recall，因 centralized iteration RPC 无法满足毫秒级 sparsity 需求。

## 设计空间与取舍

- **纯 continuous batching（Orca / vLLM 默认）**：实现简单、吞吐高；prefill/decode 硬件需求互相妥协，紧 SLO 下可能不足。
- **Chunked prefill（[[Chunked-Prefill]]）**：token 维切片与 decode 混跑，平滑 TTFT/TBT；MoE 上引发 sparsity erosion（[[LayeredPrefill-MLSys26|LayeredPrefill]]）。
- **Layered prefill（[[LayeredPrefill-MLSys26|LayeredPrefill]]）**：layer group 维调度，消除跨 chunk expert 重载；实现与 KV 跨 group 状态更复杂。
- **Disaggregated serving（[[Disaggregation]]）**：承认 prefill/decode 冲突不可调和，拆到两组 GPU；代价是 KV 跨池传输。
- **SLO-aware 扩展（[[SuperInfer-MLSys26|SuperInfer]]、[[BEAM-MLSys26|BEAM]]）**：在 continuous batching 框架上加 VLT/LVF rotation 或事件驱动 DVFS，区分 TTFT/TBT 目标。
- **Priority / admission control**：区分 P50/P99、multi-tenant fairness；论文多假设 FCFS，尾延迟讨论较少（[[vLLM-SOSP23|vLLM]] Critical Analysis）。

## 引用本概念的论文

- [[Orca-OSDI22|Orca]] — iteration-level scheduling 原始提出
- [[vLLM-SOSP23|vLLM]] — PagedAttention + continuous batching 生产实现
- [[Meta-LLM-Deploy-MLSys26|Meta-LLM-Deploy]] — 在线 SLO 下 disagg 优于 continuous batching，离线两者接近
- [[LayeredPrefill-MLSys26|LayeredPrefill]] — MoE 上 chunked prefill 的 sparsity erosion 与 layer 维替代
- [[OPKV-MLSys26|OPKV]] — iteration 级调度与层间 recall 粒度不匹配
- [[SuperInfer-MLSys26|SuperInfer]] — SLO-aware rotary scheduling 在 vLLM continuous batching 上扩展
- [[BEAM-MLSys26|BEAM]] — 事件驱动联合调 batching 旋钮与 DVFS，GPU 能耗 -51%
- [[BatchLLM-MLSys26|BatchLLM]]、[[MixLLM-MLSys26|MixLLM]]、[[Stream2LLM-MLSys26|Stream2LLM]]、[[LAPS-MLSys26|LAPS]]、[[MorphServe-MLSys26|MorphServe]] — 进阶 serving 调度
- [[HELIOS-MLSys26|HELIOS]]、[[EventTensor-MLSys26|EventTensor]]、[[OptiKit-MLSys26|OptiKit]] — 训练/multi-modal serving 的 batching 变体
- [[ReSpec-MLSys26|ReSpec]] — RL 生成阶段按 active batch 动态开关 speculation
- [[FlashAgents-MLSys26|FlashAgents]] — MAS 链式依赖下 iteration 级 overlap 与 continuous batching 正交
- [[TeleRAG-MLSys26|TeleRAG]] — batched RAG prefetching scheduler 聚类 query
- [[AIRS-MLSys26|AIRS]] — 共享 TPU pool + batch=12 提 duty cycle
- [[CDLM-MLSys26|CDLM]] — block-causal DLM 并行 unmask 与 AR serving batching 对照
- [[AgenticCache-MLSys26|AgenticCache]] — agent 规划缓存减少逐步 LLM 调用，与 serving batching 正交互补
- [[FlashAttention-2-ICLR24|FlashAttention-2]] — variable-length attention kernel 支撑 mixed prefill/decode batch

## 已知局限 / 开放问题

- prefill/decode 混跑在 MoE、紧 TBT SLO、长 prompt 下结构性低效，需 chunked/layered/disagg 补救
- overload 下 swapping + FCFS gang preemption 可能造成队列堆积与尾延迟恶化（[[vLLM-SOSP23|vLLM]]）
- 多轮对话不在轮次间保留 KV 的实验设定与真实 chat 产品差距大
- recallable sparsity、speculative rejection 等需比 iteration 更细粒度的 metadata 同步