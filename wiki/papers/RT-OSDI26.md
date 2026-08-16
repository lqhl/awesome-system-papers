---
type: paper
name: RT
full_title: "RT: Regular Types for the Streaming Shell"
authors: [Zekai Li, Lukas Lazarek, Evangelos Lamprou, George Kapetanakis, Konstantinos Mamouras, Nikos Vasilakis]
venue: OSDI
year: 2026
tags: [shell, type-systems, static-analysis, automata, reliability]
source_pdf: "[[osdi26-li-zekai.pdf]]"
source_md: "[[osdi26-li-zekai]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# 流式 Shell 的正则类型系统（OSDI 2026）

> **原题**：RT: Regular Types for the Streaming Shell

> **一句话总结**：Shell pipeline 的很多错误来自“上游可能输出的行”不满足“下游能安全接收的行”；RT 用正则语言表示流、以语言包含检查组合，并用多态类型、FST、环境具体化和 annotation 提高精度，在 730 个正确与 224 个 buggy 程序上得到 91% 总准确率、平均 0.020 秒，但无 annotation 时对 buggy 程序只识别 72%，正确性还依赖手写 command type database。

## 问题与动机

Unix [[Shell]] 可以把任何语言实现的命令用 byte stream 串起来，但接口没有类型。文件名带空格会被 `xargs` 错拆、文本字段格式可能与下游不合、`sort` 忘写 `-n` 会按字典序排数字，错误常到长任务运行中甚至破坏文件后才出现。ShellCheck 擅长语法模式，却不知道一段 pipeline 中每条可能的输出长什么样。

完整建模 shell 语义又太难：命令有大量 flag，会读取文件、环境和 filesystem state；`awk`/`sed` 本身接近小语言；跨行排序、计数和副作用也不适合简单类型。RT 主动收窄目标，只检查 line-oriented streaming core：如果上游每一行可能属于语言 `L_out`，下游只保证安全接受 `L_in`，就要求 `L_out` 是 `L_in` 的子集。

选择正则语言有三个实际好处。Unix 用户熟悉 regex；regular-language inclusion 可判定且实现成熟；不包含时还能从差集自动取出反例字符串。论文的例子中，`./ book0.txt` 就具体说明 `grep` 的输出为何会被 `xargs cat` 按空格拆坏，比单纯提示“类型不匹配”更容易定位。

## 关键观察 / 隐含假设

- **观察 1：许多命令不需要完整语义，也能用“每一行的形状”发现严重组合错误**。路径、数字、delimiter、字段格式和危险命令的输入都能用 regular language 精确或保守近似（§2–§3）。
  - **依赖假设**：目标 bug 确实由逐行 stream shape 决定。
  - **可能失效场景**：排序、唯一性、行数关系、跨行状态、JSON nesting、filesystem effect，以及文件名本身含 newline，都超出这个抽象。
- **观察 2：组合安全可以化成语言包含，错误可以化成差集 witness**。RT 检查 `L_upstream ⊆ L_expected`；失败时从 `L_upstream \ L_expected` 的 automaton 取一个字符串（算法 1、§3.4）。
  - **依赖假设**：command input type 正确描述其安全域，output type sound 地覆盖全部可能输出。
  - **可能失效场景**：手写声明漏掉 flag 语义或错误 under-approximate output 时，形式化检查本身正确也会漏报。
- **观察 3：`cat`、`sort` 等命令的最精确输出取决于输入，不能为每次调用写固定 regex**。bounded polymorphism 用 `∀α. α→α` 保存输入 language，同时给 `sort -n` 之类的命令加输入约束（§3.2）。
  - **依赖假设**：命令对行集合的关键关系可以由一个输入 type variable 表达。
  - **可能失效场景**：输出依赖多个输入之间的关系、顺序或计数时，需要更强的 relational type。
- **观察 4：`tr`、`cut`、`sed` 的变换超出普通集合运算，但许多仍是 finite-state transduction**。RT 把 FST 应用于输入 automaton，结果仍是 regular language（§4）。
  - **依赖假设**：常见调用落在可精确转换的子集，或 sound over-approximation 的 false positive 可接受。
  - **可能失效场景**：复制任意字符串、复杂 capture 或完整 `awk` 语义不是 regular transformation；一般 `translate-match` 只能放大输出集合。
- **假设 1：手工 command database 能长期覆盖实际调用**。当前覆盖 71/106 个 GNU coreutils，以及 GitHub 集合中 86% 的 command invocation；未知命令退化为 `.*→.*`。
  - **证据强度**：中弱。覆盖数字明确，但论文没有独立验证每条 declaration，也没有量化新版本/平台 flag 的维护成本；fallback 会选择不报错。

## 核心方法

正则流类型（regular stream type）是“流中任意一行可能出现的字符串集合”，语法以 POSIX ERE 为基础，并增加 intersection `&` 与 negation `!`。RT 刻意不支持 lookaround 和 backreference，以保持 regularity。命令类型把输入、输出及必要时 stderr 等多个 stream 的类型配对；sound input 应位于命令安全域内，sound output 必须包含所有真实输出，precision 则决定误报多少。

