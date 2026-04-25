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

> **一句话总结**:Short paper——KAIST 通过复核 SOSP 2023 的 Trio/ArckFS 论文和 artifact,发现多 inode 操作规则表述不清 + 6 个实现 bug(memory fence 漏、并发问题),与原作者合作修出 ArckFS+,性能基本保持(单线程 create 92.8%、open 83.3%;多线程 FxMark 97.23% geomean)。

## 问题

Trio/ArckFS(SOSP 2023)用 userspace [[NVM]] 文件系统 + 懒验证(只在 inode 所有权转移时验证元数据)在 KucoFS/SplitFS 的"每次验证贵"与 ctFS 的"不验证不安全"之间找平衡。但论文对跨目录 rename 等多 inode 操作讨论有限,且 artifact 中有若干 bug 在原评测中未触发。

## 核心方法

三类修补:

- **多 inode 操作规则澄清**:原实现阻止合法的跨目录 rename。重看 verifier 代码后,总结出 LibFS 必须满足的 3 条隐含规则(如:非空目录 relocation 前要先 commit 新父目录),保证 Trio 的 Invariant I3("FS 层次是连通树")不被攻击者绕过。
- **Crash consistency 修复**:inode 创建时 dentry 与 inode 的持久化之间缺一个 memory fence,可能导致部分持久化状态;补上 fence。
- **并发 bug 修复**:artifact 存在 segfault、目录 cycle 等并发问题,细致补强 concurrency control,性能影响最小。

## 关键结果

- FxMark 48 线程下 ArckFS+ 达到原 ArckFS 的 97.23% geomean。
- 单线程 create/open 分别 92.8%、83.3%。
- Filebench Webproxy/Varmail 16 线程下 97.1%、98.8%。
- 宏观上基本保留原论文的性能声明。
- 无 Trio 架构级漏洞,只是实现层和表述层问题。

## 相关

- **相关概念**:[[NVM]]、userspace file system、artifact evaluation、crash consistency
- **同类系统**:Trio、ArckFS、KucoFS、SplitFS、ctFS、NOVA、PMFS
- **同会议**:[[SOSP-2025]]
