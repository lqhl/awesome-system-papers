---
type: paper
name: Osprey
full_title: "Osprey: Transparent and Efficient Virtual Memory for Secure Computation"
authors: [Yicheng Liu, Alice Yeh, Harry Xu, Raluca Ada Popa, Sam Kumar]
venue: OSDI
year: 2026
tags: [secure-computation, virtual-memory, speculative-execution, paging, obliviousness]
source_pdf: "[[osdi26-liu-yicheng.pdf]]"
source_md: "[[osdi26-liu-yicheng]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# 面向安全计算的透明高效虚拟内存（OSDI 2026）

> **原题**：Osprey: Transparent and Efficient Virtual Memory for Secure Computation

> **一句话总结**：Osprey 利用安全计算密文的“内容无关性”，让低成本推测进程提前给真实进程提供页面访问轨迹，再异步换入换出 SSD；应用代码不用修改、每个密码库改少于 200 行，在 32 GB 内存限制下相对 Linux swapping 最多加速 12×，四线程时最多 16×，但保证依赖正确识别密文区域，且“不误推测”并不等于访问轨迹从不漏记。

## 问题与动机

安全计算（Secure Computation，SC）允许系统在密文上计算，涵盖同态加密（Homomorphic Encryption，HE）和安全多方计算（SMPC）。代价是数据显著膨胀：garbled circuit 中一个明文 bit 对应 128-bit 密文，即 128× 空间。中等规模 analytics 因而很快超过 DRAM，落到通用 Linux swap 后会因同步 page fault 和不理解未来访问的回收策略变得极慢。

已有 MAGE 一类 memory programming 系统提前算出完整访问计划，可用接近 Belady 的策略管理内存，但要求应用改写到专用 DSL、为密码协议重写 backend，而且计划大小随执行时间增长，短程序也可能生成 GB 级计划。另一类系统并行运行推测副本获取未来访问；为降低副本内存而丢页后可能走错路径，必须 checkpoint、rollback 或 re-fork，内核实现复杂。

Osprey 想同时保留两点：像操作系统虚拟内存一样根据运行时压力工作，又不要求 SC 应用迁移框架。它的突破口不是一般程序的推测执行，而是密文工作负载特有的访问无关性。

## 关键观察 / 隐含假设

- **观察 1：SC 不只有输入无关性，还有内容无关性。** 输入无关（input-oblivious）表示秘密输入不改变访问轨迹；内容无关（content-oblivious，CO）更强：执行中把密文字节改成任意值，访问轨迹仍不变（§1、§3.1）。
  - **依赖假设**：被标为 CO 的对象只含密文，不含会影响控制流的 pointer、长度或 allocator metadata。
  - **可能失效场景**：开发者把非 CO 数据错误放进 CO region，会改变地址计算甚至程序正确性；系统没有自动证明 annotation soundness。
- **观察 2：密文占主要内存，密码运算占主要 CPU。** 推测 pass 可把所有 CO 虚拟页 alias 到同一个 4 KiB 物理页，并用 `OSPREY_TOUCH` 只记录本应访问的地址后跳过密码运算，从而避免复制主要资源（§3.1–§3.2）。
  - **依赖假设**：SC 库的调用粒度足以低成本标注；被排除的 `binfclayer` 每 bit 调用一次库函数，`OSPREY_TOUCH` 过于频繁，推测甚至比真实执行更慢（§9.2）。
- **观察 3：页面级有限前瞻已经足以隐藏多数 SSD I/O。** programmed pass 不需要完整离线计划，只要推测 pass 能持续领先，并用 lookahead/lookbehind 异步发出 swap-in/out（§6）。
  - **依赖假设**：CPU、SSD 和 trace pipeline 能让预测及时到达；CPU oversubscription、低带宽存储或难压缩轨迹可能使真实执行追上推测。
- **假设 1：SC 的访问模式本身不会泄露秘密。** Osprey 收集并用访问轨迹调度 I/O，安全性继承所用协议的 obliviousness；论文没有单独做 side-channel 分析。
  - **证据强度**：中；这是 SC 协议的设计前提，但实现错误或不完整库适配仍需独立审计。

