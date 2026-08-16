---
type: concept
aliases: [io-uring, Linux-io_uring]
last_updated: 2026-08-14
tags: [linux, io, asynchronous-io, kernel]
---

# io_uring

> io_uring 是 Linux 的共享环异步 I/O 接口。应用把操作写入 submission queue（SQ），内核把结果写入 completion queue（CQ）；它能批量提交、减少部分系统调用，并承载注册缓冲区、轮询和 passthrough 等快速路径，但不会自动消除文件系统、调度、设备或虚拟化成本。

## 核心概念

传统同步 `read`/`write` 把“一次调用、一次等待、一次完成”绑定在一起。io_uring 把这三件事拆开：应用先准备 SQE（submission queue entry），内核或提交线程消费它，完成后生成 CQE（completion queue entry），应用再按自己的事件循环回收。一次 `io_uring_enter` 可以提交和获取多个操作，因此高并发程序不必为每个 I/O 单独做一次 syscall。

这个接口不是单一数据路径。普通模式仍经过 VFS、文件系统和 block layer；`SQPOLL` 让内核线程轮询提交环，只减少提交侧切换；`IOPOLL` 让完成侧主动轮询；fixed buffer/file 减少注册与查找；NVMe passthrough 可以把协议命令更直接地交给设备。论文比较 io_uring 时，必须写清启用了哪一种模式，否则同一个名字可能代表完全不同的 CPU、延迟和隔离取舍。

## 关键观察 / 隐含假设

- **异步接口和完成机制是两个问题。** [[UnICom-FAST26]] 发现，多进程下 `SQ_POLL` 集中的是提交线程，完成仍受底层 interrupt、sleep/wakeup 和调度约束，所以它不能单独解决完成路径成本。[[DPAS-FAST26]] 也把重点放在 polling、hybrid polling 与 interrupt 的切换，而不是 SQE 本身。
  - **隐含假设**：设备已经足够快，使完成通知和调度成为可见瓶颈。消费级 SSD 或大块 I/O 中，介质延迟与带宽可能重新主导。

- **polling、interrupt 和 hybrid 没有固定赢家。** 低 CPU 争用、持续高 IOPS 时 polling 可压低延迟；共置计算任务或负载稀疏时，interrupt 更节省 CPU。[[Aeolia-SOSP25]] 进一步指出，部分“interrupt 很慢”来自内核过早睡眠与调度策略，而不是中断本身；[[DPAS-FAST26]] 则用 per-I/O 反馈和运行时模式切换适应变化。
  - **隐含假设**：控制器能观测 queue depth、CPU contention 或 wakeup 结果，并且切换的 hysteresis 足以避免抖动。

- **io_uring 也是可扩展的控制面。** [[FS-PI-FAST26]] 用 SQE attribute 携带 Protection Information（PI），避免为每种 read/write 变体新增 syscall；[[RosenBridge-FAST26]] 在 SQ/CQ 两端加入 hook，让虚拟机中的近数据程序能够改写或重新提交 NVMe 请求。这两项工作说明共享环不仅减少 syscall，也能承载新的 per-I/O 语义。
  - **隐含假设**：新增属性、helper 和 passthrough 仍能经过权限、边界与资源检查。越接近设备，内核替应用承担的验证越少。

- **高层索引仍可能决定端到端表现。** [[OdinANN-FAST26]] 使用 io_uring 访问 SSD，但其主要收益来自 direct insert、页面内更新合并和近似并发控制，而不是更换 I/O API。异步队列只是把这些算法产生的磁盘并行度送到设备。
  - **隐含假设**：应用能产生足够多独立请求，并能正确管理 buffer lifetime、completion 和 backpressure。

- **保留内核路径仍有生态价值。** [[KernelBypassTCP-ATC25]] 把 io_uring 列为尚未纳入比较的 kernel-enhancement 路线；它的横向实验同时表明，绕过内核并不会在所有 bulk、RPC、连接数和多核场景都获胜。io_uring 的定位正是在保留 Linux 权限、文件系统和运维接口的同时缩短部分路径。

- **不是所有内核调度问题都该用 io_uring 解决。** [[Rakaia-OSDI26]] 需要在 TCP receive softirq 中恢复完整 RPC message，再做跨连接调度；它只把 io_uring 作为相邻机制提及。字节流语义、协议解析或 message-level scheduling 不会因换成共享提交环自动消失。

## 设计空间

### 提交侧

