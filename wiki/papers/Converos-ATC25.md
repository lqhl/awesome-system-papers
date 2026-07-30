---
type: paper
name: Converos
full_title: "CONVEROS: Practical Model Checking for Verifying Rust OS Kernel Concurrency"
authors: [Ruize Tang, Minghua Wang, Xudong Sun, Lin Huang, Yu Huang, Xiaoxing Ma]
venue: ATC
year: 2025
tags: [formal-methods, model-checking, rust, os-kernel, concurrency, tla-plus]
source_pdf: "[[atc2025-tang.pdf]]"
source_md: "[[atc2025-tang]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# Converos：用于验证 Rust OS 内核并发性的实用模型检查（ATC 2025）

> **原题**：CONVEROS: Practical Model Checking for Verifying Rust OS Kernel Concurrency

> **一句话总结**：针对「Rust OS 内核 unsafe 并发模块测试难以穷尽角落 interleaving、且规约-实现漂移会污染 model checking 结论」这一观察，提出 CONVEROS——PlusCal/[[TLA+]] 多层多粒度规约 + 改进 bottom-up [[Trace-Validation]]（missing event 自动推断）+ TLC model checking；4 人月验证 [[Asterinas]] 12 个并发模块（≈4K LoC），发现 20 个 bug（9 个自动检出、14 个已修复），spec-to-code ratio 0.3–2.3。

## 问题与动机

[[Asterinas]] 是 Ant Group 与学术界共建的 Rust 通用 OS 内核（100K LoC、200 syscall、可跑 JVM/MySQL），目标是生产级 Linux ABI 替代。Rust 的 ownership/borrow 在 safe 代码中消除大量 memory safety 问题，但内核开发必然触及 **unsafe**（如 `MutexGuard` 内部 `deref_mut`），且自定义同步原语的设计错误仍会导致 data race、死锁、活锁、lost wakeup、kernel panic。作者观察到：常规 expert review + CI 测试对这些并发 bug **不可靠**——难复现、难修对（range lock 案例经 3 次错误修复才被 model checker 证伪）。

直接上 [[Model-Checking]] 又有两大工程障碍：

1. **写规约门槛高**：复杂 OS 并发需要形式化方法 expertise；粒度太细状态爆炸，太粗漏 bug。
2. **规约-实现不一致**：modeling error 或代码快速演化导致 false positive/negative，使验证结论不能反映真实代码。

作者 claim：CONVEROS 不是发明新 model checker，而是让 **规约编写 + 一致性检查 + model checking** 三步变得 incremental、可自动化、成本可控，从而把工业界 [[TLA+]] 经验（AWS S3、CCF 等）迁移到 **共享内存 OS 内核并发模块**。

## 关键观察 / 隐含假设

- **观察 1**：OS 并发 bug 的根因往往是 **waitqueue / 锁状态机 / 非原子复合操作** 在特定 interleaving 下违反 safety 或 liveness；这些路径在 2–5 进程、几分钟 TLC 搜索内即可触发（Table 1 全部 bug 满足此条件）。
  - **依赖假设**：被测模块的对外交互可用有限进程数 + 测试 harness 覆盖代表性竞争；真实生产负载的复杂拓扑（IRQ、调度、内存压力）可被抽象或隔离到已验证底层原语。
  - **可能失效场景**：仅在高核数、特定硬件时序或弱内存模型下出现的 bug；跨模块长链依赖（如 logging 在低内存 rescue 中递归分配）需要额外建模才能发现。

- **观察 2**：**bottom-up trace validation** 比 top-down「重放 spec trace 到代码」更适合 OS 内核——内核难以确定性控制线程 interleaving；但经典 trace validation 要求日志顺序精确、每条 spec label 都有对应 log，在共享内存 + 不准确时间戳场景下几乎不可用。
  - **依赖假设**：missing event 引入的额外非确定性可通过 maximum exploration depth 与 convergence point 剪枝控制在可接受范围；剪枝参数略宽松时 false positive 可通过 discrepancy trace 诊断。
  - **可能失效场景**：大量 missing event 叠加使 BFS 不可行；convergence point 设置过松导致合法 trace 被剪掉（论文承认 DFS 模式下禁用 convergence pruning 以避 false positive）。

