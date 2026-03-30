# VIO: Dynamic I/O Device Passthrough with IOPA Snooping

## 论文基本信息

- **标题**: To PRI or Not To PRI, That's the question
- **作者**: Yun Wang (SJTU); Liang Chen, Jie Ji, Xianting Tian, Ben Luo (Alibaba Group); Zhixiang Wei, Zhibai Huang, Kailiang Xu (SJTU); Kaihuan Peng, Kaijie Guo, Ning Luo, Guangjian Wang, Shengdong Dai, Yibin Shen, Jiesheng Wu (Alibaba Group); Zhengwei Qi (SJTU)
- **会议**: OSDI 2025
- **链接**: https://www.usenix.org/conference/osdi25/presentation/wang-yun

## 研究背景与动机

现代云环境中，设备直通（device passthrough）技术如 SR-IOV 和 I/O 设备直通使网络和存储设备能在多租户环境下以接近原生性能的方式共享。然而，直通面临一个关键限制：DMA 可以直接访问任何客户机物理地址（GPA），如果地址被换出或不可访问，将导致 I/O 页错误（IOPF）。由于大多数设备无法处理此类故障，直通需要静态固定（pin） VM 的虚拟内存，这在多租户云环境中不可接受，因为它禁止了内存超额订阅等内存优化技术。

**PCIe ATS/PRI 方案**于 2009 年提出，2023 年 Intel Sapphire Rapids 才在 IOMMU 中引入 PRI 支持。但由于：
1. **软件/硬件兼容性问题**: 主流 I/O 设备（除高端 GPU）大多不支持 PRI，Linux v6.12 仅在 PASID 场景下支持 PRI
2. **延迟惩罚严重**: PRI 的 IOPF 处理延迟是 CPU 页错误处理的 3×-80×，因为它需要 PCIe 总线往返
3. **SR-IOV 的扩展性问题**: 将 PRI 扩展到数千个 VF 会显著增加硬件成本

**生产环境数据**: 在 300 节点的集群中，超过 80% 的 legacy VM 消耗约 800GB 内存，其中约 34% 是冷页（cold pages），每天可回收约 120GB——相当于每天节省约 30 台 2C/4GB VM 的资源。73.14% 的 VM 的 IOPS 低于 1,000，仅 3.57% 的 VM 超过 30,000 IOPS。

## 要解决的核心问题

1. **IOPF 性能惩罚**: PRI 的 IOPF 处理在 I/O 关键路径上，导致 3×-80× 的延迟增加
2. **Legacy VM 兼容性**: 超过 80% 的 legacy VM 内核不支持 PRI，无法从硬件升级中受益
3. **弹性资源利用**: 高 IOPS 工作负载需要直通性能，低 IOPS 工作负载需要内存回收能力
4. **大规模部署可行性**: 大规模云环境（300K VMs）需要无需客户机软件修改的解决方案

## 主要贡献

1. **VIO: 首个无需硬件和客户机软件修改的 IOPF-free 虚拟化方案**: 完全在主机 hypervisor 侧实现，利用 VirtIO 标准的数据平面
2. **IOPA Snooping 机制**: 在 VirtIO 数据平面中探测每个 DMA 请求，提前处理潜在的页错误，消除 IOPF
3. **IOPS 感知弹性直通**: 基于 IOPS 压力的细粒度弹性直通策略，在高负载时切换到直通模式，低负载时切换到 VIO 模式进行内存回收
4. **大规模生产部署验证**: 在全球头部 CSP 的 300K VMs 上部署，每天回收相当于 30K VM 的内存

## 研究方法与设计

### IOPA Snooping 机制

**核心思想**: 利用 VirtIO 的 split-driver 模型，在设备直接访问 DMA buffer 之前，由 hypervisor 侧的 IOPA-Snoop 模块提前探测并确保所有页都已映射。

**工作流程**:
1. **准备阶段**: VirtIO 前端在 available ring 中追加描述符链（Descriptor chain），更新 available index
2. **IOPA Snooping**: VIO 不直接让设备看到真实的 available index，而是使用 shadow available index——当设备看到 shadow index 时，IOPA-Snoop 模块检测到 index 更新
3. **页错误处理**: IOPA-Snoop 检查 buffer 中的页是否已映射（通过查询 EPT）；如果页被换出，从 swap 读取数据
4. **Shadow 更新**: 将 shadow available index 更新为真实 index，设备继续 DMA 操作
5. **直接中断传递**: 设备中断直接传递到 VM guest，无需 hypervisor 介入

**关键优化**: 页错误处理完全在 hypervisor 侧完成，无需设备参与。即使多个页错误同时发生，处理流程与 CPU 页错误一致，IOPF 处理从 DMA 关键路径中移除。

### 弹性直通机制

**两种模式**:
1. **VIO 模式（低 IOPS）**: 使用 IOPA Snooping，保证所有 DMA 页已映射，允许内存回收
2. **Passthrough 模式（高 IOPS）**: 直接让设备访问 available ring，享受接近原生性能

**模式切换流程**:
- **Passthrough → VIO**: (1) 在 EPT 中 unmap available ring；(2) 将 available ring 内容复制到 shadow available ring（~10µs）；(3) 在 IOMMU IOPT 中原子重映射 shadow available ring
- **VIO → Passthrough**: 切换前主动 swap-in 被换出的页（snooping 期间持续 swap-in）；实际切换时所有必要页已在内存中，实现无缝过渡

