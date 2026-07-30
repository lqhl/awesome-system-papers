---
type: paper
name: CAFault
full_title: "CAFault: Enhance Fault Injection Technique in Practical Distributed Systems via Abundant Fault-Dependent Configurations"
authors: [Yuanliang Chen, Fuchen Ma, Yuanhang Zhou, Zhen Yan, Yu Jiang]
venue: ATC
year: 2025
tags: [fault-injection, distributed-systems, configuration-testing, fuzzing, reliability]
source_pdf: "[[atc2025-chen-yuanliang.pdf]]"
source_md: "[[atc2025-chen-yuanliang]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-30
---

# CAFault：通过丰富的故障相关配置增强实际分布式系统中的故障注入技术（ATC 2025）

> **原题**：CAFault: Enhance Fault Injection Technique in Practical Distributed Systems via Abundant Fault-Dependent Configurations

> **一句话总结**：CAFault 的关键判断是 fault handling bug 往往由「非默认配置 + 特定 fault sequence」共同触发，所以它先用 runtime coverage 学出 configuration 与 fault 的隐式依赖，再只用 fault-handling code coverage 引导 fuzzing；在 HDFS、MySQL-Cluster、ZooKeeper、IPFS 上 48 小时找到 16 个未知 bug，比 CrashFuzz、Mallory、Chronos 多覆盖 31.5%、29.3%、81.5% 的 fault-tolerance logic。

## 问题与动机

现有 [[Fault-Injection]] 工具通常把系统配置固定在默认值上，然后搜索故障注入的位置、时间和序列。论文认为这会漏掉一类重要 bug：分布式系统的 fault tolerance logic 本身常由配置项控制，例如 replication degree、heartbeat interval、consensus mode、recovery trigger、storage type policy 等。默认配置只覆盖一小块执行路径，而真实部署中配置会因 workload、可靠性目标和资源预算而变化。

直接把配置空间和故障空间相乘不可行。论文把配置输入空间记为 M，把 fault injection 的时间、位置、序列长度等空间记为 N，朴素枚举会变成 M * N。更麻烦的是，配置项与 fault handling logic 的关系常是隐式的：一个配置项不一定直接出现在故障处理函数里，却可能通过 load balancer、heartbeat、recovery thread 或 consensus mode 改变故障路径。

CAFault 的目标不是替代已有故障注入工具，而是给它们补上 configuration awareness。核心问题可以压成两句：哪些配置值得在 fault injection 中探索？在某个配置下，哪些 fault sequence 更可能进入真正的 fault-handling deep path？

论文用 HDFS-17098 做动机例子：只有在 `dfs.datanode.balance.start=true` 和 `namenode.read.considerStorageType=true` 等配置组合下，DataNode heartbeat failure、load balancing、node restart 与 storage type 初始化时序交叠，才会触发 `Comparator.comparing` 不处理 null storage type 的 NameNode crash。这个例子支撑了论文的主张：配置改变的不是普通 workload path，而是故障恢复路径的可达性。

## 关键观察 / 隐含假设

- **观察 1**：大量 fault handling bug 不是默认配置可触发的 bug。论文实验中 16 个新 bug 里有 11 个需要特定 configuration item setting；默认配置下运行的 CrashFuzz、Mallory、Chronos 分别只找到 3、4、1 个。
  - **依赖假设**：目标系统暴露的配置项中，有足够多配置项真实影响 fault tolerance mechanism，而不是只影响日志、路径、资源上限等非故障逻辑。
  - **可能失效场景**：如果 production 部署高度标准化、默认配置已经覆盖主要 fault path，或者系统把 fault tolerance policy 固化在代码而非配置里，CAFault 的 configuration exploration 收益会变小。
  - **证据强度**：强。论文给出 4 个真实系统、16 个 bug 的触发条件和 baseline 对比；但这些系统都属于配置丰富的 distributed systems，外推到配置较少的服务需要谨慎。

