---
type: paper
name: BEAM
full_title: "BEAM: Joint Resource–Power Optimization for Energy-Efficient LLM Inference Under SLO Constraints"
authors: [Hyunjae Lee, Sangjin Choi, Seungjae Lim, Youngjin Kwon]
venue: MLSys
year: 2026
tags: [llm-serving, energy-efficiency, dvfs, slo, vllm]
source_pdf: "[[43ec517d68b6edd3015b3edc9a11367b.pdf]]"
source_md: "[[43ec517d68b6edd3015b3edc9a11367b]]"
---

# BEAM: Joint Resource–Power Optimization for Energy-Efficient LLM Inference Under SLO Constraints (MLSys 2026)

> **一句话总结**：BEAM 在 [[vLLM]] 上事件驱动联合调 GPU 频率、chunk size、microbatch，在 TTFT/TBT SLO 满足率 ~94% 下较 vanilla vLLM GPU 能耗降 **51%**、较 Window-DVFS **30%**。

## 问题

LLM inference 满足 per-request SLO 后仍有 latency slack，但 batching（资源轴）与 DVFS（功耗轴）被分别优化，错过全局能量最小。最优频率依赖 batch 形态，二者强耦合；prefill（TTFT）与 decode（TBT）目标冲突且资源纠缠。

## 核心方法

**Event-driven loop**：新 prefill 到达或任意请求完成时触发决策，steady-state 零开销。

**Phase-aware schedulers**：Prefill Scheduler 优化 TTFT；Decode Scheduler 优化 TBT，各用离线 profile 的 (num_tokens, frequency)→latency/energy 查表做 bounded search。

**Knobs**：[[Pipeline-Parallelism]] 下 chunk size、microbatch count + NVML DVFS，毫秒级应用。

## 关键结果

- vs vanilla [[vLLM]]：GPU 能耗 **-51%**（最高）
- vs Window-DVFS（DynamoLLM 风格）：能耗 **-30%**，TTFT SLO **94.9%**（-0.1pp）、TBT **94.5%**（-0.9pp）
- ~2000 token batch 较单 token：per-token latency/energy **~144×** 改善（batching 轴动机）

## 相关

- **相关概念**：[[Continuous-Batching]]、[[Chunked-Prefill]]、[[Pipeline-Parallelism]]
- **同类系统**：[[vLLM]]、DynamoLLM
- **同会议**：[[MLSys-2026]]