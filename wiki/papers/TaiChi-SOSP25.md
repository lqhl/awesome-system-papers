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

> **一句话总结**：SmartNIC 上 hybrid 虚拟化统一 pCPU/vCPU + 硬件 workload probe，control-plane 蹭 data-plane 空闲 CPU，VM 启动 **3.1×** 加速、data-plane 仅 **0.7%** 开销，阿里生产三年。

## 问题与动机

Hyperscale 云（AWS Nitro、阿里 CIPU、Azure SmartNIC）把 [[DPDK]]/SPDK data-plane (DP) 与 control-plane (CP) 静态分区。DP 按峰值预留导致 **67.5%** CPU 空闲（99% 时间），而 CP（设备初始化、VM 启动）SLO 恶化——高密度下 VM 启动超 SLO **3.1×**、CP 任务慢 **8×**。

现有 co-scheduling（LC+BE）不适用：CP 有严格 SLO 非 BE；CP 含 ms 级不可抢占例程拖累 μs 级 DP；300–500 异构 CP 任务难改代码；SmartNIC 缺 UINTR 等新特性；传统调度开销在资源受限 SNIC 上过大。

## 关键观察 / 隐含假设

- **观察 1**：DP CPU 利用率 CDF 显示绝大多数时间远低于峰值，存在可借用算力且 I/O 到达可预测窗口。
  - **依赖假设**：hardware-software workload probe 能在 DP 处理前预测突发，留出 vCPU 切换窗口。
  - **可能失效场景**：持续满负载 DP（无空闲）；预测失误导致 DP 尾延迟 spike。
  - **证据强度**：强——生产 CDF + 三年部署数据。
- **观察 2**：把 CP 封进可抢占 vCPU、DP 跑 pCPU，可打断 ms 级 CP 例程而不改 legacy CP 代码（仅 OS 小改 IPI）。
  - **依赖假设**：单 OS hybrid 虚拟化开销可忽略；vCPU/pCPU 间 native IPC 语义足够。
  - **可能失效场景**：CP 任务极端依赖低延迟 syscall 且 probe 失败频繁。
  - **证据强度**：强——0.7% DP overhead、3.1× VM 启动。
- **假设 1**：BlueField-3、Intel IPU、CIPU 等均可编程 I/O accelerator 实现 probe。
  - **证据强度**：中——多平台声明，细节因平台而异。

## 核心方法

**Tai Chi**：hybrid virtualization——vCPU 与 pCPU 同 OS；CP 跑 vCPU，DP 跑 pCPU。

- **Workload probe**（硬件+软件）：预测 I/O 到达，预先 schedule vCPU
- **µs-scale preemption**：打断 CP 长临界区
- **IPI 扩展**：vCPU/pCPU 原生 IPC，零 CP 代码修改

## 设计取舍

- **取舍 1**：虚拟化换调度灵活性，依赖硬件 probe 消除传统 vCPU 调度税。
- **取舍 2**：聚焦 SmartNIC 场景，非通用 host LC+BE scheduler。
- **边界条件**：DPDK/SPDK 类 DP；CP 与 DP 同 SNIC SoC。

## 实验与结果

- VM 启动：**3.1×**（达 SLO）
- DP 平均开销：**0.7%**
- 生产三年部署，百万级 server fleet 日常可见收益
- 支持 NVIDIA BlueField-3、Intel IPU、阿里 CIPU 等

## Critical Analysis

### 论证链条

生产 characterization（Fig. 2/3）→ 五约束 C1–C5 → hybrid virt + probe 逐一破解，工程故事完整。三年 production 是强证据。

### 假设压力测试

- DP 负载从「大多空闲」转向 AI inference 满载时是否仍安全？
- Probe 误判的 tail latency 分布未细披露。
- 跨云厂商 SNIC 异构性导致 probe 移植成本。

### 实验可信度

Production 数据权威。0.7% 是平均值，P99 DP impact 未强调。对比 prior co-scheduling baseline 在 SNIC 上实验有限。

### 系统性缺陷

论文未讨论：CP 安全隔离（恶意 vCPU）；SNIC 固件升级与 Tai Chi 协同；multi-tenant DP 公平性。

## 局限与 Future Work

- **局限 1**：依赖 I/O 可预测性，持续高负载 DP 收益下降。
- **局限 2**：平台特定 probe 实现。
- **Future work 1**：online 学习 probe，适应 DP traffic 分布漂移。

## 相关

- **相关概念**：SmartNIC、[[DPDK]]、virtualization、control/data plane
- **同类系统**：AWS Nitro、Azure SmartNIC、阿里 CIPU
- **同会议**：[[SOSP-2025]]