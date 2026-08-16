---
type: paper
name: RamRyder
full_title: "Break on Through to the Other Side: Pooling Memory Elastically with RamRyder"
authors: [Yanbo Zhou, Erci Xu, Dongjoo Seo, Adam Manzanares, Steven Swanson]
venue: OSDI
year: 2026
tags: [memory, virtualization, cxl, bandwidth-isolation, resource-pooling]
source_pdf: "[[osdi26-zhou-yanbo.pdf]]"
source_md: "[[osdi26-zhou-yanbo]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# RamRyder：分别弹性分配虚拟机的内存容量与带宽（OSDI 2026）

> **原题**：Break on Through to the Other Side: Pooling Memory Elastically with RamRyder

> **一句话总结**：RamRyder 关闭默认的 DIMM channel interleaving，把每条 DDR/CXL memory channel 变成可分配资源，并在修改后的 QEMU 和 guest Linux 中控制 page-to-channel mapping，从而给 VM 隔离带宽、按需增减容量或带宽；单机实测的应用性能通常距独占硬件 baseline 不超过 5%，但论文所称平均容量利用率提高 28.6%、平均带宽利用率提高 43.2% 来自 Alibaba trace 中对可配对 servers 的分析外推，不是生产 cluster 部署结果。

## 问题与动机

Cloud VM 通常按固定的 memory-capacity-to-vCPU ratio 售卖，用户可以买多少 GB，却不能直接预订多少 GB/s。Latency-sensitive 服务为了避免 noisy neighbor，常购买半台甚至整台 server；bandwidth-intensive job 为了获得更多 channels，也只能顺带购买不需要的 capacity 和 cores。这样可以隔离性能，却把容量和带宽一起过度配置（§1、§3.2）。

论文分析一份大型 cloud trace 后发现，带宽闲置比容量闲置更严重：90% servers 的平均 memory-bandwidth utilization 不超过 44.5%，peak 也不超过 82.2%；与此同时，55.4% servers 的平均和最高 capacity utilization 都大于 90%，仍有 18.3% servers 的平均 capacity utilization 少于 60%。单台 server 的 capacity、bandwidth 和 CPU demand 在时间上也没有明显相关性（§3.1、图 2–3）。超过 30% servers 有持续一小时以上的 capacity off-peak，超过 90% 有同样长的 bandwidth off-peak（§3.2）。

现有方案只解决一半问题。[[CXL]] pooling/tiering 主要弹性扩展容量，不提供 bandwidth reservation；Intel MBA、AMD QoS 等 hardware throttle 在 cache path 注入 delay，限速不精确且浪费 core cycles；限制 cores、frequency 或 LLC ways 又会牺牲 VM 已购买的其他资源。Load/store 直接访问 cache-coherent DIMM/CXL，host software 也无法像 network packet 一样在每次 access 上调度（§3.3、图 4）。

RamRyder 的出发点是：一条 memory channel 既是物理 contention boundary，也是近似固定的 bandwidth unit。Bandwidth 随 DIMM channel 数近线性增长；若两个 VMs 不共享 channel，再把 LLC 分开，它们就很少互相干扰。系统因此不在每次 memory access 上限速，而是在较慢的资源管理路径上决定“这个 VM 能映射到哪些 channels”（§4、图 5–6）。

## 关键观察 / 隐含假设

- **观察 1：channel count 可以近似代表可用 bandwidth。** Testbed 上 DIMM channels 在 read-only 和 mixed read/write 下近线性扩展；CXL channel 也增加 bandwidth，但每条的带宽较低、斜率更小（§4、§6.4、图 5、图 18）。
  - **依赖假设**：OS 能知道 physical address 到 channel 的映射，设备内部不会再用不可见方式 interleave。论文的 CXL 2.0 devices 每台内部正好一条 DDR5 channel；未来多 channel CXL device 不一定满足这一点。
