---
type: paper
name: Spice
full_title: "Rethinking Process Snapshots for Near-Warm Serverless Cold Starts"
authors: [Ben Holmes, Baltasar Dinis, Lana Honcharuk, Adam Belay, Joshua Fried]
venue: OSDI
year: 2026
tags: [serverless, snapshot, cold-start, virtual-memory, operating-systems]
source_pdf: "[[osdi26-holmes.pdf]]"
source_md: "[[osdi26-holmes]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# 让 Serverless 进程快照接近热启动（OSDI 2026）

> **原题**：Rethinking Process Snapshots for Near-Warm Serverless Cold Starts

> **一句话总结**：Spice 发现，从磁盘恢复 [[Serverless]] 函数慢，不只是因为工作集预测不准，而是现有 OS 无法同时高效表达“按访问顺序存盘、按虚拟地址映射”的稀疏页面，也缺少批量恢复进程元数据的接口；它用 SHELF、spliceVMA、`reexec()` 和 Junction 元数据恢复，把 13 个函数的冷调用做到只比热调用多 0.6–18 ms，平均比进程快照和 VM 快照方案分别快 7.5 倍和 9.5 倍。

## 问题与动机

许多冷门函数不值得一直留在内存里。论文引用的生产数据表明，Microsoft 的 81% 应用每分钟至多调用一次；Ant Financial 的 60% 以上函数因为内存紧张，冷启动次数多于热启动。把完成语言运行时、库加载和 JIT 初始化后的状态保存成快照，可以跳过这些工作，但前提是快照真的能从持久化存储快速恢复，而不是依赖机器上已有的热父进程。

现有恢复边界各有结构性成本。CRIU 在进程边界恢复，需要从一个空进程出发，用数百到数千次系统调用重建线程、文件描述符和内存映射；VM 快照已经包含 guest kernel 的这些对象，但也把整个 guest OS 的内存和恢复后唤醒的后台工作带了回来。论文测得 VM 活跃内存是相应进程工作集的 1.2–3.4 倍，而且进程工作集里有 19%–50% 是本可通过 host page cache 复用的文件页。VM 暂停期间积累的 timer/RCU 等 housekeeping 会在恢复后集中运行：即便把函数设为 `SCHED_FIFO`，仍可额外阻塞最多 10 ms，占端到端时间的 22%–79%（§2.1、图 2–3、表 2）。

内存布局还有第二个矛盾。恢复器希望把热点页按预计访问顺序连续存盘，以便顺序读取；Linux 的 `mmap` 却把连续文件区间映到连续虚拟地址。按访问顺序重排后，传统映射需要把地址空间切成大量小 VMA，论文观察到 VMA 数最多增加 32 倍；若按虚拟地址保存，又会退化成零散 I/O、复制和缺页。Spice 的主张因此很具体：缺的是能直接装载“稀疏、重排覆盖层”的 OS 抽象，而不只是更好的预取策略。

## 关键观察 / 隐含假设

- **观察 1：运行中进程的快照不是普通 ELF 的少数连续 segment，而是原文件或零页上的稀疏页面覆盖层。** 热点页的磁盘顺序和虚拟地址顺序通常不同；强行用普通 VMA 表达会造成 VMA 爆炸（§2.2、图 4）。
  - **依赖假设**：离线 profiling 得到的页面集合和访问顺序在后续请求中大体稳定。
  - **可能失效场景**：输入决定控制流、JIT 持续生成代码、堆工作集快速漂移时，错误预取会占用 I/O；Spice 仍能正确 fault-in 未预测页面，但延迟优势可能消失。
- **观察 2：进程元数据恢复慢，主要因为缺少批量导入接口，而不是这些元数据本身很大。** CRIU 的恢复时间会随需重放的系统调用数量增长；Spice 的紧凑对象反序列化只需 0.9–7.5 ms（§2.1、§3.4、图 12）。
  - **依赖假设**：快照点上的锁和等待队列处于可丢弃状态，文件描述符等对象可延迟重开，外部世界也没有无法重建的会话状态。
