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
last_reviewed: 2026-07-30
---

# 大规模有状态服务的高保真模型（OSDI 2026）

> **原题**：High Fidelity Models for Large Scale Stateful Services (Operational Systems)

> **一句话总结**：AWS 为 S3 API 建可执行 reference model，并以 predicate abstraction 将 concrete request/state 归成可量化 scenario，再由 coverage-driven model-based testing 系统生成 pre-state 与请求；该工具进入 S3 CI/CD，已在 S3 Express、frontend rewrite 和持续发布中阻止 372 个行为偏差，其中至少 36 个 high severity。

## 问题与动机

S3 20 年演化到超过 500 万亿 object、平均 2 亿 request/s、96 个 API operation，同一 API 还被 S3 Express One Zone 等完全不同 codebase 重实现。客户依赖的不只是成功 payload，也依赖精确 status/error/header；GetObject 单独有 21 个 input parameter、36 个 output parameter和 bucket/version/encryption state。

“拿旧 implementation 做 differential oracle”不可靠，因为 pagination、error ordering 等可能有多个合法行为；两个实现可不同但都正确。手写 integration test 又无法给出覆盖度。论文选择 executable model 作为 de facto specification，再用 abstraction 和 systematic generation 让 coverage 可度量、可在 CI 时间预算内配置。

## 关键观察 / 隐含假设

- **观察 1：API sameness 是完整 observable input-output relation，不是 happy path。** client 依赖 404/412/416、range/checksum 与 state-dependent header（§1）。
  - **依赖假设**：sequential request 能隔离验证；concurrency/consistency 由其他机制覆盖。
  - **可能失效场景**：race、eventual propagation、timeout/retry、performance与跨区域故障等非功能行为。
- **观察 2：concrete value 无穷，但行为由有限 predicate category 决定。** request/state feature 被映射为 equivalence class，coverage 以 abstract scenario 表示（§4）。
  - **依赖假设**：predicate partition 足够细，相同 category 内不存在未建模的行为差异。
- **观察 3：多数多错误请求会在第一个 validation/error precedence 后收敛，盲目笛卡尔积高度冗余。** generator 可按 error count、feature correlation 和 model state 去除 spurious/redundant scenario（§5）。
  - **依赖假设**：error precedence/model 与 SUT准确，安全 reduction 不漏交互型 bug。
- **假设 1：reference model 与实现足够独立且本身正确。**
  - **证据强度**：中；rigorous validation和长期 finding支持，但 model/SUT共同误解 specification仍不可检测。

## 核心方法

每个 API 有 executable state machine model，只保留 functional semantics。SUT response 中无法预测但合法的 request ID、Date、ETag 等被标为 prophecy/opaque value：validator 按格式或 allowed behavior 检查，必要时把值注入 model state供后续 conditional request 使用，而不是要求 byte-for-byte deterministic output（图 1、Listing 1–2）。

predicate abstraction 为 input、state 和 output feature 定义 category，例如 object size boundary、range relation、version存在性、checksum mode。generator 读取当前 model state，先构造达到目标 pre-state 的 operation sequence，再 concretize 一个尚未覆盖 abstract scenario；执行 SUT 与 model、比较全部 response element，更新 model/coverage（§4–5）。

scenario reduction 排除逻辑不可能组合，并按 `num_errors` 限制错误 feature 数；开发者可指定 change-relevant feature group，资深工程师维护 ranges/versioning 等相关组合的 campaign。短 CI campaign 覆盖小而针对性的空间，后台 rotating campaign补长尾。

## 设计取舍

- **高保真 oracle 换 model construction成本**：每个 API feature/behavior要双重实现和审查；模型本身成为关键生产资产。
- **可执行模型换形式完备性**：开发者易读、可CI运行，但不是机器证明的 protocol spec。
- **predicate reduction 换 completeness**：GetObject 抽象空间仍巨大，只能选择约15个 success feature组合/3小时campaign。
- **sequential determinism 换范围收缩**：不覆盖 distributed consistency、concurrent operation、latency或availability。
- **边界条件**：长期稳定 API、有大量 stateful edge case和多个实现时价值最大；小/快速变化 API 的 model成本可能不划算。