- 普通提交保留 syscall，但可批量 amortize，CPU 使用更可控；
- `SQPOLL` 减少提交 syscall，代价是常驻 kernel thread 和多进程间的资源竞争；
- fixed file/buffer 降低每次查找与 pinning 成本，却增加注册、生命周期和内存占用；
- passthrough 缩短协议路径，但应用更依赖具体设备语义，兼容性与安全审计更难。

### 完成侧

- interrupt 在空闲时省 CPU，但有中断投递、sleep/wakeup 与 cache pollution；
- polling 在持续高负载时延迟低，却会长期占核；
- hybrid polling 先睡后轮询，需要准确估计设备完成时间，容易受调度延迟污染；
- 集中 completion thread 可跨进程复用，但可能成为 IOPS 上限和故障单点。

### 内核集成与 bypass

- 经过 VFS/文件系统的路径保留 page cache、权限、namespace、crash consistency 与通用观测；
- direct I/O 避免 page cache，但要求 alignment、buffer lifetime 和应用自己的缓存策略；
- SPDK、GPU-direct 或 userspace driver 可以更短，却常要独占 queue/core，并重做资源隔离、错误处理与升级兼容；
- 虚拟化中还要决定请求留在 guest、QEMU userspace、host kernel 还是 passthrough device，单纯使用 io_uring 不能消除 VM-exit。

## 证据边界

- [[Aeolia-SOSP25]] 的 userspace interrupt 结果依赖 Sapphire Rapids user interrupt、`sched_ext` 与 Optane；它证明一种替代设计可行，不代表普通 io_uring 在所有设备上都慢。
- [[DPAS-FAST26]] 的主要实验是 Linux block layer 的小随机 I/O，且禁用 hyper-threading；固定 NAND/XPoint 阈值在一块 SN850X 上失效，不能当作通用策略。
- [[UnICom-FAST26]] 只支持 direct I/O，并用一个专用 completion core；它相对 io_uring 的结论主要来自 Optane 和多进程 `SQ_POLL` 设置，consumer SSD 上差距明显缩小。
- [[FS-PI-FAST26]] 的用户 PI 接口同样限于 direct I/O；buffered I/O 与 `mmap` 无法直接携带用户提供的 PI。
- [[RosenBridge-FAST26]] 使用定制 QEMU、guest driver、io_uring hook 与 NVMe passthrough；相对裸机 express path 仍有显著差距，且只验证本地盘虚拟化。
- [[OdinANN-FAST26]] 的稳定性证据来自单机单 SSD 的图索引；不能把它的端到端收益归因于 io_uring，也不能外推到分布式索引。

## 研究判断

io_uring 的真正价值不是“syscall 变成零”，而是把提交、完成和 per-I/O 元数据变成可组合接口。它给系统设计者一个比新 syscall 更统一、比完全 bypass 更兼容的落点；但系统仍必须明确谁负责轮询、谁拥有 queue、buffer 何时可释放、过载怎样回压、进程退出与设备失败怎样清理。

因此，评测 io_uring 不应只报单线程 IOPS。至少要给出模式、设备、I/O size、queue depth、CPU 核预算、P99 延迟、共置干扰和失败路径，并把 API 收益与文件系统/应用算法收益分开。否则“用了 io_uring”只是一条实现信息，不是一项可以独立成立的性能结论。

## 引用本概念的论文

- [[Aeolia-SOSP25]] — 比较 Linux io_uring、SPDK 与 userspace interrupt 路线。
- [[DPAS-FAST26]] — 为 SSD 完成路径动态选择 polling、hybrid polling 与 interrupt。
- [[FS-PI-FAST26]] — 通过 io_uring attribute 向 direct I/O 传递 Protection Information。
- [[OdinANN-FAST26]] — 用 io_uring 支撑 on-disk 图索引的并发 search/insert。
- [[RosenBridge-FAST26]] — 用 SQ/CQ hook 和 NVMe passthrough 跨虚拟化边界运行 express I/O。
- [[UnICom-FAST26]] — 说明提交侧 `SQ_POLL` 不等于完成侧优化，并提出集中完成机制。
- [[KernelBypassTCP-ATC25]] — 将 io_uring 定位为 kernel-enhancement 对照，提醒 bypass 没有普适优势。
- [[Rakaia-OSDI26]] — 展示 RPC message scheduling 仍需协议语义，不能只靠异步字节 I/O API。

## 相关概念

- [[NVMe]] — io_uring 最常见的高速块设备后端之一。
- [[SPDK]] — 更彻底的 userspace polling 与 kernel-bypass 路线。
