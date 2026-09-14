---
type: paper
name: NEMO
full_title: Finding NEMO: Nimble and Expressive Memory Observability
authors: [Shihang Li, Matthew Giordano, Tushar Garg, Rohan Kadekodi, Daniel S. Berger, Baris Kasikci, Thomas Anderson, Simon Peter]
venue: OSDI
year: 2026
tags: [memory-observability, cxl, tiered-memory, memory-controller, telemetry]
source_pdf: "[[osdi26-li-shihang.pdf]]"
source_md: "[[osdi26-li-shihang]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-02-13
---

# 面向异构内存的灵活遥测引擎（OSDI 2026）

> **原题**：Finding NEMO: Nimble and Expressive Memory Observability

> **一句话总结**：现有内存观测要么覆盖率和及时性不足、要么由固定硬件语义限制；NEMO 把可配置的 match-update-notify 管线和 SRAM 状态放入内存控制器，在 FPGA CXL 原型上用接近全覆盖的计数把 HeMem 热集切换恢复加速 5×、MEMTIS 大页拆分检测加速至多 10.4×，并以约 0.09% CPU 开销完成噪声邻居检测。

## 问题与动机

CXL-attached memory、NUMA 和多级内存让同一地址空间中的访问延迟、带宽和迁移收益差异变大。内核需要知道哪些页热、一个 hugepage 内部是否访问倾斜、哪个租户占用了带宽。错误或过时的观测会直接导致迁移、拆页和隔离策略失效。

软件方案（页表扫描、软缺页、PEBS 采样）较灵活，但在覆盖率、及时性和 CPU 开销之间存在硬约束。硬件计数器则能低成本观察完整流量，却通常只能提供 socket、channel 或进程级的固定聚合，无法随 OS 策略变化。NEMO 的目标是在内存控制器旁路增加一个小型遥测引擎，让 OS 自己定义过滤、地址映射、聚合和读后清零规则。

## 关键观察 / 隐含假设

- **观察 1：采样会把短时间窗口内的访问倾斜压扁。** HeMem 使用默认 0.02% PEBS 采样率时，热集切换后的收敛时间为 324 s；NEMO 为 67 s（图 3、图 4）。
  - **依赖假设**：内存控制器能看到目标层的请求元数据，并拥有足够 SRAM 保存策略需要的状态。
  - **可能失效场景**：原型只覆盖 CXL 内存，快速 DRAM 层仍需 PEBS；若生产控制器无法旁路观察预取或非时间性访问，收益会缩小。
- **观察 2：固定功能硬件的低开销来自牺牲策略灵活性。** NEMO 以 mask-shift-add 地址变换和有限的交换、结合更新操作，支持按页、子页或租户聚合。
  - **证据强度**：强。三个用例共享同一管线，只改变过滤器、translation、更新和通知配置（§3、§5）。
- **假设 1：单次、固定周期、结合且可交换的更新足以覆盖主要观测策略。** 这支持各内存控制器局部更新并在驱动中任意顺序归并。
  - **证据强度**：强；论文明确承认方差、精确 top-K 等需要跨状态或历史的遥测无法直接表达（§3.3）。
- **假设 2：通过时间复用可接受 SRAM 不足带来的扫描延迟。** MEMTIS 每 500 ms 重编程 112 个 hugepages，16 GiB 上完整扫描约 37 s（§6.1）。
  - **可能失效场景**：内存扩大到 TiB 级、访问模式变化更快或页迁移策略要求毫秒级反馈时，扫描窗口可能成为新的瓶颈。

## 核心方法

NEMO 在每个 memory controller 增加旁路 telemetry pipeline。请求头同时广播给多个管线，原始读写仍沿数据路径执行，因此遥测不会给 cache hit 或 DRAM/CXL 访问增加数据路径延迟（图 1）。

每条管线由三阶段组成。match 阶段从物理地址提取 primary region key，查 translation table 得到状态基址，再用 secondary mask/shift 计算子区域偏移。update 阶段对一个 SRAM 状态执行加法、位运算等固定操作。notify 阶段可对更新后的状态做阈值判断。驱动负责分配 pipeline 和状态 bank、维护地址到状态的映射、跨控制器归并结果，并提供轮询和读后清零接口（图 2、表 1）。

该抽象能自然表达三类策略：按 hugepage 计数以支持 HeMem 热集迁移；把一个 2 MiB hugepage 映射到 512 个 4 KiB counter 以支持 MEMTIS 的页内倾斜检测；把同一租户的多个 hugepage 映射到一个 counter 以统计带宽。所有局部结果可用更新操作对应的结合规则合并。

## 设计取舍

- **旁路管线换取可部署性**：NEMO 不修改 cache 和主数据通路，但只能使用请求地址、读写类型等元数据，无法直接表达需要多次计算或跨多个状态的复杂指标。
- **SRAM 换取全覆盖**：状态放在控制器 SRAM，避免每次更新额外访问 DRAM；代价是可同时追踪的区域数受限，需要时间复用。原型每条管线约 150 KiB，最大 MEMTIS 配置使用 8 条管线、约 1.2 MiB 遥测 SRAM（§4）。
- **受限更新换取线速处理**：结合且可交换的单步更新便于跨 MC 归并，也排除了精确 top-K、方差等任务。论文提出链式管线和 count-min sketch 作为扩展方向（§6.3）。
- **原型完整性仍有限**：通知机制在 FPGA 原型中未真正实现，而是由 CPU 每 1 ms 轮询模拟（§4）；遥测状态读取也尚未完全流水化。

