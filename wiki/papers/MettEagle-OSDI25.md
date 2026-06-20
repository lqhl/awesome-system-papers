---
type: paper
name: MettEagle
full_title: "MettEagle: Costs and Benefits of Implementing Containers on Microkernels"
authors: [Till Miemietz, Viktor Reusch, Matthias Hille, Lars Wrenger, Jana Eisoldt, et al.]
venue: OSDI
year: 2025
tags: [microkernel, container, serverless, l4re, security]
source_pdf: "[[osdi25-miemietz.pdf]]"
source_md: "[[osdi25-miemietz]]"
---

# MettEagle: Costs and Benefits of Implementing Containers on Microkernels (OSDI 2025)

> **一句话总结**：L4Re 微内核上 MettEagle 用 capability 原生实现容器级隔离，TCB 约为 Linux container 栈 3%，33 个相关 CVE 中 30 个全/部分缓解，冷启动 1ms（N=1）快于 runC 70ms，SeBS FaaS 端到端与 runC 差距 ≤15%。

## 问题与动机

Linux 容器靠 seccomp-bpf、namespaces、cgroups 在「进程默认 ambient authority」之上 retroactive 加固——机制复杂、攻击面大（十年 33+ 高危 kernel CVE）。微内核 PoLA 设计下进程无 ambient authority，compartment 是否可用更 lean、更安全？论文在 L4Re 上实现 MettEagle（compartment service + Phlox FaaS runtime），对比 runC/Firecracker 的安全与性能。

## 关键观察 / 隐含假设

- **观察 1**：Linux 容器隔离机制（seccomp/namespace/cgroup）SLOC 远大于 L4Re kernel（41k vs 1.45M+ 用户态 containerd/runc）；33 个高危 CVE 中 6 个 FM、多数 PM——因 MettEagle 无 eBPF/seccomp/namespace 等价物。
  - **依赖假设**：SLOC/CVE 计数可代表攻击面趋势；研究原型功能少于 containerd 但 TCB 对比方向有效。
  - **可能失效场景**：L4Re capability 实现自身存在等价内存 bug（论文列为 NM 类）；userspace service misconfiguration 仍可导致 compartment 间泄露。
- **观察 2**：冷启动 N=1：L4Re compartment ~1ms vs runC ~70ms vs Firecracker 更高——IPC gate callback、thread pool 规避 revocation 阻塞是关键实现教训。
  - **依赖假设**：双二进制加载（helper+app）是 L4Re 当前开销主因，可优化；无 warm-start 是公平对比但低估 production FaaS。
  - **可能失效场景**：64 并行启动 L4Re 峰值 100ms（capability map/unmap 锁）；moe 单锁瓶颈。
- **假设 1**：原生 L4Re 系统服务（SPAFS/LUNA/python3）而非 L4Linux VM 才能保持小 TCB 同时接近容器性能。
  - **证据强度**：强；L4Linux per-compartment VM 被明确否决。

## 核心方法

**隔离映射**：visibility→capability delegation；syscall restriction→per-session IPC gate；resource budget→session 附 consumption context（类 cgroups 但 per-service）。

**生命周期**：Phlox 建 session 收 capability → compartment service 启动 task → 退出后 revoke capability 回收（revocation 移出 hot path）。

**实现**：LSMM/PROMFS 并行化 moe；SeBS python FaaS benchmark；CVE 分类研究 + TCB SLOC。

## 设计取舍

- **取舍 1**：无 OCI 镜像/runC 兼容——POSIX 层与 OCI 需大量移植（§7）。
- **取舍 2**：UDP 栈 LUNA 单核驱动，低并行时带宽低于 Linux（350 vs 900 MiB/s），高并行可达线速。
- **边界条件**：研究原型；SPAFS 无 disk backend；FFmpeg/fork 等 benchmark 未移植。

## 实验与结果

- 冷启动：L4Re 1ms（N=1）→100ms（N=64）；runC 70ms→200ms；idle container 数量不影响启动。
- 网络：UDP ping-pong ~40µs 各平台相当；高并行 L4Re 线速，Linux 反而下降。
- SeBS：除 ZIP 外端到端与 runC 差距 ≤15%，HTML 快 10%；python 纯执行 L4Re 更慢但快启动抵消；Kata 最慢。
- 安全：TCB ~3% of Linux stack；30/33 CVE mitigated。

## Critical Analysis

### 论证链条

「PoLA → 无需 retroactive 加固 → 小 TCB + 少 CVE 面」论证直接；性能「可行」靠 SeBS 与 microbench 支撑。文件系统 IPC 慢（stat 10×）解释 python 劣势，归因清晰而非 hand-wave。

### 假设压力测试

- **已证明**：微内核 compartment 在 server 级硬件可跑 FaaS；冷启动显著优于 runC。
- **可能失效**：生产 OCI 生态、多租户 timing attack（论文 §5.3 承认 L4Re 仍有共享调度器/capability 树风险）；并行 spawn 扩展性受锁限制。
- **论文未覆盖**：与 gVisor/Firecracker 安全模型的细粒度对比；真实 cloud 混部 long-running container。

### 实验可信度

对比 runC/Kata/裸进程公平；明确无 warm-start。SeBS 子集省略透明。双 socket Xeon + 10G 网卡环境明确。

### 系统性缺陷

缺 OCI、缺成熟 FS/多核优化；ZIP/graph burst 模式 L4Re 慢 1–2×；capability unmap 10ms tick 阻塞曾迫使大量工程 workaround；论文未 claim production-ready。

## 局限与 Future Work

- **局限 1**：OCI/容器镜像生态未支持；SPAFS 性能瓶颈。
- **局限 2**：并行冷启动扩展性受 kernel/moe 锁限制。
- **Future work 1**：PM 式 shared-memory FS 降 IPC（论文 §7 提议）。
- **Future work 2**：warm-start、per-compartment 系统服务实例调优；seL4 形式化验证路径。

## 相关

- **相关概念**：capability、PoLA、microkernel
- **同类系统**：runC、Firecracker/Kata、seL4、L4Linux
- **同会议**：[[OSDI-2025]]