# To PRI or Not To PRI, That's the Question

**作者**：Yun Wang, Liang Chen, Jie Ji, Xianting Tian, Ben Luo, Zhixiang Wei, Zhibai Huang, Kailiang Xu, Kaihuan Peng, Kaijie Guo, Ning Luo, Guangjian Wang, Shengdong Dai, Yibin Shen, Jiesheng Wu, Zhengwei Qi（上海交通大学、阿里巴巴集团）
**会议**：OSDI 2025
**链接**：https://www.usenix.org/conference/osdi25/presentation/wang-yun
**源文件**：[osdi25-wang-yun.pdf](../../papers/osdi-2025/osdi25-wang-yun.pdf)

---

## 一、背景

云计算环境中，设备直通（Device Passthrough）结合 SR-IOV 技术可以让 VM 直接访问硬件 I/O 设备，获得接近裸机的性能。然而，直通模式要求将 VM 的物理内存静态 pin 住，因为 DMA 可能访问任意 Guest Physical Address，若目标页面被 swap out，将导致 I/O Page Fault (IOPF)，而大多数设备无法处理此类故障，可能引发系统崩溃。

PCI-SIG 在 2009 年提出了 Page Request Interface (PRI) 来解决这一问题，允许设备通过 IOMMU 向 OS 请求页面映射。但 PRI 的硬件支持迟迟未普及——直到 2023 年 Intel Sapphire Rapids 才在 IOMMU 中支持 PRI，且主流 NIC 和存储设备（除高端 GPU 外）基本不支持 PRI。Linux 内核（v6.12）也仅在 IOMMU_INTEL_SVA + PASID 场景下支持 PRI。

在生产环境中，云服务商依赖内存超售（oversubscription）来提高资源利用率。静态 pin 住 VM 内存使得超售无法实施，造成巨大的资源浪费。在一个 300 节点的生产集群中，超过 80% 的长期运行 legacy VM 占用约 800GB 内存，其中约 34%（~270GB）为冷页面。

---

## 二、要解决的问题

1. **PRI 硬件兼容性差**：主流 NIC 和存储设备不支持 PRI，大量 legacy VM（运行超过一年、内核不支持 PRI）无法通过硬件升级获益。大规模迁移在技术和经济上均不可行。

2. **PRI 性能开销大**：PRI 将 IOPF 处理放在 I/O 关键路径上，通过 PCIe 总线进行 fault handling，延迟是 CPU page fault 的 3x~80x。设备收到 IOPF 时通常丢包，依赖 TCP/RDMA 重传，导致数百毫秒的延迟放大（约为 IOPF 本身延迟的 100 倍）。

3. **现有软件方案不实用**：vIOMMU、coIOMMU 需要修改 guest 内核的前端驱动，引入显著性能开销；IOGuard 需要独占一个 CPU 核心；Hyperupcall 需要 eBPF 工具链修改——这些在多租户云环境中都不可行。

4. **缺乏对动态 IOPS 的适应能力**：现有方案未考虑 workload 的 IOPS 动态变化。生产数据显示 73.14% 的 VM IOPS 低于 1,000，仅 3.57% 超过 30,000 IOPS，存在明显的长尾分布特征。

---

## 三、洞察与设计

**关键洞察**：在云生产环境中，绝大多数 VM（>96%）的 IOPS 需求很低，此时 IOPF 的关键路径处理带来的延迟开销远大于收益；而 VirtIO 的数据平面提供了一个天然的"拦截点"——通过在 VirtIO 的 available ring 上实施 snooping，可以在 DMA 发起之前就确保所有目标页面已驻留在内存中，从而将 IOPF 处理从 I/O 关键路径中完全移除。

基于这一洞察，VIO 的设计包含三个核心机制：

### 1. IOPA-Snoop（I/O Page Access Snooping）

VIO 在 VirtIO 的 virtqueue 上引入一个 shadow index 机制：
- 前端驱动写入 available ring 后，设备看到的是 shadow index（尚未更新），不会立即消费新请求
- IOPA-Snoop 模块检测到 index 更新后，检查 buffer 中所有页面的 EPT 映射状态
- 若页面被 swap out，在此时完成 page fault 处理（从 swap 读入）
- 处理完成后更新 shadow available index，设备才开始 DMA 操作

这样，整个 IOPF 处理在 hypervisor 侧完成，设备和 guest 均无感知。

### 2. IOPS-Aware Elastic Passthrough

