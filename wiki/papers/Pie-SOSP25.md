---
type: paper
name: Pie
full_title: "Pie: A Programmable Serving System for Emerging LLM Applications"
authors: [In Gim, Zhiyao Ma, Seung-seob Lee, Lin Zhong]
venue: SOSP
year: 2025
tags: [llm-serving, programmable, webassembly, kv-cache, agentic-workflow]
source_pdf: "[[3731569.3764814.pdf]]"
source_md: "[[3731569.3764814]]"
---

# Pie: A Programmable Serving System for Emerging LLM Applications (SOSP 2025)

> **一句话总结**：Pie 把传统 LLM 服务单体 prefill-decode 循环拆成 42 个细粒度 handler，通过 WebAssembly 沙箱里的 "inferlet" 用户程序编排生成流程，标准任务仅 3-12% 额外延迟，agentic workflow 则吞吐高 1.3-3.4×、延迟低 1.1-2.4×。

## 问题

现有 LLM 服务系统（[[vLLM]]、TGI、甚至 [[SGLang]]、Parrot）架构都围绕"prefill-decode 单体循环 + 全局批处理"，三方面限制日益严重：(R1) [[KV-Cache|KV cache]] 的分配/驱逐/复用只能走 LRU 或 prefix cache 这类系统级启发式，tree-of-thought、graph-of-thought、beam search、attention sink 等需要显式 per-request KV 控制的策略难以表达（vLLM 一度考虑移除 beam search）；(R2) 解码流程"predict-then-sample"固定耦合，speculative decoding、parallel decoding、MCTS、grammar-constrained、watermarking 要么得改系统深处，要么只能全局开关；(R3) agentic 工作流需要在生成中插入外部工具调用、I/O、符号检查，现有系统只能返回客户端再重开 request，丢失 KV cache 并 re-prefill。

## 核心方法

Pie 的核心是把控制权交出：应用用自己写的 **inferlet** 程序（任何可编译到 WebAssembly 的语言：C++、Rust、Python）通过 API 调用细粒度 handler 来自己编排生成。Pie 本身把 [[Transformer]] forward pass 拆成三阶段 handler：(1) **embed**（文本/图像 → embedding）；(2) **forward**（输入 Embed/KvPage → 输出 Embed/KvPage，可传 attention mask 或由 position 推断）；(3) **sample**（输出 embedding → next-token 分布/token ID）。共 42 个 API，18 个核心 + 24 个运行时（inter-inferlet 通信、HTTP、消息队列等）。

两大抽象资源：**Embed**（per-token 分配，便于操纵单个 token 表示）与 **KvPage**（8-32 token 连续 KV，仿 [[PagedAttention]]），inferlet 显式 alloc/dealloc，可通过 import/export 跨 inferlet 共享。**Command queue** 让 inferlet 表达 API 调用依赖 + 优先级，batch scheduler 做**纵向批处理**（同一 queue 里连续 forward 可合批）。

三层架构：inferlet 在应用层跑；控制层做资源虚拟化、物理/虚拟 KV 地址映射、batch 调度；推理层把批次展开到 GPU kernel。WebAssembly 提供轻量沙箱，可并发跑数百 inferlet、每个采用不同优化策略。现有所有系统本质上只运行"一个固定 inferlet"（自回归循环）。

## 关键结果

- 标准文本补全任务：与 SOTA 持平，3-12% 延迟开销
- Graph-of-Thought 与 agentic workflow：延迟低 1.1-2.4×、吞吐高 1.3-3.4×
- 实现覆盖多种高级算法：attention sink、speculative decoding、constrained decoding、deliberate prompting、agentic workflow
- 开源：https://github.com/pie-project/pie

## 相关

- **相关概念**：[[KV-Cache]]、[[PagedAttention]]、[[Speculative-Decoding]]、[[Attention]]、[[WebAssembly]]、[[Transformer]]
- **同类系统**：[[vLLM]]、[[SGLang]]、Parrot、TGI
- **同会议**：[[SOSP-2025]]