## 实验与结果

- 在 Intel Xeon Gold 6430 + FPGA CXL 2.0 Type-3 原型上，主机 DRAM 为 114.1 ns、114.9 GiB/s，CXL DRAM 为 380.3 ns、16.4 GiB/s（§4）。
- FlexKVS 热集完全切换后，HeMem-NEMO 67 s 恢复稳态，HeMem-PEBS 324 s；NEMO CPU 开销 0.89%，应用吞吐最高提升 1.69×（图 3、图 4）。
- 在 FASTER KV 上，较大 value 使预取流量增多，PEBS 无法观察部分 DRAM 访问；NEMO 仍能识别页级热集并获得吞吐优势（图 5）。
- 在 MEMTIS + Silo 上，NEMO 找到的 skewed hugepages 超过 PEBS 的 2×；在 fast:slow = 1:8 时吞吐比 PEBS 基线高 13%，页拆分候选检测约 150 s，最高获得 10.4× 检测加速（图 6、图 7）。MEMTIS-NEMO CPU 开销约 3%，其中 NEMO 处理占 1.67%。
- 在 noisy-neighbor 实验中，NEMO 和 MBM 的带宽测量均与应用层 ground truth 相差不超过 0.1%。NEMO 以 0.09% CPU 开销达到与 1 ms MBM 轮询近似的隔离效果；MBM 该配置开销约 32%（图 8、图 9）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| NEMO 能以低 CPU 开销提供及时的热集信号 | HeMem-NEMO 67 s 对比 PEBS 324 s，CPU 0.89%（图 3–4） | FlexKVS；仅 CXL 层由 NEMO 覆盖 | 强 |
| 页内细粒度计数改善 hugepage 拆分 | 候选数超过 2×，检测最高加速 10.4%，1:8 时吞吐高 13%（图 6–7） | Silo、16 GiB CXL、MEMTIS 时间复用 | 中 |
| NEMO 可精确统计租户带宽并降低控制开销 | 误差不超过 0.1%，CPU 0.09%，对比 MBM 1 ms 轮询约 32%（图 8–9） | 单个合成 noisy neighbor，cgroups 控制，通知由轮询模拟 | 中 |
| 管线抽象可覆盖多种 OS 观测策略 | 三个用例分别使用一对一、一对多和多对一地址映射（§3、§5） | 仅验证加法计数及有限操作，未验证复杂遥测 | 中 |

## 批判性分析

### 论证链条

论文的主要链条是闭合的：采样和固定计数器的限制导致策略信号失真；控制器旁路管线能逐请求更新；逐请求信号改善三个已有 OS 策略。实验分别覆盖及时性、空间粒度和租户归因。不过，“适用于现代服务器内存层次”仍是从 CXL FPGA 原型外推的结论。快速 DRAM、真实 IMC、多个控制器和虚拟机环境没有被端到端验证。

### 假设压力测试

NEMO 的全覆盖只对控制器可见的流量成立。原型的 NEMO 仅观察 CXL 内存，快速层仍依赖 PEBS；因此混合层级中的完整性并非由 NEMO 单独保证。时间复用的 37 s 扫描周期也可能无法跟上高 churn 工作负载。另一方面，噪声邻居实验中最终 p99 影响受 cgroups 约 10 ms 执行延迟限制，无法证明硬件通知本身能把 SLO 反应时间降到毫秒以下。

### 实验可信度

基线包含 PEBS 和 Intel MBM，且报告采样率、轮询频率、CPU 开销、吞吐、延迟和测量误差。YCSB、Zipf、FlexKVS、FASTER KV 和 Silo 覆盖了几类典型内存服务。限制在于工作负载数量较少，CXL 容量只有 16 GiB，噪声邻居只有单租户对。通知在原型中被软件轮询替代，削弱了对硬件 notify 阶段的直接验证。

### 系统性缺陷

控制器 SRAM 的容量和 pipeline 数量成为共享资源，需要驱动处理分配、回收、跨控制器一致性和租户权限。论文描述了特权配置、地址范围校验和虚拟化接口，但没有评估恶意或频繁重编程带来的控制面开销。标准内存映射读取要求驱动处理 cache 失效；状态读取尚未完全流水化。故障恢复、遥测状态持久性、热插拔 CXL 设备和长期运维成本也未讨论。

## 局限与后续工作

- **局限 1**：硬件原型只覆盖 CXL-attached DRAM，不能单独支撑全系统多层内存的覆盖率结论。
- **局限 2**：notify 阶段在原型中未实现，实验用 1 ms CPU 轮询模拟；应在真实控制器中测量中断聚合、风暴抑制和端到端反应时间。
- **局限 3**：大内存依赖时间复用。应在 256 GiB、1 TiB 和多租户生产 trace 上测量 sweep time 对策略收益的影响。
- **后续工作 1**：实现链式 pipeline 或 count-min sketch，比较 SRAM、误差和更新吞吐，验证 NEMO 能否覆盖 top-K、频率估计等超出单计数器的任务。
- **后续工作 2**：在真实 IMC 和多 socket 拓扑上验证跨控制器归并、快速层观测、虚拟机隔离与 CXL 热插拔。

## 相关

- **相关概念**：[[Tiered-Memory]]、[[CXL]]、[[Transparent-Hugepage]]、[[Memory-Bandwidth-Monitoring]]
- **同类系统**：[[HeMem]]、[[MEMTIS]]、[[NeoMem]]、[[M5]]
- **同会议**：[[OSDI-2026]]
