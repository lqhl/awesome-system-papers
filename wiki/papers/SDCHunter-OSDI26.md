---
type: paper
name: SDCHunter
full_title: "SDCs in the Wild: Characterizing and Diagnosing SDC-defective GPUs in Production LLM Training"
authors: [Wenxin Zheng, Wenxiao Wang, Yun Zhang, Mingcong Han, Bin Xu, et al.]
venue: OSDI
year: 2026
tags: [gpu, reliability, llm-training]
source_pdf: "[[osdi26-zheng.pdf]]"
source_md: "[[osdi26-zheng]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 生产 [[LLM|LLM]] 训练中的 GPU 静默数据损坏
> **原题**：SDCs in the Wild: Characterizing and Diagnosing SDC-defective GPUs in Production LLM Training

## 问题与动机

GPU silent data corruption（SDC）与软件 bug、数值不稳定表现相似；通用 GEMM stress test 会漏掉超过 60% 的缺陷设备，使工程师耗费数周排查错误方向。

## 关键观察 / 隐含假设

- 23 张缺陷 GPU 表明 SDC 会由老化产生，并非只发生在新硬件。
- 故障高度依赖具体 data 和 execution unit，ECC 与温度保护捕获不到 logic-level bit flip。
- 假设触发异常的原始 workload/input 可被保存并重放。

## 核心方法

[[SDCHunter]] 在集群中逐步隔离小型可疑 GPU group，再用触发故障的精确 training workload 和 input 做 execution replay；这把 diagnosis 从 generic synthetic test 转成 incident-specific differential replay。

## 实验与结果

ByteDance 生产部署中，SDCHunter 成功缓解 40 起 SDC incident；characterization 覆盖 23 张 SDC-defective GPU，而标准 synthetic method 漏检率超过 60%（§4–§7，表 5）。边界是可复现输入的大规模 LLM training incident。

## 论断—证据表

| 论断 | 证据 | 边界 | 置信度 |
|---|---|---|---|
| 通用 stress test 与真实 SDC 有语义差距 | 超过 60% 缺陷设备被漏掉 | §3 | 强 |
| exact replay 可用于生产定位 | 实际缓解 40 起 incident | §7 | 强 |

## 批判性分析

### 论证链条
生产样本先揭示 data/unit specificity，再由 exact replay 直接利用这一特性，设计由证据驱动。

### 假设压力测试
不可重复 transient fault、输入未保留、跨多 GPU 才触发的错误会削弱 replay 定位能力。

### 实验可信度
真实缺陷硬件和生产部署是罕见强证据；样本来自单一组织与 GPU fleet，分布外泛化有限。

## 局限与后续工作

- 需要跨代际故障数据库、低开销在线触发捕获，以及对 CPU、network、HBM 复合 SDC 的诊断。

## 相关

- [[OSDI-2026]]
- [[GPU-Reliability]]
- [[LLM-Training]]
