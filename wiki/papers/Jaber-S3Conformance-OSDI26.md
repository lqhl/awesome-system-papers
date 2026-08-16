---
type: paper
name: Jaber-S3Conformance
full_title: "High Fidelity Models for Large Scale Stateful Services (Operational Systems)"
authors: [Nouraldin Jaber, Dongyun Jin, Bernhard Kragl, Enrico Magnago, Gustavo Petri, Thorsten Tarrach, Serdar Tasiran]
venue: OSDI
year: 2026
tags: [model-based-testing, cloud-storage, api, formal-methods, operational-systems]
source_pdf: "[[osdi26-jaber.pdf]]"
source_md: "[[osdi26-jaber]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# 用高保真可执行模型守住 S3 API 行为（OSDI 2026）

> **原题**：High Fidelity Models for Large Scale Stateful Services (Operational Systems)

> **一句话总结**：AWS 把 S3 的可观察行为写成有状态的 Java 参考模型，再用谓词抽象把无限的请求和值域变成可计数的行为场景，由生成器自动准备状态、发请求并逐字段比对；这套方法已进入 S3 的开发和 CI/CD，论文表 3 的三个项目合计在上线前发现 372 个偏差，其中 46 个被人工定为高严重度。

## 问题与动机

Amazon S3 已运行 20 年，保存超过 500 万亿个对象，平均每秒处理超过 2 亿个请求，公开 API 有 96 个操作。数百名开发者持续增加功能、重构旧代码，同一个 API 还可能用不同语言、硬件和代码库重新实现，例如 2023 年上线的 S3 Express One Zone。实现可以完全不同，但客户看到的行为必须保持一致；论文把这个问题叫作 API sameness 或 conformance checking（API 一致性检查）。

这里的“行为一致”远不只是成功请求返回相同对象。客户代码会依赖错误码、header、边界值和检查顺序。GetObject 就有 21 个输入参数、36 个输出参数加 payload，还受 bucket 是否存在、版本、加密、权限和对象创建方式影响。论文的例子中，同一个 range 请求可能返回 206、404 或 416；对象是否由 multipart upload 创建、第一 part 是否正好 5,242,881 字节，又会改变 checksum header。If-Unmodified-Since 则可能返回 200 或 412，客户会据此决定是否继续处理（§1）。

直接把旧实现当作 oracle 也不可靠。API 可能允许多种正确结果，例如 pagination 的分组不同，或一个请求同时有多个错误时，不同实现先报告不同错误。两个版本输出不一样，不代表其中一个一定错。论文因此建立独立的可执行参考模型（executable reference model），让它描述所有允许的结果，并把这份模型作为事实上的规格；随后用模型驱动测试（model-based testing，MBT）检查每个实现（§1–2）。

真正困难的是覆盖率。GetObject 的 21 个请求特征和 16 个状态特征合计被分成 135 个类别，粗略的抽象组合仍有 `10^25` 个。测试无法穷举所有具体字符串和对象状态，也无法在每次代码审批里穷举所有抽象组合。方法必须同时回答三件事：哪些输入在行为上不同，如何把 S3 和模型带到所需的前置状态，以及在有限 CI 时间内优先测哪一部分。

## 关键观察 / 隐含假设

- **观察 1：兼容性的对象是完整的可观察输入—输出关系。** 成功 body、错误码、所有 response field 和后续能看到的状态都要比较，不能只给手写的几个 assertion（§2、图 1）。
  - **依赖假设**：模型已经列出全部允许行为；没有写进模型的合法差异会成为误报，模型和实现都漏掉的行为会成为漏报。
- **观察 2：无穷的具体值可以按行为分成有限类别。** 例如 bucket 名可分成语法错误、语法正确但不存在、正确且存在；同一类别只选少量代表值，就能覆盖与该特征有关的黑盒行为（§4、图 2–3）。
  - **依赖假设**：分类足够细；同一类别里的值不会触发模型未区分的行为。
  - **可能失效场景**：开发者没有想到某个长度、编码、控制字符、跨字段关系或实现专用 fast path，coverage 仍会显示当前抽象已覆盖。
- **观察 3：状态约束可以先删除根本无法执行的组合。** “bucket 名无效但其中已有 key”这样的场景不可能存在。论文把这些关系写成布尔不变量 `inv`，用 all-sat 枚举满足 `inv` 和 campaign 配置的赋值（§5.1）。
- **观察 4：多数多错误请求在第一个错误处就返回。** 在 first-error hypothesis 下，0-error 场景覆盖成功路径，1-error 场景逐个覆盖错误路径，2-error 场景检查不同实现的错误优先级；3 个及以上错误不会增加新的首个错误或两两次序信息（§5.2、图 4）。
  - **依赖假设**：服务确实在首错处短路，多个错误不会共同触发独有的解析、清理或安全路径。
