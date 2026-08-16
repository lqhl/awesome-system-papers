---
type: concept
aliases: [EC, Erasure-Code]
last_updated: 2026-08-14
tags: [storage, reliability, distributed-systems, coding]
---

# Erasure Coding

> 纠删码（erasure coding）把 `k` 份数据编码成 `n-k` 份校验数据，在满足故障模型时用任意足够的幸存块恢复原数据，以编码、修复和实现复杂度换取比多副本更低的容量开销。

## 核心思想

一个 `(n,k)` code 的存储放大约为 `n/k`。Reed–Solomon（RS）具有 MDS 性质，但修复一个丢失块通常要从许多 helper 读取数据。LRC 增加局部校验来缩小常见修复范围；MSR/vector code 进一步降低修复流量，却可能需要很高的 sub-packetization、更复杂的系数和更稠密的编码计算。

“能恢复”只是正确性底线。系统还要决定 stripe 宽度、block 放置、foreground degraded read、background repair、并发故障、编码 CPU 和网络/磁盘调度。相同 code 放进 SSD、HDD、磁带和 LLM KV cache 后，瓶颈完全不同。

## 为什么重要

容量越大，复制成本越难接受。[[McQueen-FAST26]] 的生产对象存储用本地 LRC 和跨 region XOR 把 redundancy factor 从 2.40 降到 1.50；[[TapeOBS-FAST26]] 则在磁带归档里用 12+2 编码获得约 1.17 的冗余。这里的节省都伴随更复杂的恢复、调度和故障域假设。

现代工作逐渐把焦点从“编码率”移到“恢复路径”。[[DRBoost-FAST26]] 说明小对象 degraded read 不应被迫重建完整大 chunk；[[LESS-FAST26]] 说明最少 repair bytes 可能制造过多随机 seek；[[WiseCode-OSDI26]] 说明宽条带向量码只有在 sub-packetization、构造和编码速度都可控时才真正可部署。

## 关键观察 / 隐含假设

- **低存储开销会扩大修复 fan-in。** 宽条带让 `n/k` 更接近 1，却需要接触更多节点；[[WiseCode-OSDI26]] 的目标正是在约 100 个 data chunk 时控制 vector code 的子包化和计算成本。
- **理论最少流量不等于最低延迟。** [[LESS-FAST26]] 发现 Clay 类 MSR code 的非连续 I/O 会造成大量 seek；[[DRBoost-FAST26]] 则发现小对象只读一小部分时，全 chunk 恢复可把 degraded read 放大一到两个数量级。
- **维护读取可以跨任务复用。** [[DINGO-OSDI26]] 让 reconstruction、scrubbing 等任务声明数据集合和 deadline，再合并重复读；它优化的是调度，不改变 code 的可靠性。
- **故障场景决定最值得优化的路径。** [[WiseCode-OSDI26]] 优先单块故障，依据是其引用的生产数据中单 failure 占绝大多数；rack、firmware 或 region 级相关故障仍决定尾部风险。
- **编码也可以保护短生命周期状态。** [[GhostServe-MLSys26]] 为 TP-sharded KV cache 保存 parity，而不是完整 host copy；收益依赖 checkpoint I/O 是瓶颈，并且 8:2 配置不能直接推广到其他故障率和拓扑。
- **更少复制会增加读取距离。** [[McQueen-FAST26]] 的跨 region parity 降低容量，但 full-object GET 可能多约 50 ms；成本和 SLO 必须一起看。

## 设计空间与取舍

- **Replication、RS、LRC、MSR/vector code**：实现逐渐复杂，容量或修复流量逐渐降低；没有对所有介质都最好的 code。
- **窄 stripe 与宽 stripe**：窄 stripe 的 fan-in 和 placement 简单；宽 stripe 更省容量，却放大并发修复和相关故障管理。
- **完整块与 partial reconstruction**：partial read 适合小对象和 degraded GET，但需要更细的编码布局和缓存复用。
- **前台 degraded read 与后台 repair**：前者优先尾延迟，后者优先总吞吐；统一调度若只优化平均值，可能伤害用户请求。
- **单 region 与跨 region code**：跨地域更省副本，恢复延迟、带宽费用和故障协调更高。
- **静态 code 与 workload-aware policy**：动态选择更贴合对象大小和介质，却增加升级、兼容和运维复杂度。

## 引用本概念的论文

- [[WiseCode-OSDI26]] — 将宽条带 vector code 扩展到约 100 个 data chunk，并优化构造与编码。
- [[DINGO-OSDI26]] — 合并 reconstruction、scrubbing 等维护任务的重复读取。
- [[DRBoost-FAST26]] — 用 partial-chunk reconstruction 降低小对象 degraded-read 放大。
- [[LESS-FAST26]] — 在 repair I/O 数量和随机 seek 之间提供可调编码布局。
- [[McQueen-FAST26]] — 展示 EB 级对象存储中的本地 LRC 与跨 region parity。
- [[TapeOBS-FAST26]] — 在磁带约束下结合 batch erasure coding 与异步 HDD 缓冲。
- [[GhostServe-MLSys26]] — 用 parity checkpoint 保护 LLM serving 的分片 KV cache。
- [[DisCoGC-FAST26]] — 在编码对象存储中减少垃圾回收和写放大，说明维护路径与编码布局耦合。

## 已知局限 / 开放问题

- 可靠性模型需要纳入相关故障、repair queue、placement drift 和恢复期间的第二次故障。
- 应同时报告 normal read、degraded read、offline repair、CPU、seek、network 和存储成本。
- 新 code 进入 Ceph、HDFS 或既有对象存储时的数据迁移、rolling upgrade 和格式兼容成本常被忽略。
- code 参数与维护 deadline、对象大小、介质寿命和网络费用的联合优化仍缺少简单接口。
