---
type: concept
aliases: [rdma, Remote Direct Memory Access, RDMA, RoCE, RoCEv2, InfiniBand, IB, ibverbs, GPUDirect RDMA, NVIDIA GPUDirect]
parent: "[[Collective-Communication]]"
last_updated: 2026-04-24
tags: [networking, distributed-training, llm-inference]
---

# RDMA

> 网卡直接读写远端机器的内存、绕过对端 CPU、零拷贝、用户态 verbs。**AI 集群的事实必选项**——InfiniBand 和 RoCEv2 (RDMA over Converged Ethernet) 是当前两条主线，NVIDIA 的 GPUDirect RDMA 让 GPU 显存直接作为 RDMA buffer，进一步绕过 host DRAM。LLM 训练的 AllReduce / AllGather / ReduceScatter、MoE 的 AllToAll、[[Disaggregation]] 的 KV transfer 全都踩在 RDMA 上。

## 核心特性

传统 TCP/IP：`A: user → kernel → NIC → wire → NIC → kernel → user :B`，每次都要 CPU 拷贝、context switch、协议栈。RDMA：

1. **Kernel bypass**：用户态 verbs 直接打网卡
2. **Zero copy**：NIC 直接 DMA 读写用户内存
3. **Remote memory ops**：READ/WRITE 对端内存不用对端 CPU 参与
4. **Hardware reliability**：网卡内做重传、顺序保证

关键原语：

- **SEND / RECV**：对端需预挂 RECV，有 CPU 介入（像 two-sided）
- **RDMA WRITE**：发起方写对端指定地址，对端 CPU 完全不知道（one-sided）
- **RDMA READ**：发起方从对端指定地址读
- **ATOMIC (FAA / CAS)**：远端原子操作

## 两条路线

| | InfiniBand (IB) | RoCEv2 |
|---|---|---|
| 物理层 | 专用 IB 交换机 | 标准以太网 |
| 拥塞控制 | credit-based，link-level | DCQCN / HPCC，end-to-end PFC |
| 带宽 | 400 Gbps (NDR), 800 Gbps (XDR) | 400 Gbps, 800 Gbps |
| 运维 | 专业 IB 技术栈 | 复用 eth 运维 |
| 典型场景 | NVIDIA 超算集群 (DGX SuperPOD) | 云厂商 AI 集群 (阿里、字节、AWS EFA) |

最新的 SHARP (Scalable Hierarchical Aggregation and Reduction Protocol) 把 AllReduce 放到交换机里算，[[SakuraONE-MLSys26]] 这类工作在研究。

## GPUDirect RDMA

NVIDIA 网卡（ConnectX/NDR）和 GPU 之间走 PCIe/NVLink 直连：
- 发起方 GPU 显存 → NIC → wire → NIC → 接收方 GPU 显存
- **完全不经过 host DRAM**
- 需要 `nvidia-peermem` 驱动 + ibverbs + CUDA-aware MPI / NCCL 整条链路

## 在 AI 系统里的角色

- **训练**：AllReduce (DP 梯度)、AllToAll (MoE 的 EP dispatch/combine)
- **[[Disaggregation]]**：prefill → decode 传 KV cache，每请求 MB 级，延迟敏感
- **分布式推理**：KV migration、context sharding
- **Checkpoint save/load**：大 checkpoint 到共享存储也往 RDMA 走

近期工作把 RDMA 的抽象再往上抬了一层：
- **[[fabric-lib-MLSys26]]** (pplx-garden)：跨 vendor 的 RDMA 统一抽象，写一次代码跑 CX7/EFA/盘古，聚焦 disagg inference 的 KV transfer
- **[[DeepEP]]** (DeepSeek)：针对 H800 NVLink + CX7 RDMA 的 MoE AllToAll custom 协议
- **[[NEST-MLSys26]]**：把 RDMA 引入 MoE 训练调度

## 引用本概念的论文

- [[fabric-lib-MLSys26|fabric-lib]]、[[NEST-MLSys26|NEST]]、[[SakuraONE-MLSys26|SakuraONE]] — RDMA 作为一等 abstraction
- （隐含依赖 RDMA 的训练 / 推理系统在其 backend 里用，但通常不直接 wikilink）

## 相关概念

- 硬件：[[NVLink]]、[[NoC]]
- 通信原语：[[AllReduce]]、[[AllToAll]]、[[Collective-Communication]]、[[Multicast]]
- 使用场景：[[Disaggregation]]、[[Expert-Parallelism]]、[[Pipeline-Parallelism]]
