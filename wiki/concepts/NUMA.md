---
type: concept
aliases: [Non-Uniform-Memory-Access]
last_updated: 2026-08-14
tags: [hardware, memory, scheduling, placement]
---

# NUMA

> 非一致内存访问（Non-Uniform Memory Access，NUMA）表示处理器访问内存、缓存和 I/O 设备的成本随拓扑位置而变；线程、页面、内存通道与设备必须联合放置，才能同时得到 locality、带宽和隔离。

## 核心思想

多 socket 服务器不是一个均匀的大内存池。每个 CPU socket 或 chiplet 更接近自己的 DRAM channels、LLC 与 PCIe root complex；访问远端 node 通常要经过 socket interconnect，延迟更高、可用带宽更低，还会和其他流量争用。Linux 因此把 CPU 和 memory 暴露为 NUMA nodes，并提供 first-touch、interleave、bind、preferred、page migration 与 automatic NUMA balancing 等策略。

NUMA 正确性通常不受 placement 影响，性能却可能相差很大。只 pin thread、不约束 page，线程仍会访问远端内存；只追求 page locality、不平衡线程和 memory channel，又可能让一侧拥塞、另一侧空闲。NIC、GPU、NVMe SSD 的 DMA 路径也有 home socket：device、completion poller、application thread 与 DMA buffer 分散在不同 node 时，控制和数据都可能绕远。

随着 [[CXL]]、GPU unified memory 和 memory tiering 出现，“本地/远端”不再只是二元关系。系统面对的是带宽、延迟、容量、coherence 与 failure domain 不同的多个 tier。OSDI 2026 的论文进一步把 channel、object、cache set 和 accelerator 侧内存都纳入 placement；NUMA node 仍是通用控制接口，却不一定是最佳决策粒度。

## 为什么重要

NUMA 会决定优化能否落到真实机器上。[[RamRyder-OSDI26]] 关闭默认 channel interleaving，把每条 DRAM/CXL channel 暴露成 channel-level NUMA node，借此分别控制 VM 容量与带宽。它说明传统 node 粒度有时太粗，也说明“软件定义带宽”依赖 BIOS、physical-address mapping、定制 QEMU/guest 和 workload 配对，不是免费抽象。

NUMA 还经常是论文没有覆盖的外推边界。[[DeLFS-OSDI26]]、[[SBB-OSDI26]]、[[CoPilotIO-OSDI26]]、[[Strata-OSDI26]] 都在双路或异构平台上获得结果，却没有完整分解跨 socket placement。若概念页把这些引用都当成“NUMA-aware 机制”，会夸大证据；其中不少论文只是明确承认远端内存或跨 socket 可能让现有结果变差。

资源池化让 NUMA 更重要。[[Duhu-OSDI26]] 用单机 remote NUMA 模拟更快的共享内存，只能证明性能方向，不能替代真实多主机 CXL；[[Espresso-OSDI26]] 和 [[MAC-OSDI26]] 也用双路 NUMA/NVMeVirt 或 NUMA 仿真补足尚不存在的硬件。NUMA emulator 保留部分延迟/带宽差异，却不自动复现 fabric routing、coherence、故障和多租户争用。

## 关键观察 / 隐含假设

- **线程、页面、cache 和 device 是一个联合 placement 问题。** [[RamRyder-OSDI26]] 的 channel isolation 同时配合 CCX/LLC pinning；论文的消融显示 channel sharing 是主要干扰，但完整结果不能只归因于页面放置。
- **容量与带宽不是同一资源。** RamRyder 让少量容量横跨更多 channels 取得带宽，或让低带宽 VM 使用同一 channel 剩余容量；这种“基本独立”依赖互补 workload 和粗粒度 channel 数量。
- **NUMA node 可能仍然太粗。** [[OBASE-OSDI26]] 指出一张 node-local page 内仍可有大量冷对象；[[Sepia-OSDI26]] 关注 DMA page 映射到 LLC set/slice 的分布。local page 不等于每个字节或 cache set 都高效。
- **观测必须跟上 placement 粒度。** [[NEMO-OSDI26]] 面向多 socket、CXL 和 accelerator memory 提供更灵活、及时的 page access 观测；如果 telemetry 只能给平均 bandwidth，就难以区分远端访问、热点页和 channel contention。
- **迁移能适应 phase change，也会制造新的流量。** RamRyder 用 PTE fault 和 lazy migration 跨 channel 重分布页面；每秒采样与约秒级搬迁会漏掉短 burst，并把 fault/migration 开销放到应用路径。
- **固定 per-core ownership 隐含稳定 affinity。** [[DeLFS-OSDI26]] 的 local domain 在容器改 affinity、CPU hotplug、任务迁核或 remote-memory placement 下可能削弱；论文未按 socket 分解结果。
- **host memory tier 常被假定为便宜且不争用。** [[DirectKV-OSDI26]]、[[ECHO-OSDI26]] 和 [[Strata-OSDI26]] 都依赖 pinned host DRAM 与 PCIe；多 GPU、多租户或跨 NUMA 会改变它们的 offload/cache 带宽。
- **remote NUMA 不是 CXL 的完整替身。** [[Duhu-OSDI26]]、[[Espresso-OSDI26]]、[[MAC-OSDI26]] 的模拟有助于验证 software path，但不能证明真实 CXL switch、device coherence、tail latency 和 failure behavior。
- **很多论文共同假设 phase 足够稳定。** placement、cache、work stealing 与 offload 需要在迁移成本收回前保持有效；[[FlowANN-OSDI26]]、[[Svalinn-OSDI26]]、[[UCCL-Tran-OSDI26]] 都把 topology/jitter 变化列为可能失效条件。

