---
type: paper
name: Rex
full_title: "Rex: Closing the language-verifier gap with safe and usable kernel extensions"
authors: [Jinghao Jia, Ruowen Qin, Milo Craun, Egor Lukiyanov, Ayush Bansal, et al.]
venue: ATC
year: 2025
tags: [ebpf, kernel-extensions, rust, language-based-safety, verifier]
source_pdf: "[[atc2025-jia.pdf]]"
source_md: "[[atc2025-jia]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# Rex: Closing the language-verifier gap with safe and usable kernel extensions (ATC 2025)

> **一句话总结**：Rex 的关键观察是 eBPF 的 in-kernel verifier 与 high-level 语言契约不一致，迫使大型 extension 做大量 workaround；它用 safe Rust + 轻量 extralingual runtime 替代 verifier，在 BMC 重写中 326 行 Rust 替代 513 行 C/7 个 tail-call program，8 核吞吐 1.98M RPS 略高于 eBPF-BMC 的 1.92M。

## 问题与动机

[[eBPF]] 已从 packet filter 演化为定制存储、网络、调度的通用 [[Kernel-Extensions]] 机制，核心卖点是 in-kernel verifier 通过 bytecode 符号执行保证 memory/type/resource/termination/stack safety。但随着程序变大变复杂，开发者越来越多地遭遇 **language-verifier gap**：开发者在 C/Rust 层遵守语言契约，编译器也按契约生成代码，但 verifier 在 bytecode 层有另一套期望；安全程序被误拒时，反馈是 bytecode 级 verifier log，难以映射回源码。

作者分析 Cilium、Aya、Katran 等项目的 72 个 commit（外加 BMC、Electrode 案例），确认原始程序均安全但被 verifier 拒绝，workaround 模式包括：拆成多个小 program（27）、hint LLVM 生成 verifier-friendly bytecode（22）、改代码辅助验证（15）、应对 verifier bug（9）、重写标准库函数（1）。典型代价是 BMC 本只需 2 个 ingress/egress program，却被迫拆成 7 个 tail-call program，还要限制 packet 长度以控制 jump 指令数；Cilium 甚至要写 inline assembly 阻止 LLVM 的 32-bit move 优化。

论文 claim 的边界清晰：不是否定 eBPF 对小而简单 extension（如 packet filter）的价值，而是针对**大型、复杂、长期维护**的 extension，verifier 的 scalability 限制、编译器-验证器不同步、实现缺陷会持续制造 usability 负担。改进 verifier 本身（fuzzing、formal verification、BCF 等）难以从根本上闭合 gap，因为符号执行 scalability 和 LLVM/verifier 独立演进这两个结构性问题仍在。

## 关键观察 / 隐含假设

- **观察 1：language-verifier gap 是结构性问题，不是 verifier bug 修完就消失。** 72 个 commit 中误拒均源于 verifier 过度保守、scalability 上限或实现缺陷，而非程序真不安全；BMC 拆 program、Cilium 写 inline asm、Aya 重写 `memset`/`memcpy` 都是为「取悦 verifier」而非业务逻辑。
  - **依赖假设**：开发者主要在 high-level 语言写 eBPF，并期望语言+编译器契约足以表达安全意图。
  - **可能失效场景**：若 extension 极小（几十条指令）、逻辑线性、无循环/复杂指针追踪，verifier 限制几乎碰不到，gap 感知很弱。

- **观察 2：eBPF 期望的安全属性大多可由 safe Rust 的 language-based safety 覆盖，剩余属性可用轻量 runtime 补齐。** Rex 对齐 eBPF 的五类 safety（memory、type、resource、runtime/termination、stack），用 Rust 类型系统处理静态可判定部分，panic 处理、stack check、watchdog termination 交给 runtime。
  - **依赖假设**：Rust `no_std` 子集 + 受限 feature 集足以表达目标 extension；eBPF helper interface（~200 routines）作为 kernel 边界足够。
  - **可能失效场景**：需要 `std`、动态分配、浮点/SIMD、或 helper 未覆盖的 kernel 交互时，Rex 表达能力受限；每目标 kernel 需重建以匹配 ABI。

