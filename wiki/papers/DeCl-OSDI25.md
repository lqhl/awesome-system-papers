---
type: paper
name: DeCl
full_title: "Deterministic Client: Enforcing Determinism on Untrusted Machine Code"
authors: [Zachary Yedidia, Geoffrey Ramseyer, David Mazieres]
venue: OSDI
year: 2025
tags: [sandbox, determinism, sfi, smart-contract, verifier]
source_pdf: "[[osdi25-yedidia.pdf]]"
source_md: "[[osdi25-yedidia]]"
---

# Deterministic Client: Enforcing Determinism on Untrusted Machine Code (OSDI 2025)

> **一句话总结**：DeCl 把 Software Fault Isolation 的二进制验证思路从「内存隔离」扩展到「执行确定性」，对 LLVM 编译出的 x86-64 / Arm64 机器码做一次静态验证 + 确定性计量（gas），让智能合约直接以原生速度跑，相比 WebAssembly JIT 快约 **2×**、相比解释器快约 **30×**，开销仅约 **20%**。

## 问题

智能合约需要**确定性**执行：所有节点必须复现同样的状态转移。传统做法是 WebAssembly / EVM bytecode + 可信 JIT/解释器，但 JIT 编译器 (如 Cranelift) 是一个大型受信任组件，曾出现过多个 CVE 级漏洞；解释器则慢几十倍。同时硬件不提供强制确定性的原语，所以只能软件实现。

作者要问：**能否像 SFI 那样，对直接从 LLVM/GCC 出的机器码做静态验证，让非受信编译器的输出安全地以原生速度执行**，同时保证确定性与有界终止？

## 核心方法

DeCl 由三部分组成：

**1. 确定性指令子集验证器**：对 Arm64 只允许 Armv8.0 base ISA 的 ~180 基础指令 + 430 SIMD 指令，拒绝 UNPREDICTABLE / UNDEFINED 指令（如条件原子、malformed SBZ、stxr 等）；对 x86-64，用 Fadec 定义一个可枚举的 BDD 子集（100 基础 + 125 SSE2 + BMI2 的 SHRX），进一步用数据流分析 (Algorithm 1) 确认任何 instruction 不会读到 undefined flag，并加 guard 屏蔽 SHLD/BSR 等特定输入下输出未定义的情况。借鉴 PittSFIeld 的 **32-byte aligned bundles** 防止跳到指令中间。

**2. 确定性计量（gas）**：硬件 PMU 的指令计数不确定，所以用保留寄存器 (x23 / %r12) 显式维护。两种方案：**branch-based metering** 在每个 basic block 结尾减 gas 并条件跳转；**timer-based metering** 结合非确定性 timer 与 gas counter，但通过 bundle 对齐和加载 SHRX 技巧保证被抢占点确定。

**3. 与 SFI 内存隔离结合**：与 LFI（软件 SFI 沙箱）共享地址空间并支持 position-oblivious 代码，每个沙箱只需 128 KiB code + 128 KiB data 的预分配区，通过 mmap 页别名让运行时写 sandbox code 不需要 mprotect，单次 load + execute + exit 只需 **15 µs (M2) / 2 µs (7950X)**。另有 CPU 模糊测试工具在 5+ 微架构上验证。

## 关键结果

- SPEC 2017 上 DeCl-LFI-timer 几何平均开销 **19.2% / 19.1%** (x64/A64)；branch-based **24–39%**；最轻量的 POC (SFI 隔离 + determinism，无 metering) 仅 9%
- 比 Wasmtime-fuel 快 **2×+**：metered 几何均开销 16% 对 76%（x64）；整数 benchmark 上
- 集成到 Groundhog 智能合约引擎替换 wasm3 解释器：合约内 Ed25519 验签吞吐显著提升；zk-proof (Groth16/Plonk) 验证相比 Wasmtime 快 **2×**、相比 Wasm3 快 **30×**
- 允许用户态在沙箱内自写 cryptography（传统方案只能用硬编码 precompile）
- 验证器极小可信代码基，不用再信任 LLVM/GCC

## 相关

- **相关概念**：[[SFI]]、[[LFI]]、[[WebAssembly]]、[[Smart-Contract]]
- **同类系统**：NaCl、PittSFIeld、Wasmtime、Wasm3、Groundhog
- **同会议**：[[OSDI-2025]]
