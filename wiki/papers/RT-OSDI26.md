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
last_reviewed: 2026-07-30
---

# 流式 Shell 的正则类型系统

> **原题**：RT: Regular Types for the Streaming Shell

## 一句话总结

RT 用 regular language 描述 shell command 的逐行输入/输出，以 language inclusion 检查 pipeline composition，并以 polymorphic type、finite-state transducer、environment concretization 和 annotation 提升精度；954 个程序上平均 0.02 s，整体分类准确率 91%。

## 问题与动机

Unix shell 把不同语言实现的 command 通过无类型 byte stream 拼接，路径空格、field format、numeric sort、过滤为空和危险 `xargs rm` 等错误往往只有运行后才暴露。ShellCheck 擅长语法模式，却难以推理“上一 stage 可能产生什么行、下一 stage 能安全接收什么行”。RT 聚焦 line-oriented streaming core，在执行前检查 stream shape，而不试图建立完整 shell effect system。

## 关键观察 / 隐含假设

### 关键观察

- 大量 Unix command 虽不完全是 regular transformation，但其 line shape 可由 regular language 精确表达或有用地过近似。
- composition safety 可归结为上游 output language 是否是下游 safe-input language 的子集；失败时 automata difference 能生成具体 witness。
- `cat`、`sort` 等 output 与实际 input 相关，需要 bounded polymorphism，而不是为每个 invocation 穷举类型。
- `tr`、`cut`、`sed` 的关键变换超出普通 regex 组合，但仍可由 FST 将 regular language 映射为 regular language。

### 隐含假设

- 被检查程序的正确性主要取决于逐行 stream shape；跨行排序、计数、全局状态和 filesystem effect 可抽象掉。
- 手工 command type database 足够正确且覆盖常用 invocation；未知 command 退化为 `.* → .*` 会漏报而非误拒。
- POSIX ERE 级 regularity 足够，不支持 backreference/lookaround 是可接受取舍。
- environment concretization 读取的 file/env 在实际执行前不会发生相关变化。

## 核心方法

regular stream type 是每一行所有可能字符串的 language；regular command type 是输入、输出 type 对。RT 在 POSIX ERE 上增加 intersection `&` 与 negation `!`，但排除让 inclusion 不可判定的 backreference。类型必须 sound：input type 不超出 command safe domain，output type 覆盖所有可能输出；precision 则决定 false positive。

系统维护类似 typed standard library 的 command database：配置解析 flag 并依 invocation 构造类型，例如 `grep` 的 output 是输入与 pattern 的 intersection。当前覆盖 71/106 个 GNU coreutils，并覆盖 GitHub 集合 86% 的 command invocation。未知 command 使用保守顶类型。

### 多态与检查

多态类型 `∀α. α → α` 精确表示 `cat`；bounded form 可表示 `sort -n` 要求 input line 以 number 开头但保持原 language。检查 pipeline 时沿拓扑顺序传播 type，对每 stage 做 regular-language inclusion，再实例化 output。若 inclusion 失败，从 `L_upstream \ L_expected` 的 automaton 取一个字符串作为 counterexample，例如 `./ book0.txt` 证明 `find|grep|xargs cat` 会按空格错误拆路径。

## 复杂变换

RT 增加 `reverse`、`translate-match`、`line-extract`、`translate-chars`、`field-select` 等 type-level operator，分别覆盖常见 `sed`、`grep -o`、`tr`、`cut`/`awk` 行为。系统为 operator 构造 deterministic、functional nondeterministic 或 general nondeterministic FST，与 input DFA 做 product，再把 output projection 成 NFA。

`field-select` 与 `translate-chars` 可精确计算；一般 `translate-match` 可能只能 sound over-approximate，例如非正则的 string duplication 不可能得到精确 regular image。精度损失会产生 false positive，但 soundness 避免漏掉真实危险输出。

## 可选精化

- concretization 在第二遍读取本地 input file/env，把实际内容作为有限 regular type；第一遍仍先报告环境无关问题。
- `assume`/`input` annotation 提供假设，`assert`/`expect`/`output` 检查用户声明；常见 IP、number、URL 有 syntax sugar。
- semantic heuristic 报告空 output、向无输入 command 传值、必然 no-op 的 filter/transform，以及用 lexicographic `sort` 排 numeric input。

