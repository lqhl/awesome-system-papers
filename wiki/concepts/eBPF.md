---
type: concept
aliases: [ebpf, extended BPF, BPF, eBPF programs, Berkeley Packet Filter]
last_updated: 2026-06-20
tags: [kernel, extensions, verifier, sandboxing, observability]
---

# eBPF

> extended BPF（eBPF）是 Linux 内核的可编程扩展机制：不可信 bytecode 经 in-kernel [[eBPF-Verifier]] 静态验证后，挂载在 tracepoint、kprobe、XDP、TC、struct_ops 等 hook 上，在特权上下文中安全执行；它把「改内核」变成「加载程序」，已成为存储策略、网络 dataplane、调度、虚拟化与可观测性的事实标准扩展面。

## 核心思想

eBPF 程序由用户态 loader（bpftool、libbpf）经 `bpf()` syscall 载入，verifier 对 bytecode 做符号执行，证明 **memory safety、type safety、有界执行、栈安全** 等性质后 JIT 执行。程序通过 **maps**（hash/array/ringbuf）与内核或用户态交换状态，通过 **helpers**（~200 个内核回调）访问网络包、page、block、调度等对象。

演进上 eBPF 已从 packet filter 扩展为通用 [[Kernel-Extensions]] 平台：**struct_ops** 允许替换内核算法（如 [[cache_ext-SOSP25]] 的 page cache eviction、[[sched_ext]] 的调度类）；**tracing** 支撑高频遥测（[[Loom-SOSP25]]）；**XDP/TC** 支撑 dataplane 加速；存储方向则有 page reclaim/prefetch 外置（[[PageFlex-ATC25]]）、NVMe 驱动 NDP resubmit（[[XRP]]/[[RosenBridge-FAST26]]）、嵌套虚拟化 hyperupcall（[[HyperTurtle-ATC25]]）。

核心张力始终存在：**表达力 vs verifier 可判定性**。interval/tristate 等廉价抽象导致大量安全程序被误拒（false reject），迫使 Cilium、SCX 等项目拆 program、双倍分配 buffer、写 inline asm 取悦 verifier（[[BCF-SOSP25]]、[[Rex-ATC25]]）；verifier 实现缺陷则可误接受不安全程序，造成提权与 [[KASLR]] 绕过（[[Veritas-SOSP25]]）。

## 为什么重要

SOSP/OSDI/ATC 2025–2026 论文共同描绘 eBPF 正从「网络加速补丁」升级为 **内核可扩展性的主战场**，接过了十年前 KVM 在 OS 社区的位置（[[SOSP-2025]] 会议页综述）。原因包括：

1. **部署现实**：Meta 每台服务器运行 50+ eBPF 程序（[[Veritas-SOSP25]]）；hyperscaler 需要不改应用、不重写 swap 栈即可外置 paging policy（[[PageFlex-ATC25]]）。
2. **性能敏感路径可编程**：page cache eviction 事件率与 I/O 同量级，policy 必须在 kernel 内执行，userspace dispatch alone 带来 **16–20%** 吞吐损失（[[cache_ext-SOSP25]]）。
3. **Verifier 成为独立研究对象**：BCF（proof-guided refinement）、Veritas（spec-based fuzz oracle）、Rex（language-based safety 替代 verifier）形成「证明 + fuzzing + 语言」三条主线。
4. **边界扩展**：bpftime 把 eBPF 验证与 ERIM 隔离带到用户态应用扩展（[[bpftime-OSDI25]]）；RosenBridge 则在虚拟化边界用 [[uBPF]] 替代 kernel eBPF 做 NDP offload（[[RosenBridge-FAST26]]）。

这些论文共同假设：**eBPF hook + verifier 沙箱** 是生产环境可接受的扩展契约；但当程序变大、逻辑变复杂时，verifier 的 scalability 与 language-verifier gap 会持续制造 usability 与安全双重风险。

## 关键观察 / 隐含假设

- **观察 1：eviction/reclaim 类策略必须在 kernel 内低开销执行，userspace offload 不经济。** [[cache_ext-SOSP25]] 量化 userspace dispatch baseline 使 YCSB/RocksDB 吞吐降 **16.6–20.6%**；[[PageFlex-ATC25]] 显示 userfaultfd 额外 **4 µs/refault** 可使 Redis 再慢 **13.3%**。
- **观察 2：verifier 误拒主因是抽象过粗，而非程序真不安全。** [[BCF-SOSP25]] 在 512 个真实误拒程序上接受 **403（78.7%）**；[[Rex-ATC25]] 分析 72 个 commit 的 workaround 模式（拆 program、改 LLVM、重写标准库），认定 language-verifier gap 是结构性问题。
- **观察 3：verifier bug 分四类（RC1–RC4），传统 KASAN fuzz 无法覆盖 RC1/RC2。** [[Veritas-SOSP25]] 用 SpecCheck SMT oracle 发现 **13** 个 Linux verifier bug，含提权与 KASLR 绕过；RC1 类过保守拒绝不产生内存错误，KASAN 永远看不见。
- **观察 4：标准 eBPF 的 event-driven 单次触发不足以支撑 NDP content-based I/O resubmit。** [[RosenBridge-FAST26]] 指出 [[XRP]] 需在 I/O submission 与 completion 双点 hook；多租户云倾向 QEMU userspace [[uBPF]] 而非 host kernel eBPF。
- **观察 5：eBPF verifier 约束适合短路径、无复杂同步逻辑，复杂情况可 fallback。** [[HyperTurtle-ATC25]] 将 L1 hypervisor EPT fault 等封装为 eBPF hyperupcall，复杂同步仍走原 L1 路径。

