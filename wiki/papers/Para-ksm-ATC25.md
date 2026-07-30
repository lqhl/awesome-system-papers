---
type: paper
name: Para-ksm
full_title: "Para-ksm: Parallelized Memory Deduplication with Data Streaming Accelerator"
authors: [Houxiang Ji, Minho Kim, Seonmu Oh, Daehoon Kim, Nam Sung Kim]
venue: ATC
year: 2025
tags: [memory-deduplication, ksm, dsa, accelerator-offload, datacenter-tax]
source_pdf: "[[atc2025-ji.pdf]]"
source_md: "[[atc2025-ji]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-30
---

# Para-ksm：使用数据流加速器的并行内存重复数据删除（ATC 2025）

> **原题**：Para-ksm: Parallelized Memory Deduplication with Data Streaming Accelerator

> **一句话总结**：观察到 DSA 单次卸载 memcmp/xxhash 的 PCIe 往返延迟是瓶颈、而 vanilla [[KSM]] 串行结构无法 batch 后，Para-ksm 将候选页搜索/插入解耦并重写为 256 页 batch 提交，使每 CPU cycle 去重量比 CPU-ksm 高 31–50%，协同应用退化从 1.6–5.8× 降至 1.3–2.7×。

## 问题与动机

服务器内存占硬件成本 30–50%，而 [[Virtualization]]（VM / container）下重复页可占 11–86% 容量。[[KSM]]（Kernel Same-page Merging）是 Linux 上广泛采用的 content-based 内存去重，Meta 等 hyperscaler 已用于降低 Instagram worker 等场景的内存压力。但 ksm 带来显著的 **datacenter tax**：与 Redis 同核运行时 CPU 利用率上升 14–65%，协同应用性能退化 1.6–5.8×；其中 `memcmp` 与 `xxhash` 两个数据面函数合计占 ksm CPU 周期的 38%，并把冷页拉入 cache 造成污染。

Intel 4 代及以后 Xeon 集成片上 **Data Streaming Accelerator ([[DSA]])**，可通过 on-chip PCIe 以 cache-bypass 方式执行 page comparison 与 CRC checksum，且支持虚拟地址（无需 memory pinning）。直接替换为 DSA-ksm 能把协同应用退化降到 1.0–1.6×，但去重率显著低于 CPU-ksm——根因是单次卸载延迟比 CPU 长 2.6–2.7×，而 vanilla ksm 的 RB 树搜索必须串行（上一比较结果决定下一 tree page），无法利用 DSA 的 batch descriptor 能力。Para-ksm 的核心 claim 是：**不只要 offload，还要重写 ksm 算法以匹配加速器 batch 语义**。

## 关键观察 / 隐含假设

- **观察 1**：ksm 的数据面瓶颈是 `memcmp`/`xxhash` 的 CPU 周期与 cache pollution，而非控制面逻辑。
  - **依赖假设**：去重扫描以 4 KB 页为单位、每轮需对大量页做全页比较或 checksum；协同 workload 对 LLC 争用敏感（如 Redis p99）。
  - **可能失效场景**：页粒度更大（2 MB THP）、去重主要发生在 file-backed 而非 anonymous 区域、或 CPU 已足够空闲时 cache pollution 代价变小。

- **观察 2**：DSA 异步卸载单页时，PCIe 提交/完成往返（~6 µs）主导延迟，比 CPU 慢 2.6–2.7×；batch size=8 可将平均每 WD 延迟降低 81–83%。
  - **依赖假设**：DSA 使用 asynchronous mode + 固定 sleep 后 poll completion；数据面操作粒度为 4 KB；on-chip DSA 优于片外 [[RDMA]] SmartNIC（STYX 测得 xxhash 17 µs vs DSA 6 µs）。
  - **可能失效场景**：未来 DSA 延迟下降、或 workload 中 tree 深度极浅导致 batch 收益有限；多 socket / NUMA 下 on-chip 路径延迟特性可能不同（论文未测）。

- **观察 3**：vanilla ksm 的两处串行根因是 (B1) 单候选页选择与插入触发 RB 树 rebalance、(B2) 有序二分搜索要求比较结果决定下一方向；二者使 DSA-ksm 只能逐 WD 提交。
  - **依赖假设**：stable/unstable 两棵 RB 树按页内容字典序组织；正确性要求遍历路径与 CPU-ksm 一致；RB 树性质 P1（rebalance 不改变 predecessor/successor）与 P2（候选页分组不重叠）可用于延迟插入。
  - **可能失效场景**：树规模极大时 batch 内 comparison skewness 严重（batch>512 时 BD 利用率 <60%）；或页内容分布使搜索深度差异过大，batch 摊销失效。

- **假设 1**：部署环境为 Intel Xeon 4 代+、单 DSA group（1×64-entry WQ、4 PE）、Linux 6.2.15 定制内核；去重目标为 `madvise` 标记的 anonymous 区域。
  - **证据强度**：强——全部实验与 artifact 均在此硬件/软件栈上完成；无其他平台数据。

