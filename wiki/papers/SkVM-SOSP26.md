---
type: paper
name: SkVM
full_title: "SkVM: Revisiting Language VM for Skills across Heterogenous LLMs and Harnesses"
authors: [Le Chen, Erhu Feng, Yubin Xia, Haibo Chen]
venue: SOSP
year: 2026
tags: [agent-skills, llm-agent, compiler, runtime, jit, area/ai-infra]
source_pdf: "[[arxiv26-chen-skvm.pdf]]"
source_md: "[[arxiv26-chen-skvm]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-17
---

# SkVM：面向异构 LLM 与 Harness 的 Skill 虚拟机（SOSP 2026）

> **原题**：SkVM: Revisiting Language VM for Skills across Heterogenous LLMs and Harnesses

> **一句话总结**：对 11.8 万个公开 skill 的分析发现，raw skill 在 15% 任务上反而降分，原因是 model、harness 和 environment 三重错配；SkVM 把 skill 视为代码、LLM 视为 processor，以 capability-aware AOT、environment binding、并行提取和 adaptive JIT 编译出 target-specific variant，118 个任务上平均得分提升 15.3%、token 最多省 40%、wall-clock 加速 3.2–50 倍。

## 问题与动机

Agent skill 是带 metadata、自然语言 workflow、scripts/references 的可分发知识包。目前 harness 只是把原始 skill 塞入 context，但不同模型的 JSON、tool use、代码和规划能力不同，harness 的 tool/sub-agent 接口也不同，host 依赖还可能缺失。

论文把这一问题类比传统 portability：skill 是自然语言代码，模型是异构 processor，harness+host 是 runtime target。目标不是生成更多 skill，而是在安装和运行时把同一 skill 编译到具体 `(model, harness, environment)`。

## 关键观察 / 隐含假设

- **观察 1**：启用 skill 后总体 15% 任务退化、17% 无变化；最多 87% 任务至少有一个模型不受益，说明“有说明书就会执行”不成立（§1、§2.4）。
  - **依赖假设**：SkillsBench/PinchBench 与选取的公开 skill 能代表生态质量；下载量筛选可能偏向流行而非生产关键 skill。
- **观察 2**：15,063 个高下载 skill 中 76% 有 procedural structure、75% 含可固化 code pattern，支持 workflow DAG 和 JIT code solidification（§2.3）。
- **观察 3**：skill 所需结构能力可压缩成 26 个 primitive capabilities，覆盖语料中 95% skill（§4.1.1）。
  - **可能失效场景**：语义质量、taste、领域判断等难以由 structural capability microbenchmark 表达。
- **假设 1**：LLM 既是被适配的 target，也是 compiler/optimizer 的分析器；rollback 能控制 regression，但无法消除同源模型偏差。

## 核心方法

安装时的 **AOT compiler**有三 pass。Capability-based compilation 从 skill 提取 capability level，与 target profile 比较；小 gap 用更明确指令、example 和 constraint 做 compensation，大 gap 用 capability-equivalent implementation substitution。

**Environment binding**抽取 library、CLI、service dependency，生成 idempotent setup script，把运行时诊断搬到安装时。**Concurrency extraction**把 workflow 恢复成 DAG，并分别生成 data-level、instruction-level 和 thread-level parallelism；若 harness 不支持 batch tool/sub-agent 则回退串行。

运行时选择 target-specific variant。**Adaptive recompilation**积累跨 invocation failure/retry 与 self-recovery trace，识别系统性 capability gap，重新编译并在退化时 rollback。**Code solidification**在多次生成都匹配 signature 后，把参数化 LLM code 晋升为可直接执行函数；失败则退回 LLM path。

Resource-aware scheduler 监控 CPU、memory、API latency 和 HTTP 429，动态节流或 suspend sub-agent，并复用上次有效 concurrency hint。

## 设计取舍

