---
type: paper
name: fabric-lib
full_title: "fabric-lib: RDMA Point-to-Point Communication for LLM Systems"
authors:
  - Nandor Licker
  - Kevin Hu
  - Vladimir Zaytsev
  - Lequn Chen
venue: MLSys
year: 2026
tags:
  - rdma
  - llm-inference
  - moe
  - disaggregation
  - rl
  - point-to-point
  - fabric-lib
source_pdf: "[[c51ce410c124a10e0db5e4b97fc2af39.pdf]]"
source_md: "[[c51ce410c124a10e0db5e4b97fc2af39]]"
aliases:
  - TransferEngine
  - TransferEngine-MLSys26
---

# fabric-lib: RDMA Point-to-Point Communication for LLM Systems (MLSys 2026)

> **一句话总结**：fabric-lib 是跨 NIC 厂商的统一 RDMA 点对点库，TransferEngine 为其核心引擎，用 IMMCOUNTER 完成非有序消息通知，400 Gbps 线速，开源在 [pplx-garden](https://github.com/perplexityai/pplx-garden)，在 KvCache 传输、1.2 秒级万亿参数 RL 权重更新、MoE dispatch/combine 三大生产场景解除 vendor lock-in。

## 问题

新兴 LLM 系统模式——[[Disaggregation]] inference、[[MoE]] routing、异步 RL fine-tuning——都要灵活的点对点通信，超出 NCCL / torch.distributed 集合通信能力：

- 固定 membership 阻碍动态 scaling；
- 同步初始化开销大；
- 统一 buffer 形状对稀疏模式过度密集；
- SEND/RECV 难组合出可用低延迟。

而 RDMA 侧又存在 vendor lock-in：[[DeepEP]] 依赖 ConnectX 独有的 IBGDA；NVSHMEM 在 EFA 上性能差；Mooncake、NIXL 缺 EFA 支持。ConnectX RC 有序、EFA SRD 无序，难统一抽象。

## 核心方法

**fabric-lib** 是 Perplexity 开源的跨厂商 RDMA 点对点通信库，**TransferEngine** 为其核心引擎。关键观察：ConnectX RC 和 EFA SRD 都支持 reliable-but-unordered 语义（ConnectX RC 可忽略顺序）。围绕这一交集做统一 API。

核心原语：
- **SEND/RECV**（两侧）+ **WRITEIMM**（单侧）。
- **IMMCOUNTER**：32-bit immediate + 接收方计数器，不依赖消息顺序做完成通知；通过 GDRCopy 可直接同步到 GPU。v2 新增 PCIe ordering 正确性论证：WRITEIMM 的数据先于 immediate 到达 GPU，CPU 观察到计数器后再写 GPU flag，PCIe switch 保证数据可见。
- 透明管理 multiple NIC / GPU（EFA p5 实例 4 × 100 Gbps 聚合到 400 Gbps）。
- 支持 paged WRITE / single WRITE / scatter / barrier；UVM watcher 让 CPU 从 GPU kernel（含 CUDA graph）驱动传输。

三类生产部署：

1. **KvCache transfer**（disaggregated inference）：prefill/decode 集群间通信，支持 full CUDA Graph、layer-by-layer 低延迟传输，已在 EFA 上生产化。v2 新增 Qwen3-235B 端到端 TTFT 数据：4K–128K seqlen 下传输被计算完全隐藏，TTFT 增量主要来自 engine 多做一次 decode pass 而非传输。
2. **RL weight update**：每个 training GPU 直写到 inference GPU，pipeline 重叠 H2D memcpy / 权重准备 / [[RDMA]] 传输，Kimi-K2 万亿参数模型 1.2 秒更新（v2 详细 breakdown：full_tensor() 518ms、跨 rank 同步 357ms、RDMA submit 仅 26ms），比现有 RL 框架快 100x+。
3. **MoE dispatch/combine**：ConnectX-7 上 decode 延迟与 DeepEP 专用 kernel 持平或更优；首次给出 EFA 上可用的 MoE 实现。v2 新增端到端 decode speed 表（DeepSeek-V3 MTP EP=64）、dual-batch overlap 分析、host-proxy CPU overhead 分解（EP64 p50 仅 8.5µs CX-7 / 27.9µs EFA）。

Rust 实现，per-DOMAINGROUP worker pin NUMA，lock-free 队列，NIC-level sharding。v2 新增 Section 8 Discussion：GPU-initiated RDMA（GDA）在大多数云实例尚不可用；新 NIC（eRDMA、Broadcom、AMD）走 RC 路径即可适配，应用层代码不变。伪代码附录 A（KvCache transfer）、附录 B（RL weight transfer）。

## 关键结果

- 线速 400 Gbps on ConnectX-7 和 EFA（聚合 4 × 100 Gbps）。
- 万亿参数 RL 权重更新 1.2 s（100x+ 快于现有框架），v2 提供 PT profile 完整 breakdown。
- MoE decode 延迟与 DeepEP 持平或更优；EFA 上首个可行实现；end-to-end decode speed 在 CX-7 上匹配 DeepEP。
- EFA 上 pplx-kernels（NVSHMEM-based）比 fabric-lib 慢 3–6×；dual-batch overlap 收益有限。
- 同一二进制跨 ConnectX / EFA，避免 vendor lock-in。
- 开源：<https://github.com/perplexityai/pplx-garden>

## 相关

- **相关概念**：[[RDMA]]、[[MoE]]、[[Disaggregation]]、[[KV-Cache]]、[[PagedAttention]]
- **同类系统**：DeepEP、NVSHMEM、Mooncake Transfer Engine、NIXL、UCCL、MSCCL++
- **同会议**：[[MLSys-2026]]