- **观察 2：channel sharing 比 LLC sharing 造成更强的 interference。** Redis ablation 中，只隔离 LLC 改善有限，只隔离 channels 已消除大部分干扰，两者都隔离最好（§6.4、图 17）。
  - **重要边界**：RamRyder 的端到端 isolation 同时把各 VM vCPUs pin 到不同 CCX/LLC，不能把所有结果只归因于 page placement。
- **观察 3：capacity demand 与 bandwidth demand 可以互补。** 一个 VM 可以占少量 CXL capacity、跨多条 channels 取带宽；另一个 VM 再使用这些 channels 剩余的大量 capacity，但保持低 bandwidth demand（§4.2、图 8）。
  - **依赖假设**：resource manager 能找到这种互补 workload，且二者的峰值不会同时超过 physical limit。对 local DIMMs，初始 bandwidth 仍按 capacity/vCPU 比例分配，所以“独立”主要来自 CXL channel selection 和 cross-VM pairing，论文也称为 mostly independently。
- **观察 4：需求变化通常足够慢，可以先 attach channel 再搬 pages。** Trace 中有大量一小时以上的 off-peak；prototype 每秒读取 bandwidth counter，并在连续多秒越过 high/low threshold 后增减资源（§3.2、§4.3）。
  - **依赖假设**：持续变化多于秒级，page redistribution 也能跟上。图 21 明确显示系统会错过 very short bursts，对其他突增也比 fully over-provisioned Ideal 晚。
- **观察 5：已有 NUMA 与 memory hot-plug 机制可以承载 channel abstraction。** Hypervisor 把每条 channel 暴露成 C-NUMA node，guest 再把同一 socket/CXL tier 的 C-NUMA nodes 组合成应用可见的 S-NUMA node（§4.1、图 7）。
  - **依赖假设**：guest kernel 可以修改，applications 不必直接看到 cNodes；page fault、migration、hot-unplug 和 NUMA policy 在实际 VM lifecycle 中都能正确配合。

## 核心方法

### 把 physical channels 交给 software

Server 默认会把 physical addresses 细粒度 interleave 到一个 socket 的所有 DIMM channels，OS 看不到独立 channel。RamRyder 在 BIOS/UEFI 里关闭 channel interleaving，使每条 DIMM 对应一段线性 physical address range；provisioning tool 跳过 host firmware/OS holes，给 host OS 保留 10 GB，其余 region 用 `memmap` 作为独立 DAX device。每个 CXL device 在 testbed 内只有一条 DDR5 channel，因此也把整台 device 保留为一个 DAX device（§5.1、图 10）。

这里的“commodity server without hardware modifications”只表示不改 CPU、DIMM 或 CXL hardware。部署仍要重配 BIOS/UEFI、改变 host memory layout，并修改 QEMU 与 guest Linux；不是在现有 cloud stack 上打开一个开关就能使用。

### C-NUMA、S-NUMA 与页面分配

User-space resource manager（RM）把每条 channel 的 DAX region 切成 128 MB chunks，这是 Linux memory-hotplug block size。修改后的 QEMU 把同一 DAX device 上分配给 VM 的 chunks 组成一个 NUMA node，并通过 ACPI 告知 guest 它属于哪个 socket、DAX device 和 channel。Guest kernel 把它建立为 channel-level NUMA node（cNode），再把同一 server socket 或 CXL zNUMA domain 下的 cNodes 合成 server-level NUMA node（sNode）；applications 只看到 sNodes（§4.1、§5.2、图 7、图 11）。

分配 page 时先执行普通 server-level NUMA policy 选 sNode，再在其 cNodes 之间平均、按 page 粒度交错。这样 applications 不必改变，pages 又能并行使用 VM 已获准的全部 channels。为了隔离 LLC，RM 还把不同 VM 的 vCPUs pin 到不同 CCX（§4.1）。

### 分别扩展 capacity 和 bandwidth

对 local DIMM，VM 得到的 channel 数仍与 capacity 比例一致。CXL 路径增加了两个自由度（§4.2、图 8）：

