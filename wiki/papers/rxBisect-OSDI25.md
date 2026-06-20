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

> **一句话总结**：把 NIC Rx ring 拆成独立的空 buffer 分配环（Ax）与包接收环（Bx），使分配容量与接收容量解耦，软件仿真下吞吐相对 shRing / 默认 per-core ring 最高 +20%/+37%，尾延迟最多降 11×。

## 问题与动机

100 Gbps NIC 默认 per-core Rx ring 1Ki×1500B，I/O working set |Rx|=N×R×1500B 易超 LLC-per-core，[[DDIO]] 失效→包访问落主存→吞吐降、尾延迟爆。缩小 ring 丢包；shRing 共享 ring 需核间锁且在 RSS 倾斜（CAIDA trace 最大/最小比 325–433%）时饿死空闲核。根因：单 ring 纠缠「CPU 产空 buffer / NIC 消费」与「NIC 产包 / CPU 消费」两路 producer-consumer。

## 关键观察 / 隐含假设

- **观察 1**：|Rx| 下界由 ring 数量与大小决定，与软件处理速度脱钩——buffer 须整环轮转才能复用（Figure 2：R≥1024 超 LLC 后吞吐降 0.8×、延迟升 37×）。
  - **依赖假设**：DPDK run-to-completion、1500B MTU、ConnectX-5 类 100G NIC；stateful LB NF 代表 NF 类应用。
  - **可能失效场景**：小 packet（64B）I/O working set 小，问题减轻；socket 栈路径行为不同但论文引 prior work 称类似。
- **观察 2**：真实 trace 中 RSS 倾斜普遍，shRing 必须动态关闭→回退大 privRing——rxBisect 用 NIC 硬件跨核共享 Ax buffer 无软件锁。
  - **依赖假设**：NIC 可关联多 Ax 到一 Bx、跨 NUMA node 同 application；两阶段 allocator 支持跨核 free。
  - **可能失效场景**：需 NIC 固件/硬件支持 rxBisect 接口——论文为软件仿真，真硬件未部署。
- **假设 1**：Bx 保持 1Ki 吸收 burst，Ax 可缩小（如 128）因 rxBisect 跨核搬运空 buffer。
  - **证据强度**：中；仿真与 emulation fidelity 验证（仿真可能更差，结论保守）。

## 核心方法

**rxBisect 接口**：Ax ring（CPU→NIC 空 buffer）；Bx ring（NIC→CPU 包+消耗通知）。NIC 可从任意关联 Ax 取 buffer 填目标 Bx；跨核时 allocator 与 receiver 可不同，free 回全局 pool。

**软件侧**：RxBisect() 处理 Bx 通知、按 Ax index 补空 buffer（Listing 1 伪代码）。

**仿真框架**：对比 privRing、shRing、rxBisect；CAIDA NYC trace replay 测不平衡。

## 设计取舍

- **取舍 1**：仅改 Rx，Tx 不变——聚焦 I/O working set 主因。
- **取舍 2**：软件仿真非生产 NIC——换接口需硬件厂商采纳。
- **边界条件**：kernel-bypass/DPDK；100G 双 NIC 16-core 评测。

## 实验与结果

- vs 默认 privRing（1Ki）：吞吐最高 +37%；尾延迟最多降 11×（线速 vs 不达标时）。
- vs 理想化 shRing：不平衡 trace 下吞吐 +20%。
- Emulation fidelity：仿真吞吐最多低 12%、延迟最多高 94%——真硬件可能更好。
- LB NF：R=128 两 DDIO ways 内达线速；R 增大逐步恶化。

## Critical Analysis

### 论证链条

「DDIO working set 公式→纠缠是根因→拆 Ax/Bx」逻辑干净，与 queueing 理论（shRing 不平衡必丢包）一致。Insight 是 NIC 侧 cross-core buffer 共享 offload 同步——比 shRing 软件锁更根本。

### 假设压力测试

- **已证明**：仿真下不平衡 trace 优势显著；I/O working set microbenchmark 可复现。
- **可能失效**：真硬件 multi-Ax 策略不当仍可能饿死；极小 Ax 在极端 burst 下丢包；非 RSS 分发场景收益未知。
- **论文未覆盖**：生产 NIC 落地时间表；与 AF_XDP/IOVA 等新栈集成；多 tenant NF 安全隔离。

### 实验可信度

Emulation 自证可能偏悲观；双 NIC 16-core 环境具体。缺与 Intel CR/completion ring 已有优化的组合测试。

### 系统性缺陷

**关键**：尚未硬件实现，产业采纳不确定；跨核 buffer free 依赖 allocator（+15 cycles 以内）；参数配置指南（§4.5）需 per-app tuning。

## 局限与 Future Work

- **局限 1**：软件仿真，非商用 NIC 产品。
- **局限 2**：仅 DPDK kernel-bypass 路径验证。
- **Future work 1**：硬件 rxBisect 原型与真线速 CAIDA replay。
- **Future work 2**：与 shRing 混合策略（动态 Ax 大小）及 socket 栈适配。

## 相关

- **相关概念**：[[DDIO]]、[[RDMA]]、RSS、DPDK
- **同类系统**：shRing、PrivRing、Shinjuku、Shenango
- **同会议**：[[OSDI-2025]]