- **观察 3：复用 eBPF hook point 和 helper interface 可以在不改动 kernel 生态的前提下替换验证层。** Rex 支持 tracepoint、kprobe、perf-event、XDP、TC 五类 program，共享 hook，但不走 bytecode verifier/JIT 路径，而是加载 ELF 可执行段。
  - **依赖假设**：eBPF helper 的高层次封装已足够隔离 extension 与 kernel 内部状态（RCU 等）；extension 无嵌套执行。
  - **可能失效场景**：依赖 eBPF 特有 helper（如 `bpf_loop`、`bpf_strtol`）或 tail-call 组合语义的程序需重写；kprobe helper 等嵌套场景 Rex 明确不支持。

- **假设 1：non-adversarial safety model——extension 由 root 从可信上下文加载，防的是编程错误而非恶意攻击。**
  - **证据强度**：强。论文明确跟随现代 eBPF/KFlex 实践，不追求 unprivileged 用例；Spectre 等 transient execution 攻击和 verifier CVE 被引用为理由。

- **假设 2：把 Rust toolchain 纳入 TCB 是可接受 tradeoff。**
  - **证据强度**：中。作者援引 [[Rust-for-Linux]]、RedLeaf、Theseus 等先例，并指出 rustc 虽大于 eBPF verifier，但有活跃 fuzzing/formal verification 生态；但这是价值判断，不是形式化证明。

## 核心方法

Rex 的核心思路是**去掉独立静态验证层**，让 safety 完全落在语言契约 + 受信 kernel crate + extralingual runtime 上，从而闭合 language-verifier gap。

**Safe Rust 子集**：extension 禁止 `unsafe`、`core::mem::forget`/`ManuallyDrop`、`std`、动态分配、浮点/SIMD、`abort` intrinsic；通过 compiler flags 和 Clippy lints 强制。这与 Rust kernel module 不同——后者允许 `unsafe`，语言 safety 可被绕过。

**kernel crate（3.5K LoC Rust，其中 360 LoC unsafe）**：在 eBPF helper 之上提供 safe wrapper 和 binding。关键机制包括：
- **Memory safety**：对 pointer+size helper 用 generic monomorphization/const generics 在编译期绑定类型与 size；kernel 指针返回 safe reference，动态大小区域封装为 Rust slice（带 runtime bounds check，开销在 microbenchmark 中可忽略）。
- **Extended type safety**：引入 `rex::NoRef` auto trait，限制 `transmute` 目标类型不得含指针/引用；配合显式 bound check 防止 misinterpret cast。
- **Resource safety**：对每个 kernel 资源（spinlock、refcount 等）提供 RAII wrapper，利用 `Drop` 自动释放；正常路径靠编译器插入 drop，异常路径靠 panic handler 遍历 per-CPU resource buffer。

**Extralingual runtime（kernel 侧 2.2K LoC C）**处理静态分析难覆盖的属性：
- **Exception handling**：不用 Itanium EH ABI；panic 时 panic handler 释放已记录资源，landingpad 恢复 dispatcher 保存的 stack pointer，实现 graceful exit。采用 crash-stop 模型——panic 的 extension 及其共享 map 的 extension 递归卸载。
- **Stack safety**：无间接/递归调用时 compile-time LTO 全局 callgraph 静态求和；否则每函数调用前插入 `rex_check_stack` runtime check。每 CPU 分配 8-page 专用 stack（extension 可用 4 page，留 4 page 给 helper/panic）。
- **Termination**：用 per-CPU hrtimer watchdog 按 RCU stall timeout 限制执行时间，超时则 hijack 指令指针到 panic handler；在 helper/panic 执行期间 defer termination。与 eBPF 拒绝 back edge 不同，允许任意循环但可能被 runtime 打断。

**加载与编译**：kernel 解析 extension ELF LOAD segment 并 fixup helper/map 引用；LLVM pass 负责 stack instrumentation；`rust-bindgen` 按目标 kernel 生成类型 binding。深度实现见 [[atc2025-jia]]。

## 设计取舍

