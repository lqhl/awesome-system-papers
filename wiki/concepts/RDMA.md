---
type: concept
aliases: [rdma, Remote Direct Memory Access, RDMA, RoCE, RoCEv2, InfiniBand, ibverbs, GPUDirect RDMA]
last_updated: 2026-08-17
tags: [networking, distributed-training, llm-inference]
---

# RDMA

> 远程直接内存访问（Remote Direct Memory Access，RDMA）让网卡直接读写已经注册的远端内存，常把远端 CPU、内核网络栈和数据复制移出快速路径。它缩短了数据路径，却没有消除控制、拥塞、一致性、故障和资源隔离问题；这些成本往往只是从 CPU 搬到了 RNIC、发送端或应用协议里。

## 核心思想

应用先把一段 host 或 GPU 内存注册成内存区域（memory region，MR），得到本地或远端访问所需的 key，再通过队列对（queue pair，QP）提交 work request，并从完成队列取得结果。`READ`、`WRITE` 和 atomic 属于单边操作（one-sided operation）：远端应用线程不必逐请求运行。`SEND/RECV` 属于双边操作（two-sided operation）：接收端要预先准备 buffer，但更容易把验证、所有权和错误处理留在服务端。

RDMA 不是一种单一网络。InfiniBand 把链路、交换与 RDMA transport 放在同一套体系内；RoCEv2 把 RDMA transport 放到以太网上，通常还要配合 ECN、[[Congestion-Control|拥塞控制]] 和优先级流控（Priority Flow Control，PFC）。常见连接语义也不同：RC 提供可靠、有序连接，UC 放松可靠性，UD 是无连接 datagram，AWS EFA 的 SRD 又提供可靠但可乱序的消息。论文中“使用 RDMA”可能只表示实验网络是 InfiniBand，也可能真的依赖一侧原子操作、固定排序或远端 key；不能把这些情况混为一谈。

GPUDirect RDMA 允许 NIC 直接 DMA GPU memory。它避免 payload 经 host DRAM 中转，但“数据不经 CPU”不等于“控制也不经 CPU”。[[UEP-OSDI26]] 让 GPU 产生 16-byte command、CPU proxy 代发 verbs，payload 仍在 GPU 间直传；[[UCCL-Tran-OSDI26]] 也把 payload 留在 NIC datapath，只把拥塞控制、选路和部分可靠性搬到 host software。相反，GPU-initiated 路线让 GPU 自己 post work request，省 host round trip，却更依赖特定 NIC 和 ordering 语义。

## 为什么重要

RDMA 把一次远程访问压到微秒级后，系统瓶颈会发生转移。[[FORGE-OSDI26]] 测得 RDMA atomic 比普通 read/write 慢 4–5 倍，并会让并发 read throughput 降低 4.3 倍；[[FineMem-OSDI25]] 则指出 4 MB MR 注册约需 480 µs。于是，metadata 更新、内存注册、QP 状态和完成处理可能比 payload 本身更贵。[[DMTree-FAST26]]、[[RCuckoo-ATC25]] 和 [[FARLock-OSDI26]] 的共同方向不是让每个远端操作再快一点，而是减少操作次数、把 metadata 放到更合适的位置，或改变所有权。

高速网络也会暴露原来被传输时间遮住的软件开销。[[Blowfish-OSDI26]] 的 100 Gbps InfiniBand 场景里，虚拟机换页软件路径是网络传输的 3.4–6.8 倍；[[CetoFS-FAST26]] 测得 4 KB 随机写总延迟中 65% 来自软件栈，其中 NVMe-over-RDMA 驱动占 36.1%；[[DGC-OSDI26]] 发现远端 marking 可接近同机共享内存，但扩到 12 个 client 后 200 Gbps NIC 已成瓶颈。RDMA 因而常是“让上层设计问题变得可见”的工具，而不是自动得到低延迟的保证。

