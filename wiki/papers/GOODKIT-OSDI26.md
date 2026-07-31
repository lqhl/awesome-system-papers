---
type: paper
name: GOODKIT
full_title: "Inside Out: A Paradigm Shift In VM Introspection"
authors: [Dufy Teguia, Louis Duval, Teo Pisenti, Kahina Lazri, Daniel Hagimont, et al.]
venue: OSDI
year: 2026
tags: [virtual-machine, introspection, security, isolation]
source_pdf: "[[osdi26-teguia.pdf]]"
source_md: "[[osdi26-teguia]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# GOODKIT：从 VMM 内部重构虚拟机内省（OSDI 2026）

> **原题**：Inside Out: A Paradigm Shift In VM Introspection

GOODKIT 将 observer 作为与 target 同属一个 userspace VMM 的轻量 VM，把授权的 target memory 直接映射给 observer，并用 lock-aware coherence 和共享监控层获得接近本地访问的速度与 VM 级隔离。

## 问题与动机

LibVMI 类 out-of-VMM observer 隔离强，却需要 hypervisor 修改、跨 VMM 操作和频繁 pause target；嵌入 VMM 的 observer 快但扩大 TCB、不同 tenant observer 互不隔离；in-guest agent 又可被攻陷的 guest 欺骗。GOODKIT 试图同时获得高频 live introspection、observer isolation、独立计费与无需改 KVM/target 的部署性。

## 关键观察 / 隐含假设

### 关键观察

- target RAM 本来就是 VMM 的 HVA mapping；同一 VMM 可将选定页面注册为 observer VM 的 memory slot，绕过跨进程 LibVMI control path。
- 很多 kernel data structure 有现成 lock；observer 按 guest lock acquisition order 读数据，比暂停整个 VM 更细粒度。
- 多 observers 常重复 page-table translation、process enumeration 与 probe，可由 VMM mutualizer 计算一次后共享。

### 隐含假设

- VMM 与 GOODKIT policy trusted，observer VM isolation 和 seccomp/cgroup 足以阻止越权读写 target。
- observer 知道 target kernel symbols、types 和 lock semantics；semantic gap 并未自动消失。
- 同 VMM 容纳 target 和所有 observers 的故障域扩大是可接受的。

## 核心方法

### 共享 VMM 的 observer VM

GOODKIT 在 Firecracker userspace 内创建 target 与 observer VMs，按 policy 把 target 的 direct-map、per-CPU、vmalloc 或 text regions 映射为 observer 可读内存。KVM 无需修改，target guest 也不安装 agent。

### 一致性策略（Coherence policy）

observer 可选择 lock-free、mutex/spinlock/RWLock-aware 或 pause 等策略，在一致性、捕获率与 target overhead 间权衡。VMM probing subsystem还暴露 I/O、VM exit 和 kernel event。

### Mutualizer

共享层统一采集常用 kernel objects 与 translations，再把结果发给多个 observer，减少重复 target lock acquisition 和遍历；每个 observer 仍运行于独立 VM并单独计费。

## 设计取舍

- colocated VMM 避免 hypervisor patch，却让恶意 observer 与 target 共享 VMM process 的攻击面。
- lock-aware snapshot 不暂停全 VM，但要求正确理解 guest 内核 lock hierarchy，版本升级会破坏 policy。
- direct mapping 实现 native-speed read，access-control bug 的后果也比 RPC 接口更严重。
- mutualization 提高扩展性，却在共享结果的新鲜度与单 observer 特定需求间折中。

## 实验与结果

- 14 个 Phoronix target workload 上，GOODKIT observer 对 target slowdown 最多 1.06 倍；可比 LibVMI observer 造成 5.15–37.6 倍 slowdown（§5.6）。
- lock-based introspection 的 pause/resume 基元相比 LibVMI 最高快 17 倍；完整 policy turnaround 某些 case 最高改善 110 倍。
- 在最高 500 次/秒攻击修改 rate 下，GOODKIT 捕获率约 80%；较低同组速率保持 99%，而 LibVMI 在 200 次/秒时降至约 0.16%。
- ransomware/FIO 场景中，GOODKIT 维持 vanilla 约 875 IOPS，LibVMI 降至 747 IOPS，GOODKIT 相对 slowdown 改善约 1.17 倍；更重 probe 下差距达 1.87 倍。
- 21 个 rootkit、ransomware、liveness 与 scheduler use cases 中，GOODKIT observer code 比 LibVMI 实现短 3–6 倍，主要因共享 translation/coherence helper。
- observer 数量增加会提高 boot time 与运行 overhead；mutualizer 缓解重复工作，但论文实验规模未覆盖 hyperscale 多 tenant observer density。

## 论断—证据表

| 论断 | 机制 | 证据 | 边界 |
|---|---|---|---|
| 同 VMM observer 可兼得隔离与低开销 | observer VM + direct target mapping | target slowdown 最多 1.06 倍 | 共享 VMM 仍是共同故障/攻击域 |
| lock-aware coherence 优于全 VM pause | 获取 guest structure lock | primitive 最高快 17 倍，policy 最高 110 倍 | 依赖 kernel lock knowledge |
| 高频安全监控更完整 | 低延迟 capture loop | 500 modifications/s 仍捕获约 80% | 不是 100%，攻击者仍可竞态逃逸 |
| 多 observer 工作可复用 | mutualized translations/probes | 21 cases，代码缩短 3–6 倍 | 规模与租户隔离评估有限 |

## 批判性分析

### 论证链条

论文系统比较三种 observer placement 的矛盾，再利用 VMM address-space 事实构造“inside out”新点位。microbenchmark、target workload、攻击 capture 与 21 个 use cases 共同支持性能和适用性，而不只展示单一 rootkit detector。

### 假设压力测试

observer 若利用 Firecracker/VMM 漏洞，可能突破 VM 隔离并直接接触 target mapping；错误 lock order 可能死锁或读取不一致状态。target 启用内核地址随机化、加密内存、confidential VM 时，direct map 与语义恢复可能失效。

### 实验可信度

多 use case 和与 LibVMI 的定量比较很强，也披露 capture 非 100%。缺少恶意 observer penetration test、confidential computing、kernel version churn、VMM crash propagation 及大规模多 observer 资源隔离。

### 系统性缺陷

GOODKIT 未消除 semantic gap，只把 observer 搬到更快的位置；21 个 policy 仍需理解 target 内核布局和锁。框架宣称同时隔离 guest 与 provider，但 provider 控制 VMM 和 mapping，不能抵御恶意云运营者。

## 局限与后续工作

- 对恶意 observer、错误 mapping policy 与 VMM exploit 做系统安全评估。
- 支持 confidential VM/加密内存，明确不可直接映射时的退化路径。
- 自动适配 kernel symbols、BTF/types 与 lock changes，降低版本维护成本。
- 在数十 observer/target 和多 tenant 环境评估 mutualizer、公平计费与故障隔离。

## 相关

- [[Virtual-Machine-Introspection]]
- [[LibVMI]]
- [[Firecracker]]
- [[KVM]]
