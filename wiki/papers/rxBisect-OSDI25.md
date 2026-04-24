---
type: paper
name: rxBisect
full_title: "Disentangling the Dual Role of NIC Receive Rings"
authors: [Boris Pismenny, Adam Morrison, Dan Tsafrir]
venue: OSDI
year: 2025
tags: [networking, nic, ddio, rx-ring, dpdk]
source_pdf: "[[osdi25-pismenny.pdf]]"
source_md: "[[osdi25-pismenny]]"
---

# Disentangling the Dual Role of NIC Receive Rings (OSDI 2025)

> **一句话总结**：把 NIC Rx ring 拆成独立的「空 buffer 分配 (Ax)」和「包接收 (Bx)」两条环，让分配容量与接收容量解耦，吞吐相对 shRing / 默认 per-core ring 分别 +20%/+37%，尾延迟最多降低 11×。

## 问题

100 Gbps NIC 的 per-core Rx ring 默认 1 Ki 条 × 1500 B 缓冲，每核 I/O 工作集超过 LLC-per-core 容量（约 1.5 MiB vs ~1.4 MiB LLC/core），使 [[DDIO]] 失效、包访问回落到主存，吞吐降、尾延迟爆。缩小 ring 会丢包；shRing 共享 ring 又要在核间加锁，且在负载不均（RSS 哈希倾斜的真实 trace 中最大/最小比 325–433%）时因排队理论注定饿死空闲核，论文显示这种「病态」不均衡在 CAIDA trace 中常见。

根因在于 Rx ring 把两件事硬糅到一个环里：CPU 当生产者、NIC 当消费者的「空 buffer 供给」，与 NIC 当生产者、CPU 当消费者的「满包投递」。缩其一必损其二，这是 shrink-or-share 困局的本质。

## 核心方法

rxBisect 重新设计 NIC-CPU 接口，把两个生产者-消费者结构拆开：

- **Allocation (Ax) ring**：每核维护，存空 buffer 指针；NIC 从任意与本 Bx ring 关联的 Ax ring 里消费 buffer。可以做得很小（如 128 条），决定 I/O 工作集大小。
- **Bisected reception (Bx) ring**：每核维护，NIC 往里写收到的包及「消费了哪个 Ax ring 的哪条 entry」的通知。保持默认 1 Ki 大小以吸收突发。

关键设计点：Bx ring 可关联多个 Ax ring，NIC 把「所有核的空 buffer 池」视作一个全局共享资源，由硬件无锁地跨核借用——软件不需要额外同步（这正是 shRing 的开销来源，硬件替软件承担了）。当接收核和分配核是同一个时，两条通知合并进一个 Bx descriptor。软件侧只要求 allocator 支持跨核分配/释放，这在 Linux 内核和 DPDK 的两级（shared pool + per-core cache）分配器里本就具备，rxBisect 对 alloc 调用平均延迟只比 privRing 多约 15 cycles。

作者用一个软件 NIC 框架做 emulation prototype，保守地量化 fidelity 后再拿 emulated rxBisect 和非 emulated baseline 对比——这是避免「自画像」的好做法。

## 关键结果

- 相对默认 per-core ring：吞吐 +最多 37%、延迟最多降 11×（rxBisect 能线速、baseline 不能的情况下）
- 相对理想化 shRing（RSS 不均衡时）：吞吐 +最多 20%，且 rxBisect 不会像 shRing 那样在不均衡时自动关闭
- 硬件侧包投递的 critical-path DMA 数量与 privRing / shRing 相同，不引入额外 latency
- Emulation 相对真实 NIC 的保守度：吞吐低至 −12%，延迟高至 +94%，证明对比结果是下界

## 相关

- **相关概念**：[[RDMA]]（同属 kernel-bypass 高速网络栈）、[[DDIO]]、[[DPDK]]
- **同会议**：[[OSDI-2025]]