- **观察 3**：**多层（high/low spec）+ 多粒度（fine/coarse action 组合）** 可将 spec-to-code ratio 压在 0.3–2.3，且遵循 Remix 的 interaction-preserving 原则后，粗化已验证模块不会漏掉跨模块交互 bug。
  - **依赖假设**：模块依赖图可分析清楚；每个对外可见的共享状态变量可被识别并保留，内部变量可安全抽象；开发者愿意接受 **不做形式化 refinement proof**、改由 trace validation 桥接高低层。
  - **证据强度**：**中**——12 模块实证有效，但 PageCursor 因重构跳过 conformance；高低层之间无机器可证的精化关系。

- **假设 1**：PlusCal 的 imperative 风格足以忠实建模 Rust 并发代码（显式建模 `drop`、展开 closure），且程序员比纯 [[TLA+]] 更能维护规约。
  - **证据强度**：**强**——平均 3.6 人天/模块、一人 4 人月完成 12 模块；但 Rust 特有语义（`Arc`、原子操作中间态）仍需手工拆分 atomic label。

## 核心方法

CONVEROS 工作流三步（Figure 6）：

### 1. 形式化规约（§4）

- **高层规约**：抽象公共 API 设计意图（如互斥、无死锁），用于早期 conformance 与快速启动；对复杂锁用法可省略。
- **低层规约**：贴近实现细节，**故意保留潜在 bug**，供 model checking 检出；从高层增量展开。
- **多粒度**：基础原语（SpinLock、RwLock）用 fine-grained label（每个共享变量写操作一个原子步）；上层模块将已验证子模块粗化为 single action，仅保留外部交互变量（如 Mutex 的 `locked` guard、SpinLock 的 `wakers_lock`）。借鉴 [[Remix]]（EuroSys'25，同作者组）的 mixed-grained 与 action composition。
- **正确性性质**：通用 safety（mutual exclusion）与 liveness（deadlock/livelock/starvation freedom）；模块特有 functional safety（如 semaphore count ≥ 0、pipe write atomicity）。

语言选择：**PlusCal → TLA+ → TLC**。相对 CertiKOS 等 deductive verification（通常 5–20× 实现代码量的证明负担），CONVEROS 明确走 **existing code + 有界状态探索** 路线。

### 2. Conformance checking（§5）（2. 一致性检查（§5））

- **Trace 收集**：为每个模块写轻量 test harness（`TlaModel` trait + `run_procs` 绑核并行），在对应 spec label 处插桩 `TlaLogger`。
- **Trace specification**：自动从编译后的 TLA+ 解析 action/event 名生成；`IsEvent` 约束 trace 行与状态转移对齐。
- **Missing event 算法**（核心创新）：在不确定事件顺序或尚未插桩的代码段插入 `TlaLogger::new_missing()`，TLC 探索两条分支——(a) 跳过 missing 匹配下一正常事件；(b) 在 missing 窗口内执行允许的任意 enabled action 且不推进 trace 行号。后处理合并连续 missing event；配 **max depth** + **convergence point** 控制状态爆炸。
- **Current-state 约束**：日志可直接约束变量当前值（如 `cur_pc`），无需手改 trace spec。
- **Discrepancy debugging**：首次 validation 失败后，以最长未匹配行号为 breakpoint 二次运行，用 `ENABLED` 构造 counterexample 状态图（<100 states 时自动可视化）。
- **粒度对齐**：迭代式 logging——先对 public API 用 missing event 做粗对齐，再逐步补内部 label；统计 event coverage，对未覆盖 label 在 spec 中加 assertion 强制 TLC 产出诊断 trace。

### 3. Model checking + Bug confirmation（§5.5）（3. 模型检查+Bug确认（§5.5））

对通过 conformance 的低层 spec 跑 TLC 检查性质违反；用 violation trace 写确定性复现测试（加 delay 重建时序）。复现失败则回到规约调整；复现成功则先修 spec 再修代码，再 rerun trace validation。测试阶段常发现 **by-product bugs**（IRQ 嵌套、FPU 状态、logging 递归等）。

## 设计取舍

- **Trace validation 替代 refinement proof**：放弃 Abadi-Lamport 式精化映射，大幅降低开发者负担，但 conformance 只证明「观测到的 trace 被 spec 接受」，**不证明**实现满足规约的全行为子集；靠多层规约 + coverage 缓解 false negative 风险。
- **Missing event 的灵活性 vs 搜索成本**：允许推断事件顺序避免全局锁序列化（MBTC 式方案会引入死锁），但显著增加非确定性；BFS 需要 convergence pruning，DFS 则牺牲 pruning 保正确性。
- **有界进程数 model checking**：2–5 processes、笔记本 16-core 3 分钟内完成，换可部署性；不声称穷尽任意规模。
- **PlusCal 抽象调度**：`do_wait` 等底层 park 机制视为单原子步并假设正确，把验证焦点放在同步协议逻辑；调度器/IRQ 错误可能逃逸到 by-product 测试才发现。
- **边界条件**：工作流在「有清晰 correctness properties + 可插桩模块 + 单元级 harness」场景最优雅；对分布式跨节点协议需重新建模 process（论文 §7 讨论可扩展性但未实证）。

