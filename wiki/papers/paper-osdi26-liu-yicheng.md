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
last_reviewed: 2026-02-12
---

# 面向安全计算的透明高效虚拟内存（OSDI 2026）

> **原题**：Osprey: Transparent and Efficient Virtual Memory for Secure Computation

> **一句话总结**：安全计算中的密文既占据大部分内存，又具有内容无关性，因此 Osprey 可以用低成本推测执行在线记录页访问、异步预取和回收 SSD 页面；在 32 GB 内存限制下，它在 8 个工作负载上最多比操作系统交换快 12×，并在 6 个工作负载上达到充足内存配置的 60% 以内。

## 问题与动机

安全计算（Secure Computation，SC）在密文上执行数据分析，但密文扩张会让中等规模数据集也超出内存。例如，garbled circuit 中一个明文 bit 可能对应 16 B 密文。传统 OS paging 在这种场景下会产生大量同步 I/O，运行时间急剧上升。

已有的 SC-aware 方案各有边界。MAGE 需要应用改写到特定 DSL，并提前生成可能达到 GB 级的内存计划；通用推测执行则需要处理错误预测、回滚和额外内存。Osprey 的目标是让直接使用 SC library 的应用无需改动，同时让库维护者只做少量移植。

## 关键观察 / 隐含假设

- **观察 1：密文数据具有 content-obliviousness（CO）**。在执行中把密文覆盖为任意字节，不会改变程序的内存访问模式（§3.1）。
  - **依赖假设**：SC 协议及库实现确实不会根据密文内容改变控制流或访问地址。
  - **可能失效场景**：库把密文元数据、指针或错误处理状态混在同一页，或使用数据相关的优化时，整页覆盖可能不再安全。
- **观察 2：密文扩张和密码计算分别主导内存与 CPU 成本**（§1、§3.1）。
  - **依赖假设**：非 CO 状态占比较小，且 cryptographic operations 是主要 CPU 开销。
  - **可能失效场景**：工作负载以控制逻辑、网络等待或非密文计算为主；此时并发 speculative pass 的成本可能无法隐藏。
- **观察 3：SC 的访问模式具有输入无关性，但线程调度仍可能造成观测顺序差异**（§7）。
  - **依赖假设**：线程可以分配到固定数据分区，或库能提供足够完整的 `OSPREY_TOUCH` 标注。
  - **可能失效场景**：线程共享状态广泛、同步顺序影响访问，或标注不完整导致访问记录缺失。

## 核心方法

Osprey 同时运行 speculative pass 和 programmed pass。前者记录页粒度的未来访问，后者消费流式访问序列，使用 `madvise`/`userfaultfd` 触发异步预取与回收。推测执行不需要完整复制密文：CO region 中所有密文虚拟页映射到同一个物理页；对密文操作则可用 `OSPREY_TOUCH` 触碰将被访问的范围后直接返回。这样既减少 speculative pass 的内存，也跳过主要密码计算。

系统提供 CO allocator，把密文放入独立的地址空间区域，并把 allocator 元数据留在普通内存。采用 2 MiB slab 和 1 TiB CO region 时，平行映射数组只需约 4 MiB。Linux 内核侧增加 124 LoC 的 `/dev/aliased` 模块，用单个 VMA 将大量虚拟页别名到一个物理页；eBPF 预处理器把 page fault 地址写入共享 ring buffer。

programmed pass 以固定批次和 key page 跟踪实际执行位置。lookahead 控制预取请求和等待之间的批次数，lookbehind 控制 swap-out 请求与确认之间的间隔。系统用 low/high/max 三个水位控制回收，并优先回收预测近期不会访问、预计非 dirty、且在内存中停留较久的页面（§6）。

多线程场景中，每个线程拥有独立 CO region、访问 trace 和 programmer。Osprey 使用 MPK 为每个线程设置独立的 key-page fault 条件，避免共享页被另一线程提前触发后破坏同步（§7.3）。磁盘写入通过 overlayfs 隔离；SMPC 的网络初始化、清理和密文操作在 speculative pass 中跳过（§5.3）。

## 设计取舍

- **透明性与库移植成本**：SC 应用不改源代码，但库需要使用 CO allocator，并可选添加 `OSPREY_TOUCH`。完整标注不是正确性要求，却决定 CPU 节省幅度。
- **在线决策与最优回收的差距**：Osprey 只看到有限未来窗口，不能像 MAGE 那样用完整 trace 的 Belady 算法；换来的是无需预先规划和可响应运行时内存压力。
- **用户态灵活性与内核扩展**：核心逻辑在用户态，减少内核侵入，但依赖 Linux 5.15 的 `MADV_RECLAIM`、private anonymous `userfaultfd` 和 access-violation 转发扩展。
- **SSD 流量与性能的交换**：积极 paging 会增加写放大和 SSD 磨损。论文指出设计可替换为 far memory 或 CXL，但没有给出耐久性测量。

## 实验与结果

