# CONVEROS: Practical Model Checking for Verifying Rust OS Kernel Concurrency

**作者**：Ruize Tang (南京大学), Minghua Wang (蚂蚁集团), Xudong Sun (UIUC), Lin Huang (蚂蚁集团), Yu Huang (南京大学), Xiaoxing Ma (南京大学)
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/tang
**源文件**：[[atc2025-tang.pdf]]

---

## 一、背景

ASTERINAS 是一个用 Rust 编写的开源通用操作系统内核，兼容 Linux ABI，目标是在蚂蚁集团生产环境中部署。尽管 Rust 的所有权模型大幅增强了内存安全，OS 内核开发不可避免地需要 unsafe 代码，仍可能引入数据竞争等并发相关的未定义行为。逻辑错误和设计缺陷则可能导致死锁、活锁和功能违反。这些并发 bug 极难检测、复现和正确修复。

形式化方法中的 model checking（模型检查）是验证并发正确性的有力手段，近年来在工业界（AWS、Azure CCF 等）取得了成功应用。然而，将 model checking 应用于复杂的 OS 实现面临两大障碍：（1）编写形式化规约（specification）需要形式化方法的专业知识，且质量差的规约会阻碍 model checking 的可扩展性；（2）规约与实现之间的不一致（discrepancy）会损害验证结果的有效性，导致假阳性和假阴性。

---

## 二、要解决的问题

1. **规约编写的实用性**：传统形式化规约编写难度高，需要深厚的形式化方法背景，且难以随代码演进增量更新。对于有数十个 label 的低层规约，一次性完整编写和维护成本过高。

2. **规约-代码一致性（conformance）**：规约与实现之间的不一致是 model checking 的致命弱点——建模错误或代码快速迭代都可能使验证结果失效。现有的 trace validation 方法假设事件顺序精确记录且 trace 长度与规约完全匹配，这在共享内存并发场景中难以满足（时间戳不精确、日志不完整）。

3. **状态空间爆炸**：直接对复杂内核模块进行 model checking 面临状态空间爆炸问题，需要有效的分层和分粒度策略来管理验证规模。

---

## 三、洞察与设计

**关键洞察**：OS 并发模块天然具有层次化和可组合的结构——公共 API 抽象了设计意图，内部实现包含低层细节——可以利用这种结构将规约分为高层（设计正确性）和低层（代码细节），并在不同粒度上增量组合验证，从而使 model checking 在实际 OS 验证中变得可行。

### 三步工作流

CONVEROS 的验证流程分三步：
1. **编写形式化规约**（PlusCal → TLA+）
2. **Conformance checking**（trace validation 检查规约-代码一致性）
3. **Model checking**（在精化后的规约上验证安全性和活性属性）

### Multi-Layered Specifications（多层规约）

- **高层规约**：捕捉设计意图，只建模公共 API（如 `acquire_lock`/`release_lock`），简单直接，易于编写和验证。主要用于基本同步原语（spinlock、mutex）。
- **低层规约**：紧密反映代码实现细节，每个共享变量的修改对应一个原子动作（label）。当存在 bug 时，低层规约能够有效检测。

### Multi-Grained Specifications（多粒度规约）

借鉴 Remix 的方法论：
- **细粒度模块**：详细建模代码级行为
- **粗粒度模块**：保留交互接口但省略内部细节，减少状态空间
- 混合粒度规约组合使用，实现增量建模和可扩展验证

### 增强的 Trace Validation

引入 missing event 算法：允许 trace 中存在缺失事件，由 TLC model checker 自动推断可能的事件顺序。这解决了：
- 共享内存并发中时间戳不精确导致的事件乱序
- 低层规约大量 label 的日志负担（可增量添加日志）
- 自动生成 discrepancy trace 辅助调试

---

## 四、实现细节

### 规约语言选择

采用 PlusCal（编译为 TLA+）作为规约语言。PlusCal 的类 C 命令式语法对程序员更友好，降低了编写门槛。使用 TLC 作为 model checker。

### Trace Validation 框架

- **日志收集**：手动编写轻量测试 harness（类似单元测试），在代码的关键位置插入 `TlaLogger` 记录每个动作
- **Trace specification 自动生成**：解析 PlusCal 编译后的 TLA+ 规约，自动生成 trace specification
- **Missing event 机制**：在关键代码区域前后插入 missing event 标记，TLC 在状态探索时自动推断可能的中间事件
  - 引入两个剪枝约束：最大探索深度和收敛点（convergence point）
  - DFS 模式下禁用收敛剪枝以避免假阳性

### Discrepancy 调试

自动生成 discrepancy trace：当 trace validation 失败时，执行第二轮运行，在最长未匹配 trace line 处设置断点，构造反例路径。

### 正确性属性

- 安全性（Safety）：mutual exclusion、semaphore count ≥ 0 等
- 活性（Liveness）：deadlock-free、livelock-free、starvation-free

### 代码规模

- Trace validation 框架：681 行 Rust + 396 行 Python
- 12 个模块共约 4,000 行 ASTERINAS 代码被验证
- 规约总计 3,032 行 PlusCal

