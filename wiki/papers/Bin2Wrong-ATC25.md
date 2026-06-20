---
type: paper
name: Bin2Wrong
full_title: "Bin2Wrong: a Unified Fuzzing Framework for Uncovering Semantic Errors in Binary-to-C Decompilers"
authors: [Zao Yang, Stefan Nagy]
venue: ATC
year: 2025
tags: [fuzzing, decompiler, binary-analysis, security, differential-testing, compiler-fuzzing]
source_pdf: "[[atc2025-yang-zao.pdf]]"
source_md: "[[atc2025-yang-zao]]"
---

# Bin2Wrong: a Unified Fuzzing Framework for Uncovering Semantic Errors in Binary-to-C Decompilers (ATC 2025)

> **一句话总结**：关键观察是反编译语义错误常由 source × compiler × optimization × executable format 的特定组合触发，而 DecFuzzer/Cornucopia 等 prior fuzzer 只沿单一维度变异；Bin2Wrong 把四维统一编码进 AFL++ testcase 并做 decompiler-agnostic 差分执行，在 7 个主流反编译器上把 binary diversity 提升 10.39×/17.18×、发现 48 个语义 bug（30 已确认），并触发 Binary-Ninja 核心 control-flow structuring 重构。

## 问题与动机

[[Binary-Decompilation]] 把可执行文件还原成 C 代码，是恶意软件分析、闭源漏洞挖掘、安全加固和第三方补丁等系统任务的基础设施。反编译器的目标是恢复与原始源码语义等价的高层表示，但编译过程会剥离类型、变量名和高层结构；再加上 [[ELF]]/[[PE]]/[[Mach-O]] 格式差异、不同编译器代码布局以及 inlining、dead code elimination 等优化，反编译器极易产出**语义错误**的 C 代码——哪怕一个 branch condition 误判，也会级联破坏 control-flow 分析等下游任务。

近年来已有针对反编译器语义错误的 fuzzing 工作（DecFuzzer、Cornucopia、D-Helix、[[DSmith]]），也确实挖出过 bug。但作者对 64 个公开语义缺陷的分类表明：executable 受 **source、compiler、optimization、executable format** 四个维度共同塑造，而现有 fuzzer 各自只覆盖狭窄子集——例如 DecFuzzer 只变异 source、完全不动 optimization；Cornucopia 一次只探索单一编译器的 optimization suite；D-Helix 需要为每个 decompiler 的 IR 做逐指令语义建模，扩展到新 decompiler 估计要 40 人天。结果是大量由「特定 source + 特定编译参数」组合触发的边角错误长期漏测，直到真实用户踩坑。

本文 claim 的边界是：聚焦 **binary-to-C** 反编译器的 **语义正确性**（非 cosmetic 可读性问题），用 **decompiler-agnostic** 的黑盒差分测试覆盖开源与闭源工具；不试图穷尽万亿级搜索空间，而是用统一 mutation 做系统性 breadth-first sampling。

## 关键观察 / 隐含假设

- **观察 1：公开语义 bug 高度分散在 data expression、control structure、data object/type 和 compilation-specific 四类，且许多与特定编译配置强相关。** 作者梳理 [[Ghidra]]、Angr、Binary-Ninja、RetDec 等 issue tracker，发现 switch-case、goto、floating-point literal、calling convention、LTCG/-Ofast 等组合常触发错误；仅测 Linux [[ELF]] + 单一编译器会系统性漏掉 [[PE]]/[[Mach-O]] 和 MSVC/TCC 特有布局。
  - **依赖假设**：历史 issue 分布能代表未来 fuzz 应优先覆盖的 failure mode；四维度联合变异比单维度更能命中这些模式。
  - **可能失效场景**：LLM/神经网络反编译器（[[Coda]]、[[ReSym]]）的错误分布可能与启发式 decompiler 不同；obfuscated binary 的缺陷模式未被纳入。
  - **证据强度**：中到强。基于 64 个公开 bug 的 taxonomy 有说服力，但样本偏向已报告、可复现 issue。

- **观察 2：同一 source 经不同 compiler/optimization/format 会产生语义上截然不同的 binary，而 prior fuzzer 的 hardcoded 编译参数导致 binary diversity 极低。** 论文用 BinDiff/Radiff2 度量，Bin2Wrong 在 source+compiler+optimization 三维同时变异时 diversity 最高；相对 Cornucopia/DecFuzzer 分别高 10.39×/17.18×。
  - **依赖假设**：binary diversity 是发现语义 bug 的主导因素，高于单纯的 decompiler code coverage 增益。
  - **可能失效场景**：若大量 bug 集中在少数 compiler 的固定 pattern，unified mutation 的额外搜索开销可能不如 targeted generation；论文自己也指出 [[Reko]] 上 coverage 反而略低。
  - **证据强度**：强。Table 3/5 ablation 显示「ALL THREE」维度组合同时最大化 diversity 和 coverage-increasing binary 比例（均值 76.34%）。

