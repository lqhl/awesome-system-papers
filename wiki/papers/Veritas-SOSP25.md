---
type: paper
name: Veritas
full_title: "eBPF Misbehavior Detection: Fuzzing with a Specification-Based Oracle"
authors: [Tao Lyu, Kumar Kartikeya Dwivedi, Thomas Bourgeat, Mathias Payer, Meng Xu, Sanidhya Kashyap]
venue: SOSP
year: 2025
tags: [ebpf, fuzzing, verifier, security, formal-spec]
source_pdf: "[[3731569.3764797.pdf]]"
source_md: "[[3731569.3764797]]"
---

# eBPF Misbehavior Detection: Fuzzing with a Specification-Based Oracle (SOSP 2025)

> **一句话总结**：现有 [[eBPF]] verifier fuzz 只能靠 KASAN/运行时模式间接发现 RC3/4 类 bug，无法覆盖抽象解释过保守（RC1）与不一致规则（RC2）；Veritas 用 SpecCheck 将指令语义与安全性质编码为 SMT 可满足性 oracle，与 verifier 结果交叉比对，发现 **13** 个 Linux verifier bug（含提权与 KASLR 绕过）。

## 问题与动机

Meta 每台服务器运行 50+ [[eBPF]] 程序；[[eBPF-Verifier]] bug 可**误拒安全程序**（可用性）或**误接受不安全程序**（提权、信息泄漏）。根因四类：RC1 抽象过保守、RC2 规则不一致、RC3 实现错误、RC4 优化启发式错误。既有 formal 工作多验证单组件（如 range analysis）；fuzz 工作 oracle 窄，且未执行的路径无法发现 RC1/2。需要**holistic、可追踪根因**的 testing oracle，而非替换生产 verifier。

## 关键观察 / 隐含假设

- **观察 1**：若 SpecCheck 与 Linux verifier 对同一程序安全判定不一致，则至少一方有 bug——可把「安全程序集合」形式化后与启发式 verifier  diff。
  - **依赖假设**：SpecCheck 规范与 eBPF VM 真实语义一致；SMT 精度足够避免大量 false alarm。
  - **可能失效场景**：规范滞后于新 helper/指令时可能误报 verifier「正确拒绝」。
- **观察 2**：RC1 类 bug（如 4-byte aligned stack 不传播 range）不产生内存错误，KASAN oracle 永远看不见。
  - **依赖假设**：开发者痛点（sched-ext 数小时 debug）证明 RC1 严重性。
  - **可能失效场景**：仅影响小众 program type 的 bug 优先级可能被低估。
- **假设 1**：axiomatic pre/post-condition 规范可扩展新指令。
  - **证据强度**：中；论文展示扩展流程，但完整 ISA 覆盖度需社区长期维护。

## 核心方法

**SpecCheck**：系统规定 eBPF 指令语义（尤其动态 type system）与五项安全性质，编码为 axiomatic 规范；用 SMT 判定程序是否满足约束，输出可追踪的失败条件。

**Veritas**：coverage-guided fuzzer + SpecCheck oracle；生成程序 → 双路验证 → 不一致则报 bug。公开 https://github.com/rs3lab/veritas 。

发现案例：Figure 1 range 不传播、Figure 2 atomic/bitwise 不一致、Figure 3 缺 type check 导致无限循环、Figure 4 path pruning 导致指针泄漏等。

## 设计取舍

- **取舍 1**：SpecCheck 精确但慢——明确不作为生产 verifier，仅 testing oracle。
- **取舍 2**：全谱规范工程量大——与 Agni 等单组件证明互补而非替代。
- **边界条件**：15 个新 bug 中 12 acknowledged、8 fixed（论文 Introduction 数字）；与 abstract 13/15 需以最新 repo 为准。

## 实验与结果

- 共发现 **15** 个新 bug（摘要 13 在 SpecCheck 语境）
- 含严重安全：root 提权、绕过 [[KASLR]] 信息泄漏
- 含可用性：sched-ext 等开发者数小时 debug 的误拒
- **12** acknowledged，**8** fixed（截至论文）

## Critical Analysis

### 论证链条

「四类根因」分类清晰 → SpecCheck 直接编码安全约束 → 与 verifier diff 找 bug，逻辑闭合。从 fuzz 发现 bug 到「生产 verifier 长期正确性」的跳步大：覆盖度受 fuzz 种子与路径枚举限制，未证明 SpecCheck 与 Linux 语义完全等价（Goal 1 precision 依赖 SMT 与规范质量）。

### 假设压力测试

- **规范错误**：若 SpecCheck 过严，会把 verifier 正确行为标为 bug——论文强调 precision goal，但社区审查成本未量化。
- **性能**：SMT per program 使 fuzz 吞吐低于 KASAN-only；大规模 CI 集成成本论文未讨论。
- **修复回归**：8 fixed 后是否加入 Veritas regression suite 未详述。

### 实验可信度

真实 CVE 级案例（Figure 3–4）证据强；与 [[BCF]] 互补（BCF 提精度，Veritas 找 bug）。缺与内核主线 fuzz（如 bpf selftests 扩展）的覆盖率数字对比。

### 系统性缺陷

不解决 verifier 误拒（需 BCF/PREVAIL 类）；规范维护随 ISA 演进是长期负担；对 RC4 optimization 的完整形式化仍困难。论文未讨论 SpecCheck false negative（双方都错）场景。

## 局限与 Future Work

- **局限 1**：SpecCheck 慢，不适合在线验证。
- **局限 2**：规范完整性无机械证明与内核实现双向等价。
- **Future work 1**：SpecCheck 规范开源后由社区 diff 覆盖全 helper 表，测量与 verifier 不一致率随版本变化。
- **Future work 2**：与 [[BCF]] 结合：Veritas 找 counterexample，BCF refinement 尝试接受安全侧。

## 相关

- **相关概念**：[[eBPF]]、[[eBPF-Verifier]]、[[Fuzzing]]、[[SMT]]、[[KASLR]]
- **同类系统**：[[BCF]]、Agni、KASAN-based bpf fuzz
- **同会议**：[[SOSP-2025]]
- **对比**：[[BCF-vs-Veritas]]