---
type: paper
name: Sepia
full_title: "When DDIO Meets Page Coloring: Revisiting DDIO Performance with Sepia"
authors: [Changwoo Song, Sanghyun Kim, Jinhyeok Oh, Qizhe Cai, Joonsung Kim, Jaehyun Hwang]
venue: OSDI
year: 2026
tags: [networking, ddio, page-coloring, last-level-cache, linux]
source_pdf: "[[osdi26-song.pdf]]"
source_md: "[[osdi26-song]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# 用页面着色改善 DDIO 缓存效率（OSDI 2026）

> **原题**：When DDIO Meets Page Coloring: Revisiting DDIO Performance with Sepia

> **一句话总结**：Sepia 纠正了“DDIO leaky DMA 只因预留 LLC way 太少”的解释：Linux 为 Rx ring/page pool 分配的物理页在 LLC slice/set 上不均，即使 38 MB working set 小于 39 MB LLC，超过 12-way associativity 的 slice/set 组合占比也会达到 39.3%；它用 Stride-1 page coloring 把实用 effective LLC 从 18 MB 提到 32 MB，再配合缩小 Rx ring 和 TCP buffer，使 Linux 6.6 在 200 Gb/s TCP microbenchmark 中以 3.5 而非 6 个 core 饱和链路、LLC miss 约 0.4%，但单独 coloring 平均只提高 8.62%，论文所称 94.4% capacity 增益来自不可直接部署的 Tetris upper bound，且主要实测平台仍是单 socket 的 Intel Ice Lake/ConnectX-6 Rx path。

## 问题与动机

Intel Data Direct I/O（DDIO）让 NIC 收到的数据先写入最后一级缓存（Last-Level Cache，LLC），CPU 做协议栈和 copy-to-user 时就不必从 DRAM 冷读。默认只有两个 LLC way 接受 DDIO write miss，因此已有解释把 leaky DMA 归因于“incoming bytes 超过 DDIO-reserved capacity”。在论文的 39 MB LLC 上，这部分约为 6.5 MB；1 到 6 条 TCP flow 时，Linux throughput-per-core 下降约 46%，LLC miss 升到 60.4%（图 3、§3）。

论文发现这个解释少了一层。若某条 cache line 已被 CPU read 带回 LLC，后续 DDIO write hit 可以原地更新它，不受两个 reserved way 限制；在低负载 write-hit regime，真正的容量是整个 LLC。反过来，即使作者把 in-flight traffic 限在 6.5 MB 内，多 flow miss rate 仍可到 46.4%；单 flow 把 working set 从 22 MB 增到约 38 MB、仍小于 39 MB LLC 时，miss 也从 0.9% 升到 16.5%（图 3–4、§3.2）。

原因是 Linux buddy allocator 不看物理地址到 LLC slice/set 的映射。38 MB 页在部分 set/slice 上超过 12-way associativity，而其他位置空着；trace 的 violation ratio 从 22 MB 时 1.97% 墠到 38 MB 时 39.3%（图 5、§3.3）。Sepia 的目标不是再加 way，而是让 NIC DMA page 在 set 和 slice 上分布均匀，并在实际 page recycle 不按原顺序返回时仍维持这种分布。

## 关键观察 / 隐含假设

- **观察 1：DDIO write hit 可使用 LLC 的所有 way。** 单 flow 的约 22 MB working set 远大于 6.5 MB reserved capacity，miss 仍只有 0.9%；把 CPU 可用 LLC way 从 12 限到 2 后 miss 才明显上升（图 3–4、§3.2）。
  - **依赖假设**：CPU 会在下一次 DMA 前读这些 page，把 line 保留或重新装入 LLC；这适合会处理/copy payload 的 Rx workload。
  - **可能失效场景**：write-only DMA、CPU 很晚才读、zero-copy consumer 不访问大部分 payload，或 working set 已超过全 LLC。
- **观察 2：capacity 合规不代表不会 conflict。** 38 MB 小于 39 MB，却因 slice/set 映射倾斜产生 39.3% violation；单纯扩大 DDIO way 或 throttle incoming bytes 都不能消除这种冲突（图 3–5）。
  - **依赖假设**：静态 physical-address mapping 能预测真实冲突。作者明确承认 violation 是 high miss 的必要而非充分条件，因为 trace 没有精确 CPU read 时序。
- **观察 3：network Rx page lifecycle 比一般应用访存更适合 coloring。** driver 以 per-core ring/page pool 循环取 4 KiB page，allocation 顺序可预测，还能启动时从大块连续物理内存预分配；无需追踪任意 virtual-memory access（§1–§2）。
  - **依赖假设**：ConnectX 类 driver、per-core queue 与 page recycling 模型持续成立，且系统能预留足够 CMA contiguous memory。
