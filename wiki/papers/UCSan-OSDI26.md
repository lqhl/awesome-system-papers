---
type: paper
name: UCSan
full_title: "A Compilation-based Under-Constrained Execution Engine"
authors: [Mingjun Yin, Zhaorui Li, Ju Chen, Haochen Zeng, Chengyu Song]
venue: OSDI
year: 2026
tags: [program-analysis, under-constrained-execution, concolic-execution, compiler, memory-safety]
source_pdf: "[[osdi26-yin.pdf]]"
source_md: "[[osdi26-yin]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# UCSan：基于编译的欠约束执行引擎（OSDI 2026）

> **原题**：A Compilation-based Under-Constrained Execution Engine

> **一句话总结**：UCSan 不先启动整个程序，而是把用户指定的一组 C/C++ 函数直接编译成可运行的用户态程序；遇到尚未初始化的指针时，再用伪指针、影子元数据和即时初始化补出对象。它把欠约束执行从 KLEE、Angr 一类解释器中拆出来，因此能接到 fuzzing、concolic execution 等动态分析上；代价是结果高度依赖分析范围和外部函数模型，且当前不支持循环数据结构、并发或多次入口调用。

## 问题与动机

动态测试只有在测试入口能到达缺陷时才有效。大型系统中的内部函数往往没有现成 harness；内核、文件系统和驱动还需要 VM、磁盘镜像或设备模拟器。手工抽出模块并补齐初始化代码虽然可行，但工作量大，而且上游代码变化后很难维护（§1）。

静态分析能扫完整代码，却常为可扩展性牺牲精度。论文引用 UBITect 原研究的数据：它产生 147,643 条 use-before-initialization（UBI）报警，最终只有 52 条被确认或修复；本论文后续性能实验使用的是其中另一份含 103,351 条报警的 Linux 4.14 列表（§1、§5.3）。欠约束执行（under-constrained execution）走中间路线：从任意内部函数开始，第一次访问缺失对象时才惰性补齐，并把范围外调用替换为模型。问题是 UC-KLEE、Angr 等已有引擎靠解释执行；论文引用的已有测量中，KLEE 约比原生慢 3,000 倍，Angr 超过 321,000 倍（§1）。

UCSan 的目标不是再造一个更快的符号执行器，而是把“如何让任意代码子集能够运行”做成独立的编译期与运行时层。这样，同一份自包含二进制既可直接做具体执行，也可再接入 concolic execution、fuzzing 或 model checking（§1–§2.1）。

## 关键观察 / 隐含假设

- **观察 1：真正缺失的是对象和外部环境，不是目标函数本身。** 全局对象和栈对象可由正常编译工具链处理；从内部函数起跑时，最难的是尚未分配的堆对象、对象间别名，以及范围外函数的副作用。UCSan 因此保留原构建系统和 LLVM IR，只补这两个缺口（§1、§2.1）。
  - **依赖假设**：目标项目能产出 LLVM IR，并且所有会访问欠约束对象的代码都经过 UCSan 插桩。未处理的 inline assembly、外部库或绕过插桩的指针访问会打破这个前提。
- **观察 2：真实地址只需在解引用的一瞬间存在。** 程序内部一直携带伪指针（pseudo-pointer）；`Load`、`Store` 等指令马上访问内存前，`check_ptr` 才把逻辑偏移翻译为真实地址。真实地址不进入后续数据流，所以对象扩大并重新分配后，不会留下旧真实地址（§3.1–§3.2）。
  - **依赖假设**：编译器能拦住全部相关 pointer operation。UCSan 覆盖 `Load`、`Store`、`AtomicRMW`、`GEP`、`BitCast`、`memcpy` 等 LLVM 指令或 intrinsic；复杂汇编仍需专门 wrapper。
- **观察 3：指针别名可由影子数据流恢复。** 基于 DataFlowSanitizer 的 shadow pointer 记录逻辑基址、point-to object 和 point-by origin；多个伪指针若指向同一 object ID，翻译后也会访问同一对象（§3.1–§3.3）。
  - **失效边界**：动态对象在 seed 中靠“从 root 开始的解引用链”识别，当前无法表示循环链表等 cyclic data structure。
- **观察 4：欠约束执行与路径探索可以分层。** UCSan 本体只负责把局部代码变成可执行程序；论文把它与 SymSan 和 Thoroupy companion 组合成 UCSan†，后者才负责收集 symbolic trace、解约束和广度优先探索（§2.1、§4）。
  - **阅读结果时必须区分**：Linux UBI 报警和 CVE 复现的主要数字来自 UCSan†，不能把它们都归因于独立 UCSan runtime。
