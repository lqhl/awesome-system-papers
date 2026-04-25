---
type: paper
name: Rhone
full_title: Emulating Space Computing Networks with Rhone
authors: [Liying Wang, Qing Li, Yuhan Zhou, Zhaofeng Luo, Donghao Zhang, et al.]
venue: ATC
year: 2025
tags: [satellite-network, emulator, space-computing, leo, container]
source_pdf: "[[atc2025-wang-liying.pdf]]"
source_md: "[[atc2025-wang-liying]]"
---

# Emulating Space Computing Networks with Rhone (ATC 2025)

> **一句话总结**：面向 SCN（Space Computing Network）的两阶段 emulator——离线建模 + 在线容器执行；单节点 700 卫星，power/computation 误差 <5%、温度误差 1.3–2.5°C。

## 问题

LEO 卫星正从单纯通信节点演化为 COTS 计算 + 星座组网（Starlink、Planet Dove 等），出现「Space Computing Network」新范式。但 SCN 应用难设计、难评估：真实卫星贵（小卫星发射 ~\$150K）；现有平台都欠 fidelity——物理 setup 不可扩、analytical simulator（Cote、StarPerf、Hypatia）缺真实软硬件栈、emulator（Celestial、StarryNet）不建模能耗/热/COTS 异构性。SCN 独特的两个特征——能耗+热约束、星座网络动态性——是评估应用的关键。

## 核心方法

两阶段架构：

- **离线建模**：用 Tiansuan / BUPT-1 真卫星 telemetry（800K+ 时间戳条目）拟合 5 个模型。
  - **Power Model**：harvest 端 $P_h = S\eta I_d L_d A \cos\theta$；consumer 端按 Markov-based（多功率档随机切换）和 function-based（X-band 链路 $P_{tr}^{idle} + w_{tr} d r_{tr}$、计算 $P_c = P_s(f) + U \cdot P_d(f) + P_l(T_{hottest})$）两种 pattern。
  - **Thermal Model**：Finite Element Analysis (FEA) 在 SolidWorks 解 $\rho c \frac{\partial T}{\partial t} = \nabla \cdot (k\nabla T) + q'''$，用 implicit time discretization。
  - **Computation Model**：hardware-in-the-loop chip mirroring——拆掉散热风扇的真 COTS 板（Raspberry Pi、Atlas 200 DK）跑应用，cyclic stress 收 satPerfTable（温度↔延迟），容器内重做收 emuPerfTable（资源↔延迟），Earth-based overheat 与 in-space 误差小。
  - **Orbit + Network Model**：与 StarryNet 类似的 ISL/GSL 可见性 + 时延。
- **在线容器执行**：每颗卫星 = 1 个 state manager + 多个容器（每容器代表一颗 COTS chip）。Satellite COTS Aligner (SCA) 查 satPerfTable 拿到目标延迟、再查 emuPerfTable 决定 cgroup CPU/GPU share；GPU 通过拦截 CUDA driver API 限速。Satellite Network Aligner (SNA) 在 StarryNet docker network 之上加节点粒度内部多 SoC、用 power/thermal model 决定 node failure（替代 StarryNet 的随机 failure）。

## 关键结果

- 单物理节点（双 Xeon E5-2670 v3、64GB RAM）支持 172/348/720 颗卫星，CPU/内存开销与 StarryNet 持平或更低（720 颗时 37.7% CPU、24.5% mem）。
- power 与 computation 模型误差 <5%，thermal 模型平均误差 1.3–2.5°C。
- 两个 case study：satellite network energy drain attack（malicious traffic 触发电池快速耗尽）、real-time Earth observation（直传 vs 压缩 vs onboard filter vs onboard inference 4 策略对比）。
- 4500 行 Python/C# 实现。

## 相关

- **相关概念**：Satellite Constellation、LEO Network、COTS Hardware、Container Emulation、Finite Element Analysis
- **同类系统**：StarryNet、Celestial、Hypatia、Cote、StarPerf
- **同会议**：[[ATC-2025]]