- **观察 4：平衡 set 容易，平衡非 2 次幂 slice 更难。** Ice Lake 有 2,048 set、26 slice、12-way；5 个高位 set-index bit 可形成 32 个 page group。依次跨 group 分配能平衡 set，但 26-slice hash 的 modulo bias 仍会制造 hotspot（图 2、图 6–10）。
  - **依赖假设**：undocumented slice hash、set bits 与 associativity 能被正确 reverse engineer，换 CPU 后需要重新验证。
- **假设 1：full Sepia 的 ring/TCP tuning 对业务可接受。** headline 的 1.51 倍不只来自 coloring；系统同时把每核 Rx ring 从默认 16 MB 缩到 4 MB，并把 TCP receive buffer 调到 4 MB，以保持 write-hit regime（§5、图 16）。burst 或高 bandwidth-delay product connection 可能需要更大 buffer。
- **假设 2：应用自己的 LLC footprint 不会抢掉新增空间。** microbenchmark 重点测 packet page；production 中 application code、index、storage cache 与其他 tenant 也共享 LLC，可能让 32 MB effective budget提前耗尽。

## 核心方法

### 1. 把物理页分成 32 种颜色

Ice Lake 的 set index 有 11 bit，其中低 6 bit 落在 4 KiB page offset 内，不能由 page allocator 控制；物理地址 bit 12–16 留下 5 bit，可把 2,048 个 set 分成 32 个 page group，每组覆盖 64 个 set。Linux 默认不看 group，Sepia 的 Stride-1 则轮流从 32 个 group 各取一页，先把 set-level pressure 拉平（图 6–7、§4.1）。

group 内按连续物理地址递增分配，利用 slice hash 会把相邻地址分散到不同 slice 的经验规律。它不能完全消掉 26-slice modulo bias，但不需要保存一张昂贵的精确 mapping table，适合 kernel fast path。

### 2. Tetris 只用于测上界

作者另行 reverse engineer 每页的 slice/set pattern，把互补 pattern 拼成 Tetris block，接近理论最佳 slice balance（图 8）。在 full LLC model 中，Default/Stride-1/Tetris 的 effective capacity 分别是 18/32/35 MB，即相对 Default 增加 77.8%/94.4%。但 Tetris 超过 35 MB 后 violation 从 0.04% 跳到 9.43%，而实际 page recycle 会打乱预定顺序，所以论文明确说它不 practical；Sepia 实现采用 Stride-1，不是 Tetris（§4.1–§4.2）。

在只有 2-way 的 DDIO write-miss region，Stride-1/Tetris effective capacity 降到 3/5.5 MB，仅为理论 6.5 MB 的 46.2%/84.6%。这解释了为何 full LLC 被撑爆后，Sepia 收益会下降（图 10）。

### 3. Sepia Manager 建 per-core colored pool

Manager 用 Linux Contiguous Memory Allocator（CMA）为每个 DDIO core 预留连续区域，并按 page-group × group内位置组织成二维数组。实现每核预留 16 MB：4 MB 给 256-entry Rx ring，12 MB 给 descriptor replenishment；18 个 core 合计 288 MB（图 11、§4.3、§5）。

一个 shared pool 可给不同 core 分配互斥 color，减少 cross-core conflict，但 active-core 数变化时要重建 working set，page 又必须等 NIC 归还，管理复杂且 group 不能总是公平切分。Sepia 选择每核独立 pool，让每个 core 都可轮询全部 32 个 group；这省去跨核协调，却接受“多个 core 仍可能同时选同一 color”的平均化取舍。

### 4. Sepia Allocator 在 page hole 下维持颜色顺序

理想情况是按 0…31 page group 循环。现实中 application read 决定 page 何时 recycle，某个预期位置可能还没归还。allocator 遇到 hole 时不改 color，而是从同 group 选择最早可用 page；某组完全不可用就暂时跳过。pool 耗尽时回退 Linux allocator，因此不会阻塞 network stack，但会混入 uncolored page。负载降低、colored page 回收后，系统自然恢复（图 12、图 17、§4.3）。

### 5. 实际系统还控制 working set

Sepia 的最终配置是 **Stride-1 + 4 MB Rx ring + 4 MB TCP Rx buffer**。coloring 把 effective LLC 变大，ring/TCP throttling 把 working set 变小，两者共同把更多 flow 留在 DDIO write-hit regime。driver 只需在初始化调用 `sepia_init()`、补 ring 时调用 `sepia_alloc()`；prototype 集成 Linux 6.6 ConnectX driver，application 不改代码（§5）。

## 设计取舍

