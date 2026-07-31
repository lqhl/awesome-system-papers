---
type: paper
name: Timelock Drive
full_title: "Timelock Drive: Isolated Time-Based Defense for Storage Systems"
authors: [Jonah Rosenblum, Juechu Dong, Peter M. Chen, Satish Narayanasamy]
venue: OSDI
year: 2026
tags: [storage-security, ransomware, trusted-computing-base, formal-verification, backup]
source_pdf: "[[osdi26-rosenblum.pdf]]"
source_md: "[[osdi26-rosenblum]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 面向存储系统的隔离式时间锁防御（OSDI 2026）

> **原题**：Timelock Drive: Isolated Time-Based Defense for Storage Systems

> **一句话总结**：Timelock Drive让drive内隔离checker强制“写后固定时长不可覆盖”，即使versioning software和管理员credential全被攻陷也不能删最近备份；metadata由untrusted host维护、checker只验证append-only hash/log，SSD throughput overhead约0.5%。

## 问题与动机

ransomware常先取得管理员权限并删除backup；把retention policy放在同一backup/versioning software内，credential或bug仍可绕过。安全边界应下沉到无法由host software取消的physical block timelock，同时不把复杂versioning system放进TCB。

## 关键观察 / 隐含假设

- **观察 1**：性能或安全瓶颈并非只由资源容量决定，还取决于数据布局、执行粒度或信任边界。
- **观察 2**：论文提出的细粒度控制机制可以隔离主要开销，同时保留保守回退以维持正确性。

## 核心方法

drive controller内小型TD checker提供read/write/timelock interface；block写入后在duration内任何主体都不可modify，称transient immutability。versioning system运行在完全untrusted host，只能append新data/metadata。

纯append metadata若每次查block都scan log会慢。TD采用delegate-but-verify：host缓存/组织最新metadata，checker通过hash/integrity proof与drive上的append-only root验证，再执行timelock check。epoch/barrier限制crash时丢失的metadata窗口；checker被形式化验证。安全依赖tamper-resistant clock/controller，攻击检测需早于retention expiration。

## 实验与结果

- trace/filebench相对conventional versioning，SSD throughput overhead约0.5%、execution约0.4%，多workload少于1%（图 5/6）。
- 每100K operations最高space overhead略超3 MB；write-heavy trace I/O overhead最高但总体modest。
- ransomware/trimming attack实验中，host/VS compromised后仍能从timelocked versions恢复。
- checker以隔离prototype/emulation实现；formal model证明byte-level log replay与abstract transient-immutability state等价。

## 论断—证据表

| 论断 | 证据 | 边界 | 置信度 |
|---|---|---|---|
| compromised host不能覆盖timelocked block | formal proof/attack test | checker/clock可信 | 强 |
| versioning system可移出TCB | architecture | integrity proof完整 | 强 |
| 性能/空间开销低 | 图 5/6 | trace与prototype | 强 |
| 能防所有ransomware backup破坏 | threat model | patient attacker可等过期限 | 中 |

## 批判性分析

### 论证链条

TD把retention guarantee降到极小hardware interface，TCB明显优于“安全backup software”。但它只延迟攻击，不永久阻止；攻击者潜伏超过timelock、破坏所有新写或阻断服务仍可成功。不可覆盖还会放大合法delete/space reclamation与误配置成本，retention duration是security/capacity核心参数。

### 假设压力测试

核心假设失效时，系统可能退化到基线或暴露额外开销；极端负载与故障条件需要单独验证。

### 实验可信度

实验支持主要设计论断，但平台与工作负载范围限定了可推广性。

## 局限与后续工作

- 对patient attacker、clock rollback、controller firmware compromise与DoS做分析。
- 设计adaptive retention/capacity policy并报告长期[[Garbage-Collection|GC]]和wear。
- 在真实SSD controller集成，验证power loss、firmware update与key rotation。

## 相关

- **相关概念**：[[Ransomware]]、[[Trusted-Computing-Base]]、[[Append-Only-Log]]、[[Formal-Verification]]
- **相关系统**：[[LVM-Snapshot]]、[[Versioning-File-System]]
- **同会议**：[[OSDI-2026]]
