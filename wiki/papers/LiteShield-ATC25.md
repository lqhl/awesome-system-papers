---
type: paper
name: LiteShield
full_title: "LITESHIELD: Secure Containers via Lightweight, Composable Userspace μKernel Services"
authors: [Kaesi Manakkal, Nathan Daughety, Marcus Pendleton, Hui Lu]
venue: ATC
year: 2025
tags: [containers, isolation, microkernel, userspace, sandbox]
source_pdf: "[[atc2025-manakkal.pdf]]"
source_md: "[[atc2025-manakkal]]"
---

# LITESHIELD: Secure Containers via Lightweight, Composable Userspace μKernel Services (ATC 2025)

> **一句话总结**：把传统 guest kernel 拆成一组用户态 µkernel 服务，通过共享内存 IPC 服务 syscall，最终把 user-to-host 接口收敛到只有 22 个 syscalls（VM 是 60+ VMExits，container 默认 seccomp 是 250+），并保持与传统容器相当的性能。

## 问题

容器轻量但攻击面巨大（Linux 300+ syscalls，默认 seccomp 白名单仍 250+）。VM 隔离强但有 hypervisor + QEMU（QEMU 1.4M LoC）的额外攻击面与性能开销。Firecracker、gVisor、LightVM 等 minimization 方法仍维持完整 guest kernel，且“一刀切”的 guest kernel 难以适配多样化 microservice 需求。

## 核心方法

LiteShield 把 guest kernel 拆成 userspace **µkernel services**，guest application 与服务之间走 shared-memory IPC（基于 polling thread，类似 RDMA）：

- **Strong isolation via thin interface**：guest 应用通过 seccomp 默认禁止所有直接 syscall，只能通过 IPC 与 µkernel services 通信；µkernel services 自身也用严格 seccomp profile 限制到 22 个 syscalls。
- **Delegable vs non-delegable syscalls**：可委派的 syscall（read、open、socket 等）通过 IPC 重定向；不可委派的（fork、mmap、futex 等）通过 ptrace 拦截、由 core µkernel service 仲裁后在原进程执行。
- **POSIX 兼容**：用 LD_PRELOAD + libsyscall_intercept 在不修改 binary 的前提下注入拦截库，支持 legacy 应用。
- **Composable services**：移植 f-stack 作为用户态网络栈（仅 400+ LoC），自研 ext2-like 用户态文件系统。
- 总实现 ~7000 LoC C/C++，去掉了 hypervisor 与 QEMU。

详细 syscall 分类与 IPC 机制见 [[atc2025-manakkal]]。

## 关键结果

- User-to-host 接口仅 22 个 syscalls，对比 KVM-based VM 的 60+ VMExits 和 container 默认 250+ seccomp 白名单
- getpid 延迟显著低于 gVisor，read（4GB 文件 1B/block）超过 native（用户态 fs 优化）
- ptrace 仲裁开销 15–35µs（mmap/futex 这类轻量 syscall 占比 98%+），但调用频率低
- f-stack UDP/TCP 性能优于所有对比方案；fio 直接 IO 大块写优于 KVM/native；Redis YCSB 因 IPC 替代 syscall 反超 native

## 相关

- **相关概念**：[[Container]]、[[Microkernel]]、[[seccomp]]、[[ptrace]]、[[Userspace-Networking]]
- **同类系统**：[[gVisor]]、[[Firecracker]]、[[LightVM]]
- **同会议**：[[ATC-2025]]
