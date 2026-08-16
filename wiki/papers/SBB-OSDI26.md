---
type: paper
name: SBB
full_title: "SBB: Eliminating Centralized Bottlenecks in Userspace Network Runtime"
authors: [Kang Hu, Shuqi Dong, Chuandong Li, Ran Yi, Zonghao Zhang, Yiming Yao, Bo An, Jie Zhang, Xiaolin Wang, Yingwei Luo, Zhenlin Wang, Diyu Zhou]
venue: OSDI
year: 2026
tags: [networking, userspace-networking, scheduling, user-interrupt, multicore]
source_pdf: "[[osdi26-hu-kang.pdf]]"
source_md: "[[osdi26-hu-kang]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# 消除用户态网络运行时的中心瓶颈（OSDI 2026）

> **原题**：SBB: Eliminating Centralized Bottlenecks in Userspace Network Runtime

> **一句话总结**：微秒级网络运行时的 central timer、queue monitor 和 packet dispatcher 会分别卡住抢占、CPU 分配和负载均衡；SBB 用每核 timer/NIC User Interrupt 加上“短期 task stealing、长期 flow migration”的两级策略去掉这些中心线程，在最多 48 个 worker 的相同 tail-latency SLO 下，论文汇总吞吐比对应先前系统高 1.7–5.2 倍，但它依赖 Sapphire Rapids UINTR、定制 Linux 和简化 transport stack，48 核后也已出现跨核同步瓶颈。

## 问题与动机

内核旁路的用户态网络运行时要同时做好三件事。请求抢占（request preemption）避免长请求堵住短请求；CPU 分配（CPU allocation）让低负载 latency-critical（LC）服务把核借给 best-effort（BE）任务，又能在新包到来时快速抢回；请求负载均衡（request load balancing）则避免某个 worker 排队而另一个空闲。只解决其中一项，系统仍难同时得到高吞吐、低尾延迟和高 CPU 利用率。

Shinjuku、Caladan 等系统通常为这三件事分别放一个 central timer、monitor/iokernel 或 dispatcher。论文的预实验表明，它们不是小常数开销，而是 serial bottleneck：Shinjuku 的 timer 在超过 16 个 worker 后无法在 5 μs quantum 内及时发完 IPI；Caladan iokernel 遇到 1 ms on/off burst 时来不及逐核回收 CPU；dispatcher 每包约 200 ns，把总吞吐封在约 5 MRPS（图 3）。

简单增加中心线程也没有解决问题。多个 dispatcher 把一个全局不均衡拆成多个 group 内和 group 间不均衡；多个 core 同时发 User IPI 的总速率仍受一个 NUMA domain 限制（图 3d–e）。SBB 因而把目标定为“每个 worker 自己收包、计时和调度”，不再让任何一个专用控制 core 随 worker 数量增长。

## 关键观察 / 隐含假设

- **观察 1：中心化抢占不是算法必需，而是过去缺少每核、低成本的用户态 timer。** Sapphire Rapids 的 User Interrupt（UINTR）可让 LAPIC timer 直接进入当前用户线程，每个 worker 因此能自我抢占（§3.2、§4.3）。
  - **依赖假设**：CPU 支持 UINTR，OS 允许映射和配置 APIC/UPID，timer interrupt 的 688-cycle 路径不会吞掉微秒任务的大部分预算。
  - **可能失效场景**：旧 CPU、未暴露 UINTR 的 VM、严格禁止用户态映射中断状态的环境，或 quantum 已接近 interrupt 成本。
- **观察 2：polling 与 CPU 共享存在根本冲突。** LC 线程一旦让出 core，就不能继续 poll NIC，也就不知道何时该回来；过去只能由 central monitor 代看。NIC UINTR 让 arrival 主动通知 owning core（§3.2、§4.2）。
  - **依赖假设**：NIC 支持 per-queue interrupt、automask 和可路由 vector；低负载节省的 CPU 大于 interrupt 额外延迟。
  - **可能失效场景**：超高 packet rate 引发 interrupt 压力、NIC 不支持所需 re-arm，或 SLO 接近纯 polling 的极限延迟。
- **观察 3：task stealing 只能修短期 burst，不能修 RSS 造成的长期 flow 偏斜。** 模拟在 95% load 下发现，被反复 steal 的 packet 大多来自少数 flow；cache coherence 与 multi-stealing 使纯 stealing 明显落后 JBSQ(2)（图 4）。
  - **依赖假设**：三轮 queue 水位足以区分 temporary 与 persistent imbalance，NIC flow director 能在约 10 μs 内稳定改写 5-tuple steering。
  - **可能失效场景**：大量 one-packet flow、单个 elephant 无法拆分、flow rule table 不够，或迁移时的包重排影响 transport state。