## 核心方法

### 两个并行 pass

命令行工具同时启动 speculative process 和 programmed process（图 1）。两者执行同一应用、链接同一个轻量适配过的 SC library；前者生成未来页面访问，后者执行真实密码计算。访问序列通过共享内存队列流式传递，因此不用把完整计划落盘，也能随运行时内存压力调整。

SC library 需要两类小改动。第一类用 CO allocator 分配真正的密文字节；第二类在密码操作入口插入 `OSPREY_TOUCH(inputs, outputs)`。在真实 pass 中该调用为空操作；在推测 pass 中，它直接登记这些范围并从调用函数返回。annotation 不完整通常只会增加推测 CPU 或漏掉可预取访问，不改变 programmed pass 的计算；但把非 CO 数据误标为 CO 并不安全。

### 把 CO 数据与 metadata 分开

普通 allocator 把 free-list pointer 或 bitmap 与用户数据放在一起，这些 pointer 不能被覆盖。Osprey 因而预留 1 TiB CO region，使用 2 MiB slab 存密文，把所有 slab metadata 放在普通内存。一个平行数组把 slab 地址映射到 metadata；每 slab 只需一个 8-byte pointer，整张表约 4 MiB。推测 pass 再通过 124 行内核模块 `/dev/aliased`，用一个 VMA 把整个 CO region 的虚拟页都映射到同一物理页，避免为每页创建 VMA。

### 收集页面轨迹并隔离副作用

Osprey 以页面而非每条 load/store 为粒度。推测进程只保留一个有限窗口的 mapped pages；窗口达到阈值后按 microset 策略统一 unmap，让后续访问再次 fault。窗口小则轨迹更精确、fault 更多，窗口大则采集更快、预测更粗。

page-fault pre-handler 上的 [[eBPF|eBPF]] 程序把地址写入 ring buffer，用户线程异步整理；`OSPREY_TOUCH` 提供的显式范围与 fault 事件用 timestamp 合并。磁盘副作用放进只读 lower layer 加可丢弃 upper layer 的 OverlayFS。对 EMP-Toolkit 的网络初始化、teardown 和密码操作，库适配用 `OSPREY_TOUCH` 跳过推测 pass 的通信。

### 用轨迹驱动异步换页

programmed pass 每隔一批访问选择 key page，用人为触发的 page fault 对齐“程序执行到哪里”和“轨迹处理到哪里”。它先异步发出未来批次的读请求，隔 lookahead 批次再等待完成；swap-out 同样先写回、隔 lookbehind 批次确认完成后 unmap。

内存策略设 low、high、max 三个 watermark。超过 high 后异步回收到 low；超过 max 时暂停推测并立即回收 CO pages。候选页必须已驻留至少 `execnow` 时间，且未来窗口内不会再访问；优先回收推测为 clean 的页，再按驻留时间近似 LRU。Osprey 扩展 `madvise` 增加精确回收指定页的 `MADV_RECLAIM`，并扩展 `userfaultfd` 支持 private anonymous memory 和 `PROT_NONE` access fault。

### 让多线程各自看到同步 fault

线程调度会使共享页被另一个线程提前 fault-in，导致目标线程的 key-page fault 消失。Osprey 为每个线程维护独立 trace 和 memory programmer，并利用 Intel Memory Protection Keys（MPK）让同一页只对指定线程不可访问。其他线程先触碰该页也不会取消目标线程之后的 fault。完整 `OSPREY_TOUCH` 还能绕过依赖调度顺序的 fault 采集。

## 设计取舍

- **库级适配换取应用透明**：现有应用零修改，但 SEAL 和 EMP-Toolkit 维护者仍分别要改最多 143、106 行；这不是对任意二进制的透明 paging。
- **在线有限前瞻换取运行时适应性**：不用 GB 级计划，可响应内存压力；却不能像 MAGE 用全局最优 Belady replacement。
- **用户态策略换取少量通用内核接口**：核心算法易开发，但仍依赖 eBPF 权限、一个 alias module、修改后的 `userfaultfd`/`madvise` 和 Intel MPK。
- **SSD 容量换取 DRAM**：主动写 swap 能运行 90–192 GB footprint 的任务，却增加 I/O 和 SSD endurance 成本。
- **边界条件**：最适合密文占主要内存、密码运算占主要 CPU、访问轨迹结构化且运行够长的 SC workload；细粒度库调用、难压缩轨迹或 CPU/SSD 饱和会削弱收益。

