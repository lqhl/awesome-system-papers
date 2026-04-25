---
type: paper
name: TaiChi
full_title: "Tai Chi: A General High-Efficiency Scheduling Framework for SmartNICs in Hyperscale Clouds"
authors: [Bang Di, Yun Xu, Kaijie Guo, Yibin Shen, Yu Li, et al.]
venue: SOSP
year: 2025
tags: [smartnic, scheduling, virtualization, cloud, alibaba]
source_pdf: "[[3731569.3764851.pdf]]"
source_md: "[[3731569.3764851]]"
---

# Tai Chi: A General High-Efficiency Scheduling Framework for SmartNICs in Hyperscale Clouds (SOSP 2025)

> **一句话总结**:阿里巴巴用硬件/软件协同的 hybrid 虚拟化统一物理 CPU 与 vCPU,让 SmartNIC 上的 control-plane 任务蹭 data-plane 空闲 CPU,把 VM 启动延迟降到 1/3×,DP 仅 0.7% 开销,已在生产环境部署三年。

## 问题

云厂商(AWS Nitro、Alibaba CIPU、Azure SmartNIC)用 SmartNIC offload data-plane 服务(DPDK/SPDK)与 control-plane 任务(设备初始化/监控)。生产统计显示 DP 为保证 SLO 按峰值静态分配 CPU,99% 时间有 67.5% 的 CPU cycle 空闲;同时 CP 任务因 SmartNIC 算力不足频繁违反 VM 启动 SLO(4× instance density 下超 SLO 3.1×)。

现有 LC/BE 共调度方案(Shenango、Caladan、Concord、Skyloft、Vessel)有五大限制:忽略 CP 的 SLO、CP 的非抢占 routine(ms 级)在 DP 引起尾延迟毛刺、侵入式代码改动(CP 生态有 300-500 种异构任务)、依赖 UINTR 等 SmartNIC 不支持的硬件特性、调度开销高。

## 核心方法

Tai Chi 的 key insight 是用硬件辅助[[Virtualization]](Intel VT-x 等)把 CP 任务封装到 preemptible 的 vCPU 上下文,利用硬件 state transition 实现 μs 级抢占,天然破除非抢占 routine。具体:

- **Hybrid virtualization**:vCPU 和物理 CPU 共享同一个 OS(而非传统 VM 有 guest OS),消除虚拟化的资源税(device emulation、guest OS)与 IPC 翻译开销;小改 OS 让 vCPU 与 pCPU 之间可直接走 IPI。
- **硬件-软件协同 workload probe**:编程化 I/O accelerator 在 DP 真正开始处理前探测到 I/O workload 将到达,据此提前启动 vCPU 切换,消除虚拟化调度性能税。
- **透明部署**:CP 任务零代码改动,支持 C/Python/Java/Bash/Rust 多语言;兼容 BlueField-3、Intel IPU、CIPU、Azure SmartNIC。
- **DP 原生性能**:DP 服务直接跑在物理 CPU 上,vCPU 只在 DP idle 时介入。

## 关键结果

- CP 任务(VM 启动等)延迟降低最多 3×,恢复 SLO 达成。
- DP 服务平均开销仅 0.7%,尾延迟无显著影响。
- 已在一家 top-tier 云厂商生产环境部署三年,跨多代 SmartNIC 平台。
- 对比 Shenango/Caladan 的 ms-scale 调度粒度,Tai Chi 达到 μs-scale。

## 相关

- **相关概念**:[[Virtualization]]、[[SmartNIC]]、[[DPDK]]、[[SPDK]]
- **同类系统/工作**:[[Shenango]]、[[Caladan]]、Concord、Skyloft
- **同会议**:[[SOSP-2025]]
