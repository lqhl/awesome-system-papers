---
type: paper-report
name: Sepia
full_title: When DDIO Meets Page Coloring: Revisiting DDIO Performance with Sepia
authors: [Changwoo Song, Sanghyun Kim, Jinhyeok Oh, Qizhe Cai, Joonsung Kim, Jaehyun Hwang]
venue: OSDI
year: 2026
source_pdf: "[[osdi26-song.pdf]]"
source_md: "[[osdi26-song]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-06-24
---

# Sepia：当 DDIO 遇到页着色（OSDI 2026）

> **原题**：When DDIO Meets Page Coloring: Revisiting DDIO Performance with Sepia

> **一句话总结**：论文发现 DDIO 的 leaky DMA 不只由 DDIO 保留容量不足造成，Linux 页分配器引入的 LLC slice/set 冲突会把 39 MB LLC 的有效容量压到 18 MB；Sepia 用按 LLC 颜色分布的连续页池和较小 Rx 工作集把有效容量提高到 32 MB，并在 200Gbps 链路上用 3.5 个 CPU 核达到满速，相比 Linux 少用 2.5 个核。

## 问题与动机

Intel DDIO 允许 NIC 把接收数据直接写入 LLC，CPU 随后处理数据时可以避免从 DRAM 读取。它对高带宽网络栈的 CPU 效率很有帮助，但数据可能在处理完成前被逐出 LLC，形成 leaky DMA。过去通常把原因归结为 DDIO 保留的 LLC ways 太少。

论文在 Ice Lake 测试机上发现，工作集即使小于整个 LLC，也可能因为物理页映射到相同的 slice/set 而发生冲突。单流约 22 MB 的工作集时 LLC miss rate 为 0.9%；把工作集增至约 38 MB 后，虽然仍接近但未超过 39 MB LLC，miss rate 却升到 16.5%（§3.2、图 4）。因此只限制 in-flight bytes 或扩大 DDIO 区域不能覆盖全部问题。

Sepia 将页着色用于 NIC Rx 页分配。它预留连续物理内存，按照 LLC 的 set/slice 映射建立每核页池，顺序选择不同颜色的页，并把 Rx ring 和 TCP buffer 调小以控制总工作集。

## 关键观察 / 隐含假设

- **观察 1：DDIO 在写命中时可以使用整个 LLC，而不只是 DDIO 保留 ways。** CPU 先把页重新载入 LLC 后，后续 NIC 写入可以命中任意 way；只有写未命中才会在 DDIO 保留 ways 中分配（§2、§3.2）。
  - **依赖假设**：页在下一次 DMA 前仍能留在 LLC 中。
  - **可能失效场景**：总工作集超过 LLC 或其他应用强烈竞争 LLC 时，系统会转入写未命中模式，此时有效 DDIO 容量只有约 3 MB（图 10）。
- **观察 2：Linux 默认分配器不考虑 set 和 slice，导致有效容量显著小于物理容量。** 38 MB 工作集的 slice/set violation ratio 达 39.3%，而 39 MB LLC 的默认有效容量只有 18 MB（§3.3、图 5、图 9）。
  - **依赖假设**：物理地址到 LLC slice/set 的映射可被逆向并稳定用于目标 CPU。
  - **可能失效场景**：CPU 架构、slice 数、hash 函数或 set-index 位布局改变时，Sepia 的颜色模型需要重新推导。
- **观察 3：网络 Rx 页的生命周期足够规律，适合简单顺序着色。** NIC DMA 页、softIRQ 处理页、copy-to-user 后回收页形成相对确定的循环（图 1）。
  - **依赖假设**：页池不会长期耗尽，且回收顺序的偏差可以由同色页补洞。
  - **可能失效场景**：突发流量会耗尽 Sepia 页池，迫使系统引入未着色页；四条单核流使未着色页占比达到 35%，miss rate 升至 3.5%（图 17）。

## 核心方法

Sepia Manager 预留连续 CMA 内存，把每个 per-core Rx 页池组织成二维数组。行对应 32 个 page group；同一 group 的页共享上层 set-index bits，也就是同一种颜色。每核页池都覆盖全部颜色，避免根据活跃核数量重新划分颜色而需要重建工作集。

