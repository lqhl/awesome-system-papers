---
type: paper
name: WASIT
full_title: "WASIT: Deep and Continuous Differential Testing of WebAssembly System Interface Implementations"
authors: [Yage Hu, Wen Zhang, Botang Xiao, Qingchen Kong, Boyang Yi, et al.]
venue: SOSP
year: 2025
tags: [webassembly, wasi, differential-testing, fuzzing, bug-finding]
source_pdf: "[[3731569.3764819.pdf]]"
source_md: "[[3731569.3764819]]"
---

# WASIT: Deep and Continuous Differential Testing of WebAssembly System Interface Implementations (SOSP 2025)

> **一句话总结**：面向 WebAssembly 的 WASI 实现做 specification-driven differential testing；通过实时资源抽象追踪生成语义依赖的函数调用序列、DSL 过滤已知 bug、解耦架构支持 WASI 快速演进——在 6 个主流 Wasm runtime 里发现 48 个新 WASI bug，3 个 CVE。

## 问题

WebAssembly 靠 WASI (WebAssembly System Interface) 在浏览器外访问系统资源（文件、时钟、网络）；但 WASI 实现又难又易错：

- WASI 函数复杂且在不同系统状态下行为不同，而 WASI spec 描述极简略
- 依赖底层 host OS syscall，WASI 和 syscall 语义有微妙差异
- WASI 演进极快（6 个月 3 个版本，32 个 active proposal），维护负担大
- 实现 bug 可导致数据损坏、甚至逃逸 Wasm sandbox（CVE-2024-38358 等）

现有方案：wasm-smith、WASMaker、WADIFF 几乎不测 WASI；DrWASI、Wasix 只生成孤立/简单的 WASI 调用，无法触达深层 state；syzkaller 类工具无法避免重复触发已知 bug。

## 核心方法

WASIT 做三件事来打破瓶颈：

- **实时资源抽象与追踪**（dynamic resource abstraction and tracking）：在测试驱动端维护 WASI 涉及的资源状态（如 fd、文件、路径），以此生成 **有依赖、语义丰富**的调用序列，到达深层系统 state——避开对 runtime 源码的白盒分析（runtime 用 C/C++/Rust/Go/Java/Swift 多语言，白盒难）
- **augmentation DSL**：设计 domain-specific language 为 WASI spec 附加语义约束，自动过滤"无意义"的参数值——这让测试可以绕过已发现但未修复的 bug，实现真正的 continuous testing
- **decoupled architecture**：把 core testing control logic 与具体 WASI 调用生成解耦，WASI spec 变更时只需改生成部分，测试策略不动——能平滑 co-evolve

## 关键结果

- 4 个月间歇性测试，在 6 个主流 Wasm runtime（Wasmer、WasmEdge、Node.js 等）发现 **48 个 WASI 新 bug**
- 41 个已确认，**37 个已修复**（多为作者提供 patch），**3 个 CVE 分配**
- 收到 Node.js 和 Wasmer 等社区积极反馈，刺激了关于 WASI spec 质量的讨论
- 开源于 github.com/yagehu/wasit

## 相关

- **相关概念**：Differential testing、Fuzzing、API testing
- **同类工具**：syzkaller、AFL、DrWASI、Wasix、WADIFF
- **同会议**：[[SOSP-2025]]
