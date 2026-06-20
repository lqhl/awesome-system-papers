---
type: paper
name: T2C
full_title: "Deriving Semantic Checkers from Tests to Detect Silent Failures in Production Distributed Systems"
authors: [Chang Lou, Dimas Shidqi Parikesit, Yujin Huang, Zhewen Yang, Senapati Diwangkara, et al.]
venue: OSDI
year: 2025
tags: [distributed-systems, silent-failures, runtime-verification, program-analysis, testing]
source_pdf: "[[osdi25-lou.pdf]]"
source_md: "[[osdi25-lou]]"
---

# Deriving Semantic Checkers from Tests to Detect Silent Failures in Production Distributed Systems (OSDI 2025)

> **一句话总结**：T2C 用静态+动态分析把现有单测「去特化」为带 precondition 的参数化 semantic checker，在 ZooKeeper/Cassandra/HDFS/HBase 合成数百 checker，复现 20 个真实 silent failure 中 15 个，中位检测延迟 0.188s。

## 问题与动机

分布式系统 silent failure（语义违反但不抛异常）占生产失效 39%，现有 runtime verifier 要么只覆盖小协议，要么靠人工写 semantic checker——对 ZooKeeper/HDFS 级系统不可扩展。Daikon 类统计 invariant 只能表达变量关系，无法刻画 ephemeral znode、at-most-once 等语义。作者洞察：开发者已写的测试里嵌着 oracle 和 workload，只是绑定特定输入/setup，production 下不同 bug/条件触发时测不到。

## 关键观察 / 隐含假设

- **观察 1**：210 个跨 6 系统样本中 87% 用 assert；65% 可同时满足「expected value 约束可推断」+「非 corner-case 配置」，可泛化到 production。
  - **依赖假设**：测试 assertion 模式（result-match、consistency、status、magic value）在 Java 生态稳定；utility function 模块化（22%）可复用。
  - **可能失效场景**：20% magic value 测试、22% 需领域知识推断 expected value；C++/Rust 测试风格不同。
- **观察 2**：测试 workload 里的破坏性操作（删文件、重启集群）不必进入 checker——checker 只观察 production 触发的状态再激活 assertion。
  - **依赖假设**：production workload 能覆盖测试所 exercise 的语义路径（不同 input、不同并发）。
  - **可能失效场景**：仅特定 race 触发的 bug，production trace 从未命中 precondition。
- **假设 1**：从 test 泛化的 checker 对「未来新 bug」有效——15/20 复现 failure 的源测试在 bug 报告前就已存在。
  - **证据强度**：强；直接支撑「测试→checker」价值主张，但 5/20 未检出说明覆盖有洞。

## 核心方法

**离线**：CFG 上从 assertion 反向 slice 封装 C_f；动态分析提取 symbolic precondition C_p 与 constraints C_r；mutation 放宽过严约束；多级 validation 过滤无效 checker。

**在线**：T2C verifier 监控 workload，满足 C_p∧C_r 时激活 C_f；失败只告警不自动 mitigated（与现有 monitoring 同 scope）。

四系统 672 test → verified checker；需开发者提供包路径、编译指令、核心类 instrumentation 配置。

## 设计取舍

- **取舍 1**：不追求转化全部 test——只选 promising 子集，接受部分语义无 checker 覆盖。
- **取舍 2**：slicing 无 soundness 保证，靠 shouldExclude 过滤危险操作（restart/delete）——可能漏必要依赖或误含 side effect。
- **边界条件**：Java 系、需 instrumentation；checker 不修复故障，只缩短 MTTD。

## 实验与结果

- Feasibility study：6 系统 210 tests，Finding 1–7 量化可转化比例。
- ZooKeeper/Cassandra/HDFS/HBase：672 verified checkers。
- 20 个用户报告 production silent failure 复现：15 detected，median 0.188s；5 missed（论文分析原因）。
- Runtime overhead：小（具体系统级数字见 §6）；开源 https://github.com/OrderLab/T2C。

## Critical Analysis

### 论证链条

「silent failure 普遍 → 测试已含语义 oracle → 去特化+precondition → production 检测」链条清晰，feasibility study 支撑设计选择。把 test 当 specification 的思路巧妙，但泛化边界（magic value、特殊配置）与 production 命中率之间的 gap 主要靠 validation 和 mutation 缓解，无形式化保证。

### 假设压力测试

- **已证明**：多数 assertion 可参数化；历史 bug 大多可被衍生 checker 抓住。
- **可能失效**：新语义无对应 test；precondition 过宽导致 false positive 或过重开销；非 Java 系统需重做分析模式。
- **论文未覆盖**：checker 长期维护（代码变更后失效）；与 chaos/fault injection 的互补关系。

### 实验可信度

真实 failure 复现是强证据；但 20 个样本量有限，且选自已有 test 覆盖的语义。Baseline 对比 Daikon/回归-test 方案需细读 §6；overhead 在「小」量级但大规模 deployment SLO 未给。

### 系统性缺陷

依赖开发者配置与手工筛选 validated checkers；slicing 可能含 side effect；5/20 miss 暴露自动化边界；论文承认无 domain knowledge 时部分 test 不可转化。

## 局限与 Future Work

- **局限 1**：22% test 需领域知识；magic value 难泛化。
- **局限 2**：仅告警不缓解；instrumentation 侵入性。
- **Future work 1**：跨语言 test 模式库与 CI 集成自动再生成 checker。
- **Future work 2**：与 mercurial CPU/core 类 silent failure 的联合检测（论文 intro 提及）。

## 相关

- **相关概念**：[[Distributed-Systems]]、runtime verification
- **同类系统**：Daikon、RV-Bound、回归-test 推断方案
- **同会议**：[[OSDI-2025]]