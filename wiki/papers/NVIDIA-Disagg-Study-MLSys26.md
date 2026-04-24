---
type: paper
name: NVIDIA-Disagg-Study
full_title: "Beyond the Buzz: A Pragmatic Take on Inference Disaggregation"
authors: [Tiyasa Mitra, Ritika Borkar, Nidhi Bhatia, Ramon Matas, Shivam Raj, "et al."]
venue: MLSys
year: 2026
tags: [disaggregation, inference, survey, pareto, data-center]
source_pdf: "[[202cb962ac59075b964b07152d234b70.pdf]]"
source_md: "[[202cb962ac59075b964b07152d234b70]]"
---

# Beyond the Buzz: A Pragmatic Take on Inference Disaggregation (MLSys 2026)

> **一句话总结**：在数十万个 disaggregated serving 设计点上系统评测，发现 [[Disaggregation]] 对 prefill-heavy 流量和 >10B 模型收益最大，Chunked Pipeline Parallelism 是 FTL-高吞吐的优解，rate matching 必须动态。

## 问题

Disaggregated serving（prefill pool 与 decode pool 分离）有热度但落地少，主要因设计空间极大——模型分片、并发、prefill↔decode rate matching 交织，何时该用、怎么配置缺乏系统研究。既有论文多在小规模 testbed 测 peak throughput，不看完整 throughput-interactivity Pareto frontier。

## 核心方法

用 NVIDIA 的 datacenter-scale proprietary GPU 性能模拟器，输入（模型架构、流量 pattern、GPU 配置）输出 latency/throughput。扫描：

- **Parallelism**：TP、EP、PP、Chunked Pipeline Parallelism (CPP)、TEP (TP attention + EP FFN)；多种 batch size。
- **模型**：DeepSeek-R1、Llama-3.1-8B/70B/405B。
- **流量**：prefill-heavy vs decode-heavy 多种 ISL/OSL。
- **硬件**：Blackwell FP4、不同 NVLink domain 大小。
- **Rate matching**：integer solver 在 FTL、TTL SLA 约束下求 ctx:gen GPU 比。

对每个 config 画出 throughput-interactivity Pareto 曲线，对比 co-located（含 piggybacking/chunked prefill）vs disaggregated。

## 关键结果

- **Disaggregation 最有用的场景**：ISL >> OSL (prefill-heavy)、>10B 模型（更丰富的并行搜索空间）。
- **Chunked Pipeline Parallelism 是 prefill 阶段 key**：DeepSeek-R1 ISL=256K/64 GPU 上 PP 增大能同时压 FTL 又保持高吞吐，避开过宽 TP 的开销。
- **Rate matching 必须动态**：固定 ctx:gen=3.5 在宽松 latency 最优但严格 latency 下崩；固定 0.5 相反。动态 Pareto 包住两者。
- **Co-located 下 piggybacking 对 DeepSeek-R1 MLA 有额外 overhead**（重算 down/up proj），可用 KV cache mitigate。
- **NVLink domain 越大越利好 disaggregated**（更大 EP/TP 搜索空间）。
- **KV cache transfer 带宽**：分析公式给出 egress/ingress BW 要求，现有 datacenter 带宽足够不成瓶颈。

## 相关

- **相关概念**：[[Disaggregation]]、[[Pipeline-Parallelism]]、[[Tensor-Parallelism]]、[[Expert-Parallelism]]、[[Chunked-Prefill]]、[[KV-Cache]]
- **同会议**：[[MLSys-2026]]