- **观察 5：有状态场景需要主动造出前置状态。** 生成一个“bucket 和 key 都存在”的 GetObject 不能只改参数；必须先运行 CreateBucket 和 PutObject，并同时确认模型与实现对这两个写操作也一致（§2.2、§5.3）。
- **假设 1：顺序功能行为可以和并发一致性、性能与故障分开验证。** 论文一次只执行一个操作，模型在内存中、单线程且不关心性能；S3 的一致性由其他机制验证（§1、§2.1）。因此这篇论文不能证明并发 history、durability、availability 或延迟 SLO 正确。

## 核心方法

**1. 用简化但高保真的状态模型做规格。** 模型用 Java 实现一个带元数据的 key-value store，只保存以后能通过 API 观察到的信息，例如对象 payload、创建时间、tag、ETag、加密方式和加密 key；只用于日志、以后无法查询的 request ID 不进入状态。GetObject、PutObject、CopyObject 和 DeleteObject 共享的 conditional behavior 被写成复用 trait，减少同一语义被多次实现（§3）。

**2. 明确处理不可预测值。** request ID、时间戳和 ETag 等值不能由黑盒模型提前算出。系统把其中允许来自实现、且后续可能有用的值标成 prophecy variable：先运行被测系统（system under test，SUT），再把观测值传给模型；模型检查格式或使用它更新状态。这样既不要求模型猜随机 ID，也能在后续 If-Match 请求中使用真实 ETag（§2、Listing 1–2）。哪些字段可以被 prophecy 吸收必须很谨慎，否则会把错误输出当成自由值。

**3. 一个模型容纳多个合法错误次序。** 请求 `GetObject(bucket="non-existing", PartNumber="abc")` 同时有 bucket 不存在和 part number 非法两种错误。模型可以允许多个响应；validator 只要求 SUT 返回其中一个。不过同一个 SUT 必须一直选择同一个顺序。工具会学习每个实现的错误检查偏序，再把模型专门化，之后若顺序改变就报告偏差（§3）。

**4. 用谓词抽象定义行为场景。** 每个请求或状态 feature 被分成互斥类别，并由布尔谓词表示。一个 input scenario 就是这些谓词的一次真假赋值。抽象被称为 adequate，当且仅当同一 input scenario 的所有具体化都得到相同的输出类别；也就是说，输入谓词必须细到足以区分所有已知可观察响应（§4）。团队还会加入不改变模型输出、但可能走不同内部代码路径的类别，例如对象大小边界。

**5. 用约束和错误数缩小场景。** `inv` 描述“key 只能存在于已有且名称合法的 bucket”等状态关系；SAT 求解器只枚举满足约束的场景。每个场景另计算 `num_errors`。配置可以只取 0、1、2 个错误，并指定要完全组合的 feature group；当精确计算错误数太贵时，系统允许安全的 overapproximation，即多纳入一些错误更少的场景，而不是漏掉目标错误数的场景（§5.1–5.2）。

**6. 由 API-planner 准备状态并具体化请求。** 对每个抽象场景，planner 先把状态谓词编译成 target state，再反复查询当前模型，生成 CreateBucket、PutObject 等准备操作。每一步都先跑 SUT、再跑模型并验证；目标状态达到后，concretizer 从模型里取已有 bucket/key，或从合法、非法值池采样，生成最后一个请求。任何准备阶段的不一致也会立即成为 finding（§5.3、Listing 3）。

**7. 用配置把验证预算给最相关的交互。** 开发者按代码改动选择 feature，资深工程师预定义 Range、Conditionals、Encryption 等相关组合。短的本地和 CI campaign 先跑改动附近的空间，多个 campaign 并行；后台长期任务轮换其他组合。它给出的 coverage 是“相对于当前谓词和配置的覆盖率”，不是 API 全空间的绝对百分比（§5.4、§6.1）。

## 设计取舍

- **独立 oracle 换双重实现成本。** 服务行为既写在产品代码里，也要写进模型；团队必须审查两边，处理规格变化，并避免复制同一种错误。
- **开发者熟悉的 Java 换形式完备性。** 模型容易维护、能直接进 CI，却不是从形式规格生成，也没有证明它覆盖全部协议性质。
- **黑盒稳定性换内部覆盖盲区。** 模型不依赖某个实现，适合重写；代价是 cache、重试和不同内部状态只要输出相同就无法区分。工程师可手工加“内部路径类别”，但这又引入实现知识。
- **谓词抽象换 unknown-unknown 风险。** 分类让覆盖可计数，却只能覆盖已经写出的边界。所谓 100% 指某个配置中的 abstract scenarios，不是所有可能行为。
- **first-error reduction 换语义假设。** 它大幅减少无效组合，但若实现先累积多个错误、错误间有交互，3-error 场景可能不再冗余。
- **顺序功能模型换范围收缩。** 并发、读写一致性、硬件故障、timeout/retry、吞吐和延迟要由其他测试体系承担。

