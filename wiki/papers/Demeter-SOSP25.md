---
type: paper
name: Demeter
full_title: "Demeter: A Scalable and Elastic Tiered Memory Solution for Virtualized Cloud via Guest Delegation"
authors: [Junliang Hu, Zhisheng Hu, Chun-Feng Wu, Ming-Chang Yang]
venue: SOSP
year: 2025
tags: [tiered-memory, virtualization, cxl, pmem, guest-delegation]
source_pdf: "[[3731569.3764801.pdf]]"
source_md: "[[3731569.3764801]]"
---

# Demeter: A Scalable and Elastic Tiered Memory Solution for Virtualized Cloud via Guest Delegation (SOSP 2025)

> **一句话总结**：hypervisor 侧 [[Tiered-Memory]] 用 EPT/GPT PTE.A/D 追踪会在 [[2D-Address-Translation]] 下触发破坏性 invept，GUPS 上 TPP-H 比 guest 方案 **2.5×** 更慢；Demeter 把 TMM 完全委托 guest，用 EPT-friendly [[PEBS]] + range 分类 + double balloon，相对 hypervisor 方案最高 **2×**，相对次优 guest 方案平均 **+28%**。

## 问题与动机

云 VM 内存扩展依赖 DRAM+PMEM/[[CXL.mem]] 分层，但 per-core 内存容量增速远低于 core 数。现有虚拟化 [[Tiered-Memory]] 多在 host hypervisor 做 access tracking（PTE.A/D 扫描），在 **2D 页表**下重置 dirty 位需 full TLB flush（无 gVA 只能 invept），且 host 无法有效用 PEBS。论文提出 **guest delegation**：TMM 在 guest，host 仅 elastic provisioning（TMP）。

## 关键观察 / 隐含假设

- **观察 1**：TPP-H（EPT PTE.A 扫描）TLB flush 指令数为 TPP-G 的 **4.7×**，GUPS 总时间 **2.5×**（Table 1）。
  - **依赖假设**：GUPS 代表广内存 footprint 云 workload 的 TLB 压力。
  - **可能失效场景**：极少 mmap/极少页表扰动的 compute-bound VM 收益缩小。
- **观察 2**：PEBS v5 修复 EPT fault 中断缺陷后，guest 内 PEBS 与 VMCS debugctl 隔离可安全采样。
  - **依赖假设**：云厂商愿启用 guest PEBS；overcommit 下 lazy EPT populate 与 PEBS 协同。
  - **可能失效场景**：旧 CPU 无 PEBS v5 需 eager map workaround。
- **假设 1**：guest 虚拟地址空间做 range-based 分类保留 locality，优于 hypervisor 扫 uncorrelated gPA 页。
  - **证据强度**：强；LibLinear heatmap（Figure 4）直观支持。

## 核心方法

**Guest-delegated TMM**：EPT-friendly PEBS 热页采样 → range classifier（gVA）→ 热冷页迁移，减少 locking/TLB flush。

**Double balloon TMP**：维持云弹性与 vendor QoS，避免 tiered memory 倾斜供给。

**可扩展性**：9 VM × GUPS 时 naive guest TPP 浪费 **>4.5** core，Memtis **~1.25** core，Demeter **<0.2** core overhead。

实现开源（Zenodo）；评测 DRAM+PMEM 与 emulated CXL.mem，7 个真实 workload。

## 设计取舍

- **取舍 1**：guest 内运行 TMM → 信任 guest 不作弊（云租户模型通常可接受），host 失去全局视野。
- **取舍 2**：double balloon 复杂度 vs 纯 kernel TPP 移植到 guest。
- **边界条件**：TMP alone 最高 **+68%**；全栈 TMM **+28%** avg vs 次优 guest。

## 实验与结果

- vs hypervisor-based：**最高 2×**
- vs 次优 guest alternative：**平均 +28%**（7 workloads）
- TMP 机制 alone：**最高 +68%**
- TLB flush：Demeter **9.3M** vs TPP-H **62M** single + **20M** full
- 多 VM 扩展：CPU overhead **<0.2 core**（36-core 主机）

## Critical Analysis

### 论证链条

2D TLB 惩罚 + guest PEBS 可行 → delegation + range TMM → 多 workload 提升，逻辑闭合。到「所有 Azure/Google 分层内存部署」跳步：需 host 协同 balloon、安全隔离 guest TMM 篡改热页决策等生产 policy 未全展开。

### 假设压力测试

- **恶意 guest**：故意误导热页分类损害自身或邻居——云 SLA 通常隔离单 VM，但 host 侧 memory pressure 联动未讨论。
- **CXL**：emulated CXL.mem 与真 CXL 延迟带宽差异可能改变 range 迁移频率。
- **PEBS 隔离**：多 VM 同机 PEBS buffer 争用长期稳定性需更多月级数据。

### 实验可信度

GUPS microbench 支撑 TLB 论点有力；7 真实 workload 覆盖 DB/ML/图计算。部分 hypervisor baseline 为 TPP 改造（缺 commercial vTMM 源码）需在结论中记住。

### 系统性缺陷

guest delegation 与 live migration、snapshot、memory balloon 冲突场景论文未讨论；运维需同时理解 guest TMM + host TMP 双层调参。

## 局限与 Future Work

- **局限 1**：依赖 Intel PEBS v5 与虚拟化特性，跨厂商需移植。
- **局限 2**：host 全局调度（跨 VM 公平）能力减弱。
- **Future work 1**：真 CXL.pod 生产 trace 回放，测量 egress/PMEM wear 与性能三角。
- **Future work 2**：与 [[Demeter]]-class host hint（轻量 gPA 统计）混合，测量 invept 频率下降是否值得。

## 相关

- **相关概念**：[[Tiered-Memory]]、[[CXL]]、[[PEBS]]、[[EPT]]、[[Virtual-Memory]]、[[TLB]]
- **同类系统**：TPP、Memtis、vTMM、HeteroVisor、RAMinate
- **同会议**：[[SOSP-2025]]