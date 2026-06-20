---
type: paper
name: pKVM-GhostShell
full_title: "Ghost in the Android Shell: Pragmatic Test-oracle Specification of a Production Hypervisor"
authors: [Kayvan Memarian, Ben Simner, David Kaloper-Meršinjak, Thibaut Pérami, Peter Sewell]
venue: SOSP
year: 2025
tags: [hypervisor, formal-methods, pkvm, test-oracle, android, verification]
source_pdf: "[[3731569.3764817.pdf]]"
source_md: "[[3731569.3764817]]"
---

# Ghost in the Android Shell: Pragmatic Test-oracle Specification of a Production Hypervisor (SOSP 2025)

> **一句话总结**：在 production [[pKVM]] 上用 ambient C 编写可执行 ghost state + 纯函数式 test oracle，在运行时对照实现状态，以远低于 full verification 的成本发现多个 critical bug；核心观察是 hypervisor 规格必须跟 ownership/并发/松散语义对齐，而非只做 API 返回值检查。

## 问题与动机

[[pKVM]] 是 Google 为 Android 部署的 hypervisor，在 EL2 管理 stage-2 页表以隔离 host kernel 与 protected VM。它用 conventional C/Arm assembly 开发，高并发、与架构交织、bare-metal 运行，使 full functional verification 门槛极高，而 conventional testing 又难以覆盖 subtle isolation bug。

作者探索 **lightweight formal methods** 甜点：把期望行为写成 **test oracle**（可追溯到 1970s），运行时检查实现与规格一致性——类似 sanitizer，但检查功能正确性而非 UB。目标不是定理级 assurance，而是让 conventional kernel 开发者也能维护的可执行规格。

## 关键观察 / 隐含假设

- **观察 1**：pKVM 正确性不仅是 hypercall 返回值，还必须约束隐式 hardware page-table walk 的结果；规格需抽象 page table 为数学 map，并跟 Arm-A 地址翻译语义对齐。
  - **依赖假设**：Arm-A 架构规格足够清晰；abstraction function 能可靠地从 concrete page table 重建逻辑 map。
  - **可能失效场景**：设备/IOMMU/GIC 管理（论文明确未覆盖）上的隐式 walk 不受当前 oracle 约束。
- **观察 2**：规格只能在 implementation **拥有** 某部分 state 的时刻计算 abstraction；必须 mirror pKVM 的 per-lock ownership（host/guest/pKVM page table 分锁），否则并发下 ghost state 无意义。
  - **依赖假设**：绝大多数 hypercall 的锁纪律可被规格结构捕获；少数 multi-phase hypercall 仍除外。
  - **可能失效场景**：stage-2 translation 与 pKVM 页表更新之间的隐式 race 目前未处理，需要更 transactional instrumentation。
- **观察 3**：production hypervisor 规格必然 **loose**——on-demand host mapping 与 OOM 报告条件不能 over-fit 实现细节。
  - **依赖假设**：开发者能接受 relational/参数化 next-state 规格；测试环境可容忍规格运行开销。
  - **可能失效场景**：规格过松可能漏检；过紧则 maintenance 成本逼近 verification。
- **假设 1**：用 C 写规格虽笨拙，但 top-level 可读性足以让开发者独立 review（优于 exotic 规格语言）。
  - **证据强度**：中。有开发者讨论佐证，但规模与长期维护数据有限。

## 核心方法

1. **Reified ghost state**：C 数据结构表示抽象状态（partition of physical pages、guest metadata、per-CPU context），用 executable abstraction functions 从 concrete state 计算并记录。
2. **Pure specification functions**：每个 exception/hypercall handler 的期望 post-ghost-state 仅依赖 pre-ghost-state 与异常信息（morally pure），运行时 equality check。
3. **Ownership-aligned partial ghost state**：与实现锁结构对应的 option-typed 组件；只在持锁时记录对应抽象。
4. **Test infrastructure**：hyp-proxy 让用户态测试分配 kernel memory 并 invoke hypercall；手写测试 + abstract-model-guided random tester 避免过度随机导致整机 crash。
5. **C 作为规格语言**：绕过缺乏 inductive types/polymorphism 等限制，用 structs/unions/enum 手工编码；细节藏在下层。

开源分支：`pkvm-verif-6.4`。

## 设计取舍

- **Runtime test oracle vs proof**：可渐进获益、可维护，但不提供 end-to-end 数学保证；ghost state 执行仍依赖部分 pKVM 正确性（用独立 allocator 缓解）。
- **Ambient C vs 专用规格语言**：降低 adoption 门槛，但规格冗长且易出错。
- **Functional next-state vs relational spec**：更可读；pKVM 所需 looseness 仍可容纳。
- **覆盖范围**：functional correctness only；不含 side-channel、liveness、设备模拟。

## 实验与结果

- 在 pKVM 开发与测试中发现的 **多个 critical bug**（论文 §6 讨论具体案例）。
- 规格与基础设施开源；运行时成本 viable for testing，非 production 部署。
- 覆盖 host/guest hypercall 与 stage-2 fault 等核心路径；未覆盖 virtio 设备委托给 EL1 host 的部分。

## Critical Analysis

### 论证链条

「轻量可执行规格 + ownership + loose spec 可克服 production hypervisor 测试难点」由 existence proof（pKVM 实装 + found bugs）支撑，链条在 **已覆盖子系统** 内较闭合。从「找到 bug」到「显著提升 Android 隔离 assurance」仍有 gap——未量化 bug 严重性分布与逃逸率。

### 假设压力测试

- Ghost state 若被 pKVM bug 破坏可能 mask 不一致——论文认为 unlikely，但无形式化论证。
- 未建模的并发（multi-phase hypercall、隐式 translation race）是已知 fragility。
- Random testing 仍依赖 abstract model；对 novel attack surface 的覆盖未系统度量。

### 实验可信度

- 目标是 assurance 工程而非性能；缺少与 full verification（如 seL4/SeKVM）的 cost/benefit 量化对比。
- Bug 发现案例有说服力，但无大规模 regression 统计或长期 release 跟踪。

### 系统性缺陷

- 论文未讨论规格与主线 pKVM 版本漂移的 CI 成本。
- EL2 bare-metal 使 conventional coverage 工具受限；自定义 coverage 的代表性未详述。
- Side-channel 与物理攻击明确 out of scope。

## 局限与 Future Work

- **局限**：不含设备/IOMMU/GIC；不处理 side-channel/liveness；少数并发模式未覆盖。
- **Future work**：transactional instrumentation 处理 translation race；扩展设备路径；评估规格维护 person-year 成本随内核版本的变化。

## 相关

- **相关概念**：[[Hypervisor]]、[[TEE]]、[[seL4]]、Formal Verification、Test Oracle
- **同类系统**：SeKVM、CertiKOS、Bornholt S3 key-value oracle
- **同会议**：[[SOSP-2025]]