## 实验设置

- 论文不是公开 benchmark 上的原型评测，而是 AWS 内部多年运行报告。主要证据来自 S3 Express One Zone 上线、S3 frontend 多年重写，以及常规 S3 CI/CD；每个 finding 都被人工分析并标严重度（§6、表 3）。
- 规模分析集中在 GetObject。表 4 列出 21 个请求 features/102 个 categories 和 16 个状态 features/33 个 categories，合计 37/135；表 5 粗略估计 0-error、1-error、2-error 和任意错误场景分别为 `10^12`、`10^14`、`10^15` 和 `10^25`。
- CI 审批里，一个 campaign 的预算为 3 小时，多个 campaign 可并行。工具约每小时执行 `1.5×10^5` 个请求，论文按实际设置给出每个 campaign 约 432,000 个请求的上限（§6.1）。
- 随机对照使用 property-based testing（PBT）：每个参数从加权分布采样，再用同一抽象函数统计 unique scenarios。它是一个随机生成 baseline，不代表所有先进的 stateful PBT 工具（§6.2）。

## 实验与结果

- **S3 Express One Zone 上线**：对需要和区域 S3 严格兼容的 API 使用共同模型，对 directory bucket 的有意差异则扩展模型。上线前发现并修复 171 个偏差，其中 12 个为高严重度（§6、表 3）。
- **S3 frontend 重写**：在开发者本地和 CI 中运行；多年重写期间，系统发现 92 个 unit/integration test 没有发现的问题，其中表 3 记录 10 个高严重度问题，全部在生产部署前处理（§6、表 3）。
- **持续 S3 CI/CD**：另发现 109 个偏差，其中 24 个高严重度，并参与默认 server-side encryption、完整对象 checksum 和 conditional write 等功能发布。表 3 三行合计是 372 个 finding、46 个 high severity；摘要和结论用的是较保守的“超过 300 个回归”表述（§6、表 3）。
- **三小时预算能覆盖什么**：成功请求的每个 feature 平均有 2.4 个类别，因此 432,000 次请求只能完整组合约 15 个 success features。预定义 Ranges group 的 0/1/2-error 场景分别为 27,000、92,700、92,700，合计 212,400，约 1.5 小时；Encryption 的 2-error 场景单独就约 1,270,080，说明仍必须拆 campaign 或转到异步长期运行（§6.1、表 6）。
- **随机 PBT 的重复率**：一次 28,457 个 GetObject 请求只覆盖 9,040 个 unique scenarios，19,417 个请求落在已经覆盖的场景，即约 68% 重复。这个实验直接说明在相同抽象 metric 下，盲目随机采样把大量预算花在重复行为上（§6.2）。
- **小空间的确定性比较**：只保留 bucket、key 和 range 三个 features、共 8 个非伪场景时，PBT 在 10 次运行中平均要 3,200 个请求才集齐 8 个场景；本文 generator 直接枚举，只需 8 个请求。这个结果证明枚举对已定义小空间很高效，但不能单独证明它在完整 `10^25` 空间里实现了穷尽验证（§6.2）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 高保真模型能发现传统测试漏掉的兼容性问题 | S3 frontend 重写中有 92 个 finding 未被 unit/integration test 发现 | 一个闭源大型服务；finding 由内部人工确认 | 强 |
| 同一模型能支持独立 API 重实现 | S3 Express One Zone 上线前发现 171 个偏差 | 一个大型重实现，部分 API 有意不同 | 强 |
| 方法已在真实发布流程中长期产生价值 | 三个项目合计 372 个 finding、46 个高严重度 | 没有公开 finding 内容、false-positive 或 escape rate | 强（发现量），中（总体缺陷检出率） |
| 系统枚举比随机 PBT 少浪费请求 | 28,457 中 19,417 重复；8 场景实验为 8 对平均 3,200 请求 | GetObject、本文设定的加权随机 baseline 和抽象 metric | 强（该对照），中（推广到其他 PBT） |
| 谓词抽象使覆盖率可量化 | 表 4–6 给出 category、错误数和 campaign 场景数 | 只相对于人工定义谓词和配置；完整空间仍为 `10^25` | 中到强 |

## 批判性分析

### 论证链条

