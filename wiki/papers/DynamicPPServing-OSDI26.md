---
type: paper
name: DynamicPPServing
full_title: "Revisiting Pipeline Parallelism for LLM Serving"
authors: [Soonjae Hwang, Jeongseob Ahn]
venue: OSDI
year: 2026
tags: [llm-serving, pipeline-parallelism, chunked-prefill, scheduling, latency-slo]
source_pdf: "[[osdi26-hwang.pdf]]"
source_md: "[[osdi26-hwang]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 重新审视 [[LLM|LLM]] Serving 的流水线并行（OSDI 2026）

> **原题**：Revisiting Pipeline Parallelism for LLM Serving

> **一句话总结**：PCIe GPU 上 pipeline parallelism 避免 TP 的频繁 All-Reduce，却因在线请求的 prefill/decode混合产生动态 stage imbalance；论文以 SLO-aware dynamic chunked prefill 和 delay scheduling缓解 P–D/D–D bubble，在 4×A100 上让 PP 获得高于 TP 的 goodput，并将 Conversation workload 的 TPOT/E2E 最多降低 35%/31%。

## 问题与动机

Tensor parallelism（TP）在 NVLink 上可降低 latency，但每层 collective 在 PCIe/commodity accelerator上成为瓶颈。Pipeline parallelism（PP）只传 activation，理论吞吐更高，却不适合照搬离线固定 microbatch：在线 request arrival、prompt/output length 与 prefill/decode phase不断变化，使不同 stage 同时处理的 microbatch计算量不同，出现 Prefill–Decode（P–D）和 Decode–Decode（D–D）imbalance。

chunked prefill能缩短长 prefill，但 chunk太小降低 GEMM效率并拉长 TTFT，太大又增加 bubble/TPOT。因此最佳 chunk size随 request rate 与 SLO slack动态变化。

## 关键观察 / 隐含假设

- **观察 1**：prefill computation与chunk tokens近似成比例；调小chunk能减少跨stage latency差，但牺牲GPU throughput（§3）。
- **观察 2**：TTFT slack和TPOT slack给出相反控制信号：TPOT将违约时缩小chunk，TTFT紧张时增大chunk加快排空（§4.1）。
- **观察 3**：decode-heavy下即使没有prefill，不同microbatch active requests数量不同仍有D–D imbalance；允许有slack的旧请求延后，可重平衡各stage decode load（§4.2）。
- **依赖假设**：online measurements与arrival-rate prediction足够快，短期未来 workload近似当前；延后请求仍不违反per-request SLO。

## 核心方法

Dynamic Chunked Prefill 有两个版本。Greedy controller 每个 scheduling iteration观察 P90 TTFT/TPOT 相对SLO的slack和KV availability，逐步增减chunk size。Predictive controller离线profile不同batch/chunk的linear-layer latency与throughput，结合incoming request rate/token demand筛除不满足SLO的candidate，再选取预计bubble小且throughput高的size（§4.1）。

Delay Scheduling（DS）检查pipeline workers上的decode workload，把可容忍额外延迟的旧请求暂缓，使新请求与各stage工作量更均衡；TPOT slack不足时优先保护新request，slack充足时则以减少bubble、提高goodput为目标（§4.2）。实现基于SGLang，保持模型partition和request语义不变。

## 设计取舍

- **adaptive chunk换稳定性**：能追踪load，但feedback lag可能振荡；predictive version更稳却依赖profile/model。
- **goodput而非raw throughput**：只统计P90 TTFT/TPOT都满足SLO的最大request rate，更贴近online服务，但掩盖P99和单请求公平性。
- **delay换balance**：重排decode减少GPU idle，可能恶化被延迟旧请求的tail latency。
- **[[PCIe|PCIe]]适用性**：论文优势主要来自communication-constrained deployment；NVLink/NVSwitch上TP比较会变化。

## 实验与结果

- 单server、4×NVIDIA A100 40GB、AMD EPYC，Qwen2.5-32B/14B；trace含Azure Conversation、Azure Code、CNN、ShareGPT等（§5.1）。
- 主SLO为P90 TTFT 2,000 ms、TPOT 200 ms；goodput定义为同时满足二者的最大request rate。
- Qwen2.5-32B的Azure Conversation上，greedy DCP将TPOT/E2E降低约27%/28%，predictive DCP达到35%/31%；多种prefill-heavy trace均减少bubble（图 9）。
- Qwen2.5-14B上趋势一致，TPOT/E2E最高降低40%/50%；decode-heavy workload中DS进一步降低TTFT/E2E（图 10）。
- synthetic workload中，随prefill imbalance增大，相对baseline PP的goodput improvement由2.7×增至5.4×（32B）；decode-heavy上最高1.4×（图 13）。
- 在所测PCIe平台与SLO下，动态PP可超过TP goodput；SLO过紧到最小chunk也无法满足TPOT时，所有PP方案goodput归零（图 12）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| online PP的核心瓶颈是动态stage imbalance | 图 3/4 | 4×A100、Qwen2.5 | 强 |
| SLO-aware chunk adjustment降低P–D bubble | 图 9/10 | 多个real traces | 强 |
| delay scheduling缓解D–D imbalance | 图 10/13 | decode-heavy trace/synthetic | 中 |
| PP可优于TP | 图 9–12 | PCIe 4.0单机、两种模型/SLO | 中 |

## 批判性分析

### 论证链条

论文清楚区分P–D与D–D两类bubble，再分别用chunk controller和delay scheduler处理；SLO sensitivity揭示收益边界。它不是证明PP普遍优于TP，而是证明在低bandwidth interconnect、合适SLO下，动态调度可改变结论。

### 假设压力测试

Poisson/trace replay可能低估突发load、multi-tenant干扰和长上下文KV压力。arrival prediction错误会选错chunk；DS若持续偏爱new requests，旧请求可能遭遇tail unfairness。模型含[[MoE|MoE]]或不同stage operator cost时，单纯按token workload重平衡未必充分。

### 实验可信度

真实trace、两种模型、SLO sweep与synthetic isolation较完整；但只有4×A100 PCIe单机，缺乏8-GPU、NPU、NVLink和跨节点结果。主要使用P90，P99 regression虽局部讨论，尚不足以证明production tail安全。

### 系统性缺陷

controller依赖预profiling并与SGLang scheduler深度耦合；model升级、kernel变化后需重建latency table。PP stage固定切分，论文只调请求/chunk而不联合优化partition和KV placement。

## 局限与后续工作

- 在PCIe/NVLink/[[RDMA|RoCE]]与4→16 GPUs上绘制PP/TP crossover边界。
- 加入bursty/adversarial arrivals、P99/P99.9与per-request slowdown/fairness指标。
- 联合优化stage partition、chunk size和[[KV-Cache|KV-cache]] pressure，扩展到MoE/heterogeneous accelerators。

## 相关

- **相关概念**：[[Pipeline-Parallelism]]、[[Tensor-Parallelism]]、[[Chunked-Prefill]]、[[Goodput]]、[[Latency-SLO]]
- **相关系统**：[[SGLang]]、[[Qwen2.5]]
- **同会议**：[[OSDI-2026]]