## 实验与结果

- 实验使用 Intel Xeon Gold 5520+ 服务器、256 GB DDR5 和 Micron 7450 PRO [[NVMe|NVMe SSD]]；SMPC 两方通过双向 200 Gbit/s 直连。8 个 CKKS/SEAL 与 garbled-circuit/EMP kernel 的 unbounded footprint 为 73–192 GB，OS、MAGE 和 Osprey 的目标内存均为 32 GB（§9.1–§9.3，图 5、表 1）。
- Osprey 在全部 8 个 kernel 上都快于 OS Swapping，CKKS Sum/Statistics 最多加速 12×；6 个 workload 的时间不超过 unbounded-memory 运行时间的 1.6×。该结果包含双 pass、eBPF、共享队列和首批 trace 的端到端 warm-up（§9.3–§9.4，图 5）。
- Osprey 在 7/8 workload 上与 MAGE 相当或更快；EMP workloads 中两者差距少于 10%。但 CKKS 比较受 backend 影响：MAGE 每次操作要 serialize/deserialize SEAL ciphertext，tiled matrix multiply 中该项约占 40% 时间，不能把全部领先归因于 paging（§9.4）。
- password reuse detection 的 unbounded footprint 约 163 GB，Osprey 在 32 GB 下接近 unbounded 性能；comorbidity analysis footprint 约 91.9 GB，Osprey 利用清晰阶段结构避免保留之后不再访问的数据，也接近 unbounded（§9.5，图 6）。
- 四线程实验中，Osprey 相对 OS Swapping 最多加速 16×；SEAL matrix-vector multiply 随 1–8 线程近似线性扩展。compute-intensive matrix multiply 在 1、2、4 线程时略慢于 OS，8 线程后才因瓶颈转向内存而领先（§9.6，图 7–8）。
- 最小适配修改 SEAL 96 行、EMP 7 行；推荐适配分别为 143、106 行。推荐 `OSPREY_TOUCH` 对计算时间影响很小，却把每应用线程平均 CPU 最多降低 45%；EMP 在约 30% unbounded memory 下达到超过 90% unbounded 性能，并把 CPU 降到 0.98 core/thread（§9.7–§9.8，表 2、图 9）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| CO 能让低内存、低 CPU 的在线推测 pass 实用 | 单物理页 alias、跳过密码计算；推荐标注最多降 45% CPU（§3、§9.8） | 两个 CPU SC libraries；没有 GPU backend | 强 |
| Osprey 明显优于 Linux swapping | 8/8 kernel 更快，单线程最高 12×、四线程最高 16×（图 5、图 7） | 结构化 SC workloads、特定 NVMe 和 32 GB 限制 | 强 |
| 应用级透明性成立 | 应用零修改；库最小修改 7/96 行、推荐 106/143 行（表 2） | 必须取得并维护 SC library 源码 | 强 |
| 在线有限前瞻可接近离线 MAGE | 7/8 workload 相当或更快；EMP 差距少于 10%（§9.4） | CKKS backend 不同；MAGE 有序列化额外成本 | 中 |
| “无误推测”有明确而有限的含义 | 不产生 phantom access；不完整标注时仍可能漏记跨线程访问（§11.1） | 漏记不破坏计算正确性，但会延迟 prefetch | 强 |

## 批判性分析

### 论证链条

论文最有力的地方是把密码学属性变成系统简化：如果密文内容不会改变访问轨迹，就能丢弃密文和跳过密码计算，从根源上免去传统 speculative memory manager 的 rollback。CO allocator、alias module、`OSPREY_TOUCH`、在线 memory programmer 和 MPK 分别补上数据分离、资源压缩、轨迹采集、I/O 隐藏和多线程同步，机制链条完整。

