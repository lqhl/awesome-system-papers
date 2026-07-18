---
type: paper
name: Cylon
full_title: "Cylon: Fast and Accurate Full-System Emulation of CXL-SSDs"
authors: [Dongha Yoon, Hansen Idden, Jinshu Liu, Berkay Inceisci, Sam H. Noh, Huaicheng Li]
venue: FAST
year: 2026
tags: [cxl-ssd, full-system-emulation, femu, kvm, caching, virtualization]
source_pdf: "[[fast2026-yoon.pdf]]"
source_md: "[[fast2026-yoon]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# Cylon: Fast and Accurate Full-System Emulation of CXL-SSDs (FAST 2026)

> **一句话总结**：观察到 [[CXL]]-SSD 的 hit/miss 呈亚微秒 vs 数十微秒双峰延迟，而 QEMU upstream [[CXL]] 把所有访问都走 MMIO/VM-exit（~15 µs），根本无法做 policy 研究；Cylon 在 [[FEMU]]+QEMU/KVM 上用 Dynamic EPT Remapping 让 cache hit 直映 EPTE 零 VM-exit（~150 ns）、miss 才陷入 [[FEMU]] NAND 时序（~40 µs），对 Samsung CMM-H 校准后 Redis/GAPBS 趋势一致，并可插拔 eviction/prefetch 与 app-level cooperative caching。

## 问题与动机

[[CXL]]-SSD（如 Samsung CMM-H）把小型 DRAM cache 与大容量 NAND 通过 [[CXL.mem]] 暴露为 byte-addressable memory tier：cache hit 亚微秒、miss 落 NAND 数十微秒。这类设备有望打破 memory/storage 边界，支撑 DAX、near-data execution、弹性内存池等新抽象。但设计空间仍极开放——tens-of-µs miss 在全栈软件里如何放大成端到端 stall、何种 cache/prefetch policy 在混合局部性下有效、硬件与 OS/app 如何协同——都缺乏可系统探索的开放平台。

现有工具各缺一角：

- **商用 prototype**（CMM-H）：firmware 黑盒，eviction/prefetch knob 极少，难做 policy 或 controller 改造。
- **OpenCXD（FPGA）**：能跑功能实验但不建模 NAND 时序与带宽。
- **Trace-driven simulator**（MQSim-CXL、ESF）：可配置但极慢，无法与 unmodified OS/app 动态交互，且未对真机校准。
- **Cycle-accurate simulator**（CXL-SSD-Sim、CXL-DMSim / gem5）：设备精度高但慢到只能缩 workload。
- **QEMU upstream [[CXL]]**：能 boot unmodified guest，但所有访问走 MMIO→VM-exit，单访问 ~15 µs，比真实 cache hit 慢两个数量级，且完全不建模 DRAM cache 与 NAND 内部。

作者 claim：需要同时满足 **(1) full-stack execution**、**(2) near bare-metal 速度**、**(3) validated device fidelity**、**(4) extensible policy/co-design** 的平台。Cylon 是第一个在 [[FEMU]] 上实现上述四点的 full-system [[CXL]]-SSD emulator。

## 关键观察 / 隐含假设

- **观察 1**：[[CXL]]-SSD 性能本质是 **双峰延迟分布**——DRAM cache hit 数百纳秒、NAND miss 数十微秒；端到端研究必须能同时保留 fast path 与 slow path，而不是把所有访问统一放慢。
  - **证据**：CMM-H 上 MIO pointer chasing 在 WSS 低于/高于 48 GB cache 时分别稳定在 ns 级与 µs 级；Cylon 复现相同 capacity transition（Figure 4–5）。
  - **依赖假设**：设备以 hardware-managed DRAM write-back cache 暴露全容量；guest 用普通 load/store，不经 block I/O。
  - **可能失效场景**：host-managed FTL、[[CXL]]-NVMe 混合语义、或 coherence-heavy 共享内存设计时，双峰模型需重写。

