---
type: paper
name: ATLAS
full_title: "Unveiling Compiler Faults via Attribute-Guided Compilation Space Exploration"
authors: [Jiangchang Wu, Yibiao Yang, Maolin Sun, Yuming Zhou]
venue: ATC
year: 2025
tags: [compiler-testing, fuzzing, gcc, llvm, bug-finding]
source_pdf: "[[atc2025-wu-jiangchang.pdf]]"
source_md: "[[atc2025-wu-jiangchang]]"
---

# Unveiling Compiler Faults via Attribute-Guided Compilation Space Exploration (ATC 2025)

> **一句话总结**：在测试程序里向函数/变量/语句随机插入 C/C++ attribute（如 always_inline / no_sanitize_address / packed），触发 compiler option 单独无法触发的细粒度行为，比 baseline 多发现 109.1% bug，已在 GCC/LLVM 报 73 个 unique bug（58 已确认或修复）。

## 问题

主流 compiler fuzzing（Csmith、YARPGen、EMI）通过组合不同 compilation option 探索编译空间。但 compilation option 通常作用于整个程序，无法细粒度控制单个函数/变量。C/C++ 的 `__attribute__` 机制（noinline、aligned、optimize、packed、no_sanitize_address 等）允许程序员对单个 element 设置编译指令，覆盖了 option 触达不到的代码路径——但此前未被系统化用于编译器测试。

## 核心方法

ATLAS 在已有种子程序基础上做 attribute 插入式 fuzzing：

1. **Collect**：解析 AST 收集 function 集 S_f、variable 集 S_v、statement 集 S_s 及各自属性元组（名字、类型、位置、变量列表）
2. **Insert Attributes**：
   - 函数：FlipCoin 决定是否插入；按返回类型选 noinline / always_inline / optimize(...) / noreturn / pure 等（如 noreturn 不能用于非 void）
   - 变量：按类型筛选适用 attribute（packed 仅对 struct member；vector_size 仅对特定类型）
   - 语句：组合 #pragma omp simd 等带表达式的 attribute（用变量列表构造如 `linear(uval(x): y+1)`）
3. **Combine with options**：精心配对 attribute 与对应 compilation option（如 `__attribute__((optimize("-ftree-loop-distribution")))` 配 `-O2 -fsanitize=address,null`），用差分测试发现 ICE/crash

实例：always_inline 函数被内联到 no_sanitize_address 函数后，ASan mark 残留导致 GCC -O2 -fsanitize=address 触发 ICE——只有 attribute 组合能触发，单独 option 无法。

深度细节回 [[atc2025-wu-jiangchang]]。

## 关键结果

- 比 baseline（无 attribute 插入）多发现 **109.1%** bug
- 在 GCC trunk + LLVM trunk 共发现 **73 个 unique bug**，**58 个已确认或修复**
- 代码覆盖率高于 baseline

## 相关

- **同会议**：[[ATC-2025]]
