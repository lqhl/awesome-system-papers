---
type: paper
name: Sereno
full_title: "Inference in the Shadows: Taming Memory Bandwidth Contention in Mobile LLM Inference with Sereno"
authors: [Tong Xin, Xinrui Shi, Mingkai Dong, Zeyu Mi]
venue: OSDI
year: 2026
tags: [mobile-systems, llm-inference, memory-bandwidth, qos, speculative-decoding]
source_pdf: "[[osdi26-xin.pdf]]"
source_md: "[[osdi26-xin]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 缓解移动端 LLM 推理内存带宽争用（OSDI 2026）

> **原题**：Inference in the Shadows: Taming Memory Bandwidth Contention in Mobile LLM Inference with Sereno

> **一句话总结**：mobile SoC将NPU memory traffic设为高优先级，使后台LLM只降约1%吞吐却让前台jank +153%；Sereno把speculative decoding改作细粒度yield points，检测争用后让出带宽，平均jank降58.5%、LLM throughput反增26.4%。

## 问题与动机

on-device LLM常以notification/agent burst在后台运行，与UI CPU/GPU共享UMA DRAM。25 apps实验显示前台aggregate jank +153%，而LLM prefill/decode仅降1.01%/1.64%；根因不是compute/cache，而是历史上为media accelerator设置的NPU high-priority memory QoS被best-effort LLM继承。

## 关键观察 / 隐含假设

- **观察 1**：性能或安全瓶颈并非只由资源容量决定，还取决于数据布局、执行粒度或信任边界。
- **观察 2**：论文提出的细粒度控制机制可以隔离主要开销，同时保留保守回退以维持正确性。

## 核心方法

Sereno借speculative decoding把一次长NPU inference拆成draft/verify边界，可在不丢progress处yield。runtime监测foreground activity/memory contention，动态暂停或调节speculation，让CPU/GPU先获得bandwidth；无争用时保持larger speculative work提高[[LLM|LLM]]吞吐。无需hardware QoS修改。

## 实验与结果

- commercial smartphones、25 popular apps：foreground jank最高降92.6%、平均58.5%。
- LLM throughput最高+67.9%、平均+26.4%，来自更合适speculation/less destructive contention。
- 相对vanilla speculative decoding，jank最高低72.1%，性能只低6.2%。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 核心机制改善了论文所针对的主要瓶颈 | §6 的端到端结果与组件拆解 | 论文所测平台、模型与工作负载 | 强 |
| 机制可迁移到更广泛环境 | §6 的扩展性或敏感性实验 | 尚未覆盖所有硬件与生产条件 | 中 |

## 批判性分析

### 论证链条

论文揭示优先级反转式asymmetry，机制证据很强。Sereno以软件yield绕过硬件QoS，但只适合可speculate/可切分model；draft acceptance低时yield粒度与额外计算代价恶化。前台识别和jank反馈迟滞可能使短burst已错过frame deadline。

### 假设压力测试

核心假设一旦不成立，收益会下降或触发保守回退；部署前应覆盖负载漂移、资源争用和极端输入。

### 实验可信度

实验支持主要机制，但硬件、模型与工作负载范围限定了结论的外推能力。

## 局限与后续工作

- 与SoC vendor硬件bandwidth QoS/priority demotion比较。
- 扩展不同NPU、model、thermal/energy与连续foreground workloads。
- 联合frame scheduler做deadline-aware而非reactive yielding。

## 相关

- **相关概念**：[[Speculative-Decoding]]、[[Memory-Bandwidth]]、[[Quality-of-Service]]、[[Unified-Memory]]
- **同会议**：[[OSDI-2026]]
