---
type: paper
name: Blowfish
full_title: "Blowfish: Elastic Virtual Machine Memory for Disaggregated Memory"
authors: [Yulong Zhang, Yilong Luo, Diyu Zhou, Quan Chen, Quanxi Li, Mosong Zhou, Lei Zhu, Senbo Fu, Qian Peng, Huimin Cui, Xiaobing Feng, Tao Xie, Chenxi Wang]
venue: OSDI
year: 2026
tags: [virtualization, disaggregated-memory, memory-overcommit, huge-pages, far-memory]
source_pdf: "[[osdi26-zhang-yulong.pdf]]"
source_md: "[[osdi26-zhang-yulong]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# 面向分离式内存的弹性虚拟机内存

> **原题**：Blowfish: Elastic Virtual Machine Memory for Disaggregated Memory

> **一句话总结**：Blowfish 让 guest 负责理解自己的内存热度，让 host 负责快速搬页：它在保留 [[Transparent-Huge-Pages|透明大页]] 的同时找出 2 MB 页里的冷 4 KB 子页，并只修改 EPT 完成远端回收；在七种 workload 上，相同 5% 性能损失下比三种 HyperAlloc 路径多回收 1.6×–6.1× 内存，但代价是修改 guest 与 host 内核，并依赖合作 guest 和低延迟远端内存。

## 问题与动机

[[Disaggregated-Memory|分离式内存]]（disaggregated memory）把远端内存作为本机内存的弹性后备。论文引用的 100 Gbps InfiniBand 路径搬一个 4 KB 页少于 5 μs，比磁盘快 200 倍以上；Blowfish 的评测平台也使用 100 Gbps InfiniBand，但没有单独复测这个纯网络数字。网络变快以后，主要成本不再是传输，而是虚拟机换页的软件路径：guest swapping 要依次改 guest page table（GPT）、extended page table（EPT）和 I/O page table（IOPT），测得软件处理时间是网络传输的 3.4–6.8 倍（§3.2）。

Host 直接换页看似能绕开 guest，但它不知道 guest 的内存语义。它通常通过清除 EPT accessed bit 追踪热度，这比 guest 自己读 GPT accessed bit 多触发约 5× TLB flush。[[Transparent-Huge-Pages|THP]] 又放大这个问题：只要 2 MB 页中的一个 4 KB 子页被访问，整个大页就会被当成热页；如果关闭 THP，七个 workload 在性能下降少于 5% 时可回收 33%–49% 的内存，开启 THP 后只剩 16%–25%（§3.1，图 2）。

论文因此把问题定义为：既要保留 THP 的地址转换收益，又要以 4 KB 粒度找冷页；既要使用 guest 的准确热度信息，又要避免 guest swapping 的多层页表修改。

## 关键观察 / 隐含假设

- **观察 1：THP 的热度统计在粒度上不公平。** 普通 4 KB 页每轮只有一次被访问的机会，2 MB 页却有 512 个子页，任一命中就能把整个大页提升到最热 generation。Blowfish 的 Fair MGLRU 让 4 KB 页直接进入最年轻 generation，而 2 MB 页每次只前进一代，以抵消这种概率偏差（§4.3.1）。
- **观察 2：不必拆掉物理大页也能观察子页。** Subpage tracker 只临时拆分 page-table mapping，不拆物理页；它对第二年轻 generation 中最多 32 个 THP 观察 100 ms。少于 20% 的子页被访问时，系统把其中冷子页交给 host；多于 80% 时则认为大页内部较均匀，下一轮不再采样（§4.3.2）。
- **观察 3：语义和执行可以分层。** Guest 最了解页面用途和访问历史，host 却拥有 EPT、物理页和 [[RDMA|RDMA]] 通道。共享通道只传递“哪些 GPA 可以回收”，真正的 EPT 失效、远端写入和恢复都在 host 完成，因此 GPT 不变，远端 NIC 也不必经过 guest IOPT（§4.2、§4.4，图 4–5）。
- **假设 1：guest 愿意合作，而且报告足够及时。** 错误 GPA 会被 host 丢弃，guest 不响应时可退回普通 host swapping，但这条退路失去低开销热度跟踪；恶意 guest 还可能通过少报冷页来逃避回收（§4.7）。
- **假设 2：多代 LRU 和固定采样窗口能代表真实热度。** Fair MGLRU 要求至少三个 generation，Linux 默认是四个；100 ms、32 个 THP、20%/80% 等阈值可能漏掉短时突发，论文没有系统搜索这些参数。
- **假设 3：远端页访问仍接近微秒级。** 自动策略根据 pressure stall information（PSI）控制回收并在压力上升时提前恢复；若共享网络拥塞、远端服务器失效或尾延迟突然升高，同一个控制器未必还能守住 5% 性能预算。

## 核心方法

