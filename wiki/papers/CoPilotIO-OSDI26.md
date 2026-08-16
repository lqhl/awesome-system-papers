---
type: paper
name: CoPilotIO
full_title: "CoPilotIO: CPU as a Co-pilot for GPU I/O to Free GPU Compute"
authors: [Guanyi Chen, Qi Chen, Shu Yin, Jian Zhang]
venue: OSDI
year: 2026
tags: [gpu-io, nvme, storage, gpu-computing, asynchronous-io]
source_pdf: "[[osdi26-chen-guanyi.pdf]]"
source_md: "[[osdi26-chen-guanyi]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# 让 CPU 协助 GPU 完成 I/O（OSDI 2026）

> **原题**：CoPilotIO: CPU as a Co-pilot for GPU I/O to Free GPU Compute

> **一句话总结**：GPU 自己轮询 NVMe completion 会同时阻塞 warp、争用 SM 调度槽并制造显存流量；CoPilotIO 让 GPU 直接提交请求、CPU 在用户态轮询 completion，再用硬件 barrier 唤醒 GPU，并在 CPU 跟不上时才启用 GPU 协同轮询，因此用 24 个而不是 72 个以上的 SM 跑满约 25 GB/s PCIe，DLRM 相对 BaM 加速 1.85×。

## 问题与动机

GPU 显存远小于不断增长的模型、embedding 和图数据。应用因而需要 GPU 直接、按需地从 [[NVMe]] SSD 读取数据。现有方案有两条路线，但各有明显缺口：[[GPU-Direct-Storage|NVIDIA GPUDirect Storage]]（GDS）让数据绕过 CPU 内存，却仍由 CPU 经过内核 I/O 栈提交和回收请求；这会产生系统调用、buffer registration 和 DMA mapping 等开销，而且 GPU kernel 不能在需要数据的那一刻自行发起 I/O。

另一条路线以 [[BaM]] 为代表，把 NVMe submission queue（SQ）、completion queue（CQ）和轮询逻辑都放到 GPU。它实现了 GPU-initiated、on-demand I/O，却把 GPU warp 当作 I/O controller。论文把损失拆成三类：等待数据的 warp 无法继续执行后面的独立计算（intra-warp stall）；忙等 warp 抢占同一 SM 上其他 warp 的发射机会（inter-warp stall）；GPU-memory CQ 的反复读取又和应用争用显存带宽（inter-SM stall）。[[AGILE]] 虽把 I/O 做成异步，应用 warp 仍要轮询软件标志，并预留 GPU 资源做 completion polling。

CoPilotIO 的目标不是完全去掉 CPU，而是重新分工：GPU 保留低延迟、按需的提交路径，CPU 负责通常更浪费 GPU 资源的完成轮询。难点在于，小 I/O 的 completion 速率可能超过可用 CPU 核的处理能力，所以系统还必须在“节省 GPU”与“维持 I/O 吞吐”之间动态切换。

## 关键观察 / 隐含假设

- **观察 1：GPU completion polling 的代价不只是一条忙等 warp。** BaM 的同步轮询使同一 warp 的执行时间最高增至 1.87×；和计算 warp 共置时，计算完成时间最高增至 1.71×；当超过 24 个 SM 制造显存流量时，BaM/AGILE 的 I/O 带宽最多下降 50.6%（§3、图 2、图 6）。
  - **依赖假设**：应用同时有可运行的计算，释放出的 warp slot、SM cycle 和显存带宽能立即转成有效工作。
  - **可能失效场景**：纯计算、几乎没有存储等待的工作负载，或者大块顺序 I/O，轮询只占很小比例。
- **观察 2：CPU 并非天然做不好 GPU I/O，主要问题是内核路径和有限并行度。** 绕过内核的 SPDK-like CPU engine 使用 16 个线程，在请求大于 16 KB 时可以跑满一块 SSD；但小于 16 KB 时仍跟不上，若只靠 CPU 跑满整条约 25 GB/s 的 GPU PCIe 链路，论文估计需要 64 个以上 CPU 核（§3、图 3）。
  - **依赖假设**：服务器允许若干 CPU 核长期 busy-poll，并且 CPU、GPU、SSD 的 [[PCIe]]/[[NUMA]] 拓扑没有让跨设备控制流量变成新瓶颈。
  - **可能失效场景**：CPU 已被共置服务占满、GPU 跨 socket 访问 CPU 内存，或多 GPU 共享同一组 CPU 核和 SSD。