- **观察 4：合适的去中心化策略可以接近中心 shared-queue 的调度质量。** hybrid simulation 接近 JBSQ(2)，说明“中心化一定更均衡”不是普遍规律（图 4）。
  - **依赖假设**：模拟的 200 ns steal 成本、flow 分布和真实机器上的 cache/NUMA 代价足够接近。
- **假设 1：应用可以改写到 SBB 的 callback 接口和轻量 TCP/UDP stack。**
  - **证据强度**：中。[[RocksDB|RocksDB]] 与 Memcached 可以移植，但 stack 没有 congestion control，生产 transport 的完整兼容性未证明。

## 核心方法

**1. 每个 worker 拥有自己的数据和控制路径。** 一个 worker 绑定一个 CPU core，并有自己的 Rx/Tx queue、local request queue 和 LAPIC timer。RSS 先把 flow 分到 Rx queue；worker 收包、执行协议栈和应用、发回响应。没有专用 dispatcher、timer 或 monitor core（图 5）。不过 load stealing 仍会访问其他 worker 的 queue，所谓“无共享”更准确地说是“无中心 owner”，不是完全没有跨核同步。

**2. NIC UINTR 负责及时回收 CPU。** 若 LC 线程正在运行，NIC queue 的 vector 与 `UINV` 匹配，CPU 直接进入用户态 handler；handler 只置 pending flag，真正 dequeue、parse 和执行留给 worker bottom half。SBB 借用 Aeolia 的办法，把 UPID 映射到用户地址空间，在每次处理后重新设置 PIR。若 LC 当前没有运行，vector 不匹配，interrupt 仍会走定制 kernel handler，由它唤醒 LC 并触发 scheduler（§4.2）。因此睡眠路径仍经过内核，但不依赖一个中心 monitor。

**3. Timer UINTR 让 worker 自我抢占。** 处理每个 LC request 前，worker 写 APIC 寄存器启动 one-shot timer，写入约需 50 cycles；request 在 quantum 内结束就重置 timer，超时则直接进入用户 handler，保存 execution context，把长请求放回 local queue，再执行下一个请求（§4.3）。

**4. 两种 UINTR 按阶段复用同一 handler。** 当前硬件每核只有一组 `UIHANDLER/UINV`，不能直接区分 NIC 与 timer 来源。SBB 利用 NIC automask，把处理拆成 top half 和 bottom half：NIC UINTR 只在等待新 batch 时开启，timer UINTR 只在 application stage 开启，两者不同时有效。这样既辨别来源，也避免每个 packet 都产生 interrupt storm（图 6）。

**5. 两级负载均衡修两种时间尺度。** 每个 victim 按连续三轮水位在 Light、Busy、Overloaded 间切换。stealer 遇到 Busy worker 时拿走其一半 pending request；遇到 Overloaded 时读取它发布的 flow ID，并安装 NIC flow-director rule，把整个 flow 移到自己。前者处理短 burst，后者停止同一 flow 的长期反复偷取（§4.5.1）。

**6. 细化 task stealing 的共享开销。** local queue 前 16 项为 owner-exclusive；stealer 拿到 request 后直接执行，避免再次入队和 multi-stealing；owner 按 16 个一批 dequeue，stealer 一次拿一半；锁使用 try-lock；victim scan 从上次成功对象开始并错开各 worker 的起点。这些措施减少低负载下的锁和 cache-line 迁移（§4.5.2）。

原型在 Linux 6.12.20 上增加 2,095 LOC kernel patch，在 DPDK 25.07 上实现 4,343 LOC runtime，并另有 2,067 LOC client generator。应用必须实现三个 hook；自带 TCP/UDP stack 为了公平复用先前系统的做法，但缺少 congestion control（图 7、表 2、§5）。

## 设计取舍

- **去中心化换硬件和内核依赖。** SBB 释放专用 core，并移除单点吞吐上限，却要求 Sapphire Rapids UINTR、特定 NIC 能力、UPID/APIC 映射和定制 kernel。
- **CPU efficiency 换最低延迟。** E810 上 NIC UINTR 比持续 polling 多 0.49 μs，但允许 core 在空闲期做 BE 工作；对极短 RPC 或极严 SLO，这个常数仍可能不可接受。
- **local queue 换跨核协调。** worker 常态路径局部化，stealing、flow state 和 NIC rule update 仍会产生 coherence、锁和全局资源竞争；论文已在 48 workers 看到 sublinear scaling。
- **flow locality 换迁移复杂度。** 整 flow 迁移可消除长期偏斜，但要处理 rule 容量、更新延迟、包重排、connection state 和回滚。
- **阶段复用换状态机脆弱性。** 两种 UINTR 不同时开启才可区分来源；unexpected pending interrupt、handler bug 或 stage 边界错误可能造成漏通知或错误抢占。
- **适用边界。** 单机、短 RPC、硬件 RSS 偏斜、LC/BE 共置且 UINTR 可用时最合适；跨 NUMA、完整云虚拟化、复杂 transport 和大量短 flow 仍缺证据。