根据实时 IOPS 压力动态切换工作模式：
- **低 IOPS**（<100k）：运行 snooping 模式，每次 I/O 约 4µs 开销，但可回收冷内存
- **高 IOPS**（>100k）：切换到直通模式，绕过 snooping 开销，获得裸机性能

模式切换通过 shadow available ring 实现：
- Passthrough → Snooping：unmap EPT 中的 available ring → 复制到 shadow ring（~10µs）→ 原子重映射 IOMMU IOPT
- Snooping → Passthrough：先并行 swap in 缺失页面 → 重映射 shadow ring 回原始 native ring

### 3. Adaptive Lockpage

借鉴 Linux 的 Dual LRU / Multi-generational LRU 思想：
- 维护 Active List 和 Inactive List
- IOPA-snoop 检测到页面访问时，移入 Active List 并 unpin
- Active List 满时，最近最少使用的页面被淘汰到 Inactive List 并 pin 住
- 被 pin 的页面无需在后续 snooping 中检查 PTE，减少 overhead
- 另有 Static Lockpage 策略，用于 VirtIO RX queue 等预分配连续内存区域

---

## 四、实现细节

- **平台**：基于 Linux/KVM + QEMU，部署在 x86 平台（Intel 和 AMD 均支持）
- **VirtIO 标准**：遵循 VirtIO 1.0 standard，未来计划支持 VirtIO 1.1 的 Packed virtqueue
- **Shadow Available Ring**：通过 IOMMU IOPT 重映射实现设备和驱动对 available ring 的分离访问，切换时间约 10µs
- **Lockpage Bitmap**：以 2MB 粒度管理锁定页面，VIO 维护内部表，对 bitmap 中的页面跳过 PTE 检查（仅需 90ns 查询）
- **IOPA-Snoop 延迟**：lockpage hit 时 3.5µs，miss 时 4.5µs，page fault 时平均 700µs
- **VMM Live Upgrade**：利用 Orthus 的双 KVM 方案，对 legacy VM 进行在线升级，无需重启 VM。QEMU 通过 fork-exec 模型加载新镜像，升级窗口约 200ms
- **NVMe 扩展**：已将 IOPA-Snoop 扩展到 NVMe 协议，通过拦截 doorbell register write 实现
- **兼容性**：支持 Linux、BSD、Windows guest，已验证最古老的 CentOS 5（kernel 2.6.18）

---

## 五、实验结果

### 实验环境

| 组件 | 配置 |
|------|------|
| Host | Intel Xeon Platinum 8269CY, 52C/104T @ 2.50GHz, 2 sockets, 192GB DRAM, 1TB SSD |
| DPU | PCIe Gen3 x8, 最多 2300 VFs, 200Gb/s 带宽 |
| VM | 4 vCPUs, 8GB RAM, CentOS 7.9, dual-queue virtio-net, 10Gb/s |

### 基线对比（VPRI vs VIO，snooping 模式，注入不同频率和延迟的 IOPF）

| 应用 | VPRI 10ms 延迟下的吞吐下降 | VIO 10ms 延迟下的吞吐下降 |
|------|---------------------------|--------------------------|
| Redis | ~60% | ~6% |
| Nginx | ~45% | ~9% |
| Memcached | ~57% | ~6% |
| iperf TCP | 显著波动 | 接近 10Gb/s 稳定 |

### IOPA-Snoop 微基准

| 场景 | 延迟 |
|------|------|
| Lockpage hit | 3.5µs |
| Lockpage miss | 4.5µs |
| Page fault | ~700µs |
| 平均 | ~4µs |

### Ablation Study（netperf TCP_RR）

| 模式 | 性能（万事务/秒） | 相对 passthrough |
|------|------------------|-----------------|
| coIOMMU | 60.5 万 | 60.5% |
| VIO Snooping w/o lockpage | 87.0 万 | 87.0% |
| VIO Snooping w/ lockpage | 90.0 万 | 90.0% |
| VIO Passthrough | 100.0 万 | 100% |

### 生产环境数据

- **部署规模**：300K+ VMs，运行超过一年
- **每日内存回收**：等价于 30K VM 的内存（约 120GB/天/300节点集群）
- **IOPF 率**：在 30% 内存超售下，一小时内 1,464,225 次唯一页面访问仅触发 1 次 IOPF
- **日常 IOPF**：降至 CPU Page Fault 的 1% 以下
- **Lockpage 率**：P50=1%, P90=10%, P99=79%（P99 高主要因为 Windows VirtIO 驱动的 I/O 局部性差）
- **VMM 升级影响**：iperf 峰值带宽下仅 200ms 波动窗口

