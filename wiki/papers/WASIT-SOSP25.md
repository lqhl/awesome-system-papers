---
type: paper
name: WASIT
full_title: "WASIT: Deep and Continuous Differential Testing of WebAssembly System Interface Implementations"
authors: [Yage Hu, Wen Zhang, Botang Xiao, Qingchen Kong, Boyang Yi, Suxin Ji, Songlan Wang, Wenwen Wang]
venue: SOSP
year: 2025
tags: [wasi, wasm, differential-testing, specification-driven, fuzzing]
source_pdf: "[[3731569.3764819.pdf]]"
source_md: "[[3731569.3764819]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# WASIT：WebAssembly 系统接口实现的深度和连续差异测试（SOSP 2025）

> **原题**：WASIT: Deep and Continuous Differential Testing of WebAssembly System Interface Implementations

> **一句话总结**：[[WASI]] 规格模糊且快速演进，浅层 API 测试无法探索依赖调用链形成的深状态；WASIT 用实时 resource abstraction + 规格增强 DSL + 解耦架构做 differential testing，四个月间歇测试在 6 个 runtime 发现 48 个 WASI-specific bug（37 修复、3 CVE）。

## 问题与动机

[[WebAssembly]] 走出浏览器依赖 [[WASI]] 系统接口，但正确实现困难：函数语义依赖系统状态、与 host syscall 不完全等价、规格注释式描述模糊，且 6 个月三版发布 + 32 个 active proposals 使维护成本高。现有 [[wasm-smith]]、DrWASI 等多停留在浅层、孤立调用，无法触发 fd_open → fd_read → path_open 等依赖链的深语义 bug；[[syzkaller]] 类框架也缺乏「已知 bug 过滤」以支持持续测试。

## 关键观察 / 隐含假设

- **观察 1**：WASI 正确性取决于跨调用的 resource lifetime 与状态机，coverage-guided fuzz 无语义指导只能浅层探索。
  - **依赖假设**：从规格可抽取足够 resource/type 语义，无需白盒分析各语言 runtime 实现。
  - **可能失效场景**：实现特有扩展或 host OS 差异导致 differential 结果大量 false positive。
- **观察 2**：differential testing 在 maturity 不齐的 runtime 间会产生海量误报；必须能 programmatically 过滤无意义参数与已知 bug。
  - **依赖假设**：underspecification 导致的合法分歧可被 DSL 标注区分于真 bug。
  - **可能失效场景**：规格故意留白区域可能使真/假 bug 难以自动分界，仍需人工 triage。
- **观察 3**：WASI 快速演进要求 testing control logic 与 case generation 解耦，否则每次版本变更需重写 generator。
  - **依赖假设**：witx 兼容的 annotation DSL 可渐进添加，不必一次完备。
  - **可能失效场景**：breaking API 变更仍可能迫使大量 annotation 重写。

## 核心方法

WASIT 三组件：

1. **Real-time resource abstraction & tracking**：@resource 把 handle 提升为带 offset/flags/path 等字段的 resource；@input/@output 用类一阶逻辑约束合法调用与状态转移；配合 SMT 过滤无意义参数。
2. **Specification augmentation DSL**：兼容 witx，分 resource types、input requirements、output effects 三类注解，可渐进完善。
3. **Decoupled architecture**：控制逻辑（策略、差分比较）与 WASI 调用实例化分离，便于 co-evolve with WASI。

每轮迭代：按 abstract state 生成调用 → 各 runtime 实例化执行 → 比较结果 → 更新 resource state。

## 设计取舍

- **Differential vs single-runtime oracles**：能找跨实现不一致，但受 maturity/underspec 噪声影响，依赖 DSL 过滤。
- **Dynamic abstraction vs static analysis**：覆盖 heterogeneous C/Rust/Go/Java 实现，但 abstraction 正确性依赖人工 annotation 质量。
- **Continuous testing with bug filtering**：节省 triage，但可能隐藏尚未记录的 known issue 变体。

## 实验与结果

**指标、基线与边界**：branch-coverage test throughput、bugs/triage outcome、dependent-call sequence length；WASIT vs Wasix/DrWASI/WASIT-syzkaller；6 runtimes、4-month campaign 或 100-min/2h test workload configurations（§5）。

- 四个月间歇 campaign、6 runtimes：**48** WASI-specific bugs，**41** confirmed、**37** fixed（多为作者 patches）、**3** CVEs；这是该时期的发现数，不是生态缺陷率（§1，§5）。
- branch coverage：Node **1216 vs 748/1204**（相对 Wasix 高 **62.6%**），WAMR **403 vs363/272/385**，WasmEdge **490 vs456/322/438**，Wasmtime **156 vs114/81/153**（§5.2，Table3）。
- 2h runs 中其他方法少于 **50** calls；WASIT 超半数 runs 超过 **100**，部分到 tens of thousands，表示 dependent resource call chains（§5.3，Fig.11）。
- WASI v0.1 spec **1301** S-expression lines、约 **170** DSL annotation lines；input-requirement annotations 约 **10 person-hours**（§4、§5.3）。

## 论断—证据表

| 论断 | 证据 | 指标 / 基线 / 评测边界 | 定位 | 置信度 |
|---|---|---|---|---|
| bug yield 是 campaign outcome | 48/41/37/3 CVE | 4 months、6 runtimes；非 bug-rate | Abstract，§1 | high |
| resource tracking 增加 implementation branch coverage | Table3 counts | 100-min tests；WASmer/Wazero excluded，DrWASI not Node | §5.2，Table3 | high |
| 深调用链指标是到 inconsistency 的 sequence length | >100/tens thousands | 2h configuration；非 throughput | §5.3，Fig.11 | high |
| annotation 成本有具体范围 | 1301/170 lines、10h | preview1 implementation；不含 triage/reporting | §4、§5.3 | high |
| 演化速率是解耦动机 | 32 active proposals、3 releases/6mo | paper observation time；非长期预测 | §1 | high |

## 批判性分析

### 论证链条

「WASI 难测 → 需深状态 + 差分 + 持续过滤」由 48 bug 与 CVE 案例支撑，链条在 **已注解 API 子集** 上闭合。未量化 annotation 覆盖占 WASI 表面积比例，也未证明对所有 deep semantic bug class 完备。

### 假设压力测试

- 若多数 runtime 收敛到同一错误语义，differential 可能漏检——需 oracle 或 spec 形式化补强。
- SMT 约束求解开销与 WASI 调用频率的 scale 未详述。
- 仅测试 six runtimes；嵌入式/定制 WASI subset 外推有限。

### 实验可信度

- 真实 upstream bug、CVE、fix 数据强；缺少与 syzkaller+adapter 的 head-to-head 覆盖对比。
- 「四个月间歇」非 24/7 continuous；bug 发现率时间分布未给出。

### 系统性缺陷

- Annotation 维护成本随 WASI proposals 增长——论文声称低，但长期数据缺失。
- 论文未讨论 security exploitability 分级与 SLA 级 regression testing 集成。

## 局限与后续工作

- **局限**：依赖人工/半自动 annotation；differential 对 spec 留白敏感；未覆盖全部 WASI proposals。
- **Future work**：从 spec 自动生成更多 annotation；单-runtime semantic oracles；与 CI 深度集成的 cost 模型。

## 相关

- **相关概念**：[[WebAssembly]]、[[WASI]]、Differential Testing、[[syzkaller]]
- **同类系统**：DrWASI、Wasix、wasm-smith、WADIFF
- **同会议**：[[SOSP-2025]]
