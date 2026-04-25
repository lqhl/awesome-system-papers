---
type: paper
name: Fawkes
full_title: "Fawkes: Finding Data Durability Bugs in DBMSs via Recovered Data State Verification"
authors: [Zhiyong Wu, Jie Liang, Jingzhou Fu, Wenqian Deng, Yu Jiang]
venue: SOSP
year: 2025
tags: [database, fault-injection, fuzzing, data-durability, bug-finding]
source_pdf: "[[3731569.3764841.pdf]]"
source_md: "[[3731569.3764841]]"
---

# Fawkes: Finding Data Durability Bugs in DBMSs via Recovered Data State Verification (SOSP 2025)

> **一句话总结**:基于对 43 个真实 Data Durability Bug 的实证研究,设计上下文感知故障注入 + 功能引导触发 + checkpoint-based data graph 验证的 DBMS 测试框架,在 8 个主流 DBMS 上发现 48 个新 DDB (16 已修复, 8 获 CVE),72 小时内比 Jepsen/CrashFuzz/Mallory/CrashTuner 多发现 23-28 个 bug。

## 问题

DBMS 通过 [[WAL]]、checkpoint、redo/undo log 等机制保证 durability,但这些机制的实现仍然充满 bug。作者称之为 **Data Durability Bug (DDB)**:committed 数据在 crash recovery 后丢失或损坏的实现 bug。

现有工具不够用:
- **人工测试** 不 scalable,覆盖率低
- **Jepsen / Mallory / CrashFuzz** 为分布式系统设计,在单机 DBMS 上随机注入故障,很难精准命中 filesystem/kernel call,也无法精细比对 crash 前后的数据状态——只能发现"系统不可用"这种粗粒度异常

没有工具能系统地针对 single-node DBMS 的 durability-critical path 做精准故障注入。

## 核心方法

作者先在 PostgreSQL、MySQL、IoTDB、TDengine 的 issue 库里挖出 **43 个真实 DDB**,人工分析后得到 7 个 finding:

- **Manifestations**:data loss (33%) / data inconsistency (31%) / log corruption (20%) / system unavailability (16%)
- **Root causes**:72% 源于 crash recovery 或 flush 逻辑的缺陷,16% 是并发问题,12% 是 checkpoint 管理 bug
- **Trigger pattern**:4 步(初始数据+修改 → checkpoint → 故障诱发 crash → 恢复暴露异常)
- **关键观察**:**86%** 的 DDB 只在 SQL 语句执行 filesystem call 或其他 kernel-level syscall 时触发

据此 Fawkes 设计三个模块:

1. **Context-Aware Fault Injector**:编译期做 call-dependency 分析,找出最终调用 glibc / filesystem library 的 DBMS 函数,把它们标记为 fault-injection site。通过 hook OS 基础库注入故障,避免侵入 DBMS 源码。
2. **Functionality-Guided Fault Trigger**:维护 fault-functionality table(注入点 × SQL 功能),优先触发覆盖率低的点,生成针对性 SQL workload 驱动执行。
3. **Checkpoint-Based Data Graph Verifier**:基于 checkpoint 日志计算 expected post-recovery state,与实际恢复后数据比对,精确发现 data loss 和 inconsistency——不只是检测"系统是否存活"。

支持的 fault 类别 7 种:power failure、memory exhaustion、kill、kernel crash、disk I/O fault、software exception、shutdown 命令。

## 关键结果

- 在 PostgreSQL、MySQL、MariaDB、IoTDB、TDengine、GridDB、CnosDB、OpenGemini 上发现 **48 个新 DDB**
- **16 个** 已被开发者修复,**8 个** 获 CVE
- 72 小时运行下比 Jepsen / CrashFuzz / Mallory / CrashTuner 分别多发现 **27 / 25 / 23 / 28** 个 bug
- 分支覆盖率比四个 baseline 分别高 **84% / 48% / 47% / 70%**

## 相关

- **相关概念**:[[WAL]]、[[Checkpoint]]、[[Fault-Injection]]、[[Fuzzing]]、[[ACID]]、[[Data-Durability]]
- **同类工具**:Jepsen、Mallory、CrashFuzz、CrashTuner
- **同会议**:[[SOSP-2025]]