- **观察 3：CQ 放在 CPU 内存不会明显牺牲数据面吞吐。** SQ 仍在 GPU 显存中，GPU 可快速提交；CQ 只传递很小的控制信息，因此 GPU 或 CPU 轮询 CPU-resident CQ 都能接近 GPU-resident queue 的带宽，同时避开应用显存流量（§3、图 3）。
  - **依赖假设**：mapped host memory 的可见性和访问延迟稳定，completion 与 barrier 通知的控制流量远小于 SSD 到 GPU 的数据流量。
- **假设 1：CQ 中未及时处理的 completion 数量能代表 CPU poller 是否过载。**
  - **证据强度**：中。图 9 的人工变化负载支持该信号，但 SSD 固件尾延迟、completion burst 和 PCIe 拥塞也可能让 pending count 上升。
- **假设 2：CPU 核通常比 GPU SM 更容易让给 I/O 控制面。**
  - **证据强度**：中。端到端结果证明释放 SM 有价值，但论文没有把 CPU core-seconds、能耗和共置服务损失纳入同一成本模型。

## 核心方法

CoPilotIO 首先拆开 SQ 与 CQ。GPU 侧的 `CoPilot-GPUIOLib` 把 NVMe command 写入 GPU-resident SQ，并直接更新 doorbell，所以 GPU kernel 仍能按需发起 I/O。CQ 则固定在 CPU 内存中，由 CPU 侧的 `CoPilot-CPUIOLib` 通过 [[SPDK]]-like 用户态路径轮询；数据仍由 SSD DMA 到 GPU，CPU 只处理控制面（§4.2–§4.4、图 4）。这一设计直接回应观察 2 和观察 3：保留 GPU submission 的低延迟，同时去掉内核栈和 GPU-memory CQ 轮询。

每个异步请求返回一个 `cuda::barrier`。提交时，GPU 把 `(cid, barrier)` 写进 CPU 内存中的无锁 barrier table；CPU 看到 CQ entry 后用 16-bit command ID（CID）查表并 signal barrier。依赖数据的 warp 在 barrier 上休眠，GPU scheduler 可以运行其他 warp，而不是让它忙等。table 按 warp 私有化以避免锁争用，每项 8 B；按 4 块 SSD、每块 128 个 queue、QD 1024 计算，总空间约 4 MB（§4.3–§4.4、图 4）。

completion 出错时，CPU 在对应 table entry 设置错误状态、唤醒等待者并回收 CID。没有硬件 barrier 的 GPU 可以退化为 GDRCopy 更新 completion flag，但论文的主要实现和实验使用 `cuda::barrier`。这里的正确性重点是“等待者一定在对应 CID 完成后才继续”；它并不提供跨多次 I/O 的应用事务原子性。

CPU 核不足时，系统启用 CQ-driven adaptive CPU–GPU co-polling（§4.5、算法 1）。CPUAgent 默认持续运行；pending CQ entry 超过高阈值时，新 completion 被导向另一个、由 GPUAgent 轮询的 CPU-memory CQ，降到低阈值后再切回，并用 hysteresis 防止抖动。GPUAgent 在每个启用的 SM 上只用一个 warp，空闲时可 sleep 或 disable。

CPUAgent 与 GPUAgent 轮询各自的 queue，系统改变的是后续 completion 的归属，不是把正在运行的线程或已发出的请求在两端来回迁移。这一点降低了切换复杂度，也说明它的真实定位是“尽量少用 GPU polling”：高 IOPS 且 CPU 紧张时，GPU polling 仍会回来。

## 设计取舍