- **观察 3：进程边界能保留 host 对文件页的共享，而 VM 边界看不到这种复用。** 这既缩小读取量，也让并发恢复共享 page cache（表 2、图 14）。
  - **依赖假设**：恢复节点能找到内容完全相同的 runtime、library 和 container image；仅有相同路径并不足以证明内容相同。
- **假设 1：平台可以预先准备干净的 Junction 实例、隔离环境和物理页池。** Spice 的关键路径不含 LibOS 启动、container/cgroup/namespace 配置，也用预分配页池吸收恢复时的分配突发。
  - **证据强度**：中。论文明确说明这些选择，却没有量化池大小、闲置成本、耗尽后的尾延迟或多租户隔离代价。

## 核心方法

Snapshot Hybrid ELF（SHELF）把每个原 VMA 的“主要来源”和“快照覆盖层”分开表示。主要来源可以是原文件或匿名零页；只有与主要来源不同的页面才写进 SHELF。私有工作集页面放在文件头之后，并按 profiling 中的访问时间连续排列；冷的私有页面放在末尾。program header 记录原 VMA、backing file 和覆盖区间，trace 还记录虚拟地址、时间戳及预计是否写入。这样既能顺序读取热点私有页，也不会丢掉未走过路径在快照时应有的字节（§3.1、图 6）。

spliceVMA 是与这个格式配套的新 VMA 类型。一个连续 spliceVMA 内的不同页，可以来自 SHELF 区间、原文件或零页。每个 VMA 指向一个离线构造、完全平衡、连续数组布局的只读 B+ 区间树；kernel 可直接使用磁盘中的树，不需要恢复时分配节点、重平衡或修指针。缺页时先查覆盖区间，没有命中才回到原 backing。`munmap`、`mremap`、`mprotect` 仍修改正常 VMA/PTE；拆分后的 VMA 共享同一棵不可变树（§3.2、图 7）。

新系统调用 `reexec()` 负责批量装载。同步阶段先发起连续私有工作集读取，在 I/O 进行时批量建立 spliceVMA，再为已经可用的私有页、page-cache hit 和零页装 PTE，然后尽早返回应用。异步 kernel 线程继续读取零散共享页、处理私有页完成事件并主动安装 PTE，避免热点路径上的 minor fault。文件页进入 page cache 以便共享，快照私有页进入匿名内存；预计只读的零页映射共享 CoW zero page，预计会写的零页则提前分配私有零页（§3.3、图 8、图 9）。

非内存元数据由 Junction 单地址空间 LibOS 恢复。它从 task root 遍历对象图，每种对象用定制 serializer 保存必要字段；静止的锁和等待队列不保存，pipe 只保存有效环形缓冲区，文件描述符延迟重开。恢复前平台从一个“已干净启动”的 Junction 实例池取实例，再反序列化线程、FD、signal handler 和 timer。这个实现证明了进程边界的批量接口有潜力，但不是 Linux 原生进程元数据恢复；Linux kernel 只直接实现了虚拟内存部分（§3.4）。

生成快照时，语言 shim 在安全点暂停线程、触发 [[Garbage-Collection|GC]] 和清理 cache，Junction 先顺序导出临时镜像，7.4 KLoC 的 `shelftools` 再离线去掉未改文件页与零页、去重、建区间树并生成 trace。kernel profiler 反复执行“记录 fault—按 trace 恢复”，直到工作集稳定。运行实现还包括 Linux 6.5 上约 7.1 KLoC 的 kernel module；论文 artifact 可复现图 10 的主要延迟结果（§4、Artifact Appendix）。

## 设计取舍

- **新内核抽象换恢复速度**：SHELF、spliceVMA 和 `reexec()` 消除了逐页映射，但需要新的快照格式、kernel module 和更大的解析攻击面，不能直接部署在 stock Linux。
- **离线 profiling 换低关键路径开销**：稳定路径可获得连续 I/O 和预装 PTE；变化大的请求仍正确，却可能出现无用预取和同步缺页。
- **进程边界换更小状态**：能共享文件页、不恢复 guest OS；代价是 socket、device、peer process 等外部对象需要逐类定义恢复语义。
- **Junction 原型换 Linux 兼容证据**：可快速实现对象级序列化，但 FunctionBench 只能证明所测 Linux binaries 可运行，不能证明完整 syscall 与 kernel-heavy workload 的兼容性。
- **预热平台资源换函数冷状态**：函数本身从磁盘冷恢复，但干净 LibOS 实例和物理页池是预备资源；论文没有把这两种池的容量规划计入资源成本。