---

## 六、批判性分析

1. **基线公平性存疑**：与 VPRI 的对比中，VIO 使用 snooping 模式（即使论文说明高 IOPS 时应切换到 passthrough），这使得对比场景对 VIO 不利，但同时也意味着实际生产中 VIO 的高 IOPS 表现就是 passthrough 本身——等于在高 IOPS 场景下 VIO 没有解决 IOPF 问题，而是回避了它。

2. **Elastic Passthrough 的实际价值未充分验证**：论文声称 elastic passthrough 带来每日 10% 的内存节省，但缺乏与静态策略（如始终 snooping 或始终 passthrough + balloon）的直接对比实验。"30K VM equivalent daily savings" 这个数字缺少清晰的计算过程。

3. **snooping 开销在中等 IOPS 下被低估**：论文重点讨论了低 IOPS（snooping 开销可忽略）和高 IOPS（切换到 passthrough）两个极端。但对于 IOPS 在 10k-100k 的中间区间，snooping 的累积开销（4µs × 50k = 200ms/s，即 20% 的时间在 snooping）可能显著影响性能，论文未给出这个区间的详细数据。

4. **Windows VM 的 lockpage 问题未解决**：论文承认 P99 lockpage 率高达 79%（主要因 Windows VirtIO 驱动），但仅建议"优化驱动"，而生产中采用了静态 lockpage 配置"for ease of maintenance"。对于占约 1/4 的 Windows VM，VIO 的内存回收效果大打折扣。

5. **安全性讨论不足**：IOPA-Snoop 在 hypervisor 中拦截和修改 VirtIO available ring 的行为引入了新的攻击面——恶意 guest 可能通过构造特殊的 ring 内容来探测 host 内存布局或触发 race condition。论文未讨论这些安全隐患。

6. **NVMe 扩展仅一笔带过**：论文声称已将 VIO 扩展到 NVMe 协议，但没有提供任何 NVMe 场景的性能数据。作为 Discussion 中的重要 generalizability 论据，这一声称缺乏实验支持。

---

## 七、AI Infra / MLSys 视角

1. **GPU/加速器场景的启示**：虽然高端 GPU 已支持 PRI（如 NVIDIA 的 Unified Virtual Memory），但 VIO 的核心思想——在数据平面拦截并预处理 page fault——可以迁移到 GPU 内存管理场景。例如在 LLM 推理中，KV cache 的内存管理可以借鉴 IOPA-Snoop 的思路，在 attention 计算前预取所需页面，避免 GPU page fault 打断 kernel 执行。

2. **弹性资源管理的借鉴**：Elastic Passthrough 根据 IOPS 动态切换模式的思路，可以迁移到 GPU 显存管理中。例如在 serving 场景下，根据请求负载动态决定 KV cache 是否 offload 到 host memory，类似 VIO 根据 IOPS 决定是否启用 snooping。

3. **DPU 在 AI 训练中的角色**：VIO 依赖 DPU 进行 VirtIO offload，这与当前 AI 训练集群中 DPU/SmartNIC 承担 RDMA 通信和 collective operations 的趋势一致。VIO 的 shadow ring 机制可以为 RDMA-based 分布式训练中的内存管理提供参考。

4. **可跟进的研究方向**：
   - 将 IOPA-Snoop 机制适配到 GPU passthrough 场景（如 vGPU/SR-IOV GPU），解决 GPU 显存超售问题
   - 在 RDMA 网络中应用类似的弹性 passthrough 策略，根据 all-reduce 通信压力动态管理 pin memory

---

## 八、总结

VIO 提出了一种不依赖 PRI 硬件的 I/O 虚拟化方案，通过 IOPA-Snoop 在 VirtIO 数据平面预处理 page fault、Elastic Passthrough 根据 IOPS 动态切换模式、以及 Adaptive Lockpage 减少热页面的反复 fault。系统已在全球最大的 CSP 之一部署了超过 30 万 VM，每日回收等价于 3 万 VM 的内存，同时保持 I/O SLO。其最大优势是无需修改 guest 软件栈、兼容 legacy VM，适合大规模多租户云环境。主要局限在于依赖 VirtIO 框架和 DPU 硬件 offload，且在中等 IOPS 区间和 Windows VM 场景下效果有限。
