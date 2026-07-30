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
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# Atmosphere：使用 Rust 和 Verus 进行实用验证的内核（SOSP 2025）

> **原题**：Atmosphere: Practical Verified Kernels with Rust and Verus

> **一句话总结**：Atmosphere 用 [[Verus]] 验证 6,048 行 Rust microkernel，proof:code 为 3.32:1；完整验证在 i9-13900HX laptop、32 threads 下少于 20 秒，在 CloudLab c220g5、8 threads 下为 1分07秒。作者以自报开发 effort 论证实用性，但摘要的少于 2.5 person-years / 1.5 verified 与 §6.3 的约 2 / 14 months 存在内部差异（§6.1–6.3，Table 1–2）。

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
- **Microkernel scope vs monolithic Linux 对标**：功能集适中；论文仍在 §6.5–6.6 评估 network/storage/application performance，但不覆盖 Linux 生态完整性。
- **Big-lock multi-CPU**：简化验证，牺牲 scale-out performance。

## 实验与结果

- **Verification time**：完整 verification 在 CloudLab c220g5、8 threads 为 1分07秒；i9-13900HX laptop 上 1 thread 为 47 秒、32 threads 少于 20 秒（§6.1，Fig. 2/Table 2；compiler time 只有定性比较）。
- **Proof effort**：20.1K proof lines / 6,048 executable lines，即 3.32:1；seL4 20:1、CertiKOS 14.9:1、SeKVM 6.9:1、NrOS 10:1、VeriSMo 2.0:1（§6.1，Table 1；assurance scope 与语言不同，非 apples-to-apples）。
- **Flat permission ablation**：page-table proof:code 为 4.4:1，NrOS 为 13.3:1；single-thread verification 快超过 3×，representative mapping proof 约 30 vs 200 lines（§6.2，Table 2；只比较一个 subsystem）。
- **Kernel microbenchmarks**：call/reply 为 1,058 cycles，seL4 为 1,026；page map 为 1,984 vs 2,650 cycles（§6.4，Table 3；c220g5 under KVM，page-map syscalls 不完全等价）。
- **I/O/app path**：batch-32 network driver 达 14.2 Mpps line rate；NVMe write 232K IOPS、比约 256K device max 低 10%；Maglev atmo-c2 13.3 Mpps vs DPDK 9.72，httpd 99.4K req/s vs Nginx 70.9K（§6.5–6.6，Fig. 4–7；polling custom apps 与特定硬件）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| Atmosphere 的 full verification 可在 laptop 上少于 20 秒完成 | §6.1, Fig. 2/Table 2 | i9-13900HX；32 threads；Verus/Z3；6K-line codebase | medium |
| Proof:code ratio 为 3.32:1 | §6.1, Table 1 | 跨系统 assurance scope/语言不同；非 controlled comparison | medium |
| Flat permission design 相对 NrOS 降低 page-table proof effort | §6.2, Table 2 | one subsystem；comparable 4-level goals；实现仍不同 | medium |
| IPC/page-map cycles 与 seL4 接近或更低 | §6.4, Table 3 | c220g5 under KVM；syscalls 不完全等价 | medium |
| Selected userspace driver/apps 达到 competitive I/O throughput | §6.5–6.6, Fig. 4–7 | 10GbE/NVMe；polling custom apps；selected batch sizes | medium |

## 批判性分析

### 论证链条

「Verus + 特定设计选择降低 verified kernel 成本」由 timing/LOC/effort 数字支撑，但 **端到端 security theorem**（含 hardware model）链条未闭合——是 functional refinement，不是 full seL4 级 assurance stack。

### 假设压力测试

- Big-lock 与单笔记本验证时间不代表 many-core scale-out 或更大 ghost state。
- Boot 明确属于 trusted initialization；userspace drivers 未验证，但不自动属于每个 isolation domain 的 TCB，实际边界取决于部署与 capability 配置（§5）。
- Verus/Z3 版本漂移对 proof maintenance 的长期成本——论文未 longitudinal 数据。

### 实验可信度

- 贡献在 methodology/effort，非 benchmark throughput。
- 与 seL4/CertiKOS 的 feature/assurance 对比偏定性。
- 缺少第三方独立 re-verification 报告。

### 系统性缺陷

- §5 明确列出 Verus frontend、Z3、Rust compiler/core、assembly/trusted Rust、bootloader、CPU/firmware/hardware 等 TCB；该边界仍然较大，但并非未讨论。
- Side-channel、DMA、IOMMU 正确性的硬件依赖未形式化。
- 生产部署路径（更新、热修、驱动生态）未讨论。

## 局限与后续工作

- **局限**：big-lock；boot/drivers 未验证；functional correctness only。
- **Future work**：扩展 verified 子系统；inductive proof 自动化；与 CHERI 等硬件协同。

## 相关

- **相关概念**：[[seL4]]、[[Verus]]、Separation Kernel、Refinement Verification
- **同类系统**：[[seL4]]、CertiKOS、IronFleet、Hyperkernel
- **同会议**：[[SOSP-2025]]
