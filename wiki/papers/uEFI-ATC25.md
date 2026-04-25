---
type: paper
name: uEFI
full_title: "µEFI: A Microkernel-Style UEFI with Isolation and Transparency"
authors: [Le Chen, Yiyang Wu, Jinyu Gu, Yubin Xia, Haibo Chen]
venue: ATC
year: 2025
tags: [security, uefi, firmware, microkernel, isolation]
source_pdf: "[[atc2025-chen-le.pdf]]"
source_md: "[[atc2025-chen-le]]"
---

# µEFI: A Microkernel-Style UEFI with Isolation and Transparency (ATC 2025)

> **一句话总结**：把 [[UEFI]] firmware 模块按微内核方式 deprivilege 到 user mode + 独立地址空间沙箱，靠 trampoline 注入和 protocol 离线分析做透明 cross-module 调用，对未修改的 binary 模块也能跑，整体 boot 阶段开销仅 1.91%。

## 问题

[[UEFI]] Secure Boot 只能验签名，不防签名模块本身的漏洞：

- 2024 UEFI CVE 中 31.4% 是 memory safety、30.8% 是 improper input validation；
- BlackLotus（曾在地下论坛 5,000 美元卖）等 bootkit 利用合法签名的 Windows bootloader 漏洞绕开 Secure Boot；
- EDK2 代码量 2018-2025 涨 9×，UEFI Forum 365 厂商，模块共享地址空间，一个漏洞污染整个 firmware；
- 模块都在 SMM / EL1 高权限下执行；access control 粗粒度。

挑战：UEFI 模块大多以 binary 形式（option ROM）发布，必须透明；callout 通过运行时动态发现的 protocol pointer，静态分析不够；模块间无标准化数据格式。

## 核心方法

**µEFI** 借鉴微内核思想 + 利用 UEFI 三个独特属性（动态接口发现、单线程、协议预定义）：

- **Shadow service**：替换 system table，把核心服务调用变成 syscall，加 service-level + protocol-level 两层 [[seccomp]]-style 访问控制（按模块 GUID 显式声明 / 启发式从首个非通用协议判断模块类型）；
- **Trampoline injection**：模块拿到的协议接口是动态生成的 trampoline（read-only），调用时被 redirect 到 sandbox manager，避免 IPC 改造；三类 trampoline 分别用于 sandbox callout、core 调 sandbox、callback 自动返回；
- **Interface proxy + protocol database**：离线 analyzer 解析 EDK2 协议头文件抽 type / function / parameter 信息存表；运行时 lazy 查表做参数验证（pointer 是 buffer / array / handle？）；用 **parameter pairing** 启发式（命名模式 + 函数注释 + LLM）配对 buffer 与 size 参数；自动跨地址空间复制数据。

威胁模型：信任 UEFI 核心，不信任后续加载的所有模块（即使签名）。

## 关键结果

- 在 QEMU/KVM (x86_64) 和 Raspberry Pi 4B (AArch64) 上原型实现于 EDK2。
- 6 个真实 UEFI 模块（EnglishDxe / FAT / DiskIo 等）在沙箱内跑无须改动。
- UEFI boot 阶段总开销仅 **1.91%**。
- Parameter pairing 仅 <2.5% void* 参数无法自动解析。

## 相关

- **相关概念**：[[Microkernel]]、[[UEFI]]、[[Secure-Boot]]、[[seccomp]]、[[Driver-Isolation]]
- **同类系统**：[[KSplit]]、[[Nooks]]
- **同会议**：[[ATC-2025]]
