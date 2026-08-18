---
type: paper
name: StarfishOS
full_title: "StarfishOS: Revisiting Single System Image on CXL with State-Partitioned Microkernel"
authors: [Fangnuo Wu, Jingsheng Yan, Mingkai Dong, Wenjun Cai, Jingwei Xu, Tong Xin, Haibo Chen]
venue: SOSP
year: 2026
tags: [cxl, microkernel, single-system-image, state-partitioning, area/operating-systems]
source_pdf: ""
source_md: ""
review_status: needs-review
evidence_level: metadata-only
last_reviewed: 2026-08-17
external_url: "https://ipads.se.sjtu.edu.cn/pub/publication"
---

# StarfishOS：基于状态分区微内核重访 CXL 单系统映像（SOSP 2026）

> **原题**：StarfishOS: Revisiting Single System Image on CXL with State-Partitioned Microkernel

> **一句话总结**：IPADS 官方目录确认 StarfishOS 被 SOSP 2026 接收，题名表明它在 [[CXL]] 共享内存机器上用 state-partitioned microkernel 重新设计 single-system image；截至 2026-08-17 没有公开 PDF/abstract，无法判断状态切分、一致性协议、故障域与性能边界。

## 问题与动机

题名把问题限定为 CXL 环境中的 single-system image OS。题名、作者和会议由 IPADS、Fangnuo Wu 与 Tong Xin 的公开主页交叉确认；当前只有 metadata，本页不把题名中的架构词扩写成未经证实的设计。

## 关键观察 / 隐含假设

- **观察状态**：没有公开 abstract/full text，不能抽取 CXL latency、coherence、failure 或 scalability observation。
- **metadata 线索**：目标环境是 [[CXL]]，目标抽象是 single-system image，主要架构名是 state-partitioned microkernel。

## 核心方法

公开信息不足以说明 state 的划分单元、microkernel service、communication path 或 consistency protocol。

## 设计取舍

- **证据边界**：无法判断 state partitioning 在 locality、availability、migration 与 programming interface 之间的取舍。

## 实验与结果

截至 2026-08-17 没有公开硬件配置、baseline、metric 或性能结果。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| StarfishOS 被 SOSP 2026 接收 | IPADS 与两位作者主页 | metadata only | 强 |
| state partitioning 改善 CXL SSI | 仅题名 | 无实验公开 | 弱 |

## 批判性分析

### 论证链条

全文未公开，不能检验 CXL observation、microkernel design 与 end-to-end result 的关系。

### 假设压力测试

无法确认 state 按 node、service、object 还是 failure domain 分区，也不能判断 coherence 和 remote latency 假设。

### 实验可信度

没有公开实验材料，不能评价 baseline 与规模。

### 系统性缺陷

与 multikernel、传统 SSI、distributed shared memory 和 Linux CXL 路线的关系尚无全文证据。

## 局限与后续工作

- **局限 1**：本页只有 metadata，不含方法和实验原始证据。
- **后续工作 1**：公开全文出现后下载到 `papers/sosp-2026/`，补 MinerU markdown，并用 full-text 证据重建。

## 相关

- **相关概念**：[[CXL]]、microkernel、single-system image、disaggregated memory
- **同类系统**：[[vBPF-OSDI26]]、[[OneSidedMW-NSDI26]]
