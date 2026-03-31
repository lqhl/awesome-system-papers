# To PRI or Not To PRI, That's the question

**作者**：Yun Wang, Zhixiang Wei, Zhibai Huang, Kailiang Xu, Zhengwei Qi（上海交通大学）；Liang Chen, Jie Ji, Xianting Tian, Ben Luo, Kaihuan Peng, Kaijie Guo, Ning Luo, Guangjian Wang, Shengdong Dai, Yibin Shen, Jiesheng Wu（Alibaba Group）
**会议**：OSDI 2025（19th USENIX Symposium on Operating Systems Design and Implementation）
**DOI**：https://www.usenix.org/conference/osdi25/presentation/wang-yun
**源文件**：[osdi25-wang-yun.pdf](../../papers/osdi-2025/osdi25-wang-yun.pdf)

---

## 一、背景

云计算环境中，高性能 I/O 是支撑大规模业务的关键。SR-IOV（Single Root I/O Virtualization）与 I/O 设备直通（device passthrough）是当前主流方案，通过将物理 NIC/存储设备的 Virtual Functions 直接分配给 VM，可实现接近裸机的 I/O 性能。然而，直通模式存在一个根本性约束：设备的 DMA 操作无法处理 I/O Page Fault（IOPF），因此 hypervisor 必须将 VM 分配的物理内存静态 pin 住，禁止换出或被 overcommit。

这与云服务提供商（CSP）的核心商业模式冲突。CSP 高度依赖内存超量订阅（oversubscription）来提升资源利用率、降低成本。Alibaba 生产环境统计显示：在 300 节点集群中，超过 80% 的长期运行（≥1年）legacy VM 持有约 800GB 内存，其中约 34% 是可回收的 cold pages——但因为 passthrough 模式的内存 pin 约束，这些内存无法被回收。

PCI-SIG 早在 2009 年就引入了 Page Request Interface（PRI）来解决 IOPF 问题，但直到 2023 年 Intel Sapphire Rapids 才在 IOMMU 层面提供支持，而主流 NIC/存储设备（高端 GPU 除外）至今大多不支持 PRI。此外，Linux（v6.12）对 PRI 的支持仅限于特定 PASID+SVA 场景，硬件兼容性极为有限。

---

## 二、要解决的问题

**问题一：PRI 不适用于生产环境的高性能场景。**
PRI 将 IOPF 处理置于 I/O 关键路径中：设备通过 PCIe 向 IOMMU 发送 Page Request，IOMMU 写入 PRQ Event Queue 触发中断，OS 内存子系统处理后回应——整个流程引入 3×～80× 于 CPU page fault 的延迟。更严重的是，现代 NIC 设备遇到 IOPF 时会丢包，上层协议（TCP/RDMA）的重传会导致几百毫秒的级联延迟，远超 IOPF 本身的延迟。

**问题二：现有软件方案性能差或需要修改 Guest OS。**
vIOMMU、coIOMMU、IOGuard 等软件方案要么性能损耗大（coIOMMU 只能达到原生 passthrough 的 60.5%），要么需要修改 VM 的前端驱动。而在拥有数十万长期运行 legacy VM 的云环境中，修改 Guest OS 根本不可行。

**问题三：IOPS 分布长尾，大多数 VM 不需要高 IOPS。**
生产数据显示，73.14% 的 VM IOPS 低于 1,000，只有不到 3.57% 的 VM 需要超过 30,000 IOPS。这意味着大多数情况下可以容忍少量的 I/O 路径软件开销，只需在高 IOPS 压力时切换回 passthrough 模式。

---

## 三、核心设计

VIO（Virtual I/O）是一个基于 VirtIO 标准的软件弹性设备直通框架，完全在 Host Hypervisor 侧实现，对 Guest OS 和底层硬件透明。三个核心机制：

**1. IOPA-Snoop（I/O Page Access Snooping）**
VIO 拦截 VirtIO 前端驱动发出的 kick 通知，在将 I/O 请求真正传递给硬件设备之前，主动检查 DMA buffer 中所有页面是否映射（通过查询 EPT/Extended Page Table）。若存在未映射页面，则在 Host 侧提前触发 page fault 并完成映射，再 kick 硬件。这将 IOPF 处理从 I/O 关键路径移出，设备侧永远不会遇到 IOPF。

