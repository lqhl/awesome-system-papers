---
type: paper
name: Veritas
full_title: "eBPF Misbehavior Detection: Fuzzing with a Specification-Based Oracle"
authors: [Tao Lyu, Kumar Kartikeya Dwivedi, Thomas Bourgeat, Mathias Payer, Meng Xu, Sanidhya Kashyap]
venue: SOSP
year: 2025
tags: [ebpf, fuzzing, verifier, formal-specification, smt]
source_pdf: "[[3731569.3764797.pdf]]"
source_md: "[[3731569.3764797]]"
---

# eBPF Misbehavior Detection: Fuzzing with a Specification-Based Oracle (SOSP 2025)

> **一句话总结**:Veritas 用「SpecCheck」specification-based oracle + SMT solver 系统化编码 eBPF 指令语义和五条安全属性，对 verifier 做差分 fuzzing，发现 15 个新 bug（12 个已确认、8 个已修），涵盖从提权、KASLR 泄漏到耗时数小时才 debug 的可用性 bug。

## 问题

Linux [[eBPF]] verifier 是安全 kernel extension 的把关者，Meta 每台服务器跑 >50 个 eBPF 程序。但 verifier 本身有 bug，分两面：

- **误拒安全程序**（usability）：开发者数小时调试才能搞明白 verifier 的 abstract 怎么想的
- **误接受不安全程序**（security）：已出现过提权 (CVE) 和信息泄漏漏洞

作者梳理出 4 个 root cause：
- **RC1**: 抽象解释过近似，拒掉安全程序
- **RC2**: 安全规则不一致——bitwise AND 在 atomic 和常规下结果迥异，开发者困惑
- **RC3**: 实现错误，如缺少类型检查使 `bpf_iter_num_next` 能接任意指针导致内核死循环
- **RC4**: 优化错误，path pruning 时误把 `CAP_PERFMON` 特殊行为用到普通程序上，导致可泄漏 kernel pointer

之前 fuzzing 工作（KASAN sanitizer、runtime range discrepancy）只能触达 RC3/RC4 的部分，对 RC1/RC2 无能为力（安全程序都被 verifier 挡掉、根本跑不到 runtime）。

## 核心方法

Veritas 采用 **specification-based oracle SpecCheck**，差分比较 verifier 结果和 spec 结果：

- **eBPF 语义规范**：精确编码指令操作语义 + 动态类型系统。类型包括 `Uninit`、`Scalar(kind, val)`、`PtrType(region, memid, off)`、`PtrOrNullType`。寄存器 r0-r9 和 stack 通用、r10 和其他 region（context、packet、map）有固定类型。为 arithmetic / data handling / memory / control flow 每类指令写 pre/post-condition。
- **五条安全属性（SP1-5）**：基于 CIA triad 推导
  - SP1 控制流安全（最多 1M 指令、无死循环）
  - SP2 内存安全（pointer deref 非空、bound check、时序安全）
  - SP3 资源安全（锁/分配内存必须释放）
  - SP4 VM invariant（r10 read-only）
  - SP5 VM data safety（capability model 防 pointer 泄漏）
- **SMT 编码**：把所有动态检查编码为 SMT formula，失败时 solver 反例直接指向违规指令（trackability）
- **扩展性**：新增指令/helper 只需加 pre/post-condition，不动框架
- **集成进 fuzzer**：coverage-guided fuzzing 配合 SpecCheck 做 oracle，只要 verifier 结果和 spec 分歧就标 bug

## 关键结果

- 发现 **15 个新 bug**，12 个已被 Linux 内核开发者确认，8 个已修复
- 严重安全 bug 例子：
  - **提权到 root** 的 bug
  - 通过**路径 pruning 错误**泄漏 7 字节 kernel pointer → 绕过 [[KASLR]]，进一步串联其他漏洞可形成完整 exploit
  - `bpf_iter_num_next` 缺类型检查 → 传入用户可控 map 指针导致内核 hang
- 可用性 bug 例子：用 sched-ext 开发者数小时调试的 `array[x] = res` 误拒（RC1 导致）
- 覆盖了现有 fuzz 工作完全无法触及的 RC1/RC2

## 相关

- **相关概念**:[[eBPF]]、[[Fuzzing]]、[[Formal-Specification]]、[[SMT]]、[[KASLR]]、[[Abstract-Interpretation]]
- **同类系统**:[[PREVAIL]]、[[Agni]]、[[BCF-SOSP25]]
- **同会议**:[[SOSP-2025]]、[[BCF-SOSP25]]
