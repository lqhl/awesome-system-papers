---
type: paper
name: AEGIS
full_title: "Safeguarding LLM Training at Scale: Online SDC Detection and Insights from 35 Million GPU Hours"
authors: [Kinman Lei, Liyan Zheng, Xiang Li, Hongmin Chen, Yun Zhang, et al.]
venue: OSDI
year: 2026
tags: [distributed-training, silent-data-corruption, gpu-reliability, fault-detection, operational-systems]
source_pdf: "[[osdi26-lei.pdf]]"
source_md: "[[osdi26-lei]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 保护大规模 LLM 训练的在线 SDC 检测（OSDI 2026）

> **原题**：Safeguarding LLM Training at Scale: Online SDC Detection and Insights from 35 Million GPU Hours

> **一句话总结**：AEGIS 用 cSensor–cVerifier 抽象把inline廉价感知与lazy确定性验证解耦，并利用LLM MatMul/高精度累加特性设计校验；3,500万GPU-hours生产部署只增加0.86% overhead，发现18起真实SDC和13块faulty GPUs。

## 问题与动机

Silent Data Corruption不会触发ECC/fail-stop，却可污染gradient、loss和最终模型；万卡训练中单点微小错误会经collective传播。offline diagnostics必须停训且无法捕获偶发故障，在线冗余计算代价高，loss/outlier heuristic又有false positive与漏报。目标是在持续训练中获得高coverage、可确认、低overhead检测。

## 关键观察 / 隐含假设

- 感知异常和证明corruption无需在同一critical path完成：cSensor只保留minimal payload，cVerifier可排队、重放或更强校验（§3/§5）。
- [[LLM|LLM]]训练包含大量结构化MatMul，modern GPU用高精度accumulation；row/column checksum、自等价重复等algorithmic invariant可检测算术bit flip。
- 不同operator/precision的保护收益不同，dynamic sampling可把overhead budget集中到风险高、可校验区域。
- replay要求输入与执行环境足够deterministic；永久/间歇硬件故障可能在验证时不复现。

## 核心方法

cSensor在训练critical path执行轻量checksum/fingerprint或self-equivalence check，并输出异常候选与验证所需数据。每种机制封装为vTask，由cVerifier异步排队执行确定性复算/row-column checksum，确认后evict GPU并从clean state恢复。Supplementary outlier warning覆盖算法校验未直接保护的信号。

实现集成production LLM stack，按MatMul类别、bfloat16/FP32 accumulation与sampling rate选择检测器；sampling rate近似线性调节overhead，使operator可在目标budget内扩大coverage（§5–§7）。

## 实验与结果

- ByteDance生产部署累计3.5×10^7 GPU-hours，发现18个SDC incidents、13个faulty GPUs，平均training overhead 0.86%（§7.2）。
- algorithmic detection在所测workload平均低overhead；row+column full configuration最大slowdown 2.1%，可用sampling调低。
- case study包含约10,000-GPU训练：SDC后gradient L2 norm与loss明显跳变，GPU evict/resume后恢复，说明failure impact真实。
- fault injection覆盖多precision/operator/bit perturbation，并分析检测blind spots；生产统计提供极少见SDC的频率与类型观察（§7.3–§7.6）。

## 论断—证据表

| 论断 | 证据 | 边界 | 置信度 |
|---|---|---|---|
| 两阶段抽象实现低overhead在线检测 | §7.2/7.4 | production LLM stack | 强 |
| 能发现真实SDC | 18 incidents/13 GPUs | 3,500万GPU-hours | 强 |
| algorithmic checksum有广泛coverage | fault injection | 所测MatMul/precision | 中 |
| overhead可按sampling budget调节 | §7.5 | 近似线性实验 | 强 |

## 批判性分析

### 论证链条

35M GPU-hours是罕见且关键的operational evidence；架构又把“快但不确定”与“慢但确证”分开，使机制能生产落地。论文不仅报告检测数，也承认不同bit/precision的coverage差异。

### 假设压力测试

checksum主要保护被instrument的MatMul，network、memory、optimizer、collective或control-flow corruption可能逃逸。intermittent SDC在lazy replay时消失会降低确认率。outlier signal也可能把数值不稳定误判为硬件故障。

### 实验可信度

实验数据支持主要设计论断，但平台与工作负载范围仍限制其普遍性。

### 系统性缺陷

发现18次不足以精确估计极低failure rate和硬件世代差异；生产数据不可公开复现。0.86%是选定sampling policy下的平均，不能等同完整coverage成本。检测后依赖checkpoint clean与恢复系统，否则corrupted state可能已持久化。

## 局限与后续工作

- 扩展到collective/network/HBM与optimizer state端到端data integrity。
- 联合checkpoint provenance，确保恢复点早于corruption propagation。
- 公开匿名化fault injection/replay corpus，比较不同GPU generation与模型结构。

## 相关

- **相关概念**：[[Silent-Data-Corruption]]、[[Algorithm-Based-Fault-Tolerance]]、[[Distributed-Training]]、[[Fault-Detection]]
- **相关系统**：[[Checkpoint-Restart]]
- **同会议**：[[OSDI-2026]]
