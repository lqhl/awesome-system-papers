---
type: paper
name: LMetric
full_title: "Simple is Better: Multiplication May Be All You Need for LLM Request Scheduling"
authors: [Dingyan Zhang, Jinbo Han, Kaixi Zhang, Xingda Wei, Sijie Shen, et al.]
venue: OSDI
year: 2026
tags: [llm-serving, request-scheduling, kv-cache, load-balancing]
source_pdf: "[[osdi26-zhang-dingyan.pdf]]"
source_md: "[[osdi26-zhang-dingyan]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 乘法即可的 [[LLM|LLM]] 请求调度指标（OSDI 2026）

> **原题**：Simple is Better: Multiplication May Be All You Need for LLM Request Scheduling

> **一句话总结**：LMetric用“路由后新增prefill tokens × instance当前batch size”作score，同时编码KV$ locality和load，比较时线性组合的权重可约掉，无需调参；相对vLLM mean TTFT/TPOT降92%/24%，生产scheduler降39%/51%。

## 问题与动机

只负载均衡忽略prefix KV hit，只追KV locality又把请求堆在同instance；linear weighted score需按model/hardware/workload反复调参或simulation。

## 关键观察 / 隐含假设

- new prefill tokens近似请求在instance的额外工作。
- current batch size近似排队/load pressure。
- 两指标相乘在pairwise comparison中自然自适应尺度，无显式weight。

## 核心方法

router对每instance计算uncached input tokens和batch size的乘积，选最小score；扩展规则处理SLO、autoscaling与KV transfer。实现名LMetric/LMetric*，保持O(instances)简单决策。

## 实验与结果

- **设置**：16-GPU real traces与数百GPU production，对比vLLM-v1、Preble、llm-d、production scheduler，以mean/P99 TTFT/TPOT为指标（§6）。
- 相对vLLM mean TTFT -92%、TPOT -24%；相对production scheduler -39%/-51%。
- 另一个trace P99 TTFT/TPOT下降45%/16%。

## 论断—证据表

| 论断 | 证据 | 边界 | 置信度 |
|---|---|---|---|
| multiplication兼顾cache/load | §6、图 28 | homogeneous replicas | 强 |
| 无调参可生产部署 | §6.3 | 单model clusters | 强 |

## 批判性分析

### 论证链条

两项indicator都有直接work解释，生产结果证明简单score不是只赢synthetic。

### 假设压力测试

heterogeneous GPU/model、不同decode length和remote KV transfer会使batch size/uncached tokens不再等价于cost。

### 实验可信度

real traces与production强；未覆盖multi-model heterogeneous fleet，简单性边界明确。

## 局限与后续工作

- 加入heterogeneous capacity与predicted output而保持无调参。
- 分析adversarial prefix hotspot和fairness。

## 相关

- **相关概念**：[[Request-Scheduling]]、[[KV-Cache]]、[[Load-Balancing]]
- **相关系统**：[[vLLM]]、[[Preble]]、[[llm-d]]
- **同会议**：[[OSDI-2026]]
