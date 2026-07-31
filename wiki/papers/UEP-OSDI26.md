---
type: paper
name: UEP
full_title: "UEP: Portable Expert-Parallel Communication"
authors: [Ziming Mao, Yihan Zhang, Chihan Cui, Zhen Huang, Kaichao You, et al.]
venue: OSDI
year: 2026
tags: [mixture-of-experts, expert-parallelism, rdma, communication-library, portability]
source_pdf: "[[osdi26-mao-ziming-uep.pdf]]"
source_md: "[[osdi26-mao-ziming-uep]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 可移植的专家并行通信（OSDI 2026）

> **原题**：UEP: Portable Expert-Parallel Communication

> **一句话总结**：UEP不让GPU直接操作vendor-specific NIC MMIO，而把compact token-routing command经高吞吐GPU–CPU channel交给多线程proxy发GPUDirect RDMA，并用immediate data补ordering；支持成本由GPU×NIC组合降为按GPU适配，EFA dispatch/combine最高2.1×。

## 问题与动机

DeepEP式GPU-initiated RDMA适合细粒度[[MoE|MoE]] token dispatch，但要求GPU kernel理解NIC driver/MMIO与ordering，NVIDIA+IB实现难移植到AMD、AWS EFA、Broadcom等组合。CPU-initiated bulk collective又无法及时跟随GPU runtime routing decision。

## 关键观察 / 隐含假设

- **观察 1**：性能或安全瓶颈并非只由资源容量决定，还取决于数据布局、执行粒度或信任边界。
- **观察 2**：论文提出的细粒度控制机制可以隔离主要开销，同时保留保守回退以维持正确性。

## 核心方法

UEP保留GPU产生token-level routing command，却只把紧凑descriptor推给CPU shared queue；pinned multithreaded proxy通过portable libibverbs发GPUDirect RDMA。GPU–CPU channel批处理/并行化以承受高message rate。对缺少特殊ordering的NIC，UEP用RDMA immediate data和software protocol模拟dispatch/combine所需arrival/completion语义。

这一架构将NIC适配留在标准CPU verbs层，GPU侧只需实现channel，理论支持m GPU+n NIC为O(m) GPU工作加既有NIC driver，而非O(m×n)垂直组合。假设host CPU cores可专用于proxy且不成为瓶颈。

## 实验与结果

- 实现在NVIDIA/AMD GPU与AWS EFA/Broadcom NIC组合，证明不依赖单一vendor stack。
- EFA上dispatch/combine throughput比最佳existing EP solution最高2.1×。
- NVIDIA+EFA的SGLang token throughput最高+40%；16-node AMD+Broadcom上DeepSeek-V3 training throughput相对Primus/[[Megatron|Megatron-LM]]最高+45%。
- high-throughput/low-latency mode与不同message/token规模展示proxy/channel扩展性。

## 论断—证据表

| 论断 | 证据 | 边界 | 置信度 |
|---|---|---|---|
| CPU proxy可保留fine-grained EP性能 | microbenchmark | EFA/Broadcom | 强 |
| 架构跨GPU/NIC vendor | 四类组合 | 仍依赖verbs/GPUDirect | 强 |
| 改善真实training/serving | SGLang/DeepSeek-V3 | 两个平台 | 强 |
| 支持成本降为O(m) | architecture argument | NIC均有portable verbs | 中 |

> **证据定位**：端到端结果与组件消融见 §6。

## 批判性分析

### 论证链条

UEP以少量CPU换掉vendor lock-in，是“worst-is-better”式边界重画。CPU proxy会消耗cores、跨[[NUMA|NUMA]]并受OS jitter影响；更快GPU/NIC或更细token可能让queue成为瓶颈。portable libibverbs也不保证所有NIC具有相同atomic/ordering/error语义，software emulation增加correctness surface。

### 假设压力测试

核心假设失效时，系统可能退化到基线或暴露额外开销；极端负载与故障条件需要单独验证。

### 实验可信度

实验支持主要设计论断，但平台与工作负载范围限定了可推广性。

## 局限与后续工作

- 报告CPU core/energy成本及host oversubscription下tail。
- 扩展更多NIC、failure/retry/congestion control与large-scale topology。
- 形式化验证software-emulated ordering与GPU queue memory model。

## 相关

- **相关概念**：[[Expert-Parallelism]]、[[GPUDirect-RDMA]]、[[Mixture-of-Experts]]、[[RDMA]]
- **相关系统**：[[DeepEP]]、[[SGLang]]、[[Megatron-LM]]
- **同会议**：[[OSDI-2026]]