- **观察 5：分析范围是精度与规模的显式旋钮。** 小范围执行快，但可能漏掉真实入口施加的约束；大范围上下文更完整，却重新遇到 path explosion。论文用静态分析、人工迭代或 coding agent 生成 scope，没有自动解决这个取舍（§3.4、§5.4）。
- **假设 1：范围外函数可以由少量策略近似。** 默认 `Assume Pure` 忽略副作用；`Assume Arbitrary Changes` 可重新分配全部 pointer arguments；特殊函数用 wrapper 或 replacement，例如 `kmalloc` 映射到 `malloc`。字符串、文件 I/O 等模型不完整时会制造错误输入或漏掉路径（§3.1、§6）。

## 核心方法

### 从 LLVM IR 生成自包含程序

输入包括目标程序的 LLVM IR 和 YAML 配置。配置指定入口函数、分析范围、需纳入的 IR 文件，以及范围外函数的处理方式。UCSan 删除原 `main`，生成新的入口 wrapper；它从 seed 的 super object 读取参数，没有值时填零，然后调用目标函数。范围外函数会被删除并替换成 stub、wrapper 或指定实现。UCSan pass 之后还可串接其他 LLVM pass，最终由 Clang 将目标代码和各 runtime 链接为普通用户态 executable（§2.1、图 1–2）。

这不是“完全不用配置”。UBITect 实验从静态分析报警中提取 scope；Linux 5.10/6.16 兼容性实验用简单 call graph 纳入同一 module 的函数；漏洞复现既有人工 scope，也有 coding agent 根据 NVD 条目猜入口和 root-cause chain（§2.1、§5.3–§5.4）。

### 伪指针、影子指针与即时初始化

每次 pointer operation 前插入的 `check_ptr` 分四步工作（§3.2、图 6）：

1. 检查输入是普通真实指针、常量指针还是带 shadow 的伪指针；普通指针直接返回。
2. 用 shadow pointer 查 object table。若对象尚不存在，就按 pointer type、pointer arithmetic 或 `memcpy` 长度推测大小并分配；后来发现需要更大范围时透明地重新分配。
3. 按 point-by 元数据寻找 seed 中的对应对象；找到就反序列化内容，否则清零，并给对象内数据写入来源标签。
4. `GEP`、`BitCast` 只更新逻辑偏移；真正 `Load`、`Store` 时才计算 `object_base + current_offset - base_offset`，得到只供这次访问使用的真实指针。

Shadow pointer 同时沿函数参数、返回值和内存数据流传播。对象表保存 object ID、基址、大小、边界和释放状态，因此同一套元数据也能支持越界、释放后使用和未初始化使用检查（§3.1–§3.4）。

### 可重复执行的对象 seed

一份 seed 是若干序列化对象，每项包含 object ID、point-by、大小和内容。ID 0 的 super object 保存入口参数、全局变量和范围外函数返回值。其余动态对象不能依赖分配顺序，因此用来源元组 `<source_object_id, offset>` 串成解引用链：例如第二个链表节点由“第一个节点的 `next` 字段”定位（§3.3）。

这种表示让同一 seed 能恢复对象内容和别名关系，但只适合从 root 可达的非循环对象图。默认清零也不是现实环境的概率模型；它只是为具体执行提供确定起点，再由上层路径探索产生新 seed。

### 外部调用与内存安全检查

UCSan 为范围外函数提供三种语义：精确 custom wrapper/replacement、默认无副作用、或保守地让 pointer arguments 任意变化。`memcpy` 一类函数的 wrapper 还需同步 shadow memory。复杂 inline assembly 同样要人工或由 [[LLM|LLM]] 生成 wrapper（§3.1）。

内置 checker 检查 allocation-level OOB、UAF 和 UBI。OOB 不检测同一 struct 内从一个字段越到相邻字段的 type-level overflow；JITI 补出的对象被视为欠约束内容，不标为 UBI。checker 只保证“在给定 scope 的具体路径上确实发生了访问”，并不保证该路径能从真实程序入口到达（§3.4）。

### UCSan† 的 concolic 路径探索

UCSan pass 后再接 SymSan pass，二者使用分离的 shadow memory 区域。Python/C++ companion 把动态 symbolic trace 转成 Z3 约束，默认以 BFS 调度新 seed；伪指针约束按 64-bit bit-vector 求解。该层证明 UCSan 能承载动态分析，但 path explosion、全局 loop/recursion threshold 和 solver 成本依然存在（§4）。

## 设计取舍

