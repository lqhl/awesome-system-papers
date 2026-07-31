---
type: paper
name: Nested-SEV
full_title: "Nested SEV: Secure and Generic SEV Support for Nested Virtualization"
authors: [Kazuki Takiguchi, Kenichi Kourai]
venue: OSDI
year: 2026
tags: [confidential-computing, nested-virtualization, security]
source_pdf: "[[osdi26-takiguchi.pdf]]"
source_md: "[[osdi26-takiguchi]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 嵌套虚拟化的安全通用 SEV 支持
> **原题**：Nested SEV: Secure and Generic SEV Support for Nested Virtualization

## 问题与动机

现有 AMD SEV nested virtualization 要么无法同时保护 L1 VM，要么只支持单个 L2 VM；virtual cloud 因而必须在嵌套能力与 confidential VM threat model 之间取舍。

## 关键观察 / 隐含假设

- L2 可使用独立 SEV context 以同时不信任 L0/L1，也可共享 L1 context 以信任 L1、换取管理能力。
- physical AMD Secure Processor 可安全 multiplex 多层 context，无需在不可信 L0 中模拟。
- 假设 AMD SEV/ES/SNP 提供的底层完整性边界成立。

## 核心方法

[[Nested-SEV]] 提供两种模式：SEV virtualization 以独立 context 隔离 L2，SEV passthrough 通过 context decoupling 让 L1/L2 共享 context。emulation-less multiplexing 直接在 AMD-SP 管理多层 context，并支持多个 L2 VM。

## 实验与结果

原型覆盖 KVM、BitVisor、Xen 三类 L1 hypervisor 和 SEV0、SEV-ES、SEV-SNP；相对 single-level virtualization，各组合平均 performance degradation 为 0.9–30%（§7，图 8–13）。KVM passthrough 的 boot-time overhead 在 SEV0/SEV-ES 分别为 12%/49%；边界随 threat model 与 workload 而变。

## 论断—证据表

| 论断 | 证据 | 边界 | 置信度 |
|---|---|---|---|
| 同一设计可支持两种信任模型 | virtualization 与 passthrough 均在三类 hypervisor 实现 | 所测 SEV variants | 强 |
| 安全增强代价依 workload 可控 | 平均 degradation 0.9–30% | micro/memory/network/web workload | 中 |

## 批判性分析

### 论证链条
设计将“L1 是否可信”显式变成 context 隔离策略，再以 AMD-SP multiplexing 避免把根信任移回 L0，安全目标与机制一致。

### 假设压力测试
SEV 本身不隐藏 access pattern；设备直通、side channel、AMD-SP compromise 和复杂 live migration 超出主要边界。

### 实验可信度
三种 hypervisor 与完整 workload breakdown 覆盖广，但不同模式 threat model 不同，不能仅按性能横向排名。

## 局限与后续工作

- 优化 network 与 VM-exit 密集 workload，并改善 SEV-SNP boot validation。
- 扩展设备虚拟化、迁移与远程 attestation 的组合证明。

## 相关

- [[OSDI-2026]]
- [[Confidential-Computing]]
- [[Nested-Virtualization]]
