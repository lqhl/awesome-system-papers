# Deriving Semantic Checkers from Tests to Detect Silent Failures in Production Distributed Systems

**作者**：Chang Lou (University of Virginia), Dimas Shidqi Parikesit (University of Virginia / Bandung Institute of Technology), Yujin Huang (Pennsylvania State University), Zhewen Yang, Senapati Diwangkara (Johns Hopkins University), Yuzhuo Jing (University of Michigan), Achmad Imam Kistijantoro (Bandung Institute of Technology), Ding Yuan (University of Toronto), Suman Nath (Microsoft Research), Peng Huang (University of Michigan)
**会议**：OSDI 2025
**链接**：https://www.usenix.org/conference/osdi25/presentation/lou
**源文件**：[osdi25-lou.pdf](../../papers/osdi-2025/osdi25-lou.pdf)

---

## 一、背景

生产环境中的分布式系统提供丰富的功能（成百上千的 API、参数、命令等），但各种缺陷可导致系统**静默违反其语义**（silent semantic failures），即系统没有显式错误信号就出了问题——数据丢失、结果错误、状态不一致、安全漏洞等。这类故障无法被传统的基于 CPU 使用率、超时、异常的监控检测到。

检测此类故障需要**语义检查器（semantic checker）**，即验证系统特定语义（如 at-most-once delivery、snapshot immutability）的运行时检查逻辑。然而，编写语义检查器需要深厚的领域知识和大量人力，对大型分布式系统来说是一项艰巨的任务。近期研究 [Lou et al., OSDI'22] 表明，静默故障在成熟、经过充分测试的分布式系统中占所有故障的 39%，说明问题的普遍性和严重性。

---

## 二、要解决的问题

1. **语义检查器难以自动构建**：现有方案要么依赖手动编写（耗时、不可扩展），要么使用统计方法从执行 trace 推断不变量（Daikon/Dinv），但推断出的不变量仅表达低级变量关系，难以捕获系统级语义，且假阳性高。

2. **测试代码蕴含语义信息但无法直接复用**：分布式系统的测试用例包含丰富的语义检查逻辑（assertions），但它们被绑定在特定输入和固定环境下，无法直接在生产中检测不同 bug 引发的语义违反。例如 ZooKeeper 的 ephemeral znode 测试只检查固定路径 `/stest`，无法覆盖生产中其他路径的问题。

3. **从测试到检查器的转换面临多重挑战**：
   - 测试代码混合了 workload 执行和结果检查，需要解耦
   - 检查器需要确定其触发的前置条件（precondition），但测试中并未明确指定
   - 测试使用具体实例，而检查器需要泛化到更多场景
   - 部分测试包含危险操作（删除文件、重启集群），不能在生产中执行

---

## 三、核心设计

T2C（Test-to-Checker）的核心思路是：**直接将已有的测试代码转换为运行时语义检查器**，复用测试中的代码骨架，但松弛其严格约束以泛化检查。

### 可行性研究

作者对 6 个系统的 210 个测试用例进行了大规模研究，关键发现：
- 87% 的测试使用标准 assertion 作为检查机制
- 64% 的测试中，assertion 的期望值约束简单（常量、相等关系、同变量引用）
- 65% 的测试的检查逻辑可以泛化到生产环境
- 22% 的测试使用模块化的 utility 函数

### 整体架构

T2C 分为**离线阶段**和**生产阶段**：

**离线阶段**：
1. **Checker Function 封装**：通过静态分析（backward data-flow analysis + program slicing），从测试 oracle（assertion）出发反向追踪依赖，提取相关语句，构建参数化的 checker 函数 $C_f$。使用 purity analysis 排除有副作用的操作。
2. **Precondition 识别**：通过动态分析执行测试，记录系统操作序列，提取 assertion 之前的操作序列作为具体 precondition $C_p$。
3. **符号化**：将具体值替换为符号变量，通过等值推断等简单约束推导泛化 precondition。
4. **Precondition 变异**：通过 reduce、insert wildcard、duplicate、reorder 四种变异操作产生 variant checker，进一步扩大覆盖范围。
5. **四级验证**：编译检查 → JVM 验证 → self-validation（在原测试中替换 assertion 验证） → cross-validation（在其他测试的 workload 上运行，过滤 false positive）。

**生产阶段**：
- 部署 checker 和 verifier
- Verifier 监控系统 workload，使用 **trie 索引** 加速 precondition 匹配
- 使用 **circular buffer** 管理运行时 trace，控制内存开销
- Precondition 匹配后，将具体参数传入 checker 函数执行检查
- 检查失败时生成告警和调试报告

---

## 四、实现细节

- 主要用 **Java** 实现，约 **8,000 SLOC**
- 静态分析基于 **Soot** 程序分析框架
- 动态插桩基于 **Javassist** 字节码编辑库
- 核心设计（封装算法、参数符号化）不依赖 Java 特性，可移植到其他语言（如用 LLVM 支持 C/C++）

**关键数据结构**：
- **Trie**：用于 precondition 索引，将所有 checker 的 precondition（操作序列）反转后插入 trie，匹配时只需遍历当前 trace 的后缀
- **Circular Buffer**：管理运行时 trace，固定内存上限，避免 GC 开销，同时避免 worker 线程和 verifier 之间的竞争

**分布式语义检查**：提供 cluster mode，跨节点聚合 trace，通过分布式日志库转发事件到对应节点触发 assertion。

**接入新系统**：开发者需提供代码结构配置文件、编译指令、少量核心类（用于插桩）、约 6 个 side-effecting 操作、约 3 个 testing utility adapter 类。集成 HBase 花费约一人周。

---

## 五、实验结果

### 实验环境
20 核 2.2GHz CPU，64GB 内存，Ubuntu 18.04

### Checker 生成（Table 2）

| 系统 | 版本 | 目标测试 | 成功封装 | 健康 Checker | 验证通过 |
|------|------|---------|---------|-------------|---------|
| ZooKeeper | 3.4.11 | 109 | 100 | 90 | 46 |
| Cassandra | 3.11.5 | 257 | 242 | 232 | 100 |
| HDFS | 3.2.2 | 816 | 729 | 707 | 230 |
| HBase | 2.4 | 990 | 948 | 904 | 296 |
| **Total** | | **2172** | **2019** | **1933** | **672** |

生成的 672 个 checker 平均包含 4.3 个 assertion。

### 故障检测（Table 4）

在 20 个真实世界的静默故障上评估：

| 检测器 | 检出数 |
|--------|--------|
| **T2C** | **15/20** |
| Event checker (Oathkeeper) | 5/20 |
| State checker (Dinv) | 3/20 |
| In-vivo checker | 1/20 |
| 所有 baseline 组合 | 8/20 |

T2C 的中位检测时间为 **0.188 秒**。

### 误报率（Table 6）

使用 Jepsen 框架在无故障场景下测试 30 分钟：

| 系统 | In-vivo | State | Event | T2C |
|------|---------|-------|-------|-----|
| ZooKeeper | 2.6% | 14.2% | 3.9% | 1.3% |
| Cassandra | 55.3% | 4.7% | 9.6% | 1.0% |
| HDFS | 68.9% | 6.2% | 9.3% | 3.2% |
| HBase | 62.6% | 22.8% | 17.9% | 0.6% |

### 运行时开销（Table 8）

| 系统 | In-vivo | State | Event | T2C |
|------|---------|-------|-------|-----|
| ZooKeeper | 0.1% | 24.8% | 1.9% | 1.4% |
| Cassandra | 3.0% | 59.0% | 1.8% | 9.1% |
| HDFS | 4.4% | 61.6% | 2.7% | 3.8% |
| HBase | 1.9% | 93.3% | 0.7% | 1.5% |

T2C 平均吞吐量开销 **4.0%**，内存增加 **<6%**。

### 新 Bug 发现

在评估过程中，T2C 在最新版 ZooKeeper 3.9.2 中发现了一个新 bug（ZOOKEEPER-4837），被标记为 **P1 Critical**，会导致数据损坏和不一致。

---

## 六、批判性分析

1. **泛化能力的上限受限于测试质量**：T2C 的根本假设是系统测试中包含有价值的语义信息。但对于测试覆盖不足的语义，T2C 无能为力。论文承认 5 个未检出案例中部分是因为系统缺少相关测试，但未深入讨论这在实践中的普遍程度——成熟系统有好的测试，但真正需要此工具的可能恰恰是测试不充分的系统。

2. **Cross-validation 的有效性存疑**：Cross-validation 用其他测试的 workload 来过滤 over-generalized checker，但这本质上仍依赖测试覆盖率。如果测试集缺乏某些边界场景，over-generalized checker 可能逃过过滤。

3. **Side-effect 排除不完备**：论文使用 purity analysis + 手动列表排除危险操作，但明确承认"不能完全保证 checker 无副作用"。在生产部署中这是一个严肃的安全问题，论文将其交给未来工作（sandboxing、formal verification），但未给出具体解决方案。

4. **符号化和约束推断的局限**：22% 的测试包含 magic value，约束无法自动推断。论文的等值约束推断也可能产生过约束（coincidental equality），这些都是系统性局限而非偶发问题。

5. **评估偏差**：故障基准集（20 个故障）的选取通过关键词搜索 + 随机抽样，然后手动确认，样本量较小且存在选择偏差。检出的 15 个故障中，生成 checker 的测试平均在故障发生前 3.9 年就已存在——这暗示这些系统测试覆盖较好的区域恰恰也是 T2C 能工作的地方，可能高估了实际部署效果。

6. **仅支持 Java 系统**：当前实现依赖 Soot 和 Javassist，对 C/C++（如 MongoDB、CephFS）系统仅停留在"应该可以移植"的声明。考虑到 C/C++ 的指针分析和动态分析复杂度远超 Java，这一泛化并不简单。

7. **离线处理时间较长**：Build + Validate 阶段对 HDFS 需要约 13.5 小时，对 HBase 约 7.7 小时。虽然是一次性成本，但随着系统测试的持续增长，增量更新策略缺失可能成为实际障碍。

---

## 七、总结

T2C 提出了一种新颖的方法，通过静态和动态分析将分布式系统的已有测试代码自动转换为运行时语义检查器，用于检测生产环境中的静默故障。其核心贡献在于：（1）大规模可行性研究验证了测试代码蕴含可泛化的语义信息；（2）端到端框架实现了从测试到检查器的自动转换，包括 checker 封装、precondition 提取与符号化、变异和多级验证；（3）在 4 个大型分布式系统的 20 个真实故障上，T2C 检出 15 个，显著优于所有 baseline，且误报率低、运行时开销可控（~4%）。主要局限是依赖测试质量、仅支持 Java、side-effect 排除不完备。该工作填补了大型分布式系统语义检查器自动构建的空白，为运行时故障检测提供了一个实用且可扩展的方案。
