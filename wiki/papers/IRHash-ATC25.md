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
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# IRHash: Efficient Multi-Language Compiler Caching by IR-Level Hashing (ATC 2025)

> **一句话总结**：观察到 AST→IR 的增量成本极低（OpenSSL 上 T_rem 仅从 31.3ms 降到 30.1ms）却能显著消除 syntactic false miss（C 项目 P_acc 99.87% vs Ccache 95.32%），IRHash 在 LLVM IR 生成后立即 hash 并缓存对象文件，16 个开源项目上 C 项目平均 build 时间减少 19%（Ccache 10%、cHash 16%），且天然覆盖 C/C++/Fortran/Haskell。

## 问题与动机

软件开发的增量 build 会反复编译大量 translation unit (TU)，消耗可观时间与能源。[[Compiler-Cache]]（Ccache、sccache、cHash、Bazel/[[Buck2]] 内建缓存）通过 content-based fingerprint 复用历史对象文件，避免冗余编译。核心 trade-off 在 **何时 hash**：越早介入，剩余可跳过阶段 $T_{\mathsf{rem}}$ 越大；越晚介入，对「语义无关改动」的识别越准（$P_{\mathsf{acc}}$ 越高），但 hash 自身开销 $T_{\mathsf{over}}$ 也随已执行编译阶段增长。

现有方案分三层：
- **源码/预处理级**（Ccache）：$T_{\mathsf{over}}$ 低、$T_{\mathsf{rem}}$ 高，但空白、注释、格式等 lexical 改动都触发 false miss
- **AST 级**（cHash）：能忽略未引用类型声明等 syntactic noise，$P_{\mathsf{acc}}$ 更高，但需为每种语言的 AST 节点写 hash 规则（仅支持 C，hash 逻辑 1200+ 行），且 AST 遍历本身昂贵（OpenSSL 上 $T_{\mathsf{over}}$ 8.7ms vs Ccache 97.7ms 含预处理）
- **时间戳级**（make）：几乎零开销，但无法跨仓库/机器复用，且对 header 依赖极敏感

作者 claim：现代编译器在 AST 之后生成的 **[[LLVM-IR]]** 是 [[Build-Artifact-Reuse]]（BAR）的最佳 hash 点——IR 生成几乎不增加延迟，却已完成 typedef 擦除、constant folding 等规范化，且 IR 指令集小而语言无关，可用极少代码实现多语言缓存。

## 关键观察 / 隐含假设

- **观察 1**：从 AST 到 IR 的增量编译成本可忽略，但 IR 已消除大量 syntactic sugar，使 $P_{\mathsf{acc}}$ 显著高于源码/AST 级 hash。
  - **依赖假设**：目标编译器走「AST → IR → optimize → codegen」流水线；IR 生成阶段的 ad-hoc 规范化（typedef 擦除、常量折叠）与最终对象文件语义一致；评测改动主要来自真实 commit 历史中的局部编辑。
  - **可能失效场景**：后端在 codegen 阶段做语义等价变换（如 RISC-V `add` 操作数交换，Figure 2 案例 D）仍会导致 IR 级 false miss；依赖 LTO/跨 TU 优化的 build 中，单 TU IR hash 可能无法捕捉跨模块影响；Rust 等多层 IR（MIR/HIR）场景下，LLVM-IR 距 AST 更远，$T_{\mathsf{rem}}$ 进一步缩小。

- **观察 2**：IR 的扁平 SSA 结构（list of lists）比递归 AST 更适合快速遍历 hash，IRHash 的 $T_{\mathsf{over}}$ 比 cHash 低 1–2 个数量级，从而抵消「hash 点更晚」带来的 $T_{\mathsf{rem}}$ 损失。
  - **依赖假设**：hash 直接遍历 LLVM 内存数据结构，而非序列化 bitcode/textual IR；TU 规模适中，模板实例化不会爆炸式膨胀 IR（Asio 182 kLOC → 387 MiB IR 是反例边界）。
  - **可能失效场景**：C++ 重度模板项目（Asio $T_{\mathsf{over}}$ 14.5ms、Clazy 26.1ms）和 GHC 生成巨型 textual IR 再调 `opt` 的 Haskell 路径（ShellCheck $T_{\mathsf{over}}$ 60.7ms）使相对开销显著上升；若编译器改为流式/并行 AST 生成，cHash 与 IRHash 的 $T_{\mathsf{rem}}$ 差距可能变化。

