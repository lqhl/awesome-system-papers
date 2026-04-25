---
type: paper
name: Demeter
full_title: "Demeter: A Scalable and Elastic Tiered Memory Solution for Virtualized Cloud via Guest Delegation"
authors: [Junliang Hu, Zhisheng Hu, Chun-Feng Wu, Ming-Chang Yang]
venue: SOSP
year: 2025
tags: [tiered-memory, virtualization, cxl, pebs, cloud]
source_pdf: "[[3731569.3764801.pdf]]"
source_md: "[[3731569.3764801]]"
---

# Demeter: A Scalable and Elastic Tiered Memory Solution for Virtualized Cloud via Guest Delegation (SOSP 2025)

> **一句话总结**:把分层内存管理从 hypervisor 完全下放给 guest VM,利用 EPT-friendly PEBS 做访问采样和基于 gVA 的 range 分类,相比 hypervisor-based 方案提速最高 2×,在次优 guest-based 方案之上再提 28%。

## 问题

虚拟化云中 DRAM 容量与核数增速倒挂(十年间 CPU 核数 10×,单机内存仅 2.67×),促使 Azure/Google/Meta 向 [[CXL]].mem + DRAM 等分层内存架构转移。但现有 hypervisor-based TMM 方案(HeteroVisor、RAMinate、vTMM 等)在 2D 地址翻译下有两大硬伤:(1) 依赖扫描 PTE.A/D bits,重置时被迫 full invalidate EPT 导致 4.7× TLB flush、2.5× 执行时间;(2) 硬件级的 [[PEBS]] 采样无法穿透虚拟化边界给 hypervisor 使用。

## 核心方法

Demeter 的核心主张是 **guest-delegated tiered memory**:把 TMM 的三步 pipeline(访问跟踪 → 热度分类 → 数据迁移)整体搬进 guest,hypervisor 只负责 tiered memory provisioning (TMP)。两个关键洞察:

- **EPT-friendly PEBS 可用**:PEBS v5 修掉了架构 bug,guest PMU sample 写入 vmcs.debugctl 指向的 guest-private buffer,跨 VM 天然隔离;可直接拿到 gVA 样本,省掉地址翻译。
- **guest 虚拟地址空间保留最多 locality**:内核分配器为减少碎片打乱了物理页面布局,而 gVA 空间的热点集中在连续小范围,用 DAMON 热力图对比证实。

据此 Demeter 设计了三件套:(1) **range-based hotness classification**,segment-tree-like 结构在 gVA 上做 range 分裂/合并,把热区逐步细化到 2 MiB、冷区成块管理;(2) **scalable EPT-friendly PEBS** 用 `MEM_TRANS_RETIRED.LOAD_LATENCY` 并靠 `MSR_PEBS_LD_LAT_THRESHOLD=64ns` 过滤 cache hit,固定采样率 1/4093 并在进程 context switch 时 drain sample buffer,消掉 PMI 和专用 polling 线程;(3) **balanced page relocation** 只挑 hot range 对应的页做 promote/demote,降低锁与 TLB flush。对 host 端则用 **double balloon**-based TMP:分别管快慢层,在超售下维持弹性并暴露 vendor QoS 钮。

## 关键结果

- 36-core + 126 GiB footprint GUPS:相比 TPP-H(hypervisor 版 TPP),TLB flush 减少 4.7×、执行时间快 2.5×
- 七个真实 workload(database/HPC/graph/ML)平均比次优 guest-based 方案(Memtis 等)快 28%
- 9 VM scale 下 tracking overhead 稳定在 0.2 core 内,而 TPP 浪费 4.5+、Memtis 浪费 1.25 核
- TMP 单独带来最高 68% 性能提升,覆盖 DRAM+PMEM 和 DRAM+CXL.mem 两种配置

## 相关

- **相关概念**:[[CXL]]、[[PEBS]]、[[Tiered-Memory]]、[[KV-Cache]] 无关但 hypervisor 的 [[EPT]] 和 TLB 是关键背景
- **同类工作**:TPP、Memtis、HeMem、vTMM
- **同会议**:[[SOSP-2025]]
