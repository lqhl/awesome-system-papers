---
type: paper
name: StriaTrace
full_title: "StriaTrace: Efficient Tracing and Diagnosis for Online LLM Inference (Operational Systems)"
authors: [Haonan Wu, Yanqing Chen, Kun Qian, Xue Li, Jingbo Xu, et al.]
venue: OSDI
year: 2026
tags: [llm-serving, observability, tracing, performance-diagnosis, operational-systems]
source_pdf: "[[osdi26-wu-haonan.pdf]]"
source_md: "[[osdi26-wu-haonan]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 在线 [[LLM|LLM]] 推理的低开销追踪与诊断（OSDI 2026）

> **原题**：StriaTrace: Efficient Tracing and Diagnosis for Online LLM Inference (Operational Systems)

> **一句话总结**：StriaTrace平时只追踪同步点和critical path，检测异常时才打开详细telemetry，并以动态回归roofline+correlation定位瓶颈；相对alternatives tracing overhead降97.8%，生产中诊断数百异常、覆盖19类root causes。

## 问题与动机

[[LLM-Inference|LLM inference]]同时受TTFT/TPOT细粒度SLO约束；2K-instance现场平均正常但P99频繁越过10s/100ms。Nsight/TorchProfiler 10%–20% overhead无法continuous tracing，training诊断工具又不适合streaming request、[[Prefix-Caching|prefix cache]]和[[Disaggregation|P/D disaggregation]]的sporadic anomaly。

## 关键观察 / 隐含假设

- **观察 1**：性能或安全瓶颈并非只由资源容量决定，还取决于数据布局、执行粒度或信任边界。
- **观察 2**：论文提出的细粒度控制机制可以隔离主要开销，同时保留保守回退以维持正确性。

## 核心方法

StriaTrace用三原则限制常态成本：只trace key synchronization points、沿end-to-end critical path关联CPU/GPU/network events、仅异常窗口记录细节。它动态拟合regression-based roofline，按当前model/batch/hardware估计各stage合理上界，再用跨layer/instance/event correlation把偏差关联到root-cause category。

假设异常能被轻量signal及时触发且detail buffer保留前因；回归baseline需随software/model更新避免concept drift。

## 实验与结果

- tracing overhead相对full profiler/alternative降低97.8%，适合continuous deployment。
- 已用于development、testing与production release，诊断数百异常、19类root causes。
- 2K-instance cluster数据展示TTFT/TPOT tail，case studies覆盖GPU kernel、synchronization、cache/P-D及系统干扰。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 核心机制改善了论文所针对的主要瓶颈 | §6 的端到端结果与组件拆解 | 论文所测平台、模型与工作负载 | 强 |
| 机制可迁移到更广泛环境 | §6 的扩展性或敏感性实验 | 尚未覆盖所有硬件与生产条件 | 中 |

## 批判性分析

### 论证链条

Operational evidence强，按异常升级detail是合理的flight-recorder设计。但trigger漏报会失去最关键trace；correlation不是causality，多个共因可能误诊。19类taxonomy来自单一Alibaba stack，模型/硬件迁移后需要重新训练roofline与rules。

### 假设压力测试

核心假设一旦不成立，收益会下降或触发保守回退；部署前应覆盖负载漂移、资源争用和极端输入。

### 实验可信度

实验支持主要机制，但硬件、模型与工作负载范围限定了结论的外推能力。

## 局限与后续工作

- 发布匿名trace/root-cause corpus与diagnosis precision/recall。
- 处理concept drift和未知root cause，给出uncertainty而非强制分类。
- 联合自动mitigation闭环并验证不会因误诊扩大故障。

## 相关

- **相关概念**：[[Distributed-Tracing]]、[[LLM-Serving]]、[[Roofline-Model]]、[[Performance-Diagnosis]]
- **相关系统**：[[Nsight-Systems]]、[[PyTorch-Profiler]]
- **同会议**：[[OSDI-2026]]