- **观察 3**：IR 指令类型有限且语言无关，同一套 hash 逻辑可覆盖所有 [[LLVM]] backend 语言，实现与维护成本远低于 per-language AST hash。
  - **依赖假设**：团队使用 Clang/Flang/GHC-LLVM 等 LLVM 系工具链；缓存粒度为整 TU 对象文件；编译器 frontend 到 LLVM IR 的 lowering 是确定性的。
  - **可能失效场景**：GCC 等非 LLVM 工具链完全不适用；GHC 的 non-deterministic identifier uniquification 使跨 build 的 IR 不稳定（ShellCheck $P_{\mathsf{opt}}$ 仅 75.26%，IRHash 反而慢 0.8%）；需要最新 debug info 的 build 若默认排除 debug metadata，可能产生不符合开发者预期的 hit。

- **假设 1**：在 IR 生成后、优化器运行前做 hash，足以在准确性与 $T_{\mathsf{rem}}$ 之间取得最优平衡；对象文件变化当且仅当 IR hash 变化（无 false hit）。
  - **证据强度**：**强**——128 万+ TU 的 clean build 验证零 false hit；与对象文件 hash 对比，正确性有保障。

- **假设 2**：开发者的典型 workload 是「基于 git 历史的局部 commit 增量 build」，而非 clean build 或跨版本大规模重构。
  - **证据强度**：**中**——16 个项目各 100 个最近 commit 的增量 build 有代表性，但未覆盖 interactive 单文件编辑（论文预期 $P_{\mathsf{opt}}$ 更高）和 CI 全量 rebuild；Linux 上 IRHash 单独使用反而慢 3.1%。

## 核心方法

IRHash 是加载到 [[LLVM]] 工具链的 **compiler plugin**，在 IR 生成完成后立即插入 pass，完成 fingerprint 计算与 cache lookup，命中则 hard-link 缓存对象文件并终止编译。

**IR Hashing**（~353 行）：
- Module 级 hash = 所有 global variable + function 的聚合
- Function hash = 名称、原型、attributes + 各 basic block 的 instruction hash
- Instruction hash = opcode、operands、影响二进制的 attributes（alignment、atomicity 等）
- Type 递归 hash 到标量；inline asm 用字符串表示
- **故意不 hash 序列化 IR**：保留对 debug info 等字段的细粒度控制，避免 bitcode 序列化开销

**Caching Logic**（~208 行）：
- 与 Ccache 类似：以 hash 为文件名存对象文件，命中则 hard-link 到目标路径并更新 timestamp（兼容下游 make 等时间戳 BAR）
- Miss 时编译继续，结束后将对象文件写入 cache

**准确性机制**：IR 生成已擦除 C `typedef`、C++ `explicit` 等纯 syntactic 构造；未在 TU 中引用的类型声明不影响 hash（类似 cHash 的 struct 优化，但 IRHash 尚未实现 cHash 那种「只 hash 使用偏移而非类型本身」的 SDL 优化）。

**多语言路径**：C/C++ 经 Clang；Fortran 经 Flang；Haskell 经 GHC 9.12 的 LLVM backend（IRHash 挂在 `opt` 阶段）。可与 Ccache 串联：Ccache 先命中则跳过 IRHash，Ccache miss 时 IRHash 以更高精度补救。

总实现 561 行 C++，对比 cHash 仅 hash 部分 1200 行、Ccache 生产级 19k 行。深度细节见 [[atc2025-landsberg]]。

## 设计取舍

