---
type: paper
name: pKVM-GhostShell
full_title: "Ghost in the Android Shell: Pragmatic Test-oracle Specification of a Production Hypervisor"
authors: [Kayvan Memarian, Ben Simner, David Kaloper-Meršinjak, Thibaut Pérami, Peter Sewell]
venue: SOSP
year: 2025
tags: [formal-methods, hypervisor, pkvm, android, testing, specification]
source_pdf: "[[3731569.3764817.pdf]]"
source_md: "[[3731569.3764817]]"
---

# Ghost in the Android Shell: Pragmatic Test-oracle Specification of a Production Hypervisor (SOSP 2025)

> **一句话总结**：不做完整 formal verification，而是用 C 本身写一个可执行的 test-oracle specification（抽象函数 + ghost state），在 runtime 对比 pKVM 实际行为，以较低代价找到多个 critical bug。

## 问题

生产系统代码的安全保证仍极难给：传统 testing 不够；完整 formal verification（seL4、CertiKOS、Hyper-V 等）需要特种语言/工具、初始投入巨大、维护成本高、奖励是 all-or-nothing 的"定理"。Lightweight formal methods 被讨论几十年但仍未被广泛采纳。目标系统是 Google 为 Android 13+ 开发的 protected KVM (pKVM) hypervisor——运行在 Arm EL2、并发、用 C+汇编、管理 stage-2 页表，不是为验证而写。

## 核心方法

沿用 1970s 就有的"写一份能作为 test oracle 的 spec + runtime 对照"思路，但做在生产 hypervisor 上。关键设计：

- **用 C 写 spec**：抽象函数（reified in C、链接进可执行文件）把具体实现状态映射到抽象 ghost state（finite map 表示 Arm 页表，对应架构 spec）；再用一个 pure 计算函数描述每次 exception/hypercall 后的 abstract state 转换，runtime 比对即可
- **处理并发**：只在 pKVM 拥有某段 state 的时刻（典型是拿/放特定锁时）计算该段抽象——spec 的抽象结构镜像实现的 ownership discipline，类似 separation logic 但落地为 runtime 代码
- **loose specification**：对 on-demand mapping 细节和 OOM 报告时机用 parametric next-state 函数放宽
- **EL2 测试基础设施**：hyp-proxy 内核补丁让 user-space test 能分配 kernel 内存并发 hypercall；自写 coverage 工具；手写测试 + 带"抽象模型"引导的随机测试器（避免盲测崩系统）
- **绕开 C 的缺陷**：用 struct/union/enum 手工编码 inductive datatype，用 union of types 模拟多态

## 关键结果

- 在 pKVM 中找到**多个 critical bug**（§6 详细讨论）
- 证明即便 spec 语言是 C，且面对 bare-metal、并发、loose spec、随机测试易崩系统等挑战，test-oracle 方式仍可行
- 开发者可独立阅读/评审 spec（比专用 spec 语言更易接受）
- 开源在 github.com/rems-project/linux 的 pkvm-verif-6.4 分支
- 不覆盖 side-channel、liveness、device emulation、GIC/IOMMU

## 相关

- **相关概念**：形式化验证、Runtime monitoring、Separation logic
- **同类工作**：seL4、CertiKOS、SeKVM、S3 key-value node（Bornholt et al.）
- **同会议**：[[SOSP-2025]]