## 实验设置

- testbed 是两台直连机器。server 有两个 NUMA node，每个 node 一颗 64-core Xeon Platinum 8592 1.9 GHz；client 是 144-core Xeon 6780E。论文最多使用 48 个 worker，但没有明确给出这些 worker 的跨 NUMA placement（§6.1）。
- SBB 用 100 Gbps Intel E810；Caladan 在 E810 上退化，因此按其建议改用 ConnectX-5。不同系统还运行不同 Ubuntu/kernel。这是在给各 baseline 合适环境，但 NIC/link latency 与软件栈并非完全相同。
- workload 包括固定 1 μs、High/Extreme Bimodal synthetic、内存内且关闭 logging 的 RocksDB、Memcached LC 与 swaptions BE。除扩展实验外通常为 16 threads（表 3、§6.1–6.3）。
- baseline 按能力分组：抢占比较 Shinjuku、Concord、TQ；CPU 分配比较 Skyloft、Caladan、Caladan-DL。没有一个对手同时实现三种 scheduling，因此不存在统一、功能完全相同的端到端 baseline。

## 实验与结果

- **48-worker 总体扩展**：论文在相同 tail-latency target 下汇总 SBB 相对对应先前系统的吞吐收益为 1.7–5.2 倍（摘要、§8）。Fixed(1) 在 16/32/48 workers 下约为 9.5/19/26.5 MRPS，即 48 对 16 为 2.8 倍；Shinjuku、Concord、TQ 从 16 加到 32 几乎不再增长（图 11a、§6.4）。
- **16-worker 单应用**：Fixed(1) 在 p99.9 slowdown 50 倍 SLO 下达到 9.7 MRPS，比 TQ、Concord、Shinjuku 都高 90% 以上；High Bimodal 达 260 KRPS、比基线高 30% 以上，Extreme Bimodal 高 40% 以上；RocksDB light/heavy-tail 在相同 SLO 下高 20%–80%（图 8、§6.2）。
- **LC/BE 共置**：16 cores 上把 Memcached 与 swaptions 共置，p99.9 少于 100 μs 时，SBB 的 LC throughput 分别比 Caladan 和 Caladan-DL 高 28% 与 15%，BE 获得的 CPU efficiency 接近 Caladan-DL，同时尾延迟更低；Skyloft 仍受约 5 MRPS dispatcher 上限（图 9、§6.3）。
- **抢占与 CPU 分配扩展**：High/Extreme Bimodal 从 16 到 32 workers 分别由 260 到 520 KRPS、3.4 到 6.8 MRPS，48 workers 又比 32 高 35% 以上。Memcached+swaptions 在 p99.9 50 μs SLO 下，SBB 从约 8 扩到 16 MRPS，而 Caladan 从 6 扩到 10.2 MRPS 并在 32 workers 附近见顶（图 11b–d、§6.4）。
- **中断成本**：1 μs microbenchmark、E810 上，UINTR 相对 polling 增加 0.49 μs，占 10.81 μs 往返的 4.7%；传统 interrupt 的 notification 为 3.4 μs，UINTR 为 0.45 μs。ConnectX-5 的 UINTR 额外占比为 8.1%（图 12、§6.5）。timer UINTR 为 688 cycles，对比 User IPI 1,381、custom IPI 1,878、signal timer 7,697 cycles（表 4）。
- **负载均衡消融**：Fixed(1) 中，增强 task stealing 相对基础 stealing 把 SLO throughput 提高 30%；再加入 flow migration 后曲线继续右移并达到完整 SBB 的约 9.7 MRPS，而只用 RSS、基础 stealing 都更早触碰 p99.9 slowdown 50 倍界线（图 13、§6.5）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 去掉 central dispatcher 后，低 dispersion RPC 可随 worker 扩展 | 图 11a：16/32/48 workers 为 9.5/19/26.5 MRPS | 单机、Fixed(1)、p99.9 slowdown 50 倍、最多 48 workers | 强 |
| per-core timer UINTR 支持可扩展微秒抢占 | 图 11b–c、表 4：32 workers 近线性，688 cycles | 两个 synthetic bimodal workload、Sapphire Rapids | 强 |
| NIC UINTR 能以较小成本支持 LC/BE CPU sharing | 图 9、12：LC 吞吐高 15%–28%，E810 多 0.49 μs | Memcached+swaptions、两种 NIC、16 cores | 中到强 |
| flow migration 与 task stealing 互补 | 图 4、13：hybrid 接近 JBSQ(2)，enhanced stealing 先提高 30%，migration 再改善 | simulation 与 Fixed(1)/RSS flow 分布 | 中到强 |
| SBB 可在通用 datacenter/VM 中直接部署 | §5/§7 的实现与讨论 | 需要 kernel patch、UINTR、应用改写和简化 stack；未做 VM 实验 | 弱 |