最后，RDMA 连接携带地址、key、QP、sequence、ordering 和重传状态。扩缩容、live migration、进程重启、GPU reset 或成员变化都可能让这些状态失效。[[RDMA-LiveMigration-SOSP25]] 必须保持 wire-visible namespace 并提取设备黑盒状态；[[TrainMover-OSDI26]] 只切换受影响的 QP；[[RobustRL-OSDI26]] 干脆在失败后用 UCX 重新连。这些工作说明，绕过远端 CPU 的正常路径越短，控制面越要明确管理生命周期。

## 关键观察 / 隐含假设

- **观察 1：线速不是应用吞吐的充分条件。** [[UCCL-Tran-OSDI26]] 在无拥塞的 ConnectX-7 实机上基本追平硬件 transport，但在跨机架 flow collision 下，动态多路径让 all-to-all bus bandwidth 最多提高 4.54 倍；这说明差异来自 control policy 和拓扑，而不是 DMA 本身更快。[[Barre-ATC25]] 在 10K-GPU 生产环境把训练吞吐平均提高 9.6%，同样依赖更合适的拥塞反馈。
- **观察 2：细粒度远端操作会把 RTT、doorbell 和 atomic 放大成系统瓶颈。** [[FORGE-OSDI26]] 通过分组和延迟 flush 减少 cache metadata 流量；[[HypeReca-ATC25]] 发现约 500 B embedding 的 one-sided fetch 连理论带宽的 10% 都不到，最终改成接收端 gather 后批量传输；[[FaaScale-MLSys26]] 和 [[AITurbo-FAST26]] 也都依赖连续 block 或 grouped API 才能发挥 fabric 带宽。
- **观察 3：单边操作省的是远端 CPU，不是协议语义。** [[HDTX-ATC25]] 仍需 redo log、visibility 和 release ordering；[[Scalio-OSDI25]] 仍需 `occupied/complete` 协议保证 linearizability；[[RTSFaaS-ATC25]] 仍需全局唯一 lease 和 transaction precedence graph。地址、权限、版本与恢复责任只是移到了 client、NIC 或单独的 coordinator。
- **观察 4：本地 CPU 与 RNIC 对同一状态不天然一致。** [[FARLock-OSDI26]] 指出 RNIC atomic 只保证与同一 RNIC 上的 RDMA atomic 原子，不能直接与 host CPU 普通访存混用；其双队列加全局 ticket 正是在修复 local/remote 所有权裂缝。[[Soul-OSDI26]] 更进一步，把锁与数据权限合入 coherence transaction，而不是在一致性协议外再叠一层远端锁。
- **观察 5：可编程性有四个不同落点，没有免费方案。** [[BALBOA-OSDI26]] 用 FPGA 得到开放 datapath，但目前只覆盖 RC 的一侧 READ/WRITE 子集；[[SwCC-ATC25]] 把 C 写的拥塞算法放进 RDMA engine，控制环约 3.1 µs，和 ConnectX-5 相近而不是普遍更快；[[Barre-ATC25]] 使用 BlueField-3 PCC，易部署但绑定 event 与 rate-limiter 能力；[[UCCL-Tran-OSDI26]] 用每 NIC 约 2 个 host core 换软件策略灵活性。
- **观察 6：RoCE 的多路径与 lossless 机制可能互相冲突。** [[FLB-ATC25]] 表明，细粒度散流会把触发 PFC 的 culprit flow 扩散到更多 path，从而增加无辜 victim；其测试床最多减少 96% PAUSE。这里的结论依赖 lossless RoCE，不能直接外推到无需 PFC、能端到端选择性重传的 lossy fabric。
- **观察 7：设备与拓扑决定同一优化是否成立。** [[FreeScale-MLSys26]] 用 CPU-RDMA 避免 NCCL channel 占 GPU SM，但依赖 PCIe 5.0 和无 reduction collective；[[UEP-OSDI26]] 的 host proxy 跨 EFA、ConnectX 和 Broadcom，更可移植，却每 GPU 最多使用 4 个 CPU core；[[FuseLink-OSDI25]] 则利用 NVLink 中继空闲 NIC。它们解决的是不同硬件约束，不是可直接替换的三种实现。
- **隐含假设 1：注册内存、remote key、QP 与成员关系在操作期间稳定。** VM migration、elastic training、request migration 和 failure recovery 都会破坏这一点，见 [[RDMA-LiveMigration-SOSP25]]、[[TrainMover-OSDI26]]、[[RobustRL-OSDI26]]。
- **隐含假设 2：应用可以接受 RDMA 的故障和安全边界。** 多篇论文只测正常路径，没有覆盖 stale key、partial write、engine crash、NIC reset、跨租户访问或恶意 peer。[[GPU-CC-Security-MLSys26]] 还提醒，DMA metadata、本地 BAR 和 P2P key 本身就是可信计算边界的一部分。