**2. IOPS-Aware 弹性直通（Elastic Passthrough）**
为应对高 IOPS 场景，VIO 引入了一个 Shadow Available Ring。在 VIO（Snooping）模式下，IOMMU 指向 Shadow Available Ring，IOPA-Snoop 线程处理完页面后将请求写入真正的 Available Ring 并 kick 设备；在 Passthrough 模式下，IOMMU 直接指向原始 Available Ring，VM 的 kick 直接到达硬件，不经过 VIO。模式切换通过修改 IOMMU 的页表指针实现，对 VM 完全透明，耗时约 10µs。IOPS 监控触发切换决策：IOPS 低时用 Snooping 模式支持内存回收，IOPS 高时切 Passthrough 保障性能 SLO。同时，Shadow Ring 机制还支持不停机的 VMM 热升级（live upgrade）。

**3. Adaptive Lockpage（自适应锁页）**
I/O 操作具有强时间局部性，反复访问的热点页频繁经历 IOPF-Snoop 开销代价大。VIO 受 Linux Dual-LRU / Multi-generational LRU 启发，维护 Active List 和 Inactive List：
- IOPA-Snoop 探测到页访问时，将页移入 Active List 并 unpin（避免过度 pin）
- Active List 满时，将 LRU 尾部页移入 Inactive List 并 **pin** 住（防止被 reclaim）
- 静态 Lockpage：对 VirtIO RX Queue（连续物理内存预分配）直接整块锁定
- Lockpage Bitmap 以 2MB 粒度管理，IOPA-Snoop 前先查 Bitmap 跳过 pin 检查（节省约 1µs）

---

## 四、实现细节

- **实现规模**：在 Linux 内核 Hypervisor 层实现，修改 QEMU/KVM，支持 x86（AMD 和 Intel）平台
- **VirtIO 覆盖**：支持 virtio-net 和 virtio-blk；通过拦截 NVMe doorbell 寄存器写操作，VIO 概念已扩展到 NVMe 协议
- **硬件前提**：需要支持 VirtIO Offload 的 DPU（如 Intel IPU、NVIDIA BlueField），论文中使用内部 DPU，最高 200Gb/s 带宽，支持 2300 个 VF
- **Guest 无需修改**：一台运行 CentOS 5（内核 2.6.18，已有10年历史）的 legacy VM 可以零修改迁移到 VIO
- **锁页粒度**：2MB 大页粒度管理 Lockpage Bitmap，P50 锁页率 1%，P90 为 10%，P99 达 79%（主要因 Windows VirtIO 驱动 I/O 局部性差）
- **模式切换延迟**：Shadow Ring 机制切换耗时约 10µs，对应用透明

---

## 五、实验结果

**实验环境**

| 组件 | 配置 |
|------|------|
| Host CPU | Intel Xeon Platinum 8269CY, 52C/104T, 2 socket |
| Host DRAM | 12×16GB, 1TB SSD |
| DPU | PCIe GEN3 8 lanes, 最大 200Gb/s, 2300 VF |
| VM | 4 vCPU, 8GB RAM, CentOS 7.9, virtio-net |

基线：VPRI（SOSP'24）——在 DPU 上实现硬件 PRI 的 state-of-the-art 方案

**IOPA-Snoop 延迟分布**

| 情形 | 平均延迟 |
|------|---------|
| Lockpage Hit（Bitmap 命中） | ~3.5µs（Bitmap 查询 90ns） |
| Lockpage Miss（需查 PTE） | ~4.5µs |
| Page Fault（页不在内存中） | ~700µs |

**VIO vs VPRI 吞吐对比（注入 IOPF，Snooping 模式）**

| 应用 | VPRI 吞吐下降（10ms 延迟） | VIO 吞吐下降（10ms 延迟） |
|------|---------------------------|--------------------------|
| iperf TCP | ~50%+ | <10% |
| Nginx | ~45% | <10% |
| Redis | ~60% | ~6% |
| Memcached | ~57% | ~6% |

**Ablation Study（netperf TCP_RR）**

| 模式 | 相对性能 |
|------|---------|
| coIOMMU | 60.5% |
| VIO Snooping（无 Lockpage） | 87.0% |
| VIO Snooping（有 Lockpage） | 90.0% |
| VIO Passthrough | 100% |

**生产数据（300K VM 部署，1年+）**
- 30% 内存超量订阅下，1小时 YCSB Redis 追踪：1,464,225 次独立页访问，仅发生 1 次 IOPF
- IOPFs 降至 CPU Page Fault 的 <1%
- 每日可回收约 120GB（相当于 30K 台 2C/4GB VM 的内存）
- VMM 热升级期间网络带宽抖动极小，用户零投诉

---

## 六、批判性分析

