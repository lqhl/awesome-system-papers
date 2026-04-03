# LITESHIELD: Secure Containers via Lightweight, Composable Userspace µKernel Services

**作者**：Kaesi Manakkal, Nathan Daughety†, Marcus Pendleton†, Hui Lu（The University of Texas at Arlington, †Air Force Research Laboratory (AFRL)）
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/manakkal
**源文件**：[[atc2025-manakkal.pdf]]

---

## 一、背景

容器因高可移植性、高密度和低运维成本在云原生环境中被广泛采用。然而，容器直接共享宿主 OS 内核，暴露了 300+ 系统调用的攻击面，无法满足多租户云环境的强隔离需求。当前生产系统的常见做法是将容器部署在 VM 内以获得强隔离。

现有隔离方案形成了一个频谱：VM（hypervisor + guest kernel，强隔离但重）、unikernel（单地址空间，轻量但缺灵活性）、micro-VM（Firecracker、gVisor 等，在中间取折衷）。这些方案都试图在**隔离强度**与**性能开销**之间找平衡，但各有局限。

云原生的微服务架构进一步放大了这个矛盾：每个微服务都需要沙箱化，服务数量多且生命周期短（ephemeral），使虚拟化开销被显著放大。

---

## 二、要解决的问题

1. **隔离 vs. 性能的根本矛盾**：VM 级隔离开销大（hypervisor 层、VM Exit/Entry、双重缓存），容器级隔离攻击面大（250+ syscalls 即使有 seccomp 白名单）。现有方案在两者之间难以兼顾。

2. **Guest kernel "one-size-fits-all" 问题**：不同微服务需要不同的系统服务（定制化网络栈、专用文件系统等），但现有方案为每个 sandbox 配备完整或精简的通用 guest kernel，无法按需定制。

3. **攻击面仍然较大**：即使是 micro-VM 方案（如 Firecracker），hypervisor 本身的代码量巨大（QEMU 超过 140 万行），且 CVE 记录显示主流 hypervisor 自 2007 年以来报告了 184 个漏洞，其中 33% 发生在近 1.5 年。

4. **无法利用用户态高性能系统服务**：近年来涌现了大量高性能用户态网络栈和文件系统（如 DPDK、f-stack），但没有实用的方式将其无缝集成到通用应用隔离环境中。

---

## 三、洞察与设计

**关键洞察**：传统隔离架构将 guest kernel 作为不可分割的整体绑定到每个应用上，但实际上 guest kernel 的大部分功能（网络、文件系统、IPC 等）可以从应用中解耦出来，作为独立的用户态进程运行，通过共享内存 IPC 而非 syscall 与应用通信。这样既能将 user-to-host 接口缩减到 VM 级别（仅 22 个 syscalls），又能避免 hypervisor 和硬件虚拟化的开销。

**系统架构**：LITESHIELD 借鉴微服务架构，将 guest kernel 功能拆分为模块化的用户态 µkernel 服务：

- **Core services**（每个应用必需）：IPC 管理、syscall 仲裁、时间管理、内存管理
- **Composable services**（按需组合）：文件系统、网络、设备管理等

**Syscall 分类与处理**：
- **Delegable syscalls**（~142 个）：通过 POSIX 兼容库拦截，重定向到用户态 µkernel 服务处理
- **Non-delegable syscalls**（~28 个）：必须在原进程上下文执行的调用（如 fork、mmap），通过 ptrace 机制进行拦截、监控和验证后放行

**隔离机制**：
- 用 seccomp 默认阻断 guest 应用的所有直接 syscall
- µkernel 服务也受 seccomp 限制，仅允许最小必要 syscall 集
- 即使 µkernel 服务被攻破，攻击者也只能获得一个受限用户态进程的权限（defense in depth）

**IPC 机制**：
- 每个应用分配一块共享内存 buffer，应用将 syscall 号和参数写入 buffer 并置标志位
- µkernel 服务端用 polling thread 持续监测请求，处理完将结果写回 buffer
- 利用多核系统将应用和 µkernel 服务放在不同核心上，避免同核上下文切换，利用 LLC cache-to-cache 传输（仅需数十 CPU cycles）

---

## 四、实现细节

- 总代码量约 **7,000 行 C/C++**
- 支持约 170 个 Linux syscall（142 delegable + 28 non-delegable），user-to-host 接口仅 22 个 syscall
- 约 132 个需要 root 权限的 syscall 暂不支持

**POSIX 兼容库**：结合 LD_PRELOAD（运行时注入库、覆盖 glibc 函数）和 libsyscall_intercept（inline hooking + binary rewriting 拦截 syscall 执行路径），实现对 legacy 应用的零修改支持。

