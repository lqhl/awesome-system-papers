---
type: paper
name: HyperTurtle
full_title: "Accelerating Nested Virtualization with HyperTurtle"
authors: [Ori Ben Zur, Jakob Krebs, Shai Aviram Bergman, Mark Silberstein]
venue: ATC
year: 2025
tags: [virtualization, ebpf, nested-vm, kata-containers, kvm]
source_pdf: "[[atc2025-zur.pdf]]"
source_md: "[[atc2025-zur]]"
---

# Accelerating Nested Virtualization with HyperTurtle (ATC 2025)

> **一句话总结**：嵌套虚拟化（L0-L1-L2）每次 vm-exit 至少 4 次 world switch（1µs+ 各），HyperTurtle 把 L1 hypervisor 关键路径（EPT fault、网络、profiling）封装成 eBPF hyperupcall 安全注入 L0 执行，EPT fault 延迟降 5.1×，Kata 启动加速 27%。

## 问题

Kata containers 等用 nested VM 实现强隔离，但每次 L2 vm-exit 都得通过 L0 转发到 L1 处理，再回 L0 进 L2，至少 4 次 world switch（非嵌套只 2 次）。作者实测：

- EPT fault 处理需要 6 次 world switch，延迟比非嵌套高 5.1×（28.4µs vs 5.6µs）。
- profiling L2 from L1 比 profiling 普通 container 慢 2×、比 L0 profile L1 慢 8×（一次 sample 26 个 world switch）。
- nested-VirtIO 网络路径 3 次 world switch；Direct-Assignment（DVH）虽好但剥夺了 L1 对 L2 的 traffic shaping / routing 控制。
- Kata container 启动比非嵌套慢 2×，其中 EPT fault 占 46%。

现有方案：DVH 牺牲 L1 控制；SVT 依赖 SMT（已逐步淘汰）；PVM/X-Containers 需侵入修改；Peer-Pods 直接绕开嵌套牺牲编排灵活。

## 核心方法

HyperTurtle 受 Hyperupcalls 启发，让 L1 把关键路径逻辑编译成 eBPF program 注入 L0 hook，由 L0 在处理 L2 vm-exit 时直接调用——既消除 world switch、又保留 L1 控制权（因为 eBPF 是 L1 写的）。

设计要点：
- **共享数据**：通过 eBPF map（含新加的 shared-memory PCI device 暴露 array map）+ 新 helper `bpf_probe_read_hyperupcall` 安全访问 L1 物理内存（强制隔离不同 L1 的内存域）。
- **registration**：拆 load 与 link 为两步 hypercall，支持一个 eBPF 挂多个 hook。eBPF verifier 把关，可选 cloud vendor 签名验证（Hornet）。
- **EPT fault hyperupcall**（560 LOC）：在 L0 处理 L2 EPT fault 的步骤 ② 处插 hook；用 L1 预分配的 4096 帧 frame pool 做 EPT_{1→2} 映射；维护 hyperupcall fault log 通知 L1 同步 VMM page table；page fault log + 锁解决与 virtiofsd 等共享内存进程的 race。失败时 fallback 到原路径。
- **网络 hyperupcall**：L1 把 eBPF 挂在 L0 的 vNIC 上（XDP/TC hook），用 DVH 的速度但保留 L1 traffic policy 控制。
- **Profiling hyperupcall**：把 PMC 中断处理 + MSR 配置在 L0 直接做，避免每次 sample 26 次 world switch。

深度细节回 [[atc2025-zur]] 或 [[atc2025-zur.pdf]]。

## 关键结果

- **EPT fault**：average latency 28.4µs → 5.6µs（5.1×），P99 49.1µs → 9.3µs（5.3×）。
- **Kata container 启动**：Node.js 应用启动从 1.5s → 1.1s（27% 加速），与非嵌套 0.7s 接近。
- **网络**：相比 Nested-VirtIO 平均延迟降 33%；memcached 在 500µs SLO 下吞吐升 72%，与普通 container 持平，且仍兼容 Kubernetes CNI。
- **Profiling**：sampling 延迟降 7× （L1→L2 case）。
- 实现简洁：主要改动在 KVM 模块；EPT fault 这个最复杂的 hyperupcall 仅 560 LOC。

## 相关

- **相关概念**：[[eBPF]]、[[Nested-Virtualization]]、[[KVM]]、[[Kata-Containers]]、[[VM-Exit]]、[[EPT]]
- **同类系统**：Hyperupcalls、DVH、SVT、PVM、X-Containers、Peer-Pods、Free-The-Turtles
- **同会议**：[[ATC-2025]]