## 实验与结果

- 单机使用 28 核 Xeon Gold 5420+、128 GB 内存和标称 13,600 MB/s、1.4M IOPS 的 Crucial T705 [[PCIe|PCIe]] 5.0 SSD；13 个 Python、Node.js、Java FunctionBench 工作负载在冷 page cache 下，Spice 相对 FaaSnap*、REAP*、CRIU* 的端到端延迟分别降低 17%–96%、18%–95%、14%–96%（§5.1、图 10）。
- 跨全部函数，Spice 平均比进程快照方案快 7.5 倍、比 VM 快照方案快 9.5 倍；它是热调用的 1.01–6.34 倍，只多 0.6–18 ms，而比较系统多 3.6–1,197 ms。这里的“热调用”已经多次执行，但特意保持 CPU cache 和 TLB 等微结构状态为冷（图 10、附录表 5）。
- RNN 的用户态映射基线要创建 3,212 个 VMA，比热调用多 21 ms、达到热调用的 2.5 倍；依次加入 spliceVMA/批量建 VMA、主动装 PTE、异步预取后，只多 2 ms，即 23%。完整消融在 13 个函数上把相对热调用开销从 1.10–25.83 倍降到 1.01–6.34 倍（§5.2、图 11、附录表 5）。
- 元数据恢复为 0.9–7.5 ms，CRIU* 为 2.6–749 ms；区间树 hot lookup 在 10/100/1,000 个 interval 时为 4/8/11 cycles，Linux maple tree 为 41/59/97 cycles。私有页预取、共享页预取和 PTE 安装峰值分别约 5.2M、0.6M、4.6M pages/s（图 12、表 3、图 13）。
- 25 个并发恢复时，复用文件 page cache 相比“不共享版本”少用约 20% 存储带宽，调用吞吐高约 30%；基于 Azure trace 合成的函数混合在并发 25 时达到由并发 1 外推理想吞吐的 76%。后者把 trace 中的持续时间缩放后映射到最接近的 13 个 benchmark，并非真实生产请求回放（§5.2–§5.3、图 14、图 15）。
- 在 540 MB/s、95K IOPS 的 Micron 5400 SSD 上，单次读延迟从 58 μs 增至 163 μs；Spice 的 hello/image/CNN 延迟约从 0.9/19/67.2 ms 增至 1.2/27/71.5 ms，而 FaaSnap* 约从 39.2/75.5/250.6 ms 增至 248.4/490.6/1,889.1 ms。该实验只有三个函数和单恢复，未测试慢盘并发饱和（§5.4、图 16）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 稀疏重排页面需要新的 VMA 表达，而不只是预取优化 | 图 4、图 11、附录表 5 | Linux 6.5、FunctionBench；RNN 展示 3,212 VMA 的细粒度分解 | 强 |
| 进程快照可以从冷存储恢复到接近热调用 | 图 10 | 13 个函数、三种语言、冷 page cache、单机高速 [[NVMe\|NVMe]]；不含控制路径 | 强 |
| 批量进程元数据恢复比系统调用重放更快 | 图 2、图 12 | Junction serializer 对修改后的 CRIU；对象类型限于 benchmark | 中 |
| 进程边界的文件页共享能提高并发恢复能力 | 表 2、图 14 | 单机、同一软件栈、25 个并发、快速 SSD | 中 |
| 异步预取能降低对较慢 SSD 的敏感度 | 图 16 | 三个函数、一次恢复；慢盘尚未达到带宽瓶颈 | 中 |

## 批判性分析

### 论证链条

