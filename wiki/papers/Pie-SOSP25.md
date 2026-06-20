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
---

# Pie: A Programmable Serving System for Emerging LLM Applications (SOSP 2025)

> **一句话总结**：[[vLLM]]/TGI 单体 prefill-decode 环无法支撑 tree-of-thought、agent tool loop 等需细粒度 [[KV-Cache]] 与采样控制的应用；Pie 拆成 embedding/forward/sampling 等 handler，用 Wasm **inferlet** 编排，标准任务 **3–12%** 延迟 overhead，Graph-of-Thought/agent **1.3–3.4×** 吞吐。

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
- **边界条件**：传统 completion overhead **3–12%**；GoT/agent **1.1–2.4×** latency、**1.3–3.4×** throughput。

## 实验与结果

- 标准 text completion：**3–12%** latency overhead vs SOTA
- Graph-of-Thought / agent：**1.1–2.4×** 更低延迟、**1.3–3.4×** 更高吞吐
- 实现 attention 变体、constrained/speculative decoding、deliberate prompting 等为 inferlet

## Critical Analysis

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

## 局限与 Future Work

- **局限 1**：标准任务有小 overhead。
- **局限 2**：需要 inferlet 编程模型学习成本。
- **Future work 1**：inferlet 模板库 + auto-batcher 测量 fragmentation 下吞吐地板。
- **Future work 2**：与 [[DiffKV]] 差异化 KV 在 inferlet 内显式控制 vs 系统隐式策略对比。

## 相关

- **相关概念**：[[LLM-Inference]]、[[KV-Cache]]、[[vLLM]]、[[WebAssembly]]、[[Speculative-Decoding]]
- **同类系统**：[[SGLang]]、Parrot、TensorRT-LLM、[[Pie]]
- **同会议**：[[SOSP-2025]]