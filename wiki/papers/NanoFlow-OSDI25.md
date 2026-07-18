---
type: paper
name: NanoFlow
full_title: "NanoFlow: Towards Optimal Large Language Model Serving Throughput"
authors: [Kan Zhu, Yufei Gao, Yilong Zhao, Liangyu Zhao, Gefei Zuo, et al.]
venue: OSDI
year: 2025
tags: [llm-inference, serving, intra-device-parallelism, throughput]
source_pdf: "[[osdi25-zhu-kan.pdf]]"
source_md: "[[osdi25-zhu-kan]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# NanoFlow: Towards Optimal Large Language Model Serving Throughput (OSDI 2025)

> **一句话总结**：常见 workload 下 LLM serving 端到端实为 compute-bound（单 op 仍可能 memory/network-bound），但引擎串行执行异构 op 导致 compute 利用率仅 ~40%；NanoFlow 拆 nano-batch 并行 nano-op + 两阶段 auto-search _pipeline，LLaMA-2-70B 上吞吐 **1.91×** 于 [[vLLM]]/TensorRT-LLM 等，达理论最优 **50–72%**（8×A100 最高 **68.5%**）。

## 问题与动机

星球级 serving 关注 tokens/device/s。业界默认 LLM serving memory-bound（权重+[[KV-Cache]] 加载），但作者论证：batch 合并 prefill/decode、GQA、大模型 GEMM 主导时，**整体**受 compute 限制；然而 [[Attention]] decode 仍 memory-bound、TP 的 AllGather network-bound，现有引擎按 op 串行，瓶颈资源利用率 ~80% 但 compute 仅 ~40%。

## 关键观察 / 隐含假设

- **观察 1**：异构 op 瓶颈资源不同（黄=compute GEMM，绿=memory attention，蓝=network collective），同一设备内可 overlap 若拆成独立 nano-op。
  - **依赖假设**：额外 weight 加载可被 pipeline 隐藏（整体 compute-bound）。
  - **可能失效场景**：极小 batch 或极短 context 时可能回 memory-bound，auto-search 应重选 pipeline。
- **观察 2**：并行 kernel 争用 SM/cache 导致不可预测干扰，需二阶段 search：先无干扰模型，再 profile 修正。
  - **证据强度**：强——§6.2 展示干扰对 schedule 的影响。
- **假设 1**：ShareGPT/LMSys/Splitwise 等 practical workload 代表生产 mix。
  - **可能失效场景**：纯 prefill-heavy 或极端 MoE 通信模式可能改变最优 nano-batch 数。

## 核心方法

**Nano-batching**：切 input 为 nano-batch，duplicate op 为 nano-op，分配 GPU 资源比例并行跑。

**Auto-search**：阶段 1 定 nano 数/大小/顺序（无干扰）；阶段 2 profile 干扰重规划。

**Runtime**：组 batch、分资源、管 [[KV-Cache]]。

## 设计取舍

- **取舍 1**：duplicate op 增 memory traffic，换 compute 利用率（compute-bound 下划算）。
- **取舍 2**：搜索+profile 增加部署复杂度，换吞吐。
- **边界条件**：8×A100 DGX；LLaMA-2/3、Mixtral、Qwen 等。

## 实验与结果

- LLaMA-2-70B，ShareGPT/LMSys/Splitwise：vs SOTA **1.91×** 吞吐，**68.5%** of theoretical optimal（8×A100）。
- 多模型（LLaMA-3-70B/8B、Qwen2-72B、Deepseek-67B、Mixtral 8×7B）：**50–72%** of optimal，平均 **2.66×** vs [[vLLM]]。
- 低负载延迟接近最佳 TensorRT-LLM；SLO 内请求率 **1.64×**。

## Critical Analysis

### 论证链条

Cost model + profiling 证明 compute-bound → 串行导致低 util → nano pipeline + search → 多模型/multi-workload 提升，逻辑完整。理论最优来自简化模型，68.5% 说明仍有 30%+ 差距待解释（干扰、内存碎片等）。

### 假设压力测试

MoE all-to-all 是否与 GEMM overlap 安全？多节点 TP 下「intra-device」是否仍足够？功耗与 tail latency 论文相对吞吐次要。

### 实验可信度

Baseline 含 vLLM、TensorRT-LLM、FastGen 等强对手；单节点 8×A100 与 planet-scale 多机差距需读者外推。

### 系统性缺陷

论文未讨论与 [[Continuous-Batching]]/[[Chunked-Prefill]] 正交集成复杂度；search 失败或 workload drift 时的退化策略未强调。

## 局限与 Future Work

- **局限 1**：单节点 intra-device 为主，跨节点 pipeline 未展开。
- **Future work 1**：与 prefill-decode [[Disaggregation]] 联合调度。
- **Future work 2**：在线 workload 变化时 pipeline 增量重搜。

## 相关

- **相关概念**：[[KV-Cache]]、[[Attention]]、[[Continuous-Batching]]、[[Chunked-Prefill]]
- **同类系统**：[[vLLM]]、TensorRT-LLM、DeepSpeed-FastGen
- **同会议**：[[OSDI-2025]]
