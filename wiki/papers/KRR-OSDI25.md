---
type: paper
name: KRR
full_title: "KRR: Efficient and Scalable Kernel Record Replay"
authors: [Tianren Zhang, Sishuai Gong, Pedro Fonseca]
venue: OSDI
year: 2025
tags: [kernel, record-replay, virtualization, debugging, kvm]
source_pdf: "[[osdi25-zhang-tianren.pdf]]"
source_md: "[[osdi25-zhang-tianren]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# KRR: Efficient and Scalable Kernel Record Replay (OSDI 2025)

> **一句话总结**：Whole-VM RR 在 8 核 RocksDB/内核编译上慢 **8.97–29.94×**；KRR 只录 kernel slice，split-recorder（guest 录 syscall/copy_from_user/非确定指令，hypervisor 录中断/I/O），内核执行串行化记录调度，8 核仅 **1.52–2.79×**，kernel-bypass 路径 Redis **≤1.05×**。

## 问题与动机

内核规模大、并发 bug 难复现，record-replay 可确定性重放。Mozilla RR 等 whole-VM 方案多核开销常超核数（2 核 VM 已 2.3–3.5×）。数据中心 workload 并发高、I/O 重，且越来越多 kernel-bypass（SPDK 等），whole-VM 录 guest 全部输入浪费。

## 关键观察 / 隐含假设

- **观察 1**：多核上大量 CPU 时间在 user mode，仅 kernel 执行需要串行化记录调度，user 可全速并行。
  - **依赖假设**：目标 bug 在 kernel，replay 不需复现应用层执行细节。
  - **可能失效场景**：bug 根因在 user→kernel 交互时序且需 full-VM 语义时 KRR 非目标（论文 non-goal）。
- **观察 2**：kernel-bypass 下 bulk I/O 不经内核，whole-VM 记录事件暴涨而 kernel RR 可跳过 user 发起的 I/O。
  - **依赖假设**：hypervisor 能区分 kernel vs user 发起的 I/O。
  - **证据强度**：强——§5.2 Redis benchmark 数据。
- **假设 1**：内核 syscall/copy_from_user/io_uring 等入口可穷举插桩；x86 用 KMO-only counter 记异步事件时序。
  - **可能失效场景**：新内核子系统共享内存输入若未插桩会漏录。

## 核心方法

**Split recorder**：in-guest（syscall、user mem read、shared queue、页表 accessed/dirty、RDTSC 等）；hypervisor（中断、kernel 发起 I/O、DMA）。

**调度记录**：RCU/锁等内核串行化点记录顺序；replay 注入同序事件。

**实现**：KVM/QEMU + Linux 修改；x86 实现为主。

## 设计取舍

- **取舍 1**：不 replay 应用，换记录量与串行化范围缩小。
- **取舍 2**：需改 kernel+hypervisor，非纯用户态工具。
- **边界条件**：≤8 核评估；RocksDB、kernel compile、Redis。

## 实验与结果

- 8 核 RocksDB + kernel compile：KRR **1.52–2.79×** vs native；whole-VM **8.97–29.94×**。
- 4 核 Redis（kernel-bypass）：KRR **≤1.05×** throughput。
- 2 核 RocksDB：**1.17–1.26×**。
- **17** 个真实 Linux bug/CVE，**16/17** 成功复现（1 个非确定 bug 失败）。

## Critical Analysis

### 论证链条

双观察支撑 slice RR → split recorder 覆盖输入类 →  scalability 与 bug 复现，证据充分。Replay 速度非目标，调试场景可接受。

### 假设压力测试

新内核版本插桩维护成本？ARM 等其他架构「architecture-agnostic」声称需看实现完整度。漏录 shared-memory 路径是主要风险。

### 实验可信度

与 whole-VM RR 同机对比公平；bug 集含 6 非确定 + 5 CVE 有说服力。

### 系统性缺陷

论文未讨论 trace 存储体积长期增长、生产环境默认开启的性能；多 VM 同 host 干扰未讨论。

## 局限与 Future Work

- **局限 1**：不 replay 用户态，应用致因 bug 超出范围。
- **Future work 1**：自动化插桩覆盖新 shared-memory API。
- **Future work 2**：与 live patching 结合的在线 record 策略。

## 相关

- **同会议**：[[OSDI-2025]]