- **观察 3：decompiler-agnostic 的 recompile-and-compare oracle 足以支撑闭源与开源工具的统一测试，且 recompilation patching 可将可重编译率从 11.6% 提到 47.8%。** 借鉴 [[Csmith]] 的全局 checksum 差分执行，Bin2Wrong 只分析 decompiler 输出的 C，避开 D-Helix 对 VEX/P-code 等 IR 的逐指令建模。
  - **依赖假设**：自包含、无外部输入的 generated program 上，variable-level checksum 能捕获语义偏差；语法 patching 不会引入 false positive。
  - **可能失效场景**：需要外部输入、非确定性、浮点环境差异、undefined behavior 或 recompilation 失败（~52%）的 case 无法进入 oracle；论文未讨论 UBSan/确定性执行。
  - **证据强度**：中。30/48 bug 被开发者确认且无 patching 导致的 false positive 报告，但 oracle 天然有 coverage ceiling。

- **假设 1**：单函数 [[Csmith]] 风格 seed + libClang AST mutation 能代表真实 world binary 的语义挑战面。
  - **证据强度**：弱到中。支持 switch、string/float literal、goto 等比 prior fuzzer 更广，但明确未覆盖 union/struct/array；程序规模极小。

- **假设 2**：24 小时 AFL++ campaign + 5 轮 trial 足以对比 state-of-the-art 并发现 impactful bugs。
  - **证据强度**：中。Mann-Whitney U 检验支持 diversity/coverage 差异，但 bug 发现高度依赖 manual triage（每个 bug ~10 分钟）。

## 核心方法

Bin2Wrong 构建于 AFL++ v4.09c，核心是把影响 binary 生成的四维因素**合并为单一 unified testcase**（Figure 2）：

**Compilation mutation（前 2048 字节）**：byte 0 选择 6 个编译器之一（[[GCC]]、[[Clang]]、TCC、ICX、[[MSVC]]、AppleClang）；bytes 1–2047 每位映射一个 optimization flag，奇偶表示开/关。换编译器时重映射 optimization 字节；不兼容组合 fallback 到 -O1/-O3 等标准级别，解决 100% optimization 相关编译失败。Linux 上通过 [[WINE]]/Darling 兼容层首次在 fuzz 中同时生成 [[ELF]]、[[PE]]、[[Mach-O]]，共覆盖 **5,183** 个 optimization flags。

**Source mutation（AST 层）**：基于 libClang AST API 的自定义 mutator，针对 Table 1 中的真实 bug 模式设计——表达式删/复制/子表达式扩展/算符替换；控制结构注入 loop break/continue、always-true/false 条件、goto 重定向、switch 表达式替换；数据层 string/numeric literal 变异与 type cast。保守设计避免移动/删除变量声明，并用 AST guardrail 防止非法 continue/break 注入。

**Decompiler-agnostic oracle**：变异后按 testcase 编译 binary → 送入目标 decompiler → 对输出 C 做轻量 syntax patching（`void* const`→`char*`、重命名、`typedef` 注入、`extern` 补全等）→ 重编译 → 与原 binary 做全局 checksum 差分执行。仅 52% 左右能完成重编译，但论文强调这不妨碍其成为 bug 发现最多的方案。

**工程流程**：5 个支持 QEMU coverage tracing 的 decompiler 用 grey-box 模式（Binary-Ninja、R2Ghidra、Reko、RetDec、Rev.Ng），Angr/Relyze 用 black-box；seed 为 10 个 [[Csmith]] 程序（手工补 string literal）。Bug 经人工最小化后报给开发者。深度实现细节见 [[atc2025-yang-zao]]。

## 设计取舍

