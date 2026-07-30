---
type: paper
name: Pie
full_title: "Pie: A Programmable Serving System for Emerging LLM Applications"
authors: [In Gim, Zhiyao Ma, Seung-seob Lee, Lin Zhong]
venue: SOSP
year: 2025
tags: [llm-serving, programmability, wasm, kv-cache, inferlet]
source_pdf: "[[3731569.3764814.pdf]]"
source_md: "[[3731569.3764814]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# Pie：用于新兴 LLM 应用程序的可编程服务系统（SOSP 2025）

> **原题**：Pie: A Programmable Serving System for Emerging LLM Applications

> **一句话总结**：Pie 将生成流程拆为 handler，并以 Wasm inferlet 编排。对 Llama-3 1B/3B/8B text completion，其 TPOT 比 vLLM 高 2.39%–11.41%；若应用能利用显式 KV、I/O 与控制流，作者在限定工作流中测得更大的收益。

## 问题与动机

新兴 [[LLM-Inference]] 需：**R1** 应用级 KV 分配/驱逐/复用；**R2** 可定制 decode（speculative、MCTS、grammar）；**R3** 生成与 tool/API/代码执行紧耦合。现有系统全局 LRU/prefix cache、封闭 sampling loop、跨请求丢 KV 迫使昂贵 reprefill（round-trip + 状态丢失）。

## 关键观察 / 隐含假设

- **观察 1**： monolithic loop 优化 batched text completion，但 agent 工作流是「开环」——必须交还客户端才能 tool call。
  - **依赖假设**：handler API 粒度足够表达主流技术 yet 可高效 batch。
  - **可能失效场景**：inferlet 逻辑过重导致 Wasm 调度开销反超收益。
- **观察 2**：数百并发 inferlet 可各用不同优化（自定义 KV、spec decode、agent loop）共享同一引擎。
  - **依赖假设**：[[WebAssembly]] sandbox 够轻；GPU handler 仍集中批处理。
  - **可能失效场景**：极度碎片化 inferlet 使 batch 退化。
- **假设 1**：标准 completion 仅 3–12% overhead 可接受换可编程性。
  - **证据强度**：中强；advanced 任务 1.3–3.4× 增益显著。

## 核心方法

**Pie**： dismantle monolithic loop → **handlers**（embed、KV op、forward、sample…）。

**Inferlet**：用户 Wasm 程序（Rust/C++/Python 编译）调用 API 编排全流程。

分层架构；开源 https://github.com/pie-project/pie 。

## 设计取舍

- **取舍 1**：程序mability vs 默认易用性——开发者需写 inferlet 非仅 HTTP prompt。
- **取舍 2**：Wasm 安全 vs native 性能——热点仍在 GPU handler。
- **边界条件**：text completion 的 TPOT 结果限于 Llama-3 1B/3B/8B 与 L4；复杂工作流收益取决于 inferlet 与应用逻辑。

## 实验与结果

**指标、基线与边界**：TPOT、end-to-end latency、throughput；Pie vs vLLM/SGLang；Llama-3 1B/3B/8B、GCP G2/L4 或各任务指定 workload（§7）。

- text completion TPOT：8B 为 **65.59 ms vs 64.06 ms**，3B 为 **32.01 ms vs 30.30 ms**，1B 为 **18.75 ms vs 16.83 ms**（Pie vs vLLM，§7.4，Table 4）。
- 1B agent workflows（ReACT/CodeACT/Swarm，分别 8/8/32 次外部 I/O）中，Pie 记录 **4.27/3.18/6.14 s** 和 **29.94/40.18/5.21 agents/s**；在该实现中相对 vLLM/SGLang 最多降低 **15%** 延迟、提高 **30%** 吞吐（§7.1，Fig.6）。
- deliberate prompting 的简化任务中，最多降低 **28%** 延迟、提高 **34%** 吞吐（§7.2）。

## 论断—证据表

| 论断 | 证据 | 指标 / 基线 / 评测边界 | 定位 | 置信度 |
|---|---|---|---|---|
| 标准 completion 的可编程性代价较小 | TPOT 增加 2.39%（8B）、5.64%（3B）、11.41%（1B） | Pie vs vLLM；Llama-3、L4、BF16 | §7.4，Table 4 | high |
| agent 结果依赖于具体外部 I/O 工作流 | ReACT/CodeACT/Swarm 的 latency 与 agents/s 如上；最多 15%/30% 改善 | 1B、8/8/32 external I/O；vs vLLM/SGLang Python client | §7.1，Fig.6 | high |
| deliberate prompting 有受限的端到端收益 | 最多 28% latency 降低与 34% throughput 提升 | ToT/RoT arithmetic、GoT summarization，指定分支深度 | §7.2 | high |
| 应用语义优化可带来较大吞吐改善 | 同时保留 API-doc KV、并发 API、丢弃一次性 KV 时为 3.5× | 作者构造的典型 agent workflow；vs vLLM Python workflow | §7.2，Fig.7 | high |
| adaptive batching 在饱和条件下优于三种固定策略 | 128 inferlets 时 84.85 req/s；Eager/K-only/T-only 为 5.61/30.09/78.11 | fully saturated scheduler、128 concurrent inferlets | §7.4，Table 5 | high |

## 批判性分析

### 论证链条

三限制清晰 → handler+inferlet → 先进应用大幅赢、基准小亏，trade-off 诚实。到「替代 vLLM 默认路径」需生态（inferlet 库、debug、监控）成熟——论文开源第一步。

### 假设压力测试

- **安全**：inferlet 调 handler 的授权与 quota；恶意 inferlet 占 KV 耗尽 GPU。
- **批处理**：per-inferlet 自定义 sampling 使 central scheduler NP-hard 近似启发式稳定性未知。
- **与 [[HedraRAG]]**：RAG 工作流可用 inferlet 表达，但是否比 RAGraph 自动优化更省力因团队而异。

### 实验可信度

Yale 团队、多 emerging benchmark；SOTA 对比公平性需看 inferlet 手工优化程度。缺超大并发 production trace。

### 系统性缺陷

运维复杂度（数百 inferlet 版本）、多租户隔离、与 K8s autoscaling 集成论文未讨论。Wasm 调试 GPU 异步错误栈困难。

## 局限与后续工作

- **局限 1**：标准任务有小 overhead。
- **局限 2**：需要 inferlet 编程模型学习成本。
- **Future work 1**：inferlet 模板库 + auto-batcher 测量 fragmentation 下吞吐地板。
- **Future work 2**：与 [[DiffKV]] 差异化 KV 在 inferlet 内显式控制 vs 系统隐式策略对比。

## 相关

- **相关概念**：[[LLM-Inference]]、[[KV-Cache]]、[[vLLM]]、[[WebAssembly]]、[[Speculative-Decoding]]
- **同类系统**：[[SGLang]]、Parrot、TensorRT-LLM
- **同会议**：[[SOSP-2025]]