**Guest 侧热度跟踪。** Blowfish 修改 [[MGLRU]] 的 promotion 规则形成 Fair MGLRU，再用 Subpage tracker 检查候选 THP 内部的 4 KB accessed bit。它只拆 mapping，观察完成后重新合并，因此仍可保留物理连续性。Guest 把冷页 GPA 经共享内存队列交给 host，空闲页则由 host 扫描共享的 guest allocator；冷页选择用已有 LRU 锁同步，队列索引和 allocator 状态用原子更新（§4.3–§4.5、§4.7）。

**Host 侧回收与恢复。** Host 收到 GPA 后，锁住对应 EPT entry、让映射失效并做必要的 TLB flush，把 4 KB 内容经 RDMA 写到远端，再把远端地址编码到 non-present EPT entry 的高位。下一次访问产生 EPT violation，host 分配本地页、从远端读回并恢复映射。页面始终保留同一 GPA，所以不需要走 guest swap，也不修改 GPT；RDMA 由 host 发起，所以该路径也不需要改 guest IOPT（§4.4）。

**对内核服务保留“热页”。** Guest 的 `khugepaged` 若发现候选区域超过一半页面最近未访问，就不把它合成 THP；`kcompactd` 优先避开最年轻和已经回收的页。这样后台合页和压缩不会立刻把 Blowfish 刚做出的冷热分离重新打乱，但 direct compaction 仍可在内存紧急时越过这些限制（§4.5）。

**自动控制。** 系统先回收 free page，直到 guest 只保留 100 MB 空闲水位，再每 100 ms 根据 PSI 选择冷页。压力升高时主动 restore，压力降低时继续 reclaim。论文强调策略可替换；实现中的阈值和扫描周期是启发式控制，而不是有稳定性证明的 SLO controller（§4.6）。

## 设计取舍

- **跨层合作换取短路径。** Guest 修改约 1,700 行、host 修改约 6,000 行 Linux 代码，得到比 guest swapping 更少的页表修改；代价是不能透明支持完全未修改或不合作的 VM。
- **保留 THP 换取采样复杂度。** 临时拆 mapping 避免永久关闭 THP，却需要周期性选样、TLB 操作和冷热阈值；实验测到该 tracker 自身会给 Cassandra 和 TriangleCount 带来 3.1% 与 0.9% 开销（§5.3，图 9）。
- **Host RDMA 换取更简单的 I/O 地址路径。** 把远端内存 NIC 放在 host 侧省去 IOPT 更新，但论文没有证明任意 guest passthrough device、DMA pinning 或设备直通场景都能保持相同语义。
- **PSI 驱动换取通用接口。** PSI 不需要理解每个应用，却只是任务因内存压力而停顿的间接信号；相同阈值未必对应不同租户的 throughput 或 tail-latency SLO。
- **页内粒度换取元数据和锁。** 4 KB 回收提高容量弹性，但每页 EPT 状态、远端地址和锁会增加管理开销；论文只展示到四个 reclaim/restore thread，没有给大 VM fleet 的元数据规模。

## 实验与结果

- **平台、基线与 workload**：一台计算服务器和一台内存服务器各配 2 颗 Xeon Gold 6342、256 GB 内存，通过 100 Gbps ConnectX-5 InfiniBand 连接；Ubuntu 20.04、Linux 6.1、QEMU 8.2.1，关闭 turbo、frequency scaling 和超线程，开启 THP。七个 workload 覆盖 Memcached/Cachelib、Cassandra/YCSB、GAPBS TriangleCount、GraphChi PageRank、Liblinear、Spark KMeans 和 SPEC CPU `602.gcc_s`，内存规模约 8–36 GB。对比 HyperAlloc 的 guest、4 KB guest 和 host 三条路径；作者为它们接入同一 Hermit 远端后端和控制策略（§5，表 2）。
- **相同性能预算下回收更多内存**：在吞吐下降不超过 5% 时，Blowfish 相对 HyperAlloc-4K-G、HyperAlloc-H、HyperAlloc-G 的回收率提升范围为 1.6×–6.1×。例如 GraphChi 分别为 3.4×、6.1×、3.9×，Memcached 为 3.1×、5.3×、3.2×；七项中每个对比都获益，但倍数随 workload 和基线差异很大（§5.1.1，图 6）。
- **Tail latency 与 CPU 开销**：在吞吐下降 5% 的配置下，Memcached 的 P95 latency 增幅相对三种基线缩小 2.8×、4.7×、3.9×，Cassandra 为 1.9×、2.5×、2.1×。Blowfish 的额外 CPU 分别约为 11% 和 14%，HyperAlloc-4K-G 为 24% 和 26%（§5.1.2，图 7）。
- **多 VM 与组件效果**：六组双 VM 共跑实验中，Blowfish 在 PSI 阈值 0.04 下的归一化性能下降为 1.06–1.25；Fair MGLRU 让 Memcached 和 KMeans 的可回收率再提高 7.2% 和 6.5%。这说明公平 promotion 和子页识别都有效，但多租户证据只有两台 VM，并非数据中心规模（§5.2–§5.3，图 8–10）。
- **单页路径与扩展性**：回收和恢复一个 4 KB 页分别用 14.5 μs、9.8 μs，比 HyperAlloc-4K-G 低 53% 和 60%；论文摘要报告最高 2.48×、2.14× 加速。单 thread 达约 170 K pages/s，2/4 thread 的能力为 2.0×/3.9×，说明当前范围内锁竞争较小（§5.3，图 11）。