**用户态网络栈**：移植了基于 DPDK 的 f-stack，仅需 400+ 行适配代码。f-stack 从 IPC shared buffer 获取请求，入队到操作队列处理，结果写回 buffer。每个 f-stack 实例绑定一个 software tap device，支持多容器共享物理网卡。

**用户态文件系统**：从头实现了 ext2 兼容的用户态文件系统，具有简化的 page cache 机制，避免 VM 场景下的 double caching 问题。

**Non-delegable syscall 仲裁**：应用启动时注册为 core µkernel service 的 ptrace tracee，后续所有 non-delegable syscall 被 ptrace 拦截，核心服务执行 sanity check 后放行。

---

## 五、实验结果

**实验平台**：Intel Xeon Gold 6430, 96GB DDR5, Micron 7450 NVMe SSD (ext4), Ubuntu 22.04, Linux 5.15。对比 Docker、KVM VM、Firecracker (v1.10.1)、gVisor (v1.10.1, sysrap mode)。所有方案配置 16 核 32GB RAM。

| 评测项 | LITESHIELD 表现 | 对比 |
|---|---|---|
| getpid 延迟 | 显著低于 gVisor | 与 KVM/Firecracker 相当 |
| read 延迟（4GB 文件 1B/block） | 优于所有 VM 方案 | 甚至优于 native（得益于轻量用户态 FS） |
| ptrace 开销 | mmap: 25.5µs (99.1% overhead), fork: 35.7µs (46.8%), clock_nanosleep: 23.3µs (29.0%), futex: 15.5µs (98.4%) | 轻量 syscall overhead 比重大，但这些调用频率低 |
| UDP 网络 | 优于所有隔离方案 | 接近 native |
| TCP 网络 | 小包与其他方案相当 | 大包落后 Firecracker（f-stack 缺 GRO 特性） |
| Direct I/O 写（4GB 文件） | 小 block size 优于 KVM 和 native | 大 block size (1MB) 略低 |
| Cached I/O 写 | 线程数增加时扩展性最佳 | 简化 page cache 机制的优势 |
| Redis + YCSB | 四种 workload 均优于 native | 优于 Firecracker 和 gVisor |

---

## 六、批判性分析

1. **ptrace 开销被轻描淡写**：论文称 non-delegable syscalls "generally invoked infrequently"，但 mmap 和 futex 在许多真实工作负载中调用频率极高（如 malloc 频繁触发 mmap，多线程应用大量使用 futex）。99% 的 overhead 对这些场景可能造成严重影响，但论文未用任何 syscall trace 数据证明其频率确实低。

2. **网络实验设置不充分**：UDP/TCP 测试使用 veth pair 连接，这是一个极简拓扑，无法反映真实云环境的网络复杂性。f-stack 缺少 GRO 是一个已知的基本特性缺失，论文以"没有 one-size-fits-all 方案"一笔带过，但这在大包传输场景下是硬伤。

3. **安全性声明过于乐观**：论文声称 22 个 syscall 接口与 VM 的 20+ hypercall 相当，但 syscall 和 hypercall 的攻击面并不直接可比——单个 syscall（如 ioctl）的攻击面可能远大于多个 hypercall 的总和。论文缺乏对这 22 个 syscall 的具体攻击面分析。

4. **实用性限制被低估**：statically linked 应用和 inline assembly syscall 指令会绕过拦截库，论文仅在 Future Work 中提及"hot patching"方案，但这在实际部署中是一个严重的兼容性问题。Go 语言的运行时就使用 raw syscall 指令。

5. **缺乏多租户场景评测**：论文的威胁模型是多租户隔离，但所有实验都是单容器性能测试，没有评估多容器共享 µkernel 服务时的性能干扰和隔离效果。

6. **用户态文件系统仅实现 ext2 级别**：ext2 不支持 journaling，在崩溃一致性方面远不如现代文件系统。论文中 LITESHIELD 的 FS 性能优势部分来自于功能简化，这不是公平比较。

---

## 七、总结

LITESHIELD 提出了一种将 guest kernel 解耦为用户态 µkernel 服务的容器隔离架构，通过共享内存 IPC 和 seccomp 实现了仅 22 个 syscall 的 thin user-to-host 接口，在保持 VM 级隔离强度的同时避免了 hypervisor 开销。其 composable µkernel 服务的设计允许按需集成高性能用户态组件。主要局限包括 ptrace 对 non-delegable syscall 的高开销、对 statically linked 应用的兼容性问题，以及缺乏多租户场景的实际验证。
