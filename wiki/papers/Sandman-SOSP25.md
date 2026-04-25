---
type: paper
name: Sandman
full_title: "Sleeping with One Eye Open: Fast, Sustainable Storage with Sandman"
authors: [Yanbo Zhou, Erci Xu, Anisa Su, Jim Harris, Adam Manzanares, Steven Swanson]
venue: SOSP
year: 2025
tags: [storage, ssd, energy-efficiency, spdk, nvme-of, polling]
source_pdf: "[[3731569.3764804.pdf]]"
source_md: "[[3731569.3764804]]"
---

# Sleeping with One Eye Open: Fast, Sustainable Storage with Sandman (SOSP 2025)

> **一句话总结**:在 SPDK busy-polling 栈之上引入浅睡眠 + cache-coherence 唤醒 + 从 NIC 队列做 μs 级 I/O 突发检测,平均功耗降最高 39.38%、能耗降 33.36%,同时性能与纯 polling 相比差距 ≤5%。

## 问题

全闪服务器性能飙到 2500K IOPS、14 GB/s、单盘 120 TB,但代价是能耗。PCIe 5.0 NVMe SSD 要撑满,一盘就吃 3 逻辑核(比 SATA 32×、PCIe 3.0 4×),而主流 polling 栈([[SPDK]])逼 CPU 常驻 100% 频率。Table 1 实测:系统总功耗 412W→940W,CPU 常在 1.82× idle 水平,带动风扇从 18K RPM 升到 28K。真实云 trace(30 分钟内 82 次突发)下 3.4× 的能耗被浪费。现有 4 种方案没一个兼顾高性能与低功耗:

- **Linux interrupts**:轻载省电但 context switch 在 5120K+ IOPS 下功耗反超 SPDK
- **Governor**(P-state 调频):硬件跨 P-state 切换需要 >450 μs PLL lock,burst 下 tail latency 3× 差
- **Dynamic Scheduling**:μs 级 interval 下 thread-load 估计失真,60 秒内瞎迁 100 万次线程
- **Hybrid Polling**:sleep/active 频繁转,能省电但收益有限

## 核心方法

Sandman 基于四条设计准则,跑在 SPDK 之上:

- **Fast resource scaling**:不调频不切 context,让空闲 core 进入浅层快唤醒 sleep state,并利用 **cache-coherence 机制 + 轻量线程** 作为唤醒通道——唤醒路径仅依赖 cacheline invalidation,比信号量/futex 快得多。
- **Resource monitoring policy**:让多个 core 一起睡、睡得更久,避免独立频繁转换带来的抖动。
- **I/O burst detection via NIC queues**:不用传统的 CPU-cycle 计数,而是在 NVMe-oF 的 **RDMA NIC 队列** 上看进站 I/O 速率,μs 级精度判断 burst。
- 整个框架整合成一个 scheduler,决定哪些 core 唤醒、何时唤醒、以什么优先级处理。

## 关键结果

- 对两块生产块存储 field trace:能耗比 Linux 低 30.23%,比 SPDK 低 33.36%,延迟分布接近 SPDK
- Burst workload:Sandman 与 SPDK 性能相当,显著低于 Governor/DynSched 的 tail latency(GOV 3× 高)
- 平台:16× PCIe 5.0 NVMe SSD + 200 Gbps RDMA NIC
- 平均功耗降最高 39.38%,tail latency 与 SPDK 在 corner case 仅差 ≤5%

## 相关

- **相关概念**:[[SPDK]]、[[NVMe-oF]]、[[RDMA]]、[[Polling-vs-Interrupt]]、[[Sustainable-Computing]]
- **同类工作**:Governor/cpufreq、Linux interrupt path、Hybrid Polling(OSDI 前期工作)、Dynamic Scheduling in SPDK
- **同会议**:[[SOSP-2025]]
