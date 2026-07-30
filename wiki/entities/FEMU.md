---
type: entity
kind: tool
aliases: [Fast-Emulator-for-NVMe-SSDs]
status: active
last_updated: 2026-07-18
tags: [storage, nvme, ssd, emulation, benchmark]
---

# FEMU

> FEMU 是本资料库中使用的 NVMe SSD 仿真平台，用于在可控设备行为下对存储管理思想进行原型设计或评估。

## 是什么

FEMU 为在生产 SSD 上进行困难、昂贵或观察不充分的实验提供了一个软件测试平台。论文可以在硬件部署之前改变设备参数、检查主机/设备交互以及评估算法。

仿真结果是有关建模行为的证据，而不是生产设备行为的证明。固件策略、媒体可变性、排队、磨损和控制器实现可以改变真实硬件的结论。

## 关键观察 / 隐含假设

- **观察**：受控仿真有助于将存储机制与硬件噪声隔离。 [[Cylon-FAST26]] 和 [[WARP-FAST26]] 使用此类评估上下文进行存储路径分析。
- **假设**：所选择的设备模型保留了与系统声明相关的瓶颈。 [[Xerxes-FAST26]] 说明了为什么必须区分模拟器假设和真实设备验证。

## 演进时间线

- 2026 FAST：[[Cylon-FAST26]] — evaluates a storage-system mechanism with controlled device behavior.
- 2026 FAST：[[WARP-FAST26]] — uses storage evaluation infrastructure for device-path analysis.
- 2026 FAST：[[Xerxes-FAST26]] — highlights emulator versus deployment-boundary considerations.

## 相关概念

- [[NVMe]]、[[ZNS]]、[[Garbage-Collection]]、[[Write-Amplification]]

## 相关论文

- [[Cylon-FAST26]] — storage-system evaluation.
- [[WARP-FAST26]] — storage-path evaluation.
- [[Xerxes-FAST26]] — emulator and device-boundary analysis.