- **GPU SM 换 CPU 核**：正常负载下减少 GPU stall，但需要 4–8 个 dedicated CPU cores；低负载阶段最多使用 16 个（图 9c）。
- **CPU-only 的纯净异步路径换自适应回退**：CPU 跟不上时启用 GPUAgent 能保住吞吐，却逐渐恢复论文试图避免的 GPU 资源干扰。
- **split queue 的低显存干扰换跨设备同步**：CQ 和 barrier table 很小，但引入 CPU/GPU memory visibility、CID 复用、设备错误和 agent 失效等协议状态。
- **轻量集成换平台依赖**：GoFS 改动少于 20 行，但实现依赖 NVIDIA mapped host memory、`cuda::barrier`、GDRCopy 和可由 GPU 操作的 NVMe queue。
- **边界条件**：4–64 KB、I/O 与计算混合、高 SM 压力、需要深 queue 的工作负载最合适；大块顺序传输、CPU 极度紧张或没有可重叠计算时收益会缩小（§6）。

## 实验与结果

- 测试机是双路 Xeon Gold 6530（每 socket 32 核）、256 GB DDR5、A100 40 GB 或 H800 80 GB，以及四块 Samsung 990 Pro PCIe 4.0 SSD；相对 BaM，论文把 I/O-induced stall 的最大降幅总结为 55.5%，图 6b 中 inter-warp stall 最多下降 18.6%，而重显存竞争下 BaM/AGILE 的 I/O 带宽最多下降 50.6%，CoPilotIO 基本保持不变（§5.1–§5.2、图 6）。
- 4 KB random read/write 中，CoPilotIO 的吞吐和平均延迟都优于 BaM 与 AGILE；对单 SSD、16-thread GDS 的 request-size sweep 中，它在所有大小上更快，并在 4 KB 时仍接近设备峰值（图 7、图 8、表 2）。
- IOPS 随时间变化时，CPU-only 版本吞吐明显波动，自适应版本维持稳定带宽；GPUAgent 接管更多 CQ 后，active CPU poller 从最多 16 个降到 3–4 个，中等稳态通常为 4–8 个（§5.3、图 9）。
- 四块 SSD、8 KB random read、108 个 queue、QD 1024 下，CoPilotIO 用 24 个 SM 跑满 PCIe 4.0 x16 的约 25 GB/s，而 BaM 和 AGILE 需要 72 个以上 SM；图中是超过 3× 的 SM 数差异，论文摘要保守概括为少用 50% SM（§5.4、图 10a）。
- 把 [[GoFS]] 的 BaM I/O engine 换成 CoPilotIO 只改少于 20 行代码，4 KB random read 最多提升 17.4%；AGILE 因未知 runtime error 未进入这个比较（§5.5、图 10b）。
- SSD-offloaded FlashMoE（2,048 experts、64 GB weights）相对 BaM 最多加速 1.44×；Criteo 1 TB DLRM、batch 2,048、10,000 次迭代中，CoPilotIO 为 BaM 的 1.85×，AGILE 为 1.41×（§5.6、图 11）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| GPU polling 会在 warp、SM 调度和显存三个层面干扰应用 | 图 2、图 6：1.87×、1.71×、50.6% 三组测量 | A100/H800 上的合成 compute–I/O 共置 workload | 强 |
| split SQ/CQ 与 CPU barrier notification 能消除主要 polling stall，且不损失 I/O 吞吐 | 图 6–8、表 2 | 单机、四块消费级 NVMe、4 KB random I/O 为主 | 强 |
| adaptive co-polling 能在 CPU 不足时维持带宽 | 图 9：负载变化时吞吐稳定，CPU poller 降至 3–4 个 | 人工变化 IOPS、最多 16 个 CPU poller | 中 |
| CoPilotIO 用更少 GPU 资源跑满 PCIe | 图 10a：24 SM 对 72 个以上 SM、约 25 GB/s | 四 SSD、8 KB random read、108 queue | 强 |
| 释放的 GPU 资源能转成端到端应用性能 | 图 10b、图 11：GoFS +17.4%，[[MoE\|MoE]] 1.44×，DLRM 1.85× | 一个 GPU filesystem、一个 synthetic MoE 配置和 Criteo DLRM | 中 |

