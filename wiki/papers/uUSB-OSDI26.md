---
type: paper
name: µUSB
full_title: "µUSB: Practical and Safe USB Driver Reuse for Arm TrustZone"
authors: [Xuankai Zhang, Sijin Li, Pei Meng, Meng Wang, Yongzhao Zhang, et al.]
venue: OSDI
year: 2026
tags: [trustzone, usb, driver-specialization, tee, program-analysis]
source_pdf: "[[osdi26-zhang-xuankai.pdf]]"
source_md: "[[osdi26-zhang-xuankai]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# Arm TrustZone 的实用安全 USB 驱动复用（OSDI 2026）

> **原题**：µUSB: Practical and Safe USB Driver Reuse for Arm TrustZone

> **一句话总结**：µUSB对normal-world完整USB driver做mutational record，沿concrete traces静态lift出device-specific FSM/template，再在TEE replay小型driver；覆盖4 USB classes/6 devices，near-native性能且recorder overhead仅2.3%。

## 问题与动机

TrustZone secure I/O缺USB；将Linux USB stack塞进TEE扩大TCB，复杂protocol/DMA/vendor variants又难重写micro-driver。

## 关键观察 / 隐含假设

- USB control/data interaction由高度deterministic FSM驱动。
- 对目标device/use case，少量mutation traces可覆盖必要states。
- lifted driver只能执行已记录/验证interaction，缩小TCB。

## 核心方法

record阶段在VM/real driver上变异input并抓取MMIO/DMA/control flow；program analysis用trace约束源码，lift出USB driver template与state transitions；TEE runtime按template replay并验证device response。application只获得窄typed API。

## 实验与结果

- **设置**：storage/video/audio/HID六设备，对比native和Circle driver，以throughput/latency、driver size、analysis overhead为指标（§6）。
- camera最高比native快26%，HID平均4.5×；recorder overhead 2.3%。
- template generation平均56.9s；driver storage比full stack小12×–116×。

## 论断—证据表

| 论断 | 证据 | 边界 | 置信度 |
|---|---|---|---|
| record-lift-replay生成可用driver | 图 7/9 | 4 classes/6 devices | 强 |
| TCB显著缩小 | 表 7 | specialized use cases | 强 |

## 批判性分析

### 论证链条

利用USB FSM deterministic属性把reuse转为specialization，性能/size都与目标一致。

### 假设压力测试

未记录error/recovery state、malicious device或firmware变化会离开template coverage；trace completeness难证明。

### 实验可信度

设备类别多且端到端app可用，但每类样本少，安全性依赖analysis soundness。

## 局限与后续工作

- coverage proof、USB fuzzing与hotplug/error recovery。
- 更多vendor/classes与DMA/IOMMU攻击。

## 相关

- **相关概念**：[[TrustZone]]、[[USB]]、[[Driver-Specialization]]、[[Trusted-Execution-Environment]]
- **同会议**：[[OSDI-2026]]