## 实验与结果

- **规模**：12 个 [[Asterinas]] 并发模块，合计 **3,965 LoC** 代码、**3,032 LoC** 规约、262 actions、77 variables；实际 model checking 约 **4,000 LoC** 范围。
- **Bug**：**20** 个新 bug——**9** 个由 CONVEROS model checking 直接报出（死锁/livelock/互斥/semaphore 下溢等），**11** 个为建模/诊断阶段 by-product；全部确认，**14** 已修复。代表案例：RangeLock lost wakeup（Figure 3–5）、Mutex `then_some` eager eval 导致 guard 误 drop 解锁（Figure 14）、RwLock 非原子 `try_read` 与 `try_downgrade` 竞态致 30 reader 下 downgrade 耗时 26s。
- **人力**：规约 **43.5** 人天 + conformance **21.5** 人天 + 框架开发 12 人天 ≈ **4 人月**（单人 TLA+ 背景）；平均每模块 3.6 人天规约、2 人天 conformance。
- **Spec 效率**：spec-to-code ratio **0.3–2.3**（SpinLock 0.33，RangeLock 1.16，RwMutex 2.28）；SysV Semaphore 最费时（9 人天，复杂 `semop` 语义）。
- **Model checking 性能**：每 bug **≤3 分钟**（2–5 processes，16-core/32GB/22 线程）。
- **评估边界**：相比未报告 competing verifier，所有 runtime 是 12 个 Asterinas module 在 laptop 上的 bounded model-checking 结果，不能外推为无界验证。
- **Conformance**：全流程约 **15** 处 modeling error 被 trace validation 抓住（如 RwMutex `fetch_or` 返回值语义建模错误，Figure 16）；property checking 阶段 **零 false positive**（全部可复现）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| CONVEROS 发现并确认 Asterinas 并发 bug | 20 confirmed，9 direct model checking、11 diagnosis by-product，14 fixed（§6.1，Table 1） | 12 selected concurrency module，非 OS-wide defect rate | high |
| 所报告 bug 在 bounded checking 中快速检测 | 所有报告 bug 在 2–5 process 下少于 3 min（§6 opening） | 16-core/32 GB laptop、22 thread；非 unbounded-state verification | high |
| 12-module corpus 的验证工作量有统计 | 3965 LoC code、3032 LoC spec、43.5 person-day spec、21.5 conformance（§6.2，Table 2） | Git-history estimate；PageCursor conformance 未计 | high |
| trace validation 揭露建模错误 | 约 15 个 modeling error，含 RwMutex fetch_or case（§6.3，Fig. 16） | workflow-specific；未测 false-positive rate | medium |
| RangeLock repair case 需多轮反例驱动修改 | 三个 attempted fix 被模型检查否决后得到 waiter/waker solution（§2，Fig. 3–5） | 单一 case study，不代表 general repair-time reduction | medium |

## 批判性分析

### 论证链条

Observation（Rust OS 并发测试不可靠 + 规约-代码漂移破坏 MC 可信度）→ Design（多层多粒度 PlusCal spec + 增强 bottom-up trace validation + incremental workflow）→ Result（4 人月/20 bugs/可管理 spec ratio）链条在 **「内核同步原语级模块」** 范围内闭合良好。最强证据是 range lock 与 Mutex 等 case study：每次错误修复都被 model checker 反例否决，形成「spec 先行修对 → 代码跟进」闭环。

薄弱跳步在于：从 **12 个模块、有界进程** 的验证外推到「CONVEROS 使 OS 并发验证 practical」——尚未覆盖文件系统 crash consistency、网络协议状态机、完整 syscall 端到端路径；by-product bugs 说明 harness 测试仍承担大量「非 MC 直接发现」工作，论文将 11/20 计入成果合理但模糊了「model checking 直接覆盖率」边界。

### 假设压力测试

- **论文已证明**：在 Asterinas 当前代码快照上，所列模块在 2–5 进程配置下满足所声明 safety/liveness；trace validation 能捕获规约建模错误；missing event 在 SpinLock/Mutex 等场景实用。
- **可能失效（推断）**：
  - **弱内存 / RCU / 无锁结构**：PageCursor 等 lock-free 路径规约更复杂，重构期跳过 conformance 暗示工程摩擦大；未讨论 weak memory 下额外 interleaving。
  - **规模外推**：5 进程以上或 IRQ 与线程交错的真实调度下，harness 是否仍代表 production trace 未验证。
  - **代码演化**：规约维护成本随内核增长线性/超线性累积，论文 4 人月是 snapshot 成本，非持续 CI 集成成本。