## 设计空间与取舍

- **单边与双边**：单边读写适合固定地址、被动 memory node 和读多场景；双边消息让服务端做 validation、batching 和 ownership，更适合可变数据结构与复杂更新。[[DPA-Store-OSDI26]] 用 NIC 上的有状态索引避免 client 保存远端树；[[HypeReca-ATC25]] 从细粒度 one-sided 改成接收端 gather，说明“多一次远端参与”有时反而更快。
- **RC、UC、UD 与 SRD**：RC 把可靠、有序传输交给 NIC，部署简单但 transport policy 难改；UC/UD 给软件更多控制，也要求应用处理乱序、丢包和重组。[[UCCL-Tran-OSDI26]] 的 UC、Broadcom RC、EFA UD 后端能力并不相同，不能用一个总成绩代表所有 backend。
- **硬件控制与软件控制**：固定 ASIC 延迟低、功耗稳；PCC/嵌入式 core 可升级但受 event 和内存限制；FPGA 开放却增加开发与验证成本；host software 最灵活，但消耗 CPU 并受 scheduling jitter 影响。[[SwCC-ATC25]]、[[BALBOA-OSDI26]]、[[Barre-ATC25]]、[[UCCL-Tran-OSDI26]] 正好覆盖这四个位置。
- **逐包控制与批量控制**：逐包反馈更快，却需要更高 packet rate 和更强 NIC state；batch/chunk 能摊薄 doorbell 与 QP 访问，但增加等待和拥塞反应时间。UCCL-Tran 默认每 32 KB 做一次控制，实机效率高，大规模 sender-driven simulation 却出现 17.9% completion-time 损失。
- **host proxy 与 GPU initiated**：proxy 可以统一不同厂商 verbs、做 bounds check 和排序；GPU initiated 减少 command latency，但强绑定 NIC。UEP 的结果证明“GPU 决定、CPU 代发、NIC 搬 payload”是可行中间点，不证明 CPU 永远有空闲核。
- **注册粒度与保护**：大 MR 摊薄注册成本，却扩大权限范围和内存浪费；小 MR 隔离好，却使 pin、MTT 和 key 管理昂贵。[[FineMem-OSDI25]] 用预注册 MR 加 Memory Window 做细粒度保护，本质是把慢路径预付并保留可撤销的 key。
- **轮询与中断**：busy polling 能缩短 completion latency，却持续耗 core 与能量。[[Sandman-SOSP25]] 在 NVMe-oF/RDMA 环境用浅睡眠、协同唤醒和 burst detection，把性能控制在 SPDK 的正负 5% 内，同时降低 39% 功耗；这说明 progress engine 也是 RDMA 系统的一等资源。
- **RDMA 与 CXL/共享内存**：RDMA 提供网络级显式操作，CXL/共享内存提供 load/store 外观，但仍要处理 coherence、NUMA、failure 和资源仲裁。[[Duhu-OSDI26]] 的 RDMA baseline 只有一个 outstanding request，不能据此断言共享内存抽象天然比 pipeline 后的 RDMA 快。

