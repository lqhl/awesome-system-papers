# Selective On-Device Execution of Data-Dependent Read I/Os

**作者**：Chanyoung Park, Minu Chung, Hyungon Moon（UNIST, Ulsan National Institute of Science and Technology）
**会议**：FAST 2025（23rd USENIX Conference on File and Storage Technologies）
**链接**：https://www.usenix.org/conference/fast25/presentation/park
**源文件**：[fast2025-park.pdf](../../papers/fast-2025/fast2025-park.pdf)

---

## 一、背景

随着数据量增长，存储设备越来越远离主处理器（CPU），即使是本地存储也通常通过 PCIe 连接，其往返延迟达到微秒级别。近存储计算（near-storage computing）因其在性能、能效和可扩展性方面的优势而受到关注。已有研究如 λ-IO、Insider 等利用存储设备内部的高带宽优势，将数据密集型计算卸载到设备侧以减少数据传输量。另一方向，XRP 和 BypassD 则利用低延迟存储设备的特性，将计算放置在主机软件栈的最底层（设备驱动层）来加速 I/O。

现代低延迟存储（如 Intel Optane）使得软件栈延迟的占比显著增大。例如，使用 NVM 设备时，软件层延迟占总延迟的 48–53%。这催生了绕过软件栈、将计算推向更靠近存储介质的需求。XRP 提出的 **resubmission**（重提交）模式——即根据前一次读取结果决定下一次读取地址的 data-dependent read I/O 模式——在遍历 on-disk 数据结构（如 B+-tree）时尤为常见。

---

## 二、要解决的问题

**核心问题**：on-device 计算资源能否加速 data-dependent read I/O？

现有工作的局限：

1. **吞吐量导向的 in-storage computing**（如 λ-IO、Insider）专注于减少数据传输量的场景（如 grep），不适用于 data-dependent read 场景，因为后者的数据传输量与计算时间相当。
2. **XRP** 将 resubmission task 放在 host kernel 的设备驱动层执行，但仍需经过完整的 NVMe 请求处理流程，存在微秒级的驱动层开销。
3. **设备侧处理器算力有限**（频率低、功耗受限），单纯将 resubmission task 卸载到设备可能因计算延迟增加而抵消数据访问延迟的优势。
4. **商用计算存储设备**（如 Samsung SmartSSD）的 FPGA 通过 PCIe 连接设备内部存储，并未真正减少访问延迟。

---

## 三、洞察与设计

**关键洞察**：on-device resubmission 的收益取决于两个约束条件——(1) resubmission task 必须足够轻量，设备侧处理器能快速完成；(2) 处理器必须在设备内部（同一 SoC），紧邻存储介质。当设备侧资源充裕时，on-device 执行可以同时避免 PCIe 往返延迟和 NVMe 驱动层处理开销；当设备侧繁忙时，回退到 in-kernel 路径反而更优。

基于此洞察，作者设计了 **SODE**（Selective On-Device Execution），一种自适应混合执行机制，包含三个核心设计：

### D1: Hybrid Resubmission（混合重提交）
SODE 的 on-device 路径作为 in-kernel 路径的辅助资源。收到 NVMe SODE command 后，on-device runtime 判断设备侧处理器是否空闲：空闲则在设备侧执行；否则通过 **Reverse-Offloading（R-Offloading）** 将任务回退到 host kernel 的 in-kernel 路径。这避免了设备侧排队导致的尾延迟恶化。

### D2: Optimistic Resubmission with Cached Metadata（乐观重提交）
Resubmission task 需要文件系统元数据（如 ext4 extent status tree）将文件偏移转换为逻辑块地址。SODE 在请求发起时缓存一份元数据副本发送到设备，乐观地执行整条 resubmission chain，仅在链完成时校验元数据是否变化。这基于目标文件（read-only）几乎不更新的假设，避免了每次 resubmission 都需 PCIe 往返获取最新元数据。

### D3: Parallel Resubmission Tasks（并行重提交）
由于设备侧处理器频率低，单个 resubmission task 的执行时间会增加（如 WiredTiger 从 1867ns 增至 4403ns）。SODE 允许将 resubmission task 拆分为多个并行的 eBPF filter，每个实例处理数据块的一部分来查找下一次读取地址。对 WiredTiger，4 路并行将设备侧 resubmission 延迟从 4403ns 降至 993ns。

---

## 四、实现细节

SODE 基于 **NVMeVirt**（软件 NVMe 设备模拟器）实现，模拟 Intel Optane DC SSD 的延迟特性。

