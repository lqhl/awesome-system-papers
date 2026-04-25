---
type: paper
name: CAFault
full_title: "CAFault: Enhance Fault Injection Technique in Practical Distributed Systems via Abundant Fault-Dependent Configurations"
authors: [Yuanliang Chen, Fuchen Ma, Yuanhang Zhou, Zhen Yan, Yu Jiang]
venue: ATC
year: 2025
tags: [fault-injection, distributed-systems, fuzzing, configuration-testing, reliability]
source_pdf: "[[atc2025-chen-yuanliang.pdf]]"
source_md: "[[atc2025-chen-yuanliang]]"
---

# CAFault: Enhance Fault Injection Technique in Practical Distributed Systems via Abundant Fault-Dependent Configurations (ATC 2025)

> **一句话总结**：把「故障注入」与「配置变体」联合 fuzz：用动态依赖建模 (FDModel) + fault-handling guided fuzzing，比 SOTA 多覆盖 31.5%/29.3%/81.5% 故障容错逻辑，48 小时挖出 16 个 HDFS/MySQL-Cluster/ZooKeeper/IPFS 未知 bug。

## 问题

分布式系统的故障容错机制由配置项控制，但现有 fault injection 工具（CrashFuzz、Mallory、Chronos 等）只在默认配置下注入故障，忽略了配置变体导致的执行路径，错过大量 bug。配置 × 故障的联合空间 M·N 巨大，无法穷举：MySQL-Cluster 的 consensus 选项 (Raft/Paxos/Quorum) 会改变网络分区与数据一致性的处理路径。

## 核心方法

CAFault 两阶段交替：

1. **FDModel（Fault-Dependent Model）构建**：随机变异配置 c → c'，监控 coverage 变化反推「哪些配置项与哪个故障 fi 有隐式依赖」，再用二分最小化算法从 k 个变异项中提取最小相关子集。覆盖类型分类变异（boolean 取反、enum 替换、数值偏移、字符串语义化）。
2. **Fault-handling guided fuzzing**：静态分析提取 try/catch/finally (Java) / try/throw (C++) / defer/panic/recover (Go) 块及其 call trace 作为「故障容错代码」，只用这部分代码 coverage 引导 fault sequence 变异，避免探索无关路径。

实现层用 [[Coverage-Guided-Fuzzing]] 思想；coverage 工具：JaCoCo (Java) / gcov (C++) / gtest (Go)。Workload 来自 HiBench/SQLancer/JMeter/ipfs-benchmark。架构细节回 [[atc2025-chen-yuanliang]]。

## 关键结果

- 4 个目标系统、48 小时实验，CAFault 找到 **16 个未知 bug**（HDFS 3、MySQL-Cluster 6、ZooKeeper 4、IPFS 3），全部已确认修复。
- CrashFuzz、Mallory、Chronos 分别只找到 3、4、1 个；加上 FDModel 增强后变为 9、12、5 个，仍漏掉 3 个 deep-path bug（需 fault sequence 组合）。
- Fault-tolerance 代码覆盖：相比 CrashFuzz/Mallory/Chronos 多覆盖 31.5%/29.3%/81.5%。
- 11/16 bug 必须特定配置才能触发，5/16 是 deep-path 多故障组合。

## 相关

- **相关概念**：[[Fault-Injection]]、[[Coverage-Guided-Fuzzing]]、[[Static-Analysis]]
- **同类系统**：CrashFuzz、Mallory、Chronos、Jepsen、ChaosMonkey
- **同会议**：[[ATC-2025]]
