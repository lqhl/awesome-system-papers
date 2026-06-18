---
type: paper
name: AccelOpt
full_title: "AccelOpt: A Self-Improving LLM Agentic System for AI Accelerator Kernel Optimization"
authors: [Genghan Zhang, Shaowei Zhu, Anjiang Wei, Zhenyu Song, Allen Nie, Zhen Jia, Nandita Vijaykumar, Yida Wang, Kunle Olukotun]
venue: MLSys
year: 2026
tags: [llm-agent, kernel-optimization, code-generation, trainium, beam-search]
source_pdf: "[[19ca14e7ea6328a42e0eb13d585e4c22.pdf]]"
source_md: "[[19ca14e7ea6328a42e0eb13d585e4c22]]"
---

# AccelOpt: A Self-Improving LLM Agentic System for AI Accelerator Kernel Optimization (MLSys 2026)

> **一句话总结**：把 AI accelerator kernel 优化建模为 LLM agent 的 beam search + optimization memory 问题，在 AWS Trainium NKI 上自主把 peak throughput 从 49% 提到 61%（Trainium 1）/45% 提到 59%（Trainium 2），用 gpt-oss-120b + Qwen3-Coder-480B 开源组合匹配 Claude Sonnet 4 性能但成本低 **26×**。

## 问题

新兴 AI 加速器（Trainium、Cerebras、Groq、TPU 等）架构与 GPU 差异大，缺乏成熟的优化启发式。以 AWS Trainium + NKI（Neuron Kernel Interface）为例，H100 的 attention kernel 从发布到 85% peak 用了两年人力调优；新加速器投产即面临同样困境。已有 LLM 生成 kernel 的工作多针对 GPU，且依赖专家注入硬件知识。两大挑战：(1) 优化空间巨大（memory layout、并行化、调度策略），LLM 查询成本高，需要高效探索；(2) 如何让系统**自主**在没有人工 heuristic 的前提下累积优化经验。

## 核心方法

AccelOpt = beam search + optimization memory + 三 agent 工作流。

**三 Agent Workflow**：
- **Planner**：根据当前 kernel 候选和 optimization memory 提出优化 plan。
- **Executor**：把 plan 实现成代码，验证正确性并 profile 性能。
- **Summarizer**：从成功优化中提取可复用 insight。

**Beam Search（Algorithm 1）**：
- 每轮维护 B 个 candidate kernel。每个 candidate 让 planner 生成 N 个 plan，每个 plan 让 executor 尝试 K 次，共产生 B × N × K 个 kernel。
- 候选选择函数 β：每个 plan group 取最快正确 kernel 构成代表池，再选 top-B；不足用上一轮候选填充（给难任务分配更多 sampling 预算）。
- 消融表明 beam search 比 repeated sampling 更有效（累积性改进）。

**Optimization Memory Curation（Algorithm 2）**：
- 维护容量 ExpN 的 experience 队列，每轮追加最多 TopK 个新条目（FIFO）。
- 每个 experience = slow-fast kernel pair 的伪代码 + summarizer 总结的 generalizable 策略。
- **正/负 rewrite 都存**：baseline → faster（positive, 阈值 $t_{pos}=1.04$）；slower → baseline（negative, 阈值 $t_{neg}=1.15$）。负样本捕获失败尝试。
- 按 (candidate, plan) 分组选 outlier，防止相似高 speedup 案例占满内存。
- Memory + beam search 比纯 beam search 节约 16–17% cost 达成同样 speedup。

**NKIBench**：作者构建 14 个 NKI kernel 的 benchmark，覆盖 Matmul、BatchMatmul、GQA、Mamba block、LoRA 等，**用 roofline model 算理论峰值**，用 "% of peak" 而非相对 speedup 作为指标。

**Profiling Service**：多机分布式，利用 core-level + machine-level 并行，对 B × N × K 个 kernel 并发 profile，core 轮转缓解性能波动。

## 关键结果

- Trainium 1：平均 peak throughput 从 **49% → 61%**；Trainium 2：**45% → 59%**。
- 开源 LLM 组合（Qwen3-Coder-480B executor + gpt-oss-120b 其他 agent）匹配 Claude Sonnet 4（thinking mode）但成本低 **26×**；Claude 作 AccelOpt backbone 比 repeated sampling 省 **3.3×**。
- Mamba：从 28.4% baseline 自主优化到 **54.6% peak**（1.04× 最佳人工 52.7%）；RoPE：**21.1% → 29.6%**（1.4× 人工参考）。
- FlashInfer-Bench（H100 Triton）泛化：平均 **1.27×** speedup，GQA decode 峰值 **3.19×**。
- 发现的优化包括 peephole（代数化简、rsqrt fusion、SiLU → x·sigmoid(x)）和非局部 loop 变换（BatchMatmul+Softmax 去 memory spilling 的多步推理）。

## 相关

- **相关概念**：LLM-Agent、Beam-Search、Roofline-Model、Test-Time-Learning
- **同类系统**：KernelTuner、PIKE、TritorX、[[LLaMEA-KernelTuner-MLSys26]]
- **同会议**：[[MLSys-2026]]