**IOPS 阈值**: 监控 VM 的 IOPS，超过阈值（如 100k IOPS）自动切换到 Passthrough 模式。

### 自适应锁页机制

基于 IOPA snoop 收集的 I/O 页访问模式信息，区分 I/O 热页和冷页，对热页进行特殊处理以减少 IOPF 同时保持良好的内存效率。

## 关键实现细节

### 兼容性与透明性
- **无需客户机修改**: 所有实现位于 host hypervisor 侧，legacy VMs 完全透明
- **无需硬件修改**: 不依赖 ATS/PRI，利用 VirtIO 标准
- **VMM 实时升级**: 通过 VMM 实时升级（如 Orthus）部署到现有 legacy VMs，无需 VM 重启或重新配置

### VirtIO 标准利用
- 利用 VirtIO 1.0 标准的数据平面抽象
- 提供 stateful 接口给 custom-rendering 应用（兼容性）
- 底层 Spade2D 引擎提供 stateless 接口以实现并行化

## 实验结果与分析

### 生产环境评估
- **内存回收**: 每天回收约 120GB 内存，相当于 30K VM（2C/4GB）
- **IOPS 感知弹性直通**: 相比传统直通，在保持 SLO 的同时实现每天约 10% 的内存减少

### Iperf 性能测试
- Legacy VM 在 VMM 升级过程中（~200ms 窗口）出现轻微性能波动
- 升级完成后 VM 在 VIO 模式下运行，与升级前性能一致

### 帧率测试（针对折叠屏场景）
- Mate70（单屏）、MateX5（双折）、MateXT（三折）在新设计下帧率均有改善
- 功耗降低 3.0%（通过更好地利用多核）

## 潜在问题与局限性

1. **仅支持 VirtIO 设备**: VIO 的 IOPA Snooping 机制依赖 VirtIO 的 split-driver 模型，对非 VirtIO 设备（如原始 PCIe 设备）的支持有限
2. **IOPS 阈值的设置**: 100k IOPS 阈值是生产环境的经验值，可能不适合所有工作负载场景，需要进一步的自适应机制
3. **Shadow ring 的内存开销**: 每个 VM 需要 shadow available ring，在大规模部署（300K VMs）时额外的内存开销可能相当可观
4. **切换延迟的实际影响**: VIO → Passthrough 切换需要提前 swap-in 页，如果 VM 突然从低 IOPS 切换到高 IOPS，swap-in 的延迟可能导致瞬时性能下降
5. **与 VFIO 的关系**: 论文未讨论 VIO 与 VFIO 框架的关系，可能存在集成挑战

## 未来工作方向

1. 扩展 VIO 机制到非 VirtIO 设备
2. 自适应 IOPS 阈值调整
3. 与其他内存管理技术（如透明大页）的协同优化

## 个人评注

### 优点
1. **工程洞察深刻**: 论文通过 Alibaba 生产环境（300 节点，300K VMs）的实际数据分析，揭示了云环境中 73.14% 的 VM IOPS 低于 1,000 这一关键特征，为弹性直通设计提供了数据支撑
2. **IOPA Snooping 机制的创新**: 将 hypervisor 侧的主动页预取与 VirtIO 的 available ring 机制结合，巧妙地将 IOPF 从 DMA 关键路径中移除
3. **与 VMM 实时升级的集成**: 通过 Orthus 实现 VIO 对 legacy VMs 的透明部署，解决了工程中最大的采用障碍
4. **表格 1 的清晰对比**: 将 VIO 与 6 种现有方法（vIOMMU、IOGuard、Ballooning、FreePageReporting、Hyperupcall、IOPF/VPRI）从 IO 安全、硬件兼容性、客户机修改、回收类型和开销等维度进行了全面对比

### 潜在问题
1. **"10% 内存减少"的绝对值**: 每天约 10% 的内存减少是在整个 300K VMs 集群的规模下，还是单个 VM 的平均值？论文未明确说明。从上下文看，这似乎是集群级别的数字——但即使是 10%，对于内存密集型云服务商的节约也是巨大的
2. **"无需客户机修改"的实际限制**: 虽然 VIO 本身无需客户机修改，但 VirtIO 前端驱动需要在 VM 中运行（这是 VirtIO 的标准要求）。如果 legacy VM 没有 VirtIO 驱动，VIO 的 snoop 机制将不适用
3. **IOPS 阈值的敏感性**: 100k IOPS 作为切换阈值的依据未充分说明——这个阈值是如何确定的？是否考虑了不同时间段的工作负载波动？如果阈值设置不当，可能导致频繁的模式切换，反而影响性能
4. **Shadow available ring 的实现复杂度**: Shadow index 机制要求 IOPA-Snoop 模块跟踪原始 ring 的状态，添加了一层复杂性。在极高 IOPS（> 100k）场景下，每个 IO 请求都可能触发 snoop 操作，如何保证 snoop 本身不成为瓶颈？
5. **与 D-VSync 的关系**: 论文提到 D-VSync 是 HarmonyOS NEXT 中最新的帧率同步技术，但未讨论 VIO 与 D-VSync 的集成——两者是互补还是互斥？
