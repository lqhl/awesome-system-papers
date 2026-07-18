---
type: paper
name: LAPS
full_title: "LAPS: A LENGTH-AWARE-PREFILL LLM SERVING SYSTEM"
authors: [Jianshu She, Zonghang Li, Hongchao Du, Shangyu Wu, et al.]
venue: MLSys
year: 2026
tags: [llm-serving, prefill, disaggregation, scheduling, sglang]
source_pdf: "[[ec5decca5ed3d6b8079e2e7e7bacc9f2.pdf]]"
source_md: "[[ec5decca5ed3d6b8079e2e7e7bacc9f2]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# LAPS: A LENGTH-AWARE-PREFILL LLM SERVING SYSTEM (MLSys 2026)

> **一句话总结**：[[PD-Disaggregation]] 后 prefill 内长短请求仍互相干扰（mix 使 long-prefill P90 飙升）；LAPS 在 prefill 阶段再按长度拆池 + bucket 批处理 + CUDA Graph，多轮真实 trace 上 prefill 延迟 **>30%↓**，多实例 SLO 违约 **28%↓**，高并发吞吐 **35%↑**（Qwen2.5-32B）。

## 问题与动机

[[LLM]] serving 常用 [[PD-Disaggregation]]，但 prefill 池内 **long compute-bound prefill** 与 **short memory-bound prefill/re-prefill**（多轮聊天占 **81%** prompt <256）混批产生 compute–memory interference（Fig.1）。需在 prefill 内部再做 length-aware 调度，而非仅 PD 分离。

LAPS 提出第四类部署模式：**prefill batch temporal/spatial disaggregation**（与 mix、PD temporal、PD spatial 并列）。

## 关键观察 / 隐含假设

- 观察 1：re-prefill 因读历史 KV，在更短 L 下即转 memory-bound（统一 latency 模型给出 L_reprefill_m）。
  - **依赖假设**：LMsys-Chat-1M 分布代表生产 multi-turn。
  - **可能失效场景**：超长单轮 prompt 主导时 long pool 压力不同。

- **观察 2：长短混跑显著抬高 long-prefill P90，并发越高越严重。**
  - **依赖假设**：隔离长短池可消除互扰。
  - **可能失效场景**：两池资源静态划分可能在 skew burst 时一侧饥饿。

- **观察 3：short-prefill 侧 waiting window + length bucket + CUDA Graph 降 launch 开销、提高 batch 均匀性。**
  - **依赖假设**：SLO-aware scheduler 平衡 window 与吞吐。
  - **可能失效场景**：极低延迟 SLO 时 window 趋近 0，收益缩小。

- **假设 1**：与现有 PD 架构兼容，可叠加部署。**
  - **证据强度**：**强**——基于 [[SGLang]] 实测。

## 核心方法

**Dual prefill pools**：runtime 分 long/short，batch disaggregation 消除 interference。

**Short-prefill scheduler**：动态 waiting window；按输入长度 bucket；CUDA Graph cluster 执行。

**Multi-instance**：spatial 分离 + 负载感知在实例间调 long/short 负载。

## 设计取舍

- **四段 disaggregation vs 运维复杂度**：多池调度、路由规则增加，换 TTFT/SLO。
- **Bucket+window vs 即时调度**：提高 GPU 效率，可能略增 short 等待。
- **vs chunked prefill**：正交，LAPS 针对池内异构而非 prefill-decode 交错。
- **边界条件**：Qwen2.5-32B、H200；与 vanilla SGLang PD 对比。

## 实验与结果

- Prefill latency：**>30%↓** vs vanilla SGLang PD。
- Multi-instance SLO violations：**28%↓**（data-parallel）；vs SGLang router LB 再 **12%↓**。
- High concurrency mixed requests：prefill 吞吐 **35%↑**。
- 表征：63% 首轮 prompt <256 tokens；后续轮 **81%** <256。

## Critical Analysis

### 论证链条

PD 不够 → 表征 compute/memory 边界 → 池化+bucket → 多指标改进，逻辑闭合。两池容量配比是否需自适应是主要未闭环问题。

### 假设压力测试

[[RAG]] 超长单轮、agent 大 tool payload 可能重塑 long/short 比例。与 [[LAPS]] 名不同的 layer-wise 优化无涉。

### 实验可信度

真实 LMsys trace 动机；SGLang 集成可信。缺：与 [[LayeredPrefill]]/chunked 系统 head-to-head。

### 系统性缺陷

论文未讨论跨池迁移、冷启动池、global power cap。CUDA Graph 与 dynamic shape 冲突运维未深谈。

## 局限与 Future Work

- **局限 1**：双池静态容量可能 skew 敏感。
- **局限 2**：依赖 SGLang 栈特性。
- **Future work 1**：RL/反馈控制动态 long/short 实例比例。
- **Future work 2**：与 [[TokenWeave]]/[[Disaggregation]] 联合测端到端 TTFT。

## 相关

- **相关概念**：[[Disaggregation]]、[[Prefill]]、[[CUDA-Graph]]、[[SGLang]]
- **同类系统**：[[vLLM]]、chunked prefill、[[LayeredPrefill]]
- **同会议**：[[MLSys-2026]]
