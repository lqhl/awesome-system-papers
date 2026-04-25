---
type: paper
name: RDMA-LiveMigration
full_title: "Device-Assisted Live Migration of RDMA Devices"
authors: [Artem Y. Polyakov, Gal Shalom, Aviad Yehezkel, Omri Ben David, Asaf Schwartz, et al.]
venue: SOSP
year: 2025
tags: [rdma, live-migration, virtualization, pci-passthrough, cloud]
source_pdf: "[[3731569.3764795.pdf]]"
source_md: "[[3731569.3764795]]"
---

# Device-Assisted Live Migration of RDMA Devices (SOSP 2025)

> **一句话总结**:NVIDIA ConnectX-7 首次实现 [[RDMA]] passthrough 设备的 sub-second 下线时间 live migration，同时对 guest VM 和网络对端全透明，并支持 GPUDirect 下 GPU+RDMA 多设备一致性迁移。

## 问题

云厂商把 HPC/AI 负载拉进虚拟化环境是大趋势，但 RDMA 设备要求 PCIe passthrough + SR-IOV 裸机性能。这违反了 guest OS 和底层硬件的 decoupling，使 Live Migration (LM) 变得极为困难——现代 hypervisor (VMware ESX、KVM/QEMU) 干脆在 passthrough 场景禁用 LM。

RDMA 带来三重挑战：

- **Namespace 难以复制**：QP number、memory key 是设备分配的身份，软件无法精确在目标设备复制。已有方案 (MigrOS 等) 需要改 guest kernel 或 libibverbs 做 runtime translation，不适合云租户透明场景。
- **In-flight 消息**：RDMA transport 状态封装在硬件，软件方案只能 drain 所有 WQE（可能浪费 GB 级消息），或粗暴 abort（原子操作会破状态）。
- **Peer 连接**：migration 对 peer 可见，QP 重建需要全局协调；MigrOS 引入 Paused 状态但对 migrating VM 故障不健壮。

更棘手的是 AI 场景 RDMA + GPU 组合（如 Azure NDv2），需要在 PCIe fabric 层面同时 suspend 多个 passthrough 设备并维持 P2P 通信一致性。

## 核心方法

作者提出 **device-assisted** 方法，硬件与 hypervisor 分工明确，给出 12 条 "Device Assists"（DA1-12）：

- **Network transparency (DA1-4)**：设备精确保留 RDMA namespace、local 地址、remote 连接；配合 exponential backoff 让 reliable transport 撑过 downtime；包级别 quiesce（记下 sequence number、opcode、virtual address、atomic cache）而非 drain，retransmission 负担 negligible。
- **State extraction (DA5-7)**：黑盒式批量抽取 VF 的 Interconnect Context Memory (ICM) 而非逐 object 序列化；relax 微架构状态（timer、拥塞控制、QoS credit 等 migration 后无意义的丢弃）；用 vendor 特定的 migration tag 处理 firmware 版本兼容（滚动升级场景）。
- **Two-phase suspend (DA12)**：单设备用双向 posted PCIe write 利用 PCIe ordering 刷 in-flight TLP；多设备用 suspend-active / suspend-passive 两阶段解耦——active 阶段停止发起新事务但仍能响应，passive 阶段密封。通过 PCIe LCA 论证这能保证跨设备 P2P 事务最终一致。算法适用于 NVLink 等其他 memory fabric。
- **Pipelined image transfer (DA8-10)**：把 save/transfer/load 三阶段流水线化，将下线时间从 `S+T+L` 降到 `max(S,T,L)`；DMA dirty-rate 控制防止设备高速 dirty VM memory。

API 分三类：Query、Device Control、Image Access，加进 KVM/QEMU 共约 6K LOC firmware + hypervisor 改动，从 ConnectX firmware 28.41.1000 起 GA。

## 关键结果

- **Sub-second 下线时间**：即使 VM 用满 RDMA 资源（数十万 QP/MR）
- 迁移后**性能无退化**，运行期零开销
- 支持 GPUDirect 场景下 GPU+NIC 协同迁移
- 与 ConnectX-6 firmware 互操作做 rolling upgrade
- 已在 production Linux 虚拟化栈 Generally Available

## 相关

- **相关概念**:[[RDMA]]、[[Live-Migration]]、[[PCIe]]、[[SR-IOV]]、[[GPUDirect]]、[[IOMMU]]
- **同类系统**:[[MigrOS]]
- **同会议**:[[SOSP-2025]]