---

## 五、实验结果

### Bug 发现

在 ASTERINAS 的 12 个并发模块中发现 20 个 bug：

| 类别 | 数量 | 详情 |
|------|------|------|
| CONVEROS 自动发现 | 9 | 包括 deadlock、mutual exclusion violation、livelock/starvation、功能安全违反 |
| 诊断过程中发现的附带 bug | 11 | kernel panic、hang、数据截断、栈溢出等 |
| 已修复 | 14 | 其余未修复因优先级低 |

### 关键 Bug 案例

| Bug | 模块 | 违反属性 | 根因 |
|-----|------|---------|------|
| #1 | RangeLock | Deadlock-free | 等待过时 wait queue 导致 lost wakeup |
| #2 | Mutex | Mutual exclusion | `then_some` 导致 MutexGuard 提前 drop 引发非预期解锁 |
| #3 | RwLock | Livelock/Starvation-free | 非原子 `try_read` 与 `try_downgrade` 竞争 |
| #9 | TTY | Deadlock-free | 四个 spinlock 的循环依赖 |

### 验证开销

| 指标 | 数据 |
|------|------|
| 总投入 | 约 4 person-months（1 名具有 TLA+ 经验的开发者） |
| 规约编写 | 43.5 person-days |
| Conformance checking | 21.5 person-days |
| Spec-to-code ratio | 0.3 ~ 2.3 |
| 每个模块平均代码量 | 330 行 |
| 每个模块平均规约时间 | 3.6 person-days |
| Bug 检测时间 | 均在 3 分钟内（16 核 CPU、32GB RAM、22 并行线程） |

### Discrepancy 发现

在整个工作流中发现约 15 个建模错误，trace validation 在发现微妙的规约-代码不一致方面特别有效。

---

## 六、批判性分析

1. **单人专家依赖**：整个验证工作由一名具有 TLA+ 专业知识的开发者完成。论文声称 CONVEROS "accessible"，但 4 person-months 的投入对大多数开发团队而言仍是不小的门槛。PlusCal 虽比 TLA+ 友好，但仍需要对形式化方法有相当理解。

2. **Conformance 的局限被轻描淡写**：论文承认 trace validation 不能证明 refinement，可能接受不符合规约的 trace，但没有量化这个 gap 有多大。12 个模块中 PageCursor 跳过了 conformance checking（因为模块在重构中），说明该方法对快速迭代的代码适用性有限。

3. **Bug 数量的统计口径**：20 个 bug 中 11 个是"by-product bugs"（诊断过程中手动发现），严格来说不是 CONVEROS 自动检测的。将这些归功于 CONVEROS 有夸大之嫌，虽然 CONVEROS 确实创造了发现它们的机会。

4. **实验规模受限**：仅验证了约 4,000 行代码（ASTERINAS 总计 100K 行），覆盖率约 4%。论文没有讨论如何扩展到更大范围的模块，或对非并发模块的适用性。

5. **Missing event 的正确性-效率权衡**：missing event 机制虽然提升了实用性，但引入了额外的非确定性，可能导致假阳性（false convergence pruning）或假阴性（探索深度不足）。论文提到需要"略高于估计值"地设置最大深度，但如何确定这个值缺乏系统方法。

6. **与其他工具的比较不充分**：没有与 Kani、VSync、fuzzing 工具（Razzer、OZZ）在同一组 bug 上进行直接对比，难以判断 CONVEROS 的相对优势。

---

## 七、AI Infra / MLSys 视角

本文主要聚焦 OS 内核并发验证，与 AI Infra 没有直接关联。但以下几点值得关注：

1. **Rust 在系统软件中的并发验证需求**：随着越来越多的 AI 基础设施（如高性能推理引擎、分布式训练框架）采用 Rust 编写，CONVEROS 的方法论可为这些系统的并发正确性验证提供参考。特别是自定义同步原语（如 GPU 调度器中的 lock-free 数据结构）是 bug 高发区。

2. **分布式系统适用性**：论文在 §7 讨论了 CONVEROS 的可推广性，指出可以扩展到分布式系统的 crash safety 和 fault tolerance 验证。对于分布式训练中的 checkpoint、gradient synchronization、fault recovery 等关键路径，类似的多层多粒度规约方法可能有价值。

3. **增量验证思路**：AI 系统代码迭代极快，CONVEROS 的增量式 conformance checking 思路——先用高层规约快速验证，再逐步细化——与 AI Infra 的快速迭代需求匹配。

---

## 八、总结

CONVEROS 提出了一套实用的 OS 并发模块 model checking 方法论，核心创新包括多层多粒度规约方法和增强的 trace validation（支持 missing event 自动推断）。在 ASTERINAS 的 12 个并发模块上，以约 4 person-months 的投入发现了 20 个 bug（含 9 个自动发现的严重并发 bug），spec-to-code ratio 仅 0.3-2.3，展示了 model checking 在实际 OS 验证中的可行性。主要局限在于需要形式化方法专业知识、trace validation 不等价于 refinement proof、以及 missing event 机制在正确性和效率间的权衡。
