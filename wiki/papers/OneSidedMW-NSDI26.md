---
type: paper
name: OneSidedMW
full_title: "OneSidedMW: Managing Disaggregated Memory Efficiently, Flexibly, and Securely with RNIC Offloading"
authors: [Zixuan Wang, Jinyu Gu, Xingda Wei, Yubin Xia]
venue: NSDI
year: 2026
tags: [disaggregated-memory, rdma, memory-window, rnic-offloading, isolation]
source_pdf: "[[nsdi2026-wang-zixuan.pdf]]"
source_md: "[[nsdi2026-wang-zixuan]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-17
---

# OneSidedMW：用 RNIC offload 管理解聚内存（NSDI 2026）

> **原题**：OneSidedMW: Managing Disaggregated Memory Efficiently, Flexibly, and Securely with RNIC Offloading

> **一句话总结**：ODRP 的 RNIC 地址翻译让每次访问变慢，RPC-MW 又依赖弱 MNode CPU；OneSidedMW 让 RNIC 直接 bind/unbind type-2 memory window，并以 QP/MW grouping 和管理—访问 QP 分离保留多 QP 性能与隔离，在 KV store 中比 RPC-MW 最高快 10.6 倍、swap workload 比 ODRP 最高快 32.3%。

## 问题与动机

解聚内存需要同时满足细粒度分配、one-sided access、MNode 低 CPU、variable-size I/O 和跨租户隔离。MR registration 迫使系统用大块分配，RPC-MW 的通知路径会饱和 MNode CPU；[[ODRP-NSDI25]] 虽把管理完全下沉 RNIC，却把 translation WR 放在每次 access 上，并绑定 4 KiB swap 语义。

论文的核心转向是：RNIC offload 不再模拟完整 page table，而只负责控制面上的 type-2 MW bind/unbind；正常数据访问恢复原生 RDMA READ/WRITE。

## 关键观察 / 隐含假设

- **观察 1**：type-2 MW bind/unbind 比 MR registration 轻量，又由硬件把 MW 固定到特定 QP，能兼顾细粒度与强隔离（§2.2、§3）。
  - **依赖假设**：commodity RNIC 暴露可由预装 WR 动态改写的 BIND MW 字段。
- **观察 2**：多个 MW 可以绑定同一 memory chunk，因此可让不同 QP 分别承载 latency-sensitive 与 background access（§4.1）。
- **观察 3**：管理请求远少于 access；只有少数 QP 需要 offloaded chain。96 个带 offload 的 QP 会让 READ latency 增加 12.6%（§3.2），支持 management/access 分离。
- **假设 1**：type-2 MW/QP binding 是足够强的租户边界；threat model 信任 MNode 与 RNIC，不覆盖侧信道或 firmware bug。

## 核心方法

MNode 把 memory 划为可配置 chunk，每个 chunk 预分配一组 type-2 MW；MWTable 保存 address/rkey，free MW queue 管理未分配 group。CN 通过 Alloc QP 触发 RNIC WR chain，chain pop entry、bind MW group 到多个 Access QP，并返回 metadata。

**QP and MW Grouping**把多个 MW 绑定到同一 chunk，使同一数据可通过多个硬件隔离的 QP 访问。**Management-Access QP Separation**只在少量 Alloc/Free QP 上安装 offloaded logic，通过改 BIND WR 的 qpn 字段把 MW 分配给普通 Access QP。

free chain 先 unbind 固定分配给 Free QP 的第一个 MW，以硬件 QP check 验证释放者身份，再回收整个 group。allocation owner 和 hardware counter 支持 crash reclamation 与配额控制。

## 设计取舍

- **取舍 1**：每个 chunk 配多个 MW 换多 QP 隔离和并行，代价是 RNIC MW metadata 数量与初始化成本增长。
- **取舍 2**：swap 集成用 1 MiB allocation 而非 ODRP 的 4 KiB，换更低管理频率；利用率不一定达到严格 100%。
- **边界条件**：实验使用 ConnectX-5、Linux 4.15、1 MN+6 CN；MW 数量、on-chip cache 与现代 RNIC 行为可能不同。

## 实验与结果

- 100 Gbps ConnectX-5、1 MN+6 CN；集成 Fastswap 与 RACE hash，比较 Static-MR、RPC-MW type-1/type-2 和 ODRP（§6）。
- KV workload 中，2 KiB allocation 可回收 81.1% MN memory、吞吐 overhead 18.4%；相比 RPC-MW 吞吐最高 2.71 倍，扩展场景最高 10.6 倍（图 6及§6.1）。
- OneSidedMW P99 仅比 Static-MR 高 10–15 μs；RPC-MW CPU 饱和时 P99 达其 5.26 倍（图 6）。
- swap workload 中，相比 Static-MR memory utilization 最高 2.38 倍、真实应用 overhead 不超过 6.3%；比 ODRP 最高快 32.3%、比 RPC-MW 最高快 21.5%（§1、§6.2）。
- grouping 与 QP separation 分别处理 request interference 和 offload resource contention；论文报告 96 个 offload QP 会使 one-sided READ latency 增加 12.6%（§3.2）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 管理 offload 与原生 access 可以解耦 | §6：swap/KV 两种集成均优于 ODRP/RPC-MW | ConnectX-5、单 MN | 强 |
| type-2 MW 同时提供细粒度和隔离 | §4.4 安全分析、图 6 性能 | 非形式证明，可信 RNIC | 中强 |
| 方案能泛化到多类 DM runtime | Fastswap 与 RACE 两个 case | 仅两类 prototype | 中 |

## 批判性分析

### 论证链条

OneSidedMW 直接回应 ODRP 暴露的固定粒度和每次翻译成本，形成清楚的工作演进。两项 QP 技术分别由测得的 head-of-line blocking 与 offload resource contention 支撑，不是无测量的复杂化。

### 假设压力测试

若应用只需单 QP、小规模或粗粒度长寿命 allocation，grouping 的收益可能抵不过 MW metadata；若 RNIC 限制 type-2 MW 数量或 BIND throughput，细粒度 chunk 会先耗尽 control resource。

### 实验可信度

同时测 throughput、memory efficiency、P99 和 MNode CPU，并覆盖 swap/object runtime，证据比只做 microbenchmark 完整。硬件和软件栈较旧，跨 vendor 与大规模 rack-level pooling 未验证。

### 系统性缺陷

empty queue、CN crash、配额和 DoS 最终仍依赖 MNode CPU control plane。QP/MW group configuration 暴露新的调参面；RNIC 的错误诊断、reset 后恢复、metadata persistence 未系统评估。

## 局限与后续工作

- **局限 1**：只验证单 MN，且缺少 RNIC reset、link failure 和 malicious request 的 fault injection。
- **局限 2**：MW group 的容量与 on-chip resource 成本没有跨型号测量。
- **后续工作 1**：在多代 RNIC 上测 `chunk size × MW group size × QP count` 的性能/容量边界。
- **后续工作 2**：将 ODRP 与 OneSidedMW 统一成可按 workload 选择 page translation 或 MW capability 的远端内存 API。

## 相关

- **相关概念**：[[RDMA]]、disaggregated memory、memory window
- **同类系统**：[[ODRP-NSDI25]]