## 实验与结果

- 在 GetObject request generation 的 workload boundary 内，以 unique abstract-scenario coverage 为 metric：systematic generator 用 8 requests 达到 100% coverage；相比随机 PBT baseline 平均需要 3,200 requests（§6.2）。
- S3 Express One Zone launch 前阻止 171 deviations，其中 12 high severity；模型同时编码 directory bucket 的 intentional differences（§6、表 3）。
- 多年 frontend API rewrite 的 CI 发现 92 个 unit/integration test 漏掉的问题，全部在 production deployment 前修复（§6）。
- 持续 S3 CI/CD 另发现 109 deviations，其中24 high severity，并支持 default encryption、full checksum、conditional write 等发布。三项合计372 findings、至少36 high-severity。
- 单 campaign 约 1.5×10^5 request/hour，三小时预算约432K request；GetObject 每 feature平均2.4 success category，只能完整组合约15 features。Range预定义group 212,400 requests约1.5小时（§6.1、表 6）。
- 以 property-based testing（PBT）为 baseline 的 GetObject 实验中，PBT 28,457 requests 只覆盖 9,040 unique scenario、19,417 重复；在仅含 8 个目标 scenario 的边界内，PBT 平均需 3,200 requests，而 systematic generator 只需 8 个（§6.2）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| model-based conformance能捕获传统test漏掉的回归 | §6/表3：三项372 deviations，frontend rewrite独有92个 | AWS内部S3、人工severity与fix确认 | 强 |
| abstraction支持可量化高效coverage | §6.1：432K request/3h、feature-group campaign | GetObject与内部predicate配置 | 中 |
| systematic generation比随机PBT少冗余 | §6.2：28,457中19,417重复；8场景只需8请求 | 两个GetObject小实验 | 强 |
| model可支持独立重实现 | S3 Express launch阻止171 deviations | 一个大型新implementation | 强 |

## 批判性分析

### 论证链条

“API行为复杂→需要reference model→抽象使系统探索可行→CI finding证明价值”链条非常务实。最重要成果不是新算法单点，而是20年stateful service中model如何成为spec并进入组织流程。论文没有声称穷尽所有场景；coverage metric只相对于当前predicate universe，不能被误读为真实behavior completeness。

### 假设压力测试

若未想到某个predicate boundary，model和generator会把不同行为合并，coverage仍显示100%。model与implementation共享开发者认知或复制逻辑时会有 correlated bug。prophecy value使用过宽可能让SUT随意输出被model吸收；过窄则误报合法 nondeterminism。跨request并发和failure/retry恰是stateful cloud service重要bug来源，但不在范围。

### 实验可信度

多年真实CI、重大launch和hundreds confirmed fixes是强production evidence，比synthetic benchmark更有说服力。限制是闭源：看不到table细项、model LOC/维护人力、false-positive rate、finding类型与漏到production的false negative。PBT比较只在小scenario，未与stateful property-based/model checker强工具全面比较。

### 系统性缺陷

model evolution需要governance：谁判定deviation是SUT bug、model bug还是intentional change；不同implementation feature flag会增加branch。campaign配置依赖senior developer knowledge，抽象并未消除人工taste。三小时并行campaign还需大规模测试环境与state cleanup，成本未量化。

## 局限与后续工作

- **局限 1**：只验证normal sequential functional behavior，不覆盖consistency、concurrency、availability、performance和security policy。
- **局限 2**：coverage受人为predicate定义限制，无法量化unknown unknown。
- **后续工作 1**：将并发history/linearizability checker与reference model组合，按schedule/state coverage评估multi-operation race。
- **后续工作 2**：用production deviation和code diff自动建议predicate refinement，以新增unique finding/额外campaign成本衡量。
- **后续工作 3**：公开匿名化运营指标：model维护人时、deviation FP/分类、escape rate与每千CI-hour high-severity yield。

## 相关

- **相关概念**：[[Model-Based-Testing]]、[[Predicate-Abstraction]]、[[Differential-Testing]]、[[API-Conformance]]
- **同类系统**：[[Amazon-S3]]、[[S3-Express-One-Zone]]
- **同会议**：[[OSDI-2026]]