- **取舍 1**：为每个 target 保存 variant 和 profile，换跨模型/harness portability；target 更新会带来重新 profile/compile 成本。
- **取舍 2**：code solidification 以连续 signature match 为安全门，牺牲可固化覆盖率换 correctness fallback。
- **取舍 3**：26 capabilities 让编译器简单可扩展，但只描述 structural correctness，不能保证输出洞见或事实质量。
- **边界条件**：评测在 Mac Mini M4、8 models、3 harnesses、118 tasks；没有数小时/多日 long-horizon state、context compaction 或 crash recovery 实验。

## 实验与结果

- 语料含 clawhub.ai 28,990 和 skills.sh 89,280 个 skill；详细 taxonomy 使用下载超过 100 的 15,063 个（§2.3）。
- 8 models×3 harnesses 上 SkVM variant 均取得最高平均分；相比 Skill-Creator，BareAgent 上 Qwen3-30B/Devstral-small 分别提高 25%/10%，cross-harness gap 从最多 13 point 降到 5 point（图 9–10）。
- Qwen3-30B 的 14 类任务中，原 skill 有 11 类低于 no-skill；AOT 后平均 score 提升 88%，三轮 JIT 后 10/14 达满分（图 11）。
- 最强 model/最弱 harness 组合 token saving 接近 40%；target profiling 一次需 7.3–31.1 分钟，成本 0.033–0.079 美元（图 12–13）。
- concurrency extraction 最高加速 3.2 倍；PDF code solidification 将 10,469–15,116 ms 降至 206–568 ms，即 19–50 倍（图 15–16）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| raw skill 缺乏跨 target portability | 图 2、§2.4：15% 退化、harness 差最多 13 point | 选定公开 benchmark/skills | 强 |
| AOT+JIT 同时改善质量和成本 | 图 9–12：平均 +15.3%、token 最多 -40% | 8 models、3 harnesses | 强 |
| SkVM 是 long-horizon agent runtime | 只测重复 invocation、并行和短任务 | 无持久状态/多日恢复 | 弱 |

## 批判性分析

### 论证链条

大规模生态测量支撑 mismatch，三类 mismatch 分别映射到 compiler pass，evaluation 也逐项覆盖 binding、parallelism 和 solidification。最有价值的新抽象是 primitive capability，而不只是 LLM 改写 prompt。

### 假设压力测试

capability microbenchmark 可能被 target update、prompt contamination 或 benchmark-specific behavior 快速淘汰；模型在 microbenchmark 会做，不等于长 workflow 中稳定调用。LLM compiler 对 skill intent 的错误理解可能产生表面过测、实际越权的 variant。

### 实验可信度

模型/harness 组合广，且包含 no-skill、original、Skill-Creator 与 staged ablation。每题仅 5 个 input，部分评分依赖 LLM judge；没有独立安全审计、用户自定义 skill 或真实生产长任务。

### 系统性缺陷

env-binding script 与 solidified code 会执行生成代码，供应链、权限、sandbox 和 secret handling 论文未系统讨论。variant registry、compiler model version 和 rollback state 都需要可审计 provenance。

## 局限与后续工作

- **局限 1**：26 capabilities 只覆盖结构正确性，不覆盖语义真实性、领域 judgment 与安全 policy。
- **局限 2**：没有验证长程任务中的 context compaction、best-state preservation、异步重启和跨天恢复。
- **后续工作 1**：将 skill DAG、variant、execution event 和 checkpoint 组合成持久状态，按 [[Li-LongHorizonResearchEvaluation-arXiv26|Beyond Final Scores]] 的 feedback-control 指标评测。
- **后续工作 2**：对 env-binding 与 solidification 增加 least-privilege capability、签名、sandbox 和可重放审计。

## 相关

- **相关概念**：[[LLM]]、agent skill、AOT/JIT compilation、agent harness
- **同类系统**：[[OpenHands-ICLR25]]、[[AutoScientists-arXiv26]]、[[EviGraph-arXiv26]]
