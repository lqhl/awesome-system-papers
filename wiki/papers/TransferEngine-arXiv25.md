---
type: paper
name: TransferEngine
full_title: RDMA Point-to-Point Communication for LLM Systems
authors: [Nandor Licker, Kevin Hu, Vladimir Zaytsev, Lequn Chen]
venue: arXiv
year: 2025
tags: [llm-inference, rdma, p2p-communication, moe, kv-cache, disaggregation]
source_pdf: "[[2510.27656v1.pdf]]"
source_md: "[[2510.27656v1]]"
---

# RDMA Point-to-Point Communication for LLM Systems (arXiv 2025)

> **一句话总结**：TransferEngine 把 NVIDIA ConnectX RC 与 AWS EFA SRD 两类 RDMA 硬件的最大公约数（reliable but unordered delivery）抽象成统一 P2P 接口，用新颖的 IMMCOUNTER 原语替代 ordering-dependent 的完成通知，在 disaggregated [[KV-Cache]] 传输、RL weight sync（1T 模型 1.3s）、[[MoE]] dispatch/combine（ConnectX-7 上超越 DeepEP）三个生产场景中验证。

## 问题

新兴 LLM 系统模式——[[Disaggregation|disaggregated inference]]、MoE routing、asynchronous RL fine-tuning——都需要灵活的 P2P 通信，超出 collective（NCCL / torch.distributed）的能力边界：collective 要求固定成员、同步初始化、统一 buffer 大小，无法支持 dynamic scaling 和稀疏通信。

理论上 [[RDMA]] 早已提供 SEND/RECV/WRITE 等灵活原语，但落到 LLM 框架里几乎用不上：硬件碎片化（NVIDIA ConnectX 用 RC 协议提供 in-order delivery，AWS EFA 用 SRD 协议提供 out-of-order delivery）让现有 P2P 实现（DeepEP 依赖 ConnectX 独有的 IBGDA、NVSHMEM 在 EFA 上严重劣化、Mooncake 和 NIXL 缺 EFA 支持）都被锁定在单一硬件上。结果：没有任何 vendor-portable 的 P2P 通信库可用。

## 核心方法

**关键洞察**：ConnectX RC 可以忽略 ordering 用作 unordered，EFA SRD 本身就 unordered；以「reliable but unordered delivery」作最大公约数，可以构建一个跨硬件的可移植抽象。

**TransferEngine** 是一个 Rust 实现的 RDMA 库：

- API 极简：`submit_send/recv`（两侧 RPC）+ `submit_single_write` / `submit_paged_writes` / `submit_scatter` / `submit_barrier`（一侧 WRITE 系列）
- 用 **IMMCOUNTER** 替代 ordering：每个 WRITE 可附带 32-bit immediate value，receiver 端聚合 immediate counter 后通过 callback / atomic flag 通知，从而完全不依赖 message ordering
- 透明管理多 NIC per GPU：EFA 需要聚合 4 个 100Gbps NIC 才能达到 400Gbps，TransferEngine 在 DOMAINGROUP 内 shard / load-balance
- DOMAIN 针对 EFA（libfabric）和 ConnectX-7（libibverbs）做硬件特定优化（Work Request templating、WR chaining、relaxed PCIe ordering）

**三个 production 场景**：

1. **KvCache transfer**（[[Disaggregation]] inference）：prefiller 在 chunked prefill 中每层结束后通过 UVM watcher 触发 layer-by-layer 的 paged WRITE 到 decoder；decoder 用 `expect_imm_count` 等待完成。CUDA Graph compatible。
2. **RL weight update**：抛弃 collective 的「gather → broadcast」（被 train rank0 的 NIC 限制），改为每个 train GPU 直接 one-sided WRITE 到 inference GPU，配合 4-stage pipeline（H2D memcpy / weight prep / RDMA / barrier）。
3. **MoE dispatch/combine**：host proxy 协调 GPU + NIC，NVLink 节点内传输 + RDMA 跨节点。private buffer 隐藏 routing 信息交换的延迟，单次 scatter 完成 combine。

## 关键结果

- **峰值带宽**：ConnectX-7 378 Gbps（32 MiB single WRITE）；EFA 336 Gbps（双 NIC 聚合）
- **RL weight update**：256 train GPU → 128 inference GPU，trillion-parameter (Kimi-K2) **1.3 秒**完成同步，对比现有方案 100× 加速
- **MoE decode latency**（DeepSeek-V3 设置，128 tokens/rank）：ConnectX-7 上**优于 DeepEP**（在 16/32 ranks），尽管 TransferEngine 用 host proxy 而 DeepEP 用 IBGDA 直发；EFA 上提供首个可用实现（NVSHMEM 在 EFA 上 unusably slow）
- **MoE prefill**（4096 tokens/chunk）：DeepEP 仍占优（其 sender-side partial sum 减少 RDMA bytes），TransferEngine 在 EP=64 大规模时差距收敛
- **Portability**：同一份代码跑 ConnectX-7 和 EFA，避免 vendor lock-in

## 相关

- **相关概念**：[[KV-Cache]]、[[MoE]]、[[Disaggregation]]、[[RDMA]]
- **同类系统 / 对比对象**：DeepEP（ConnectX-only，IBGDA-based）、NVSHMEM（EFA 上严重劣化）、Mooncake、NIXL、UCCL-EP、MSCCL++
- **可被集成进**：[[vLLM]]、SGLang、TensorRT-LLM、FlashInfer 等推理框架；OpenRLHF、AReaL、veRL、Slime 等 RL 框架
- **同期工作**：Splitwise (ISCA'24)、DistServe、Mooncake (FAST'25)、3FS、pplx-kernels
- **依赖底层**：libfabric / libibverbs / GDRCopy / GPUDirect RDMA / GPUDirect Async (IBGDA)