- **观察 2**：在 QEMU/KVM 上仿真 sub-µs hit，**VM-exit 是硬瓶颈**——MMIO 路径把每次 guest load 膨胀到 ~15 µs，完全掩盖真实 hit latency。
  - **证据**：QEMU-CXL 在 MIO 8 GB WSS 下 CDF 单峰于 10–20 µs（avg 14.6 µs），无亚微秒分量；Cylon 同配置双峰，hit avg 977 ns（Figure 3）。MLC 隔离路径开销：100% hit 时 Cylon 0.16 µs vs QEMU 14.74 µs（Figure 2）。
  - **依赖假设**：实验 host 使用 Intel EPT + KVM；guest vCPU pinned 到与 cache 不同 NUMA 节点以模拟 remote-NUMA hit（~150 ns）。
  - **可能失效场景**：AMD NPT / ARM Stage-2 虽论文声称可映射，但未实测；非 KVM 虚拟化或嵌套虚拟化下 DER 开销未知。

- **观察 3**：Cache policy 收益 **强烈依赖 workload 局部性**，在 random 访问下任何 eviction 都塌缩到 ~24% 命中率。
  - **证据**：Cylon 上 Seq/Stride 下 S3FIFO 可达 99% hit，Rand 下 FIFO/LIFO/CLOCK/S3FIFO 均 ~24.3% hit、>100M misses（Table 3）；Redis Zipfian 下 LIFO 优于 FIFO（Figure 11）。
  - **依赖假设**：研究目标是 in-device DRAM cache policy，而非 CPU cache 或 SSD-internal FTL/GC；working set 可用 normalized WSS/cache-size 比较不同容量设备。
  - **可能失效场景**：生产 trace 局部性介于 microbenchmark 与纯随机之间；多租户共享设备、写密集或 GC 干扰会改变 policy 排序。

- **观察 4**：CMM-H 等 FPGA prototype 的 **controller 开销** 会抬高 hit latency、提前压低带宽，与「理想架构行为」可分离。
  - **证据**：CMM-H hit ~800 ns、带宽在 cache 未满时即下降；Cylon hit ~150 ns（remote NUMA DRAM），在 cache 饱和前维持 32 GB/s，但 qualitative DRAM→NAND 转折与 CMM-H 一致（Figure 6–7、9）。
  - **依赖假设**：Cylon 刻意建模 intended architectural behavior，而非逐周期复刻黑盒 firmware；用 CMM-H 作 ground truth 校 trend 而非绝对数值。
  - **证据强度**：**中**——Redis/GAPBS 趋势对齐，但 Cylon miss 路径常比 CMM-H 更慢（Figure 5），作者归因于 prototype 内部 prefetch/metadata。
  - **可能失效场景**：下一代 ASIC CXL-SSD 若 hit 接近本地 DRAM、或并行度远高于 4 thread，Cylon 的「理想化 hit path」可能高估性能。

- **假设 1**：Host DRAM 作 [[FEMU]] backend + 预配置 NAND 时序足以支撑 **policy 与全栈行为** 研究，multi-TB 容量不是首轮验证必需。
  - **证据强度**：**中**——read 40 µs / write 200 µs / erase 2000 µs 来自 datasheet 与 [[FEMU]] 验证模型，GC 干扰随 FTL 状态变化；但 emulated capacity 受 host DRAM 限制（当前 96 GB），SPDK NVMe backend 标为 ongoing。

## 核心方法

Cylon 在三个域协作：**unmodified guest VM**、**轻改 Linux KVM**、**host userspace QEMU/[[FEMU]]**。对 guest，设备是标准 [[CXL]] 2.0 Type-3（DAX 或 CPU-less NUMA）；可见容量等于 backend SSD，DRAM cache 由设备透明管理——无需改 guest driver。

### Hybrid access path

Guest load/store 经 EPT 翻译：

- **Cache hit（fast path）**：EPTE 处于 **Direct**——指向 DRAM cache 的 HPA，RW + Write-Back，guest 原生指令完成，**零 VM-exit**。
- **Cache miss（slow path）**：EPTE 处于 **Trap**（R=W=X=0）→ EPT violation → KVM → QEMU [[CXL]] ct3d → [[FEMU]] FTL 线程模拟 NAND（channel/die/plane 并行、R/P/E 延迟、GC 干扰）→ fill cache → EPTE 改 Direct + INVEPT。

Eviction：clean 直接 Trap；dirty 先 writeback 到 [[FEMU]] 再 Trap。该路径直接回应 **观察 1、2**：保留双峰延迟，避免 QEMU 式「全慢路径」。

