---
type: paper
name: Sieve
full_title: "Understanding and Detecting Fail-Slow Hardware Failure Bugs in Cloud Systems"
authors: [Gen Dong, Yu Hua, Yongle Zhang, Zhangyu Chen, Menglei Chen]
venue: ATC
year: 2025
tags: [fail-slow, fault-injection, distributed-systems, bug-study, reliability]
source_pdf: "[[atc2025-dong.pdf]]"
source_md: "[[atc2025-dong]]"
---

# Understanding and Detecting Fail-Slow Hardware Failure Bugs in Cloud Systems (ATC 2025)

> **一句话总结**：研究 5 个云系统 48 个 fail-slow 硬件 (FSH) 故障案例，发现 100% 都源于 synchronized / timeout 机制 + 细粒度故障；提出 Sieve 静态识别这两类 fault point 并精确注入 delay，在 ZooKeeper/Kafka/HDFS 找到 6 个未知 bug。

## 问题

Fail-slow 硬件（NIC 突降到 1 Kbps、NVMe SSD 一个月内 1.41% 受影响）只让部分 I/O 慢下来而非完全失败，能逃过现有 heartbeat 等检测器。AWS 的 fail-slow 事件曾耗 9 小时定位，PagerDuty 上一个 ZooKeeper fail-slow NIC 案例诊断花了 5 个月。已有 fault injection 工具（FATE、Legolas、Chronos 等）只针对粗粒度故障（crash、partition），无法触发 FSH bug。

## 核心方法

基于对 ZooKeeper/HDFS/HBase/MapReduce/Cassandra 共 48 个 FSH 故障的 study，得到两条关键观察：(1) 所有 FSH bug 都由 synchronized 块 / timeout 机制中的 I/O 触发；(2) 必须细粒度故障（不是 fail-stop）才能触发。Sieve 据此把搜索空间从全部 I/O 收窄到这两类 fault point：

- **同步 I/O 识别**：Soot 静态分析两种 pattern，(a) critical region（lock/unlock 包裹）通过遍历 call graph 匹配最后一个非 return 后的 exit point；(b) hard barrier（notify/wait）。
- **Timeout-protected I/O 识别**：识别 wait(timeout) 的 soft barrier；以及 `elapsedTime = endTime - startTime` 这种公式，taint 分析匹配 startTime 与对应 endTime。
- **注入策略**：Javassist 在 fault point 前插桩 fail-slow agent，运行时把 call stack/thread ID 上报 controller。同 basic block 内的 fault point 分组只取最后一个；context-sensitive 避免重复注入相同 call stack。Sync 类故障注入 5 分钟 delay；timeout 类注入 2/3 timeout 值以同时触发 timeout handler 与 race。

详细 algorithm/implementation 回 [[atc2025-dong]]。

## 关键结果

- 7 个 FSH bug 检出（6 unknown + 1 known HDFS-15869，2 已确认）：ZK-4816/4817/4836/4844、KAFKA-16401/16412、HDFS-15869。
- 重现 48 个 study bug 中的 34 个；剩下 14 个需要多故障注入或缺乏 oracle/checker。
- 与 Random、FATE、Legolas、Chronos 对比，Sieve 是唯一能命中全部检测出的 7 个 bug 的工具；ablation Sieve-I/Sieve-S 验证 grouping + context 的必要性。
- Bug study 反向洞察：73.5% FSH 故障近 10 年才被报告，58.3% 导致节点不可用，89.6% 仅一个 fail-slow 设备就能触发。

## 相关

- **相关概念**：[[Fault-Injection]]、[[Static-Analysis]]、[[Timeout-Mechanism]]、[[Gray-Failure]]
- **同类系统**：FATE、Legolas、Chronos、Panorama
- **同会议**：[[ATC-2025]]
