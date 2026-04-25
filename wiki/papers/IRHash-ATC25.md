---
type: paper
name: IRHash
full_title: "IRHash: Efficient Multi-Language Compiler Caching by IR-Level Hashing"
authors: [Tobias Landsberg, Johannes Grunenberg, Christian Dietrich, Daniel Lohmann]
venue: ATC
year: 2025
tags: [compiler-cache, llvm, build-system, hashing, ir]
source_pdf: "[[atc2025-landsberg.pdf]]"
source_md: "[[atc2025-landsberg]]"
---

# IRHash: Efficient Multi-Language Compiler Caching by IR-Level Hashing (ATC 2025)

> **一句话总结**：在 LLVM IR 级别做编译缓存的 hash，相对源码级 Ccache 和 AST 级 cHash 更准（false miss 少 1–2 个数量级）且天然支持多语言（C/C++/Fortran/Haskell），16 个开源项目实测 C 项目平均 build 时间减少 19%。

## 问题

编译缓存（Ccache、sccache、cHash 等）对降低开发周期 build 时间至关重要，原理是计算 translation unit (TU) 的指纹 hash 找复用对象文件。trade-off 在「hash 算得多早 / 多准」：

- **Ccache** 在源码或预处理后做 hash，最快但任何空白注释改动都 false miss
- **cHash** 在 AST 后做 hash，能消除一些 syntactic noise（如未引用的类型声明），但只支持 C，且 AST 哈希实现要为每个 AST 节点类型写规则（C 用了 1200+ 行）

把 hash 推到更晚阶段能更准，但要付出更多 T_over（执行到该阶段的开销）；问题是哪个阶段 trade-off 最好。

## 核心方法

作者论证 **LLVM IR 是最佳 hash 点**：

1. **T_rem（剩余可省时间）几乎不损**：从 AST 到 IR 只需一次树遍历，OpenSSL 上 T_rem 仅从 31.3ms 略降到 30.1ms
2. **P_acc（准确性）更高**：IR 生成会做 typedef 擦除、ad-hoc constant folding 等规范化，syntactic sugar/explicit 修饰符等被消掉
3. **T_over（hash 自身开销）极低**：IR 是扁平 SSA 序列（list of lists），数据结构本来就为频繁遍历优化；LLVM IR 在 OpenSSL 上 T_over 仅 0.7ms，cHash 是 8.7ms，Ccache 是 97.7ms
4. **多语言通用**：所有有 LLVM backend 的语言（C/C++/Fortran/Haskell 等）都直接支持，无需为每个语言写 hash 规则

**实现**：LLVM plugin，IR pass 在 IR 生成后立即跑。hash 包含 module 内 global variable + function（递归到 basic block + instruction）；instruction hash 含 opcode、operand、影响二进制的 attribute（alignment、atomicity）；type 递归到标量；inline asm 用字符串。CC 逻辑像 Ccache：以 hash 为文件名存对象文件，命中则 hard-link。

故意**不直接 hash 序列化的 LLVM bitcode**：(1) 失去对 hash 内容的细粒度控制（如默认排除 debug info）；(2) 序列化本身耗时。

整个实现 561 行 C++（hash 逻辑 353 行 + cache logic 208 行），cHash 仅 hash 部分就要 1200 行。深度细节回 [[atc2025-landsberg]]。

## 关键结果

- 16 个开源项目（Linux、OpenSSL、PostgreSQL、CPython、Bash、Lua、SQLite、Bochs、Asio、LAPACK、ShellCheck 等）100 个 commit 历史
- C 项目平均 P_acc：Ccache 95.32% / cHash 99.19% / **IRHash 99.87%**（false miss 比 Ccache 少 1–2 个数量级）
- C 项目平均 build 时间减少：Ccache 10% / cHash 16% / **IRHash 19%**
- C++ 项目（Asio、Clazy、GammaRay、Bochs）IRHash 平均 P_acc 98.86% vs Ccache 88.20%（cHash 不支持 C++）
- 也支持 Fortran（LAPACK，P_acc 99.99%）和 Haskell（ShellCheck，P_acc 100%）
- 实现仅 561 行 C++，远少于 cHash 的 1200 行

## 相关

- **相关概念**：[[Compiler-Cache]]、[[LLVM-IR]]、[[Build-Artifact-Reuse]]、[[Content-Hashing]]
- **同类系统**：Ccache、sccache、cHash（AST 级，仅 C）、Bazel/Buck2 内建缓存
- **同会议**：[[ATC-2025]]