类型数据库类似语言的 typed standard library。配置文件先解析命令与 flag，再为 invocation 构造类型，例如 `grep` 的输出是输入语言与 pattern 的交集，`xargs cat` 作为整体构造。找不到声明时，RT 使用 `.*→.*`，避免阻塞分析但也基本放弃检查这一 stage。用户可通过 `rti` 查看和扩展数据库。

type checker 沿 pipeline 或 DAG 的拓扑顺序传播中间 stream type。简单类型检查上游 output 是否包含于当前 command input；多态类型先检查 bound，再把实际输入替换到输出中的 `α`。不包含时构造 automata difference 并给出 witness。这个过程只证明声明所表达的 stream compatibility，不证明命令副作用或脚本整体业务结果正确。

为表达复杂变换，RT 增加 `reverse`、`translate-match`、`line-extract`、`translate-chars` 和 `field-select`。每个 operator 构造 deterministic、functional nondeterministic 或 general nondeterministic FST，与输入 DFA 做 product，再把 transition output 投影成结果 NFA。`field-select` 与 `translate-chars` 可精确计算；一般 `translate-match`/`line-extract` 保证 sound，却可能产生更大的语言和 false positive。

三类可选精化补上下文。环境具体化（concretization）在第二遍直接读取本地文件和环境变量，把当前内容变成有限 type；第一遍仍先找环境无关错误。`assume`/`input` annotation 提供假设，`assert`/`expect`/`output` 增加待检查性质。四个 heuristic 另外报告必为空输出、给无输入命令传值、必然 no-op 的 filter/transform，以及对 numeric input 使用 lexicographic `sort`；这些是高概率 bug，不是严格 type error。

实现与 7 组 benchmark 以 MIT license 开源。artifact 包括 checker、71 个 coreutils 覆盖起点、FST/annotation/concretization 实现、全部 benchmark 与复现实验脚本。

## 设计取舍

- **逐行 regular type，换取可判定和快速检查**：能处理常见路径/字段错误并生成 witness；无法表达跨行、递归 structured data 和一般副作用。
- **sound over-approximation，换取不漏掉变换输出**：复杂 `sed` 仍可分析，但放大的 output language 会给正确 pipeline 报错。
- **手工 type database，换取可读、可修改的接口**：命令专家能精确处理 flag；数据库本身成为 trusted specification，未知命令会静默降低保护。
- **annotation/concretization，换取精度**：准确率提高，却把一部分规格责任交给开发者，并引入环境读取与 TOCTOU 风险。
- **heuristic 与 type error 分层**：能发现严格包含关系捕捉不到的常见错误；若 UI 没清楚显示 confidence，可能造成 warning fatigue。
- **边界条件**：最适合短到中等、line-oriented、命令已在数据库中的 pipeline；大型复杂 regex、动态生成命令、循环/跨行状态和 effect-heavy script 不是当前强项。

## 实验与结果

- **语料与配置边界**：suite 共 954 个程序，其中 730 个正确、224 个含至少一个 composition bug；来源包括 57 对 GitHub bugfix 前后脚本、11 个 StackOverflow bug、LadderTypes、Koala、Intercode、120 个 [[LLM|LLM]]-generated bug 和手写测试。RT 数据库覆盖 71/106 coreutils、GitHub 集合 86% 的 invocation（§6.1、表 3）。
- **总体准确率必须分类型看**：无 annotation 时正确分类 703/730 个 correct、161/224 个 buggy，总计 864/954，四舍五入为 91%；对应 correct accuracy 96%、buggy accuracy 72%，即 27 个 false positive、63 个 false negative。加 annotation 后为 716/730 和 210/224，总准确率 97%，两类准确率 98%/94%，false positive/negative 各 14（图 8、表 4–表 5）。
- **与 baseline 的比较**：在 buggy 程序上 RT 为 72%，ShellCheck 与经补充 simple declaration 的 LadderTypes 都约 20%，差 52 个百分点；RT 独有发现 87 个 bug，ShellCheck 独有 5 个，LadderTypes 没有独有发现，但在无 annotation 时仍有 58 个 bug 三者都漏掉（§6.2、图 8 右侧）。ShellCheck 的目标比 RT 更广，论文只统计 pipeline/output 相关 warning。
- **扩展的收益与代价**：无 annotation 时，full RT 正确识别 161 个 buggy/703 个 correct；关闭 heuristic 后变成 94/714，说明 heuristic 多抓 67 个 bug、也多误报 11 个 correct。关闭 FST 后 correct 只剩 583，等价于 false-positive rate 从约 4% 升到约 20%；有 annotation 时 heuristic 把 false negative 从 82 降到 14，约减少 83%。definite warning 在该 corpus 中准确率 100%，possible-bug warning 为 86%（表 4–表 5）。
- **分析时间**：Ubuntu 20.04、8-core Ryzen 7 4800H、16 GB RAM 上，RT 平均 0.020 秒，范围 0.009–0.903 秒；ShellCheck 平均 0.018 秒，LadderTypes 为 3.081 秒。每个程序都少于 1 秒；最大 DFA 为 201 states，最慢的 5-stage pipeline 含一个需 105-state DFA 的复杂 input annotation（§6.3、图 9）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| regular type 能发现真实 shell composition bug | 表 3、图 8：224 个 buggy 中识别 161 个，独有发现 87 个 | buggy accuracy 72%；包含 120 个 LLM-generated 和手写样例 | 强 |
| FST 显著降低粗糙 command type 的误报 | 表 4：关闭 FST 后 correct 分类从 703 降到 583，false-positive rate 约 4%→20% | 当前 command database 与 954-program corpus | 强 |
| annotation 能补上预期输出等缺失规格 | 表 4–表 5：FN 63→14，总准确率 91%→97% | annotation 由知晓程序意图的人提供，编写成本未测 | 强 |
| automata-based checker 在所测程序上足够快 | §6.3：平均 0.020 秒，最大 0.903 秒；DFA 最大 201 states | 多为短 pipeline，未做 adversarial state-explosion 测试 | 强 |
| 91% accuracy 代表对 buggy shell 的高覆盖 | correct 730、buggy 224 的 program-level 聚合 | buggy accuracy 只有 72%，总体数受 correct 类占多数影响 | 中 |

