---
type: concept
aliases: [rdma, Remote Direct Memory Access, RDMA, RoCE, RoCEv2, InfiniBand, IB, ibverbs, GPUDirect RDMA, NVIDIA GPUDirect]
last_updated: 2026-07-30
tags: [networking, distributed-training, llm-inference]
---

# RDMA

> Remote Direct Memory Access（RDMA）让 NIC 直接读写远端注册内存并绕过对端 CPU；它是解聚内存、GPU collective 与低延迟存储的基础，同时把拥塞、内存注册和 transport 可演化性变成系统问题。

## 核心思想

RDMA 提供 SEND/RECV、READ/WRITE 与 atomic verbs；InfiniBand/RoCE RNIC 负责可靠传输和 ordering，GPUDirect RDMA 进一步让 GPU memory 成为 DMA buffer。one-sided path 降低对端 CPU 成本，但要求发起方掌握 remote address、lifetime 和 protection key。

## 为什么重要

OSDI 2026 同时暴露了 RDMA 的三类边界。[[UCCL-Tran-OSDI26]] 将固定在 RNIC 的 transport control 搬到 host software，在 ConnectX-7 collective 上最高提升 4.5×；[[FORGE-OSDI26]] 显示 2000 ns 级 remote atomic 会把 cache housekeeping 放大至少 20×；[[Soul-OSDI26]] 则把 synchronization 融入 generalized coherence，消除 layered lock 的冗余消息。

此外，[[UEP-OSDI26]] 以 GPU→CPU proxy 统一 vendor-specific NIC，[[BALBOA-OSDI26]] 用开源 100 Gb/s RoCEv2 pipeline 探索可编程 data path。共同结论是：line rate 只是起点，control path、粒度和语义决定 application goodput。

## 关键观察 / 隐含假设

- **观察：硬件 transport 的稳定性与 ML workload 的变化速度不匹配。** [[UCCL-Tran-OSDI26]] 以 software multipath 处理 flow collision。
- **观察：远端原子很快但不是免费。** [[FORGE-OSDI26]]、[[FARLock-OSDI26]] 都通过批量/所有权降低同步次数。
- **假设：registered buffer 与 peer state 稳定。** migration、elastic membership 和 failure 会破坏该假设，见 [[TrainMover-OSDI26]]。

## 设计空间与取舍

- **One-sided / two-sided**：one-sided 省对端 CPU，two-sided 更容易管理 ownership 与 validation。
- **Hardware / software control**：硬件低开销但难演化；软件灵活却消耗 host CPU。
- **Fine-grained / batched**：细粒度低等待但放大 doorbell/atomic；batch 提吞吐但增加 latency。

## 引用本概念的论文

- [[UCCL-Tran-OSDI26]] — extensible software transport。
- [[FORGE-OSDI26]] — memory-disaggregated cache 的同步放大。
- [[Soul-OSDI26]] — generalized coherence synchronization。
- [[UEP-OSDI26]] — GPU initiated vendor-neutral RDMA proxy。
- [[DPA-Store-OSDI26]] — 对比有状态 RDMA ordered KV。

## 已知局限 / 开放问题

- 需要跨 vendor 的 congestion、failure、security 与 GPU ordering 统一抽象。
- software control path 的 CPU opportunity cost 和大规模稳定性仍缺生产证据。