1. **Channel selection**：同样一段 guest physical memory 可以横跨更多 CXL channels 以取得 bandwidth，也可以集中在较少 channels 只取得 capacity。某 VM 横跨 channels 后留下的 capacity，可配给 low-bandwidth VM。
2. **Cross-tier placement**：若目的是扩容量，沿用 Linux tiering，把 hot pages 留在 DIMM、cold pages 放到 CXL；若目的是扩带宽，则按各 sNode 的最大 bandwidth 做 weighted interleaving。例如 3 条每条 36 GB/s 的 DIMM channels 加 1 条 27 GB/s CXL channel，DIMM:CXL page ratio 为 8:3；每个 sNode 内仍平均 interleave 到 cNodes。

这不是把一条 channel 的 capacity 与 bandwidth 从物理上拆开，而是控制一个 VM 的 pages 跨几条 channels，再用多个需求互补的 VMs 填满各 channel。因此 allocation granularity、可配对性和 CXL tier 性能仍限制“解耦”程度。

### 运行时弹性与惰性重分布

RM 经 domain socket 读取 guest `meminfo` 监测 capacity，经 `perf_event` 的 per-core counters 汇总每个 VM 的 bandwidth，每秒采样一次。文中策略示例是在 utilization 连续多秒高于 80% 时增加资源，低于 40% 时回收；capacity 复用普通 memory hot-plug，bandwidth 则改变 channel 数（§4.3、§5.2）。

若总 capacity 为 `X`、原来跨 `N` 条 channels，增加 bandwidth 时先从新 CXL channel 映射 `X/(N+1)` guest physical memory 并 hot-plug 成新 cNode，然后把旧 `N` 条 channels 上总计同样大小的 memory hot-unplug，最终 capacity 仍为 `X`，channel 数变为 `N+1`（§4.3、图 9）。

已经分配的 pages 不会自动使用新 channel。Guest 扫描对应 page-table entries、清除 present bits；application 再访问时触发 page fault，kernel 重算 sNode/cNode，把位置不符的 page 标记为 migration。增加 channel 时采用 lazy migration，回收时需要更快地把 page 移出被 unplug region。这个机制把一次大搬迁摊开，却会在 application path 上加入 faults 和 migration traffic（§4.3）。

## 设计取舍

- **Physical channel isolation 换精确 bandwidth QoS**：不靠 delay 限速，干扰小；每 socket 只有约 12 条 DIMM channels，资源稀缺且粒度很粗。
- **关闭 hardware interleaving 换 OS 控制**：VM 可独占 channels；page-granularity software interleaving 不如 cache-line hardware interleaving 细，single-thread row-buffer locality 会变差。
- **修改 guest kernel 换 application transparency**：applications 只看 sNodes、不改代码；cloud operator 要维护定制 Linux、QEMU、ACPI 和 hot-plug protocol。
- **CXL mapping 换 capacity/bandwidth 部分解耦**：可以少量 capacity 跨多 channel，或多 capacity 集中少 channel；CXL latency、单 channel bandwidth 和配对 workload 决定实际效果。
- **Lazy page migration 换平滑扩容**：不在 attach 时暂停搬完所有 pages；带宽提升要等 faults/migration，访问 pages 承担额外 latency。
- **每秒 feedback 换低 controller overhead**：能跟踪持续 demand；少于采样/redistribution 时间的 burst 会错过。
- **CCX pinning 换完整 isolation**：同时移除 LLC noisy neighbor；也限制 CPU placement，并让 channel 与 cache 两种收益必须靠 ablation 区分。

## 实验与结果