Sepia Allocator 以 stride-1 顺序轮转 page group，尽量让页均匀覆盖 set。页尚未回收时，分配器从同一颜色中选择下一个可用页，保持颜色序列而不是跳到任意物理页。若池耗尽，则暂时回退 Linux 分配器，并在着色页重新回收后恢复使用（§4.3、§5）。

Stride-1 同时利用两点：按 page group 分配可避免 set-level imbalance；连续物理地址通常会在 slice 间扩散，可部分缓解 slice 冲突。论文还构造了 Tetris 作为理论上限，通过逆向得到的 slice/set 模式排列页序，但它依赖精确的预定义序列，难以应对真实回收造成的 page holes，因此没有作为实际实现。

Sepia 不只做页着色，也限制工作集：默认每核把 Rx ring 调到 4 MB，并配合 4 MB TCP receive buffer。前者降低 descriptor 页数量，后者限制 packet-occupied memory，使低流数时工作集保持在着色后的 32 MB 有效容量内。

## 设计取舍

- **硬件特化换取低热路径开销。** 方法需要 LLC set 位宽、slice hash 和切片数量等微架构知识；论文只验证了 Intel Ice Lake 与 Emerald Rapids，移植到 AMD 或未来 Intel CPU 需要重新逆向。
- **每核全颜色页池换取管理简单。** 该设计减少跨核协调，但允许不同核心在共享 LLC 中发生部分冲突；它只保证平均颜色均衡，不提供严格的跨核隔离。
- **工作集限制换取 DDIO 命中率。** 较小 Rx ring 和 TCP buffer 可能降低缓冲突发流量的能力，并改变拥塞控制和排队行为；论文主要在链路瓶颈由接收端 CPU 承担的环境中评测。
- **回退 Linux 分配器保证鲁棒性，但会污染颜色分布。** 突发 workload 下的性能恢复依赖后续页回收，未给出长期高突发压力下的稳定界限。

## 实验与结果

- 测试平台为双路 Intel Xeon Gold 6354、39 MB LLC、ConnectX-6 200Gbps NIC、Linux 6.6，启用 TSO、GRO、9000B jumbo frame、DIM 和 aRFS（§3.1）。
- 默认 Linux 的有效 LLC 容量只有 18 MB；Stride-1 提高到 32 MB，即相对提高 77.8%，可使用总 LLC 的 82.1%；理论上限 Tetris 为 35 MB（图 9）。
- 在写命中最佳配置中，Sepia 将 LLC miss rate 保持在约 0.4%，用 3.5 个核打满 200Gbps，相比 Linux 少 2.5 个核，单位核吞吐提高约 1.51×（图 13）。
- 消融实验中，单独 Stride-1 的单位核吞吐平均提高 8.62%、最高 11.4%；Ring Throttling 在 4 流时使内存带宽比 Default 降低 47.0%（图 16、表 1）。两者结合最高带来 50.8% 的吞吐提升。
- 在写未命中 regime，18 流时 Sepia 的 LLC miss rate 最高 16.4%，但仍低于 Linux，说明页着色不能消除超出有效 DDIO 容量后的容量 miss（图 15）。
- SPDK NVMe-over-TCP 的 64 KB 和 128 KB 请求带宽分别最高提高 26.7% 和 51.1%；Nginx 的 2 MB 与 4 MB 页面上传带宽最高提高 20% 和 27.1%；Memcached 的 512 KB 与 1 MB value 吞吐最高提高 22% 和 25.9%，1 MB 时平均延迟从 1.40 ms 降至 1.12 ms（图 18–20）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| DDIO miss 的主要来源不只是保留容量，页映射冲突会降低有效 LLC 容量 | 22 MB 与 38 MB 工作集的 0.9%/16.5% miss rate、violation ratio 1.97%/39.3%（§3.2–§3.3、图 4–5） | Ice Lake、特定 Rx 页生命周期；violation 与实际逐出并非逐次访问级证明 | 强 |
| Stride-1 能提高有效 LLC 容量 | Default 18 MB、Stride-1 32 MB、Tetris 35 MB（§4.2、图 9） | 依赖已知 slice/set 映射和连续页；仅覆盖两类 Intel 平台 | 强 |
| Sepia 能降低真实网络应用的 CPU 和带宽成本 | 200Gbps 用 3.5 核、SPDK/Nginx/Memcached 结果（§6.1、§6.4、图 13、18–20） | 单机接收端瓶颈、特定 NIC/CPU、预设 ring 与 buffer 调参 | 中-强 |
| Sepia 能应对页池耗尽 | 1/4 流交替实验中着色页可恢复（§6.3、图 17） | 20 秒切换和受控突发；长期高压与多租户竞争未覆盖 | 中 |

