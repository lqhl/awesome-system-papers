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

> **一句话总结**：观察到 C/C++ `__attribute__` 能对单个函数/变量/语句做 option 无法做到的细粒度编译控制，ATLAS 在种子程序上随机插入 attribute 并配对激活 option，比无 attribute baseline 平均多发现 109.1% bug，在 GCC/LLVM trunk 报 73 个 unique bug（58 已确认或修复）。

## 问题与动机

[[Compiler-Testing]] 长期依赖 [[Csmith]]、[[YARPGen]]、EMI 等生成/变异测试程序，再叠加不同 compilation option（`-O1`…`-O3`、sanitizer、独立优化 pass）做 stress / [[Differential-Testing]]，已在成熟 [[GCC]] / [[LLVM]] 上挖出大量 bug。但 compilation option 默认作用于**整个程序**，无法让「函数 A 强制 inline + 函数 B 关闭 ASan」这类 per-element 组合同时出现。

C/C++ 的 attribute（`always_inline`、`no_sanitize_address`、`optimize(...)`、`vector_size`、`packed`、`noreturn`、`pure` 等）在 frontend 解析后会影响 semantic analysis、optimization、codegen 各阶段，粒度比全局 flag 更细。Figure 1 的 GCC bug 43234 表明：给 `foo()` 单独加 `optimize("-ftree-loop-distribution")` 会 crash，而全程序开同一 option 不会——说明 attribute 能触达 option-only 探索不到的编译状态。然而此前几乎没有工作**系统化**把 attribute 当作 fuzz 维度。

作者 claim 的边界是：在已有合法 C 种子程序上，通过 attribute-guided mutation **扩大 compilation space exploration (CSE)**，提高 ICE / crash 发现率；不是新的程序生成器，也不验证生成代码的运行时语义正确性（oracle 是编译器是否 crash）。

## 关键观察 / 隐含假设

- **观察 1**：attribute 与 compilation option 的**交叉组合**能触发 option 单独或 attribute 单独无法复现的罕见编译路径（如 `always_inline` 的 `foo()` 被内联进带 `no_sanitize_address` 的 `bar()`，全局 `-finline-functions` + `-fsanitize=address` 仍不 crash）。
  - **依赖假设**：测试目标是 C 前端 + middle-end + backend 的 ICE/编译失败；attribute 语义在 GCC/LLVM 文档中有明确定义；种子程序本身可编译。
  - **可能失效场景**：Rust / Go 等无等价 attribute 机制的语言；attribute 被宏完全隐藏、parser 忽略的路径；只关心 miscompilation（需 differential execution oracle）时，crash-only oracle 覆盖不足。

- **观察 2**：现有 fuzz 已把「全局 option 组合」挖得较深，**per-element 编译策略**仍是低密度区域；向函数/变量/语句随机插 attribute 能显著提高 compiler 代码覆盖率（GCC line +30,519、LLVM line +41,806 vs RO）。
  - **依赖假设**：LibTooling 解析出的 AST 位置与编译器实际处理位置一致；随机插入的 attribute 在类型检查通过后即可进入后续 pass；coverage 提升与 bug 发现正相关。
  - **可能失效场景**：大量 attribute 导致语义非法或编译早期拒绝，使有效测试时间下降（论文报告 ATLAS compilable 比例低于 RO/EMI）；coverage 饱和后边际 bug 率下降（RO 在 Csmith 上约 40h 饱和，ATLAS 10 天内仍持续发现）。

- **观察 3**：许多高价值 attribute 在真实软件中常见（`optimize`/`optnone` 用于调试与 benchmark，`simd` 用于 HPC，`aligned`/`vector_size` 用于 SIMD 代码），因此 attribute 触发的 bug 并非纯人造边角。
  - **依赖假设**：文档列出的 attribute 集合与生产代码使用分布有重叠；trunk 测试发现的 bug 会出现在多版本 release 中（Figure 7：GCC 4 个 bug 跨越 8 年、LLVM 4 个跨越 6 年）。
  - **可能失效场景**：论文排除 GPU 专用 attribute；C++ 模板/宏展开后 attribute 附着点与手写代码不同；仅测 trunk daily build，与 LTS 发行版维护分支的 bug 池可能错位。

