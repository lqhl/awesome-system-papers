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

> **一句话总结**：T2C 把开发者早已写好的单测通过静态+动态分析「去特化」为带 precondition 的参数化 checker,在 ZooKeeper/Cassandra/HDFS/HBase 上合成数百个 runtime checker,成功检测 20 个真实生产 silent failure 中的 15 个,中位延迟 0.188 秒。

## 问题

分布式系统的 silent failure(语义被违反但不抛异常,如 ephemeral znode 没被清理、at-most-once 消息被重放)占 39% 的生产失效。现有 runtime verifier 要么只针对协议等定义清晰的小范围性质,要么靠人工写 semantic checker——对 ZooKeeper/HDFS/HBase 级别的大系统根本写不完;而 Daikon 类统计 invariant 推断只能抓到变量层关系,完全不表达语义。

## 核心方法

**洞察**:开发者的单测其实已经用 assertion + 配套 workload 编码了**具体的语义预期**,只是测试代码把参数写死了(例如硬编码路径 `/stest`),所以只能检到那几个样例,过不去生产中的不同输入。如果把具体参数「符号化」并提炼出该 assertion 成立的 precondition,就能把测试变成可复用的 runtime checker。

T2C 流水线:
1. **Feasibility study**:先对 6 个系统 210 个测试抽样,发现 87% 用标准 assertion,65% 满足「约束易推断且语义不限于 corner case」——方法可行。
2. **静态分析**:识别测试里做语义检查的关键 assertion 语句,把与 assertion 相关的变量、调用和 setup 语句打包成独立 checker 函数,把具体常量符号化为 checker 参数。
3. **动态分析 + 数据/控制流追踪**:在系统内跑测试时追踪 assertion 里值的来源和依赖,抽取 assertion 成立的前置条件(precondition);没有 precondition 的 checker 会被过滤掉以降低误报。
4. **多层验证**:对合成的 checker 做生效范围、稳定性、与测试原意一致性的多级验证。

部署时 checker 挂在生产实例上,按 precondition 激活,触发 assert 违反则报警并给出定位。

## 关键结果

- 在 ZooKeeper / Cassandra / HDFS / HBase 上成功从 672 个单测合成验证过的 semantic checker(每系统数十至数百个)。
- 采样 20 个用户报告的真实生产 silent failure 重现,T2C 合成的 checker 检出 **15 个**,中位检测延迟 0.188 秒。
- 有趣的是:这些救命 checker 所源自的测试,往往是开发者在 failure 发生之前很久就写好的,只是因为参数写死所以没起作用。
- Runtime overhead 小。
- 开源:github.com/OrderLab/T2C。

## 相关

- **相关概念**:runtime verification、semantic check、invariant inference、Daikon
- **同类工作**:Daikon / 其他统计 invariant 推断;[[TrainCheck-OSDI25]]（DL 训练侧的姐妹工作,共用 Peng Huang 团队）
- **同会议**:[[OSDI-2025]]