- **编译执行换兼容性约束**：复用 LLVM 优化、ABI 和 sanitizer 基础设施，速度远高于解释器；代价是必须获得可插桩 IR，并为复杂 inline assembly 或特殊外部函数补模型。
- **访问时补对象换环境真实性**：无需启动完整内核或设备；补出的对象和零初始化可能落在真实系统永远不会出现的状态。
- **可自动扩容换 OOB 灵敏度**：JITI 发现尺寸估小后可重分配，能继续执行；但如果真正 allocation 位于 scope 外，这会把部分真实越界“扩没”。论文的若干 NVD 样例只有关闭 dynamic reallocation 才能复现（§5.4.2）。
- **较小 scope 换可扩展性**：减少 path explosion；缺少 allocation、deallocation、初始化或外部返回值约束时会漏报或误报。
- **外部函数默认 pure 换低建模成本**：多数无关调用可直接跳过；字符串、文件 I/O、状态机和设备操作的语义不能靠该默认值保持。
- **单入口、单线程换简单执行模型**：适合局部内存安全路径；不适合需要多次调用积累状态、并发交错、时序或真实设备事件的缺陷。

## 实验与结果

- **平台与比较对象**：主机为双 Intel Xeon Platinum 8168、755 GB 内存，Ubuntu 20.04.3、Linux 6.5；UCSan 使用 Clang/LLVM 12。原 UC-KLEE 仓库已不可用，作者改用 IncreLux 的 KLEE-based engine（KLEE-IL），两边均使用 Z3 4.8.15。这意味着结果比较的是当前替代实现，不是原 UC-KLEE（§5.1）。
- **执行速度与编译兼容性**：20 节点链表、不探索路径时，UCSan 用 9 秒，KLEE-IL 20 秒，Angr 79 秒；这说明相对解释器更快，也说明插桩与 JITI 离“原生速度”仍很远。nbench 中 UCSan 比 KLEE-IL 高数百到数千倍，例如 `STRING SORT` 为 41.993 对 0.01282 iterations/s；Angr 18 小时仍未完成一次迭代并最终 OOM（§5.2、表 1）。Linux 5.10.240 和 6.16.0 分别成功编译 14,503 个 scope（96.2%）和 139,509 个 scope（88.9%），失败主要来自未处理 inline assembly（§5.3）。
- **UBI 报警处理**：Linux 4.14 的 UBITect 任务使用 24 个并行实例，每项限 2 分钟、2 GB，并把编译/链接时间计入 TTF。UCSan† 可分析的 66,999 项中完成 63,957 项，即 95.46%；KLEE-IL 可分析 52,802 项，完成率 41.29%。表 2 给出的平均 TTF 是 14.37 秒和 105.71 秒，正文却称 UCSan† 快 6.36 倍；按表中显示值计算约为 7.36 倍。正文还把 0.32 秒/条与 5.14 秒/条称为 15.06 倍，按显示值计算约为 16.1 倍，因此应优先引用原始时间和完成率，而不是这两个有内部矛盾的倍数。UCSan† 多确认 111 项，其中至少 15 项后来在 git history 中被修复（§5.4.1、图 7、表 2–3）。
- **已知漏洞复现**：30 个手工选取的 NVD 漏洞中，UCSan† 复现了大多数，但 scope 也是人工从修复提交中迭代提取。AFGen 的 94 个 CVE 由 OpenAI Codex GPT-5.5 生成配置，69 个复现、25 个失败，失败多因循环/递归导致 path explosion；7 个 case 出现由外部函数缺失约束造成的 false positive。SyzSpec 的 38 个 kernel bugs 中复现 26 个；12 个未确认项主要受 scope 猜测、loop threshold 和一个不支持的并发缺陷影响，未确认项中还出现 8 个 false positive（§5.4.2、表 4–5）。
- **大 scope 压力测试与边界**：每个 module 跑 1 小时，`binder_ioctl` 的 2,027 个 basic blocks 覆盖 68.6%，但 7 个 null dereference 全是缺上下文造成的误报；`tcp_v4_do_rcv` 跨 26 文件、8,930 blocks，只覆盖 16.1%，单次入口调用无法建立其 stateful/re-entrant 状态；两个 ACPI scope 覆盖 49.36% 和 56.50%，各自报告的 null/OOB 也都是 `kmalloc(0)` 模型造成的误报（附录 §9.2）。

## 论断—证据表

| 论断 | 机制与证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 编译式欠约束执行明显快于解释式实现 | nbench 多项高数百至数千倍；UBI 平均处理速度 0.32 对 5.14 秒/条（表 1、表 3） | KLEE-IL 是替代基线；具体执行仍有很高插桩开销 | 强（所测任务内） |
| 方法能覆盖复杂 C/kernel 代码 | Linux 5.10/6.16 scope 编译成功率 96.2%/88.9%（§5.3） | 复杂 inline assembly 仍需 wrapper；不是代码行覆盖率 | 强（编译兼容性） |
| 更高吞吐能增加动态分析有效结果 | UBI 多完成 42,155 项、多确认 111 项，至少 15 项后来被修复（§5.4.1） | 只验证一个静态分析数据集，且“被修复”来自事后 git 检查 | 强（该数据集） |
| 不写传统 harness 也能复现多类漏洞 | AFGen 69/94、SyzSpec 26/38；另有 30 个手工 NVD case（§5.4.2） | 仍需 scope、entry、外部模型，部分由人工或 coding agent 生成 | 中到强 |
| 分析结果的准确性受上下文控制 | AFGen 有 7 个 false-positive cases；大型 module case 中多条报警均为误报（§5.4.2、附录 §9.2） | 论文没有系统报告所有成功任务的 precision/recall | 强（说明边界），弱（总体精度） |

