# Inferring Likely Counting-related Atomicity Program Properties for Persistent Memory

**作者**：Yunmo Zhang, Junqiao Qiu (City University of Hong Kong); Hong Xu (The Chinese University of Hong Kong); Chun Jason Xue (MBZUAI)
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/zhang-yunmo
**源文件**：[[atc2025-zhang-yunmo.pdf]]

---

## 一、背景

Persistent Memory（PM）技术（如 Intel Optane、CXL-SSD）提供字节寻址的持久化存储接口，绕过传统存储栈开销。然而 PM 编程面临严峻的 crash consistency 挑战：store 先写入 volatile cache 再异步刷写到持久介质，期间 write 顺序可能被重排。程序员需要显式使用 `clflush`/`sfence` 或 transaction 接口确保一致性，但正确使用这些原语要求深厚的专业知识，导致 PM 程序中 crash consistency bug 频发。

现有 PM 测试工具（Witcher、Huang et al.、AGAMOTTO 等）依赖 PM program properties（ordering 和 atomicity 属性）来高效注入 crash 并触发 bug。手动标注这些属性耗时且需要专家知识，因此出现了基于控制依赖和数据依赖的自动推断方法。但现有依赖分析方法在 atomicity 属性推断方面能力有限，特别是无法处理容器类数据结构与其逻辑大小变量之间的原子性关系。

---

## 二、要解决的问题

1. **Counting correlation 未被现有方法覆盖**：PM 程序中普遍存在"数组 + 逻辑大小变量"的模式（如树节点的 `children` 数组与 `childrenCount`），两者需原子更新。但 Witcher 依赖 guardian pattern（flag 变量控制其他变量访问），Huang et al. 依赖双向守护关系，容器类数组通常不充当 guardian 角色，导致这类 atomicity 属性无法被推断。

2. **逻辑大小是程序员意图，非显式行为**：数组的逻辑大小（valid elements 数量）是语义概念，不直接体现在程序行为中。例如数组插入操作中，`size` 变量在插入完成后才更新，中间状态的数组实际大小与 `size` 值不一致，使得直接匹配"定义"变得困难。

3. **并发程序工具不适用于 PM 场景**：MUVI 等并发 bug 检测工具虽可能发现部分 counting-related bug，但缺乏系统性检测能力，且其运行时技术（如控制线程交织）难以迁移到 PM 的任意 crash 场景。

---

## 三、洞察与设计

**关键洞察**：虽然数组的逻辑大小无法从定义中直接获取，但数组的读访问索引必然落在逻辑大小约束的有效元素范围内——这是程序员意图的必然反映。通过验证"所有读索引 < 逻辑大小变量"这一不变量，可以发现 counting correlation 关系。

基于此洞察，论文设计了两类 access range invariant：

- **Read Range Invariant**：对数组的所有读访问，索引必须小于逻辑大小变量的值。这是核心不变量，因为读操作体现了程序员获取有效元素的意图。
- **Write Range Invariant**（可选）：写索引 ≤ 逻辑大小变量值（允许插入操作扩展一个位置），用于提高推断精度。

推断框架三步流程：
1. **Symbolic Range Generation**：使用 Symbolic Range Analysis（SRA）对 LLVM IR 进行分析，计算所有数组访问索引的符号范围（over-approximation）。
2. **Candidate Variable Pairs Generation**：收集所有数组指针和出现在符号范围中的整数变量，形成候选对 `{(ptr, int)}`。
3. **Constraint-based Invariant Validation**：将符号范围编码为 SMT 约束，用 Z3 solver 验证不变量。对 read invariant，检查 `idx_upper < int_lower` 是否恒成立（通过证明其否定 UNSAT）。满足不变量的变量对生成 `ATOMICITY(ptr, int)` 属性。

论文还支持三种 counting correlation 模式：单数组逻辑大小、多数组累计大小、数组互补大小（相对于常量的补数）。

---

## 四、实现细节

