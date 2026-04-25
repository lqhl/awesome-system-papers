---
type: paper
name: BCF
full_title: "Prove It to the Kernel: Precise Extension Analysis via Proof-Guided Abstraction Refinement"
authors: [Hao Sun, Zhendong Su]
venue: SOSP
year: 2025
tags: [ebpf, verifier, abstraction-refinement, smt, formal-methods]
source_pdf: "[[3731569.3764796.pdf]]"
source_md: "[[3731569.3764796]]"
---

# Prove It to the Kernel: Precise Extension Analysis via Proof-Guided Abstraction Refinement (SOSP 2025)

> **一句话总结**:BCF (eBPF Certificate Framework) 通过「proof-guided abstraction refinement」把复杂推理 offload 到用户态 SMT solver，内核只做线性时间 proof check，让 eBPF 验证器接受了 403/512 (78.7%) 之前被错误拒绝的真实程序，平均 proof 541 字节、检查 48.5 微秒。

## 问题

Linux [[eBPF]] verifier 用抽象解释（interval + tristate domain）静态检查扩展程序，强制线性时间复杂度以保证内核安全和性能。但这些廉价的 abstract domain 本质上是**过近似**——比如 `r2 &= 0xf; r2 <<= 1` 后正确范围是偶数子集，而抽象只能给 `[0,30]`，丢掉了「最低位必为 0」这种信息。

结果是 verifier 频繁误拒安全程序。Cilium、Calico、Tetragon、SCX（eBPF 调度器）、Elastic 这些大项目里，开发者被迫做诡异的 workaround：分配双倍内存、写内联汇编、加冗余检查，甚至 Elastic 要分 256 KiB 但只能用 128 KiB。

已有工作要么继续在内核塞更精细的 domain（如 PREVAIL 的 Zone）、加重 verifier 复杂度；要么做 runtime instrumentation。都没摆脱 precision-complexity trade-off。

## 核心方法

BCF 的关键 insight 是**解耦**：把复杂推理挪到用户态，内核只做 proof check（线性时间）。

流程三步：

1. **Refinement Condition Generation**：当 verifier 卡住时（例如 memory access 可能越界），触发 refinement。通过 backward analysis 找到需要精确追踪的指令 suffix，然后做 symbolic tracking，把目标寄存器表达成符号表达式（如 `(sym&0xf) + (0xf-(sym&0xf))` 实际恒为 `15`）。派生出「符号表达式必须包含于 refined abstraction 」的 refinement condition。
2. **用户态 proof 生成**：把 condition 编码为 BCF 二进制格式，送给用户态的 cvc5 SMT solver。solver 为固定位宽 bit-vector 理论生成 proof tree（45 条 primitive rule，如 trans、cong、sub_elim、false_elim）。
3. **内核 proof 检查**：内核 proof checker 线性扫描 proof，每步核对 premise 与 conclusion 是否满足声称的 rule；通过后 verifier 采纳 refined abstraction 继续分析。任何伪造 proof 或不合法 rule 都被 rejected。

实现：verifier 扩展 1663 LoC、proof checker 2337 LoC、uapi 190 LoC、loader 349 LoC、cvc5 修改 1837 LoC，共 7366 LoC。集成只加 5 个 `bpf_attr` 字段、无需新 syscall。

## 关键结果

- 512 个来自 Cilium/Calico/xdp-project/BCC 等真实项目的安全但被拒 eBPF 程序，**BCF 接受 403 个 (78.7%)**
- 平均 **proof 大小 541 字节**、**proof check 时间 48.5 微秒**
- 端到端分析平均 9.0 秒，其中 proof check < 1%，用户态部分约 21%
- 未接受的 109 个主要是 symbolic tracking 对 non-register-sized stack spill 支持不完整（工程问题，不影响 soundness）
- Linux 内核社区方向标：现在有了「既保持简单又精确」的第三条路

## 相关

- **相关概念**:[[eBPF]]、[[Abstract-Interpretation]]、[[SMT]]、[[Proof-Checking]]、[[CEGAR]]
- **同类系统**:[[PREVAIL]]、[[Agni]]
- **同会议**:[[SOSP-2025]]、[[Veritas-SOSP25]]
