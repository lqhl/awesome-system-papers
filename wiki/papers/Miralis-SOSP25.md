---
type: paper
name: Miralis
full_title: "The Design and Implementation of a Virtual Firmware Monitor"
authors: [Charly Castes, François Costa, Neelu S. Kalani, Timothy Roscoe, Nate Foster, et al.]
venue: SOSP
year: 2025
tags: [firmware, tee, risc-v, virtualization, security, verification]
source_pdf: "[[3731569.3764826.pdf]]"
source_md: "[[3731569.3764826]]"
---

# The Design and Implementation of a Virtual Firmware Monitor (SOSP 2025)

> **一句话总结**：vendor firmware 与 TEE security monitor 同处最高特权是 TCB 膨胀根因；Miralis 用 Virtual Firmware Monitor 在 RISC-V 上无修改运行 M-mode firmware 于用户态，配合可选 fast-path offload，性能相对 native **无退化**，Kani 符号执行在开发期修 21 个 bug。

## 问题与动机

[[TEE]]/enclave/CVM 依赖 security monitor，但多数平台上它与 **vendor firmware**（Arm EL3/RISC-V M-mode）同处最高特权，百万行级闭源 firmware bug 可危及整个平台。[[Dorami]] 需 firmware 重构与 binary scanning， adoption 难。作者问：能否对 **unmodified** vendor firmware 应用 least-privilege？

## 关键观察 / 隐含假设

- **观察 1**：按 Popek-Goldberg 定义，RISC-V M-mode **可虚拟化**；Arm EL3 则不行——VFM 路径在 RISC-V 上可行。
  - **依赖假设**：平台 MMIO/系统寄存器文档完备；硬件遵守规格。
  - **可能失效场景**：undocumented platform-specific 指令/寄存器使 emulation 不完整；x86 因 microcode/SMM 等被论文排除。
- **观察 2**：多数 firmware 功能不需 unfettered 特权；拦截特权资源访问即可 decouple functionality from isolation enforcement。
  - **依赖假设**：fast-path offload 可覆盖高频 optional-feature 仿真开销。
  - **可能失效场景**：严重依赖 M-mode 专属特性的 firmware 可能无法全仿真。
- **观察 3**：可用现有 executable ISA spec（Sail 等）表达 VFM 规格，配合 Kani 做 instruction emulation/memory protection 穷尽检查。
  - **依赖假设**：规格覆盖范围与 VFM 实现同步维护。
  - **证据强度**：中。找到 21 bug，但非 full security proof。

## 核心方法

**Virtual Firmware Monitor (VFM)** 两组件：

1. **Firmware virtualization**：经典软件虚拟化拦截 M-mode 特权访问；vendor firmware 以 user-space 实体运行。
2. **Fast-path offloading（可选）**：常见操作绕过 deprivileged firmware，减轻仿真开销。

**Miralis**（Rust，RISC-V）：可插拔 isolation policy；已 port [[Keystone]]、[[ACE]] security monitor；平台含 VisionFive 2、HiFive Premier P550、OpenSBI 等 **unmodified** firmware。

验证：Kani model checker 针对 emulation 与 memory isolation（非端到端 security theorem）。

## 设计取舍

- **Deprivilege vs refactor firmware**：零 vendor 改动，但 VFM 成为新 TCB。
- **Symbolic execution vs full verification**：实用 assurance，非 seL4 级定理。
- **RISC-V focus vs portable x86**：可落地商用板卡，但生态覆盖窄。
- **Performance-neutral goal**：不加速 firmware；安全不付性能税。

## 实验与结果

- 广泛 application benchmark：**无性能退化** vs native firmware execution。
- 开发期 Kani 发现 **21** bugs（lost virtual interrupt、PC overflow、OOB 等）。
- 成功虚拟化多平台 **unmodified** vendor/open firmware。
- 扩展支持 enclave + CVM 与 Keystone/ACE 集成。

## Critical Analysis

### 论证链条

「M-mode virtualizable → VFM deprivilege → TEE TCB 缩小」逻辑清晰，但 **security guarantee** 链条止于 pragmatic testing + 部分 symbolic verification，未形式化 end-to-end isolation theorem（论文明确非目标）。

### 假设压力测试

- 闭源 firmware 可能触发未文档化行为，emulation 缺口即安全缺口。
- Fast-path offload 若实现错误可能变成 privilege escalation 通道——需严格 audit。
- 仅 RISC-V；Arm EL3 不可虚拟化意味着主流 server 路径不同。

### 实验可信度

- 性能对比全面；安全评估偏开发期 bug 发现，缺 red-team 渗透量化。
- 与 Dorami/TrustZone 隔离对比定性为主。

### 系统性缺陷

- 论文未讨论 VFM 自身漏洞响应与 firmware 热更新协同。
- Side-channel、transient execution 明确 out of scope。
- 多核 firmware /auxiliary core firmware 未覆盖。

## 局限与 Future Work

- **局限**：RISC-V only；非 full verification；不含 x86/Arm EL3；辅助核 firmware out of scope。
- **Future work**：更大规模 symbolic proof；Arm 替代架构路径；formal TCB reduction 度量。

## 相关

- **相关概念**：[[TEE]]、[[Keystone]]、Firmware、[[RISC-V]]、Trusted-Computing-Base
- **同类系统**：Dorami、[[seL4]]、ARM TF-A、OpenSBI
- **同会议**：[[SOSP-2025]]