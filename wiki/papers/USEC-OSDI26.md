---
type: paper
name: USEC
full_title: "USEC: A User-Requirement-Driven Mandatory Access Control Framework for Operating Systems (Operational Systems)"
authors: [Yu Jiang, Wenhuan Liu, Fuchen Ma, Yuheng Shen, Yuanliang Chen, et al.]
venue: OSDI
year: 2026
tags: [operating-system-security, mandatory-access-control, linux, lsm, access-control]
source_pdf: "[[osdi26-jiang-yu.pdf]]"
source_md: "[[osdi26-jiang-yu]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 用户需求驱动的操作系统强制访问控制框架（OSDI 2026）

> **原题**：USEC: A User-Requirement-Driven Mandatory Access Control Framework for Operating Systems (Operational Systems)

> **一句话总结**：USEC 把 SELinux 的全系统 domain–type allow-list 改为对少量关键资源声明保护意图，并仅在相关路径按需执行/缓存决策；等价需求下 policy code 最多减少 10×，相对 SELinux overhead 低 3.4%–17.1%，已部署超过 800 万 endpoints。

## 问题与动机

Mandatory Access Control（MAC）可在application被攻陷后限制kernel resources访问，但SELinux policy需要维护大量labels、types与跨module rules；高频LSM hook又让即使与security policy无关的operation也支付检查成本。严格policy还常破坏legacy/proprietary software，导致enterprise deployment干脆关闭SELinux。USEC面向的实际目标不是追求最大policy expressiveness，而是让vendor能声明自己真正关心的security-critical resources，并在现有Linux生态中上线。

## 关键观察 / 隐含假设

- **观察 1**：vendor的实际安全需求通常集中在少量resource/capability；policy应以“被保护资源允许谁做什么”为中心，而非枚举全系统domain–type pairs（§3）。
- **观察 2**：未被policy点名的资源无需进入MAC engine，可继续由DAC/已有LSM处理；demand-driven hooks能避开irrelevant paths（§4）。
- **观察 3**：同一subject/object/operation决策重复出现，可用bitmap/decision cache减少policy lookup与synchronization。
- **依赖假设**：管理员完整列出critical resources；漏列不是deny，而是回退DAC，因此配置简洁性同时扩大misconfiguration的潜在blind spot。

## 核心方法

Resource-centric policy template直接锚定file、process、IPC、socket等semantic resource class，并描述allowed principals和read/write/execute operation。UOS V25实例只需11 modules/949 KB，相比SELinux的320 modules/2.1 MB；file_contexts由5,428降至1,577，homedirs由408降至65（§1）。

kernel侧只为policy声明的resource/capability启用enforcement path；无关对象近似零USEC overhead。命中保护对象后，bitmap与decision cache快速判断operation，online policy update可在不中断服务时替换规则。Compatibility interface补充process lifecycle、file I/O audit、socket event等binary-compatible LSM hooks，并允许与SELinux等module共存；shadow/learning mode用于部署前观察（§3–§5）。

## 设计取舍

- **opt-in protection换可部署性**：避免全局strict policy破坏应用，但安全边界完全取决于resource inventory。
- **semantic abstraction换expressiveness**：比SELinux type enforcement简单，难表达复杂information-flow、role/MLS constraint。
- **cache换更新复杂度**：policy change必须正确invalidate相关decision，online availability不应留下stale allow。
- **coexistence换统一性**：DAC、USEC与其他LSM共同决定结果，auditing/troubleshooting需要理解组合语义。

## 实验与结果

- 等价security requirements下，USEC policy source最多比SELinux少10×；UOS production policy的module/context数量也显著下降（§6.1）。
- Filebench五种workload平均相对LSM-disabled degradation：USEC 6.87%、SELinux 10.86%、AppArmor 9.51%（表 4）。
- Nginx throughput为92,185 req/s，距disabled baseline 4.32%；SELinux为84,748 req/s、下降12.04%。USEC P99 12.140 ms，SELinux 12.990 ms（表 5）。
- across representative workloads，相对SELinux runtime overhead降低3.4%–17.1%；compatibility case展示可保护选定资源而不阻断SELinux不兼容应用（§6.2–§6.3）。
- Operational evidence：超过210 security vendors采用，截至early 2025部署超过8,000,000 enterprise endpoints，覆盖finance、energy、transportation（§1）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| resource-centric policy降低配置量 | §1、§6.1 | UOS/等价policy case | 强 |
| demand-driven enforcement降低开销 | 表 4/5 | Filebench、Nginx、同机对照 | 强 |
| 兼容性优于全局SELinux policy | §6.3 case studies | 选定应用/资源 | 中 |
| 框架可大规模部署 | operational deployment | 800万endpoints、vendor报告 | 强 |
| 提供“SELinux-level”通用安全性 | 设计/攻击讨论 | opt-in resource scope | 中 |

## 批判性分析

### 论证链条

USEC将安全系统的中心问题从“更强expressiveness”改成“让关键保护真正被启用”。policy-size、performance、compatibility与deployment四类证据能解释为何产品愿意采用，这是Operational Systems论文的优势。

### 假设压力测试

如果administrator遗漏credential、socket或transitive dependency，USEC会让路径回退DAC，简洁性直接转化为coverage风险。动态resource、container namespace、rename/hardlink/mount alias可能让“资源中心”匹配比静态path复杂。cache invalidation与online update race也是security-critical correctness点。

### 实验可信度

每项benchmark多次运行并报告variance、production规模极强；但policy equivalence由作者定义，尚缺独立attack corpus验证SELinux和USEC在相同threat model下确实阻断同一行为。800万deployment说明可运维，不等同于经过800万endpoint的安全有效性实验。

### 系统性缺陷

opt-in MAC更像targeted hardening而非默认deny的complete mediation。与多LSM共存会产生policy composition、audit attribution和precedence问题。论文没有充分量化policy omission、rule update failure或cache poisoning后的fail-safe行为。

## 局限与后续工作

- 用公开attack suites与formal resource-coverage model验证和SELinux的保护等价性。
- 对rename/mount namespace/container/TOCTOU及policy hot-update并发做系统性fuzzing。
- 提供coverage lint与least-privilege learning工具，明确标出未受USEC保护、仅依赖DAC的访问路径。

## 相关

- **相关概念**：[[Mandatory-Access-Control]]、[[Linux-Security-Modules]]、[[Least-Privilege]]、[[Decision-Cache]]
- **相关系统**：[[SELinux]]、[[AppArmor]]、[[UOS]]
- **同会议**：[[OSDI-2026]]
