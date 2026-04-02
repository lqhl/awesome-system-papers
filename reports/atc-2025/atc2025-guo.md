# Optimizing Input Minimization in Kernel Fuzzing

**作者**：Hui Guo (East China Normal University), Hao Sun (ETH Zurich), Shan Huang (East China Normal University), Ting Su (East China Normal University), Geguang Pu (East China Normal University), Shaohua Li (The Chinese University of Hong Kong)
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/guo
**源文件**：[[atc2025-guo.pdf]]

---

## 一、背景

Coverage-guided kernel fuzzing 是发现操作系统内核 bug 的最有效手段之一。Syzkaller 作为最具代表性的内核 fuzzer，已在 Linux 内核中发现超过 5000 个 bug，并被集成到 Linux 内核的测试流水线中。

Kernel fuzzing 的核心循环包含两个阶段：**mutation**（变异生成新的系统调用序列）和 **minimization**（最小化有趣程序以保留覆盖率的同时去除冗余调用和参数）。Minimization 对后续 mutation 的质量至关重要——实验表明去掉 minimization 会导致覆盖率下降 27.5%、发现 bug 数下降 40.4%。然而，minimization 阶段本身开销巨大：在 48 小时的 fuzzing campaign 中，57.5% 的程序执行被消耗在 minimization 上，其中 call removal 占 34.0%，argument simplification 占 66.0%。

---

## 二、要解决的问题

Syzkaller 当前采用 **one-by-one minimization** 策略：对一个 interesting program 中的每个 call 逐个尝试移除，对每个参数逐个尝试简化，每次尝试都需要执行程序来验证覆盖率是否保留。这带来两个关键问题：

1. **Call removal 代价高**：对 n 个调用的序列，需要 n-1 次程序执行来逐个尝试移除，即使很多调用与 target call 毫无关联。
2. **Argument simplification 代价高**：对每个参数及其子字段逐一简化，但大量 fixed-size 参数（如 Integer、Flag、Resource）的简化对减少后续 mutation 空间无实质帮助，属于无效开销。

此前没有工作系统性地探索和解决 kernel fuzzing 中 minimization 的高成本问题。

---

## 三、洞察与设计

**关键洞察**：

1. **对于 call removal**：如果一个 call 与 target call 之间不存在 influence relation（即不共享任何全局内核状态），那么移除该 call 不会影响 target call 的覆盖率。因此可以通过静态和动态分析推断 influence relation，将所有无关 call 一次性移除，而非逐个尝试。
2. **对于 argument simplification**：只有 variable-size 参数（如 Array、Buffer）的简化才能有效减少 mutation 搜索空间；fixed-size 参数（如 Integer、Flag、Resource）的简化不改变 mutation 空间大小，可以直接跳过。

基于上述洞察，论文提出两个优化策略：

### Influence-guided Call Removal

- 定义 **influence relation**：call $c_i$ 对 $c_j$ 有影响，当且仅当执行 $c_i$ 能通过修改内核内部状态来改变 $c_j$ 的执行路径。
- 通过静态分析（基于 Syzlang 类型信息中的 resource 共享关系）和动态分析（观察 minimization 过程中移除 call 后对下一个 call 覆盖率的影响）收集 influence relation，存入二维矩阵 M。
- 给定 interesting program P 和 target call $c_n$，通过 worklist 算法识别所有与 $c_n$ 有直接或间接 influence relation 的 relevant calls，其余为 irrelevant calls。
- 一次性移除所有 irrelevant calls，仅需 1 次执行验证。若验证失败则回退，再进行 one-by-one removal 确保最小性。

### Type-informed Argument Simplification

- 分析每个参数的类型信息：primitive type（Integer、Flag、Protocol、Resource）为 fixed-size；derived type（Array、Buffer）为 variable-size；Pointer 和 user-defined type 递归分析。
- 跳过所有 fixed-size 参数的简化，仅对 variable-size 参数执行二分搜索式的元素缩减。

两个策略正交，分别优化 minimization 的两个子阶段。

---

## 四、实现细节

- 基于 Syzkaller（commit 1759857fa9bd）实现，命名为 **SyzMini**。
- **Influence relation 收集**：参考 HEALER 的方法，结合静态分析和动态分析。静态分析检查两个 syscall 之间是否通过 resource type 共享状态；动态分析在 Syzkaller 默认 minimization 过程中观察 call 移除对相邻 call 覆盖率的影响。运行 Syzkaller 至覆盖率饱和（约 4 天），共收集 74,865 条 influence relation（44,966 条静态 + 29,899 条动态）。
- **类型分析**：基于 Syzlang 的类型声明，递归分析参数类型。Linux 内核中约 80% 的参数为 fixed-size（2020-2023 年的 Syzkaller 数据）。
- 覆盖率验证使用 Syzkaller 默认的 branch coverage，按 call 粒度独立记录。
- 代码开源：https://github.com/ecnusse/SyzMini

---

## 五、实验结果