- **取舍 1：IR 生成后 vs 优化后 hash**——在 optimizer 之前 hash 以保留更大 $T_{\mathsf{rem}}$（可跳过整个 opt+codegen），但无法识别「仅优化器才能消除的语义等价改动」（如 Lua 重构后需优化才等价的案例）；若移到 opt 之后，准确性可能更高但节省更少。
- **取舍 2：遍历内存 IR vs 序列化 bitcode**——前者 $T_{\mathsf{over}}$ 极低且可排除 debug info，后者实现简单但慢且难定制；放弃与 [[ThinLTO]] 天然集成时「顺便 hash 已序列化 IR」的便利。
- **取舍 3：整 TU 缓存 vs per-function 缓存**——TU 级实现简单、无 IPO 依赖追踪风险；放弃函数级细粒度复用（跨函数 inline 会使 A 的改动污染 B 的 hash，需大量编译器改造）。
- **取舍 4：不做 IR normalization**——避免 normalization bug 导致 silent wrong compilation，也避免拓扑排序等 normalization 的 $T_{\mathsf{over}}$；代价是后端/优化器可消除的等价变换（操作数顺序等）仍 false miss。
- **取舍 5：LLVM 绑定 vs 编译器无关**——一次实现覆盖多语言，但完全不支持 GCC、MSVC 等非 LLVM 生态。
- **边界条件**：在 Clang/Flang 系、commit 级增量 build、中等规模 C/C++ 项目上最稳定；模板巨型 IR、non-deterministic frontend（GHC）、或 $P_{\mathsf{opt}}$ 极低的场景收益有限甚至为负。

## 实验与结果

- **正确性**：16 项目 × 100 commit，共 1,289,086 TU clean build，**零 false hit**（对象文件变化时 IR hash 必变）
- **准确性 $P_{\mathsf{acc}}$**（C 项目平均）：Ccache 95.32% / cHash 99.19% / **IRHash 99.87%**；Mbed TLS false miss：Ccache 6.38% → cHash 0.24% → IRHash 0.03%
- **开销 $T_{\mathsf{over}}$**（per TU 平均，C 项目）：Ccache 含预处理最重；cHash 次之；**IRHash ~0.4%** 相对总编译时间（OpenSSL：Ccache 97.7ms、cHash 8.7ms、IRHash 0.7ms）
- **端到端节省**（100 commit 增量 build，C 项目平均）：Ccache 10% / cHash 16% / **IRHash 19%**；C++ 项目 IRHash 19.4% vs Ccache 6.0%
- **多语言**：Fortran LAPACK $P_{\mathsf{acc}}$ 99.99%、节省 12.4%；Haskell ShellCheck $P_{\mathsf{acc}}$ 100% 但因 GHC 非确定性仅节省 0.8%
- **组合缓存**：Ccache+IRHash 在 6/16 项目上最优（如 GammaRay 26.4% vs 单独 Ccache 20.2% / IRHash 10.6%）；Linux 上组合 3.2% vs IRHash 单独 -3.1%
- **实现规模**：561 行 C++ vs cHash hash 算子 1200 行

## Critical Analysis

### 论证链条

论文用 Equation 1 将 BAR 形式化为 $P_{\mathsf{opt}} \cdot P_{\mathsf{acc}} \cdot T_{\mathsf{rem}} - T_{\mathsf{over}}$ 的权衡，再以 OpenSSL 微观分解（Figure 1）论证 IR 是「准确性提升 ≫ 延迟增加」的 sweet spot，逻辑链条清晰。128 万 TU 零 false hit 证明安全性；Tab. 3/4/5 分别验证 $P_{\mathsf{acc}}$、$T_{\mathsf{over}}$、端到端收益，与 conceptual claim 基本闭合。

薄弱跳步在于：将 16 个开源项目的 commit 增量 build 外推为「IR-level hashing 应成为现代编译器标准扩展」（Section 7）——Linux kernel 单独 IRHash 反而更慢（-3.1%），且未评测 Bazel/[[Buck2]]/distcc 等生产级分布式 build 集成后的 cache 一致性、跨机器复用等行为。

### 假设压力测试

- **论文已证明**：在 LLVM 系工具链、TU 级对象文件缓存、git commit 历史驱动的增量 build 上，IRHash 比 Ccache/cHash 更准确且多数项目更快。
- **可能失效**（推断）：
  - **编译器版本/flags 变化**：hash 是否包含完整 compiler flags、target triple、macro 定义；论文默认项目配置 + Clang，未系统测试 flags 漂移
  - **LTO/PGO**：跨 TU 优化改变 IR↔对象文件映射，TU 级 IR hash 的充分性存疑；[[ThinLTO]] 场景论文仅提及可复用序列化 IR，未实验
  - **Determinism**：GHC ShellCheck 案例表明 frontend 非确定性可直接摧毁缓存价值；其他 LLVM frontend 的确定性未被系统审计
  - **Debug/覆盖率 build**：默认排除 debug info 在 `-g` 场景下是否仍正确且符合预期，论文声称可配置但未评测