- **Resubmission 线程**：在 NVMeVirt 中新增 4 个 resubmission 线程，与原有的 dispatcher 和 I/O 线程交互。I/O 线程完成读请求后将结果转发给 resubmission 线程，后者执行 eBPF filter 并决定是否发起后续读请求。
- **Wimpy 处理器模拟**：将 Xeon 处理器频率降至 1.2GHz 模拟 ARM Cortex-A53 级别的低功耗处理器。通过与真实 Zynq ZCU102（4 核 Cortex-A53 @ 1.2GHz）对比验证了模拟的合理性（get 操作延迟分别为 6.85µs vs 6.70µs）。
- **eBPF 沙箱**：复用 XRP 的 BPF verifier 和 JIT 编译。在执行 resubmission task 前后通过 **MPK**（Memory Protection Key）的 WRPKRU/RDPKRU 指令切换内存访问权限，实现硬件级沙箱隔离。
- **Extent 缓存**：每次 `read_sode` 调用时复制完整 extent tree（实践中 < 2KB），随 NVMe SODE command 发送到设备。完成时通过版本号校验一致性。
- **WiredTiger 适配**：修改 40 行 eBPF resubmission task 代码实现并行化，另修改 70 行 WiredTiger 代码在页面头部未使用位中传递子任务的查找范围。
- **新系统调用**：`read_sode` 和 `read_sode_parallel`，分别用于串行和并行 resubmission。
- **代码开源**：https://github.com/cssl-unist/sode

---

## 五、实验结果

**实验环境**：Intel Xeon Gold 6136 × 2（NUMA），Ubuntu 18.04，Linux 5.12.0。Node 0 用于 host（3.0GHz），Node 1 用于 NVMeVirt + resubmission（1.2GHz）。

### BPF-KV（简单 B+-tree KV store）

| 指标 | SODE vs read | SODE vs XRP |
|------|-------------|-------------|
| 吞吐量（depth 6） | +55.3–121.5% | +16.4–38.5% |
| 最大吞吐量提升 | — | **+41%**（单线程） |
| 99th 尾延迟 | -11.6–37.5% | 显著降低 |
| 99.9th 尾延迟 | -8.2–30.1% | 显著降低 |

- Index depth = 1 时收益消失（resubmission 次数太少）。
- Open-loop 负载下，SODE 峰值吞吐量比 XRP 高约 10.5%；仅用 on-device 路径的变体吞吐量反而低于 XRP，验证了混合执行的必要性。

### WiredTiger + YCSB

| 指标 | 结果 |
|------|------|
| 吞吐量提升（vs XRP，geomean） | **+5.46%** |
| 99th 尾延迟降低（vs XRP） | **最多 3.85%** |
| Resubmission 系统调用延迟降低 | 最多 9.4% |
| On-device/In-kernel 分配（3 线程，workload C） | 69% / 31% |

- 不使用并行 resubmission 时，SODE 吞吐量比 read 低 54%；启用 4 路并行后比 read 高 19%。
- 随着 cache size 增大或 Zipfian 常数增大（更偏斜），收益递减。
- Workload D 因 on-disk tree 深度低，resubmission 仅占搜索时间的 3%，收益不明显。

---

## 六、批判性分析

1. **基于模拟器而非真实硬件**：SODE 的全部评估基于 NVMeVirt 模拟器，将 Xeon 降频到 1.2GHz 来模拟 wimpy 处理器。尽管与 ARM Cortex-A53 在微基准测试上延迟接近，但真实 SSD 控制器的内存层次、中断处理、固件开销等完全不同。频率降低不等于架构模拟，cache 大小、pipeline 深度、内存带宽等差异被完全忽略。

2. **WiredTiger 上的收益偏小**：在 WiredTiger（唯一的"真实应用"）上，吞吐量提升 geomean 仅 5.46%，尾延迟降低最多 3.85%。考虑到引入了新的系统调用、内核修改、设备固件扩展、元数据缓存/校验等复杂性，这个收益的工程价值存疑。

3. **元数据一致性的乐观假设**：论文假设目标文件是 read-only 的，实验中从未观察到版本号不匹配。但论文没有评估一旦发生 abort 的性能惩罚——整条 resubmission chain 作废并重新执行，在长链场景下代价可能很高。作者在 Discussion 中承认了这一点但没有量化。

4. **单设备评估**：所有实验仅使用单个（模拟的）存储设备。论文承认 SODE 无法处理文件跨设备分布的情况（如 RAID），但即使在单机多盘的常见配置下的行为也未评估。

5. **On-device 资源的竞争**：论文假设 4 个核心专用于 resubmission，不考虑 SSD 固件自身的维护任务（GC、wear leveling）对这些核心的竞争。Discussion 中提到了但未量化。

6. **Baseline 选择**：未能与 SPDK 对比（因 NVMeVirt 不支持）。SPDK 完全绕过内核的方式可能提供更好的延迟，是一个重要的缺失 baseline。

7. **Resubmission chain 长度有限**：WiredTiger 中 30% 的请求仅 resubmit 2 次，深度分布集中在 2-5 次。这意味着 SODE 的核心优势场景（深 resubmission chain）在实际 KV store workload 中并不占主导。

---

## 七、总结

SODE 提出了一种选择性地在存储设备内部执行 data-dependent read I/O 的 resubmission task 的机制，通过混合 on-device 和 in-kernel 执行路径、乐观元数据缓存、并行 resubmission 三个设计来平衡设备侧低访问延迟与有限算力之间的矛盾。在 BPF-KV 上最高提升 41% 吞吐量，在 WiredTiger 上平均提升 5.46% 吞吐量。主要局限在于全部基于模拟器评估、真实应用收益有限、以及对 read-only 文件和专用核心的强假设。这是首个探索 on-device 计算加速 data-dependent read I/O 的研究，其核心贡献在于明确了 on-device 执行的适用条件和局限性。