### Dynamic EPT Remapping (DER)

核心是用 EPTE 权限位在 Direct/Trap 间切换，而非 MMIO 陷 hypervisor。安全约束：VM 创建时注册两段不可变 GPA range（cache 区、SSD 区）；KVM ioctl 只允许改 PFN selector 与 R/W/X；per-EPTE lock 串行化并发 eviction/prefetch。TLB 失效用 INVEPT/INVVPID，并 **批量/按 range** 摊销——prefetch burst 时合并 shootdown；invalidation 严格在 miss path，相对 40 µs NAND fetch 可忽略。设计可映射到 AMD NPT / ARM Stage-2（论文声称，未评测）。

### Shared EPT Memory

VM init 时预分配连续 leaf EPTE 表，映射到 kernel 与 QEMU/[[FEMU]] 共享内存。FEMU 用 LPN（SSD 逻辑页号）**O(1)** 索引更新 EPTE，发 `<index, state, cookie>` 描述符而非每次 ioctl syscall——把 Cylon-I（ioctl 路径，miss 开销 23.04 µs）降到 Cylon-S（16.27 µs，NAND=0 时）。同时暴露 EPTE 数组给 guest，支撑 app 观测 cache residency。

### Configurable caching & observability

插件式 **eviction**（FIFO、LIFO、CLOCK、[[S3-FIFO]] 等）与 **prefetch**（next-N line）。Hit 对 emulator 不可见，故用两条观测路径：(1) 周期清 EPT accessed bit + Linux DAMON；(2) 可选 Intel PEBS 采样（1/1000 开销可接受）。回应 **观察 3**，把 Cylon 从「复现 CMM-H」升级为 policy 实验台。

### Application-level interface

共享内存 ring queue + 薄用户库（亦可 ioctl fallback），支持 prefetch/pin/evict、动态选 policy、查统计——类比 OpenChannel-SSD 的 host-managed FTL 思路，探索 **cooperative caching**（DB 预取 join 表、图计算 pin frontier、ML 预取 mini-batch）。

### Extensibility beyond CMM-H

模块化 backend 可换 [[FEMU]] 参数或未来 SPDK NVMe，探索 CXL–NVMe 一体化（NVMe-oC）、CXL–FTL 直通暴露 NAND 并行、低延迟 flash 等。实现：~6,282 LOC [[FEMU]] v8.0.0 + ~1,261 LOC Linux v6.4.6；已 upstream MoatLab/FEMU。

## 设计取舍

- **取舍 1：DER 改 hypervisor vs 纯 QEMU 设备模型**。侵入 KVM EPT 与 memslot（`KVM_MEMSLOT_DUAL_MODE`），换 nanosecond hit 与可分析 miss path；代价是 kernel patch、Intel EPT 为主路径验证、运维需定制内核。
- **取舍 2：理想化 hit latency vs 设备绝对 fidelity**。Hit 由 host remote-NUMA DRAM（~150 ns）决定，低于 CMM-H FPGA hit（~800 ns）；换更干净的 policy ablation，牺牲对特定 prototype 微观延迟的逐点匹配。
- **取舍 3：Host DRAM backend vs 真实容量**。Backend 数据放 host DRAM 换速度与实现简单，容量受 host 内存限制；架构上可换 SPDK NVMe（ongoing），但当前 evaluation 最大 96 GB NAND。
- **取舍 4：Hardware-managed cache 透明性 vs host-managed 探索**。默认隐藏 cache、guest 无感，与 CMM-H 一致；app API 可选开启 cooperative 控制，但论文未系统评测 security/isolation。
- **边界条件**：在 Intel KVM + [[FEMU]] + 单设备、读偏重或图/Redis 类 workload 上最优雅；多设备 fabric、强 coherence、写密集 sync 持久化、或需精确复刻特定 vendor firmware 时变脆。

## 实验与结果

**Host**：双路 Xeon Gold 6242、384 GB DDR4；guest Ubuntu 22.04、8 vCPU、96 GB DRAM；Cylon 配置 96 GB [[CXL]] DAX、4.8 GB DRAM cache、96 GB NAND（read 40 µs / write 200 µs / erase 2000 µs）。**Validation**：Samsung CMM-H（48 GB cache + 1 TB）于 Xeon 6710E + DDR5。