- **观察 2**：configuration-fault dependency 可以用 runtime coverage 差异近似学习。CAFault 在相同 fault 输入下比较配置 `c` 与变异配置 `c'` 的 fault-handling coverage；若 coverage 不同，就把变异过的配置项视为候选依赖，再用 binary search-based minimization 缩小依赖项集合。
  - **依赖假设**：coverage difference 是 fault relevance 的足够好代理；运行噪声、异步调度和 nondeterminism 不会频繁制造虚假差异；单个 fault 输入能暴露主要配置依赖。
  - **可能失效场景**：论文自己在 historical bugs 实验中承认，某些配置项只有在特定 multi-fault combination 下才影响 fault handling，CAFault 的第一阶段可能学不到这种依赖。10 个历史 bug 中漏掉的 1 个就属于这种复杂依赖。
  - **证据强度**：中到强。FDModel ablation 显示比随机配置生成多找到 128.5% bug、多覆盖 29.19% fault-handling code；但模型准确率没有用完整 precision/recall 形式报告，主要通过测试效果间接证明。

- **观察 3**：普通 code coverage 不是 fault injection 的好反馈信号。fault injection 很容易跑进和 fault tolerance 无关的代码路径，导致 fuzz budget 被普通业务逻辑吸走。
  - **依赖假设**：异常处理块及其 call trace 可以近似代表 fault-handling logic；Java 的 `try/catch/finally`、C++ 的 `try/catch/throw`、Go 的 `defer/panic/recover` 足以覆盖主要恢复逻辑。
  - **可能失效场景**：如果系统的 fault handling 是显式状态机、error-code propagation、actor message loop、background reconciler 或配置驱动 policy，而不是异常路径，静态识别出的 fault-handling code set 可能漏掉关键逻辑。
  - **证据强度**：中。CAFault 相比随机 fault injection 和普通 coverage-guided fuzzing 分别多检测 77.8% 和 33.3% bug，多覆盖 18.04% 和 11.46% fault-handling code；但 fault-handling code identifier 的 recall 没有独立评估。

- **假设 1**：48 小时测试窗口和 20-node Docker cluster 足以代表这些工具的相对效率。
  - **证据强度**：中。论文说多数工具在 10 小时后 coverage 基本收敛，CAFault 在约 8 小时后超过 baseline；但所有容器在单台 128-core 机器上运行，网络和故障模型仍是实验环境，不等价于真实跨机房或云平台故障。

## 核心方法

CAFault 是一个两阶段交替框架：先构建 FDModel，再在当前高质量配置下做 fault-handling guided fuzzing。它把已有 fault injection 工具遗漏的维度显式拆开：Configuration Generator 负责找 fault-dependent configurations，Fault Injector 负责在这些配置下搜索 fault sequences，Interaction Adaptor 负责配置格式转换、workload loading 和 anomaly detection。

第一阶段是 **Implicit Dependency Construction**。CAFault 从 Configuration Input Set 中取配置 `c`，变异生成 `c'`，让 Distributed System Under Test 分别加载两份配置，并遍历 Fault Input Set 中的 delay、crash、restart、packet loss 等 fault operation。对于每个 fault，它收集 runtime coverage。如果 `c` 与 `c'` 在同一 fault 下产生不同 fault-handling coverage，CAFault 就认为被变异的配置项可能与该 fault 有隐式依赖。

FDModel 的最小化是这一步的关键简单化。由于一次 mutation 可能改了多个配置项，CAFault 用 binary search-based minimization 递归测试配置项子集：如果只保留某个子集的变异后 coverage 不再变化，就认为这些项不是必要依赖；如果仍能触发 coverage difference，就保留并继续拆分。这个算法没有试图恢复精确 data-flow，只用「覆盖是否变化」来保留有用配置项，符合论文想要的 practical testing 框架。

配置 mutation 按类型处理：boolean 取反，enum 随机选可用值，numeric 在合法范围内加减，time string 按语义生成，IP address 和 file path 这类容易破坏拓扑或启动条件的字符串会跳过。这个设计让 CAFault 更像 guided configuration fuzzing，而不是无约束地破坏配置文件。