- **论文未覆盖**：SMP 核间迁移、优先级反转、实时性 SLO、验证工具链自身的可信基（TLC、编译器、test harness 正确性）。

### 实验可信度

- **Benchmark 代表性**：模块选取覆盖锁、futex、IPC、TTY 等「高价值并发核心」，与 Asterinas 痛点对齐；但不是随机采样或 production fault 分布。
- **Baseline 对比**：未与 SKI/Snowboard/Razzer 等系统化并发测试、或 Kani/VSync 等 Rust/弱内存验证工具定量对比 **bug 发现率 / 人月成本**；与 C2TLA+、CMC、Remix 的对比主要在方法论层面（§8）。
- **Ablation**：missing event、convergence point、自动 trace spec 生成的重要性主要靠 case study 与工程叙述，缺少「关掉 missing event 后 conformance 失败率/工时」的量化 ablation。
- **Metric 覆盖**：聚焦 correctness bugs，未系统测量验证引入的 runtime 插桩开销、CI 周转时间、或修复后性能回归。

### 系统性缺陷

- **尾延迟 / 生产路径**：验证在 test harness 而非真实 syscall 路径；Pipe atomicity bug 竟由 sendfile 测试暴露，说明 harness 与生产 API 组合才能触发某些性质。
- **资源隔离 / 故障恢复**：未讨论验证期间插桩日志对内核时序的影响是否掩盖 heisenbug；论文未讨论在线验证或生产环境监控集成。
- **可观测性 / 运维**：工具链需 TLA+ 专业知识；4 人月由单人完成，团队规模化时的培训与规约 review 流程论文未讨论。
- **持续集成**：未报告规约与代码同步的自动化 CI pipeline；代码快速演化时 conformance 回归成本是 practical 性的长期瓶颈，仅定性声称 incremental 设计可缓解。

## 局限与后续工作

- **局限 1**：验证范围限于 **12 个并发模块**，且均在 **2–5 进程** 有界配置；对全内核或弱内存语义无完备保证。
- **局限 2**：Trace validation **不构成精化证明**，存在接受非一致 trace 的理论 false negative 风险；靠 coverage 与多层规约缓解但无定量上界。
- **局限 3**：Missing event 剪枝可能引入 false positive，需人工读 discrepancy trace；DFS/BFS 模式行为不一致增加调参负担。
- **局限 4**：高度依赖 **Ant Group 内部 Asterinas 开发节奏** 与作者 TLA+ 专长，外推到其他 Rust/C OS 需重建 harness 与领域性质。
- **Future work 1**：对 PageCursor 等 lock-free / 重构中模块补齐 conformance，量化 mixed-grained 粗化在更深层依赖图上的漏检率。
- **Future work 2**：与 [[Asterinas-ATC25]] 的 KERNMIRI 内存安全检测、或 SKI 类 schedule exploration 做 **bug 发现率 × 人月** 对照实验，明确各自适用边界。
- **Future work 3**：将 trace validation + missing event 嵌入 CI，测量「每次 kernel PR 规约漂移检测」的延迟与维护成本，验证是否真可持续 practical。
- **Future work 4**：扩展到底层分布式组件（论文声称 workflow 可复用 Remix 经验），需实证 inter-node message/fault 与 intra-node 并发联合建模开销。

## 相关

- **相关概念**：[[Model-Checking]]、[[TLA+]]、[[PlusCal]]、[[Trace-Validation]]、[[Formal-Methods]]、[[Concurrency]]、[[Rust]]、[[Deadlock]]、[[Livelock]]
- **同类系统**：C2TLA+、CMC、EXPLODE、VSync、Kani、CertiKOS、Verus、Remix、SandTable、CCF（Confidential Consortium Framework）
- **同会议**：[[ATC-2025]]、[[Asterinas-ATC25]]（被验证对象）、[[Remix]]（multi-grained spec 方法论前身）
- **对比**：CONVEROS（MC + trace validation，无手工证明）vs CertiKOS/Verus（deductive verification，强保证高成本）；bottom-up trace validation vs Remix/MBTC top-down 重放；系统化测试（SKI/Snowboard）的 interleaving 探索 vs TLC 状态空间搜索