## 批判性分析

### 论证链条

论文的因果链条很清楚：解释器慢，所以把“补对象、翻译指针、处理外部调用”下沉到 LLVM pass 和 runtime；真实地址不逃逸，使对象可在运行时扩大；再接 SymSan，验证这层加速能转化为更多完成任务和更多确认缺陷。nbench、Linux 编译率、UBI 和漏洞复现分别覆盖速度、兼容性和分析效果，不只报一个 microbenchmark。

但“无需 harness”容易被误读。传统 harness 的对象构造被 JITI 自动化了，入口、scope、函数模型和 checker 仍要提供；大数据集里这部分工作转交给静态分析或 coding agent，并没有消失。应把贡献理解为“把 harness 的内存搭建机械化”，而非全自动理解任意组件环境。

### 假设压力测试

如果漏洞需要外部函数精确返回值、设备状态、字符串/文件 I/O、多次入口调用或并发交错，默认 pure/zero-filled 环境会给出错误路径。把 scope 放大可补约束，却增加 solver 与 path explosion；把 scope 缩小能跑完，又更容易误报。动态 reallocation 也有两面性：开启会隐藏 scope 外 allocation 的真实 OOB，关闭则可能把单纯尺寸推断不足当成 OOB。当前没有通用自动规则决定何时切换。

伪指针不逃逸是实现正确性的核心不变量。未经插桩的汇编、外部库保存指针、特殊 ABI 或整数—指针技巧都可能泄漏伪指针或真实指针；论文只说明可写 wrapper，没有给出完整覆盖检查。循环对象、共享对象图和 stateful re-entry 也直接挑战 seed 的解引用链模型。

### 实验可信度

优点是硬件、版本、timeout、内存上限和并行度都写清楚，TTF 还把 UCSan 编译与 KLEE-IL 链接时间计入；作者公开了兼容性失败、AFGen false positives，以及三个大型 kernel module 的负面结果。至少 15 个后来修复的 UBI 提供了比单纯报警数量更强的真实性证据。

不足是原 UC-KLEE 不可用，只能比较 KLEE-IL；30 个 NVD case 的选择和 scope 都由作者人工完成，存在 selection/oracle advantage；94 个 AFGen 与 SyzSpec 配置依赖特定 coding agent，配置质量与复现实验绑在一起。论文没有统一给出 bug-level precision、recall、重复运行方差、solver time 分布或人工审查时间。9 秒跑 20 节点链表也表明 headline 的“编译式”不应等同于接近 native。

### 系统性缺陷

UCSan 把环境复杂度集中到 `check_ptr`、shadow metadata、scope 和外部模型中：任何漏插桩或模型错误会系统性影响整条分析链。每次 pointer operation 插桩也使 runtime 本身较重。当前 checker 只做 allocation-level OOB，无法发现 struct 内跨字段越界；JITI 对象不算 UBI；单线程、单入口和全局 loop/recursion threshold 限制了内核状态机与并发缺陷。

更根本地说，欠约束执行无法同时保证“局部、快”和“来自真实入口可达”。UCSan 提高了可跑规模，却没有消除这个语义张力。附录中 `binder_ioctl`、ACPI 的全部报警都是误报，`tcp_v4_do_rcv` 覆盖仅 16.1%，正好说明性能提升之后，scope inference 和环境建模成为新的主要瓶颈。

## 局限与后续工作

- 为字符串、文件 I/O、内核 allocator、设备接口和常见 inline assembly 建立带版本的模型库，并报告每类模型对 false positive/negative 的影响。
- 支持循环与共享对象图，明确同一对象经多条解引用链到达时的规范化身份和 seed 格式。
- 把单一全局 loop/recursion threshold 改成按函数、路径或目标自适应的预算，并与 directed exploration 联合评测。
- 增加多入口调用和可持久化状态，使 TCP、协议栈和 driver lifecycle 能跨事件探索；并发执行需单独定义 schedule、内存模型和 race checker。
- 对 scope 做可解释的自动扩展：当报警依赖范围外约束时，指出应加入的 allocation、caller 或 external function，而不只重新让 coding agent 猜测。
- 建立完整 precision/recall 数据集，记录 scope 生成时间、人工确认成本、重复运行方差和关闭 dynamic reallocation 后新增的真/假 OOB。

## 相关

- **方法**：欠约束执行、concolic execution、LLVM instrumentation、shadow memory
- **同会议**：[[OSDI-2026]]