## 批判性分析

### 论证链条

论文从地址分布测量出发，证明“工作集小于 LLC”不等于“不会冲突”，再用可控页分配实验把有效容量从 18 MB 提高到 32 MB，最后在真实网络应用中观察到 CPU 效率改善。Stride-1、Ring Throttling 与最终 Sepia 的消融也能区分页着色和工作集缩减的贡献。

但部分性能收益来自两项配置变化，而不是页着色单独贡献：Sepia 同时缩小 Rx ring 和 TCP buffer。论文通过消融报告了各自影响，却没有在更多拥塞控制、突发到达和不同 buffer 语义下验证这些配置是否保持应用行为等价。对“通用网络栈优化”的外推因此应保持谨慎。

### 假设压力测试

Sepia 的核心依赖是 Intel LLC 的物理地址映射稳定且可测量。slice hash 是未公开的微架构细节，CPU 换代后可能改变。论文指出 power-of-two slice 数可消除部分 modulo bias，但仍需要颜色分配；这说明硬件结构本身并不能替代软件页布局。

方法还默认工作集主要由可控的 NIC Rx 页和 packet-occupied memory 构成。其他应用、虚拟机、文件缓存或内核线程共享 LLC 时，颜色均衡不会提供隔离。多核高负载超过约 3 MB 有效 DDIO 容量后，Sepia 只能降低冲突，不能解决容量 miss。

### 实验可信度

实验覆盖 iperf、SPDK、Nginx 和 Memcached，并包含 miss rate、吞吐、单位核效率、内存带宽和平均延迟。基线使用同一 Linux 内核和相同硬件，消融能够解释工作集缩减的作用。限制在于平台数量少，网络流量主要由人工构造的 TCP 流和固定消息大小产生；没有比较更多 NIC、CPU 架构、虚拟化环境或真实生产 trace。

### 系统性缺陷

Sepia 需要 CMA 预留每核 16 MB；18 个核心的示例分配 288 MB 连续物理内存。论文没有详细讨论长时间运行后的 CMA 碎片、内存压力和 NUMA 放置。每核页池也可能造成内存预留与活跃流数量不匹配。页池耗尽时回退到 Linux 分配器，意味着性能可能随负载历史变化，运维系统需要暴露颜色命中率和回退率等指标；论文未给出完整可观测性方案。

## 局限与后续工作

- **局限 1**：实现绑定 ConnectX 驱动和 Intel LLC 细节；其他 NIC、AMD 或未来 Intel 架构需要重新获得 set/slice 映射。
- **局限 2**：写未命中 regime 的有效 DDIO 容量仍约为 3 MB，18 流时 miss rate 达 16.4%；Sepia 需要和 SHRing、流量整形或 LLC 架构改造结合。
- **局限 3**：突发流量会引入未着色页，当前恢复实验不能代表长期过载；应测量持续 burst、流加入/退出和跨核迁移下的稳定性能。
- **后续工作 1**：将 Sepia 与 SHRing 的共享 Rx ring 结合，在相同链路速率和 buffer 预算下分别测量总工作集、DDIO miss rate、P99 延迟和内存带宽。
- **后续工作 2**：在至少一种非 Intel 架构和虚拟化环境中自动推导颜色映射，并验证 CMA 预留、NUMA 放置与多租户 LLC 竞争的成本。

## 相关

- **相关概念**：[[DDIO]]、[[Page-Coloring]]、[[LLC]]、[[Zero-Copy-Networking]]
- **同类系统**：[[SHRing]]、[[NetChannel]]、[[SPDK]]
- **同会议**：[[OSDI-2026]]
