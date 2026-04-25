---
type: paper
name: Bin2Wrong
full_title: "Bin2Wrong: a Unified Fuzzing Framework for Uncovering Semantic Errors in Binary-to-C Decompilers"
authors: [Zao Yang, Stefan Nagy]
venue: ATC
year: 2025
tags: [fuzzing, decompiler, binary-analysis, security, differential-testing]
source_pdf: "[[atc2025-yang-zao.pdf]]"
source_md: "[[atc2025-yang-zao]]"
---

# Bin2Wrong: a Unified Fuzzing Framework for Uncovering Semantic Errors in Binary-to-C Decompilers (ATC 2025)

> **一句话总结**：把 source/compiler/optimization/executable-format 四维统一成 AFL++ 单一 testcase 进行 fuzz，在 7 个主流反编译器上把二进制多样性比 Cornucopia/DecFuzzer 提升 10.39×/17.18×，挖到 48 个语义 bug、30 个已确认，触发 Binary Ninja 核心代码结构重构。

## 问题

二进制反编译器（Binary Ninja、Ghidra、Angr、RetDec 等）把可执行文件还原成 C 代码，是恶意分析、漏洞挖掘、安全加固的基础工具，但「语义错误」会让上层任务失败。已有的 fuzz 方法（DecFuzzer、Cornucopia、D-Helix、DSmith）每个只覆盖部分维度——DecFuzzer 只动 source 不动 optimization；Cornucopia 只玩单一编译器的 optimization；D-Helix 要求逐反编译器建模 IR、扩展一个新 decompiler 要 40 天人力。结果是大量由 source × compiler × opt × format 组合触发的边角错误漏过测试，最后让真实用户踩坑。

## 核心方法

Bin2Wrong 把 binary 的四个生成维度**整合成一个 unified testcase**：前 2048 字节编码 compiler（6 选 1：GCC/Clang/TCC/ICX/MSVC/AppleClang）和 optimization flag（5183 个 flag 总集，按 byte 奇偶决定开关），后续是源码 AST。AFL++ 自定义 mutator 同时变异：

- **Source 层**：基于 libClang AST，覆盖表达式（删/复制/扩展子表达式、改算符）、控制结构（loop break/continue 注入、条件 always-true/false、goto 重定向、switch 表达式替换）、数据字面量（string/numeric 替换/位翻转/类型 cast）
- **Compilation 层**：Linux 上用 WINE/Darling 兼容层支持 PE（MSVC）和 Mach-O（AppleClang），首次让 fuzz 跨 ELF/非 ELF
- **差分 oracle**：Csmith 风格的全局 checksum 对比原 binary 与 decompile→recompile 后的运行结果，**完全 black-box**，与 D-Helix 的 IR 建模相反，能直接套到任何输出 C 的反编译器（包括闭源的 Binary Ninja）
- **Recompilation patching**：自动修复 decompiler 输出中常见的 `void* const`、`__cdecl` 名字、自定义类型 macro 等小语法错，让重编译率从 11.6% 提到 47.8%

深度细节回 [[atc2025-yang-zao]]。

## 关键结果

- 在 7 个反编译器（Binary Ninja、Angr、R2Ghidra、Reko、Relyze、RetDec、Rev.Ng）上，binary diversity 比 Cornucopia 高 10.39×、比 DecFuzzer 高 17.18×（BinDiff 度量）
- decompiler code coverage 比 Cornucopia 高 1.16×、比 DecFuzzer 高 1.32×；coverage-increasing binary 比例分别高 3.56×、59.61×
- 共发现 48 个新语义 bug，42 个 Bin2Wrong 独占，30 个已被开发者确认或修复
- 其中一个 bug 直接导致商用反编译器 Binary Ninja 的 core code-structuring 模块重构

## 相关

- **相关概念**：[[Fuzzing]]、[[Differential-Testing]]、[[AFL]]
- **同会议**：[[ATC-2025]]