## 论断—证据表

| 论断 | 直接证据 | 评测边界 | 置信度 |
|---|---|---|---|
| THP 会遮住大量可回收的冷 4 KB 子页 | 开启 THP 时 5% 性能预算内只可回收 16%–25%，关闭时为 33%–49%（图 2） | 七个 workload、单一 Linux/THP 配置 | 强 |
| Guest 跟踪、host 搬页能明显缩短单页路径 | 4 KB reclaim/restore 为 14.5/9.8 μs，较 HyperAlloc-4K-G 低 53%/60%（图 11） | 单计算节点、单远端内存节点、100 Gbps IB | 强 |
| Blowfish 在相同性能损失下回收更多内存 | 七项 workload、三种基线的提升范围为 1.6×–6.1×（图 6） | 基线远端后端与策略由作者统一扩展；不是原系统直接复现值 | 强 |
| Fair MGLRU 和 Subpage tracker 都有独立价值 | Fair MGLRU 增加 6.5%–7.2% 回收率；tracker 开销为 0.9%–3.1%（图 9） | 组件实验各只选少量 workload，未扫全部参数 | 中强 |
| 机制可直接扩展到大规模多租户 VM fleet | 仅有六组双 VM 和最多四 thread 的实验 | 未测 NIC 竞争、远端故障、租户隔离或数百 VM 控制稳定性 | 弱 |

## 批判性分析

### 论证链条

论文先把远端传输与软件换页拆开，证明软件已经更贵；再分别说明 guest 路径多改页表、host 路径热度不准；最后用“guest 给语义、host 做搬页”同时解决两者。单页延迟、端到端回收率和两项组件实验能闭合这条链。最容易被误读的是 1.6×–6.1×：它表示在相同 5% 性能预算下相对某条 HyperAlloc 路径的回收率倍数，不是应用吞吐加速，也不是机器内存直接减少同样倍数。

### 假设压力测试

首要测试应同时制造 guest 不合作、突发热点和远端 NIC 拥塞：比较 shared channel 延迟、100 ms tracker 漏判、PSI controller 是否振荡，以及 fallback host swapping 能否守住 tail SLO。还应把 2 MB 页内访问从均匀、单热点、周期热点逐步改变，检查 20%/80% 阈值和“2 MB 每次只升一代”是否误伤真正的热大页。对恶意租户则要限制少报冷页和伪造压力带来的容量不公平。

### 实验可信度

论文列出硬件、软件、线程绑定、七个 workload、三条基线和明确的 5% 口径，并同时报告 throughput、P95、CPU、组件延迟与共跑结果，主结论可信。局限是所有机器来自同一双服务器环境，baseline 由作者接入 Hermit，且没有方差或长时间稳定性数据。双 VM 实验不足以支持多租户公平，四 thread 扩展性也不能代表整机数百 VM 的 EPT 锁和 RDMA queue 压力。

### 系统性缺陷

Blowfish 的主要缺陷不是一个慢函数，而是信任和控制边界：host 要依赖 guest 报告，但负责资源超售的恰恰是 host；不合作 guest 可以迫使系统回退到更贵路径。系统还把远端地址写进 non-present EPT entry，并假设远端页可靠可取回，却没有讨论内存服务器故障、数据加密、重复制或迁移。最后，PSI 只给出全局压力代理，未提供 per-tenant 容量配额、tail-latency SLO 或远端带宽公平，因此离生产级 memory marketplace 仍有明显距离。

## 局限与后续工作

- 在多计算节点共享远端内存的环境中加入带宽竞争、拥塞、远端故障和恢复实验，并报告数据保护成本。
- 支持或明确限制 device passthrough、pinned DMA、live migration 与 confidential VM；验证 EPT-only 状态在这些路径上的正确性。
- 把 PSI 启发式升级为 per-VM SLO controller，报告稳定性、误判率、容量公平和恢复流量峰值。
- 在不合作或恶意 guest 上评估 fallback，并设计 host 可验证的回收贡献与配额机制。
- 扩大到数百 VM 和多 memory server，量化 EPT 元数据、锁、RDMA queue、shared channel 与 background scanner 的扩展瓶颈。

## 相关

- **相关概念**：[[Disaggregated-Memory]]、[[Memory-Overcommitment]]、[[Transparent-Huge-Pages]]、[[Far-Memory]]、[[MGLRU]]
- **相关系统**：[[HyperAlloc]]、Hermit
- **同会议**：[[OSDI-2026]]