- **语言绑定 vs 通用性**：强制 safe Rust 闭合 gap，但放弃 C 生态和 Aya 式「Rust 前端 + eBPF bytecode」路径；小 filter 仍适合原生 eBPF，大型程序适合 Rex。
- **去掉 verifier vs 更大 TCB**：TCB 从 eBPF verifier 变为 rustc + Rex kernel crate + Rex runtime；换来开发者只面对一种契约（Rust 编译器诊断），不再维护 verifier workaround 知识。
- **Runtime check vs 静态 guarantee**：termination 用时间上限而非静态证明，减少 false positive，但超时语义与 eBPF「编译期拒绝 back edge」不同；deadlock 仍沿用 eBPF 单锁限制。
- **无 JIT vs 性能**：Rex 不做 helper inline/JIT，map lookup 比 eBPF inlined 慢 0.5–4 ns；macro benchmark 上被消除 tail-call/state-passing 收益抵消。
- **Dedicated stack vs 共享 kernel stack**：更强 stack safety（eBPF 的 indirect tail call/nesting 已知可破 stack 保证），但每 CPU 常驻 8-page 映射。
- **Crash-stop panic vs 继续服务**：panic 后卸载 extension 及共享 map 依赖方，保证 kernel 一致性，但可用性低于「尽力恢复」模型。
- **边界条件**：最优雅于大型复杂 extension（BMC 类）、softirq/task context、可接受 root-only 部署；脆弱于 hard/NMI interrupt program、需多锁/嵌套 extension、或强依赖 eBPF 特有 helper/verifier-oriented API 的场景。

## 实验与结果

- **Usability（BMC case study）**：Rex-BMC 326 行 Rust vs eBPF-BMC 513 行 C（7 个 program + tail call + map 传状态）；无需 `BMC_MAX_PACKET_LENGTH` 等 verifier 复杂度 workaround，可直接用 slice/iterator/closure。
- **Macro（Memcached + in-kernel cache，8 核）**：vanilla Memcached 365K RPS；eBPF-BMC 1.92M RPS（5.26×）；Rex-BMC 1.98M RPS（5.43×），略高于 eBPF，归因于消除 tail call/map 状态传递及 rustc 优化。
- **Micro — empty program**：eBPF 42.1±4.1 ns vs Rex 42.6±5.8 ns（dispatcher 开销 ~0.5 ns）。
- **Micro — spinlock acquire/release**：eBPF 130.4±20.3 ns vs Rex 183.1±27.5 ns（资源记录 + per-CPU state flag，~50 ns）。
- **Micro — recursive depth 1–33**：Rex 正常递归比 eBPF tail call 约快 3×（eBPF 受 tail-call 计数与 map 传参开销）。
- **Micro — map lookup**：Rex 比 non-inlined eBPF 慢 2–4 ns（wrapper + 无 JIT inline）；array/hash 差距小于 inlined eBPF 的 0.5–1.2 ns 优势。

## Critical Analysis

### 论证链条

主链条较闭合：language-verifier gap 有 72-commit 实证 → 去掉 verifier、改用 language-based safety 在概念上消除 gap → Rex-BMC 代码显著简化且 macro 性能不低于 eBPF → microbenchmark 解释了个别 runtime 开销但被宏观收益抵消。最有价值的贡献是把「verifier usability」问题形式化为 language-verifier gap，并给出可共存的替代框架，而非继续修补 verifier。

薄弱跳步在于 **generalizability**：唯一大型 case study 是 BMC（网络 cache）；storage（XRP）、调度（SCX）、分布式协议（Electrode/DINT）等论文引用的复杂 eBPF 场景未逐一重写。作者论证这些也会受益，但尚未用同等深度的实现验证。

### 假设压力测试

**workload assumption**：Rex 假设目标 extension 足够大，以至于 verifier 拆分/汇编 workaround 成本显著。对 XDP 小包 filter 或单次 map update，Rex 的 ELF 加载、专用 stack、runtime instrumentation 可能得不偿失。论文自己也把 hard/NMI context 的小 program 留给 eBPF。

**resource bottleneck assumption**：BMC benchmark 瓶颈在 NIC driver 层 bypass 内核网络栈，runtime 纳秒级开销被掩盖。若 extension 是 tight loop 内频繁 helper/spinlock（微基准已显示 +50 ns/lock），高锁竞争 workload 下差距可能放大。论文未测 tail latency 分布。

**hardware/deployment assumption**：实现基于 Linux v6.11、x86-64、AMD EPYC + Mellanox 40GbE；每 kernel 版本需重编译 binding。跨架构（ARM）、跨 kernel 长期维护成本论文仅定性讨论（比追 verifier bug 容易），缺少量化。

