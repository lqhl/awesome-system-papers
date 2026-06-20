---
type: paper
name: ArckFS+
full_title: "Analyzing and Enhancing ArckFS: An Anecdotal Example of Benefits of Artifact Evaluation"
authors: [Jonguk Jeon, Subeen Park, Sanidhya Kashyap, Sudarsun Kannan, Diyu Zhou, Jeehoon Kang]
venue: SOSP
year: 2025
tags: [artifact-evaluation, nvm, userspace-filesystem, reproducibility, short-paper]
source_pdf: "[[3731569.3768291.pdf]]"
source_md: "[[3731569.3768291]]"
---

# Analyzing and Enhancing ArckFS: An Anecdotal Example of Benefits of Artifact Evaluation (SOSP 2025)

> **一句话总结**：Artifact evaluation 复核 SOSP'23 Trio/ArckFS，澄清多 inode 规则并修 6 个 bug，ArckFS+ 性能为原版 **97.23%** geomean（FxMark 48 线程），论证 lazy verification 架构无根本漏洞。

## 问题与动机

Trio/ArckFS（SOSP 2023）用 userspace [[NVM]] FS + lazy metadata verification（inode 所有权转移时验证）平衡 KucoFS/SplitFS 的「每次验证贵」与 ctFS 的「不验证不安全」。论文对跨目录 rename 等多 inode 操作表述不清；released artifact 含 memory fence 缺失、并发 bug，原 benchmark 未触发。

## 关键观察 / 隐含假设

- **观察 1**：多 inode 操作（cross-directory rename）需要 LibFS 满足三条隐含规则才能保证 Invariant I3（FS 层次为连通树）；原实现错误阻止合法 rename。
  - **依赖假设**：verifier 代码审查可抽取完整规则；规则充分非必要已够用。
  - **可能失效场景**：更复杂多 inode 操作（hardlink+rename 组合）仍有未覆盖规则。
  - **证据强度**：中——与原作者协作澄清，无新架构漏洞。
- **观察 2**：inode 创建路径 dentry/inode 持久化间缺 memory fence 可导致 partial persist crash inconsistency。
  - **依赖假设**：补 fence 即可；无更广泛 ordering bug。
  - **可能失效场景**：其他 create/unlink 路径仍有 fence 遗漏（论文只修 identified bug）。
  - **证据强度**：强——具体 patch + 复现路径。
- **假设 1**：并发 bug 修补强控制后性能影响最小。
  - **证据强度**：强——FxMark/Filebench 97–102% 性能保持。

## 核心方法

三类修补（ArckFS+）：

1. **多 inode 规则澄清**：总结 3 条 LibFS 规则，修复非法拒绝合法 cross-directory rename
2. **Crash consistency**：inode 创建补 memory fence
3. **并发**：修 segfault、directory cycle 等，增强 concurrency control

KAIST 与 Trio 原作者合作完成。

## 设计取舍

- **取舍 1**：short paper 深度有限，非全面 re-audit 全部代码路径。
- **取舍 2**：性能优先的 minimal patch，非重写 verifier。
- **边界条件**：ArckFS artifact 覆盖的 benchmark/workload。

## 实验与结果

- FxMark 48 线程：**97.23%** geomean vs ArckFS
- 单线程 create/open：**92.8%** / **83.3%**
- Filebench Webproxy/Varmail 16 线程：**97.1%** / **98.8%**
- 宏观保留 Trio 论文性能声明

## Critical Analysis

### 论证链条

「AE 价值 → 发现 presentation+implementation 问题 → 协作修复」叙事完整，支持 SOSP AE 政策，但不构成新系统贡献。

### 假设压力测试

- 未触发 bug 是否意味其他路径仍有问题？short paper 明确「无架构级漏洞」但非 exhaustive。
- 其他 Trio-based FS 是否共享同类 fence 模式？
- open 83.3% 回归原因未深入。

### 实验可信度

与原版对比公平（同 benchmark）。单线程 open 偏低值得 follow-up。缺新安全 property 的形式化陈述。

### 系统性缺陷

论文未讨论：修复后 verifier 规则的形式化规范；对其他 userspace NVM FS 的迁移清单。

## 局限与 Future Work

- **局限 1**：short paper，audit 范围有限。
- **局限 2**：open 路径仍有 ~17% 性能差距。
- **Future work 1**：将三条多 inode 规则写入 Trio verifier 形式化 spec 并 machine-check。

## 相关

- **相关概念**：[[NVM]]、userspace file system、artifact evaluation、crash consistency
- **同类系统**：Trio、ArckFS、KucoFS、SplitFS、ctFS、NOVA
- **同会议**：[[SOSP-2025]]