## 设计空间与取舍

- **路线 1：增强生产 verifier（BCF、Vishwanathan 优化）**：保持内核内线性时间验证，on-demand SMT refinement 提高精度；牺牲是依赖用户态 prover、21.3% 程序仍无法接受（[[BCF-SOSP25]]）。
- **路线 2：Testing oracle 而非替换 verifier（Veritas）**：SpecCheck 编码指令语义与安全性质，与 verifier 交叉比对挖 bug；牺牲是 SMT 慢、不适合在线验证（[[Veritas-SOSP25]]）。
- **路线 3：Language-based safety 替代 verifier（Rex）**：safe Rust + extralingual runtime，复用 eBPF hook/helper 生态；牺牲是 Rust 子集限制、TCB 转向 rustc、panic 后 crash-stop 卸载（[[Rex-ATC25]]）。
- **路线 4：struct_ops 替换内核算法（cache_ext、sched_ext）**：kernel 内可定制 eviction/scheduling，per-cgroup 隔离；牺牲是 verifier 表达力上限、policy bug 的运维回滚 story 未成熟（[[cache_ext-SOSP25]]）。
- **路线 5：策略外置、机制保留（PageFlex）**：eBPF 处理 fault/scan 轻量事件，重逻辑放用户态 agent + `process_madvise`；牺牲是 **608 LoC** 内核改动与 4-byte per-page state 上限（[[PageFlex-ATC25]]）。
- **路线 6：用户态 eBPF（bpftime）**：ERIM 硬件隔离 + concealed entry，Nginx 扩展开销 **~2%**；牺牲是 x86 MPK 绑定、与 kernel eBPF 统一 policy 仍开放（[[bpftime-OSDI25]]）。
- **路线 7：用户态 uBPF 跨虚拟化边界（RosenBridge）**：PREVAIL 验证 + io_uring 双 hook；牺牲是相对 bare-metal NDP **~35%** 带宽、**~55%** 延迟损失（[[RosenBridge-FAST26]]）。

## 引用本概念的论文

- [[cache_ext-SOSP25]] — struct_ops 定制 page cache eviction，per-cgroup 隔离，generic policy 吞吐最高 **+38%**
- [[BCF-SOSP25]] — proof-guided abstraction refinement，78.7% 真实误拒程序被接受，内核验证明 **48.5μs**
- [[Veritas-SOSP25]] — SpecCheck SMT oracle 差分 fuzzing，发现 13 个 verifier bug（含提权）
- [[Rex-ATC25]] — 闭合 language-verifier gap：safe Rust 替代 verifier，BMC 326 行 vs eBPF 513 行
- [[PageFlex-ATC25]] — eBPF 外置 reclaim/prefetch 策略，保留内核 swap 栈，Redis 性能损失 <1%
- [[FlexGuard-SOSP25]] — sched_switch hook 检测 critical section 被抢占，锁性能 **1–6×**
- [[HyperTurtle-ATC25]] — 嵌套虚拟化 EPT fault 等封装为 eBPF hyperupcall，EPT fault 延迟降 **5.1×**
- [[Loom-SOSP25]] — 高频 eBPF 遥测 + log-structured 存储，平衡 complete capture 与低 probe 开销
- [[RosenBridge-FAST26]] — 虚拟化边界 NDP：kernel eBPF 不足，QEMU uBPF + io_uring passthrough
- [[Aeolia-SOSP25]] — user interrupt 与 eBPF/SPDK/io_uring 并列的高性能 I/O 完成路径选项
- [[bpftime-OSDI25]] — 用户态 bpftime：eBPF 验证 + ERIM 隔离，应用扩展 **~2%** 开销
- [[uCache-FAST26]] — 对比路线：消除 syscall 边界后 callback 策略无需 eBPF 沙箱（假设需验证）

## 已知局限 / 开放问题

- **Verifier 长期正确性**：BCF 提高接受率、Veritas 找 bug，但两者均未形式化证明与 Linux 实现双向等价
- **Language-verifier gap 共存**：Rex 与原生 eBPF 将长期并存，大型程序选型（verifier workaround vs Rust 子集）缺乏系统指南
- **eBPF 指令/栈上限**：学习型 eviction、复杂 ML policy（LRB）可能触 verifier 预算，cache_ext/PageFlex 均承认表达力边界
- **部署前提**：cache_ext 依赖 cgroup v2；PageFlex 需内核 tracepoint 补丁；bpftime 绑定 x86 ERIM
- **安全模型分层**：生产 eBPF 多为 root 加载、non-adversarial；unprivileged eBPF 与 multi-tenant uBPF 的威胁模型对齐仍是开放问题
- **与 kernel-bypass 趋势的张力**：[[uCache-FAST26]]、SPDK、io_uring direct path 旁路 page cache 时，eBPF cache 策略收益域需重新划定