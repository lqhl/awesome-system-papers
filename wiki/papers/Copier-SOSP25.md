---
type: paper
name: Copier
full_title: "How to Copy Memory? Coordinated Asynchronous Copy as a First-Class OS Service"
authors: [Jingkai He, Yunpeng Dong, Dong Du, Mo Zou, Zhitai Yu, Yuxin Ren, Ning Jia, Yubin Xia, Haibo Chen]
venue: SOSP
year: 2025
tags: [memory-copy, os-service, async, avx, dma, linux, harmonyos]
source_pdf: "[[3731569.3764800.pdf]]"
source_md: "[[3731569.3764800]]"
---

# How to Copy Memory? Coordinated Asynchronous Copy as a First-Class OS Service (SOSP 2025)

> **一句话总结**:Copier 把 memcpy 升级为**一级 OS 服务**，用 queue-based async 抽象 + AVX/DMA piggyback 调度 + 跨特权级 copy absorption，Redis 延迟加速 **1.8×**、比 SOTA zIO 快 **1.6×**，且对 ≥0.3KB 的内核拷贝和 ≥0.5KB 的用户拷贝都有效（zero-copy 方案通常要 ≥10-16KB 才有收益）。

## 问题

Memory copy 至今仍是系统性能大户：memcached、Redis、Protobuf、proxy、CoW handler 等场景中 copy 占用 up to 66.2% CPU cycle；谷歌数据中心 4-5% 周期耗在 copy；HarmonyOS 相机、音乐、浏览器等 copy 占 3-49%。

现有优化有三类，每类都有明显短板：

- **硬件加速 memcpy**：AVX SIMD 很强但内核不能用（保存/恢复寄存器几 KB 开销太高）；Intel I/OAT DMA 能降 CPU 但用户态难访问且小拷贝不合算。
- **Zero-copy 和 page remapping**：有 page 对齐要求、不支持多副本、有 TOCTTOU 攻击面、remapping 本身有成本——所以 Linux zero-copy send 官方建议 ≥10KB、zIO 要 ≥16KB，但实际 Twitter memcached 95% 请求 ≤10KB、AliCloud block 70% 在 4-10KB。
- **Function-based copy**：每次同步阻塞执行，错过 copy 和 use 之间的时间窗口。

作者的两个 insight：
1. **Copy-Use window**：数据被 bulk copy 后往往是 piece-wise 使用，两者之间有 2-10× of copy time 的间隔，可以 async 隐藏 copy 延迟。
2. **全局视角下的 copy 有可合并机会**：跨特权级的 K→I→D（kernel→input buffer→database）经常中间 I 大部分没被读——可以吸收成 K→D。

## 核心方法

Copier 用三组 per-client 队列（Copy / Sync / Handler Queue）+ 内核 Copier thread (基于 io_uring SQPOLL) 提供服务：

- **amemcpy + csync 原语**: 应用提交 async task 后继续执行，用 csync(addr, size) 按需 poll 等待。Copy task 被切分成 segment（细粒度 bitmap 描述符），允许 **copy-use pipeline**——还在拷后段时前段已可用。Sync Task 可以**提升优先级**（out-of-order execution）绕过 head-of-line blocking。
- **Piggyback 硬件调度**: AVX 小拷贝快、DMA 大拷贝省 CPU。Copier 的 dispatcher 把 DMA 子任务 piggyback 到 AVX 任务上并行跑，**不浪费 CPU 等 DMA**；对 <12KB 小任务还能跨 task 外部 piggyback (e-piggyback)，让 DMA 陪跑小拷贝。VA-PA 转换有 ATCache 缓存（Redis 地址复用率 >75%）。
- **Copy absorption**: 有 order dependency 追踪（syscall trap/return 作 barrier 指示符）+ data dependency 追踪（重叠内存区域），把 K→I→D 合并为 K→D。配合 segment 粒度的 **layered absorption**（只从最新源拷相应段，防止 I 中间被改的段被覆盖）和用户标记 **Lazy Copy Task**（只作 absorption 媒介，不真正执行）进一步减少实际拷贝。
- **资源隔离**: 新建 `copier` cgroup 控制器，用 copy length 作资源单位（不是 CPU 时间，因为 cache/TLB 状态影响执行时间）；CFS 风格调度保证公平。
- **Proactive fault handling**: 主动 walk VMA/page table 做地址转换，锁页防迁移，不靠硬件 page fault。
- **Toolchain**: libCopier (高/低级 API) + CopierSanitizer (debug) + CopierGen (自动化插入 csync 编译工具)

基于 Linux 和 HarmonyOS 5.0 落地。

## 关键结果

- **Redis**: 延迟 **1.8× 加速** vs baseline，**1.6×** vs zIO (SOTA)
- **Video decoding on phone**: 延迟最高降 **10%**
- send()/recv() syscall、Protobuf、Binder IPC、CoW fault handling 均有收益
- 适用门槛：kernel copy ≥0.3KB、user copy ≥0.5KB（有足够 Copy-Use window 时）；仅硬件收益则 kernel≥2KB/user≥12KB
- 商用 HarmonyOS 5.0 已集成（实验性）

## 相关

- **相关概念**:[[Memory-Copy]]、[[Zero-Copy]]、[[io-uring]]、[[DMA]]、[[AVX]]、[[IPC]]、[[Cgroup]]
- **同类系统**:[[zIO]]、[[Fastmove]]、[[L4]]、[[Arrakis]]、[[XRP]]
- **同会议**:[[SOSP-2025]]