论文的核心链条很务实：S3 的事实规格散落在 20 年行为里，旧实现又不能可靠充当 oracle，因此先建立能列出所有允许响应的模型；具体输入无穷，再用等价类和状态谓词把它变成有限、可配置的场景；最后用生产 CI finding 证明这项维护成本确实换来了价值。最强证据是 S3 Express 和 frontend 重写，而不是 8 场景的小实验。

需要特别收窄“no scenario left behind”。系统不会在每次变更上覆盖 GetObject 的 `10^25` 个抽象场景；它只对配置选中的 feature group 做完整枚举，再用长期轮换补其他组合。coverage 的分母由人写的 predicates 和 campaign 决定。论文对此是诚实的，wiki 页面也不应把它改写成“穷尽 S3 所有行为”。

### 假设压力测试

最大的风险是 model–SUT 共错。模型和服务开发者可能根据同一份错误文档实现相同错误，逐字段比较也看不出来。若一个类别划得过粗，两个 concrete values 走出不同结果，当前抽象仍可能报告 100% coverage。Prophecy variable 也有相同边界：允许范围过宽会吸收错误，过窄会把合法随机性报成偏差。

first-error hypothesis 对常见 request validation 很合理，但不是一般定理。实现可能先解析多个字段、组合错误信息、记录安全审计，或在清理路径上受多个错误共同影响。此时 3-error 场景可能触发 1/2-error 没有覆盖的代码。论文还要求每个 SUT 固定自己的错误顺序；这保护客户兼容性，却也意味着一个原本同样合法的顺序变化会被报告，需要治理流程判断它是回归还是允许的演化。

### 实验可信度

多年生产 CI、三项重大工程、人工严重度和上线前修复构成很强的 operational evidence。特别是 92 个问题被传统测试漏掉，直接支持方法的增量价值。表 4–6 也没有掩盖组合爆炸，给出了三小时预算的真实边界。

不足是所有资产都闭源。论文没有报告模型代码量、API 覆盖数、开发和审查人时、false-positive rate、模型自身错误占 finding 的比例、重复 finding、缺陷类别，以及已经逃到生产的 false negatives。PBT baseline 只是加权随机采样；它没有和带 coverage guidance、state machine、shrinking 或约束求解的先进 stateful PBT 做同预算比较。因而“比 PBT 高效”应限制在论文这两个实验。

### 系统性缺陷

模型成为事实规格后，组织必须回答谁有权改变它。一次 deviation 可能是 SUT bug、模型 bug、文档 bug，或有意的新行为；S3 Express 还要维护共同语义与产品差异。如果审批者只更新模型让测试通过，工具会失去独立性。论文说明模型要在服务变化前扩展，但没有详述 code review、双人批准、版本兼容窗口和回滚规则。

API-planner 会真实创建 bucket、写对象和改变状态。大规模并行 campaign 因而需要隔离、清理、配额、成本控制和可重复命名；准备操作失败也可能来自环境噪声，而不是真正语义偏差。论文没有量化测试基础设施、状态清理、flaky run 或每个 high-severity finding 的发现成本。

## 局限与后续工作

- **局限 1**：只验证正常的顺序功能行为；并发 history、一致性、durability、可用性、性能和故障恢复不在模型范围内。
- **局限 2**：coverage 只相对于人工谓词和 campaign 配置，无法测量没有被想到的输入边界或状态关系。
- **局限 3**：生产证据闭源，模型维护成本、false positive、false negative 和 escaped regression 没有公开。
- **局限 4**：first-error reduction 假设错误检查短路；多错误交互和非短路实现没有单独验证。
- **局限 5**：随机 PBT 对照较弱，不能代表整个 property-based testing 领域。
- **论文提出的后续工作**：从服务交互和源代码自动学习或挖掘 predicates，减少建立、维护抽象的人力（§8）。
- **后续工作 1**：把生产 deviation、代码 diff 和 model diff 变成 predicate refinement 候选，并报告每个新增谓词带来的 unique finding 与额外 campaign 成本。
- **后续工作 2**：把 reference model 接到并发 history/linearizability checker，按操作交错和状态覆盖率验证读写 race，同时继续用现有模型检查单步响应。
- **后续工作 3**：公开匿名化运营指标，包括模型 LOC/人时、finding 分类、误报率、逃逸率、flaky rate 和每千 CI 小时的高严重度产出。
- **后续工作 4**：与 coverage-guided stateful PBT 和约束求解工具做相同时间、相同状态准备成本的比较，而不只比较随机参数采样。

## 相关

- **相关概念**：模型驱动测试、谓词抽象、差分测试、API conformance
- **相关系统**：Amazon S3、S3 Express One Zone
- **同会议**：[[OSDI-2026]]