第二阶段是 **Fault-Handling Guided Fuzzing**。CAFault 先静态识别 fault tolerance logic：Java 中扫描 `try/catch/finally`，C++ 中扫描 `try/catch/throw`，Go 中扫描 `defer/panic/recover`，再沿 call trace 扩展成 fault-handling code set。运行 fuzzing 时，它只计算这部分代码的 coverage，把进入新 fault-handling coverage 或发现新 bug 的 fault sequence 放回 seed pool。

FDModel 还会反过来约束 fault candidate set。给定当前配置 `c'`，CAFault 从 FDModel 中选择与该配置相关的 fault operations，过滤已有 fSeq pool 中包含无关 fault 的序列，再进行 mutation。这里的 feedback 是 sequence-level 的：CAFault 不要求精确归因到序列里的某个 fault，只判断整条 fault sequence 是否带来新 fault-handling coverage 或新 anomaly。

实现上，CAFault 对四个系统做了适配：HDFS 与 ZooKeeper 是 Java，用 JaCoCo 收 coverage；MySQL-Cluster 是 C++，用 gcov；IPFS 是 Go，用 gtest。workload 分别来自 HiBench、SQLancer、JMeter 和 ipfs-benchmark。bug detector 复用了已有工具：CrashFuzz 的 crash recovery detector、Chronos 的 timeout monitor、Mallory 的 AddressSanitizer/log checker/consistency checker。

## 设计取舍

- **动态依赖学习换准确性**：FDModel 避免纯静态 reachability 的大量 false positive。论文报告静态 AST reachability 预建依赖有约 67% false positive，主要因为分布式系统大量 multithreading 和 asynchronous execution 难以静态判断。但动态学习需要真的启动集群、加载配置、注入 fault、清理状态，初期 coverage 增长慢。
- **coverage 代理换通用性**：CAFault 不需要理解每个系统的语义，也不要求开发者手写 configuration-fault dependency model。代价是 coverage difference 只能说明执行变化，不能保证变化来自语义上有意义的 fault tolerance behavior。
- **异常处理识别换低人工成本**：用 exception-handling code 和 call trace 自动标记 fault-handling code，工程上简单、跨语言可做。代价是依赖语言风格；error-code 风格、event-driven recovery 和 background reconciliation 可能被低估。
- **sequence-level feedback 换实现简单**：CAFault 不归因单个 fault 对 coverage 的贡献，避免复杂 blame assignment。代价是 seed pool 可能保留较长、含冗余 fault 的序列，后续 minimization 或 replay 成本会变高。
- **适配接口保留人工边界**：论文说迁移到新系统只需实现 `config.format()`、`Workloading()`、`statusMonitor()` 三类接口。这个接口面不大，但仍要求对目标系统的 workload、配置格式和 anomaly oracle 有工程理解。

## 实验与结果

