---
type: paper
name: CountingAtomicity
full_title: "Inferring Likely Counting-related Atomicity Program Properties for Persistent Memory"
authors: [Yunmo Zhang, Junqiao Qiu, Hong Xu, Chun Jason Xue]
venue: ATC
year: 2025
tags: [persistent-memory, atomicity, crash-consistency, static-analysis, smt]
source_pdf: "[[atc2025-zhang-yunmo.pdf]]"
source_md: "[[atc2025-zhang-yunmo]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# CountingAtomicity：推断持久内存的可能与计数相关的原子性程序属性（ATC 2025）

> **原题**：Inferring Likely Counting-related Atomicity Program Properties for Persistent Memory

> **一句话总结**：PM 程序中容器数组与其逻辑 size 变量之间存在 counting correlation，但 dependency-based 推断（[[Witcher]]、Huang et al.）因数组不充当 guardian 而抓不到；本文用 read/write range invariant + [[Symbolic-Range-Analysis]] + [[SMT]]（Z3）静态推断 likely 原子性属性，在 P-ART、P-BwTree、CCEH、Level-Hashing 上发现 **14** 个原子性 bug（**11** 个新），分析耗时 **0.2–0.6s/程序**，远快于 Witcher 的 **11min–1h**，且覆盖 MUVI（4）与 Witcher（3）漏检的多数 case。

## 问题与动机

[[Persistent-Memory]]（Intel Optane、CXL-SSD 等）提供 byte-addressable 持久存储，但 store 先写 volatile cache 再异步 flush，crash 时持久化顺序可能与程序顺序不一致。程序员需显式使用 `clflush`/`clwb` + `sfence`，或 [[PMDK]] 的 transaction（TX）接口保证 crash consistency。即便如此，真实 PM 程序仍大量存在 ordering bug 与 atomicity bug。

现有 PM 测试工具（[[Witcher]]、Huang et al.、[[Pmtest]] 等）为控制爆炸的 PM 状态空间，依赖开发者手工标注或预先指定的 program properties 来高效注入 crash。Witcher 与 Huang et al. 尝试从 control/data dependency 自动推断 likely properties，对 ordering（persist-before）效果较好，但对 **atomicity（persist-together）** 覆盖不足——它们只识别 guardian 变量模式：要么多个 guardian 需原子更新（Witcher），要么 guardian 互相 guard 形成循环依赖（Huang et al.）。

PM 中更常见的一类结构是 **counting correlation**：容器式数组（children、hash bucket、ring buffer slot 等）与记录其逻辑元素个数的整型 size 变量语义绑定。例如 P-ART 的 `children` 与 `childrenCount`：crash 若只持久化数组或只持久化 size，恢复后会读到 dangling pointer 或丢失已写入数据。这类结构在 hash table、radix tree、file system metadata（btrfs `i_size`、ext4 `i_disksize`）中普遍存在，但数组本身不是 `if(x)` 里的 guardian，dependency 分析系统性漏检。

作者 claim：需要 complement 现有 atomicity 推断的 **第三类属性模式**——counting-related atomicity——并给出可静态验证的 inference framework，最终用于 PM bug detection。

## 关键观察 / 隐含假设

- **观察 1：逻辑 size 是程序员意图而非程序语义，不能直接用「SZ == 数组有效长度」定义 counting correlation。** 数组 insert 中间态（Listing 1：先 shift 再 `size += 1`）会使真实有效长度与 SZ 暂时不一致，静态定义会误判。
  - **依赖假设**：程序员意图可通过 **访问范围行为** 间接刻画——所有 **read** 索引必须落在 SZ 约束的有效元素区间内。
  - **可能失效场景**：若程序对数组的 read 不经过 size 约束（如无界 scan、错误指针算术），invariant 不成立，推断失效；若 size 与数组关系是间接的（通过多级 indirection），候选对生成可能漏掉。

- **观察 2：write 索引可临时越出当前逻辑 size（insert 写 `[p, size]`），因此 read range invariant 比 write range 更可靠；可选 write range invariant（`idx ≤ SZ + c`）在「每次 insert 只增 1 元素」假设下可提高精度。**
  - **依赖假设**：PM 数据结构更新以 append/insert 为主，单次操作扩展幅度有界（默认 `c=0`）。
  - **可能失效场景**：batch resize、memmove 整块重写、或一次操作插入多个元素时，write invariant 需调大 `c` 或失效；论文默认 `c=0` 可能漏报或误报。