## 批判性分析

### 论证链条

论文选择了清楚而实用的抽象边界：把 stream composition 变成 regular-language inclusion，利用差集给可读 witness，再用 polymorphism 与 FST 避免所有命令都退化成 `.*`。feature ablation 也分别证明 heuristic、FST 和 annotation 的作用。结论不能扩成“给 shell 加了完整静态类型”：RT 只检查声明覆盖到的逐行流关系，业务输出、跨行性质和副作用仍可能完全错误。

### 假设压力测试

command database 是系统的规格根。声明漏掉 flag、平台差异或 error stream，check 算法再严格也无效；未知命令的 `.*→.*` fallback 会让不兼容 stage 穿过去。环境具体化读取的是检查时内容，执行前文件/env 改变会形成 TOCTOU；读取巨大或敏感文件也有成本和隐私问题。Unix filename 可以含 newline，单行 path type 在这种合法输入上也会失真。复杂 capture、`awk`、嵌套 JSON 和跨行排序只能近似或不表达。

### 实验可信度

57 对真实 GitHub bugfix、StackOverflow 与既有 suite 提供了现实证据，作者还人工核对候选 commit，并公开 artifact。另一方面，224 个 buggy 中有 120 个由 LLM 生成，外部真实性有限；730/224 类别不平衡使 91% overall accuracy 看起来高于 72% buggy accuracy。论文没有报告数据库/heuristic 是否在独立 held-out corpus 前冻结，annotations 也可能由已知标签和期望输出的人编写。ShellCheck 不是同一类语义 checker，LadderTypes 又由作者补充 simple declarations，baseline 比较需要按这一口径理解。

### 系统性缺陷

维护 106 个 coreutils 的 flag 组合已经不小，更不用说发行版差异和第三方 CLI；论文没有 command specification 的测试覆盖、版本管理或错误声明回滚机制。warning 是 program-level 评测，一份脚本可能有多个问题，但实验没有报告每个 warning 的 precision/recall、定位质量或开发者修复时间。automata 理论上可能指数膨胀；实验最大只有 201 states，未覆盖恶意或自动生成 regex。错误 annotation 作为 assumption 还可能压掉真实 warning，系统未讨论可信边界和 CI policy。

## 局限与后续工作

- **局限 1**：无 annotation 的 buggy accuracy 为 72%，49/63 个 false negative 来自缺少预期输出规格，说明许多错误不能只靠命令安全域发现。
- **局限 2**：71/106 coreutils 和 86% GitHub invocation 仍留下未知命令，`.*→.*` fallback 不会 fail closed。
- **局限 3**：line-level regular language 不表达跨行、递归结构、命令副作用和完整 shell control semantics。
- **局限 4**：语料含大量 LLM/handwritten bug，没有独立 held-out 规格评测或 adversarial automata benchmark。
- **后续工作 1**：从 man page、测试和 execution trace 半自动合成 command type，并在独立版本/发行版上以 mutation test 检查 soundness。
- **后续工作 2**：为未知 command 提供可配置的 fail-open/fail-closed policy，在危险 sink 前要求所有上游 type 都有可信来源。
- **后续工作 3**：按 warning 而非 program 报告 precision/recall，并做用户实验测 witness 是否缩短定位与修复时间。
- **后续工作 4**：为 DFA/FST 设置 state/time budget和可解释 fallback，在生成式复杂 regex 上测最坏分析成本。

## 相关

- **相关概念**：[[Shell]]、[[Static-Analysis]]、[[Type-Systems]]、[[Finite-State-Transducer]]、[[Program-Reliability]]
- **同类系统**：ShellCheck、LadderTypes、CoLiS、Smoosh
- **同会议**：[[OSDI-2026]]
- **源文档**：[[osdi26-li-zekai]]、[[osdi26-li-zekai.pdf]]
