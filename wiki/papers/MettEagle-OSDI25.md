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

> **一句话总结**：在 L4Re 微内核之上实现的容器引擎 MettEagle，利用 capability 原生替代 seccomp-bpf/namespace/cgroups，TCB 缩至 Linux 的 3%，33 个相关 CVE 中 30 个得到全/部分缓解，同时容器冷启动比 runC 更快（1 ms vs 70 ms）。

## 问题

Linux 上实现容器需要在单体内核里叠加 seccomp-bpf、namespaces、cgroups 等复杂机制来弥补进程默认拥有 ambient authority 的缺陷。这些机制自身成为攻击面，过去十年产生了大量 CVE（33 个高危相关），并给内核带来运行时开销。而 Firecracker 这类 lightweight VM 方案以牺牲启动时间为代价。

微内核天生遵循最小权限原则（PoLA）：task 默认无任何 capability，必须显式请求。理论上不需要 seccomp 这类补丁式限制就能自然实现容器隔离。但业界担心：微内核是否能扛住**服务器级硬件 + 动态 serverless workload**？性能是否可接受？论文就是要证明这两点。

## 核心方法

作者在 L4Re 微内核之上构建 **MettEagle** 容器引擎，由 compartment service（低阶运行时，类比 runC）和 Phlox（高阶 FaaS runtime，类比 containerd）组成。每个容器（这里叫 compartment）由 task 集合组成，只持有 MettEagle 显式下发的 capabilities。Linux 的 namespace/seccomp/cgroups 分别映射为：capability 集合决定可见性；每个系统服务在不同 session 暴露不同 IPC gate 决定可用系统调用；session 中挂 resource consumption context 做资源配额。

为适配服务器负载，作者给 L4Re 做了多项改造：并行化的内存管理 **LSMM**（基于 LLFree page frame allocator），并行的 boot 文件系统 **PROMFS**，内存文件系统 **SPAFS**，以及用户态 NIC 驱动和 UDP 栈 **LUNA**。还针对发现的性能问题提出 callback 替代一次性 reply capability、线程池避免 unmap 关键路径、capability 数据结构细粒度锁等优化。为跑 FaaS 还把 Python3 port 到 L4Re 上。

安全论证是核心贡献之一：基于 CVE 研究法，筛选出 33 个 seccomp/BPF/namespaces/cgroups 相关的 Linux 内核 CVE，逐条分析 MettEagle 是否能缓解——14 个完全缓解、16 个部分缓解、3 个不缓解。同时 TCB SLOC 从 Linux 的约 270 万行缩到 MettEagle 的约 8.7 万行（含 L4Re kernel 4.1 万 + 用户态组件）。

## 关键结果

- TCB：MettEagle 约 **86,651 SLOC** vs Linux 容器栈约 **2,699,812 SLOC**（约 **31× 更小**）
- 33 个相关高危/严重 CVE 中 **14 完全缓解 + 16 部分缓解 + 3 不缓解**
- 单容器冷启动：L4Re **1 ms** vs runC **70 ms** vs Kata+Firecracker 更高；64 并发启动 L4Re 100 ms vs runC 200 ms
- SeBS serverless benchmark：除 ZIP 外 L4Re 相比 runC 差距在 **15% 以内**，HTML 甚至快 10%
- UDP 带宽：多 socket 下可达 10 GbE 线速；单 socket Linux 900 MiB/s vs L4Re 350 MiB/s（微内核 NIC 栈单核处理）

## 相关

- **相关概念**：capability-based security、microkernel、PoLA、seccomp-bpf、namespaces、cgroups、FaaS
- **同类系统**：seL4、runC、Firecracker、Kata Containers、BlackBox、unikernel
- **相关实体**：L4Re、Fiasco 微内核、SeBS benchmark
- **同会议**：[[OSDI-2025]]