## 设计空间与取舍

- **First-touch / bind / interleave**：first-touch 简单但依赖初始化线程；bind 强化 locality 却可能热点；interleave 平衡 channel 带宽，却增加单线程 latency 并放弃部分 row-buffer locality。
- **Thread migration / page migration / work stealing**：迁线程便宜但可能丢 cache locality；迁 page 保持执行位置却复制大量数据；偷 task 适合短期偏斜，但跨 node queue 和 cache-line transfer 更贵。
- **Node / channel / page / object 粒度**：node 控制简单、状态少；channel 能隔离 bandwidth；page 是 OS 常用单位；object 更贴近真实热度，却需要 runtime、allocator 或地址编码配合。粒度越细，观测与 metadata 越重。
- **Static placement / feedback control**：静态 pinning 稳定、可预测；在线迁移适应 phase，但要选择采样周期、hysteresis 与迁移预算，短 burst 可能来不及响应。
- **Locality / load balance**：严格本地化可能留下空闲核和 channel；追求平衡则增加 remote access。调度器应按 workload 的 latency、bandwidth 与 cache footprint 选择，而非固定一条规则。
- **Hardware interleaving / software-visible channels**：硬件按 cache line 交错，透明且细；[[RamRyder-OSDI26]] 关闭它以获得 channel ownership，换来 BIOS 重配、较粗分配和 software interleaving 开销。
- **真实硬件 / NUMA 仿真**：仿真便于探索尚不可得的 CXL/NMP 设计；结论必须明确哪些延迟来自实测、哪些来自模型，不能把应用 speedup 当作真实 device 结果。

## 引用本概念的论文

### 以拓扑、带宽或 placement 为核心

- [[RamRyder-OSDI26]] — 将 physical memory channel 暴露为可分配的 C-NUMA node，并用 S-NUMA 对应用隐藏细节；单机隔离证据强，cluster 利用率提升来自 trace 配对外推。
- [[Catur-MLSys26]] — 用 placement defect、持续训练与 speculative shielding 学习云 VM 的 NUMA 放置；核心证据是 1 亿 VM trace replay，硬件细节与公开复现仍有限。
- [[NEMO-OSDI26]] — 为 NUMA、CXL 与 accelerator memory 提供细粒度、及时的 memory observability，服务 placement 与 tiering policy。
- [[OBASE-OSDI26]] — 在 page 内按对象热度重排，说明 node-local/page-local 仍可能含大量冷字节。
- [[SBB-OSDI26]] — 去中心化用户态网络 runtime；NUMA-local stealing 是后续工作，48-worker 跨 node placement 没有充分报告。
- [[ScaleSwap-FAST26]] — 以 per-core swap resource 与 delegation 扩展多核、多 NVMe swap；NUMA placement 会影响其共享资源路径。
- [[DSA-2LM-ATC25]] — 用 Intel DSA 批量卸载分层内存页复制；它加速迁移执行，但继承的 hotness placement 未必选到最影响性能的页面。
- [[SoarAlto-OSDI25]] — 用 latency、MLP 与 CPU stall 重估分层内存 placement，说明“最热页面优先放快层”并不总是性能最优。

### 内存池化、分层与异构执行

- [[Duhu-OSDI26]] — 用 remote NUMA 模拟更快共享内存，明确该结果不能等同真实多主机 CXL。
- [[DirectKV-OSDI26]] — GPU kernel 直接访问 CPU-resident KV cache；依赖 pinned host memory 与可控 NUMA bandwidth。
- [[ECHO-OSDI26]] — 稀疏注意力 KV offload 假定大容量 host pool 与 PCIe 基本独占；多 NUMA/tenant 未验证。
- [[Strata-OSDI26]] — 分层上下文缓存的 host bandwidth 结果依赖 pinning 和 socket locality。
- [[Wang-LocalMoEInference-OSDI26]] — CPU–GPU 混合 MoE 推理需要按 CPU core、memory channel 与 GPU 拓扑放置。
- [[LiteSwitch-OSDI26]] — 将远端 NUMA 与 switched CXL 作为更长 memory stall 的来源。
- [[MAC-OSDI26]] — 用双 NUMA 仿真与 FPGA 热路径验证 CXL 侧回收元数据加速；完整系统仍不是原生 CXL 3.x。
- [[Espresso-OSDI26]] — 以双路 NUMA 和 NVMeVirt 做应用级仿真，不能替代真实盘间 CXL transaction。
- [[Megalon-OSDI26]] — 使用修改后的 NUMA Node Replication 维护部分一致 CXL 内存上的本地索引副本。
- [[Weave-OSDI26]] — RL 后训练的组大小与切换成本受 host oversubscription、NUMA 和 PCIe 拥塞约束。