### 实验可信度

- **Benchmark 代表性**：16 项目覆盖 kernel、DB、crypto、interpreter、科学计算、Haskell 工具，规模从 16k 到 26M LOC，领域广；但仅 100 个最近 commit，对 long-term 重构/branch 切换的 $P_{\mathsf{opt}}$ 覆盖有限。
- **Baseline 强度**：Ccache 和 cHash 是合理的直接对比对象；未与 sccache 远程缓存、Bazel action cache、FASTBuild 等生产方案比较端到端 CI 成本。
- **Ablation**：Figure 2 五类改动（A–E）清晰展示各层 BAR 能力边界；缺少对 hash 字段选择（含/不含 debug info、attributes 子集）、hash 时机（pre-opt vs post-opt）、struct 类型优化移植的独立 ablation。
- **Metrics**：聚焦 build time 与 $P_{\mathsf{acc}}$，**未报告** cache 存储开销、跨分支命中率、尾延迟分布、开发者感知延迟（单文件 edit-rebuild 循环）。

### 系统性缺陷

- **尾延迟与存储**：cache 目录无限增长（实验不设上限），大规模项目的磁盘占用与 lookup 延迟论文未讨论。
- **故障恢复**：cache 损坏、hard-link 失败、并发多进程写同一 cache entry 的行为论文未讨论。
- **可观测性**：561 行原型无提及 hit/miss 统计、false miss 原因分析工具，运维可观测性弱于 Ccache。
- **资源隔离**：多开发者/CI 共享 cache 时的冲突、权限、污染策略论文未讨论。
- **兼容性**：作为 LLVM pass 需修改编译命令行；与某些 LTO/PGO 流程的集成路径论文未验证。

## 局限与 Future Work

- **局限 1**：仍有 false miss——后端 codegen 等价变换（操作数交换）、优化器才能消除的语义等价（Lua 重构案例）、以及 Asio 中 `std::move` 等显式化改动；$P_{\mathsf{acc}}$ 不可能达到 1.0。
- **局限 2**：仅支持 LLVM IR，且 hash 点在 frontend lowering 之后、optimizer 之前；对 Rust [[MLIR]] 等多层 IR 架构，最佳 cache 层级仍是开放问题（Section 5.2 明确承认 $T_{\mathsf{rem}}$ 会下降）。
- **局限 3**：TU 级粒度无法安全做 per-function 缓存，因 LLVM IPO/inlining 使函数间二进制相互依赖。
- **局限 4**：GHC 等非确定性 frontend 使 IRHash 在 ShellCheck 上无收益甚至略慢；说明 IR 级 caching 强依赖 frontend 确定性。
- **Future work 1**：在 IR hash 前做 **IR normalization**（basic block 拓扑排序等）并量化其 $P_{\mathsf{acc}}$ vs $T_{\mathsf{over}}$ 权衡；需严格正确性验证框架防止 normalization bug。
- **Future work 2**：移植 cHash 的 struct 类型使用偏移 hash 优化（SDL 案例），测量对 $P_{\mathsf{acc}}$ 的边际收益。
- **Future work 3**：在 [[MLIR]]/rustc 多层 IR 中系统测量「在哪一层 cache」的 $T_{\mathsf{rem}}$-$P_{\mathsf{acc}}$ 曲线，而非仅 LLVM-IR。
- **Future work 4**：与 distcc/Bazel/sccache 等分布式 build 集成，评测跨机器 IR cache 共享的命中率、一致性开销和 storage 成本。

## 相关

- **相关概念**：[[Compiler-Cache]]、[[LLVM-IR]]、[[LLVM]]、[[Build-Artifact-Reuse]]、[[Content-Hashing]]、[[ThinLTO]]
- **同类系统**：Ccache、sccache、cHash、Bazel、[[Buck2]]、FASTBuild、distcc
- **同会议**：[[ATC-2025]]
- **对比**：cHash（同作者 ATC'17 AST 级方案，仅 C）、TASTING（同作者 ICSOFT'22 AST hash 用于测试复用）