## 批判性分析

### 论证链条

论文的逻辑链比较完整：先分别测出三类 polling stall，再证明 CPU 用户态 poller 和 CPU-resident CQ 可行，最后用 split queue、hardware barrier 与 adaptive fallback 对应这些测量。最需要收窄的表述是“消除 GPU polling”：正常路径确实如此，但高 IOPS、CPU 不足时 GPUAgent 会重新轮询。准确结论应是“把 GPU polling 变成按需回退，并尽量减少它”，而不是任何负载下都彻底去掉。

### 假设压力测试

论文已证明单 GPU、单台双路服务器上的收益，没有证明这个 CPU/GPU 资源交换在多 GPU 或云端仍成立。若多块 GPU 共用 4–8 个 busy-poll CPU 核、SSD 或 PCIe switch，CPU 可能先成为系统瓶颈。pending CQ count 也不只反映 CPU capacity：SSD tail latency、completion burst 或 PCIe congestion 都可能触发 GPUAgent，阈值控制器需要在这些干扰下单独测误判率和 p99 latency。

### 实验可信度

实验覆盖三类 stall、纯 I/O、自适应行为、SM scaling、GoFS 和两个 AI workload，证据层次较完整；BaM 与 AGILE 也代表同步和异步 GPU-centric 路线。不过 GDS 因不支持 GPU-initiated I/O 只在图 8 比较，AGILE 又因 runtime error 缺席 GoFS 和 MoE，端到端 baseline 并不齐全。MoE 使用人工构造的 routing/config，硬件只覆盖两款 NVIDIA GPU 和一种 CPU/PCIe 拓扑；论文也没有报告误差条、CPU 共置干扰、整机能耗或成本。

### 系统性缺陷

论文描述了单次 completion error，却没有用 fault injection 检查 CPUAgent crash、SSD reset、GPU kernel abort、queue overflow、CID wraparound 或 barrier-table exhaustion。跨设备协议一旦丢失通知，等待 warp 可能永久睡眠；过早复用 CID 则可能唤醒错误请求。adaptive rebinding 与失败恢复之间的状态机、监控指标和运维接口也未展开。另一个未计量成本是 dedicated CPU busy polling 对同机服务和能耗的影响。

## 局限与后续工作

- **局限 1**：收益依赖可与 I/O 重叠的 GPU 计算；论文明确指出纯计算和大块顺序 I/O 的收益有限。
- **局限 2**：CPU scarcity 会让 GPUAgent 恢复轮询，系统没有用统一成本模型判断何时值得占用 CPU 或 GPU。
- **局限 3**：只验证单 GPU、四 SSD、NVIDIA runtime，缺少多 GPU、跨 [[NUMA]]、虚拟化/MIG 和不同 GPU vendor 的证据。
- **局限 4**：错误处理有设计说明，但没有 recovery/fault-injection 实验，也未证明 CID 与 barrier 生命周期在所有异常路径上有界结束。
- **后续工作 1**：分别控制 CPU contention、SSD tail latency 和 PCIe congestion，测 pending-count controller 的错误切换率、p99 I/O latency 与 GPU stall。
- **后续工作 2**：把 CPU core-seconds、GPU SM-seconds、功耗和端到端 SLO 纳入同一目标函数，比较固定 CPU-only、固定 GPU-only 和 adaptive policy 的整机成本。
- **后续工作 3**：在 2–8 GPU、跨 socket 和共享 SSD 的拓扑上测吞吐、公平性与 CPU poller scaling，验证单 GPU 结论能否外推。
- **后续工作 4**：注入 CPUAgent failure、SSD reset、GPU kernel cancellation 和 CID wraparound，检查每个 barrier waiter 是否被正确完成或显式报错。

## 相关

- **相关概念**：[[GPU-Direct-Storage]]、[[Asynchronous-IO]]、[[NVMe]]、[[PCIe]]、[[GPU-Memory-Tiering]]
- **同类系统**：[[BaM]]、[[AGILE]]、[[GoFS]]、[[GeminiFS]]
- **同会议**：[[OSDI-2026]]