## 证据边界与相反结果

- **“RDMA 更快”常只是实验底层，不是论文结论。** [[BatchGen-OSDI26]]、[[DINGO-OSDI26]]、[[RLinf-OSDI26]]、[[SDCHunter-OSDI26]] 和 [[Tessera-OSDI26]] 使用 InfiniBand/RoCE 测试床，但没有隔离 RDMA 本身的贡献。引用这些论文只能说明部署条件，不能当成 RDMA 机制证据。
- **快速网络可能不是瓶颈。** [[Blowfish-OSDI26]] 的主要成本是页表路径，[[CetoFS-FAST26]] 是内核与驱动，[[Mage-SOSP25]] 是 fault/eviction 协调，[[Umap-OSDI26]] 是锁和 cache protocol。此时继续升级带宽不会按比例改善端到端性能。
- **专用 fabric 也不总优于软件路径。** [[EcoServe-OSDI26]] 在 10 Gbps Ethernet 上通过时间错峰避免跨实例 KV 传输；它的价值恰好来自“不把高速 RDMA 当部署前提”。[[Bidaw-FAST26]] 选择本地 SSD，而不是 RDMA 池化内存，换来更低成本但需要 I/O-aware 调度。
- **远端原子并非一定应该移除。** [[RCuckoo-ATC25]] 在 ConnectX-5 device memory 和 masked CAS 条件下证明细锁可以有效；[[FARLock-OSDI26]] 也保留 remote queue。正确结论是要控制 placement、跨度和 contention，而不是“atomic 一律不好”。
- **生产证据仍不均衡。** Barre、AITurbo、DeepServe、Greyhound、SakuraONE 等有生产背景；BALBOA、SwCC、UCCL-Tran、Soul 等主要来自小型实机、受控 testbed 或模拟。应把机制可行性与多年多租户稳定性分开描述。

## 引用本概念的论文

### 传输、拥塞控制与 NIC

- [[BALBOA-OSDI26]] — 实现开放 FPGA RoCEv2 engine，在 100 GbE 达约 11.2–11.6 GB/s；范围限于 RC 的一侧 READ/WRITE，性能只测到 32 QP，且没有完整拥塞控制。
- [[Barre-ATC25]] — 在 BlueField-3 PCC 上实现可部署的 RoCE 控制组件；有 10K-GPU 一年生产证据，但可移植性受特定 firmware event 限制。
- [[Coyote-v2-SOSP25]] — 把 RoCEv2 作为可动态重配置 FPGA shell 的系统服务，重点是共享虚拟内存和模块化，不是新的 RDMA transport 语义。
- [[FLB-ATC25]] — 研究 PFC 环境中 load balancing 与拥塞扩散的冲突，并用路径收缩隔离 culprit flow。
- [[FiDe-ATC25]] — 用长期压力测试说明 RDMA 快速路径仍可能出现 243 µs 突刺；它把稳定交互视为 failure detector 的底层要求。
- [[KernelBypassTCP-ATC25]] — 系统比较 kernel-bypass TCP；RDMA 只作为另一条 bypass 路线的对照，论文没有做同接口 head-to-head。
- [[RDMA-LiveMigration-SOSP25]] — 通过设备辅助保存 QP namespace、暂停 packet 和提取状态，实现 passthrough RDMA VM 的透明迁移。
- [[SakuraONE-MLSys26]] — 展示 800-GPU、800GbE RoCEv2 开放网络的生产集群；它是部署与 workload 证据，不是协议微基准。
- [[SwCC-ATC25]] — 把软件可编程、逐包拥塞控制 core 放进 RDMA engine；控制环与 ConnectX-5 都约 3.1 µs，证明接近 ASIC 而不是普遍超过 ASIC。
- [[UCCL-Tran-OSDI26]] — 保留 NIC/GPUDirect payload path，把 transport control 搬到 host；在跨机架碰撞下收益大，但依赖大消息和可预留 CPU core。
- [[UEP-OSDI26]] — 用 CPU proxy 代发 GPU 产生的细粒度命令，统一 EFA、ConnectX 与 Broadcom，并补齐乱序语义。
- [[fabric-lib-MLSys26]] — 在 ConnectX RC 与 EFA SRD 上提供可靠、可乱序的 P2P primitive；400 Gbps 是 WRITE 微基准峰值，不代表所有小写入或应用更新。
- [[rxBisect-OSDI25]] — 从 NIC receive ring 分离 buffer 分配和接收容量；RDMA 是潜在适用数据面之一，现有证据仍是软件仿真与 DPDK 路径。

