---
type: paper
name: Miralis
full_title: "The Design and Implementation of a Virtual Firmware Monitor"
authors: [Charly Castes, François Costa, Neelu S. Kalani, Timothy Roscoe, Nate Foster, Thomas Bourgeat, Edouard Bugnion]
venue: SOSP
year: 2025
tags: [firmware, virtualization, riscv, tee, security-monitor, formal-verification]
source_pdf: "[[3731569.3764826.pdf]]"
source_md: "[[3731569.3764826]]"
---

# The Design and Implementation of a Virtual Firmware Monitor (SOSP 2025)

> **一句话总结**:提出「虚拟固件监控器」(VFM)这一新类系统软件,用经典 trap-and-emulate 软件虚拟化把未修改的厂商 RISC-V 固件降级到 user-space 运行,从而把 firmware 移出 [[TEE]] 安全监控器的 TCB;原型 Miralis(6.2K LoC Rust)在 VisionFive 2、HiFive Premier P550 上相对原生执行零性能退化,并用 Kani 符号执行验证了指令模拟与内存保护的关键组件,发现并修复 21 个 bug。

## 问题

现代 [[TEE]](enclave、confidential VM)依赖一个最高特权的 security monitor 作为信任根,但它与厂商固件(RISC-V M-mode / Arm EL3)co-located 在同一特权级,固件几十万行代码里的任何 bug/漏洞都能威胁整个平台。已有的分离方案如 Dorami 需要改固件二进制并做 scan,厂商不买账就没用;Arm TrustZone 虽然分出 EL3,但固件仍比 monitor 权限高,本质问题未解。

## 核心方法

**Virtual Firmware Monitor (VFM)**:把经典虚拟化延伸到最高特权级。
- 用 Popek & Goldberg 的 trap-and-emulate 理论分析:RISC-V 的 M-mode 是可虚拟化的(所有 sensitive 指令都是 privileged),Arm 的 EL3 不是(如 cpsid 在 U-mode 被静默当 no-op)
- 把厂商固件当成运行在 U-mode 的 guest,虚拟一个 vM-mode 给它;OS(S-mode、U-mode)原生跑不受影响
- VFM 只做隔离,不做资源复用,因此比传统 hypervisor 简单得多

**Miralis 实现**(RISC-V,Rust,6.2K LoC):
- 支持 12 条 privileged 指令、84 个 CSR 的 shadow copy 与 emulation
- 用 RISC-V PMP(Physical Memory Protection)做内存隔离——为固件提供虚拟 PMP,物理 PMP 中 Miralis 的规则优先级永远更高
- **Fast path offloading**:观察到 VisionFive 2 上 99.98% 的 trap 都是 5 种 RISC-V 标准功能(timer 读、timer 设置、misaligned load/store、IPI、remote fence)的软件仿真,这些可以直接由 Miralis 处理而不走固件,把 boot 阶段世界切换从 5500/s 降到 1.17/s,性能退化消失
- 可扩展支持自定义隔离策略:已移植 Keystone(enclave)和 ACE(confidential VM)两个 security monitor

**形式化验证**:用 Kani Rust 模型检查器 + 高质量 Sail ISA spec 做穷举符号执行,验证指令 emulation 和内存隔离,开发过程中捕获 21 个 bug。

## 关键结果

- 首个 VFM 实现 Miralis,开源、Rust 编写、支持自定义 isolation 策略
- 在 VisionFive 2、HiFive Premier P550 上相对原生执行无性能退化
- Keystone 和 ACE 两个 security monitor 成功移植到 Miralis 之上
- 开发过程发现并修复 21 个 bug(虚拟中断丢失、PC 溢出、越界访问等)
- 无须修改厂商固件二进制即可部署

## 相关

- **相关概念**:[[TEE]]、[[Trap-and-Emulate]]、[[RISC-V]]、[[Formal-Verification]]、[[Confidential-Computing]]
- **同类系统**:Keystone、ACE、Dorami、TF-A、OpenSBI
- **同会议**:[[SOSP-2025]]
