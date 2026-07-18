---
type: paper
name: DeCl
full_title: "Deterministic Client: Enforcing Determinism on Untrusted Machine Code"
authors: [Zachary Yedidia, Geoffrey Ramseyer, David Mazieres]
venue: OSDI
year: 2025
tags: [sandboxing, determinism, smart-contracts, sfi, x86, arm64]
source_pdf: "[[osdi25-yedidia.pdf]]"
source_md: "[[osdi25-yedidia]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# Deterministic Client: Enforcing Determinism on Untrusted Machine Code (OSDI 2025)

> **一句话总结**：智能合约等需 adversarial 确定性，传统 WASM/EVM 解释器 TCB 大；DeCl 把 SFI 式机器码验证扩展到确定性子集（x86-64/Arm64），配合确定性 metering 与 LFI 位置无关隔离，SPEC 子集 ~20% 开销，Groundhog 集成相对解释 **~30×**、相对 JIT **~2×**，沙箱启动 **<15µs**。

## 问题与动机

确定性执行目前只能靠定义 IL 的解释器/JIT（WASM、eBPF、EVM），需信任整个翻译栈。SFI 擅长内存隔离（NaCl/LFI），但无人对原生机器码做确定性保证。DeCl 目标：不信任编译器，仅信任小型 verifier + rewriter。

## 关键观察 / 隐含假设

- **观察 1**：确定性可像 memory-safety 一样用「只允许已知语义指令」的静态分析强制执行。
  - **依赖假设**：runtime 禁用 SMP、提供确定性 syscall API、初始内存清零。
  - **可能失效场景**：需浮点确定性子集时当前仅整数+SIMD（论文留 future）。
- **观察 2**：传统定时器 interrupt 使抢占点非确定；需 branch metering 或指令计数 metering。
  - **证据强度**：强——两种机制单独描述并评估。
- **假设 1**：x86 需 32-byte aligned bundles + W⊕X 防 jump-into-instruction；Arm64 固定宽指令 + W⊕X 足够。
  - **可能失效场景**：编译器未配合 bundle padding 则验证拒绝。

## 核心方法

**验证器**：拒绝非确定性指令（RDRAND、原子 load/store 对等）；x86 对 SHLD/BSF 等 guard 未定义输入。

**Rewriter**：LLVM/GCC 汇编后处理，产可验证二进制。

**Metering**：分支计数或指令预算确定性抢占。

**+LFI**：位置无关 sandbox，Linux 进程内多沙箱，快速启动。

**Groundhog**：替换 WASM 解释路径跑原生合约。

## 设计取舍

- **取舍 1**：拒绝大量指令与浮点，换小 TCB 与近原生速度。
- **取舍 2**：torn store 遇页边界直接终止程序，简化 Arm 语义。
- **边界条件**：Armv8.0 + 16KiB 页；x86 BMI2（SHRX）用于 branch metering。

## 实验与结果

- SPEC 2017 子集 + metering + SFI：**~20%** CPU overhead（x86/Arm64）。
- Groundhog：vs 解释 **~30×**，vs JIT **~2×**；load+execute **<15µs**。
- 17 个 Linux bug/CVE 复现路径与 KRR 不同领域——DeCl 侧为合约引擎场景。

## Critical Analysis

### 论证链条

威胁模型清晰 → 指令枚举/BDD → rewriter 产码 → SPEC 与 Groundhog 数字，工程完整。确定性跨微架构依赖 ISA 子集假设，新 CPU 扩展需更新 verifier。

### 假设压力测试

侧信道：论文称去除 timer/原子后缓解，但 cache 等需 runtime 配合。大型合约是否触及指令预算边界行为一致？浮点 ML 合约不在范围。

### 实验可信度

SPEC 子集非全套；Groundhog 对比条件需读 §6 配置。与 WASM SIMD 提案演进的对照在 related work。

### 系统性缺陷

验证拒绝率高时开发者调试成本；论文未讨论 formal proof of verifier 自身。

## 局限与 Future Work

- **局限 1**：整数子集，无 general FP determinism。
- **Future work 1**：可验证确定性浮点子集。
- **Future work 2**：与 eBPF 策略统一的跨平台 policy 语言。

## 相关

- **同会议**：[[OSDI-2025]]
