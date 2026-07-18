---
type: entity
kind: tool
aliases: [Fast-Emulator-for-NVMe-SSDs]
status: active
last_updated: 2026-07-18
tags: [storage, nvme, ssd, emulation, benchmark]
---

# FEMU

> FEMU is an NVMe SSD emulation platform used in this corpus to prototype or evaluate storage-management ideas under controllable device behavior.

## 是什么

FEMU provides a software testbed for experiments that would be difficult, expensive, or insufficiently observable on a production SSD. Papers can vary device parameters, inspect host/device interactions, and evaluate algorithms before hardware deployment.

An emulation result is evidence about the modeled behavior, not proof of production-device behavior. Firmware policies, media variability, queueing, wear, and controller implementation can change the conclusion on real hardware.

## 关键观察 / 隐含假设

- **观察**：controlled emulation helps isolate a storage mechanism from hardware noise. [[Cylon-FAST26]] and [[WARP-FAST26]] use such evaluation contexts for storage-path analysis.
- **假设**：the chosen device model preserves the bottleneck relevant to the system claim. [[Xerxes-FAST26]] illustrates why emulator assumptions and real-device validation must be distinguished.

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