- **统一四维 mutation 换搜索空间爆炸与 campaign 成本**：不追求 exhaustive，靠 AFL++ 式随机采样 breadth；trillions 级配置空间下「同时变异」比逐维 isolate 更能发现 multi-dimensional edge case，但单次 compile+decompile+recompile 链远比纯 source fuzz 昂贵。
- **Decompiler-agnostic C-level oracle 换 IR 精度**：避开 D-Helix 每 decompiler 40 人天的 IR 集成成本，直接测闭源 Binary-Ninja；代价是无法定位 IR 阶段根因，且受 recompilation rate（47.8%）硬上限。
- **轻量 syntax patching 换吞吐**：作者明确优先 fuzzing speed 而非 100% recompilation；84% 失败来自 undeclared identifier。更强 program repair 可能显著降低 24h bug yield。
- **保守 source mutation 换 executable 稳定性**：不注入/移动声明，避免 mutation 本身引入 crash；可能漏掉依赖复杂数据布局（struct/union/array）的 decompiler bug。
- **排除 obfuscation/linker mutation 换聚焦语义恢复**：混淆交给专用 deobfuscation 插件；linker 相关问题多为 syntactic parse failure 而非语义错误——合理 scope，但限制了 malware/加固场景的外推。

## 实验与结果

- **设置**：Ubuntu 22.04、i9-12900K、64GB RAM；7 个 x86 decompiler（Angr、Binary-Ninja、R2Ghidra、Reko、Relyze、RetDec、Rev.Ng）；对比 Cornucopia（Clang + 全 optimization suite）和 DecFuzzer（GCC + -O0）；每 fuzzer 5 轮 × 24h；统计检验 Mann-Whitney U、p=0.05。
- **Binary diversity**：BinDiff 均值相对 Cornucopia/DecFuzzer 分别高 **10.39×** / **17.18×**；三维联合变异（ALL THREE） diversity  consistently 最高。
- **Code coverage**：均值 edge coverage 高 **1.16×** / **1.32×**；coverage-increasing binary 比例高 **3.56×** / **59.61×**（geo mean）。[[Reko]] 上 coverage 略低于 Cornucopia，但 binary quality 指标远优。
- **Bug discovery**：共 **48** 个新语义 bug，**42** 个 Bin2Wrong 独占，**30** 已确认/修复；Cornucopia 10 个、DecFuzzer 0 个。按 decompiler：Binary-Ninja 11、RetDec 11、Angr 9、Relyze 7 等。
- **Root cause 分析**：68.75% 为 data recovery，20.83% expression，10.42% control structure；floating-point 被还原为 hex integer 是跨 Angr/Binary-Ninja/Reko 的共性 issue；switch-case 在 MLIL→HLIL 阶段被错误拆成独立 if 触发 Binary-Ninja High Severity bug 并导致 core restructuring。
- **Compilation 维度**：仅 3 个 bug 直接由 optimization 组合触发；8 个仅出现在单一 format；多数 bug 跨多 compiler/format 但不覆盖全部——说明 unified exploration 的必要性。Reko 在 [[Mach-O]]/[[ELF]] 上 calling convention 参数顺序错误（Figure 6）、TCC 双级 indirection string 布局（Figure 7）均为 prior ELF-only fuzzer 难以触发的案例。
- **Impact**：Binary-Ninja 8 个 bug 有 severity 评分（1 High / 4 Medium / 3 Low）；开发者对 Angr、Binary-Ninja、R2Ghidra、Reko、Rev.Ng 全部确认。

## Critical Analysis

### 论证链条

论文的 observation → design → result 链条整体闭合。先用 64 个公开 bug 证明四维度都重要，再用 Table 2 说明 prior work 的 dimensional gap，然后提出 unified testcase 直接回应该 gap；Table 3/5 ablation 把「联合变异」与更高 diversity/coverage-increasing ratio 挂钩，Table 6 把 diversity 与更多 unique bugs 连接，§5.4 的 case study 进一步展示这些 bug 确实来自 source×compilation 组合而非单维噪声。

最强证据是 **bug 独占率**（42/48）和 **开发者确认**（30/48），加上 Binary-Ninja 结构性修复这一外部验证。较弱环节是作者自己承认 bug 发现与 diversity 的相关性可能强于 coverage（§5.3），但缺少严格因果 ablation（例如固定 diversity、只变 oracle 或只变 mutation policy 的对照）。

### 假设压力测试

**Recompilation oracle 是最脆环节**。~52% decompiled 程序无法进入差分执行，其中 undeclared identifier 占 84%；这意味着大量潜在语义错误可能被 silently dropped。论文用「仍找到最多 bug」反驳，但这不能证明 false negative rate 低——也许 dropped cases 里还有同等数量 bug。对闭源 decompiler 输出质量更差或 C++ 反编译场景，上限会更低。

**Single-function micro-program 假设**限制外推。真实二进制含多函数交互、全局状态、动态链接、C++ vtable/exception；Bin2Wrong 刻意用自包含单函数 + placeholder globals 映射 locals，简化了 calling convention 和 inter-procedural 分析压力，但也可能高估/低估某些 decompiler 在规模程序上的表现。

