---
type: concept
aliases: [rdma, Remote Direct Memory Access, RDMA, RoCE, RoCEv2, InfiniBand, IB, ibverbs, GPUDirect RDMA, NVIDIA GPUDirect]
parent: "[[Collective-Communication]]"
last_updated: 2026-06-20
tags: [networking, distributed-training, llm-inference]
---

# RDMA

> 网卡直接读写远端机器内存、绕过对端 CPU、零拷贝、用户态 verbs。InfiniBand 和 RoCEv2 是当前 AI 集群两条主线；NVIDIA GPUDirect RDMA 让 GPU 显存直接作为 RDMA buffer，进一步绕过 host DRAM。LLM 训练的 AllReduce / AllGather、MoE 的 AllToAll、[[Disaggregation]] 的 KV transfer 全都踩在 RDMA 上。

## 核心思想

传统 TCP/IP：`A: user → kernel → NIC → wire → NIC → kernel → user :B`，每次 CPU 拷贝、context switch、协议栈开销。RDMA 提供：

1. **Kernel bypass**：用户态 verbs 直接打网卡
2. **Zero copy**：NIC 直接 DMA 读写用户内存
3. **Remote memory ops**：READ/WRITE 对端内存无需对端 CPU 参与
4. **Hardware reliability**：网卡内重传、顺序保证

关键原语：SEND/RECV（two-sided，对端需预挂 RECV）；RDMA WRITE（one-sided，发起方写对端指定地址）；RDMA READ（发起方从对端读）；ATOMIC（FAA/CAS 远端原子操作）。

两条路线：InfiniBand（专用交换机、credit-based 拥塞控制、400–800 Gbps NDR/XDR，NVIDIA 超算 DGX SuperPOD）；RoCEv2（标准以太网、DCQCN/HPCC 拥塞控制、云厂商 AI 集群 AWS EFA 等）。SHARP 把 AllReduce 下沉到交换机（[[SakuraONE-MLSys26]] 等研究方向）。

**GPUDirect RDMA**：ConnectX/NDR 网卡与 GPU 经 PCIe/NVLink 直连，发起方 GPU 显存 → NIC → wire → NIC → 接收方 GPU 显存，完全不经过 host DRAM；需 `nvidia-peermem` + ibverbs + CUDA-aware MPI/NCCL 整条链路。

## 为什么重要

RDMA 是 AI 集群「通信不再经过 CPU」的基础设施假设——没有这个假设，disaggregated inference 的 KV transfer、MoE 的 AllToAll、大模型训练的 gradient AllReduce 都会在 host 协议栈上撞墙。这些论文共同假设：**RDMA 带宽足够时，瓶颈转移到 collective 调度、拓扑感知、以及 GPU-initiated vs CPU-initiated 路径选择**。

近期工作把 RDMA 抽象再抬一层：[[fabric-lib-MLSys26]] 提供跨 vendor（CX7/EFA/盘古）统一抽象，聚焦 disagg inference KV transfer；[[DeepEP]] 针对 H800 NVLink + CX7 RDMA 异构带宽设计 MoE hierarchical AllToAll；[[FreeScale-MLSys26]] 用 CPU-RDMA ring AllGather/AllToAll overlap 时不占 SM；[[FaaScale-MLSys26]] 用 GPUDirect RDMA 做模型 block multicast 与 pipeline 推理重叠。

## 关键观察 / 隐含假设

- **观察 1：disagg KV transfer 在典型 datacenter 配置下通常不是瓶颈，但拓扑与异步传输实现关键。** [[NVIDIA-Disagg-Study-MLSys26]] 式 3/4 推导 egress/ingress 需求，Figure 14 显示现有机房带宽可支撑；NIXL 提供非阻塞 P2P RDMA/NVLink 路径；层间流水可 overlap 传输与 prefill 计算。
- **观察 2：完成通知不必依赖 message ordering——WRITEIMM immediate 计数 + PCIe 序可在无序网络上保证可见性。** [[fabric-lib-MLSys26]] 针对 production disagg KV transfer 设计 heartbeat + per-request cancellation token。
- **观察 3：MoE EP 的异构带宽使 naive AllToAll 严重倾斜。** [[DeepEP]]（DeepSeek）H800 节点内 NVLink 160 GB/s vs 跨节点 RDMA 50 GB/s，需 hierarchical 分阶段协议；[[NEST-MLSys26]] 把 RDMA 引入 MoE 训练 placement 搜索。
- **观察 4：CPU-initiated RDMA collective 可在 overlap 时不占 SM。** [[FreeScale-MLSys26]] 针对 recommendation 场景 UIH 长度异质性 straggler，用 CPU-RDMA ring AllGather/AllToAll；高带宽 IB 上验证，慢网络外推需实测。

