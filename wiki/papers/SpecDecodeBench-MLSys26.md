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

> **一句话总结**：首次在生产级 [[vLLM]] 上系统评测 n-gram / EAGLE / EAGLE-3 / Draft-Model / MTP 等 [[Speculative-Decoding]] 变体，发现验证阶段开销主导、接受行为在 position/request/dataset 三层高度异质，实测与理论上界差距大；自适应组合多方法可达 4.9× 端到端加速。

## 问题

过去 [[Speculative-Decoding]] 评测存在三大缺陷：
1. **prototype 实现**而非生产级 inference engine——缺少 CUDA graphs 等关键优化
2. **batch size = 1** 不符合真实部署
3. 只看 average latency、dataset-level acceptance rate 等高层指标，缺少时间/内存拆解和 position-level 分析

问题：到底 SD 在真实部署下值多少加速？不同变体适合什么场景？距离理论上界还有多远？

## 核心方法

**实验设置**：
- 引擎：vLLM v0.10.1.1（默认开启 KV cache mgmt、continuous batching、chunked prefill、CUDA Graphs）
- 模型：Llama3.1-8B、Llama3-70B、Qwen3-8B、GLM-4.5-Air-106B
- 变体：Draft-model based、EAGLE / EAGLE-3、MTP、n-gram（prompt lookup）
- Workload：CNN/DailyMail、ShareGPT、InstructCoder、GSM8K、AIME22-24、GPQA-Main
- 用 token throughput 而非 latency（输出长度因 GPU 非确定性而抖动）

**分析维度**：
- 时间/内存拆解（propose、verify、system overhead）
- Acceptance 在 position / request / dataset 三层的异质性
- Tree-style（k=6, 21） vs chain-style（k=3）verification

**理论上界模拟器**：
- 构建 simulator：在"所有提议 token 都被接受"的理想场景下评估
- 展示观测值与上界的 gap，标示改进方向
- 按 position-specific acceptance 数据自适应组合多 SD 方法

## 关键结果

- **所有 SD 变体都快过 baseline**，但加速随 batch size 增大单调降低——70B 受影响更明显（从 1.96× 降到 1.72×）
- **Verification 主导执行时间**；低接受率时的"白跑"成本在高负载下会让 SD 比普通 decode 还慢
- **n-gram 在 code-editing（InstructCoder）惊艳**：利用 token 复用，Llama3.1-8B 甚至超过 EAGLE-3
- **Draft-model 在 70B 最强**，但 8B 上 proposing 开销占比从 12.5% 涨到 37.5%，被 EAGLE-3 反超
- **Tree verification** 仅在 batch=1 略优；batch=64 时 k=21 树直接跌破 1× speedup
- **Reasoning workloads**（长 CoT 生成）上 EAGLE-3 和 n-gram 收益最大，MTP 受限于共享 head
- **自适应组合多方法**可达 **4.9× 端到端加速**

## 相关

- **相关概念**：[[Speculative-Decoding]]、[[KV-Cache]]、[[Chunked-Prefill]]
- **同类系统**：[[vLLM]]、[[SGLang]]、EAGLE / EAGLE-3、Medusa、MTP
- **同会议**：[[MLSys-2026]]
