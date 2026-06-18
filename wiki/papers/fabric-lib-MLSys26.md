---
type: paper
name: fabric-lib
full_title: "fabric-lib: RDMA Point-to-Point Communication for LLM Systems"
authors: [Nandor Licker, Kevin Hu, Vladimir Zaytsev, Lequn Chen]
venue: MLSys
year: 2026
tags: [rdma, llm-inference, moe, disaggregation, rl, point-to-point]
source_pdf: "[[c51ce410c124a10e0db5e4b97fc2af39.pdf]]"
source_md: "[[c51ce410c124a10e0db5e4b97fc2af39]]"
---

# fabric-lib: RDMA Point-to-Point Communication for LLM Systems (MLSys 2026)

> **一句话总结**：fabric-lib 是跨 NIC 厂商的统一 RDMA 点对点库，用 IMMCOUNTER 完成非有序消息通知，在 ConnectX-7 与 AWS EFA 上均达 400 Gbps 线速，万亿参数 RL 权重更新 1.3 s，并解除 DeepEP / NVSHMEM 的 vendor lock-in。

## 问题

新兴 LLM 系统模式——[[Disaggregation]] inference、[[MoE]] routing、异步 RL fine-tuning——都需要灵活的点对点通信，超出 NCCL / torch.distributed 集合通信能力：固定 membership 阻碍动态 scaling，同步初始化开销大，SEND/RECV 难组合出可用低延迟。而 RDMA 侧又存在 vendor lock-in：DeepEP 依赖 ConnectX 独有的 IBGDA；NVSHMEM 在 EFA 上性能差；Mooncake、NIXL 缺 EFA 支持。

## 核心方法

**fabric-lib** 的 **TransferEngine** 核心观察：ConnectX RC 和 EFA SRD 都支持 reliable-but-unordered 语义。围绕这一交集做统一 API：

- **SEND/RECV**（两侧）+ **WRITEIMM**（单侧）。
- **IMMCOUNTER**：32-bit immediate + 接收方计数器，不依赖消息顺序做完成通知；通过 GDRCopy 可直接同步到 GPU。
- 透明管理 multiple NIC / GPU（EFA p5 实例 4×100 Gbps 聚合到 400 Gbps）。
- 支持 paged WRITE / single WRITE / scatter / barrier；UVM watcher 让 CPU 从 GPU kernel（含 CUDA Graph）驱动传输。

三类生产部署：

1. **[[KV-Cache]] transfer**（disaggregated inference）：prefill/decode 集群间通信，支持 full CUDA Graph、layer-by-layer 低延迟传输，已在 EFA 上生产化。
2. **RL weight update**：每个 training GPU 直写到 inference GPU，pipeline 重叠 H2D memcpy / 权重准备 / [[RDMA]] 传输，万亿参数模型 1.3 秒更新，比现有 RL 框架快 100×+。
3. **MoE dispatch/combine**：ConnectX-7 上 decode 延迟与 DeepEP 专用 kernel 持平或更优；首次给出 EFA 上可用的 MoE 实现。

Rust 实现，per-DOMAINGROUP worker pin NUMA，lock-free 队列，NIC-level sharding。

## 关键结果

- 线速 400 Gbps on ConnectX-7 和 EFA。
- 万亿参数 RL 权重更新 1.3 s（100×+ 快于现有框架）。
- MoE decode 延迟与 DeepEP 持平或更优；EFA 上首个可行实现。
- 同一二进制跨 ConnectX / EFA，避免 vendor lock-in。
- 开源：https://github.com/perplexityai/pplx-garden/

## 相关

- **相关概念**：[[RDMA]]、[[MoE]]、[[Disaggregation]]、[[KV-Cache]]、[[PagedAttention]]
- **同类系统**：[[vLLM]]、[[SGLang]]、DeepEP、NVSHMEM、Mooncake Transfer Engine、NIXL
- **同会议**：[[MLSys-2026]]