**scaling assumption**：72-commit 分析来自 Cilium/Aya/Katran 等活跃项目，可能高估「所有 eBPF 开发者」受 gap 影响的程度；小型内部 extension 未必进入样本。

**correctness/SLO assumption**：panic 走 crash-stop 并递归卸载共享 map 的 extension，对生产是强语义但论文未讨论 rolling upgrade、部分失效对多-tenant hook 的影响，也未给可观测性接口（除 ring buffer debug）。

### 实验可信度

强项是 **同一 workload 上的 apples-to-apples**：Rex-BMC vs eBPF-BMC vs vanilla Memcached，同硬件、同 workload trace、多核扩展曲线；microbenchmark 系统拆解 dispatcher、lock、recursion、map lookup 开销。

Baseline 公平性较好：eBPF-BMC 是已发表、已优化的系统实现，不是 toy program。弱点是 **覆盖面窄**——仅一个复杂 application + 合成 microbench；未与 [[KFlex]]、Aya、Rust kernel module 或「BCF-augmented verifier」路径对比。性能 claim「不牺牲性能」在 BMC 上成立，但不能外推到所有 extension 类型。

Usability claim 部分依赖 **定性代码对比**（Figure 5 cache invalidation），行数统计（326 vs 513）是启发式指标，未做开发者时间、缺陷率等客观 usability study（论文承认 measuring usability is challenging）。

### 系统性缺陷

- **Isolation/recovery**：panic 卸载 extension 及依赖方，但论文未讨论热替换、版本共存、故障注入下的恢复时间；对共享 map 的多 extension 部署，blast radius 大于单 eBPF program 验证失败。
- **Tail latency**：未报告 P99/P999；watchdog termination 在 extension 被其他中断占用时可能延迟，论文称实验中未遇到但未排除。
- **Deadlock**：仍限制单锁，与 eBPF 相同；多锁需求需改 kernel spinlock 逻辑，论文仅提及可能方向。
- **Security**：明确放弃 unprivileged/adversarial；TCB 含 rustc（远大于 verifier）的 supply-chain 风险论文未量化。
- **运维**：需定制 kernel（v6.11 Rex patch）、Rust 工具链、per-kernel rebuild；论文未讨论与发行版 kernel/eBPF CO-RE 的部署摩擦。

## 局限与 Future Work

- **局限 1：仅支持 safe Rust，无动态分配。** `alloc` crate 与 eBPF all-context allocator 集成尚未完成，限制复杂数据结构与部分标准库能力。
- **局限 2：program 类型与上下文受限。** 当前五种 hook；hard/NMI interrupt（如 perf-event 某些模式）明确不目标；无 extension 嵌套。
- **局限 3：runtime 语义与 eBPF 不同。** 时间上限 termination 可能误杀长但合法循环；panic crash-stop 对共享状态 extension 影响面大。
- **局限 4：case study 单一。** 除 BMC 外缺少其他大型 production extension 的端到端迁移证据。
- **Future work 1**：集成 Rust `alloc` 与 eBPF 分配器，测量对 expressiveness 和 fragmentation 的影响。
- **Future work 2**：结合 Verus/Kani 等 Rust 验证技术减少 runtime panic 路径，评估能否在不重引入 language-verifier gap 的前提下缩小 extralingual runtime。
- **Future work 3**：对 storage/scheduling 类复杂 eBPF（XRP、SCX）做 Rex 移植，量化开发与维护成本下降及性能回归边界。

## 相关

- **相关概念**：[[eBPF]]、[[Kernel-Extensions]]、[[Rust-for-Linux]]、[[Language-Based-Safety]]、[[Software-Fault-Isolation]]、[[XDP]]、[[RAII]]
- **同类系统**：[[BCF-SOSP25]]（proof-guided verifier 精化）、Aya-rs（Rust→eBPF bytecode，仍依赖 verifier）、[[KFlex]]（SFI + verifier 协同）、bpftime、RedLeaf、Tock
- **同会议**：[[ATC-2025]]
- **对比**：Rex 消除 verifier vs BCF 增强 verifier vs KFlex 保留 verifier 扩表达力