不过，“消除 misspeculation”需要按 §11.1 收窄。Osprey 保证推测轨迹不会包含真实执行不发生的 phantom access；不完整 annotation 和多线程共享页仍可能让 trace 漏访问，只是 programmed pass 最终正常 fault 并保持正确。更关键的是，错误地把控制 metadata 标成 CO 会直接破坏执行，论文没有自动验证这一安全前提。

### 假设压力测试

如果 SC protocol 允许 secret-dependent shortcut、GPU kernel 或库内 pointer 与 ciphertext 混排，CO 假设和当前 allocator 接口都可能不成立。推测必须领先真实执行；SEAL matrix-vector 的推测 CPU 约为真实 pass 每线程的 42%，在 CPU 已满载时可能无法领先，而 EMP 同一比例少于 10%，说明成本强烈依赖协议实现（§11.2）。

多线程正确预取依赖完整 `OSPREY_TOUCH` 和 Intel MPK。ARM、GPU 或不允许内核扩展的云环境不能直接复用。论文还假设 local NVMe 足以承受主动写回；换成网络 SSD、跨 rack far memory 或 SSD endurance 受限环境后，交叉点需要重测。

### 实验可信度

评测包含两类密码协议、8 个 kernel、两个 end-to-end application、1–8 线程、annotation 消融和三种 baseline，且报告了未 tiling matrix multiply、compute-bound 多线程以及被排除 `binfclayer` 等负面边界，透明度较高。所有 Osprey 时间包含 warm-up，性能口径清楚。

公平性仍有两处限制。第一，Osprey 自己用内部 watermark 限内存而不进 cgroup，因为作者观察到 cgroup 会额外 swap；作者通过 RSS/htop 检查 32 GB，但隔离机制不同。第二，MAGE 与 Osprey 对 CKKS 使用不同执行 backend；EMP 虽做了相同优化并把 unbounded 差异压到 5% 内，CKKS 的领先仍混有 serialization 成本。SMPC 只测高速本地直连，WAN 结论引用前作而非本系统实测。

### 系统性缺陷

部署要修改 Linux 5.15、加载 eBPF 和内核模块、取得 SC library 源码并长期维护 annotation。库升级后，新增 ciphertext type 或 side effect 若未标记，性能会悄然退化；误标则可能出错，但系统没有 lint、runtime assertion 或可观测性指标指出 coverage。

每个应用线程还带一个推测线程和一个 programming thread，增加调度实体与 CPU 竞争。频繁 SSD swap 的峰值写流量、写放大和器件寿命没有量化。故障恢复也未讨论：speculative/programmed process、shared trace queue 或 SSD I/O 中途失败后，系统是否能安全重启和清理 OverlayFS 仍不清楚。

## 局限与后续工作

- **局限 1**：正确性依赖 SC library 只把真正 content-oblivious 的数据放入 CO region；当前没有自动验证，且完整标注影响多线程 trace 质量。
- **局限 2**：实现依赖 Linux 5.15 扩展、eBPF、alias kernel module 和 Intel MPK，未覆盖 GPU、ARM、托管云或不同 swap backend。
- **局限 3**：`binfclayer` 因库调用过细被排除，naive matrix multiply 的难压缩轨迹也会退化；方法并非对所有 SC 程序同样透明高效。
- **后续工作 1**：为 CO type 和 allocation 建静态类型检查，并用故意误标 pointer/metadata 的测试验证能在执行前拒绝错误 annotation。
- **后续工作 2**：在 CPU 饱和、NVMe 带宽受限和 WAN/far-memory backend 上扫描 trace window、lookahead 和线程数，以吞吐、p99 fault stall、写放大和预测领先距离评估稳定区间。
- **后续工作 3**：实现不依赖 MPK 的多线程同步路径，并测试 process crash、trace queue 丢事件和 swap I/O 失败时的恢复语义。

## 相关

- **相关概念**：[[Secure-Computation]]、[[Virtual-Memory]]、[[Speculative-Execution]]、[[Obliviousness]]、[[Memory-Protection-Keys]]
- **同类系统**：MAGE、3PO
- **同会议**：[[OSDI-2026]]