**Cross-platform compilation via WINE/Darling** 引入 fidelity 风险。MSVC/AppleClang 在兼容层上的 binary 是否与原生 Windows/macOS  toolchain 行为一致，论文未做系统验证；若兼容层引入额外 artifact，可能触发 decompiler bug 却不代表真实 deployment。

**Manual bug triage** 使结果难完全客观复现。每个 bug ~10 分钟人工最小化，无自动化 fault localization；RetDec/Relyze 未回复导致 confirmation 率不完整。长期 fuzzing service 需要 triage 流水线，否则 throughput 优势会被人力抵消。

### 实验可信度

Baseline 选择合理：Cornucopia 和 DecFuzzer 是近期代表性工作，且配置遵循原论文；省略 D-Helix（仅支持 2/7 decompiler）和 [[DSmith]]（source 更窄）有说明。7 个 decompiler 覆盖开源+商用，比多数 prior work 广。

主要缺口：（1）**仅 x86 + C**，未测 ARM/RISC-V、C++、Go/Rust 新兴 decompiler；（2）**24h×5 trials** 对 fuzzing 偏短，未报告多周 campaign 的 duplicate bug rate 或 saturation；（3）**DecFuzzer 零 bug** 令人警惕——需确认是工具失效还是配置/effort 不公平，论文未展开；（4）coverage 工具对 [[Reko]] 用不同 tracer（AFL-Showmap vs AFL-QEMU-Cov），跨 decompiler 比较需谨慎；（5）未量化 syntax patching 或 checksum oracle 的 false positive/false negative。

### 系统性缺陷

**尾延迟与资源成本**：每次 testcase 要走 compile→decompile→patch→recompile→双份执行，吞吐远低于 crash-guided fuzzing；论文优先 speed over repair completeness，但未给出 end-to-end executions/hour 或 dollar cost，难以评估 production 部署可行性。

**隔离与确定性**：并行 fuzz 7 个 decompiler 的环境隔离、decompiler 内部 timeout、浮点/UB 导致的 flaky checksum 均未讨论。对 security workflow，flaky oracle 会伤害 triage 可信度。

**可观测性**：闭源 decompiler 失败时只有「checksum mismatch」，无 IR 阶段定位；运维上难以把 48 个 bug 自动归类到 CFG recovery vs dataflow vs codegen pipeline。

**兼容性**：依赖 AFL++ QEMU mode 的 decompiler 需要可 instrumentation 的 binary build；对 heavily obfuscated 或 non-standard binary，workflow 可能直接前置失败——论文在 §6.3 承认 obfuscation 未覆盖。

## 局限与 Future Work

- **局限 1：recompilation oracle 天花板（47.8%）**。可测方向：引入 stronger semantic-preserving repair 或 interpreter-based differential testing（不重编译 decompiled C），对比 bug recall vs throughput trade-off。
- **局限 2：source 模型缺少 struct/union/array 与多函数程序**。可用 [[GrayC]]/[[YARPGen]] 式扩展或 LLM program generator（[[Fuzz4All]]）生成更大型、跨函数 testcase，测量 bug 类型分布如何变化。
- **局限 3：未覆盖 obfuscation 与 malformed binary**。Future work 可把 control-flow flattening 等作为第五维 mutation，或专门测 deobfuscation plugin + decompiler 组合链路。
- **局限 4：搜索策略仍是 uniform random mutation**。论文提议 targeted mutation（保证特定 source+optimization 组合产生 interesting machine code）可客观验证：固定 budget 下 targeted vs unified-random 的 unique bug rate。
- **局限 5：manual triage 瓶颈**。应构建 decompiler-specific minimizer/deduplicator 或与 symbolic execution 结合做 crash-free semantic diff root-causing，并报告 triage 人力成本曲线。

## 相关

- **相关概念**：[[Fuzzing]]、[[Differential-Testing]]、[[Coverage-Guided-Fuzzing]]、[[Binary-Decompilation]]、[[Compiler-Fuzzing]]、[[Control-Flow-Recovery]]
- **同类系统**：DecFuzzer、Cornucopia、D-Helix、[[DSmith]]、[[Csmith]]、AFL++
- **目标工具**：Binary-Ninja、[[Ghidra]]、Angr、RetDec
- **同会议**：[[ATC-2025]]
- **源材料**：[[atc2025-yang-zao]]、[[atc2025-yang-zao.pdf]]