- **假设 1**：FlipCoin 随机插入 + 类型约束筛选 + attribute→option 映射（Algorithm 3）足以系统探索 CSE，无需语义保持变异（不像 EMI 要求 I/O 等价）。
  - **证据强度**：**中强**——73 个 trunk bug、58 确认；但 24/73 仅 attribute 即可触发，49/73 仍依赖 option，说明 option 维度不可缺；且未证明已覆盖全部 attribute×option 空间。

- **假设 2**：10 天 Correcting Commits 对比 GCC-5.1 / LLVM-5.0.0 的 bug 数可代表 ATLAS 相对 RO/AO/EMI 的效率优势。
  - **证据强度**：**中**——方法被社区广泛使用，但仍是近似计数；选旧版本是因为 sanitizer 支持与 bug 池已部分耗尽，有利于公平对比，却可能低估 trunk-only 长期 fuzz 的绝对发现量。

## 核心方法

ATLAS 四阶段流水线（Figure 3）：Collect → Insert Attributes → Select Options → Validate。

**Collect（§3.1）**：用 [[LLVM]] LibTooling 解析种子程序 [[AST]]，收集函数集 \(S_f\)、变量集 \(S_v\)、语句集 \(S_s\)，为每个元素记录类型、名字、位置等属性元组，供后续插入定位。

**Insert Attributes（§3.2, Algorithm 1）**：对每个元素 FlipCoin 决定是否插入；按类型过滤非法组合（如 `noreturn` 不能用于返回 `int` 的函数，`packed` 只用于 struct member）。三类插入：
- **函数**：`noinline` / `always_inline` / `optimize(level|"-pass")` / `pure` / `returns_twice` / sanitizer 相关等；
- **变量**：`vector_size`、`aligned`、`packed` 等；
- **语句**：`#pragma omp simd` 及 `linear(uval(x): y+1)` 等带变量列表的 clause（Algorithm 2）。

每轮遍历生成一个变异程序，重复直到达到 \(N\) 个 variant。

**Select Options（§3.3, Algorithm 3）**：维护 attribute→required option 映射 \(\mathcal{M}_o\)（来自 GCC/LLVM 文档）。例如 `no_sanitize_address` 需 `-fsanitize=address` 才生效；将插入 attribute 对应的 option 合并为程序专属编译选项 \(O\)。

**Validate（§3.4）**：在 \(O\) 基础上再随机抽取至多 5 个额外优化 option（沿用既有研究「平均约 5 个 option 触发 bug」的经验），对 GCC/LLVM 编译；**编译器 crash 即报 bug**，再用 C-Reduce 化简后人工提交。种子来源：GCC/LLVM 回归测试集、[[Csmith]]、[[YARPGen]]。

与 RO（无 attribute）、AO（无 compilation option）、EMI（Hermes 实现）的对比设计见 §4.3。实现与 attribute 列表细节见 [[atc2025-wu-jiangchang]]。

## 设计取舍

- **取舍 1：attribute 插入 vs 语义保持变异**——不做 EMI 式行为等价约束，换取更大变异空间与实现简单；代价是无法发现「编译成功但错误代码」类 miscompilation，oracle 仅限 ICE/crash。
- **取舍 2：随机 FlipCoin vs 定向搜索**——低实现复杂度、易与任意种子生成器叠加；牺牲对 attribute 组合的结构化探索，可能重复无效组合；论文未报告 mutation 调度策略的收敛性。
- **取舍 3：类型合法即接受 vs 语义可执行性**——插入后 compilable 比例低于 RO/EMI（如 Csmith 上 ATLAS 30,170/46,416 compilable vs RO 53,458/53,481），用覆盖率与 bug 数换吞吐。
- **取舍 4：GCC/LLVM 双栈 vs 单一 IR**——覆盖主流 C 工具链；需维护两套 attribute 集合与 \(\mathcal{M}_o\)，且排除 GPU attribute，不覆盖 CUDA/HIP 等路径。
- **取舍 5：trunk 连续测试 vs 固定 release**——trunk 利于抢先报 bug、减少 duplicate（§4.1）；效率对比却用 GCC-5.1/LLVM-5.0.0，两套评估目标不完全一致。
- **边界条件**：最适合已有合法 C 种子 + 需要刺激 frontend/middle-end/optimization 交互的场景；对「纯全局 opt 空间」已饱和的编译器版本，增益主要体现在 attribute-only 触发的 24 个 bug 及 ATLAS 独占 unique bug（Csmith 上 10 个，约 20.4%）。

