---
type: paper
name: Omniglot
full_title: "Building Bridges: Safe Interactions with Foreign Languages through Omniglot"
authors: [Leon Schuermann, Jack Toubes, Tyler Potyondy, Pat Pannuto, Mae Milano, Amit Levy]
venue: OSDI
year: 2025
tags: [rust, ffi, memory-safety, type-safety, sandboxing]
source_pdf: "[[osdi25-schuermann.pdf]]"
source_md: "[[osdi25-schuermann]]"
---

# Building Bridges: Safe Interactions with Foreign Languages through Omniglot (OSDI 2025)

> **一句话总结**：第一个在 Rust 中对未修改的 C 库保持所有 soundness 不变式（内存、类型、别名、并发）的 FFI 框架，用「弱化类型 + 延迟验证」避免昂贵的 copy/serialization，性能接近 unchecked FFI，大幅优于 copy-based 同安全级别方案。

## 问题

Rust 号称内存/类型安全，但真实系统不可能丢掉几十年工程磨合的 C 库（OpenSSL、lwIP、zlib…）。现有 FFI（rust-bindgen 生成 `extern "C"`）把所有安全证明推给开发者：一条 C 函数违反 Rust 的 UTF-8、`aliasing XOR mutability`、`bool ∈ {0,1}` 等不变式，就能让 Rust 端出现 use-after-free、段错误等本被类型系统杜绝的漏洞（论文给出的例子：C 侧返回非 0/1 的 bool 会错位解释 enum 的 discriminant，从而把 slice 指针当 CString）。

单纯的内存隔离（如 WebAssembly 沙箱、MPK）挡不住语义层面的违规：即使 C 代码只碰自己的沙箱内存，返回值的 bit pattern 依然可能破坏 Rust 的 type invariants；指针别名没法追踪，让 Rust 的 XOR 规则无从保证。

## 核心方法

Omniglot 不对整个程序做 whole-program soundness 证明，而是把 **每次 foreign call** 看作本地论证：

- **弱化的 binding 类型**：为每个 foreign 函数生成一个返回「tainted 版本」（如 `?bool`）的绑定 `f'`。`?bool` 没有 `{0,1}` 限制，调用 `f'` 本身绝不会破坏 soundness。
- **运行时 validation + downcast**：safe wrapper `f` 里调用 `f'`，拿 `?bool` 做 O(1) 检查（合法 bit pattern / alignment / UTF-8 等）后 cast 回真 `bool`。复杂类型（含内部引用、typestate）则禁止直接验证，改用 symbolic handle 指回 Rust 拥有的副本。
- **可插拔 runtime + memory isolation**：接口对隔离原语无 knowledge，作者在嵌入式 OS 内核上用 RISC-V [[PMP]]、Linux userspace 上用 x86 [[MPK]]——"strong" runtime 阻止 adversarial 库绕过（并发线程、syscall 逃逸）；"weak" runtime 用于可信库。
- **Scopes（零成本编译期时序检查）**：引入一种类似 lifetime 的 scope 机制，静态拒绝会让 validation 被后续 foreign 调用作废的代码。
- **无 copy/no serialization**：共享内存区域直接 dereference，只要目标对象完全落在 foreign 沙箱合法区域；修改后的 rust-bindgen 自动生成 Omniglot binding。

## 关键结果

- 覆盖实践库：cryptography、compression、image decoding、文件系统、TCP/IP stack
- 性能接近 unchecked FFI，几乎等同于「只加内存隔离」的方案
- 相比同安全级别的 copy/serialize-based 工作（例如 Sandcrust 等）快一个量级
- 内核和 userspace 两个 runtime 均可工作，Tock OS 嵌入式场景可用

## 相关

- **相关概念**：[[Rust]]、[[FFI]]、[[MPK]]、[[PMP]]、[[Memory-Isolation]]
- **同会议**：[[OSDI-2025]]
