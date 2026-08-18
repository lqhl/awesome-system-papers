---
type: paper
name: NEO
full_title: "NEO: Saving GPU Memory Crisis with CPU Offloading for Online LLM Inference"
authors: [Xuanlin Jiang, Yang Zhou, Shiyi Cao, Ion Stoica, Minlan Yu]
venue: MLSys
year: 2025
tags: [llm-inference, cpu-offloading, kv-cache, online-serving, scheduling, area/ai-infra]
source_pdf: "[[66a026c0d17040889b50f0dfa650e5e0.pdf]]"
source_md: "[[66a026c0d17040889b50f0dfa650e5e0]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-17
---

# NEO：以 CPU 卸载缓解在线 [[LLM|LLM]] 推理的显存危机（MLSys 2025）

> **原题**：NEO: Saving GPU Memory Crisis with CPU Offloading for Online LLM Inference

> **一句话总结**：NEO 观察到 decode attention 在 CPU/GPU 上都受内存带宽约束、而本地主机 CPU 常被闲置，于是只把部分请求的 attention 与 [[KV-Cache]] 卸载到 CPU，并用非对称流水线和在线负载调度隐藏通信；相对 GPU-only 在 T4/A10G/H100 上最高分别提高 7.5×/26%/14% 吞吐，同时保持相近延迟（§5、图 9–10）。

## 问题与动机

在线 [[LLM-Inference]] 依赖 batching 提高 GPU 利用率，但模型权重和随序列增长的 KV cache 共同限制 batch size。直接交换 KV cache 会被 PCIe 带宽限制；FlexGen 一类 layer-wise offload 又用高延迟换吞吐；FastDecode 则需要远端 CPU 集群，成本可能超过一块 A10G。

论文目标是在不改变模型精度和在线延迟的前提下，只利用 GPU 服务器自带的 CPU 与 DRAM 扩大有效 batch。难点是 CPU 明显弱于 GPU，而且真实请求的输入、输出长度动态变化，固定 offload 比例会迅速失配。

## 关键观察 / 隐含假设

- **观察 1**：decode [[Attention|attention]] 的算术强度低，CPU 与 GPU 的有效差距更接近内存带宽差距，而不是峰值 FLOPS 差距（§2.2）。
  - **依赖假设**：CPU 内存带宽仍有余量，且 attention kernel 能接近可用带宽。
  - **可能失效场景**：CPU 同时承担高负载 preprocessing、网络或多租户任务。
- **观察 2**：dense GPU operator 的执行时间可覆盖 token state 的 CPU/GPU 通信，A10G 实验中前者约为后者的 5–10 倍（§2.2）。
  - **依赖假设**：[[PCIe|PCIe]]/[[NUMA|NUMA]] 拓扑稳定，request mix 足以形成可重叠的两个 sub-batch。
- **假设 1**：增大 batch 带来的 GPU 利用率收益大于 CPU attention 与调度成本。
  - **证据强度**：中；T4/A10G/H100 的收益差异很大，说明 crossover 强依赖硬件。

## 核心方法

NEO 把请求分成 GPU-request 与 CPU-request。前者的 KV 全留在 HBM；后者的 KV 和 decode attention 放到 DRAM/CPU，但 linear、FFN 与 prefill 仍在 GPU。非对称流水线把 CPU-request 的 attention 与 GPU-request 的 dense computation、prefill 和 KV transfer 重叠，避免对半切 batch 导致 CPU 成为固定瓶颈。

负载感知调度器维护 prefill wait queue、GPU decode queue 和 CPU decode queue，每个 iteration 根据预计 GPU/CPU 时间、显存与队列积压决定新请求放置、迁移和 batch 构成（§3.2、附录 A）。实现基于 SwiftLLM，并用 Intel ISPC 生成 CPU attention kernel；这意味着机制可移植到 [[vLLM]]/[[SGLang]]，但论文没有展示移植成本。

## 设计取舍

- **部分卸载而非全量卸载**：保留 HBM 的 KV 容量和 GPU attention 带宽，同时使用 CPU；代价是两套 cache pool、迁移与调度状态。
- **在线 heuristic 而非离线最优计划**：适应输出长度不可预测，但最优性依赖执行时间估计准确。
- **边界条件**：低端 GPU、强 CPU、较长 decode 更有利；H100 上 GPU-only 已很强，收益只有最高 14%。

## 实验与结果

- 两个公开 trace、Llama-2-7B/Llama-3-8B/Llama-3.1-70B，覆盖 T4、A10G 和 8×H100；相同延迟下吞吐最高提高 7.5×、26% 和 14%（§5.2，图 9–10）。
- 更强 CPU 配合 A10G 时，吞吐最高提高 79.3%，显示 CPU memory bandwidth 是主要扩展轴（§5.5，图 14）。
- 相对 FastDecode+，NEO 在只用本机 CPU 的设定下维持在线 latency，并避免远端多 CPU server 的成本（§5.3）。
- 动态输入/输出长度与负载切换实验中，load-aware scheduling 优于固定 offload policy，但评测没有覆盖多租户 CPU contention（§5.4–5.5）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 本机 CPU 可在不牺牲在线延迟时提高吞吐 | T4/A10G/H100 最高 7.5×/26%/14%（§5.2，图 9–10） | 三类 GPU、三组模型与两个 trace | 强 |
| 非对称流水线优于全量或对称卸载 | pipeline breakdown 与 FastDecode+ 对比（§5.3、图 11） | SwiftLLM 实现；未在 vLLM 原生栈复现 | 中 |
| 调度能适应长度变化 | dynamic input/output sensitivity（§5.4） | 公开 trace；无突发 CPU 干扰 | 中 |

## 批判性分析

### 论证链条

论文从“显存限制 batch”到“CPU bandwidth 可用”，再以 partial offload 和 iteration scheduling 回应两类瓶颈，链条完整。最强证据来自跨三代 GPU 的收益梯度，它也同时表明 NEO 不是普适加速：GPU 越强、CPU 越弱，收益越小。

### 假设压力测试

NUMA 错放、CPU background service、PCIe oversubscription 或短 prompt/短 output 都可能使 overlap 窗口不足。CPU-request 的 KV 长期驻留也可能挤占 host memory，论文未评估多个模型共享一台 host 时的隔离。

### 实验可信度

硬件和模型覆盖较广，baseline 包含 GPU-only 与 FastDecode+。但核心实现基于 SwiftLLM 而非生产 vLLM；延迟分布、P99 和调度器 CPU overhead 的长期稳定性证据有限。

### 系统性缺陷

两套 KV pool 与 request migration 扩大了 scheduler 的状态空间；CPU 故障或进程抖动会直接进入在线关键路径。论文没有给出 admission control、租户隔离和 CPU overload 时的 fail-safe 策略。

## 局限与后续工作

- 在共享 CPU、NUMA 错放和 PCIe contention 下测 P99 与 crossover，给出自动关闭 offload 的安全阈值。
- 在原生 [[vLLM]]/[[SGLang]] 上复现，并测迁移成本、维护复杂度和多模型隔离。

## 相关

- **相关概念**：[[LLM-Inference]]、[[KV-Cache]]、[[Continuous-Batching]]、[[PagedAttention]]
- **同类系统**：[[vLLM]]、[[SGLang]]、FlexGen、FastDecode
- **同会议**：MLSys 2025