## 实验与结果

**RQ1 — Bug finding（trunk 实战）**：
- 共报告 **73** 个 unique bug（GCC **44**，LLVM **29**），**58** 已确认或修复，**17** 已修复
- **49** 个需 compilation option 才触发，**24** 个仅靠 attribute 插入即可触发
- GCC 侧 1 个 P1（#114687）、14 个 P2；部分 bug 影响自 GCC-5 / LLVM-5 起长达 6–8 年的版本（Figure 7）
- 组件分布（Table 2）：Front-End **23**（31.5%）、Middle-End **21**、Optimization **16**、Back-End **13**
- 高频触发 attribute：`returns_twice`、`vector_size`、`sanitize`、`simd`、`optimize`、`always_inline`/`noinline` 等（Table 3）

**RQ2 — 效率（10 天，GCC-5.1 + LLVM-5.0.0，Correcting Commits）**：

| 生成器 | 方法 | GCC | LLVM | 合计 |
|--------|------|-----|------|------|
| Csmith | RO / AO / EMI / **ATLAS** | 13/19/17/**32** | 5/11/11/**17** | 18/30/28/**49** |
| YARPGen | RO / AO / EMI / **ATLAS** | 8/12/10/**25** | 6/10/9/**13** | 14/22/19/**38** |

- ATLAS 相对无 attribute baseline 平均多 **109.1%** bug；覆盖 AO 发现的全部 bug，并有 Csmith **10**、YARPGen **11** 个独占 bug
- EMI 仍有少量独占 bug（更多变异 + 更高 compilable 吞吐）；ATLAS 在相同周期内 compilable 数更低
- 时间趋势（Figure 9）：RO 约 40h 饱和，ATLAS/AO 在 10 天内持续发现

**RQ3 — 代码覆盖率（10k Csmith 种子，GCC-15 / LLVM-19，编译限时 10s）**（Table 5，括号内为相对 RO 增量）：
- GCC：**36.3%** line（+30,519）、**37.6%** function（+1,152）、**23.2%** branch（+24,958）
- LLVM：**36.8%** line（+41,806）、**27.6%** function（+1,953）、**21.7%** branch（+12,954）
- 四项方法百分比接近，但 ATLAS 在绝对覆盖行/分支数上最高

**环境**：48-core Intel 2.30GHz、120GiB RAM、Ubuntu 22.04；artifact 提供 Docker 镜像。

## Critical Analysis

### 论证链条

动机案例（Figure 1/2）直接支撑「attribute × option 可触发新 bug」；流水线把 observation 映射到 Collect→Insert→Option→Crash oracle，逻辑闭合。trunk 73 bug + 效率实验 109.1% 提升 + 覆盖率增量形成三角验证。

薄弱跳步在于：将「attribute 提升 CSE」外推为「应成为 compiler testing 标准层」（§5.2 集成主张）——论文未量化集成到 EMI/[[Csmith]] 后的**边际** bug 率，也未证明 109.1% 在最新 release（非 GCC-5.1）上仍成立。Abstract 的 109.1% 来自 controlled 10 天实验，与 trunk 73 bug 的绝对数量是不同实验设定，读者需分开解读。

### 假设压力测试

- **论文已证明**：在 C 种子 + GCC/LLVM 上，attribute 插入能提高 bug 发现、覆盖率，且不少 bug 对应真实常用 attribute。
- **可能失效**（推断）：
  - **语言扩展**：仅 C，未测 C++20 `[[attribute]]`、Rust `#![feature]` 等；模板实例化可能改变 attribute 附着语义。
  - **Miscompilation**：crash-only oracle 对 silent wrong code 无感；与 EMI 或 differential execution 结合才有语义保证。
  - **Workload 漂移**：若编译器减少 per-function attribute 支持或改为 IR metadata 统一表达，当前 AST 插入策略需重做。
  - **规模**：单程序插入密度、\(N\) 个 variant 与 10s 编译限时如何外推到 CI 级小时长 fuzz，论文未建模。

### 实验可信度

- **Benchmark**：种子含官方回归集 + Csmith + YARPGen，代表性强；效率实验刻意选旧版以利用 Correcting Commits，与 trunk 实战互补。
- **Baseline**：RO/AO 隔离 attribute 贡献合理；EMI 选 Hermes（OOPSLA'16 live mutation）是强对手，但 EMI 更高 compilable 数引入混淆因子，论文诚实报告 EMI 独占 bug。
- **Ablation**：AO vs ATLAS 证明 option 必要；RO vs ATLAS 证明 attribute 必要；缺少对 FlipCoin 概率、\(N\)、option 个数上限 5 的 sensitivity。
- **Metrics**：聚焦 bug 数与覆盖率，**未报告** fuzz 吞吐（programs/hour）、去重后 bug 率、误报率；Correcting Commits 精度依赖后续 fix commit 可识别。

### 系统性缺陷

- **人工环节**：crash 后需人工分析 + C-Reduce + 提 issue，难以无人值守闭环；LLVM 开发者响应慢，确认率低于 GCC（论文自述）。
- **可观测性**：论文未讨论 fuzz  campaign 的统计面板、重复 crash 聚类、attribute 命中率——**论文未讨论**。
- **资源与尾延迟**：未分析高 sanitizer + 高 opt 组合下的单测编译尾延迟分布；48-core 工作站结果难直接映射 modest CI 机器。
- **隔离与恢复**：并行 continuous testing 时缓存、编译器临时文件、竞态崩溃的隔离策略——**论文未讨论**。
- **兼容性**：attribute 与 LTO、PGO、交叉编译的组合未被系统评测。

## 局限与 Future Work

- **局限 1**：只覆盖 C、排除 GPU attribute；双编译器文档驱动，attribute 集合随版本漂移需持续维护。
- **局限 2**：Oracle 仅限编译期 crash，不覆盖 miscompilation、错误诊断、debug info 损坏等其它 compiler reliability 维度。
- **局限 3**：变异不保证语义合法，compilable 率低于 RO/EMI，整体 fuzz 吞吐受限；`vector_size` 等 attribute 易与程序约束冲突。
- **局限 4**：bug 计数依赖 Correcting Commits 近似，且效率实验与 trunk 实战使用不同编译器版本。
- **Future work 1**：与 EMI、Creal 等语义保持生成器**级联**——先 EMI 扩程序结构，再 ATLAS 插 attribute，量化边际 unique bug（§5.2 已提出方向，缺实验）。
- **Future work 2**：把 attribute fuzz 与 miscompilation oracle（differential execution、translation validation）结合，覆盖 ICE 之外的错误。
- **Future work 3**：对高产出 attribute（`sanitize`×inline、`vector_size`、`simd`）做加权或演化搜索，替代纯 FlipCoin，在相同 compilable 预算下提高 unique bug 率。
- **Future work 4**：扩展至 C++ / Rust 属性系统，或 IR 级 metadata fuzz，观察 frontend 插入 vs IR pass 插入的覆盖差异。

## 相关

- **相关概念**：[[Compiler-Testing]]、[[Fuzzing]]、[[Differential-Testing]]、[[AST]]、[[LLVM]]、[[GCC]]、[[AddressSanitizer]]
- **同类系统**：[[Csmith]]、[[YARPGen]]、EMI（Hermes）、GrayC、Creal、ClozeMaster
- **同会议**：[[ATC-2025]]、[[IRHash-ATC25]]、[[Bin2Wrong-ATC25]]、[[HEC-ATC25]]
- **对比**：RO/AO 展示 attribute 与 option 的分解贡献；[[Bin2Wrong-ATC25]] 在反编译器重编译链路上做差分 fuzz，与 ATLAS 的「编译前端属性探索」形成工具链上下游互补