- **假设 2**：为公平比较，CPU-ksm 与 Para-ksmC 通过调 `pages_to_scan` 等参数使 **memory saving 可比**，再衡量性能与效率。
  - **证据强度**：中——保证「同等去重效果下的 tax」对比合理，但可能掩盖「最大去重速度」或「默认 sysctl 配置」下的真实运维权衡。

## 核心方法

**DSA-ksm（直接 offload baseline）**：在内核空间用 IDXD 驱动实现 DSA-based `memcmp`（Comparison opcode）与 `xxhash`（CRC Generation opcode），异步提交后 sleep 让出 CPU，唤醒后读 completion record。利用 DSA 虚拟地址支持，避免 STYX 式 pinning 与地址翻译；约 300 LoC 内核改动。

**Para-ksmC（主方案）**：将 ksm 从「逐页搜索-插入」改为两阶段 batch 流水线，回应观察 3 与 DSA batch 能力：

1. **候选页 batching**：从 advised region 取 N=256 个连续候选页（不足则立即处理剩余页），为每页维护 `search_result`（候选页地址 + predecessor/successor 指针）。
2. **并行 tree search**：同一层所有候选页 vs 当前 tree page 打包为一个 batch descriptor（BD）提交 DSA；根据比较结果更新各页下一层 tree page 与 predecessor/successor，保持与 CPU-ksm 相同遍历路径以保证正确性。
3. **延迟插入**：全部搜索完成后，按 predecessor 地址 hash 分组；组内多页用 CPU `memcmp` 排序、合并重复页入 stable tree，再按 P1/P2 依次插入 unstable tree 并 rebalance。

**Para-ksmT（舍弃）**：对单候选页 speculative 比对接下来 M 层共 2^M−1 个 tree page，仅 M 次比较有用，去重率仅为 CPU-ksm 的 9.2%，因浪费 DSA 算力未采用。

与 STYX（片外 SmartNIC + RDMA）、Catalyst（GPU）等同为 kernel function offloading，但 Para-ksm 强调 **算法-加速器协同设计**：batch 语义驱动 ksm 重构，而非仅替换函数实现。实现细节与伪代码见 [[atc2025-ji]] / [[atc2025-ji.pdf]]。

## 设计取舍

- **去重效率 vs 协同应用性能**：Para-ksmC 的 deduplication efficiency 比 CPU-ksm 高 31–50%，但平均性能退化 2.1×，高于 DSA-ksm 的 1.3×——因组内排序、successor 更新、hash 分组等控制面仍占 CPU（ksm CPU 利用率 31% vs DSA-ksm 7.3%）。换取的是与 CPU-ksm 可比的 memory saving 与远高于 DSA-ksm 的短期去重速度。
- **正确性优先的 batching vs speculative 并行**：Para-ksmC 保持原 RB 树搜索路径；Para-ksmT 用 speculative 多 tree page 比较换延迟，但 DSA 资源浪费 87%+（M=6 时额外 2% DRAM 带宽）。在 DSA PE 稀缺前提下选择前者。
- **搜索/插入解耦 vs 实现复杂度**：延迟插入避免 batch 内 rebalance 互相干扰，但引入 comparison skewness（批内各页比较次数不均）和更大内核状态机；batch size 256 是效率峰值与 BD 利用率的折中（>256 后 DSA 处理能力与 skewness 双瓶颈）。
- **边界条件**：在 duplicate 率高、树搜索深度适中、VM 密集部署且 ksm 扫描积极时收益最大；单页延迟敏感且可接受较低去重率时 DSA-ksm 更优；无 DSA 或旧代 Xeon 上无法部署。

## 实验与结果

- **平台**：Intel Xeon 8460Y+（40 核，HT 关，2.0 GHz）、8×32 GB DDR5、1 DSA group（64-entry WQ，4 PE）；40 VM 各 1 vCPU / 6 GB，Liblinear / Graph500 / Redis+YCSB 协同 ksm。
- **协同应用退化**（相对 no-ksm）：CPU-ksm 平均 3.3×（Redis YCSB 3.7×）；DSA-ksm 1.3×、STYX 1.4×、Para-ksmC 2.1×。Para-ksmC 比 CPU-ksm 降低退化 1.6×，但劣于 DSA-ksm。
- **CPU 占用**：CPU-ksm 平均占 server CPU 48.2%；DSA-ksm/STYX ~5.5–7.3%；Para-ksmC 31.0%。
- **Cache**：相对 CPU-ksm，DSA-ksm LLC miss rate 降 28%，Para-ksmC 降 18%（控制面仍触页）。
- **去重效果**：DSA-ksm 前 20 s 仅达 CPU-ksm memory saving 的 12%；Para-ksmC 100 s 内低约 20%，最终差距 <1%。
- **去重效率**（memory saving per 1K CPU cycles，相对 CPU-ksm）：DSA-ksm 5–65%；Para-ksmC **1.3–1.5×**。
- **微基准**：DSA-a vs CPU-t 节省 memcmp/xxhash CPU 周期 6.6×/6.0×；batch size 8 延迟降 81%/83%。