- 在 SEAL 的 CKKS 和 EMP-Toolkit 的 garbled circuits 上评估 8 个工作负载；机器为 8×32 GB 内存，swap 使用 4 TB Micron 7450 PRO SSD，受限配置统一为 32 GB（§9.3）。
- Osprey 在所有工作负载上优于 OS Swapping，最佳为 12×；其中 6 个工作负载距离 Unbounded（能容纳全部计算的配置）不超过 60%（§1、图 5）。
- CKKS/SEAL 多数工作负载中 Osprey 优于 MAGE；MAGE 的 SEAL backend 每次操作序列化和反序列化 ciphertext，在 tiled matrix multiplication 中约占 40% 运行时间（§9.4）。
- EMP-Toolkit 受限配置下 Osprey 与 MAGE 的差距低于 10%；这也反映了 Osprey 在线、有限窗口回收策略相对完整离线计划的代价（§9.4）。
- password reuse detection（约 163 GB unbounded footprint）接近 Unbounded；comorbidity analysis（约 91.9 GB）因阶段性访问模式获得接近 Unbounded 的性能（§9.5、图 6）。
- 四线程下 Osprey 相对 OS Swapping 的优势最高达到 16×；matrix-vector multiply 随线程数线性扩展（§9.6、图 7–8）。加入 `OSPREY_TOUCH` 后，CPU usage per thread 最多下降 45%；EMP-Toolkit 达到超过 90% Unbounded 性能，同时约使用 30% 内存（§9.8、图 9）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| CO 能让 speculative pass 避免错误预测，并显著降低其资源成本 | §3.1、§9.8、图 9 | SEAL/CKKS 与 EMP-Toolkit；依赖库标注 | 强 |
| Osprey 比 OS Swapping 更适合受限内存的 SC | 图 5–6、§9.4–§9.5 | 32 GB、单 SSD、8 个工作负载及 2 个端到端应用 | 强 |
| Osprey 的在线回收接近离线 MAGE | §9.4、图 5 | EMP 差距低于 10%；SEAL 对比受 MAGE backend 序列化成本影响 | 中 |
| 多线程 MPK 同步机制有效 | §7.3、图 7–8 | SEAL 多线程；EMP-Toolkit 只支持单线程 | 中 |

## 批判性分析

### 论证链条

论文的链条在 CO 语义成立时是闭合的：密文可被覆盖，故 speculative pass 可共享物理页并跳过密码计算；访问 trace 再用于 programmed pass 的异步 paging。实验也覆盖了库移植、线程数和端到端应用，而非只测单一微基准。

但“透明”是应用级透明，不是完全零改动。库维护者需要理解哪些对象和操作是 CO；论文把这部分成本限定在少于 200 LoC，但不同 SC library 的内部表示可能更难拆分。另一个跳步是从两种协议和结构化 kernel 外推到更广泛 SC workload。

### 假设压力测试

完整 `OSPREY_TOUCH` 标注能生成确定性 trace；标注缺失时系统可能漏掉访问，虽不产生 phantom access，却会错过及时预取（§11.1）。高度数据相关的协议实现、动态线程分区或依赖密文内容的分支会破坏 CO 前提。论文还主要使用本地 SSD 和局域网络，WAN 延迟、SSD 共享争用以及更大集群的影响没有直接测量。

### 实验可信度

实验报告了端到端运行时间并纳入 warm-up，覆盖 unbounded、OS swapping 和 MAGE。对 MAGE 的比较并非完全同构：MAGE 的 baseline 使用其 interpreter，而 Osprey 和 OS 直接调用 SEAL；作者明确解释了这一差异，并对 EMP baseline 做了相应优化。评测对吞吐/运行时间和内存上限覆盖较好，但没有报告 SSD 写入量、尾延迟、能耗、故障恢复或长期运行成本。

### 系统性缺陷

Osprey 依赖 eBPF、定制内核模块、MPK 和扩展后的 `userfaultfd`，部署和内核维护成本高于普通 paging。页面追踪、双进程执行和同步 fault handler 也增加了可观测性与故障排查复杂度。论文未讨论多租户隔离、进程崩溃后的 swap 状态清理、恶意或错误库标注，以及 SSD 寿命的定量影响。

## 局限与后续工作

- **局限 1**：协议覆盖只有 CKKS/SEAL 和 HalfGates/EMP-Toolkit，且 EMP-Toolkit 的实验仅支持单线程。
- **局限 2**：不完整标注会损失预取及时性；论文未给出不同标注覆盖率下的系统化性能曲线。
- **局限 3**：评测使用单机 SSD 和两台服务器的直连网络，无法直接代表 WAN 或共享存储环境。
- **后续工作 1**：在至少三类 SC library、不同 CO 覆盖率和真实 WAN trace 上测量 P99、I/O 写入量及 CPU/能耗开销。
- **后续工作 2**：将 swap backend 替换为 CXL/far memory，比较相同访问 trace 下的带宽、延迟和容量收益。
- **后续工作 3**：验证 CO 思路在 oblivious database、神经网络训练或推理中的适用条件，明确哪些中间状态可安全覆盖。

## 相关

- **相关概念**：[[Secure Computation]]、[[Virtual Memory]]、[[Speculative Execution]]、[[Content Obliviousness]]、[[Far Memory]]
- **同类系统**：[[MAGE]]、[[3PO]]
- **同会议**：[[OSDI-2026]]
