---
type: paper
name: Agentix
full_title: "Agentix: An Efficient Serving Engine for LLM Agents as General Programs"
authors: [Michael Luo, Xiaoxiang Shi, Colin Cai, Tianjun Zhang, Justin Wong, et al.]
venue: NSDI
year: 2026
tags: [llm-agents, agent-serving, program-scheduling, preemption, long-horizon]
source_pdf: "[[nsdi26-luo-agentix.pdf]]"
source_md: "[[nsdi26-luo-agentix]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-17
---

# Agentix：把 LLM Agent 作为通用程序调度的服务引擎（NSDI 2026）

> **原题**：Agentix: An Efficient Serving Engine for LLM Agents as General Programs

> **一句话总结**：Agentix 发现多轮 agent 的主要延迟不是单次推理，而是 request-level 与 program-level 两层队首阻塞；它拦截程序的 LLM 调用并把已完成调用数作为进度信号进行抢占和优先调度，在多种 agent workload 上以相同 latency 将 program throughput 提高 4–15×（§6，图 8–13）。

## 问题与动机

现有 [[LLM-Inference]] engine 看到的是互不相关的 request，却看不到一个 agent program 内部的顺序、循环、并发和 tool dependency。长程任务会产生多次 LLM call；每一轮都重新进入 queue，少量慢调用又会拖住整个 program 的完成时间。

Agentix 的目标不是改 agent 的 planning quality，而是最小化 end-to-end program completion time：让已投入大量计算、接近完成的程序不被新请求反复插队。

## 关键观察 / 隐含假设

- **观察 1**：agent program 的累计 waiting time 可超过 model execution time，且来自 request 与 program 两级 HOL blocking（§2，图 2–3）。
- **观察 2**：已完成的 [[LLM|LLM]] call 数是无需理解程序语义即可获得的 progress proxy（§3）。
- **假设 1**：更多已完成调用通常意味着程序更接近结束。
  - **证据强度**：中；动态分支、retry 和递归 agent 可能使 call count 与剩余工作反相关。

## 核心方法

Agentix 在 agent runtime 与 serving engine 之间拦截 LLM call，为每个 request 附加 program identity 和已完成调用信息。单线程算法优先推进已有进度的 program，并在新 call 到来时抢占低优先级 decode。

对并行/分布式 program，系统避免一个 fan-out program 垄断所有 slot，将 program progress 与其 active calls 联合计分。实现与 [[vLLM]] 连续 batching 集成，保持 token-level preemption，不要求改 agent source logic。

## 设计取舍

- **program completion 优先于 request fairness**：显著降低长程序 JCT，但新程序或调用很多的程序可能等待更久。
- **黑盒 progress proxy**：接口简单，却无法识别关键路径、失败重试和高价值 branch。
- **边界条件**：收益随每个 program 的 call 数与 queue contention 增大；单轮 chatbot 几乎没有 program-level 信息可用。

## 实验与结果

- 多种 LLM 与 agentic workload 上，相同 latency 下 program throughput 相对 [[vLLM]] 等 baseline 提高 4–15×（§6.2–6.4，图 8–13）。
- 单线程与分布式 program scheduler 均降低 cumulative queueing；收益主要来自高并发、多调用 workflow（§6.3）。
- preemption 和 metadata tracking overhead 相对 model execution 较小，但论文没有覆盖 tool call side effect 或 cancellation safety（§6.5）。
- 结果衡量系统完成速度，不证明 agent task success、规划质量或 long-horizon reliability 提高。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| program-aware scheduling 优于 request-only | 相同 latency 下 throughput 4–15×（§6，图 8–13） | 选定 agent graph、模型与并发 | 强 |
| call count 可作为实用 progress proxy | 单/分布式 policy 对比（§6.3） | 分支结构未极端变化 | 中 |
| 集成开销较小 | scheduler/preemption microbenchmark（§6.5） | vLLM 实现与被测硬件 | 中强 |

## 批判性分析

### 论证链条

论文准确指出 serving abstraction 丢失 program context，并用最小 metadata 恢复一部分调度信息。4–15× headline 反映 baseline 在多轮 queueing 下很差，也依赖 program graph 和高 contention；它不是单次模型 inference speedup。

### 假设压力测试

program 可能在完成很多 call 后进入更大的 branch，或因 verifier 失败重跑；call count 会误判剩余工作。优先“接近完成者”也可能造成长程序、低优先级租户 starvation。

### 实验可信度

覆盖多种 agent workload 和两类程序结构，end-to-end JCT 指标正确。缺少生产 trace、任务成功率、tool latency distribution 与 admission fairness。

### 系统性缺陷

抢占 LLM decode 容易，抢占带副作用的 tool call 不容易；runtime 必须准确传播 program identity。调度器若看不到外部工具状态，仍可能优化错误的 critical path。

## 局限与后续工作

- 加入 critical-path/remaining-work estimator，并用 branch、retry、verifier failure 压测误判。
- 同时报告 task success、tenant fairness、P99 JCT 与 starvation，不能只报 aggregate throughput。

## 相关

- **相关概念**：[[LLM-Inference]]、[[Continuous-Batching]]、[[KV-Cache]]
- **同类系统**：[[vLLM]]、Continuum、FlashAgents
- **同会议**：NSDI 2026

