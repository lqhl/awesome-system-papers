---
type: paper
name: NVIDIA-Disagg-Study
full_title: "A Pragmatic Exploration of Prefill-Decode Disaggregation in Large Scale Inference"
authors: [Tiyasa Mitra, Ritika Borkar, Nidhi Bhatia, Shivam Raj, Hongkuan Zhou, "et al."]
venue: MLSys
year: 2026
tags: [disaggregation, inference, pareto, rate-matching, data-center]
source_pdf: "[[202cb962ac59075b964b07152d234b70.pdf]]"
source_md: "[[202cb962ac59075b964b07152d234b70]]"
---

# A Pragmatic Exploration of Prefill-Decode Disaggregation in Large Scale Inference (MLSys 2026)

> **一句话总结**：模拟扫描数十万 [[Disaggregation]] 设计点：prefill-heavy 流量和 >10B 模型收益最大，prefill 侧 Chunked Pipeline Parallelism 是紧 FTL 下的优解，ctx:gen GPU 比必须动态 rate matching（NVIDIA Dynamo Planner 验证）。

## 问题

[[Disaggregation]]（prefill pool 与 decode pool 分离）热度高但大规模落地少：模型分片、batch、prefill↔decode **rate matching** 与 FTL/TTL SLA 交织，设计空间极大。既有工作多在小 testbed 报 peak throughput，缺少完整 **throughput–interactivity Pareto** 曲线与流量/硬件敏感性指导。

## 核心方法

NVIDIA 用 datacenter-scale GPU 模拟器（kernel-aware、含 NVLink/Ethernet 网络模型）扫描数百万配置，对比 co-located（含 piggybacking/[[Chunked-Prefill]]）vs disaggregated：

- **Parallelism 搜索**：TP、EP、PP、Chunked Pipeline Parallelism (CPP)、TEP；prefill/decode 池可独立选 mapping。
- **Rate matching**：Algorithm 1 固定满足 FTL 的 prefill config，Algorithm 2 用 integer solver 在 TTL 约束下匹配 ctx:gen GPU 数并最小化总 GPU。
- **真实验证**：NVIDIA Dynamo + Dynamo Planner 做 SLA-aware 动态 rate matching；DeepSeek-R1 distilled Llama-8B on H200 测 goodput。

模型：DeepSeek-R1、Llama-3.1-8B/70B/405B；硬件以 Blackwell FP4 为主。

## 关键结果

- **Disaggregation 最赚**：ISL >> OSL（prefill-heavy）、模型 >10B（并行搜索空间更大）。
- **CPP 是 prefill 关键**：DeepSeek-R1 ISL=256K/64 GPU，增大 PP 可同时压 FTL 又保吞吐，通信量远低于宽 [[Tensor-Parallelism]]。
- **动态 rate matching 必要**：固定 ctx:gen=3.5 在宽松 latency 好、收紧则崩；0.5 相反；最优曲线动态包住二者。
- Co-located piggybacking 对 DeepSeek-R1 MLA 有 chunk 重算 overhead；decode-heavy、宽松 latency 时 co-located 仍更合适。
- Prefix caching / speculative decoding 会改变最优 ctx:gen 比——系统需弹性伸缩。

## 相关

- **相关概念**：[[Disaggregation]]、[[Pipeline-Parallelism]]、[[Tensor-Parallelism]]、[[Expert-Parallelism]]、[[Chunked-Prefill]]、[[KV-Cache]]、[[RDMA]]
- **同类系统**：NVIDIA Dynamo、Mooncake、[[SGLang]] disagg
- **同会议**：[[MLSys-2026]]