- **路径开销（MLC，NAND=0）**：100% hit — Cylon 0.16 µs vs QEMU 14.74 µs；0% hit — Cylon-S 16.27 µs vs Cylon-I 23.04 µs（Shared EPT 省 ~7 µs syscall/walk）。
- **延迟分布（MIO 8 GB WSS，FIFO）**：Cylon 双峰 hit avg 977 ns + µs 级 miss；QEMU 单峰 avg 14.6 µs（Figure 3）。
- **带宽（MLC，WSS/cache 归一化）**：Cylon 在 4.8 GB cache 内维持 ~32 GB/s remote-NUMA 带宽，饱和后降至 NAND 吞吐；CMM-H 更早掉带宽（opaque controller）；超 cache 后两者收敛（Figure 6）。
- **Redis YCSB-C（1 KB record）**：小 WSS（0.33×）Cylon hit 更快；中 WSS（1.06×）双峰混合；大 WSS（2.10×）两者 CDF 重叠于 NAND-bound（Figure 7）。
- **GAPBS Betweenness（kron）**：小图 Cylon 略快于 CMM-H（更低 hit latency）；大图两者趋同（NAND miss 主导）（Figure 9）。
- **Policy sweep**：Seq/Stride 下 S3FIFO + next-8 prefetch 可把 latency 压到 sub-10 µs 区间；Rand prefetch 无增益；Redis 12.8 GB footprint 下 LIFO 优于 FIFO/CLOCK/S3FIFO（Figure 8、10–11）。
- **Scalability**：4 thread 饱和，与 CMM-H 设备并行度一致，非 host TLB shootdown 瓶颈。

## Critical Analysis

### 论证链条

链条为 **现有平台三角缺陷（慢/无全栈/无 device 模型）→ CXL-SSD 双峰延迟是核心现象 → DER+Shared EPT 分别消除 hit VM-exit 与 miss 更新开销 → [[FEMU]] 提供状态相关 NAND 时序 → CMM-H 校准 micro+macro trend → 可插拔 policy/app API 证明 extensibility**。在「Intel KVM full-system + Samsung CMM-H 类 hardware-managed cache」设定下逻辑闭合较好；Figure 2–3 对 QEMU 的对比直接支撑「无 DER 则 claim 不成立」。

薄弱跳步：(1) Table 1 中 MQSim-CXL、ESF、gem5 系工具 **未做同条件端到端对比**，extensibility 相对 trace/simulator 的优势主要靠定性定位；(2) Cylon 对 CMM-H 是 **qualitative trend match**，hit 更快、miss 有时更慢，作者用「idealized baseline」解释，读者若关心绝对延迟误差需自行换算；(3) app-level cooperative caching **几乎无定量实验**，更多是设计愿景；(4) multi-TB SPDK backend 标为 future，「explore next-gen architectures」在容量维度尚未实证。

### 假设压力测试

- **虚拟化栈绑定**：DER 深度依赖 Intel EPT + 定制 KVM；AMD/ARM 仅架构性讨论，云主机常见嵌套虚拟化或不同 hypervisor 时路径未验证。
- **Hit latency 不可配**：当前 hit 由 host NUMA 拓扑决定（~150 ns），无法注入 800 ns 级 FPGA 延迟；policy 比较结论可能对「过快 hit」敏感，低估 miss 占比小时 controller 微观效应。
- **Backend 容量与持久性**：Host DRAM backend 限制 scale-up study（TB 级 working set、GC 长期行为）；crash 后数据语义继承 [[FEMU]]/VM 配置，论文未讨论与真实 CXL 持久性/ordering 的差异。
- **Observability 开销**：PEBS/DAMON 对 hit 统计有效，但高采样率下是否改变 cache 行为（尤其 prefetch burst 与 EPTE 翻转）未系统量化。
- **工作负载外推**：Redis/GAPBS + MIO/MLC 以读与指针 chasing 为主；写密集、[[CXL]] 内存语义与 storage 语义混合（bytefs、checkpoint）、多租户干扰未覆盖。

### 实验可信度