- **观察 3：dependency-based 工具（Witcher、Huang et al.）在 14 个 detected bug 中仅分别覆盖 3 个，因为数组很少作为 guardian 出现在条件分支；MUVI 的 access-together-times 启发式在 insert 场景下需极低阈值才有效，不具可扩展性。**
  - **依赖假设**：counting bug 是 PM 测试工具当前 coverage gap 的主要来源之一，而非边缘 case。
  - **可能失效场景**：若生产代码普遍用 TX 包裹所有 array+size 更新，或 size 更新与数组更新在同一条原子指令路径上，实际 bug 密度可能低于 benchmark 样本。

- **假设 1：Symbolic Range Analysis（SRA）对 C/LLVM IR 的数组访问索引与整型变量范围 over-approximation 足够紧，可支撑 SMT 证明 invariant。**
  - **证据强度**：**中**。Listing 1 手工 walkthrough 与 P-ART 等真实程序结果支持；但 SRA 本质是 over-approximation，undecidable 索引直接编码为 False 丢弃，可能漏检。

- **假设 2：候选 (ptr, int) 对只需枚举「出现在 ptr 符号访问范围中的整型变量」，无需全程序笛卡尔积。**
  - **证据强度**：**中强**。大幅缩小搜索空间且在四个 benchmark 上找到 14 bug；但对间接 size（通过 struct 字段链、宏展开）的覆盖论文未系统讨论。

- **假设 3：推断出的 likely property 可通过检查更新是否位于 `TX_BEGIN`/`TX_END` 之间来确认 violation。**
  - **证据强度**：**弱到中**。evaluation 采用 **手工** 确认而非端到端 trace-based checker；作者明确将集成到 Huang et al. 式 property-checking 留给 future work。当前 pipeline 是 inference + manual audit，不是全自动 testing tool。

## 核心方法

论文把 counting correlation 形式化为三种 pattern，均要求满足 **ATOMICITY(SZ, ARR)**（persist-together）：

1. **单数组逻辑 size**：SZ 表示 ARR 有效元素数。
2. **多数组累计 size**：`Σ idx_i < SZ_s`（默认 N=2）。
3. **补 size**：`idx < C - SZ_c`（需用户提供常数 C）。

核心推断不依赖 causation（dependency），而依赖 **correlation**：变量在整个程序执行中维持语义关系。

**Invariant 1 — Read Range（必要条件）**

$$\forall \rho \in P,\; Read_\rho(ARR, idx) \Rightarrow idx < Val_\rho(SZ)$$

（pattern 2/3 分别用 sum 与 `C - SZ` 替换右端。）直觉：read 代表程序员要读「已提交」的有效元素，索引必受逻辑 size 约束。

**Invariant 2 — Write Range（可选，收紧假阳性）**

$$\forall \rho \in P,\; Write_\rho(ARR, idx) \Rightarrow idx \leq Val_\rho(SZ) + c$$

默认 `c=0`；承认 insert 时 write 可触及 `size` 位置。

**三步 inference workflow**（Figure 2）：

1. **LLVM bitcode + SRA**：识别 struct member 等数组指针 `ptr`；对 Extended SSA 上每个访问索引计算符号区间 `[l, r]`（φ 取并、σ 取与条件交）。Listing 1 的 loop 示例见 Figure 3。
2. **候选对生成**：`{ptr} × {int}`，其中 `int` 仅取出现在 `ptr` 符号范围中的整型变量。
3. **SMT 验证**：对每个候选对，把 invariant 编码为 Z3 约束（read 用 `[[idx]]↑ < int_ν`，write 用 `≤`）；对 invariant 取否定求 **UNSAT**，成功则输出 `ATOMICITY(ptr, int)`。多个 SSA 形式用析取处理，避免手工对齐赋值点。

与 MUVI access-together-times 对比：insert 访问数组 `size-p+1` 次、size 仅 1 次，频率启发式失效；range invariant 直接刻画语义约束。

深度实现与公式见 [[atc2025-zhang-yunmo]]。

## 设计取舍