### 远程内存、索引、事务与分布式状态

- [[ODRP-NSDI25]] — 把 4 KiB remote paging 的分配、TT 翻译、load/store/invalidate 编成 RNIC WR chain，在单 MNode、8 CNode 上实现 100% remote-memory utilization 和近零远端 CPU；代价是固定 swap/page 语义与额外 WR latency。
- [[OneSidedMW-NSDI26]] — 将 RNIC offloading 限制在 type-2 Memory Window bind/unbind 控制面，让正常数据访问保持原生 one-sided READ/WRITE；QP/MW grouping 换来隔离与并行，也增加 RNIC metadata 和配置成本。
- [[Blowfish-OSDI26]] — host 用 RDMA 换入换出 4 KB guest 页面，证明高速网络下页表和虚拟化软件路径反而主导成本。
- [[DGC-OSDI26]] — 用 200 Gbps RDMA 把 JVM marking 放到共享服务；SPECjbb P99 最多降 60.3%，但 12 个 backend 已逼近 NIC 上限。
- [[DMTree-FAST26]] — 把 fingerprint 与锁元数据协作缓存到 compute pool，减少 memory-server RNIC 的 IOPS/带宽热点。
- [[DPA-Store-OSDI26]] — 用 DPA 上的有状态 learned index 替代 client 直接遍历远端树，展示 two-sided/NIC processing 对 stateful one-sided client 的另一种取舍。
- [[Duhu-OSDI26]] — 以 CXL 共享解耦内存承载不可变对象；其 RDMA 对照被限制为单 outstanding request，只能说明该设定下的接口成本。
- [[FARLock-OSDI26]] — 用 local/remote 双队列、Peterson 协调和全局 ticket 同时保留本地快路径与 FCFS。
- [[FineMem-OSDI25]] — 用预注册 MR、Memory Window 和可信分配服务，把细粒度远程分配从昂贵注册路径中分离。
- [[FORGE-OSDI26]] — 用分组、可预测淘汰窗口与 lazy counter flush，减少解耦 cache 中昂贵的远端 metadata 和 atomic。
- [[HDTX-ATC25]] — 在弱 CPU memory node 上用 redo log、visibility 和 RNIC Wait/Enable 把事务 commit 压到 2 RTT。
- [[Mage-SOSP25]] — 说明 page-based RDMA far memory 在多核下会被 fault-in、eviction 和全局协调拖垮，重点在异步流水而非单次网络时延。
- [[Mako-OSDI25]] — 以 WAN geo-replication 为目标；单数据中心比紧耦合 RDMA 系统慢约 50%，是设计目标不同造成的反例。
- [[Nostor-OSDI25]] — 在 RDMA 内存 KV 上以组合设计和 XOR parity 降低容错空间与 stripe fan-out。
- [[Picsou-OSDI25]] — 讨论跨 RSM/WAN 传输时以 RDMA 作为低成本局域网语境对照，并未提出 RDMA datapath 优化。
- [[RCuckoo-ATC25]] — 利用 RNIC device memory 与 masked CAS，让细粒度锁在 small-value disaggregated KVS 中重新可行。
- [[RTSFaaS-ATC25]] — 用 affinity-aware lease 与 TPG 替代每次事务的远端 lock/validation；证据来自 5 节点、约 7 µs RTT 的 RDMA 集群。
- [[Scalio-OSDI25]] — 客户端用 one-sided read/write 做热读 cache 和写缓冲，并用协议限制 CAS，服务 DPU JBOF。
- [[Soul-OSDI26]] — 把锁权限与数据 coherence 合并；当前 Ethernet 实现依赖 lossless RoCE/PFC、可靠有序且无故障的 transport。
- [[Spirit-SOSP25]] — 在共享 RDMA remote swap 中联合分配本地 cache 和远端带宽，说明两种资源可互换但拥塞收敛仍缺证据。
- [[uTPS-SOSP25]] — 在 200 Gbps RDMA/DPDK KVS 上按 cache residency 拆线程池，并以 SRQ/MP-RQ 支持在线重配置。