- **实机 testbed、VM 与 baseline**：论文使用单台 AMD EPYC Zen 5 server，128 logical cores（SMT）、每 socket 12 条 DDR5 channels；实验只用一个 socket 的 8 条 channels，每条装 32 GB DDR5。机器有 8 个 CPU dies，每个 32 MB L3/16 logical cores，以及 4 台 256 GB Samsung CXL 2.0 devices，运行 Debian/Linux 6.15。VM1/2 各 16 vCPUs、32 GB、1 条 DIMM channel，VM3/4 各 48 vCPUs、96 GB、3 条 channels，四个 VMs pin 到不同 CCX。Baseline 为无 co-location、独占硬件的 Ideal；默认 channel sharing 的 Shared；以及在 Shared 上按 capacity/core 比例配置 Intel MBA/AMD QoS 的 HW-Throttle。Ideal 可能让 VM 在同样 bandwidth level 使用更多 channels，因此不是完全等资源的 baseline（§6、§6.1）。
- **实机 microbenchmark isolation**：Intel MLC 在每 core 使用 100 MB buffer、64 B stride，四个 VMs 同时跑 read-only 或 3:1 read/write。Shared 下小 VM1 的 read latency 最多比 Ideal 高 78.5%，maximum bandwidth 最多低 41.2%；HW-Throttle 仍不能精确隔离。RamRyder 的 VM1 latency 距 Ideal 少于 5%，并最多比 Shared 低 42.7%。Mixed traffic 趋势相同，但 VM2 在 Ideal 和 RamRyder 中都比 read-only 少约 15.3% bandwidth，说明 channel 数并不是跨 read/write mix 的统一带宽单位（§6.1、图 12）。
- **实机 application workloads**：Memcached/Redis 各装入 6000 万个 16 B key/1 KB value，并跑 3000 万次 YCSB operations；Shared/HW-Throttle 的 Memcached tail latency 在 YCSB-A/F 分别高 31.4%/27.2%，Redis worst case 高 42.7%，RamRyder 保持在 Ideal 的 5% 内，Redis YCSB-D throughput 比 Shared 高 9%（Ideal 高 16.2%）。STREAM 使用 5000 万 elements，Shared throughput 比 Ideal 低 37.3%、time 高 58.8%，RamRyder 各项距 Ideal 5% 内。67M-node/1.3B-edge graph 的 BFS/PR/CC/BC 中，Shared time 比 Ideal 高 41.4%，RamRyder 比 Shared 少 25.2% 且距 Ideal 5% 内（§6.2、图 13–14）。这些都是单台真实 server 的测量，不是 cluster result。
- **Cluster 数字是 trace pairing 外推**：作者在 Alibaba trace 中寻找“任一 timestamp 的 combined capacity 和 bandwidth 都不超过 100%”的 server pairs，再重新计算 consolidation 后的 utilization。图 15 得到 P30 server 的平均/最大 capacity utilization 分别提高 28.6%/22.1%，P90 server 的平均/最大 bandwidth utilization 分别提高 43.2%/26.1%。这一步没有在 fleet 上运行 RamRyder，也没有计入 placement churn、failure domain、network/CPU constraints 或 SLA headroom。随后只选择一对 trace，用 custom workload generator 在 VM3/4 回放 timestamped capacity/bandwidth requests：server 1 capacity 大于 70%、平均 bandwidth 10.1%，server 2 capacity 少于 20%、平均 bandwidth 38.4%。它验证 prototype 能跟踪一个合成的互补 profile，不是原 production applications 的 replay（§6.3、图 15–16）。
- **机制拆解、software overhead 与动态响应**：Redis ablation 证明 channel isolation 比 LLC isolation 贡献大，两者结合最好；DIMM bandwidth 随 channel 数近线性增加，CXL 也增加但 slope 较低（图 17–18）。Software interleaving 相对 hardware interleaving，在 128 threads 下平均/最高 overhead 为 3.6%/4.4%，single thread 为 5.1%/7.4%，最差点是 2 KB stride（图 19）。给 10 GB read workload 加一条 CXL channel 时，bandwidth 从 38 GB/s 经 2.2 秒升到 68 GB/s，约 40% pages 以 1.82 GB/s 被迁移；reclaim 用 1.1 秒，该次测试未见明显 latency spike（图 20）。图 21 同时显示 1 秒 monitoring 和 page redistribution 会漏掉短 burst，并落后于预先拥有全部 channels 的 Ideal（§6.4）。