## 批判性分析

### 论证链条

作者链条清晰：profile ksm → 识别 38% 数据面开销 → DSA offload 降 CPU tax 但降去重率 → 归因 PCIe 往返 + 串行算法 → batch 摊销 + Para-ksmC 重构 → 效率超 CPU-ksm 且 saving 趋同。薄弱环节在于 **性能 claim 与效率 claim 不完全同向**：最高去重效率伴随比 DSA-ksm 更差的协同应用退化，论文用「可调 pages_to_scan 使 saving 可比」统一口径，但未展示「固定 ksm 扫描强度、谁更快达到目标 saving」的运维视角。

### 假设压力测试

- **Workload**：Liblinear/Graph500/Redis 代表计算与 KVS，但非 Meta 生产 trace；Redis 用 CAT 隔离 LLC，真实混部可能更糟。
- **硬件**：单 socket、单 DSA group；多 socket ksm 与 DSA WQ 争用、NUMA 远程页访问论文未讨论。
- **规模**：40 VM / 6 GB 远小于 hyperscale 节点；RB 树规模增大时 comparison skewness 与插入 hash 开销可能非线性上升（Figure 9 已示 batch>512 利用率 <60%）。
- **安全/隔离**：[[Copy-on-Write]] 去重侧信道与跨 VM 信息泄露论文未讨论（KSM 领域已知顾虑）。

### 实验可信度

- Baseline 较强：含同作者 STYX（ATC'23）、CPU-ksm、no-ksm；并复现 SmartNIC 方案。
- 公平性：主动调参使 memory saving 对齐，适合比「tax per saved byte」，但不代表默认 ksmtuned 行为。
- Ablation：batch size（16–1024）、Para-ksmT 负结果、async vs sync DSA 有支撑；缺少「仅 batch 不改插入算法」的分解实验。
- Metrics 覆盖 throughput（saving）、efficiency、CPU%、LLC miss、p99（Redis），但未测恢复/正确性回归、ksmd 与 DSA 故障时的行为。

### 系统性缺陷

- **尾延迟与干扰**：Redis 报 p99，但 ksm 扫描与 DSA 中断/唤醒模式对长期 tail 的影响仅部分覆盖；固定 sleep 后 poll 的策略对延迟方差的影响未量化。
- **可观测性与运维**：需定制内核（artifact: linux-paraksm）；与主线 kernel 合并成本、升级路径论文未讨论。
- **资源隔离**：DSA 4 PE 与多 tenant 共享时的 QoS（WQ priority）在去重场景下的配置指南缺失。
- **故障恢复**：DSA 完成超时、descriptor 失败时 ksm 回退策略论文未讨论。

## 局限与后续工作

- **局限 1**：Para-ksmC 协同应用退化仍达 1.3–2.7×，高于 DSA-ksm，hyperscaler 若优先保护 SLA 可能仍倾向「低开销、慢去重」而非「高效率、中等开销」。
- **局限 2**：仅评估 Para-ksmC；Para-ksmT 与组内 CPU memcmp 的替代方案（如更大 DSA 或组内也 offload）未充分探索。
- **局限 3**：评估窗口 160–200 s，长期运行下 tree 膨胀、skewness 恶化、内存碎片化对 batch 效率的影响未知。
- **Future work 1**：在 **生产级 container/VM 混部 trace** 上测量「达到 X% memory saving 所需时间与 p99 代价」的 Pareto 曲线，验证 observation 2 的 batch 收益是否随树规模衰减。
- **Future work 2**：将 Para-ksm 的 batch 搜索/延迟插入与 UPM/CMD 等 **减少无效比较** 的软件 hint 叠加，测量能否在保持 DSA-ksm 级低 CPU% 的同时恢复 Para-ksmC 效率。
- **Future work 3**：多 socket 上 DSA WQ 分区 + NUMA-local 候选页 batch 的调度策略；需测量 remote page 访问对 BD 摊销的侵蚀。

## 相关

- **相关概念**：[[Memory-Deduplication]]、[[DSA]]、[[On-Chip-Accelerator]]、[[Datacenter-Tax]]、[[Copy-on-Write]]、[[Virtualization]]、[[RDMA]]
- **同类系统**：[[STYX]]（SmartNIC offload ksm）、Catalyst（GPU）、PageForge（近内存控制器）；同会议 [[DSA-2LM-ATC25]] 亦用 DSA 做内核数据面 offload
- **同会议**：[[ATC-2025]]
- **对比**：Para-ksm 相对 DSA-ksm 用更高 CPU 换去重吞吐；相对 STYX 用更低延迟 on-chip 路径换更少 kernel 改动（~300 vs ~1300 LoC）