### 作为实现假设、评测环境或未覆盖边界

- [[ARCTIC-OSDI26]] — benchmark 将内存和 core 均匀 interleave 到两个 node；因此未比较 locality policy。
- [[CoPilotIO-OSDI26]] — CPU poller、GPU、SSD 的跨 node 拓扑是未覆盖边界。
- [[DGC-OSDI26]] — NUMA/cgroup 可隔离资源，却不能阻止共享 marker 读取其他 runtime heap。
- [[DVLA-OSDI26]] — VM placement debt 指标没有纳入 NUMA、memory、network 与 accelerator 约束。
- [[DeLFS-OSDI26]] — 双路平台未按 socket 分解 per-core domain 的 remote-memory 成本。
- [[FlowANN-OSDI26]] — fetch-window 上界可能被 NUMA、排队与多租户长尾打破。
- [[Ichnaea-OSDI26]] — object tracking 只在单台 Intel 机器评测，缺少 NUMA/高线程压力。
- [[InfiniDefrag-OSDI26]] — 多 VM 结果未覆盖 NUMA 分区、超配和长期 churn。
- [[M3U-OSDI26]] — vCPU 固定在单 socket；高端 VM post-copy 结论依赖该放置。
- [[MDK-OSDI26]] — accessed-bit 操作会影响 NUMA/reclaim，framework 未建模共享页与共同 tier pressure。
- [[MIMESYS-OSDI26]] — 相同平均资源 trace 无法复现 NUMA locality 造成的尾延迟。
- [[Merlin-OSDI26]] — 只扩到 32 threads，未报告 NUMA placement，吞吐外推受限。
- [[PeeR-OSDI26]] — 将 NUMA-local work stealing 留为后续工作。
- [[Quark-OSDI26]] — node agent 把 NUMA topology 纳入 batch capacity normalization。
- [[Rakaia-OSDI26]] — 单台小规模老款 Xeon 结果未覆盖多 socket/NUMA。
- [[Sepia-OSDI26]] — 单 socket page coloring 结果可能被跨 NUMA、多 NIC 和后台流量破坏。
- [[Svalinn-OSDI26]] — overload controller 假定 NUMA/cache 干扰不会在一个周期内剧烈改变最优并发。
- [[TypeCraft-OSDI26]] — 类型热点诊断不自动检查 NUMA、false sharing 与 ABI 回归。
- [[UCCL-Tran-OSDI26]] — CPU oversubscription或 NUMA 错置会把 transport jitter 带入 GPU 网络尾延迟。
- [[UEP-OSDI26]] — 每 GPU 固定 CPU proxy，跨 NUMA placement 可能进入 token critical path。
- [[kSTEP-OSDI26]] — 一部分 scheduler bug 只有 NUMA、非对称核心等特殊拓扑才可触发。
- [[vBOIDs-OSDI26]] — balancer 把目标 core 限制在允许的 NUMA topology 内，以避免任意远迁。
- [[MAIO-FAST26]] — 为 LLM model loading 重做可编程 page-cache policy，并把默认内核忽略 NUMA/XPU affinity 作为关键动机之一。

## 已知局限 / 开放问题

- OS 缺少统一描述 CPU、LLC、memory channel、CXL switch、GPU/NIC/NVMe 与带宽争用的 topology model；仅有 node distance 不够表达共享 link。
- page migration、scheduler migration、DMA buffer relocation 和 device queue ownership 各自优化，可能相互抵消；需要联合控制面与可观测性。
- physical channel 是粗粒度资源。租户数多于 channel、多个 bandwidth-heavy workload 同时 burst 时，隔离与利用率难以兼得。
- huge page、pinned/DMA page、unmovable kernel memory、confidential VM 和 live migration 会限制在线重放置；失败时的回退与进度上界仍不清楚。
- NUMA 仿真应报告模型误差，并在真实 CXL/多 socket hardware 出现后复验；应用级平均性能不足以验证 tail、coherence 与 failure behavior。
- 多租户 placement 应同时报告 latency、bandwidth、cache miss、UPI/CXL traffic、migration bytes、能耗与公平性，而不是只给单一吞吐。
