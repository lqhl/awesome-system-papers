---
type: paper
name: Fawkes
full_title: "Fawkes: Finding Data Durability Bugs in DBMSs via Recovered Data State Verification"
authors: [Zhiyong Wu, Jie Liang, Jingzhou Fu, Wenqian Deng, Yu Jiang]
venue: SOSP
year: 2025
tags: [dbms-testing, durability, fault-injection, crash-consistency, wal]
source_pdf: "[[3731569.3764841.pdf]]"
source_md: "[[3731569.3764841]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# Fawkes：通过恢复的数据状态验证查找 DBMS 中的数据持久性错误（SOSP 2025）

> **原题**：Fawkes: Finding Data Durability Bugs in DBMSs via Recovered Data State Verification

> **一句话总结**：基于 43 个真实 DDB 案例归纳「checkpoint → fault at fsync → recovery 验证」模式，Fawkes 用上下文感知 fault injection + 功能引导触发 + checkpoint 数据图验证，在 8 个 DBMS 发现 **48** 个未知 DDB（16 已修、8 获 CVE）。

## 问题与动机

[[WAL]]/checkpoint/redo-undo 机制理论上保证 data durability，但实现复杂，Data Durability Bugs (DDB) 可导致 data loss(33%)、inconsistency(31%)、log corruption(20%)、unavailability(16%)。Jepsen/Mallory 等随机 fault injection 难以在 filesystem/kernel call 精确点触发，且 correctness check 粗粒度，无法对比 crash 前后数据状态。

## 关键观察 / 隐含假设

- **观察 1**：86% 研究的 DDB 仅在 SQL 执行路径触及 filesystem 或 kernel syscall 时才能稳定复现。
  - **依赖假设**：DDB 根因多在 flush/recovery 顺序错误，与 I/O 调用点强相关。
  - **可能失效场景**：14% 可在任意阶段触发的逻辑型 DDB（如 TDengine WAL checkpoint 逻辑错误）。
  - **证据强度**：强——43 case 人工归因统计。
- **观察 2**：DDB 可归纳为四步：数据创建/修改 → checkpoint → fault crash → recovery 暴露异常。
  - **依赖假设**：测试框架能控制 checkpoint 时机并构造预期 recovery 后状态。
  - **可能失效场景**：分布式 DBMS 多节点一致性超出单节点 DDB 定义。
  - **证据强度**：中——四 DBMS 样本，未覆盖 graph/vector store。
- **假设 1**：基于 checkpoint + log 可机械计算 expected post-recovery data graph，与 observed 对比足以检测 subtle loss/inconsistency。
  - **证据强度**：中——对 8 个 DBMS 有效，但 state 计算复杂度随 schema/SQL 特性增长。

## 核心方法

1. **Context-aware fault injection**：编译期扫描 call graph，在触及 glibc/fs 的代码段插桩 hook。
2. **Functionality-guided fault triggering**：维护 fault-site coverage + fault-functionality 表，优先生成覆盖少 site 的 SQL workload。
3. **Checkpoint-based data graph verification**：crash 后 reboot，比较 expected vs recovered 数据图。

## 设计取舍

- **取舍 1**：聚焦单节点 fault-induced crash，排除 optimizer 静默不写盘类「逻辑 bug」。
- **取舍 2**：需 DBMS 源码编译插桩，无法黑盒测试 closed-source 引擎。
- **边界条件**：关系型/时序型 OLTP 引擎；分布式协议正确性非目标。

## 实验与结果

- 在 8 个 DBMS、72h 的作者适配比较配置中，相比 Jepsen/CrashFuzz/Mallory/CrashTuner，Fawkes 分别发现 29 对 2/4/6/1 个 DDB；边界是这些工具使用 Fawkes workload generation，而非 stock-tool 对比（§6.3，Table 4）。

- 8 个 DBMS：PostgreSQL、MySQL、MariaDB、IoTDB、TDengine、GridDB、CnosDB、OpenGemini
- **48** 新 DDB，**16** 已修，**8** CVE
- 72h 对比：比 Jepsen/CrashFuzz/Mallory/CrashTuner 多发现 23–28 个 bug，分支覆盖高 47–84%

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| Two-week campaign found previously unknown DDB | 48 unique，16 fixed、8 CVE（§6.1–6.2，Table 2） | 8 DBMS、Docker/local network | high |
| Adapted comparison setup finds more DDB | 72h：Fawkes 29 vs Jepsen 2/CrashFuzz 4/Mallory 6/CrashTuner 1（§6.3，Table 4） | baselines adapted with Fawkes workload，非 stock head-to-head | high |
| Branch coverage increases in same setup | 320848 vs 174604/216985/218135/188810（§6.3，Table 3） | 72h、8 DBMS、covered branch proxy | high |
| Ablation shows component contribution | context injection +3 bug；trigger +40.1% branch/+3 bug；data graph +21 DDB（§6.4，Table 5–6） | 72h aggregate、mineru labels garbled | medium |

## 批判性分析

### 论证链条

motivation study (43 DDB) → 三组件设计需求 → Fawkes 实现，逻辑严密。从 manifestation 统计到 injection site 选择有清晰映射。

### 假设压力测试

- 仅 4 个 DBMS 做 deep study，graph DB/vector DB 泛化性未知。
- SQL grammar 组合爆炸下 state verifier 能否 scale 到超复杂 transaction？
- 与 Jepsen 的 distributed partition 场景互补但不重叠，不能替代全部 DB 测试。

### 实验可信度

真实 bug + CVE 背书强。72h fuzz 对比公平性取决于各工具调参；branch coverage 作为 proxy 合理。

### 系统性缺陷

论文未讨论：false positive 率；对加密/压缩表空间的支持；云托管 DB 托管层 fault 模型。

## 局限与后续工作

- **局限 1**：单节点、fault-crash 为主，非分布式一致性。
- **局限 2**：需源码级插桩。
- **Future work 1**：将 data graph verification 扩展到 replication lag 场景下的 durability 语义。

## 相关

- **相关概念**：[[WAL]]、crash consistency、fault injection
- **同类系统**：Jepsen、Mallory、CrashFuzz
- **同会议**：[[SOSP-2025]]