**实验环境**：AMD 3995WX 64-core CPU，128GB RAM，Ubuntu 20.04 LTS。测试内核：Linux 5.15、6.1、6.11。每个 VM 分配 4 核 CPU + 4GB RAM。每轮 24 小时，重复 10 轮。

### 覆盖率和 Bug 检测（RQ1）

| 指标 | Linux v5.15 | Linux v6.1 | Linux v6.11 | 总体 |
|------|------------|------------|-------------|------|
| Syzkaller 覆盖率 | 145.371K | 150.677K | 133.172K | 143.073K |
| SyzMini 覆盖率 | 164.724K | 169.015K | 149.311K | 161.017K |
| 覆盖率提升 | +13.3% | +12.2% | +12.1% | **+12.5%** |
| Speed-up | 1.83× | 1.61× | 1.62× | **1.69×** |

| Fuzzer | v5.15 | v6.1 | v6.11 | 总 Bug 数 |
|--------|-------|------|-------|----------|
| Syzkaller | 14 | 12 | 6 | 27 |
| SyzMini | 28 | 20 | 12 | **50** |

- SyzMini 发现 **1.7–2× 更多的 unique bugs**。
- 在 22 个共同 bug 上，SyzMini 的 hitting-round 更高、µTTE 更低。
- 长期 fuzzing（3 天）：SyzMini 在最新上游内核发现 **13 个未知 bug**，全部得到确认，4 个已修复。

### Minimization 成本降低（RQ3）

| 策略 | Call Removal 执行数 | Arg Simplification 执行数 | 总执行数 |
|------|-------------------|-------------------------|---------|
| One-by-one | 140,620 | 260,239 | 400,859 |
| Influence-guided | 60,372 (↓57.1%) | – | 320,611 (↓20.0%) |
| Type-informed | – | 96,896 (↓62.8%) | 237,516 (↓40.7%) |
| 两者结合 | 60,372 (↓57.1%) | 96,896 (↓62.8%) | **157,268 (↓60.7%)** |

Minimization 占程序执行比例从 ~48-53% 降至 ~11-16%。

### 通用性验证（RQ4）

| 增强工具 | 覆盖率提升 | Bug 提升 |
|---------|-----------|---------|
| SyzVegas+ | +14.5% | 1.5× unique bugs |
| CountDown+ | +4.5% | +66.7% KASAN bugs |
| SyzDirect+ | – | 1.5× bug reproduction |

---

## 六、批判性分析

1. **Influence relation 的精度与完整性问题**：静态分析仅基于 resource type 共享关系推断 influence，这是一个保守但不完整的近似。动态分析仅观察相邻 call 的影响，忽略了间接依赖的动态表现。论文承认了精度问题但未深入量化 false positive/negative 的比例。Figure 11 的实验隐含了精度随 proportion 变化的趋势，但这个 proportion 本质上是随机抽样而非精度控制。

2. **Influence relation 收集的前置成本被低估**：收集 influence relation 需要运行 Syzkaller 约 4 天至覆盖率饱和。这一前置成本在评估中未被纳入总时间预算。对于不同内核版本或配置，是否需要重新收集也未讨论。

3. **实验基线选择有局限**：所有比较对象都是 Syzkaller 及其衍生工具。未与其他 minimization 优化方法（如基于 delta debugging 的变体）进行比较。虽然论文解释了 delta debugging 不能直接用于 syscall 序列，但并非完全不可适配。

4. **Bug 去重方式的影响**：论文使用 KASAN 报告的 call trace 进行 bug 去重，但未详细说明去重策略的粒度。不同的去重粒度可能显著影响 1.7-2× 的数字。

5. **Type-informed 策略的假设过于强**：论文假设 fixed-size 参数的简化对减少 mutation 空间无益。但实际上，mutation 不仅仅是搜索空间大小的问题——将 fixed-size 参数简化为默认值可能影响后续 mutation 的路径多样性。论文未分析跳过 fixed-size simplification 是否导致某些 bug 被遗漏。

6. **长期有效性数据不充分**：24 小时和 3 天的实验对于评估 kernel fuzzer 而言较短。工业级 fuzzing（如 syzbot）通常是数周甚至持续运行。12.5% 的覆盖率优势是否会随时间收敛未有充分证据。

---

## 七、总结

SyzMini 提出了两个正交的优化策略来降低 kernel fuzzing 中 minimization 阶段的开销：influence-guided call removal 利用系统调用间的影响关系批量移除无关调用，type-informed argument simplification 利用参数类型信息跳过 fixed-size 参数的简化。两者结合将 minimization 的程序执行开销降低 60.7%，使更多资源分配给 mutation，从而实现 12.5% 的覆盖率提升和 1.7-2× 的 bug 发现增长。该方法通用性好，可集成到多种 Syzkaller 衍生 fuzzer 中。主要局限在于 influence relation 需要较高的前置收集成本，且对不同内核版本/配置的迁移性未充分验证。