- **实验对象**：HDFS 3.4.1、MySQL-Cluster 8.4、ZooKeeper 3.9、IPFS 0.33。每个系统运行在 20 个 Docker virtual nodes 上，容器配置为 2.25 GHz 6-core CPU、16 GB RAM、480 GB SATA SSD，10 Gbps network；所有容器在一台 128-core AMD EPYC 7742、512 GB memory 的物理机上。
- **bug detection**：CAFault 在 48 小时内找到 16 个未知 fault handling bugs：HDFS 3 个、MySQL-Cluster 6 个、ZooKeeper 4 个、IPFS 3 个。论文称全部已被对应 vendor confirmed and fixed。
- **baseline 对比**：CrashFuzz、Mallory、Chronos 分别找到 3、4、1 个 bug。用 CAFault 的 FDModel 增强后，CrashFuzz+、Mallory+、Chronos+ 分别找到 9、12、5 个；仍漏掉 #1、#4、#10 这类还需要 deep multi-fault interaction 的 bug。
- **bug 类型**：16 个 bug 中，8 个会导致 server node crash 且无法自动恢复，3 个涉及 data synchronization 导致 inconsistency 或 data loss，5 个导致服务 hang。11/16 需要非默认配置，5/16 是默认配置也能触发。
- **fault-handling coverage**：CAFault 在 HDFS、MySQL-Cluster、ZooKeeper、IPFS 上的 fault-handling code coverage 分别为 13684、19162、6254、3097。相对 CrashFuzz、Mallory、Chronos 平均多覆盖 31.5%、29.3%、81.5% fault tolerance logic。
- **FDModel ablation**：关闭 FDModel、随机生成配置的 CAFault- 只找到 7 个 bug；CAFault 找到 16 个。四个系统合计多覆盖 9480 个 fault-handling code，论文汇总为 +29.19%。
- **fault-handling feedback ablation**：随机 fault injection 版本 `CAFault_r` 找到 9 个 bug，传统 code coverage-guided 版本 `CAFault_c` 找到 12 个，完整 CAFault 找到 16 个。完整版本相比分别多覆盖 18.04% 和 11.46% fault-handling code。
- **accuracy sanity check**：在 10 个历史非默认配置 bug 上，CAFault 复现 9 个；漏掉的 1 个需要特定多故障组合才能体现配置依赖，暴露了 FDModel 当前只用单 fault 依赖学习的 blind spot。

## 批判性分析

### 论证链条

论文的链条基本闭合：动机例子说明配置会改变故障路径；FDModel ablation 说明 configuration awareness 本身有效；fault-handling feedback ablation 说明只靠普通 coverage 不够；baseline+FDModel 仍漏掉 3 个 deep-path bug，进一步支撑第二阶段 fuzzing 的必要性。

最强的证据不是单一 coverage 数字，而是分层对比：原 baseline、baseline+FDModel、CAFault-、CAFault_c、完整 CAFault 都出现了。这让论文能区分「配置探索」与「fault sequence 搜索」两个贡献，而不是只展示一个端到端工具更强。

但它也有一个典型 testing paper 的外推跳步：fault-handling code coverage 被当作 fault tolerance logic coverage，再进一步被用作 bug-finding capability 的代理。这个代理在四个系统上和 bug 数量同向，但论文没有证明更多 fault-handling coverage 一定更接近 production resilience，也没有给出 coverage set 的 manual validation。

### 假设压力测试

CAFault 对「配置丰富、恢复逻辑由配置影响、故障路径通过异常/恢复代码表达」的系统非常自然。HDFS、ZooKeeper、MySQL-Cluster、IPFS 都符合这个画像：长生命周期服务、复杂配置、节点 failure/restart/reconnect、consensus 或 replication 机制。

压力来自三类场景。第一，fault handling 不走异常机制，而是由状态机或 control-plane reconciler 表达时，Fault Tolerance Logic Identifier 可能漏掉真正重要的 recovery path。第二，配置项只有在多故障组合下才产生行为差异时，FDModel 的单 fault 学习阶段可能不会把它纳入候选依赖。第三，真实 production 的 fault 相关配置未必能随意 mutation；某些配置组合虽然合法但不代表有意义部署，会把测试预算花在低概率状态。

论文的 attacker discussion 也略快。它说某些 bug 可被攻击者通过特定 fault operations 触发，造成节点 crash、hang、data loss。但实验主要是可靠性 testing，不是威胁模型分析；攻击者是否能控制对应 fault timing、配置前提和集群状态，需要另行证明。

### 实验可信度

baseline 选择合理：CrashFuzz 代表 code coverage-guided fault injection，Mallory 代表 distributed system greybox fuzzing，Chronos 代表 timeout/deep-priority fuzzing。更重要的是，论文还做了 CrashFuzz+、Mallory+、Chronos+，显示 FDModel 可作为增强层，而不是只对自家 fuzzer 有利。