**基线选择的局限性**
论文选择 VPRI（SOSP'24）作为唯一基线，理由是市面上没有支持 PRI 的商用 NIC，只能用 VPRI（DPU 内实现软硬件协同 PRI）。然而，这一基线并不公平：VPRI 本身是高端 DPU 加速方案，其 IOPF 处理仍走 PCIe 关键路径；而 VIO 完全绕过了 IOPF 发生本身。真正的公平对比应包括：纯 VirtIO（无直通，全软件）、原始 Passthrough、以及带有良好 IOPF 处理的 PRI 硬件实现（如 Intel SPR 平台上的原生 PRI）。论文在注释中承认了这一点（"in this case, to demonstrate the worst-case performance of VIO, we used snooping mode for comparison"），但将此作为主要对比结果呈现，显得略有偷换概念之嫌。

**高 IOPS 场景下 Snooping 的实际瓶颈被低估**
论文展示了 Elastic Passthrough 的必要性（Snooping 模式在高 IOPS 时相比 Passthrough 性能下降 10%），但未详细分析 IOPS 切换阈值的设定方法、切换抖动对应用的影响，以及切换期间 in-flight I/O 的处理。10µs 的切换延迟在 RDMA/高频金融场景下可能是问题。

**Lockpage 的 Windows VM 问题未解决**
论文发现 P99 锁页率高达 79%（因 Windows VirtIO 驱动局部性差），但给出的结论是"在生产中使用静态锁页以便于维护"，并未解决根本问题。Windows VM 是云上重要的工作负载，这一 70%+ 的锁页率可能严重削弱内存回收的收益。

**生产数据的代表性问题**
"300K VM 每日回收 120GB"这一数字是在什么样的内存超量订阅比例下取得的？论文中提到 30% 超量订阅，但生产环境的实际比例未明确。此外，"相当于 30K VM" 的换算方式（按 2C/4GB）过于乐观——实际高价值 VM 通常配置更多内存，回收收益会相应缩减。

**VirtIO 依赖是根本约束**
VIO 要求 Guest VM 使用 VirtIO 驱动，以及 Host 侧有支持 VirtIO Offload 的 DPU。在已有大量 legacy SR-IOV 直通方案（vendor-specific VF 驱动）的环境中，迁移成本不可忽视。此外，VirtIO 1.1（Packed Queue）的支持被列为 future work，当前实现基于 VirtIO 1.0，性能上限受限。

---

## 七、AI Infra / MLSys 视角

**与 AI 系统的关联**
论文开篇即提及大语言模型（LLM）是对高性能 I/O 有强需求的云负载之一。当前 AI 训练/推理集群大量使用 SR-IOV RDMA NIC（InfiniBand/RoCE）以及 NVMe SSD，VIO 的问题场景直接适用于 GPU 训练 VM 的内存管理。

**可借鉴的 insight**
1. **IOPF 从关键路径移出的通用思路**：在 AI 训练中，梯度通信（AllReduce）和模型参数加载都依赖高吞吐 RDMA，任何 I/O 抖动都可能导致 step time 上升。VIO 将 page fault 处理异步化的思想，可用于 GPU 显存管理（Unified Virtual Memory 中的 prefetch 策略优化）。
2. **基于访问模式的自适应锁页**：AI 训练的 Activation/KV Cache 具有极强的阶段性时间局部性（forward pass 固定访问模式），VIO 的 Adaptive Lockpage 可迁移为 GPU HBM 与 Host DRAM 之间的智能 pinning 策略。
3. **弹性直通的负载感知切换**：LLM 推理的 prefill 和 decode 阶段 IOPS 特性差异显著，类似的 IOPS-aware mode switching 可应用于推理系统中的 KV Cache 卸载（offloading）策略。

**潜在延伸方向**
- 将 VIO 的 Shadow Ring + Elastic Passthrough 扩展到 GPU Direct Storage 场景，支持 GPU-to-NVMe 的 DMA 路径上的内存超量订阅
- 探索在 disaggregated memory 架构（如 CXL 内存池）中，利用类似 IOPA-Snoop 的机制处理远端内存访问 fault，减少 fault 处理对 GPU Kernel 执行的影响

---

## 八、总结

VIO 提出了一种务实的云端 I/O 设备直通内存管理方案：通过在 VirtIO 数据平面中插入 IOPA-Snoop 主动预处理 DMA 页，结合 IOPS 感知的弹性 passthrough 切换和自适应锁页机制，在不修改 Guest OS、不依赖 PRI 硬件的前提下，实现了接近原生 passthrough 的性能，并支持内存超量订阅。该方案已在阿里云 300K 规模 VM 生产环境中部署超过一年，每日可节省相当于 30K VM 的内存。主要局限在于依赖 VirtIO 和 DPU 支持、Windows VM 锁页率偏高、以及弹性切换阈值调优未充分讨论。