论文把两个常被混在一起的问题拆开：快照边界决定需要恢复多少 OS 状态，内存表示决定这些状态能否高吞吐装载。SHELF 与 spliceVMA直接解除“磁盘顺序和虚拟地址顺序必须一致”的限制，`reexec()` 负责把剩余读取藏到执行后面，Junction 则验证批量元数据恢复。图 11 和附录表 5 能把主要收益对应回这些机制，因此“快照恢复 data path 可以接近热调用”的论证是闭合的。

但论文有时把这个较窄结论写成“end-to-end cold start”。评测明确排除了请求调度、placement、network setup、container/cgroup/namespace 配置，也把 LibOS boot 移到池中。实验实际证明的是从已有隔离环境里恢复函数状态并执行，而不是完整云平台收到请求到返回结果的端到端延迟。

### 假设压力测试

最关键的是工作集稳定性。论文反复 profile 到 trace 稳定，但没有改变函数输入来测 trace miss、无用读取比例或 P99 page-fault tail。若一个函数按输入选择模型、动态加载插件或生成大量 JIT code，SHELF 仍保持字节正确，性能却可能退回到随机缺页。类似地，静态路径名只在固定 container image 中安全；论文自己也指出生产版应使用 content hash 或 image-layer ID。

另一个假设是预备资源始终充足。高并发下预分配物理页池可能耗尽，干净 Junction 实例池也可能排队；论文没有报告两者的容量、补充速率或内存占用。图 15 只扩到 25 个并发，不能直接推出多租户机器或机架级 burst 的行为。

### 实验可信度

实验覆盖三种语言、13 个函数、冷 cache、进程和 VM baseline、逐组件消融、并发以及快慢 SSD，且 artifact 明确支持复现主图。作者也认真调优 baseline：给 VM 中的函数用 `SCHED_FIFO`，给 CRIU 加 lazy mapping，所以不是拿默认弱配置做比较。

仍需注意环境并不完全同质：Spice 在 Junction/Linux 6.5，CRIU* 在原生 Linux，VM artifact 使用 Linux 4.14 guest。表 4 说明这些非 kernel-heavy 函数在 Junction 和 Linux 的热执行大多接近，但 hello 等短任务差异明显，也没有 kernel-heavy workload。论文还未说明主延迟图的重复次数、误差条或尾分位；因此平均值很强，尾延迟证据较弱。

### 系统性缺陷

SHELF 是能导入地址空间和 OS 对象的高权限格式。论文未讨论恶意或损坏快照的校验、签名、版本兼容、回滚和 fuzzing；这些都是把 `reexec()` 放入生产 kernel 前必须解决的攻击面。外部 socket、GPU/device state、多进程共享对象、credential 和 peer failure 的语义也没有展示。

快照制作需要安全点、语言专用 shim、多轮 profiling 和离线重写。论文没有量化 capture time、存储空间、构建吞吐、镜像升级后的重建成本，也没有评测 snapshot GC 或跨版本兼容。因而它对“恢复有多快”给出强证据，对“整个快照生命周期是否经济”还没有证据。

## 局限与后续工作

- **局限 1**：当前原型在 host 上运行；直接用于 VM 仍需 host–guest hypercall 和 EPT 批量预装，论文只提出方向。
- **局限 2**：完整 Linux 进程元数据恢复尚未实现；现在依赖 Junction、干净 LibOS 实例池和受限的 benchmark 兼容面。
- **局限 3**：评测不含平台控制路径、隔离环境建立、外部连接恢复、快照制作成本及预分配池的资源经济性。
- **后续工作 1**：用真实请求输入和到达 trace 测 trace hit rate、无用预取字节、P50/P99 延迟，并在快慢盘并发饱和时测页池耗尽行为。
- **后续工作 2**：为 SHELF 加 content identity、格式版本、签名和原子回滚；对 parser、interval tree 与 `reexec()` 做损坏镜像和恶意镜像 fuzzing。
- **后续工作 3**：实现 socket/epoll、多进程和 device state 的恢复协议，并通过 peer disconnect、镜像升级和部分恢复失败注入验证语义。

## 相关

- **相关概念**：[[Serverless]]、[[Virtual-Memory]]、[[Memory-Prefetching]]、[[Page-Cache]]
- **同类系统**：CRIU、FaaSnap、REAP、Junction
- **同会议**：[[OSDI-2026]]
