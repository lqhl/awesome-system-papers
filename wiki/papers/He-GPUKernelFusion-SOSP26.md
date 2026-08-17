---
type: paper
name: He-GPUKernelFusion
full_title: "Taming Dynamism on GPUs: Cross-SM Kernel Fusion via SM Cooperation and Just-in-Time Reduction"
authors: [Jingkai He, Guangda Sun, Tianjian Li, Dong Du, Yubin Xia, Haibo Chen]
venue: SOSP
year: 2026
tags: [gpu, kernel-fusion, dynamic-workload, sm-cooperation]
source_pdf: ""
source_md: ""
review_status: needs-review
evidence_level: metadata-only
last_reviewed: 2026-08-17
external_url: "https://ipads.se.sjtu.edu.cn/pub/publication"
---

# 驯服 GPU 动态性：跨 SM Kernel Fusion（SOSP 2026）

> **原题**：Taming Dynamism on GPUs: Cross-SM Kernel Fusion via SM Cooperation and Just-in-Time Reduction

> **一句话总结**：IPADS 官方目录确认该论文被 SOSP 2026 接收，题名表明它用 SM cooperation 与 just-in-time reduction 处理动态 workload 下的跨 SM kernel fusion；截至 2026-08-17 未发现公开 PDF 或 abstract，因此不能确认具体机制、实验数据和适用边界。

## 问题与动机

论文题名将问题限定为动态 GPU workload 下的 kernel fusion。论文作者、题名和 venue 来自 IPADS 官方 publication 页面及第一作者主页；SOSP 2026 将于 2026-09-29 至 10-02 举行，当前没有可进入 raw layer 的公开全文，本页只保存可验证 metadata，不等同于论文评审。

## 关键观察 / 隐含假设

- **观察状态**：没有公开 abstract/full text，无法从原文抽取 workload measurement、bottleneck 或隐含假设。
- **metadata 线索**：研究主题属于动态 GPU workload 与 kernel fusion；标题明确给出跨 SM 协作（SM cooperation）和即时规约（just-in-time reduction）。

## 核心方法

公开 metadata 只给出机制名称，不足以确认它们如何工作。本文不会从题名推测同步协议、编译路径或硬件实现。

## 设计取舍

- **证据边界**：没有公开正文，无法比较 fusion coverage、compile overhead、runtime synchronization 和 portability。

## 实验与结果

截至 2026-08-17 没有可引用的 benchmark、baseline、metric 或结果数字。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 论文被 SOSP 2026 接收 | IPADS publication 与作者主页 | metadata only | 强 |
| 方法改善动态 GPU workload | 仅题名 | 无实验公开 | 弱 |

## 批判性分析

### 论证链条

全文未公开，无法判断 observation、design 与 result 是否闭合。

### 假设压力测试

无法确认“dynamism”指动态 shape、control flow、operator graph 还是 kernel resource variation。

### 实验可信度

没有公开实验材料，不能评价 benchmark、baseline 或统计稳定性。

### 系统性缺陷

fusion 的正确性条件、SM 间同步机制、硬件依赖和编程接口均不能从 metadata 判断。

## 局限与后续工作

- **局限 1**：本页只有 metadata，不含论文技术证据。
- **后续工作 1**：公开全文出现后下载到 `papers/sosp-2026/`，运行 MinerU，并按 `wiki-paper` 的 full-text 门槛重建本页。

## 相关

- **相关概念**：GPU、kernel fusion、dynamic workload
- **同类系统**：[[FlowANN-OSDI26]]、[[XSched-OSDI25]]
