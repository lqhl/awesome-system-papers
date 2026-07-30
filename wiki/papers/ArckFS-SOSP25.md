---
type: paper
name: ArckFS
full_title: "Analyzing and Enhancing ArckFS: An Anecdotal Example of Benefits of Artifact Evaluation"
authors: [Jonguk Jeon, Subeen Park, Sanidhya Kashyap, Sudarsun Kannan, Diyu Zhou, Jeehoon Kang]
venue: SOSP
year: 2025
tags: [artifact-evaluation, nvm, userspace-filesystem, reproducibility, short-paper]
source_pdf: "[[3731569.3768291.pdf]]"
source_md: "[[3731569.3768291]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 分析和增强 ArckFS：工件评估好处的轶事示例（SOSP 2025）

> **原题**：Analyzing and Enhancing ArckFS: An Anecdotal Example of Benefits of Artifact Evaluation

> **一句话总结**：这项定向 artifact evaluation 复核 SOSP'23 Trio/ArckFS，识别 1 个表述问题和 6 个 implementation bugs；修补后的 ArckFS+ 在 48-thread FxMark 上达到 ArckFS metadata throughput 的 97.23% geomean。作者称此次复核未发现 inherent vulnerability，但这不是 exhaustive audit（§3.2、§4、§5.2，Fig. 4，Table 1–2）。

## 问题与动机

Trio/ArckFS（SOSP 2023）用 userspace [[NVM]] FS + lazy metadata verification（inode 所有权转移时验证）平衡 KucoFS/SplitFS 的「每次验证贵」与 ctFS 的「不验证不安全」。论文对跨目录 rename 等多 inode 操作表述不清；released artifact 含 memory fence 缺失、并发 bug，原 benchmark 未触发。

## 关键观察 / 隐含假设

- **观察 1**：cross-directory rename 的 Rules 1–2 规定 verification/release 顺序，Rule 3 打破两者形成的循环依赖；Invariant I3 由 verifier 检查，而不是三条规则共同“证明”（§3.2、§4.1）。
  - **依赖假设**：verifier 代码审查可抽取完整规则；规则充分非必要已够用。
  - **可能失效场景**：更复杂多 inode 操作（hardlink+rename 组合）仍有未覆盖规则。
  - **证据强度**：中——与原作者协作澄清，无新架构漏洞。
- **观察 2**：inode 创建路径 dentry/inode 持久化间缺 memory fence 可导致 partial persist crash inconsistency。
  - **依赖假设**：补 fence 即可；无更广泛 ordering bug。
  - **可能失效场景**：其他 create/unlink 路径仍有 fence 遗漏（论文只修 identified bug）。
  - **证据强度**：强——具体 patch + 复现路径。
- **假设 1**：并发与持久化 bug 修补后的性能影响在所测 workload 上总体有限，但不均匀。
  - **证据强度**：强——FxMark geomean 97.23%，但单项最低 75.45%，单线程 open 仅为原版 83.3%（§5.1–5.2，Fig. 3–4）。

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

- **Artifact findings**：相对 Trio SOSP'23 artifact commit `8fa7f83`，论文识别 1 个 presentation issue 与 6 个 bugs：cross-directory rename、crash inconsistency 和 4 个 concurrency bugs（§3.2、§4.1–4.6，Table 1；部分并发问题以 `sleep()` 放大，非 exhaustive audit）。
- **FxMark**：48 threads 下，ArckFS+ 相对 ArckFS metadata throughput geomean 为 97.23%，单项范围 75.45%–154.70%（§5.2，Fig. 4，Table 2；2×24-core Xeon 6248R、384GB DRAM、1.5TB Optane）。
- **Single-thread metadata**：open/create/delete throughput 分别为 ArckFS 的 83.3%/92.8%/92.2%；作者将回退归因于 RCU read-side section 与新增 memory fence（§5.1，Fig. 3；不能外推所有 data paths）。
- **Filebench**：重建的 shared-directory framework 中，Webproxy/Varmail 在 1 thread 为 101.1%/102.1%，16 threads 为 97.1%/98.8%（§5.3；该 framework 与原 Filebench 和 Trio private-directory artifact 都不同）。
- **Sharing cost**：4KB write/1GB 时 ArckFS+ / NOVA / trust-group 为 0.41/1.16/1.80 GiB/s；Create-10 为 10.18/6.38/0.76 微秒（§5.4，Table 4；trust group 放松安全边界）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 定向 artifact review 识别并修复 6 个 implementation bugs | §3.2, §4.1–4.6, Table 1 | Trio commit 8fa7f83；部分 bug 以 sleep 放大；非 exhaustive | strong |
| ArckFS+ 在 48-thread FxMark 上保持 97.23% geomean throughput | §5.2, Fig. 4, Table 2 | dual 24-core Xeon；Optane；修改后的 FxMark workload | strong |
| Correctness patches 对单线程 metadata 产生不均匀回退 | §5.1, Fig. 3 | open/create/delete；同机 microbenchmark | strong |
| Shared-directory Filebench 中 ArckFS+ 与 ArckFS 接近 | §5.3 | rebuilt framework；1/16 threads；per-filename locks | strong |
| Trust group 提高 sharing performance 但改变安全边界 | §5.4, Table 4 | Trio §6.5 configs；4KB write / Create-10 | medium |

## 批判性分析

### 论证链条

「AE 价值 → 发现 presentation+implementation 问题 → 协作修复」叙事完整，支持 SOSP AE 政策，但不构成新系统贡献。

### 假设压力测试

- 未触发 bug 是否意味其他路径仍有问题？short paper 明确「无架构级漏洞」但非 exhaustive。
- 其他 Trio-based FS 是否共享同类 fence 模式？
- open 相对 ArckFS 为 83.3%，即约 16.7% 回退；作者归因于新增 RCU read-side critical section（§5.1，Fig. 3）。

### 实验可信度

与原版对比公平（同 benchmark）。单线程 open 偏低值得 follow-up。缺新安全 property 的形式化陈述。

### 系统性缺陷

论文未讨论：修复后 verifier 规则的形式化规范；对其他 userspace NVM FS 的迁移清单。

## 局限与后续工作

- **局限 1**：short paper，audit 范围有限。
- **局限 2**：open 路径仍有 ~17% 性能差距。
- **Future work 1**：将三条多 inode 规则写入 Trio verifier 形式化 spec 并 machine-check。

## 相关

- **相关概念**：[[NVM]]、userspace file system、artifact evaluation、crash consistency
- **同类系统**：Trio、ArckFS、KucoFS、SplitFS、ctFS、NOVA
- **同会议**：[[SOSP-2025]]