### AI 训练、推理与模型状态搬运

- [[AITurbo-FAST26]] — 借用空闲 compute fabric 和 host DRAM做 AI bulk I/O staging；P2P QP 约 15 ms 建立，RoCE 只用最低优先级 QoS，细粒度隔离仍未解决。
- [[BatchGen-OSDI26]] — 在 200 Gb/s InfiniBand 上评测离线大批量生成；RDMA 是 KV migration/offload 的条件，不是主创新。
- [[CrossPipe-ATC25]] — 研究跨数据中心 pipeline training；其结论提醒通信调度仍受 receive post、buffer 和 dependency 影响，RDMA 本身不消除 pipeline bubble。
- [[DCP-OSDI26]] — 当前主实验是 PCIe GPU serving；把 RoCE/RDMA 下 PP、TP 与 hybrid 的交叉点列为待验证问题。
- [[DeepServe-ATC25]] — 用 RoCE/HCCS NPU-fork 加速模型复制；普通 RoCE 为 0.71–0.91 s，HCCS 为 0.15–0.19 s，收益明显受互连层级影响。
- [[DynaRL-OSDI26]] — 在每节点 8 张 400 Gbps RoCEv2 NIC 的 H100 集群测在线资源迁移；没有注入 fabric contention 或故障。
- [[EcoServe-OSDI26]] — 通过时间错峰减少 KV 跨实例传输，在慢 Ethernet 上也有效；它是“不把 RDMA 当必要条件”的重要对照。
- [[FaaScale-MLSys26]] — 用 400 Gb/s InfiniBand 与 GPUDirect 做 block multicast，并让模型未传完就开始 pipeline 推理；低带宽或 jitter 会缩小收益。
- [[FreeScale-MLSys26]] — 用 CPU-RDMA ring 传无 reduction collective，避免 NCCL 与 dense kernel 争 SM；依赖高速 host path。
- [[FuseLink-OSDI25]] — 通过 NVLink 把多块空闲 NIC 聚合成动态链路，并以 RDMA 完成跨机 GPU 传输。
- [[GPU-CC-Security-MLSys26]] — 从 DMA、BAR 和 I/O metadata 角度审视 confidential GPU；RDMA 在这里属于威胁面，而不是单纯性能工具。
- [[Greyhound-ATC25]] — 用 NCCL timeline 检测生产 GPU/RoCE fail-slow，并以 P2P RDMA swap 调整 topology；真实根因仍可能包含 firmware 和共享链路。
- [[Hermes-ATC25]] — 把 RDMA retransmission、小包和 HBM contention 纳入 Ascend 训练的分层诊断，强调通信问题必须与 host/device 时间线联合解释。
- [[Hetu-v2-OSDI26]] — 在 graph switching 时用 fused reshard 平衡 NVLink/InfiniBand 流量；RDMA 是异构计划切换的数据通道。
- [[HypeReca-ATC25]] — 发现细粒度 one-sided embedding fetch 利用率低，改用远端 gather 后发送连续批次。
- [[NEST-MLSys26]] — 把层级网络成本纳入分布式 placement；RDMA 只是成本矩阵的一种 fabric，动态拥塞未建模。
- [[NVIDIA-Disagg-Study-MLSys26]] — 模拟与原型表明典型数据中心配置下 KV 跨池带宽通常可承受，但结论依赖 NIXL 的异步 RDMA/NVLink 和正确 topology。
- [[Prism-OSDI26]] — 以 host DRAM、NVLink 或 GPUDirect RDMA 快速激活模型/KV；跨节点与较弱 host memory 尚待验证。
- [[RLinf-OSDI26]] — 在最多 256 张 H100 和 400 Gbps RoCEv2 上评估 RL workflow 计划；RDMA 贡献没有单独消融。
- [[RobustRL-OSDI26]] — 失败后通过 UCX/RDMA 动态重连和分片权重拉取，展示弹性系统不能依赖固定 NCCL membership。
- [[RollArt-OSDI26]] — 区分小而频繁的 trajectory 与 61.02 GB 权重更新；跨 cluster 400 Gbps RDMA 仍需 9.442 s，所以最终用 bucket 化与 overlap。
- [[SDCHunter-OSDI26]] — 在高速 RDMA GPU 集群做确定性 replay 诊断；网络型号和带宽未报告，不能用来量化 RDMA 对诊断开销的贡献。
- [[Seer-OSDI26]] — 依赖 Mooncake 分层 KV pool 和每节点 8×400 Gbps RDMA 迁移 rollout chunk；3 TB 累计迁移在低配或共享 fabric 上可能变成瓶颈。
- [[Syncopate-OSDI26]] — 当前只优化单机 GPU 通信；跨节点 lowering 仍需显式处理 RDMA completion、progress 和 failure。
- [[Tessera-OSDI26]] — 在 4,096–12,288 张 Hopper/RoCE GPU 上联合 pipeline partition 与通信重叠；结果绑定内部 profile 和网络版本。
- [[TrainMover-OSDI26]] — 两阶段 CCL 只切换受替换机器影响的 QP，使连接准备与训练状态搬运尽量离开停机窗口。
- [[Weave-OSDI26]] — 模型先跨 20 Gbps 慢链路传一份，再在集群内用 400 Gbps InfiniBand/NVLink 广播，说明分层 topology 比一律使用最快 primitive 更重要。