- **Stride-1 简单性换非完美 slice balance**：不需要在 runtime 查询 hash，full LLC 只能用到 82.1%，2-way DDIO region 更只有 46.2%。
- **per-core pool 换免协调**：core 上下线不需重建全局 pool，但 cross-core color collision 没有硬隔离保证。
- **预分配换稳定 fast path**：288 MB CMA 与默认 ring footprint 相当，却要求启动时拿到连续物理内存；长期 fragmentation、hotplug 和 memory pressure 未测。
- **fallback 换可用性**：burst 不会因 colored pool 空而阻塞，cache conflict 会暂时回来。
- **缩小 ring/TCP buffer 换 cache locality**：有利于低 RTT 200 Gb/s testbed；高 RTT、大 burst 或不同 congestion-control workload 可能丢 throughput。
- **硬件感知换 application 透明**：Nginx/Memcached 不修改，kernel/driver 和每代 CPU 的 mapping methodology 必须维护。

## 实验设置

- 主平台是两台直连 200 Gb/s 的机器，每台 2-socket Intel Xeon Gold 6354（Ice Lake，18 core/socket）、39 MB 12-way LLC、256 GB DRAM、ConnectX-6；使用 Ubuntu 20.04、Linux 6.6，开启 TSO/GRO、9,000-byte MTU、DIM、aRFS，关闭 hyperthreading、IOMMU 与 irqbalance（§3.1）。主要结果只使用 18 个 DDIO-enabled core。
- microbenchmark 是 iperf long-lived TCP flow，一 flow 一 core；指标是 total throughput 除以总 CPU utilization 得到的 throughput-per-core、LLC/L2 miss、packet-occupied memory。best case 还把 ring/TCP buffer 都调小，不是只换 allocator。
- application 包括 [[NVMe|NVMe]]-over-TCP [[SPDK]]（NULL block device、64/128 KB、QD16）、Nginx HTTP POST（2/4 MB body）和 Memcached 100% SET（4 KB–1 MB value）。SPDK 与 Nginx 每个配置取 5 次平均；Memcached 只写明报告平均吞吐，没有给重复次数。
- 论文称 methodology 也在 Xeon 6526Y Emerald Rapids 上测试过，但定量主结果都来自 6354；AMD、跨 socket、多 NIC 与 virtualized tenant 未覆盖。

## 实验与结果

- **有效容量**：以 violation ratio 少于 1% 定义 effective LLC，Default/Stride-1/Tetris 分别为 18/32/35 MB。实用 Stride-1 比 Linux 增 77.8%，Tetris 上界增 94.4%；在 2-way DDIO region 则仅为 3/5.5 MB（图 9–10、§4.2）。
- **200 Gb/s 主结果**：write-hit microbenchmark 中，Sepia throughput-per-core 比 Default 最高高约 1.51 倍，以 3.5 个 core 饱和链路，Linux 需 6 个；到 6 flow 仍保持约 0.4% LLC miss（图 13–14、§6.1）。这是 coloring 与 ring/TCP throttling 的组合结果。
- **组件消融**：只加 Stride-1 平均提高 8.62%、最高 11.4%；完整 Sepia 最高提高 50.8%。4-flow memory bandwidth 为 Default 31.29 GB/s、Stride-1 30.01、只缩 ring 16.59、Sepia 0.96，说明 working-set control贡献很大（图 16、表 1、§6.2）。
- **容量溢出与 burst**：18 flow 时 Sepia LLC miss 升到 16.4%，但仍低于 Default、throughput-per-core 仍更高。单 core 4 条 6 MB-buffer flow 会让 pool 中 uncolored page 达 35%，miss 到 3.5%，throughput 从 64 降到 55 Gb/s；每 20 秒切回 1 flow 后可恢复（图 15、图 17、§6.1、§6.3）。
- **SPDK 与 Nginx**：相对 default Linux，NVMe-over-TCP 的 64/128 KB read bandwidth 最高提高 26.7%/51.1%，但 target 是 NULL device；Nginx 2/4 MB POST upload bandwidth 最高提高 20%/27.1%（图 18–19、§6.4）。
- **Memcached 边界**：4 KB SET 几乎不从 DDIO 受益，Sepia 与 Default 持平；512 KB/1 MB 时 bandwidth 最高提高 22%/25.9%，average latency 从 0.74/1.40 ms 降到 0.60/1.12 ms（图 20、§6.4）。

## 论断—证据表

