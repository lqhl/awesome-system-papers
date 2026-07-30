---
type: paper
name: Sandman
full_title: "Sleeping with One Eye Open: Fast, Sustainable Storage with Sandman"
authors: [Yanbo Zhou, Erci Xu, Anisa Su, Jim Harris, Adam Manzanares, Steven Swanson]
venue: SOSP
year: 2025
tags: [storage, power-management, spdk, nvme, sustainability]
source_pdf: "[[3731569.3764804.pdf]]"
source_md: "[[3731569.3764804]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 睁着一只眼睛睡觉：使用 Sandman 进行快速、可持续的存储（SOSP 2025）

> **原题**：Sleeping with One Eye Open: Fast, Sustainable Storage with Sandman

> **一句话总结**：PCIe 5.0 all-flash 服务器用 [[SPDK]] busy-polling 即轻载也耗 **1.82×** idle CPU 功率，云 trace 显示预留算力可达需求 **3.4×**；Sandman 用浅睡眠 + 协同唤醒 + NIC 队列微秒级 burst 检测，相对 SPDK 性能 **±5%** 内，功耗 **-39%**、能耗 **-33%**。

## 问题与动机

全闪存节点（多 NVMe PCIe 5.0 + 200Gbps [[RDMA]]）饱和单盘需 **32×** SATA 时代 core 数；polling 栈在 <5% IOPS 时 CPU 功耗仍接近峰值（Table 1）。Google/Meta/阿里 trace 显示频繁 burst，预留 peak polling 容量造成 **3.4×** 能源浪费（Figure 2）。Governor/动态调度/混合 polling 要么损 tail latency，要么省电有限。

## 关键观察 / 隐含假设

- **观察 1**：降 CPU frequency 或跨核迁移线程唤醒开销高；浅睡眠 + 协同唤醒优于 per-core 独立变频。
  - **依赖假设**：cache-coherence + lightweight thread 可作高效唤醒机制。
  - **可能失效场景**：极短 burst 密集到睡眠/唤醒来不及。
- **观察 2**：传统 CPU cycle 计数估 load 太粗；应直接看 NIC 队列到达的 I/O 做 **μs 级** burst 检测。
  - **依赖假设**：NVMe-oF target 瓶颈可映射到网络队列深度变化。
  - **可能失效场景**：本地 NVMe 无 NIC 路径时需另设 detector。
- **假设 1**：与 SPDK 性能差距应 <5% corner case 才可替代生产 polling。
  - **证据强度**：中强；microbench + 云 block trace replay。

## 核心方法

**Sandman** 调度框架（ atop SPDK）：

1. **Fast resource scaling**：cores 进入浅睡，避免 DVFS/context switch 高开销
2. **Resource monitoring**：协同多核同睡同醒，延长低功耗驻留
3. **I/O burst detection**：分析 NIC 入队请求，非 CPU cycle 启发式

评测：PCIe 5.0 SSD + 200Gbps RDMA NVMe-oF，对比 Linux interrupt、Governor、Dynamic Scheduling、Hybrid Polling、SPDK。

## 设计取舍

- **取舍 1**：绑定 SPDK 生态 → 非 SPDK 栈需移植 detector/wakeup。
- **取舍 2**：浅睡 vs 深睡——选快速唤醒牺牲更深节能。
- **边界条件**：corner case 仍可能 **5%** 性能差距。

## 实验与结果

- 平均功耗：**最高 -39.38%**；能耗：**最高 -33.36%**
- vs SPDK：性能 corner case **within 5%**；云 block trace 能耗 **-30.23%** vs Linux、**-33.36%** vs SPDK
- latency 分布与 SPDK **可比**
- 相对 Governor/Dynamic Scheduling：更好性能；相对 Hybrid Polling：更低功耗

## 批判性分析

### 论证链条

R1–R3 能源动机 + 现有方案失败模式 → 三条 design guideline → Sandman 接近 SPDK 性能降功耗，链条完整。从单节点实验到「1000+ 服务器 24h trace 模式」外推合理但缺多租户混部干扰数据。

### 假设压力测试

- **burst 预测错误**：过早睡眠导致 tail spike——5% 边界需生产 SLO 验证。
- **多队列 NIC**：detector 在 sharded queue 上是否仍 μs 准确未详述。
- **SSD 功耗**：Table 1 SSD 随负载变，Sandman 主要救 CPU/fan cascade。

### 实验可信度

Samsung/UCSD 合作、field trace replay 可信；baseline 覆盖主流 power-saving 路线。缺与 cgroup CPU idle 策略、K8s 节点 autoscaler 联合效果。

### 系统性缺陷

论文未讨论 Sandman 与 QoS 租户隔离、睡眠态 debug/profiling 干扰；SPDK 版本升级耦合。

## 局限与后续工作

- **局限 1**：实现 atop SPDK，通用 kernel block 路径未覆盖。
- **局限 2**：corner case 5% 差距对 latency-SLO 严苛场景可能仍不可接受。
- **Future work 1**：与 K8s 节点 scale-to-zero 联动，测量 rack 级 PUE。
- **Future work 2**：本地 NVMe（无 NVMe-oF）burst 检测原型。

## 相关

- **相关概念**：[[SPDK]]、[[NVMe]]、[[Power-Management]]、[[RDMA]]、[[Sustainability]]
- **同类系统**：SPDK Governor、Hybrid Polling、Linux interrupt mode
- **同会议**：[[SOSP-2025]]