- **取舍 1**：静态 SRA + SMT vs 动态 trace（Daikon）。不等式 invariant 在动态分析中精度差、loop 下难扩展；静态方法 0.2–0.6 s 完成四程序分析，但依赖分析精度，undecidable 索引直接放弃。
- **取舍 2：Read invariant 为主、Write invariant 为辅**——准确反映 insert 中间态语义，牺牲对「只写不读」关系的覆盖；可选 write invariant 需用户假设每次扩展幅度。
- **取舍 3**：Complement 而非替代 Witcher/Huang。专注 counting 模式，不处理 guardian ordering；实际部署应组合多种 property inference。
- **取舍 4：Likely property + 手工确认 vs 端到端 automated testing**——快速产出 candidate properties 并 demonstrated utility（14 bugs），但 violation confirmation 未自动化，工程落地仍需人工或二次集成。
- **边界条件**：C 程序 + LLVM IR；pattern 2/3 需用户指定 N、C；临时 loop 变量可能被误判为 size（论文承认 false positive，建议后处理过滤 DRAM 变量）。

## 实验与结果

- 相比 MUVI/Witcher，在 4 个 PM data-structure benchmark 的 CPU 上，SRA+SMT inference 为 0.2–0.6 s，并发现 14 个 violation；该结果不含 end-to-end crash testing（§4.2，Table 3）。

- **Benchmark**：P-ART、P-BwTree（Recipe 持久索引）、CCEH、Level-Hashing（Table 2），均为流行 PM 数据结构。
- **Bug 发现**：共 **14** 个 atomicity violation，**11** 个新 bug、3 个已被 [[Witcher]] 报告（Table 3）。影响包括 fault/data loss、stale pointer read、memory corruption。
- **Bug 类型**：4 个为 array vs **allocation size**；其余为 array vs **logical size**。场景涵盖 radix tree children 数组、bloom filter value 数组、hash table resize 等。
- **对比**：MUVI 识别 **4/14**（对称高频访问时有效）；Witcher 识别 **3/14**（仅当数组元素指针充当 guardian 时，如 bug #2、#6、#13）。
- **Case study**：CCEH bug #9（`dir->_` 与 `dir->capacity`）——本文与 MUVI 可检，Witcher 失败（数组非 guardian）；Figure 4 展示 read/write 范围如何支撑推断。
- **性能**：property inference **0.2–0.6 秒/程序**；Witcher 需 **11 分钟–1 小时**。作者指出大规模 PM 系统上 SMT 可能成为瓶颈，建议限制同 basic block SSA、constraint caching 等优化。
- **False positive**：临时 loop 变量与 logical size 行为相似导致误报；可通过检查变量是否在 PM 地址空间等 **manual post-processing** 过滤。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| SRA+SMT inference 找到 atomicity violation | 14 total、11 previously unknown（§4.2，Table 3） | P-ART、P-BwTree、CCEH、Level-Hashing pinned version；人工检查 transaction protection | medium |
| 该 counting class 覆盖 evaluated baseline 漏检案例 | MUVI 找到 4、Witcher 找到 3（§4.2，Table 3） | 四个 PM data structure；Huang pattern 不在所选 array/int pair 中，未定量比较 | medium |
| property inference 的静态运行时间很短 | 每个 benchmark 为 0.2–0.6 s（§4.2） | 2×Xeon Gold 5317、128 GB DRAM、512 GB Optane；非 end-to-end crash testing | high |
| violation 涵盖 logical/allocation size correlation | 4 allocation-size、其余 10 logical-size，报告有 fault/data loss/stale pointer/memory corruption（§4.2，Table 3） | 仅四个 selected PM structure 的人工分类 | medium |
| 方法仍需人工审计确认属性 | 每个 inferred property 人工检查 TX_BEGIN/TX_END；trace checking 留作 future work（§4.1） | 依赖 libpmemobj-like transaction semantic；无 precision/recall 测量 | high |

## 批判性分析

### 论证链条

主链条清晰：**counting correlation 普遍存在 → dependency 模式无法刻画 → 用 access range invariant 刻画程序员意图 → SRA 提取范围 → SMT 证明 → 生成 likely atomicity property → 手工验证 TX 保护缺失 → 发现真实 bug**。P-ART `children`/`childrenCount` 例子有效说明 observation 与 design 的对应关系。

薄弱环节在 **result → claim** 的最后一跳：14 个 bug 证明 inference **能产出有用 properties**，但未证明集成后能在 **无人值守测试** 中达到相同 recall/precision。论文把 automated property checking 标为 future work，因此「testing tool」叙事强于当前交付物——当前更像 **static property inferencer + manual audit**。

### 假设压力测试