## 论断—证据表

| 论断 | 机制与证据 | 评测边界 | 置信度 |
|---|---|---|---|
| Memory channel 可作为可分配的 bandwidth/isolation unit | DIMM bandwidth 随 channel 数近线性；图 17 中 channel isolation 比 LLC isolation 更有效（图 17–18） | 单台 Zen 5、8 条 DDR5 channels；read/write mix 和 CXL slope 不同 | 强（该平台） |
| RamRyder 能让 co-located VM 接近独占性能 | MLC、Redis/Memcached、STREAM、graph 多项结果距 Ideal 不超过 5%（图 12–14） | Ideal 无 co-tenant 且可用更多 channel parallelism；四个固定 VMs | 强（所测 workload） |
| Capacity 与 bandwidth 可以 mostly independently 分配 | CXL channel selection、weighted interleaving 与互补 VM pairing（图 8、图 16） | 依赖 channel granularity、已知 topology 和互补需求；local DIMM 仍按 capacity 比例 | 中到强 |
| Cluster consolidation 可显著提高两种利用率 | Trace pairing 计算出平均 capacity +28.6%、平均 bandwidth +43.2%（图 15） | 分析外推而非 live deployment；只检查 memory 两维和每时刻不超过 100% | 中 |
| Runtime 可以平滑增减 bandwidth | 10 GB workload 中 2.2 秒扩展、1.1 秒回收，未见明显 latency spike（图 20） | 单一 sequential-read microbenchmark；会错过短 burst，没有 tail distribution | 中 |

## 批判性分析

### 论证链条

论文先用 trace 证明 capacity、bandwidth 的闲置彼此不同步，再指出“按 capacity 买 bandwidth”和 delay throttle 都不适合，随后把 physical channel 提升为 software-visible allocation unit。C-NUMA/S-NUMA 让 guest 继续使用 NUMA primitives，CXL channel selection 再提供第二个 capacity/bandwidth 自由度。这条链条把 data-center 资源问题和 page placement 机制连接得很好，microbenchmark、application、ablation 也一致证明 channel contention 是主要性能来源。

最容易误读的是 cluster claim。28.6% 和 43.2% 不是部署 RamRyder 后量到的 fleet 指标，而是 trace 中找两两互补 servers、假设能无成本 co-locate 后的计算；实机只回放一个配对 profile。论文证明了 single-host mechanism 的可行性和 potential，不等同于证明 cloud scheduler 在真实 CPU、network、failure domain 与 SLA 约束下能实现同样利用率。

### 假设压力测试

Channel 是粗粒度且数量有限的资源。Testbed 一 socket 只有 12 条，本实验用了 8 条；小 VM 的需求若不到一条，只能继续 shared channel，并回到论文已经证明不精确的 throttle。VM 数远多于 channels、多个 bandwidth-heavy tenants 同时 burst，或 capacity-heavy tenant 也突然产生 bandwidth demand 时，互补 pairing 失效。

动态路径假设 demand 持续数秒。每秒一次 counters、连续阈值和 1–2 秒 redistribution 已足以错过短 burst。清 PTE present bit 让后续 access 触发 fault 的方案，还要面对 huge pages、pinned/DMA pages、unmovable kernel memory、writeback 和 memory-hot-unplug failure；论文没有说明这些情况如何回退。Immediate reclaim 也可能与 application 争用正在缩减的 channel bandwidth。

“CXL device 等于一条 channel”只对这批 Samsung CXL 2.0 devices 成立。未来 device 内多条不可控 DDR channels、CXL switch sharing、NUMA distance 不对称或不同 read/write bandwidth，会让静态 weighted ratio 失准。Performance counters 被 virtualized、multiplexed 或受 co-tenant 影响时，per-VM bandwidth estimate 也可能有误差。

### 实验可信度

