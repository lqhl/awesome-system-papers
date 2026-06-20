---
type: paper
name: Atmosphere
full_title: "Atmosphere: Practical Verified Kernels with Rust and Verus"
authors: [Xiangdong Chen, Zhaofeng Li, Jerry Zhang, Vikram Narayanan, Anton Burtsev]
venue: SOSP
year: 2025
tags: [microkernel, formal-verification, rust, verus, separation-kernel]
source_pdf: "[[3731569.3764821.pdf]]"
source_md: "[[3731569.3764821]]"
---

# Atmosphere: Practical Verified Kernels with Rust and Verus (SOSP 2025)

> **一句话总结**：用 [[Verus]] SMT 验证器在 Rust 中证明 microkernel 功能正确性（6K 行代码、proof:code 3.32:1、笔记本 <20s 验证），关键设计是 raw pointer + flat permission storage + 手动内存管理，使 feature-rich kernel 的验证成本接近 commodity 开发（约 2.5 person-years）。

## 问题与动机

[[seL4]] 等 verified kernel 需 11+ person-years 与大量形式化基础设施；Hyperkernel 等 push-button 方案又过度简化接口（如 open 必须指定 fd 号）。近年 [[Verus]] 等结合 linear types、permission reasoning 与 SMT 自动化，但能否验证 pointer-centric、递归数据结构密集的 production-grade kernel 仍是 open debate。

Atmosphere 要证明：**automated verifier 可实用地验证 low-level systems**，同时支持 mixed-criticality separation kernel 特性（multi-CPU、process/thread、IPC、VMA、IOMMU、container abstraction）。

## 关键观察 / 隐含假设

- **观察 1**：Rust 非线性类型对 cyclic kernel 结构不友好；拥抱 raw pointer + Verus permission pointers 反而比强行 idiomatic Rust 更易验证高性能结构（Linux 式 internal storage、reverse pointer O(1) 删除）。
  - **依赖假设**：Verus flat permission storage 可避免递归 proof 爆炸。
  - **可能失效场景**：更复杂子系统（网络栈、复杂 FS）可能重新触达 inductive proof 难点。
- **观察 2**：将子系统内所有 permission pointer **扁平** 存到顶层 map，可用非递归规格编码无界树/页表性质，分离 structural vs non-structural 论证。
  - **依赖假设**：全局 flat view 不破坏性能与模块化开发。
  - **可能失效场景**：极大地址空间下 ghost state 规模与验证时间可能超线性增长——论文仅报告 <20s，规模外推未测。
- **观察 3**：Rust 自动内存管理在 kernel 规格与实现间制造语义 gap（non-deterministic syscall spec、leak）；显式 manual alloc/free + leak freedom proof 更干净。
  - **依赖假设**：manual lifetime 可被 Verus 完全覆盖；Rust ownership 仍约束 tracked ghost 变量。
  - **可能失效场景**：复杂 cyclic object graph 的 leak freedom proof 维护成本随功能增长。

## 核心方法

Atmosphere = verified microkernel + separation kernel policies：

- 全 Rust 实现，**functional correctness** = refinement of high-level abstract spec（ghost state side-by-side）。
- 6K executable lines + 20.1K proof（14.3K spec + 5.8K hints）；2.9K lines 顶层 syscall 抽象规格。
- 不依赖 Rust std 未验证类型；只信 Verus native types。
- 演示 mixed-criticality **non-interference**：不同 container group 可定义自定义隔离语义，并通过 verified service 通信。
- Boot/init、用户态 driver、benchmark 等非验证部分另计 ~1 person-year。

## 设计取舍

- **Raw pointers + flat permissions vs elegant Rust**：验证可扩展，但代码风格接近 unsafe C。
- **Static verification vs runtime assurance**：强保证，但不覆盖 timing/side-channel/硬件 bug。
- **Microkernel scope vs monolithic Linux 对标**：功能集适中，I/O 性能与生态未是目标。
- **Big-lock multi-CPU**：简化验证，牺牲 scale-out performance。

## 实验与结果

- 验证时间 **<20s**（现代笔记本），短于完整 kernel 编译时间，支持 interactive verify 循环。
- Proof-to-code ratio **3.32:1**，低于 seL4 等 prior work（作者 claim）。
- 总开发 **<2.5 person-years**（verified 部分 ~1.5 PY）。
- 支持 processes/threads/IPC/VMA/IOMMU/containers 等特性（论文 §1）。

## Critical Analysis

### 论证链条

「Verus + 特定设计选择降低 verified kernel 成本」由 timing/LOC/effort 数字支撑，但 **端到端 security theorem**（含 hardware model）链条未闭合——是 functional refinement，不是 full seL4 级 assurance stack。

### 假设压力测试

- Big-lock 与单笔记本验证时间不代表 1024-core 或更大 ghost state。
- 未验证 boot/user driver 仍是 TCB 一部分。
- Verus/Z3 版本漂移对 proof maintenance 的长期成本——论文未 longitudinal 数据。

### 实验可信度

- 贡献在 methodology/effort，非 benchmark throughput。
- 与 seL4/CertiKOS 的 feature/assurance 对比偏定性。
- 缺少第三方独立 re-verification 报告。

### 系统性缺陷

- 论文未讨论 verified code 与 Rust/LLVM/硬件编译链的 trust boundary。
- Side-channel、DMA、IOMMU 正确性的硬件依赖未形式化。
- 生产部署路径（更新、热修、驱动生态）未讨论。

## 局限与 Future Work

- **局限**：big-lock；boot/drivers 未验证；functional correctness only。
- **Future work**：扩展 verified 子系统；inductive proof 自动化；与 CHERI 等硬件协同。

## 相关

- **相关概念**：[[seL4]]、[[Verus]]、Separation Kernel、Refinement Verification
- **同类系统**：[[seL4]]、CertiKOS、IronFleet、Hyperkernel
- **同会议**：[[SOSP-2025]]