- **SRA 精度**：复杂指针别名、函数间摘要缺失、宏与内联边界可能使范围过宽（漏检）或过窄（误报）。四个开源 PM 结构相对规整，外推到百万行 storage stack（btrfs、ext4 全量）时 SMT 约束数量与 solver 时间是否可控，论文仅定性讨论。
- **C/LLVM 限定**：现代 PM 代码亦含 C++ 模板、自定义 allocator、JIT 路径；LLVM pass 对「数组 vs 普通指针」的区分在高级抽象下可能失效。
- **TX 语义多样性**：验证假设 libpmemobj 式 `TX_BEGIN`/`TX_END` 即充分保护；若使用细粒度 persistency model（[[Intel-x86-persistency]]）、手写 fence 序列或第三方 TX 库，手工确认规则需重写。
- **Multiple size variables**：allocated size vs logical size 并存时，MUVI 亦困难；本文通过 range invariant 可区分部分 case（bug #10–#14 为 allocation size），但用户需理解两种 size 语义，否则可能选错候选对。

### 实验可信度

**优点**：选的四个 benchmark 代表 PM 索引与 hashing 主流设计；与 Witcher、MUVI 做 **逐 bug 对照** 而非仅报总数；给出具体文件行号与影响分类；分析时间数量级差异有说服力。

**不足**：
- Baseline 公平性：Witcher/MUVI 原设计目标含 ordering + 其他 atomicity，并非专为 counting 优化；对比说明 complementary value，但不能解读为全面 superiority。
- 无 precision/recall 形式化指标：false positive 靠人工 inspection 定性描述，缺系统 FP/FN 统计。
- Bug confirmation 非自动化：未展示 inferred property 输入 trace-based checker 后的端到端检出率。
- 规模单一：无 Linux FS、PMDK 全库、企业 PM database 级评估。

### 系统性缺陷

- **可运维性**：论文未讨论 CI 集成、property 变更时的 regression、或与现有 [[Pmtest]]/AGAMOTTO 类工具的接口。Inferencer 输出 likely properties，开发者仍需理解 invariant 含义才能 trust。
- **尾延迟 / 运行时开销**：纯静态分析，无在线开销；但若未来做 dynamic validation，PM write 成本使 exhaustive crash injection 仍昂贵——论文未讨论。
- **正确性保证**：SMT 证明的是 **invariant 在 SRA 抽象下恒真**，不是 PM 硬件模型下的完全正确性；persistency ordering 与 atomicity 是不同维度，本文不处理 ordering bug。
- **可观测性**：论文未讨论如何向开发者解释「为何推断 ATOMICITY(ptr, int)」——缺 counterexample 或 access path 可视化会降低修复效率。

## 局限与后续工作

- **局限 1**：False positive 来自 loop 临时变量等，需 manual post-processing；论文未给出自动过滤规则或 learning-based ranking。
- **局限 2**：SMT solver 在大规模程序上可能成为瓶颈；仅提出 block-local SSA 限制与 caching 方向，无实测数据。
- **局限 3**：Evaluation 止于 property inference + 手工 violation 确认，未集成 Huang et al. 式 trace analysis 形成 closed-loop tester。
- **局限 4**：Pattern 2/3（累计 size、补 size）需用户提供 N、C；自动化程度低于 pattern 1。
- **Future work 1**：将 inferred properties 接入现有 PM property checker，在相同 benchmark 上测量 **端到端** bug detection rate 与 false positive rate，并与 Witcher 组合评估 coverage union。
- **Future work 2**：对 Linux FS（btrfs/ext4 counting bug 已有先例）做规模化 case study，量化 SRA+SMT 时间与 solver 失败模式，验证「0.6s」是否可扩展到万行模块。
- **Future work 3**：为误报的 loop 变量设计 **PM-aware def-use filter**（区分 DRAM scratch vs PM-resident metadata），目标是将 manual post-processing 自动化并可测量 precision 提升。

## 相关

- **相关概念**：[[Persistent-Memory]]、[[Crash-Consistency]]、[[Symbolic-Range-Analysis]]、[[SMT]]、[[Atomicity]]、[[Intel-x86-persistency]]
- **同类系统 / 工具**：[[Witcher]]、Huang et al. (ASE'24)、[[Pmtest]]、MUVI、AGAMOTTO、Mumak、P-ART、P-BwTree、CCEH、Level-Hashing、[[PMDK]]
- **同会议**：[[ATC-2025]]
- **源材料**：[[atc2025-zhang-yunmo]]、[[atc2025-zhang-yunmo.pdf]]
