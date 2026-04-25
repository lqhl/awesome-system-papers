---
type: paper
name: FlexGuard
full_title: "FlexGuard: Fast Mutual Exclusion Independent of Subscription"
authors: [Victor Laforet, Sanidhya Kashyap, Călin Iorgulescu, Julia Lawall, Jean-Pierre Lozi]
venue: SOSP
year: 2025
tags: [locks, ebpf, scheduling, concurrency, oversubscription]
source_pdf: "[[3731569.3764852.pdf]]"
source_md: "[[3731569.3764852]]"
---

# FlexGuard: Fast Mutual Exclusion Independent of Subscription (SOSP 2025)

> **一句话总结**:用 [[eBPF]] hook 在内核 context switch 时精确检测锁持有者被抢占,把等待线程从 spin 转为 block——非 oversubscribed 下吞吐 1-6× 优于 POSIX,oversubscribed 下最多 5×,不再靠启发式 timeout。

## 问题

Spinlock 在非 oversubscribed 场景性能好,但线程数超过硬件上下文数时会"性能雪崩"——等待者 spin 占满 CPU,锁持有者被调度器抢占,临界路径无法推进,MCS 的临界段延迟可暴涨 4 个数量级。

已有混合方案(POSIX spin-then-park、Shuffle、MCS-TP、Malthusian、Antić 等)依赖启发式 timeout 或定期探测线程数,要么过早 block(损失 spin 优势)要么过晚 block(撞上 preemption)。根本问题在于把 OS 调度器当黑盒,只能间接推断 preemption。

## 核心方法

**Key insight**:通过 [[eBPF]] 挂钩 `sched_switch` tracepoint,内核每次 context switch 都同步暴露被抢占线程的 PC、栈、寄存器,能精确判断它是否在临界段内。

- **Critical-section detection**:eBPF hook 读出 preempted 线程的 PC,若落在已注册的 CS 范围内,就向锁 metadata 发信号。
- **Lock algorithm**:借鉴 Shuffle lock(MCS 队列 + TATAS fast path,每线程一个队列节点而非每线程每锁一个),但当检测到 CS preemption 后,所有当前 waiter 立即 block(通过 futex),让出 CPU 让持有者恢复运行;持有者返回后 waiter 被唤醒继续。
- **无需改内核**:完全靠 eBPF,可在现代 Linux 上部署。

## 关键结果

- 微基准、LevelDB、PARSEC Dedup、SPLASH2X Raytrace/Streamcluster:非 oversubscribed 下 1-6× 优于 POSIX;oversubscribed 下最多 5×。
- 非 oversubscribed 性能接近 MCS(spinlock 最优 baseline),oversubscribed 不雪崩,接近 pure blocking lock。
- 不依赖手调 timeout,subscription-agnostic。

## 相关

- **相关概念**:[[eBPF]]、[[MCS-Lock]]、Spinlock、Futex、Oversubscription
- **同类系统**:Shuffle lock、MCS-TP、Malthusian(Dice)、u-SCL
- **同会议**:[[SOSP-2025]]
