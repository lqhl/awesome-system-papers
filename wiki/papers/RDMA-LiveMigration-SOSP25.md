---
type: paper
name: RDMA-LiveMigration
full_title: "Device-assisted Live Migration of RDMA devices"
authors: [Artem Y. Polyakov, Gal Shalom, Asaf Schwartz, Aviad Yehezkel, Omri Ben David, Omri Kahalon, et al.]
venue: SOSP
year: 2025
tags: [rdma, live-migration, virtualization, cloud, gpudirect]
source_pdf: "[[3731569.3764795.pdf]]"
source_md: "[[3731569.3764795]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# Device-assisted Live Migration of RDMA devices (SOSP 2025)

> **一句话总结**：PCI passthrough [[RDMA]] 破坏 VM 与硬件解耦使 [[Live-Migration]] 极难；本文用 NVIDIA ConnectX 设备辅助（namespace 保持、包粒度 quiesce、黑盒状态提取）扩展 KVM/QEMU，在 HPC/AI + [[GPUDirect]] 场景实现亚秒级 downtime 且正常运行零开销。

## 问题与动机

云侧 HPC/AI VM 需 [[RDMA]] passthrough 保 bare-metal 性能，但设备状态对 hypervisor 不可见，主流 hypervisor 在 passthrough 时禁用 LM。既有方案或协调销毁/重建 RDMA 资源（downtime 大），或改 guest API（租户软件不可控）。多设备场景（[[RDMA]] + GPGPU P2P）还需同时暂停设备并保持设备间通信一致性。论文目标：**对 guest 与网络 peer 均透明**的 LM。

## 关键观察 / 隐含假设

- **观察 1**：RDMA namespace（QP number、remote key）在 wire 可见；精确重建可免去与所有 peer 的全局协调。
  - **依赖假设**：目标 VF 能分配与源一致的 namespace；firmware 支持 migration tag 兼容性检查。
  - **可能失效场景**：rolling upgrade 跨不兼容 firmware tag 时需额外策略。
- **观察 2**：in-flight 消息若按 QP drain 会浪费 GB 级传输；设备可在**包粒度**暂停并记录重传状态。
  - **依赖假设**：固件暴露 sequence、atomic 缓存等微架构状态的可重建子集（DA5 放松完整微架构快照）。
  - **可能失效场景**：非标准 verb 扩展、自定义 offload 特性可能无法完整迁移。
- **假设 1**：hypervisor 应以黑盒 bulk 提取 VF 状态，而非遍历 Verbs 对象（DA6）。
  - **证据强度**：强；对比软件遍历 QP 创建连接需 ≈15s vs 镜像加载显著更快。

## 核心方法

提出十条 **Device Assist (DA)** 原则与通用 migration API，在 ConnectX 上实现：

1. **网络透明**：保持 RDMA namespace、本地/远端连接；RC 传输用指数退避重传容忍 downtime（DA3–4）。
2. **状态提取**：架构状态精确序列化；微架构状态「放松」以控制镜像大小（DA5–7）。
3. **虚拟化集成**：device state pre-copy、dirty-rate 控制（RDMA write 可不经过 vCPU）、流水线镜像传输（DA8–10）。

**多设备**：提出 PCIe fabric 上 quiesce 直接 P2P 通信的硬件无关方案（§4），支持 [[RDMA]]-GPU 同时迁移。扩展 Linux KVM/QEMU（GA，QEMU 8.1+），约 1K LOC。

## 设计取舍

- **取舍 1**：放松微架构状态 vs 镜像精度 → 镜像更小、迁移更快，但依赖设备语义等价重建。
- **取舍 2**：OOB 控制通道与设备镜像分离 → 当前 16 Gbit/s OOB 在高端 NIC 吞吐下成为 pre-copy 瓶颈（论文 §7.2.4 承认）。
- **边界条件**：生产网络重配置可压至 ≈81ms 额外中断；实验环境曾出现 310ms outlier。

## 实验与结果

- HPC/AI + [[GPUDirect]] Allreduce：亚秒级 downtime，迁移后性能无退化
- 相对软件遍历资源：MR 批量加载 **>2 个数量级** 加速；QP 创建+连接 **≈6×** 于镜像加载
- NPB：多数 benchmark RDMA 额外 downtime **≈150ms**；FT/LU 因 RDMA dirty 率更高达 **6×/2×** 内存传输量
- pre-copy：15 Gbit/s 脏率边界下迁移时间比 1 Gbit/s 节流长 **3.3×**
- pipelined transfer：downtime 仅再降 **3%**（OOB 带宽掩盖收益）

## Critical Analysis

### 论证链条

「RDMA 状态在设备内、软件遍历太贵」→ 设备辅助黑盒迁移 + namespace 保持 → 亚秒 downtime 与透明性，链条在 ConnectX + KVM 路径上闭合。从实验室到百万次/月生产 LM（§1 背景）的跳步在于：租户不可控软件、多 vendor NIC 混部、800Gbps NIC 与 OOB 带宽错配尚未在本文完全解决。

### 假设压力测试

- **Peer 行为**：假设 RC 退避足够；恶意或异常 peer 在 Paused 态行为论文未等同 MigrOS 式分析。
- **多租户**：同时迁移多台 VM 时 namespace 与 switch 表项压力未详述。
- **GPU**：vGPU + GPUDirect 实验有，但更广加速器组合（NVLink 多卡）扩展性待验证。

### 实验可信度

NVIDIA 作者 + GA 代码可信度高；基线对比 prior 软件方案充分。OOB 16 Gbit/s 与生产 800G 差距使 pre-copy 结论外推需谨慎。网络重配置 80ms 开销表明「端到端透明」仍依赖 SDN/IB 运维成熟度。

### 系统性缺陷

API 虽称 device-agnostic，实现深度绑定 ConnectX；故障恢复、部分迁移失败回滚、可观测性（migration 进度对租户）论文未讨论。QP 数量达数十万时 resume 扫描 active QP 开销（_firmware 实现可缓解_）仍是运维风险点。

## 局限与 Future Work

- **局限 1**：OOB 通道带宽与 RDMA 脏率不匹配时 pre-copy 不收敛（§7.2.4）。
- **局限 2**：非 ConnectX 设备需重新实现 DA 语义。
- **Future work 1**：RDMA OOB 或更快控制面通道，测量 400G/800G NIC 下 downtime 上界。
- **Future work 2**：与 cloud 编排器联合调度「迁移窗口」与 peer 退避参数，量化 tail SLO。

## 相关

- **相关概念**：[[RDMA]]、[[Live-Migration]]、[[Virtualization]]、[[GPUDirect]]、[[PCIe]]、[[KVM]]
- **同类系统**：MigrOS、Virtuoso（RDMA migration 软件路线）
- **同会议**：[[SOSP-2025]]