## 设计空间与取舍

- **路线 1：NCCL/MPI 默认 RDMA backend（训练 collective）**：成熟、与 PyTorch 集成好；牺牲是 collective 语义固定，对 MoE AllToAll 拓扑不敏感。
- **路线 2：Custom MoE 协议（[[DeepEP]]、[[fabric-lib-MLSys26]]）**：hierarchical / vendor-aware，针对异构带宽优化；牺牲是维护成本与生态锁定。
- **路线 3：Disagg KV P2P transfer（[[fabric-lib-MLSys26]]、NIXL、Mooncake）**：one-sided WRITE + 异步 completion，layer-by-layer overlap；牺牲是 prefiller/decoder sharding 不一致时需 page-wise offset/stride 转换。
- **路线 4：GPUDirect RDMA multicast（[[FaaScale-MLSys26]]）**：模型 block 广播与 pipeline 重叠；牺牲是 multicast 组管理与 fault tolerance 复杂度。
- **路线 5：CPU-RDMA ring（[[FreeScale-MLSys26]]）**：overlap 不占 SM；牺牲是 host memory 与 prefetch 开销，短 sequence 收益有限。
- **路线 6：交换机内聚合 SHARP（[[SakuraONE-MLSys26]]）**：AllReduce 下沉交换机；牺牲是 IB 交换机专用硬件依赖与可编程性限制。

## 引用本概念的论文

- [[fabric-lib-MLSys26|fabric-lib]] — 跨 vendor RDMA 统一抽象，production disagg KV transfer over EFA & ConnectX
- [[NVIDIA-Disagg-Study-MLSys26|NVIDIA-Disagg-Study]] — KV 跨池传输带宽通常非瓶颈；NIXL 非阻塞 P2P RDMA/NVLink
- [[NEST-MLSys26|NEST]] — RDMA 作为 MoE 训练 placement 一等 abstraction
- [[FreeScale-MLSys26|FreeScale]] — CPU-RDMA ring AllGather/AllToAll，overlap 时不占 SM
- [[FaaScale-MLSys26|FaaScale]] — GPUDirect RDMA 模型 block multicast，与 pipeline 推理重叠
- [[SakuraONE-MLSys26|SakuraONE]] — RDMA 交换机内聚合 abstraction
- [[GPU-CC-Security-MLSys26|GPU-CC-Security]] — H100 GPU-CC 数据路径加密与 BAR0 firewall 安全分析（I/O threat model）
- [[CetoFS-FAST26|CetoFS]] — NVMe-oF over RDMA 解聚存储，用户态数据面 offload
- [[Coyote-v2-SOSP25|Coyote-v2]] — FPGA shell 与 RDMA 异构计算
- [[RDMA-LiveMigration-SOSP25|RDMA-LiveMigration]] — 亚秒级 RDMA device live migration
- [[Mage-SOSP25|Mage]]、[[Spirit-SOSP25|Spirit]] — far memory / 公平分配与 RDMA 扩展性
- [[CrossPipe-ATC25|CrossPipe]]、[[FuseLink-OSDI25|FuseLink]]、[[DeepServe-ATC25|DeepServe]] — 分布式 serving / 训练中的 RDMA 路径
- [[Bidaw-FAST26|Bidaw]]、[[DMTree-FAST26|DMTree]] — RDMA 存储与树结构通信优化

## 已知局限 / 开放问题

- [[fabric-lib-MLSys26]] GPU-initiated 路径在支持硬件上仍为可选 backend，非默认
- 跨 vendor RDMA 抽象的性能一致性（CX7 vs EFA vs 盘古）缺乏公开 head-to-head benchmark
- disagg KV transfer 在长 context（单序列 >10 GB）场景下仍可能带宽 bound，与 prefix cache / speculative decoding 叠加后的 Pareto 未系统重扫（[[NVIDIA-Disagg-Study-MLSys26]] 局限 2）
- RoCEv2 在拥塞下的 tail latency 与 IB credit-based 的对比在 MoE AllToAll 场景缺乏系统测量
- RDMA 安全模型（[[GPU-CC-Security-MLSys26]]）与 production disagg serving 的 threat model 对齐仍是开放问题