论文给出的 hardware/VM 配置、四个明确 baselines、MLC 参数、YCSB dataset size 和 graph size 很完整；真实 DDR5/CXL 2.0 hardware 上的结果比 simulation 有力。Microbenchmark 展示 latency-bandwidth curve，applications 覆盖 latency-sensitive 与 bandwidth-intensive 两类，ablation 又把 LLC/channel isolation 分开，机制证据较扎实。图 19–21 还主动暴露了 single-thread overhead 和 burst lag。

外推范围仍限于单台 AMD server、四个固定大小 VMs、每个 VM 独立 CCX，以及四台每台单 DDR channel 的 CXL devices。没有多 socket、不同 CPU/CXL vendors、更多 tenants、mixed security domains 或持续数天的运行。Ideal 没有 co-location，且论文承认它在相同 bandwidth level 可使用更多 channels；因此“距 Ideal 5%”很有参考价值，却不是完全资源对等比较。

Cluster analysis 只做 pairwise memory-capacity/bandwidth feasibility，没有说明 trace 时间长度、pairing algorithm 的 operational churn，也没有真实 application/SLO performance。Custom generator 复现的是 utilization curve，不是 instruction/cache/page-access distribution；它无法证明同样 capacity/bandwidth 数字下的真实 workload tail latency。所有主要实验都没有 error bars 或 repeated-run variance。

### 系统性缺陷

部署面比“software-defined”这个名称更重：host 要关闭 hardware interleaving、把绝大部分 RAM 变成 DAX；QEMU 要支持 channel topology/RPC/hotplug；guest 要维护 cNode/sNode、page policy 和 fault-driven migration。VM live migration、snapshot/restore、host reboot、memory failure、overcommit 和 heterogeneous guest versions 都会碰到新的 topology state，论文没有给出兼容或 recovery protocol。

Physical isolation 也带来 fragmentation。Capacity chunks 是 128 MB，但 bandwidth allocation 以整条 channel/device 为单位；当 capacity 分散在很多低-bandwidth VMs 上，可能没有完整 channel 可安全转给高-bandwidth VM。Cross-VM sharing CXL channel 还需要 enforcement：若原本 low-bandwidth tenant 突然变重，系统只靠秒级 feedback，短时间内不能保证另一个 tenant 的 QoS。

清 PTE、fault 和 page migration 扩大了 guest kernel 的 correctness/security surface。论文没有评估 P99 page-fault latency、TLB shootdown、migration bandwidth accounting、NUMA policy interaction 或恶意 tenant 通过 demand oscillation 触发 thrashing。Multi-host CXL pool 只在 discussion 中提出，当前 RM、isolation 和 fault domain 都是 single-host 设计。

## 局限与后续工作

- 在多 vendor CPU、不同 DIMM population、multi-channel CXL device、CXL switch 和 multi-socket NUMA 上验证 channel mapping 与 bandwidth scaling。
- 加入 pinned/huge/DMA/unmovable pages、hot-unplug failure、VM crash/reboot、snapshot 和 live migration 测试，并给出 rollback protocol。
- 报告 page-fault/P99 latency、TLB shootdown、migration traffic、energy 和 demand oscillation 下的 thrashing，而不只看一个 10 GB sequential workload 的平均曲线。
- 用真实 applications 做长时间 trace-driven experiment，并把 CPU、network、failure domain、SLA headroom 与 placement churn 加入 cluster consolidation，区分 potential 与 realized utilization。
- 为小 VM 设计 sub-channel isolation，或明确 channel sharing 时的 bandwidth guarantee；评估 tenants 数大于 channels 数时的 fairness 和 fragmentation。
- 让 controller 预测 burst 或按 SLO 提前扩展，同时给 performance-counter error、sampling lag 和 reclaim contention 设置安全余量。

## 相关

- **相关概念**：[[CXL]]、[[Memory-Bandwidth]]、[[Memory-Pooling]]、[[Performance-Isolation]]、[[NUMA]]
- **同会议**：[[OSDI-2026]]