仍有两个公平性细节需要记住。第一，baseline+FDModel 使用的是 CAFault 生成的 fault-dependent configurations，这证明 FDModel 对已有工具有帮助，但它不是一个完全独立 baseline。第二，所有工具的 detectors 来自已有工具组合，CAFault 能找到所有 bug 可能部分受益于 detector union；论文强调的是 fault sequence/config exploration，但 detector coverage 本身也是端到端 bug 数的重要变量。

workload 的代表性中等：HiBench、SQLancer、JMeter、ipfs-benchmark 都是合理公开 benchmark，但不是 production trace。测试拓扑是 20 Docker nodes on one physical machine，适合 controlled comparison，却弱化了真实网络、磁盘、跨机 failure domain、cloud noisy neighbor 等变量。

### 系统性缺陷

CAFault 最大的工程成本是运行时依赖学习。每个 candidate configuration 都要加载系统、跑 workload、注入 fault、收 coverage，这解释了 Figure 9 中前约 8 小时 CAFault coverage 低于 baseline。对 CI 或 nightly testing 来说，48 小时窗口可能能接受；对开发者本地迭代来说偏重。

第二个风险是状态污染与 replay。论文说记录 fault type、timing、code location，并多次重放以降低 nondeterminism；但分布式系统的状态清理、外部资源、后台线程、日志和数据目录残留都可能影响 replay。note 中不能把「可复现」理解成确定性 replay，只能理解成工程上尽量稳定。

第三个风险是 oracle 限制。CAFault 当前覆盖 crash recovery、timeout、memory vulnerability、log checker、consistency checker 等，但 fail-slow、load imbalance、性能退化、资源泄漏等 bug 的 oracle 更难定义。论文在 Discussion 中也承认 load imbalance 这类 bug 的判定容易 false positive。

## 局限与后续工作

- **局限 1**：FDModel 当前主要从单 fault 输入下的 coverage difference 学依赖，容易漏掉只在 multi-fault combination 中显现的 configuration-fault dependency。历史 bug 复现实验中漏掉 1/10，正是这种情况。
- **局限 2**：动态 learning 有明显时间成本。CAFault 初期要构建 FDModel，前几个小时 coverage 增长慢；如果测试预算很短，baseline 可能更快进入浅层 fault path。
- **局限 3**：fault-handling logic identifier 基于异常处理和 call trace，无法保证覆盖所有 fault tolerance mechanism。事件循环、显式错误码、reconciler、lease/heartbeat state machine 都可能需要更专门的识别方式。
- **局限 4**：实验 workload 是公开 benchmark，不是 production trace。论文证明了工具在 controlled setting 中能找到真实 bug，但没有证明 bug distribution、configuration distribution 和 fault timing 与生产环境一致。
- **Future work 1**：把 FDModel 扩展为 multi-fault dependency model，客观指标可以是 historical non-default multi-fault bugs 的 recall 从 9/10 提升到 10/10，并报告 dependency precision/recall。
- **Future work 2**：用静态 analysis 或 SMT solver 生成初始 dependency candidates，再用动态 coverage refinement 剪掉 false positive。可验证指标是达到同等 coverage/bug 数所需测试时间，而不是只报告模型构建速度。
- **Future work 3**：为 fail-slow、load imbalance、resource leak 等非 crash/hang/inconsistency bug 设计 oracle，并测量 false positive rate。论文已经指出 load imbalance 的定量 oracle 是难点。
- **Future work 4**：引入 production-like configuration distribution 和 fault trace，对「高质量配置」做优先级排序：不是只看 unique fault-handling coverage，也看该配置在真实部署中出现的概率或风险权重。

## 相关

- **相关概念**：[[Fault-Injection]]、[[Configuration-Testing]]、[[Coverage-Guided-Fuzzing]]、[[Static-Analysis]]、[[Distributed-Systems]]
- **同类系统**：[[CrashFuzz]]、[[Mallory]]、[[Chronos]]、[[Jepsen]]、[[ChaosMonkey]]
- **相关机制**：[[Consensus]]、[[Replication]]、[[Checkpointing]]、[[Crash-Recovery]]
- **同会议**：[[ATC-2025]]