## 批判性分析

### 论证链条

论文先把 timer、monitor、dispatcher 三个中心瓶颈分别测出来，再给出相应的 per-core timer UINTR、NIC UINTR 和 hybrid balancing，设计与证据一一对应。最有价值的发现是纯 stealing 失败来自长期 flow 偏斜，而不是“去中心化天然差”；模拟和图 13 都支持两级策略。需要收窄的是“纯 decentralized、无 shared component”：stealer 仍读写 victim queue，flow migration 仍共享 NIC rule table，只是这些资源没有单一中心线程。

### 假设压力测试

UINTR 的可用性高度依赖 CPU、虚拟化和安全策略；论文声称 commodity VM 也适合，却没有验证 hypervisor 是否暴露 device UINTR 和 APIC/UPID mapping。大量 one-packet flow 会让 flow migration 来不及生效，单个 elephant 又不能靠整 flow 迁移分摊。跨 NUMA 时 victim scan、queue lock 和 cache-line transfer 更贵，而论文没有说明 48-worker placement。两种 interrupt 必须按阶段互斥，也值得用并发 arrival/timer race 做压力测试。

### 实验可信度

synthetic 分布、RocksDB、Memcached/BE 共置、三种 scheduling 的扩展实验和机制消融覆盖很广，tail SLO 而非平均 latency 也符合目标。公平性仍有限：没有单一 baseline 覆盖全部功能；系统运行不同 kernel，Caladan 使用不同 NIC；RocksDB 全内存且关闭 logging；transport stack 缺 congestion control。headline 的 1.7–5.2 倍来自不同 workload/对手的汇总，不是同一配置下对一个系统的固定倍数。

### 系统性缺陷

2,095 LOC kernel patch、应用 callback 改写和自有 stack 增加部署与维护成本。论文没有评测 worker crash、丢失 NIC/timer interrupt、NIC reset、flow-rule installation failure、包重排、rule-table exhaustion、优先级反转或租户隔离。去中心化还让全局 debug 更难：短期 tail spike 可能来自 interrupt、steal、migration 或错误状态转换，但文中没有统一 trace/observability 设计。

## 局限与后续工作

- **局限 1**：只测支持 UINTR 的 Intel 平台与两款 NIC，未验证 AMD/ARM、VM、SmartNIC 或普通云实例。
- **局限 2**：最多 48 workers，已经出现 sublinear scaling；跨 NUMA placement 与 64–192 core 行为没有报告。
- **局限 3**：轻量 TCP/UDP stack 没有 congestion control，RocksDB 又关闭 logging，生产协议和存储路径被简化。
- **局限 4**：不同 baseline 使用不同 kernel/NIC，且没有一个功能等价的三类 scheduling 统一对照。
- **后续工作 1**：在 64–192 cores、单/双/四 NUMA 下报告 P50/P99.9、MRPS、steal 次数、flow-rule update、LLC miss 和 UPI traffic，找出 48 核后的主导成本。
- **后续工作 2**：在 KVM 或公有云 VM 中验证 device UINTR delivery、interrupt remapping、权限隔离和 noisy-neighbor 下的 tail SLO。
- **后续工作 3**：加入完整 TCP congestion control 与 QUIC，迁移 flow 时逐包检查 ordering、retransmission、connection state 和 rule rollback。
- **后续工作 4**：注入 lost interrupt、simultaneous NIC/timer event、worker crash、NIC reset 和 rule-table exhaustion，测 dropped request、错误抢占、恢复时间与 SLO violation。

## 相关

- **相关概念**：[[Kernel-Bypass-Networking]]、[[User-Interrupt]]、[[Work-Stealing]]、[[Flow-Migration]]、[[NUMA]]
- **同类系统**：[[Shinjuku]]、[[Caladan]]、[[Concord]]、[[DPDK]]
- **同会议**：[[OSDI-2026]]
