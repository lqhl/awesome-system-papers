---
type: paper
name: ProbeFS
full_title: "ProbeFS: Hierarchical DNA File Systems via Biochemical Content Addressability and Parallelism"
authors: [Ruihan Li, Yuankun Zhang, Mingkai Dong, Yaya Hao, Fei Wang, Chunhai Fan, Haibo Chen]
venue: SOSP
year: 2026
tags: [dna-storage, file-system, content-addressing, biochemical-parallelism]
source_pdf: ""
source_md: ""
review_status: needs-review
evidence_level: metadata-only
last_reviewed: 2026-08-17
external_url: "https://ipads.se.sjtu.edu.cn/pub/publication"
---

# ProbeFS：利用生化内容寻址与并行性的层级 DNA 文件系统（SOSP 2026）

> **原题**：ProbeFS: Hierarchical DNA File Systems via Biochemical Content Addressability and Parallelism

> **一句话总结**：IPADS 官方目录确认 ProbeFS 被 SOSP 2026 接收，题名显示它从 [[LiqSD-FAST25|DNA block device]] 继续推进到层级文件系统，并把 biochemical content addressability 与 parallelism 作为核心机制；截至 2026-08-17 尚无公开 PDF/abstract，无法确认接口、正确性和实验结果。

## 问题与动机

题名把问题限定为 DNA medium 上的 hierarchical file system。题名、作者和会议来自 IPADS 官方 publication 页面与 Mingkai Dong 个人 publication 页面；当前公开材料只有 metadata，因此本页不写方法细节或性能结论。

## 关键观察 / 隐含假设

- **观察状态**：无公开 abstract/full text，不能确认论文测得的 DNA access pattern、介质瓶颈或 filesystem workload。
- **metadata 线索**：工作对象是 hierarchical DNA file system；标题强调 biochemical content addressing 和 biochemical parallelism；作者团队延续 [[LiqSD-FAST25]] 路线。

## 核心方法

除题名给出的两个机制名外，没有足够证据说明 addressing format、directory representation、parallel execution 或 update protocol。

## 设计取舍

- **证据边界**：无法确认接口通用性、biochemical resource cost、failure handling 和 consistency model。

## 实验与结果

截至 2026-08-17 没有公开 benchmark、baseline、真实 DNA prototype 或性能数字。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| ProbeFS 被 SOSP 2026 接收 | IPADS 与作者 publication 页面 | metadata only | 强 |
| ProbeFS 优于既有 DNA storage | 仅题名 | 无实验公开 | 弱 |

## 批判性分析

### 论证链条

全文未公开，不能验证从 DNA observation 到 filesystem design 的推导。

### 假设压力测试

无法判断 content address 的编码、冲突处理、rename/update 语义和 crash consistency。

### 实验可信度

没有公开实验材料，不能评价其是否构建真实生化 prototype。

### 系统性缺陷

biochemical parallelism 对应 PCR、sequencing、synthesis 还是容器级并行仍未知。

## 局限与后续工作

- **局限 1**：本页只有 metadata，不含方法或实验的原始证据。
- **后续工作 1**：公开全文出现后下载到 `papers/sosp-2026/`，补 source_pdf/source_md 并按 full-text 模板重建。

## 相关

- **相关概念**：DNA storage、content addressing、file system
- **同类系统**：[[LiqSD-FAST25]]、[[SysSpec-FAST26]]