## 实验与结果

**证据定位**：§6.1–§6.3、图 8；954 个程序与 ShellCheck、LADDERTYPES 进行 effectiveness、ablation 和 runtime 对比。

benchmark 含 StackOverflow、GitHub、既有论文与人工/真实 bug，共 954 个程序。

- RT 整体准确率 91%（864/954）：buggy program 72%，correct program 96%；加 annotation 后分别为 94% 和 98%。
- RT 找到 state-of-the-art 忽略的 87 个 bug；buggy program 准确率比 LADDERTYPES 和 ShellCheck 高 52 个百分点。
- definite warning 准确率 100%，possible-bug warning 为 86%，说明 confidence 能区分 sound mismatch 与 approximation/heuristic。
- full configuration 有 27 false positive、63 false negative；带 annotation 的相应集合总准确率约 97%，false positive/negative 各 14。
- FST 将 false-positive rate 从 20% 降至 4%；各扩展最多降低 83% false negative。
- 全部 954 程序约 20 s，平均 0.02 s，单个均少于 1 s。

## 论断—证据表

| 论断 | 证据 | 边界 | 置信度 |
|---|---|---|---|
| regular type 能发现真实 shell composition bug | 954 程序上 91% accuracy，额外发现 87 个 baseline 漏掉的 bug | buggy recall 仍只有 72% | 强 |
| automata 分析足够快 | 954 个程序 20 s，平均 0.02 s | 评估脚本规模有限，复杂 regex/FST 可能 state explosion | 强 |
| FST 扩展 materially 提升精度 | ablation：false positive 从 20% 降至 4% | 一般 transduction 仍需 over-approximation | 强 |
| annotation 可显著补齐上下文 | buggy/correct accuracy 提升至 94%/98% | 把部分证明义务转给开发者，错误 annotation 可能误导 | 强 |
| warning confidence 有可解释性 | definite warning 100% accurate，possible warning 86% | benchmark label 与 type database 质量决定该结果 | 强 |
## 批判性分析

### 论证链条

RT 选取了很好的抽象边界：不解释 shell 的全部动态语义，而把 stream composition 化为成熟 automata 问题。错误 witness 比“类型不匹配”更符合 shell 用户习惯。多态 regular type 与 FST operator 使设计不止是为 command 写粗糙 regex，ablation 也证明这些机制确有价值。

### 假设压力测试

- 71/106 coreutils 的手工 database 是可信计算基；错误或过宽声明会漏报，维护所有 flag 与平台差异成本高。
- line-level language 无法表达跨行 invariant、排序、唯一性、行数关系、CSV quoting/JSON nesting 的完整语义。
- buggy accuracy 72% 表明 28% 已知错误仍漏掉；91% overall 容易被 correct program 比例掩盖。
- concretization 存在 TOCTOU，且读取敏感/巨大输入也带来安全和成本问题。
- FST/DFA 的 worst-case state explosion 在小脚本平均时间中不明显，敌意或生成式 regex 需资源上限。
- heuristic warning 并非 sound typing judgment，用户必须理解 confidence 层级，否则会产生 warning fatigue。

### 实验可信度

954 个多来源程序、baseline 和 feature ablation 支撑 effectiveness；但 corpus 规模与脚本复杂度有限，且 command type database 的人工标注质量同时影响 ground truth 与结果。

## 局限与后续工作

- **局限**：逐行 regular language 无法表达跨行、全局排序和完整 structured-data invariant。
- **后续工作**：应扩大独立标注 corpus、自动验证 command type，并对 automata state explosion 设置资源预算。

后续可从 man page、test 或 trace 半自动合成并验证 command type；引入 bounded relational refinement 表达 delimiter/field count 和有限跨行属性；为 automata 设 complexity budget 与 graceful approximation；把 RT 嵌入 editor/CI；并以更大、独立标注的生产 corpus 分开报告 precision、recall 与危险 side-effect bug 的覆盖率。

## 相关概念

- [[Shell]]
- [[Static-Analysis]]
- [[Type-Systems]]
- [[Finite-State-Transducer]]
- [[Program-Reliability]]