- **Benchmark 代表性**：Micro（MLC/MIO）精准刻画双峰延迟与 policy；macro（Redis/GAPBS）覆盖 KV 与图 analytics，对「memory-tier expansion」研究有代表性，但对 OLTP 写路径、文件系统 on DAX、ML training checkpoint 代表性弱。
- **Baseline 公平性**：QEMU-CXL 是唯一可跑 unmodified guest 的开源 full-system 对照，对比公平且对 Cylon 有利；与 trace-driven / gem5 工具缺少同等 full-stack 数字，不宜直接得出「全面优于所有 prior work」的量化结论。
- **Ablation**：Cylon-I vs Cylon-S 清晰分解 Shared EPT；policy/prefetch sweep 充分；缺少 DER off（全 MMIO）、无 batch INVEPT、无 [[FEMU]] GC 等组件级 ablation。
- **Metric 覆盖**：带宽、延迟 CDF、应用完成时间、hit rate 覆盖较好；**能耗、多 VM 共 host 干扰、故障注入、正确性（dirty eviction ordering）、app API 延迟开销** 论文未讨论或仅一笔带过。

### 系统性缺陷

- **部署成本**：需打补丁的 Linux 6.4.6 + 定制 [[FEMU]] + 固定 NUMA 拓扑（cache 在 node 1、vCPU 在 node 0），对非 VT 实验室复现有门槛；论文未讨论容器化或多实验并行时的资源隔离。
- **尾延迟与 MSHR 压力**：§4.4 理论分析 MSHR 填满会放大 miss，但实验以均值/CDF 为主，缺少高并发 core 下 tail stall 与 MSHR 饱和的专门测量。
- **安全与多租户**：Shared EPT 让用户态 [[FEMU]] 写 EPTE 描述符，KVM 校验 PFN 范围；但恶意 guest 通过 alias、侧信道或 API 滥用 prefetch 的影响 **论文未讨论**。
- **可观测性运维**：Policy 实验依赖 hit 统计间接推断，生产级 debug（哪层 miss：cache vs FTL vs GC）工具链未成型。
- **设备并行度假设**：4 thread 饱和归因于设备，暗示实验规模上限；更大并行度下 DER batch invalidation 与 [[FEMU]] 锁竞争可能重新成为瓶颈——论文未外推。

## 局限与 Future Work

- **局限 1**：Backend 当前用 host DRAM，emulated capacity 受 host 内存限制；SPDK NVMe backend 仍在进行。
- **局限 2**：Cache hit latency 不可独立配置，与 CMM-H 等 prototype 的绝对 hit 延迟有系统偏差。
- **局限 3**：App-level cooperative caching 接口已实现，但缺乏与 hardware-managed policy 对比的系统性 macrobenchmark。
- **局限 4**：主要验证 Intel KVM + Samsung CMM-H；其他 vendor CXL-SSD 与 non-KVM 环境未评测。
- **Future work 1**：在 SPDK 多 TB backend 上复现 Redis/GAPBS，测量容量缩放时 GC 干扰与 policy 稳定性是否仍与 microbenchmark 一致。
- **Future work 2**：为 hit path 增加可校准 delay injection，对比「理想 150 ns」与「FPGA 800 ns」下 eviction/prefetch 结论是否翻转。
- **Future work 3**：在写密集 + fsync 工作负载上测量 dirty eviction writeback 与 [[FEMU]] GC 叠加对端到端 tail latency 的影响，填补 persistence 语义空白。
- **Future work 4**：对 app API 做 DB/graph/ML 真实 cooperative caching case study，并量化 API 命令相对 miss penalty 的开销比。

## 相关

- **相关概念**：[[CXL]]、[[FEMU]]、[[S3-FIFO]]、[[KV-Cache]]、EPT、KVM、DAMON
- **同类系统**：QEMU-CXL、MQSim-CXL、CXL-SSD-Sim、CXL-DMSim、OpenCXD、[[NVMeVirt]]
- **同会议**：[[FAST-2026]]
- **对比**：Cylon 填补「full-system + near bare-metal + validated CXL-SSD device model」空白；相对 trace-driven 工具补动态 OS/app 交互，相对 QEMU-CXL 补双峰延迟与可配 cache policy
