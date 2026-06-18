---
type: paper
name: SpecDecodeBench
full_title: "Speculative Decoding: Performance or Illusion?"
authors: [Xiaoxuan Liu, Jiaxiang Yu, Jongseok Park, Ion Stoica, Alvin Cheung]
venue: MLSys
year: 2026
tags: [speculative-decoding, benchmarking, llm-inference, vllm, measurement]
source_pdf: "[[f0935e4cd5920aa6c7c996a5ee53a70f.pdf]]"
source_md: "[[f0935e4cd5920aa6c7c996a5ee53a70f]]"
---

# Speculative Decoding: Performance or Illusion? (MLSys 2026)

> **一句话总结**：首次在生产级 [[vLLM]] 上系统评测 n-gram / EAGLE / EAGLE-3 / Draft-Model / MTP 等 [[Speculative-Decoding]] 变体，发现 verification 占 42–95% 执行时间、接受行为在 position/request/dataset 三层高度异质，实测与理论上界差距大；自适应组合多方法可达 **4.9×** 端到端加速。

## 问题

过去 [[Speculative-Decoding]] 评测存在三大缺陷：
1. **prototype 实现**而非生产级 inference engine——缺少 CUDA graphs 等关键优化
2. **batch size = 1** 不符合真实部署
3. 只看 average latency、dataset-level acceptance rate，缺少时间/内存拆解和 position-level 分析

问题：SD 在真实部署下到底值多少加速？不同变体适合什么场景？距离理论上界还有多远？

## 核心方法

**实验设置**：
- 引擎：vLLM v0.10.1.1（默认开启 [[KV-Cache]] 管理、[[Continuous-Batching]]、[[Chunked-Prefill]]、CUDA Graphs）
- 模型：Llama3.1-8B、Llama3-70B、Qwen3-8B、GLM-4.5-Air-106B
- 变体：Draft-model、EAGLE / EAGLE-3、MTP、n-gram（prompt lookup）
- Workload：CNN/DailyMail、ShareGPT、InstructCoder、GSM8K、AIME22-24、GPQA-Main
- 用 token throughput 而非 latency（输出长度因 GPU 非确定性而抖动）

**分析维度**：
- 时间/内存拆解（draft、verify、rejection sampling、system overhead）
- Acceptance 在 position / request / dataset 三层的异质性
- Tree-style（k=6, 21）vs chain-style（k=3）verification

**理论上界模拟器**：
- 理想场景下所有提议 token 均被接受，量化观测值与上界 gap
- 按 position-specific acceptance 自适应组合多 SD 方法

## 关键结果

- 所有 SD 变体均快于 baseline，但加速随 batch size 增大单调降低——70B 上 EAGLE 从 **1.96×→1.72×**（batch 1→32）
- **Verification 占 42–95%** 执行时间；低接受率时高负载下 SD 可慢于普通 decode
- **n-gram 在 InstructCoder 惊艳**：BLEU-4>0.6 时比 EAGLE-3 最高快 **53%**（proposal len=3），len=5 可达 **100%**
- **Draft-model 在 70B 最强**；8B 上 proposing 开销占比 **12.5%→37.5%**，被 EAGLE-3 反超
- Tree verification 仅 batch=1 略优；batch=64 时 k=21 树直接 **<1×**
- Reasoning workload 上 EAGLE-3 **1.64–1.80×**；自适应组合最高 **4.9×**
- 内存：n-gram 零额外开销；EAGLE 静态权重 +3–5%；draft-model 8B 配对 0.6B 时 per-token KV **1.77×**

## 相关

- **相关概念**：[[Speculative-Decoding]]、[[KV-Cache]]、[[Chunked-Prefill]]、[[Continuous-Batching]]
- **同类系统**：[[vLLM]]、[[SGLang]]、EAGLE / EAGLE-3、Medusa、MTP
- **同会议**：[[MLSys-2026]]