### 存储、操作系统与其他对照

- [[Bidaw-FAST26]] — 选择本地 SSD 做 KV 容量层；RDMA 池化内存是更快但成本不同的未对比路线。
- [[CetoFS-FAST26]] — 在 NVMe-over-RDMA Optane 上把数据面与权限、并发、日志协同卸到 storage target，直接展示内核路径的放大。
- [[Copier-SOSP25]] — 把 copy 作为 OS 服务；与 RDMA/DPDK zero-copy 的整合被明确留为空白。
- [[CoreSec-OSDI26]] — 把 RDMA timeout 作为 server–ToR 故障诊断证据之一，关注的是 telemetry 可信度而不是数据通路。
- [[DINGO-OSDI26]] — 使用 40 GbE InfiniBand 测 HDFS 维护 I/O 合并；RDMA 只是测试床条件。
- [[DRack-ATC25]] — 用 CXL 池化 rack 内 NIC；当前 socket 透明层没有覆盖 RDMA verbs，强依赖 verbs 的应用仍需适配。
- [[DShuffle-ATC25]] — DPU 经 RDMA 把 shuffle spill 发到远端 DPU 后直写磁盘，代价是新的 failure、retry 与隔离问题。
- [[FastACS-ATC25]] — 用内部 RMA one-sided read 服务热尾数据；论文提出应在 commodity RDMA 上验证可移植性。
- [[HATS-FAST26]] — RDMA/disaggregated compaction 只作为未来架构；现有证据来自 Cassandra 内的分层调度。
- [[LESS-FAST26]] — 指出高速 RDMA/InfiniBand 普及后，repair 可能转而受磁盘 seek 主导；主测试床仍是 HDD 与普通以太网。
- [[Lockify-FAST26]] — 把“单客户端零通信”当 emulated RDMA 上界，不能视作真实 RDMA DLM 的 head-to-head。
- [[M3U-OSDI26]] — 主实验是 100 Gbps VM migration；RDMA 只在未来 topology sweep 中出现，当前不能证明最佳 worker 数可迁移。
- [[MAIO-FAST26]] — 以兼容的 page-cache 控制加速模型加载，对比需要深改推理栈或 RDMA/NVLink 的专用路线。
- [[MOST-FAST26]] — 把 RDMA 远端 NVMe 作为异构两层存储的一种部署背景；核心机制是 tiering 与少量 mirror。
- [[Okapi-OSDI25]] — 讨论纠删码 stripe 与 group 解耦；RDMA 只作为快存储对比语境。
- [[Oxbow-OSDI26]] — 通过 BlueField-2 加 RDMA/NVMe-oF 模拟计算存储设备；收益主要来自混合内核/用户态文件系统协议。
- [[Para-ksm-ATC25]] — 以片外 RDMA SmartNIC 对比片内 DSA，说明 4 KB 去重算子很容易被设备往返延迟支配。
- [[PathWeaver-ATC25]] — 多 GPU ANNS 只测到单机 4 GPU；跨节点 RDMA 是尚未验证的扩展边界。
- [[Pluto-OSDI26]] — 当前分布式图评测没有给 RDMA break-even；论文把不同 RTT、带宽与聚合粒度扫参列为后续工作。
- [[Poby-ATC25]] — 用 RNIC 接收镜像、硬件解压、host 解包；它用大块连续传输避免小文件造成 PCIe/RDMA transaction 放大。
- [[Sandman-SOSP25]] — 在 200 Gbps RDMA NVMe-oF 上减少 busy polling 能耗，表明低延迟 completion 与功耗需要联合调度。
- [[SwitchGNN-ATC25]] — 使用 P4 in-network multicast/aggregation；它与标准 RDMA 集群的接口、运维和升级差异尚未量化。
- [[Umap-OSDI26]] — 说明把 DFS 链路换成 RDMA 不能消除 `mmap` 的全局锁、4 KB fault 和 cache 一致性问题。