- **前端**：C 程序经 LLVM 编译为 bitcode IR，转换为 Extended SSA 形式（φ-function 处理多前驱、σ-function 处理条件分支）。
- **SRA 实现**：基于开源 Nazaré et al. 实现修改的 LLVM compiler pass。符号范围用 `[lower, upper]` 区间表示，程序输入作为符号核。φ-function 取 union（min lower, max upper），σ-function 取 intersection。
- **SMT 编码**：用 Python + Z3 实现。对 read invariant，构建 `∧(idx_upper < int_lower)` 的合取，对 int 的多个 SSA form 取析取。通过证明 `¬INV` 为 UNSAT 来验证不变量。
- **数组识别**：通过 LLVM pass 识别所有指针变量，检查操作数区分数组与普通指针。
- **False positive 处理**：临时循环变量可能被误判为逻辑大小变量，但可通过手动后处理轻松过滤（检查变量在 PM 还是 DRAM 中）。

---

## 五、实验结果

**实验平台**：2× Intel Xeon Gold 5317 CPU，128GB DRAM，512GB Intel Optane DC PM（4× 128GB interleaved mode）。

**测试对象**：

| PM 程序 | 描述 | 版本 |
|---|---|---|
| P-ART | Persistent Adaptive Radix Tree | f0b891a |
| P-BwTree | Persistent BwTree | f0b891a |
| CCEH | Dynamic Hashing for PM | b62a9c8 |
| Level-Hashing | Hash Indexing for PM | 28eca31 |

**Bug 检测结果**：共发现 14 个 atomicity violation，其中 11 个为新发现 bug。

| 对比工具 | 检测 bug 数 |
|---|---|
| 本文方法 | 14 |
| MUVI | 4 |
| Witcher | 3 |

Bug 影响类型包括：fault or data loss（指针数组与逻辑大小不一致导致悬挂指针读取）、stale read or data loss（值数组原子性违反）、memory corruption（分配大小与数组不一致导致读取未分配内存）。

**推断耗时**：0.2–0.6 秒（静态分析，无需探索程序状态），而 Witcher 需要 11 分钟到超过 1 小时。

---

## 六、批判性分析

1. **评测规模极小**：仅测试了 4 个 PM 数据结构程序，且都是相对简单的学术原型（P-ART、P-BwTree、CCEH、Level-Hashing）。论文未在任何生产级 PM 系统（如 PMDK 内部组件、PM 文件系统 NOVA/ext4-DAX）上验证。虽然在动机部分提到了 btrfs 和 ext4 的 counting-related bug，但实验中并未实际测试这些系统。

2. **Bug 验证方式为手动检查，而非实际触发**：论文仅通过人工检查 `TX_BEGIN`/`TX_END` 是否包围相关更新来确认 bug，未实际构造 crash scenario 触发 bug。将推断属性集成到 property-checking 流程（如 Huang et al.）被推迟到 future work，这意味着当前方法的端到端实用性未被验证。

3. **False positive 处理依赖人工**：论文承认临时循环变量会被误判，但仅以"easily filtered by manual post-processing"一笔带过。对于大规模 PM 系统，人工过滤的成本可能不低，且论文未报告 false positive 的具体数量和比例。

4. **三种 correlation pattern 的第二、三种需用户提供参数**：累计大小模式需要用户指定数组数量 N，互补大小模式需要用户提供常量 C。这削弱了方法的"自动推断"定位。

5. **SMT 可扩展性存疑**：论文自己提到 SMT solver 可能成为大规模 PM 系统的瓶颈，提出的缓解措施（限制检查的 SSA、constraint caching）均未实现和验证。0.2–0.6 秒的运行时间建立在极小规模测试对象上，不具说服力。

6. **与 MUVI 和 Witcher 的比较不完全公平**：这两个工具设计目标并非 counting-related atomicity，论文用一个专门针对 counting correlation 的工具去比较通用工具在这一特定子问题上的表现，结论的意义有限。

---

## 七、总结

本文识别了 PM 程序中一类重要但被忽视的 atomicity 属性——counting correlation（容器类数组与其逻辑大小变量的原子性关系），提出基于 access range invariant 和 symbolic range analysis + SMT solving 的自动推断方法。在 4 个 PM 数据结构上发现 14 个 atomicity bug（11 个新发现）。方法思路清晰、推断速度快，但评测规模小、端到端验证缺失、可扩展性未经检验，实际应用价值有待更大规模系统上的验证。