| 论断 | 论文证据 | 评测边界 | 置信度 |
|---|---|---|---|
| conflict miss 是 leaky DMA 的独立来源 | 38 MB 小于 39 MB LLC，violation 39.3%、miss 16.5%；throttling 后 miss 仍达 46.4%（图 3–5） | Ice Lake slice/set trace；violation 没有精确 CPU-read timing | 强 |
| Stride-1 可扩大实用 effective LLC | 图 9：18 MB 提到 32 MB，增 77.8% | 依赖 reverse-engineered Intel mapping；94.4% 是 Tetris 上界 | 强 |
| 完整 Sepia 显著提高 CPU efficiency | 图 13：1.51 倍、3.5 vs 6 core、约 0.4% miss | 200 Gb/s 低 RTT，ring/TCP buffer 同时调小 | 强 |
| coloring 与 working-set control 有协同 | 图 16、表 1：Stride-only 平均 8.62%，完整系统最高 50.8%，bandwidth 31.29 降到 0.96 GB/s | 少量 flow 的 best-case microbenchmark | 强 |
| application 收益随 payload/working set 增大 | 图 18–20：SPDK 最高 51.1%、Nginx 27.1%、Memcached 25.9%；4 KB Memcached 持平 | SPDK 为 NULL backend；大 POST/SET workload | 中到强 |

## 批判性分析

### 论证链条

论文先用 write-hit/write-miss 区分纠正“只有 2-way capacity”的旧解释，再用 physical-address trace 找到 conflict，最后以 coloring、allocator 与应用实验闭环，观察到设计的映射很直接。最容易误读的是两个 headline：94.4% 是 Tetris theoretical upper bound，而真正 Sepia 用 Stride-1、增 77.8%；1.51 倍也不是 page coloring 单独贡献，消融显示 Stride-1 平均只有 8.62%，大部分收益依赖同时缩 ring/TCP working set。旧页把两者都归到 allocator，夸大了单一机制。

### 假设压力测试

如果 CPU 有不同 set indexing/slice hash、cache 不 sliced、slice 数和 associativity 改变，32-group Stride-1 需要重新推导。若 application data 本身占大量 LLC，network page 即使分布均匀也会 capacity miss。高 RTT 连接需要更大 receive window，4 MB TCP buffer 可能压低 line rate；bursty DMA 已显示 uncolored page 会达 35%。跨 socket/[[NUMA]]、多个 NIC queue、VM/tenant 和 background memory traffic 都可能破坏“各 core 平均均衡”的假设。

### 实验可信度

microbenchmark 从 counter/trace 到真实 throughput，另有 clear ablation、write-hit/write-miss、burst 与三类 application，且公开了 4 KB Memcached 无收益的负结果，证据较完整。baseline 是 tuned networking feature 但默认 allocator/ring；full Sepia 又同时改 ring 与 TCP buffer，幸好图 16能拆开贡献。缺口是没有直接对比 SHRing 等 capacity-miss system，没有 AMD/多代硬件定量图，没有 production trace、多 tenant、p99 tail 或 allocator overhead。SPDK 用 NULL device，Nginx/Memcached 选择大 payload，偏向放大 DDIO 作用。

### 系统性缺陷

Sepia 依赖 undocumented cache mapping 与 288 MB contiguous CMA reserve，论文未测 boot-time reservation failure、memory fragmentation、hotplug、page migration、memory pressure 或 kernel upgrade后的维护成本。per-core pool 没有全局 color ownership，不能提供 cache isolation；fallback 让正确性安全但性能不可预测。系统只改 ConnectX Rx driver，generic driver API、userspace stack 和 zero-copy application buffer 尚未实现。论文也没有讨论 cache side channel、安全隔离或与 Intel CAT/DDIO-way reconfiguration 的控制冲突。

## 局限与后续工作

- **局限 1**：实用 Sepia 是 77.8% Stride-1，不是 94.4% Tetris；后者依赖无法在 recycle 下保持的精确顺序。
- **局限 2**：主要结论来自 Intel Ice Lake + ConnectX-6 单 socket Rx path；AMD、跨 socket、多 NIC 与 TX 未验证。
- **局限 3**：headline 性能需要同时缩小 Rx ring 与 TCP buffer；高 RTT、burst 与不同拥塞控制下可能不成立。
- **局限 4**：需要 288 MB CMA contiguous reserve，未量化 fragmentation、allocation overhead 与其他 LLC consumer 干扰。
- **后续工作 1**：在不同 Intel/AMD 代际自动探测 set/slice mapping，并用硬件 counter 验证错误探测时安全降级。
- **后续工作 2**：扫描 RTT、bandwidth-delay product、burst length、ring/TCP buffer 与 application LLC footprint，报告 throughput、p99 与 miss phase boundary。
- **后续工作 3**：与 shared-ring/traffic-shaping/DDIO-way control 组合和单独对比，分离 conflict/capacity/L2 三类贡献。
- **后续工作 4**：在多 socket、多 NIC、VM tenant 和长期 memory pressure 下测 CMA 成功率、cache fairness 与恢复时间。

## 相关

- **相关概念**：DDIO、page coloring、LLC conflict miss、zero-copy networking、[[NUMA]]
- **相关系统**：[[SPDK]]、SHRing、NetChannel
- **同会议**：[[OSDI-2026]]