## 已知局限 / 开放问题

- **统一 transport API 仍不等于统一语义。** UC、RC、UD、SRD 对 ordering、atomic、重传和接收 buffer 的要求不同。需要用同一 failure suite 验证 timeout、乱序、重复、partial write、sequence wrap 和 reconnect，而不只比较带宽。
- **注册内存的撤销与隔离仍很脆弱。** 生产系统需要回答 stale rkey、进程退出、GPU reset、VM migration、页迁移和 tenant teardown 时谁先停止 DMA、谁回收 key，以及如何证明没有 use-after-free。
- **拥塞控制缺少跨层闭环。** 应把 application deadline、collective phase、NIC queue、ECN/PFC 和路径状态放进同一实验，报告 goodput、P99、victim flow、公平和 CPU/core-hours；只给无拥塞 line rate 或单一 incast 倍率不够。
- **CPU 机会成本经常没有闭合。** host proxy、polling、reassembly 和 software transport 都会占 core。未来评测应在相同总 CPU/GPU/NIC 预算下，注入 data loading、storage I/O、co-tenant 和 NUMA 错放，再看端到端吞吐。
- **小消息和混合流量证据不足。** 很多 GPU 论文以 MB–GB collective 证明吞吐；真正的 serving、agent、metadata 和 control traffic 可能是 KB 级并和 bulk flow 共存，需要报告 packet rate 与 tail latency。
- **安全与可观测性需要成为一等语义。** 可编程 transport、shared QP、remote atomic 和 GPU DMA 都需要访问控制、审计、trace、故障定位与可回滚升级。现有论文多把这些问题留给部署者。
